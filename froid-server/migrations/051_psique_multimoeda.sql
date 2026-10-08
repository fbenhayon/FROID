BEGIN;

-- Multimoeda do FROID Psique (decisao do dono, 06 e 07/10/2026): o mesmo
-- numero em BRL, USD e EUR, sem conversao, moeda escolhida pelo idioma. Cada
-- moeda e uma tabela de precos propria (versao "2.1", "2.1-usd", "2.1-eur";
-- uma ativa por moeda pelo indice da 035). Este arquivo e GERADO por
-- tools/psique_multimoeda_sync.py a partir do texto real da 046 (teste de
-- espelho garante a igualdade); nao editar a mao.

-- 1. Os tres CHECK (currency = 'brl') viram CHECK (currency IN (...)).
--    Ampliar nunca falha sobre as linhas BRL existentes.
DO $$
DECLARE c record;
BEGIN
    FOR c IN SELECT conrelid::regclass::text AS tabela, conname
        FROM pg_constraint
        WHERE conrelid IN ('psique_pricing_tables'::regclass,
                           'psique_purchases'::regclass,
                           'psique_organization_licenses'::regclass)
          AND contype='c'
          AND pg_get_constraintdef(oid) ILIKE '%currency = ''brl''%'
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', c.tabela, c.conname);
    END LOOP;
END $$;

ALTER TABLE psique_pricing_tables ADD CONSTRAINT psique_pricing_tables_moeda
    CHECK (currency IN ('brl','usd','eur'));
ALTER TABLE psique_purchases ADD CONSTRAINT psique_purchases_moeda
    CHECK (currency IN ('brl','usd','eur'));
ALTER TABLE psique_organization_licenses ADD CONSTRAINT psique_organization_licenses_moeda
    CHECK (currency IN ('brl','usd','eur'));

-- 2. A licenca grava a moeda da tabela do preview (antes: literal 'brl').

