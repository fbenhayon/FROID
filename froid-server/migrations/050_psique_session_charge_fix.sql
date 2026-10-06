BEGIN;

-- 050: corrige a cobranca de uma sessao que ja estava pendente (revisao 06/10/2026).
--
-- Na 047, a fila FIFO de pendencias incluia a PROPRIA sessao sendo cobrada. Com
-- saldo >= 2, a fila a liquidava ('session:'||S) e o ramo da sessao atual gravava
-- 'session:'||S de novo: violava UNIQUE(organization_id, idempotency_key) e a
-- transacao inteira desfazia. Com saldo == 1, liquidava S na fila e respondia
-- "pendente" sobre uma sessao ja paga. A unica mudanca e excluir a sessao atual
-- da fila; o resto e a funcao da 047, byte a byte.

CREATE OR REPLACE FUNCTION psique_v2_session_charge(org uuid, member uuid, actor uuid, session_id text, note text)
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
          -- 050: a sessao atual NAO entra na fila; ela e tratada logo abaixo.
          AND substr(l.idempotency_key, length('session-pending:')+1) <> sid
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

INSERT INTO schema_migrations(version) VALUES('050_psique_session_charge_fix');
COMMIT;
