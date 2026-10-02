BEGIN;

-- Fase 7.2: consumo de sessao no V2 ("uma sessao = um credito"), com a
-- politica A aprovada pelo proprietario (entregar e acertar depois): o registro
-- clinico nunca e bloqueado por falta de saldo. Esta e a Opcao B do desenho
-- (docs/psique-v2-fase7.2-desenho.md): uma funcao focada e SEPARADA do comando
-- grande (psique_v2_credit_command), que reusa o guarda de papeis de 042 e o
-- primitivo psique_v2_append de 038. A idempotencia vem da UNIQUE(organization_
-- id, idempotency_key) ja existente em credit_ledger (001). Nada aqui toca o
-- caminho V1: so carteiras credit_model='psique_v2' chegam a esta funcao.

-- 1) Dois eventos novos no ledger v2: SESSION_CONSUMPTION debita 1 credito sem
--    reserva (a sessao e um ato clinico atomico, nao uma analise com lease);
--    SESSION_PENDING marca a sessao a descoberto sem mover saldo (politica A).
ALTER TABLE credit_ledger DROP CONSTRAINT credit_ledger_event_type_check;
ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_event_type_check CHECK (event_type IN (
    'purchase','consumption','refund','adjustment','migration_opening',
    'TRIAL_GRANT','TRIAL_EXPIRATION','CREDIT_RESERVATION','CREDIT_CONSUMPTION',
    'CREDIT_RELEASE','CREDIT_RESTORE','MANUAL_ADJUSTMENT','CREDIT_PURCHASE',
    'SESSION_CONSUMPTION','SESSION_PENDING'));

-- 2) Semantica dos dois eventos novos, acrescentada ao contrato fechado do v2.
--    O resto do CHECK e copiado VERBATIM de 037 (o banco e a autoridade; se 037
--    mudar, este CHECK tem de acompanhar).
ALTER TABLE credit_ledger DROP CONSTRAINT credit_ledger_version_semantics;
ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_version_semantics CHECK (
    (ledger_version=1 AND event_type IN ('purchase','consumption','refund','adjustment','migration_opening')
        AND reserved_delta=0 AND reserved_after=0 AND analysis_source_id IS NULL
        AND reservation_id IS NULL AND original_consumption_id IS NULL AND funding IS NULL)
    OR (ledger_version=2 AND funding IS NOT NULL AND reserved_after<=balance_after AND (
        (event_type='TRIAL_GRANT' AND delta=10 AND reserved_delta=0 AND funding='TRIAL')
        OR (event_type='TRIAL_EXPIRATION' AND delta<0 AND reserved_delta=0 AND funding='TRIAL')
        OR (event_type='CREDIT_RESERVATION' AND delta=0 AND reserved_delta=1 AND reservation_id IS NOT NULL)
        OR (event_type='CREDIT_CONSUMPTION' AND delta=-1 AND reserved_delta=-1 AND reservation_id IS NOT NULL)
        OR (event_type='CREDIT_RELEASE' AND delta=0 AND reserved_delta=-1 AND reservation_id IS NOT NULL)
        OR (event_type='CREDIT_RESTORE' AND delta=1 AND reserved_delta=0 AND original_consumption_id IS NOT NULL
            AND reason IS NOT NULL AND length(trim(reason))>0)
        OR (event_type='MANUAL_ADJUSTMENT' AND delta<>0 AND reserved_delta=0 AND funding='PAID'
            AND reason IS NOT NULL AND length(trim(reason))>0)
        OR (event_type='CREDIT_PURCHASE' AND delta>0 AND reserved_delta=0 AND funding='PAID')
        OR (event_type='SESSION_CONSUMPTION' AND delta=-1 AND reserved_delta=0)
        OR (event_type='SESSION_PENDING' AND delta=0 AND reserved_delta=0)
    ))
);

