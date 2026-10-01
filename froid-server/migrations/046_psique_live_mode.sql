BEGIN;

-- Fase 6: o modo LIVE passa a existir por decisao explicita do operador.
-- Este arquivo e GERADO por tools/psique_live_mode_sync.py a partir do texto
-- real das migrations 039/040 (teste de espelho garante a igualdade); nao
-- editar a mao. As travas CHECK(livemode=false) viram travas de coerencia:
-- cada linha continua declarando seu modo, e a sessao precisa do prefixo
-- (cs_test_/cs_live_) do modo que a linha declara.

DO $$
DECLARE c record;
BEGIN
    FOR c IN SELECT conrelid::regclass::text AS tabela, conname
        FROM pg_constraint
        WHERE conrelid IN ('psique_stripe_price_mappings'::regclass,
                           'psique_purchases'::regclass,
                           'psique_stripe_events'::regclass,
                           'psique_organization_licenses'::regclass)
          AND contype='c'
          AND (pg_get_constraintdef(oid) ILIKE '%livemode = false%'
               OR pg_get_constraintdef(oid) LIKE '%cs\_test\_%')
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', c.tabela, c.conname);
    END LOOP;
END $$;

ALTER TABLE psique_purchases ADD CONSTRAINT psique_purchases_sessao_por_modo
    CHECK (stripe_checkout_session_id IS NULL OR stripe_checkout_session_id ~
        (CASE WHEN livemode THEN '^cs_live_[A-Za-z0-9]+$' ELSE '^cs_test_[A-Za-z0-9]+$' END));
ALTER TABLE psique_stripe_events ADD CONSTRAINT psique_stripe_events_sessao_por_modo
    CHECK (checkout_session_id IS NULL OR checkout_session_id ~
        (CASE WHEN livemode THEN '^cs_live_[A-Za-z0-9]+$' ELSE '^cs_test_[A-Za-z0-9]+$' END));

-- Assinaturas antigas saem antes das novas (parametro live adicionado).
DROP FUNCTION psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text);
DROP FUNCTION psique_v2_license_price_mapping(uuid,uuid,uuid,text,text);

