BEGIN;

-- 052: cota por membro na cobranca V2 (decisao do dono, 18/10/2026).
--
-- A regra: a sessao de um profissional so e recusada por DOIS motivos — o
-- limite que o responsavel lhe atribuiu (organization_member_quotas, 010) ou
-- o esgotamento dos creditos da clinica. O caminho V1 ja fazia isso; a
-- cobranca V2 (047/050) nunca consultou a cota. Esta migration regrava
-- psique_v2_session_charge copiando a definicao da 050 BYTE A BYTE e
-- acrescentando so a variavel e o bloco marcados "052" (teste de espelho em
-- tests/test_psique_member_quota_v2.py). Decisoes do dono: sessao pendente
-- por falta de saldo CONTA na cota (a sessao aconteceu); pool esgotado segue
-- deixando pendente, como o V2 faz hoje.

CREATE OR REPLACE FUNCTION psique_v2_session_charge(org uuid, member uuid, actor uuid, session_id text, note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE
    wallet organization_wallets%ROWTYPE; trial psique_trials%ROWTYPE;
    instant timestamptz; free integer; available integer; fund text;
    pend record; charged_now boolean:=false; pending_now boolean:=false;
    settled integer:=0; pending_total integer; sid text;
    quota_row organization_member_quotas%ROWTYPE; -- 052
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

    -- 052: cota por membro (regra do dono, 18/10/2026). A sessao conta na cota
    -- no momento em que e ACEITA — cobrada OU pendente —, porque aconteceu.
    -- Sem linha de cota para o membro, nada muda (pool da clinica). Conta uma
    -- so vez por session_id: uma sessao que ja ficou pendente e volta para
    -- liquidar nao conta de novo. A regra e a mesma do caminho V1 (010).
    SELECT * INTO quota_row FROM organization_member_quotas
        WHERE organization_id=org AND membership_id=member FOR UPDATE;
    IF FOUND AND NOT EXISTS(SELECT 1 FROM credit_ledger WHERE organization_id=org
            AND idempotency_key='session-pending:'||sid AND event_type='SESSION_PENDING') THEN
        IF quota_row.consumed_sessions + 1 > quota_row.quota_sessions THEN
            RAISE EXCEPTION 'PSIQUE_MEMBER_QUOTA_EXHAUSTED' USING ERRCODE='P0001';
        END IF;
        UPDATE organization_member_quotas
            SET consumed_sessions=consumed_sessions+1, updated_at=clock_timestamp()
            WHERE organization_id=org AND membership_id=member;
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

INSERT INTO schema_migrations(version) VALUES('052_psique_member_quota_v2');
COMMIT;