-- 3) A funcao de cobranca de sessao. SECURITY DEFINER, fronteira unica: valida
--    GUC + membership ativo + papel clinico (reusa o guarda de 042), trava a
--    carteira, liquida pendencias antigas FIFO e entao cobra a sessao atual;
--    sem saldo, marca pendencia e NUNCA bloqueia.
CREATE FUNCTION psique_v2_session_charge(org uuid, member uuid, actor uuid, session_id text, note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE
    wallet organization_wallets%ROWTYPE; trial psique_trials%ROWTYPE;
    instant timestamptz; free integer; available integer; fund text;
    pend record; charged_now boolean:=false; pending_now boolean:=false;
    settled integer:=0; pending_total integer; sid text;
BEGIN
    sid:=trim(session_id);
    IF coalesce(sid,'')='' THEN RAISE EXCEPTION 'SESSION_ID_REQUIRED'; END IF;
    -- Contexto: a GUC tem de bater com os argumentos (o atendimento nao cobra
    -- em nome de outra organizacao/membro).
    IF froid_current_organization_id() IS DISTINCT FROM org OR
        froid_current_membership_id() IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'PSIQUE_CONTEXT_MISMATCH' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM organization_memberships m JOIN organizations o ON o.id=m.organization_id
        JOIN users u ON u.id=m.user_id WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
        AND m.status='active' AND u.status='active' AND o.status='active'
        AND o.organization_type IN ('solo','clinic')) THEN
        RAISE EXCEPTION 'PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED' USING ERRCODE='42501';
    END IF;
    PERFORM psique_v2_credit_command_roles(org, 'SESSION_CHARGE');

    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org FOR UPDATE;
    IF NOT FOUND OR wallet.credit_model<>'psique_v2' THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;
    instant:=clock_timestamp();
    PERFORM psique_v2_expire(org, actor, instant);
    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org;
    SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
    free:=CASE WHEN trial.status IN ('ACTIVE','EXHAUSTED') THEN
        trial.credits_granted-trial.credits_used-trial.credits_reserved-trial.credits_expired ELSE 0 END;
    available:=wallet.balance-wallet.reserved_balance;

    -- Ja cobrada? idempotente por session_id.
    IF EXISTS(SELECT 1 FROM credit_ledger WHERE organization_id=org
              AND idempotency_key='session:'||sid AND event_type='SESSION_CONSUMPTION') THEN
        RETURN jsonb_build_object('charged',true,'applied',false,'pending',false,
            'balance',wallet.balance,'available_balance',available,
            'pending_total',psique_v2_session_pending_total(org));
    END IF;

    -- FIFO: liquida as pendencias mais antigas primeiro, enquanto houver saldo.
    FOR pend IN
        SELECT substr(l.idempotency_key, length('session-pending:')+1) AS psid
        FROM credit_ledger l
        WHERE l.organization_id=org AND l.event_type='SESSION_PENDING'
          AND NOT EXISTS(SELECT 1 FROM credit_ledger c WHERE c.organization_id=org
                AND c.event_type='SESSION_CONSUMPTION'
                AND c.idempotency_key='session:'||substr(l.idempotency_key, length('session-pending:')+1))
        ORDER BY l.created_at, l.id
    LOOP
        EXIT WHEN available<1;
        fund:=CASE WHEN free>0 THEN 'TRIAL' ELSE 'PAID' END;
        PERFORM psique_v2_append(org,actor,'SESSION_CONSUMPTION',-1,0,'session:'||pend.psid,
            fund=>fund, explanation=>'SESSION_SETTLED');
        IF fund='TRIAL' THEN
            UPDATE psique_trials SET credits_used=credits_used+1 WHERE organization_id=org;
            free:=free-1;
        END IF;
        available:=available-1; settled:=settled+1;
    END LOOP;

    -- A sessao atual.
    IF available>=1 THEN
        fund:=CASE WHEN free>0 THEN 'TRIAL' ELSE 'PAID' END;
        PERFORM psique_v2_append(org,actor,'SESSION_CONSUMPTION',-1,0,'session:'||sid,
            fund=>fund, explanation=>coalesce(nullif(trim(note),''),'SESSION'));
        IF fund='TRIAL' THEN
            UPDATE psique_trials SET credits_used=credits_used+1 WHERE organization_id=org;
        END IF;
        charged_now:=true;
    ELSE
        -- Sem saldo: marca a pendencia uma unica vez e NUNCA bloqueia.
        IF NOT EXISTS(SELECT 1 FROM credit_ledger WHERE organization_id=org
                AND idempotency_key='session-pending:'||sid AND event_type='SESSION_PENDING') THEN
            PERFORM psique_v2_append(org,actor,'SESSION_PENDING',0,0,'session-pending:'||sid,
                fund=>'PAID', explanation=>'SESSION_OVERDRAWN');
        END IF;
        pending_now:=true;
    END IF;

    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org;
    RETURN jsonb_build_object('charged',charged_now,'pending',pending_now,'applied',true,
        'settled_pending',settled,'balance',wallet.balance,
        'available_balance',wallet.balance-wallet.reserved_balance,
        'pending_total',psique_v2_session_pending_total(org));
END $$;

-- Contagem de sessoes a descoberto ainda nao liquidadas (pendencia sem consumo).
CREATE FUNCTION psique_v2_session_pending_total(org uuid)
RETURNS integer LANGUAGE sql STABLE SET search_path=public,pg_temp AS $$
    SELECT count(*)::integer FROM credit_ledger l
    WHERE l.organization_id=org AND l.event_type='SESSION_PENDING'
      AND NOT EXISTS(SELECT 1 FROM credit_ledger c WHERE c.organization_id=org
            AND c.event_type='SESSION_CONSUMPTION'
            AND c.idempotency_key='session:'||substr(l.idempotency_key, length('session-pending:')+1));
$$;

REVOKE ALL ON FUNCTION
    psique_v2_session_charge(uuid,uuid,uuid,text,text),
    psique_v2_session_pending_total(uuid)
    FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION
        psique_v2_session_charge(uuid,uuid,uuid,text,text),
        psique_v2_session_pending_total(uuid)
    TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('047_psique_session_consumption');
COMMIT;
