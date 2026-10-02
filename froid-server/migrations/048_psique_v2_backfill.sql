BEGIN;

-- Fase 7.3: backfill NAO destrutivo de uma carteira V1 para a carteira unica
-- V2, preservando o saldo liquido e a trilha v1 (ao contrario do DELETE que a
-- conta demo usou). Decisoes do proprietario (02/10/2026): o saldo carregado e
-- PAID permanente (D2b); as pendencias V1 em aberto viram SESSION_PENDING V2
-- (D2c); e o sinal "ja comprou alguma vez" e carregado para o portao V2 de
-- inicio de sessao, que sera reexpresso na 7.4/7.5 (D2a). Mecanismo e piloto
-- agora; conversao em massa na janela da 7.4 (D2d).

-- 1) O sinal "ever_purchased" na carteira. Para uma org V2, o portao de inicio
--    de sessao (receita) precisa saber se ela ja comprou alguma vez; no V1 isso
--    vivia em session_credit_purchases (JSON). O backfill carrega o booleano; o
--    portao futuro combina esta coluna com a existencia de CREDIT_PURCHASE no
--    ledger v2. Default false: org nova nao comprou ate comprar.
ALTER TABLE organization_wallets ADD COLUMN ever_purchased boolean NOT NULL DEFAULT false;

-- 2) Um evento de abertura proprio do backfill (o paralelo v2 do
--    migration_opening do v1), distinguivel de um MANUAL_ADJUSTMENT de operador.
ALTER TABLE credit_ledger DROP CONSTRAINT credit_ledger_event_type_check;
ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_event_type_check CHECK (event_type IN (
    'purchase','consumption','refund','adjustment','migration_opening',
    'TRIAL_GRANT','TRIAL_EXPIRATION','CREDIT_RESERVATION','CREDIT_CONSUMPTION',
    'CREDIT_RELEASE','CREDIT_RESTORE','MANUAL_ADJUSTMENT','CREDIT_PURCHASE',
    'SESSION_CONSUMPTION','SESSION_PENDING','V2_MIGRATION_OPENING'));

-- 3) Semantica do evento novo, acrescentada ao contrato fechado. O resto e
--    copia VERBATIM do estado corrente (037 + 047); se eles mudarem, este CHECK
--    acompanha. V2_MIGRATION_OPENING: credita o saldo liquido carregado, sem
--    reserva, como PAID (igual a CREDIT_PURCHASE na forma).
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
        OR (event_type='V2_MIGRATION_OPENING' AND delta>0 AND reserved_delta=0 AND funding='PAID')
    ))
);

-- 4) O comando de backfill. SECURITY DEFINER, mesma fronteira dos demais: GUC +
--    membership ativo + papel de dono (reusa o tier do ENROLL). Vira a carteira
--    de v1 para psique_v2 SEM apagar a trilha v1 (o gatilho de imutabilidade so
--    barra NOVAS linhas v1 sob carteira v2, e nenhuma sera inserida). Zera o
--    numero v1 e reabre o saldo liquido como evento v2 auditavel; carrega as
--    pendencias; grava o sinal ever_purchased. Idempotente por organizacao.
CREATE FUNCTION psique_v2_backfill_from_v1(org uuid, member uuid, actor uuid,
    net integer, has_purchased boolean, pending_ids text[], note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE
    wallet organization_wallets%ROWTYPE; prior_pool integer;
    opened boolean:=false; pend text; sid text; pending_added integer:=0;
BEGIN
    IF net IS NULL OR net < 0 THEN RAISE EXCEPTION 'BACKFILL_NET_INVALID'; END IF;
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
    -- Abrir/converter carteira e ato do dono: 'ENROLL' seleciona o tier correto
    -- (owner no legado, ORG_ADMIN no RBAC v2) no guarda unico de 042.
    PERFORM psique_v2_credit_command_roles(org, 'ENROLL');

    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;
    IF wallet.credit_model='psique_v2' THEN
        -- Idempotente: ja convertida. Nao mexe em saldo nem em ever_purchased.
        RETURN jsonb_build_object('converted',false,'already_v2',true,
            'balance',wallet.balance,'ever_purchased',wallet.ever_purchased);
    END IF;
    prior_pool:=wallet.balance;
    -- O JSON e a fonte autoritativa (modo off); o pool v1 pode estar defasado.
    -- Por isso o saldo carregado e o 'net' (calculado do JSON), nao o pool: o
    -- numero v1 e descartado e substituido pela abertura v2.
    UPDATE organization_wallets
       SET balance=0, reserved_balance=0, credit_model='psique_v2',
           authority='shared', ever_purchased=has_purchased,
           version=version+1, updated_at=clock_timestamp()
     WHERE organization_id=org;
    IF net > 0 THEN
        PERFORM psique_v2_append(org, actor, 'V2_MIGRATION_OPENING', net, 0,
            'v2-backfill-opening:'||org, fund=>'PAID',
            explanation=>coalesce(nullif(trim(note),''),'V1_BACKFILL'));
        opened:=true;
    END IF;
    IF pending_ids IS NOT NULL THEN
        FOREACH pend IN ARRAY pending_ids LOOP
            sid:=trim(pend);
            CONTINUE WHEN sid='';
            IF NOT EXISTS(SELECT 1 FROM credit_ledger WHERE organization_id=org
                    AND idempotency_key='session-pending:'||sid AND event_type='SESSION_PENDING') THEN
                PERFORM psique_v2_append(org, actor, 'SESSION_PENDING', 0, 0,
                    'session-pending:'||sid, fund=>'PAID', explanation=>'V1_PENDING_CARRIED');
                pending_added:=pending_added+1;
            END IF;
        END LOOP;
    END IF;
    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org;
    RETURN jsonb_build_object('converted',true,'already_v2',false,'opened',opened,
        'balance',wallet.balance,'prior_pool',prior_pool,
        'ever_purchased',wallet.ever_purchased,'pending_carried',pending_added);
END $$;

REVOKE ALL ON FUNCTION psique_v2_backfill_from_v1(uuid,uuid,uuid,integer,boolean,text[],text) FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION psique_v2_backfill_from_v1(uuid,uuid,uuid,integer,boolean,text[],text)
    TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('048_psique_v2_backfill');
COMMIT;