CREATE FUNCTION psique_v2_checkout_prepare(org uuid, member uuid, actor uuid,
    code text, version text, account text, idem text, live boolean)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE wallet organization_wallets%ROWTYPE; offer psique_pricing_offers%ROWTYPE;
    mapping psique_stripe_price_mappings%ROWTYPE; purchase psique_purchases%ROWTYPE;
    table_row psique_pricing_tables%ROWTYPE;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    IF coalesce(trim(idem),'')='' THEN RAISE EXCEPTION 'IDEMPOTENCY_KEY_REQUIRED'; END IF;
    IF account !~ '^acct_[A-Za-z0-9]+$' THEN RAISE EXCEPTION 'STRIPE_ACCOUNT_REQUIRED'; END IF;
    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org FOR UPDATE;
    IF NOT FOUND OR wallet.credit_model<>'psique_v2' THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;
    SELECT * INTO purchase FROM psique_purchases WHERE organization_id=org AND idempotency_key=idem;
    IF FOUND THEN
        IF purchase.product_code<>code THEN RAISE EXCEPTION 'IDEMPOTENCY_MISMATCH'; END IF;
        RETURN jsonb_build_object('purchase_id',purchase.id,'status',purchase.status,
            'product_code',purchase.product_code,'credits',purchase.credits,
            'total_cents',purchase.total_cents,'currency',purchase.currency,
            'pricing_version',purchase.pricing_version,'pricing_hash',purchase.pricing_hash,
            'stripe_checkout_session_id',purchase.stripe_checkout_session_id,
            'stripe_price_id',(SELECT m.stripe_price_id FROM psique_stripe_price_mappings m WHERE m.id=purchase.mapping_id),
            'created',false);
    END IF;
    SELECT * INTO table_row FROM psique_pricing_tables t
        WHERE t.code='FROID_PSIQUE_V2' AND t.version=$5;
    IF NOT FOUND THEN RAISE EXCEPTION 'PRICING_VERSION_NOT_INSTALLED'; END IF;
    SELECT * INTO offer FROM psique_pricing_offers o
        WHERE o.pricing_table_id=table_row.id AND o.product_code=$4;
    IF NOT FOUND OR NOT offer.active OR offer.billing_type<>'one_time'
        OR offer.credits IS NULL OR offer.total_cents IS NULL THEN
        RAISE EXCEPTION 'PRODUCT_CODE_NOT_PURCHASABLE';
    END IF;
    SELECT * INTO mapping FROM psique_stripe_price_mappings
        WHERE offer_id=offer.id AND pricing_table_id=table_row.id
        AND stripe_account_id=account AND livemode=live AND active AND lookup_key IS NOT NULL;
    IF NOT FOUND THEN RAISE EXCEPTION '%', CASE WHEN live
        THEN 'STRIPE_LIVE_MAPPING_REQUIRED' ELSE 'STRIPE_TEST_MAPPING_REQUIRED' END; END IF;
    INSERT INTO psique_purchases(organization_id,offer_id,pricing_table_id,mapping_id,product_code,
        pricing_version,pricing_hash,currency,credits,total_cents,stripe_account_id,livemode,
        idempotency_key,status,created_by)
    VALUES(org,offer.id,table_row.id,mapping.id,offer.product_code,table_row.version,
        table_row.config_hash,table_row.currency,offer.credits,offer.total_cents,
        mapping.stripe_account_id,live,idem,'CREATED',actor::text)
    RETURNING * INTO purchase;
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.purchase.create','psique_purchase',purchase.id::text,
        jsonb_build_object('product_code',code,'credits',offer.credits,'total_cents',offer.total_cents));
    RETURN jsonb_build_object('purchase_id',purchase.id,'status',purchase.status,
        'product_code',purchase.product_code,'credits',purchase.credits,
        'total_cents',purchase.total_cents,'currency',purchase.currency,
        'pricing_version',purchase.pricing_version,'pricing_hash',purchase.pricing_hash,
        'stripe_checkout_session_id',NULL,'stripe_price_id',mapping.stripe_price_id,
        'created',true);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_stripe_event(account text, live boolean, evt text,
    etype text, session text, payload_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE row_record psique_stripe_events%ROWTYPE; linked uuid; inserted boolean;
BEGIN
    SELECT id INTO linked FROM psique_purchases WHERE stripe_checkout_session_id=session;
    INSERT INTO psique_stripe_events(stripe_event_id,stripe_account_id,livemode,event_type,
        checkout_session_id,purchase_id,payload_sha256)
    VALUES(evt,account,live,etype,session,linked,payload_hash)
    ON CONFLICT (stripe_event_id) DO NOTHING;
    inserted:=FOUND;
    SELECT * INTO row_record FROM psique_stripe_events WHERE stripe_event_id=evt;
    IF row_record.payload_sha256<>payload_hash OR row_record.event_type<>etype
        OR row_record.stripe_account_id<>account OR row_record.livemode<>live THEN
        RAISE EXCEPTION 'STRIPE_EVENT_PAYLOAD_MISMATCH';
    END IF;
    RETURN jsonb_build_object('event_row_id',row_record.id,'duplicate',NOT inserted,
        'processing_status',row_record.processing_status,'purchase_id',row_record.purchase_id);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_apply_purchase(evt text, session jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE inbox psique_stripe_events%ROWTYPE; purchase psique_purchases%ROWTYPE;
    mapping psique_stripe_price_mappings%ROWTYPE; ledger_id uuid; failure text;
    instant timestamptz:=clock_timestamp();
BEGIN
    SELECT * INTO inbox FROM psique_stripe_events WHERE stripe_event_id=evt FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'EVENT_NOT_RECORDED'; END IF;
    IF inbox.processing_status<>'received' THEN
        RETURN jsonb_build_object('applied',false,'code','EVENT_ALREADY_PROCESSED',
            'processing_status',inbox.processing_status);
    END IF;
    IF session->>'id' IS DISTINCT FROM inbox.checkout_session_id THEN
        RAISE EXCEPTION 'EVENT_SESSION_MISMATCH';
    END IF;
    SELECT * INTO purchase FROM psique_purchases
        WHERE stripe_checkout_session_id=inbox.checkout_session_id FOR UPDATE;
    IF NOT FOUND THEN
        UPDATE psique_stripe_events SET processing_status='rejected',processed_at=instant,
            error_sanitized='PURCHASE_NOT_FOUND' WHERE id=inbox.id;
        RETURN jsonb_build_object('applied',false,'code','PURCHASE_NOT_FOUND');
    END IF;
    IF purchase.status='APPLIED' THEN
        UPDATE psique_stripe_events SET processing_status='resolved',processed_at=instant,
            purchase_id=purchase.id,error_sanitized='PURCHASE_ALREADY_APPLIED' WHERE id=inbox.id;
        RETURN jsonb_build_object('applied',false,'code','PURCHASE_ALREADY_APPLIED');
    END IF;
    IF purchase.status NOT IN ('CHECKOUT_CREATED','PENDING_PAYMENT','PAID') THEN
        UPDATE psique_stripe_events SET processing_status='rejected',processed_at=instant,
            purchase_id=purchase.id,error_sanitized='PURCHASE_STATUS_'||purchase.status WHERE id=inbox.id;
        RETURN jsonb_build_object('applied',false,'code','PURCHASE_STATUS_'||purchase.status);
    END IF;
    SELECT * INTO mapping FROM psique_stripe_price_mappings WHERE id=purchase.mapping_id;

    failure:=NULL;
    IF (session->>'livemode')::boolean IS DISTINCT FROM purchase.livemode THEN
        failure:=CASE WHEN purchase.livemode THEN 'TEST_SESSION_REFUSED' ELSE 'LIVE_SESSION_REFUSED' END;
    ELSIF inbox.stripe_account_id<>purchase.stripe_account_id THEN failure:='WRONG_STRIPE_ACCOUNT';
    ELSIF session->>'currency' IS DISTINCT FROM purchase.currency THEN failure:='WRONG_CURRENCY';
    ELSIF (session->>'amount_total')::bigint IS DISTINCT FROM purchase.total_cents THEN failure:='WRONG_AMOUNT';
    ELSIF session->>'client_reference_id' IS NOT NULL
        AND session->>'client_reference_id'<>purchase.id::text THEN failure:='WRONG_PURCHASE_REFERENCE';
    ELSIF session#>>'{metadata,purchase_id}' IS NOT NULL
        AND session#>>'{metadata,purchase_id}'<>purchase.id::text THEN failure:='WRONG_PURCHASE_REFERENCE';
    ELSIF session->>'price_id' IS NOT NULL AND session->>'price_id'<>mapping.stripe_price_id THEN failure:='WRONG_PRICE';
    ELSIF session->>'product_id' IS NOT NULL AND session->>'product_id'<>mapping.stripe_product_id THEN failure:='WRONG_PRODUCT';
    ELSIF session->>'quantity' IS NOT NULL AND (session->>'quantity')::integer<>1 THEN failure:='WRONG_QUANTITY';
    END IF;
    IF failure IS NOT NULL THEN
        UPDATE psique_stripe_events SET processing_status='rejected',processed_at=instant,
            purchase_id=purchase.id,error_sanitized=failure WHERE id=inbox.id;
        UPDATE psique_purchases SET status='REVIEW_REQUIRED',status_reason=failure WHERE id=purchase.id;
        RETURN jsonb_build_object('applied',false,'code',failure);
    END IF;

    IF session->>'payment_status' IS DISTINCT FROM 'paid' THEN
        -- checkout.session.completed with an async method still pending.
        UPDATE psique_purchases SET status='PENDING_PAYMENT' WHERE id=purchase.id
            AND purchase.status='CHECKOUT_CREATED';
        UPDATE psique_stripe_events SET processing_status='resolved',processed_at=instant,
            purchase_id=purchase.id,error_sanitized='ASYNC_PAYMENT_PENDING' WHERE id=inbox.id;
        RETURN jsonb_build_object('applied',false,'code','ASYNC_PAYMENT_PENDING');
    END IF;

    UPDATE psique_purchases SET status='PAID' WHERE id=purchase.id;
    ledger_id:=psique_v2_append(purchase.organization_id,purchase.created_by::uuid,'CREDIT_PURCHASE',
        purchase.credits,0,'purchase:'||purchase.id,fund=>'PAID',
        explanation=>'STRIPE_TEST_CHECKOUT '||evt,purchase=>purchase.id);
    UPDATE psique_purchases SET status='APPLIED',applied_at=instant,
        stripe_payment_intent_id=nullif(session->>'payment_intent',''),
        status_reason=NULL WHERE id=purchase.id;
    UPDATE psique_stripe_events SET processing_status='credited',processed_at=instant,
        purchase_id=purchase.id WHERE id=inbox.id;
    RETURN jsonb_build_object('applied',true,'ledger_id',ledger_id,'purchase_id',purchase.id,
        'credits',purchase.credits);
END $$;

CREATE FUNCTION psique_v2_license_price_mapping(org uuid, member uuid, actor uuid,
    catalog_version text, account text, live boolean)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE price text;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT m.stripe_price_id INTO price FROM psique_stripe_price_mappings m
        JOIN psique_pricing_offers o ON o.id=m.offer_id
        JOIN psique_pricing_tables t ON t.id=m.pricing_table_id
        WHERE o.product_code='FROID_ORG_LICENSE' AND t.version=catalog_version
        AND m.stripe_account_id=account AND m.livemode=live AND m.active
        AND m.lookup_key IS NOT NULL;
    IF price IS NULL THEN RAISE EXCEPTION 'LICENSE_PRICE_MAPPING_REQUIRED'; END IF;
    RETURN jsonb_build_object('price_id',price);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_seat_confirm(org uuid, member uuid, actor uuid, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE lic psique_organization_licenses%ROWTYPE; preview psique_seat_changes%ROWTYPE;
    payload jsonb; active_now integer; instant timestamptz:=clock_timestamp();
    new_billed integer; new_next integer; new_status text;
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
        INSERT INTO psique_organization_licenses(organization_id,pricing_version,pricing_hash,
            currency,stripe_account_id,livemode,stripe_customer_id,stripe_subscription_id,
            stripe_subscription_item_id,stripe_price_id,license_status,
            billed_clinical_seat_count,next_cycle_clinical_seat_count,current_period_end,created_by)
        VALUES(org,preview.pricing_version,preview.pricing_hash,'brl',payload->>'account_id',
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

REVOKE ALL ON FUNCTION
    psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text,boolean),
    psique_v2_license_price_mapping(uuid,uuid,uuid,text,text,boolean)
    FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION
        psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text,boolean),
        psique_v2_license_price_mapping(uuid,uuid,uuid,text,text,boolean)
    TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('046_psique_live_mode');
COMMIT;