CREATE OR REPLACE FUNCTION psique_v2_seat_confirm(org uuid, member uuid, actor uuid, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE lic psique_organization_licenses%ROWTYPE; preview psique_seat_changes%ROWTYPE;
    payload jsonb; active_now integer; instant timestamptz:=clock_timestamp();
    new_billed integer; new_next integer; new_status text; moeda text;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT * INTO preview FROM psique_seat_changes
        WHERE id=(args->>'preview_id')::uuid AND organization_id=org FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'PREVIEW_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF preview.change_status<>'PREVIEWED' THEN
        RETURN jsonb_build_object('applied',false,'code','PREVIEW_'||preview.change_status);
    END IF;
    SELECT * INTO lic FROM psique_organization_licenses WHERE organization_id=org FOR UPDATE;
    IF (FOUND AND (preview.license_id IS DISTINCT FROM lic.id
            OR preview.license_version IS DISTINCT FROM lic.version
            OR (args->>'expected_version')::bigint IS DISTINCT FROM lic.version))
        OR (NOT FOUND AND preview.license_id IS NOT NULL) THEN
        UPDATE psique_seat_changes SET change_status='ABORTED',resolved_at=instant WHERE id=preview.id;
        RETURN jsonb_build_object('applied',false,'code','LICENSE_VERSION_CONFLICT');
    END IF;
    active_now:=psique_v2_active_clinical_count(org);
    IF active_now IS DISTINCT FROM preview.to_active THEN
        UPDATE psique_seat_changes SET change_status='ABORTED',resolved_at=instant WHERE id=preview.id;
        RETURN jsonb_build_object('applied',false,'code','PREVIEW_STALE_SEAT_COUNT');
    END IF;
    payload:=nullif(args->'stripe','null'::jsonb);

    IF lic.id IS NULL THEN
        -- First subscription. Zero clinicians never create one.
        IF preview.to_active=0 THEN
            UPDATE psique_seat_changes SET change_status='CONFIRMED',resolved_at=instant,
                stripe_result='null'::jsonb WHERE id=preview.id;
            RETURN jsonb_build_object('applied',true,'code','NO_LICENSE_REQUIRED');
        END IF;
        IF payload IS NULL OR (payload->>'livemode')::boolean
                IS DISTINCT FROM (args->>'expected_livemode')::boolean
            OR payload->>'customer_id' !~ '^cus_[A-Za-z0-9]+$'
            OR payload->>'subscription_id' !~ '^sub_[A-Za-z0-9]+$'
            OR payload->>'item_id' !~ '^si_[A-Za-z0-9]+$'
            OR payload->>'price_id' !~ '^price_[A-Za-z0-9]+$'
            OR payload->>'account_id' !~ '^acct_[A-Za-z0-9]+$'
            OR (payload->>'quantity')::integer IS DISTINCT FROM preview.to_active THEN
            RAISE EXCEPTION 'LICENSE_SUBSCRIPTION_EVIDENCE_REQUIRED';
        END IF;
        -- Multimoeda (051): a moeda da licenca e a da tabela de precos do
        -- preview, e o Price assinado precisa pertencer a essa mesma tabela.
        SELECT t.currency INTO moeda FROM psique_pricing_tables t
            WHERE t.code='FROID_PSIQUE_V2' AND t.version=preview.pricing_version;
        IF moeda IS NULL THEN RAISE EXCEPTION 'PREVIEW_PRICING_VERSION_NOT_INSTALLED'; END IF;
        IF NOT EXISTS (SELECT 1 FROM psique_stripe_price_mappings m
                JOIN psique_pricing_tables t ON t.id=m.pricing_table_id
                WHERE m.stripe_price_id=payload->>'price_id'
                AND t.version=preview.pricing_version) THEN
            RAISE EXCEPTION 'LICENSE_PRICE_NOT_FROM_PREVIEW_CATALOG';
        END IF;
        INSERT INTO psique_organization_licenses(organization_id,pricing_version,pricing_hash,
            currency,stripe_account_id,livemode,stripe_customer_id,stripe_subscription_id,
            stripe_subscription_item_id,stripe_price_id,license_status,
            billed_clinical_seat_count,next_cycle_clinical_seat_count,current_period_end,created_by)
        VALUES(org,preview.pricing_version,preview.pricing_hash,moeda,payload->>'account_id',
            (payload->>'livemode')::boolean,
            payload->>'customer_id',payload->>'subscription_id',payload->>'item_id',
            payload->>'price_id',coalesce(nullif(payload->>'license_status',''),'ACTIVE'),
            preview.to_active,preview.to_active,
            nullif(payload->>'current_period_end','')::timestamptz,actor::text)
        RETURNING * INTO lic;
    ELSE
        IF preview.to_active=0 THEN
            IF payload IS NULL OR (payload->>'cancel_at_period_end')::boolean IS DISTINCT FROM true
                OR payload->>'subscription_id' IS DISTINCT FROM lic.stripe_subscription_id THEN
                RAISE EXCEPTION 'LICENSE_CANCELLATION_EVIDENCE_REQUIRED';
            END IF;
            new_billed:=lic.billed_clinical_seat_count; new_next:=0; new_status:='CANCEL_AT_PERIOD_END';
        ELSIF preview.to_active>lic.billed_clinical_seat_count THEN
            -- Increase: the seat is billed from now on; the proration accrues
            -- to the next invoice. Never always_invoice. Coming back from a
            -- scheduled cancellation also requires the un-cancel evidence.
            IF payload IS NULL OR (payload->>'quantity')::integer IS DISTINCT FROM preview.to_active
                OR payload->>'subscription_id' IS DISTINCT FROM lic.stripe_subscription_id
                OR coalesce(payload->>'proration_behavior','')<>'create_prorations'
                OR (lic.license_status='CANCEL_AT_PERIOD_END'
                    AND (payload->>'cancel_at_period_end')::boolean IS DISTINCT FROM false) THEN
                RAISE EXCEPTION 'LICENSE_QUANTITY_EVIDENCE_REQUIRED';
            END IF;
            new_billed:=preview.to_active; new_next:=preview.to_active;
            new_status:=CASE WHEN lic.license_status='CANCEL_AT_PERIOD_END' THEN 'ACTIVE'
                ELSE lic.license_status END;
        ELSIF lic.license_status='CANCEL_AT_PERIOD_END' THEN
            -- Reactivation within the billed quantity: the only Stripe change
            -- is removing the scheduled cancellation; no new charge.
            IF payload IS NULL OR (payload->>'cancel_at_period_end')::boolean IS DISTINCT FROM false
                OR payload->>'subscription_id' IS DISTINCT FROM lic.stripe_subscription_id
                OR payload ? 'quantity' THEN
                RAISE EXCEPTION 'LICENSE_REACTIVATION_EVIDENCE_REQUIRED';
            END IF;
            new_billed:=lic.billed_clinical_seat_count; new_next:=preview.to_active;
            new_status:='ACTIVE';
        ELSE
            -- Reduction or return within the already billed quantity:
            -- operational now, financial on the next cycle, no new charge and
            -- no Stripe change today (10 -> 8 -> 9 must not touch Stripe).
            IF payload IS NOT NULL THEN RAISE EXCEPTION 'REDUCTION_MUST_NOT_CHARGE'; END IF;
            new_billed:=lic.billed_clinical_seat_count; new_next:=preview.to_active;
            new_status:=lic.license_status;
        END IF;
        UPDATE psique_organization_licenses SET billed_clinical_seat_count=new_billed,
            next_cycle_clinical_seat_count=new_next,license_status=new_status,
            version=version+1,updated_at=instant WHERE id=lic.id RETURNING * INTO lic;
    END IF;

    UPDATE psique_seat_changes SET change_status='CONFIRMED',resolved_at=instant,
        stripe_result=payload,license_id=lic.id WHERE id=preview.id;
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.license.change','psique_organization_license',lic.id::text,
        jsonb_build_object('preview_id',preview.id,'billed',lic.billed_clinical_seat_count,
            'next_cycle',lic.next_cycle_clinical_seat_count,'license_status',lic.license_status));
    RETURN jsonb_build_object('applied',true,'license_version',lic.version,
        'billed_clinical_seat_count',lic.billed_clinical_seat_count,
        'next_cycle_clinical_seat_count',lic.next_cycle_clinical_seat_count,
        'license_status',lic.license_status);
END $$;

-- 3. A confirmacao da licenca le a tabela de precos DO PREVIEW antes de
--    tocar o Stripe: o Price certo e resolvido pela versao gravada no preview,
--    nunca repetido pelo cliente.
CREATE FUNCTION psique_v2_seat_preview_catalog(org uuid, member uuid, actor uuid, preview_ref uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE preview psique_seat_changes%ROWTYPE;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT * INTO preview FROM psique_seat_changes WHERE id=preview_ref AND organization_id=org;
    IF NOT FOUND THEN RAISE EXCEPTION 'PREVIEW_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    RETURN jsonb_build_object('preview_id',preview.id,'change_status',preview.change_status,
        'pricing_version',preview.pricing_version,'pricing_hash',preview.pricing_hash);
END $$;

REVOKE ALL ON FUNCTION psique_v2_seat_preview_catalog(uuid,uuid,uuid,uuid) FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION psique_v2_seat_preview_catalog(uuid,uuid,uuid,uuid) TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('051_psique_multimoeda');
COMMIT;
