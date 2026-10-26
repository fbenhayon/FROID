BEGIN;

-- 054: duas correcoes da revisao de 20/10/2026 (docs/revisao-pre-fase5.md).
--
-- 1. A cobranca V2 CONTA a sessao na cota sem recusar. A 052 levantava
--    PSIQUE_MEMBER_QUOTA_EXHAUSTED ao arquivar, e a politica A faz o
--    atendimento seguir com credit_charge="falhou" e tentar de novo na
--    proxima gravacao — que falhava para sempre: nao debitava, nao contava,
--    nao virava pendencia. Decisao do dono: a sessao que aconteceu conta e
--    debita mesmo acima da cota; quem barra e o portao de inicio (main.py).
--    Copia da 052 byte a byte, trocando o IF/RAISE por um comentario.
-- 2. psique_v2_scheduling_patients: o clinico recebe o nome so dos pacientes
--    atribuidos a ele (patient_assignments ativas) ou com atendimento dele;
--    os demais, identificador curto. A 053 dava a qualquer CLINICIAN o nome
--    de todos os pacientes ativos da organizacao, mais que o papel V1
--    professional (patients.read_assigned) permite. Devolve names_scope
--    ('all' | 'own' | 'none') para o painel explicar o que mostra.

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
        -- 054: nao recusa. A sessao aconteceu: conta e debita mesmo acima da
        -- cota (decisao do dono, 20/10/2026); quem barra e o portao de inicio.
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

CREATE OR REPLACE FUNCTION psique_v2_scheduling_patients(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb; com_nome boolean; eh_clinico boolean; escopo text;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    -- Nome para secretaria e administrador de todos; para o clinico, so dos
    -- pacientes atribuidos a ele ou com atendimento dele (decisao do dono,
    -- 20/10/2026: a 053 dava a qualquer clinico o nome de todos). O
    -- supervisor recebe so o identificador curto.
    com_nome:=psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN']);
    eh_clinico:=psique_v2_role_check(ARRAY['CLINICIAN']);
    escopo:=CASE WHEN com_nome THEN 'all' WHEN eh_clinico THEN 'own' ELSE 'none' END;
    SELECT coalesce(jsonb_agg(jsonb_build_object(
        'patient_id',p.id,
        'label',CASE WHEN com_nome OR (eh_clinico AND (
                EXISTS (SELECT 1 FROM patient_assignments pa WHERE pa.organization_id=org
                    AND pa.patient_id=p.id AND pa.membership_id=member AND pa.status='active')
                OR EXISTS (SELECT 1 FROM psique_appointments ap WHERE ap.organization_id=org
                    AND ap.patient_id=p.id AND ap.clinician_membership_id=member)))
            THEN p.full_name ELSE 'Paciente '||right(p.id::text,4) END)
        ORDER BY CASE WHEN com_nome THEN p.full_name ELSE p.id::text END),'[]'::jsonb)
    INTO result
    FROM patients p WHERE p.organization_id=org AND p.status='active';
    RETURN jsonb_build_object('patients',result,'with_names',escopo<>'none','names_scope',escopo);
END $$;

INSERT INTO schema_migrations(version) VALUES('054_cota_conta_e_paciente_do_clinico');
COMMIT;
