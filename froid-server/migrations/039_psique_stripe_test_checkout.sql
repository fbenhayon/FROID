BEGIN;

-- Phase 2B: Stripe TEST checkout/webhook state. Additive only. livemode is
-- rejected by CHECKs; LIVE requires a later authorized release, not a flag.

-- A) Mapping gains the Stripe lookup_key and an activation flag. Rows are
-- still written only by the explicit operator tool under the migration role.
ALTER TABLE psique_stripe_price_mappings
    ADD COLUMN lookup_key text CHECK (lookup_key IS NULL OR lookup_key ~ '^[a-z0-9_]{1,200}$'),
    ADD COLUMN active boolean NOT NULL DEFAULT true;
CREATE UNIQUE INDEX psique_mapping_lookup_key
    ON psique_stripe_price_mappings(stripe_account_id,livemode,lookup_key)
    WHERE lookup_key IS NOT NULL;

-- B) Purchase state machine of Phase 2B. 'prepared'/'canceled' keep their
-- historical Phase 1 meaning; they are not reinterpreted.
ALTER TABLE psique_purchases DROP CONSTRAINT psique_purchases_status_check;
ALTER TABLE psique_purchases ADD CONSTRAINT psique_purchases_status_check CHECK (status IN
    ('prepared','canceled','CREATED','CHECKOUT_CREATED','PENDING_PAYMENT','PAID','APPLIED',
     'CANCELED','EXPIRED','FAILED','REVIEW_REQUIRED'));
ALTER TABLE psique_purchases
    ADD COLUMN stripe_payment_intent_id text
        CHECK (stripe_payment_intent_id IS NULL OR stripe_payment_intent_id ~ '^pi_[A-Za-z0-9]+$'),
    ADD COLUMN applied_at timestamptz,
    ADD COLUMN status_reason text;

CREATE OR REPLACE FUNCTION psique_v2_purchase_snapshot_guard()
RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE offer psique_pricing_offers%ROWTYPE; org_type text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'psique_purchase_history_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND (to_jsonb(NEW) - ARRAY['status','stripe_checkout_session_id',
            'stripe_payment_intent_id','applied_at','status_reason'])
        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','stripe_checkout_session_id',
            'stripe_payment_intent_id','applied_at','status_reason']) THEN
        RAISE EXCEPTION 'psique_purchase_snapshot_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.stripe_checkout_session_id IS NOT NULL
        AND NEW.stripe_checkout_session_id IS DISTINCT FROM OLD.stripe_checkout_session_id THEN
        RAISE EXCEPTION 'psique_checkout_identity_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.stripe_payment_intent_id IS NOT NULL
        AND NEW.stripe_payment_intent_id IS DISTINCT FROM OLD.stripe_payment_intent_id THEN
        RAISE EXCEPTION 'psique_payment_identity_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.applied_at IS NOT NULL
        AND NEW.applied_at IS DISTINCT FROM OLD.applied_at THEN
        RAISE EXCEPTION 'psique_applied_receipt_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status IN ('canceled','CANCELED','APPLIED','EXPIRED','FAILED')
        AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'psique_purchase_status_is_terminal';
    END IF;
    SELECT * INTO offer FROM psique_pricing_offers WHERE id=NEW.offer_id;
    IF NOT FOUND OR offer.billing_type<>'one_time' OR NOT offer.active
        OR NEW.product_code IS DISTINCT FROM offer.product_code
        OR NEW.credits IS DISTINCT FROM offer.credits
        OR NEW.total_cents IS DISTINCT FROM offer.total_cents THEN
        RAISE EXCEPTION 'psique_purchase_does_not_match_offer';
    END IF;
    SELECT organization_type INTO org_type FROM organizations WHERE id=NEW.organization_id;
    IF org_type IS NULL OR org_type NOT IN ('solo','clinic') THEN
        RAISE EXCEPTION 'psique_purchase_organization_not_supported';
    END IF;
    RETURN NEW;
END;
$$;

-- C) One CREDIT_PURCHASE per Purchase, enforced in the ledger itself.
ALTER TABLE credit_ledger
    ADD COLUMN purchase_id uuid REFERENCES psique_purchases(id) ON DELETE RESTRICT;
CREATE UNIQUE INDEX psique_one_grant_per_purchase ON credit_ledger(purchase_id)
    WHERE event_type='CREDIT_PURCHASE';

DROP FUNCTION psique_v2_append(uuid,uuid,text,integer,integer,text,uuid,uuid,uuid,text,text);
CREATE FUNCTION psique_v2_append(
    org uuid, actor uuid, kind text, amount integer, held integer, idem text,
    source_id uuid DEFAULT NULL, reservation uuid DEFAULT NULL,
    origin uuid DEFAULT NULL, fund text DEFAULT NULL, explanation text DEFAULT NULL,
    purchase uuid DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
DECLARE result uuid:=gen_random_uuid(); wallet organization_wallets%ROWTYPE;
BEGIN
    UPDATE organization_wallets SET balance=balance+amount,reserved_balance=reserved_balance+held,
        version=version+1,updated_at=clock_timestamp()
        WHERE organization_id=org AND credit_model='psique_v2' RETURNING * INTO wallet;
    IF NOT FOUND THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;
    INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,idempotency_key,
        actor_user_id,ledger_version,reserved_delta,reserved_after,analysis_source_id,
        reservation_id,original_consumption_id,funding,reason,purchase_id)
    VALUES(result,org,amount,wallet.balance,kind,idem,actor,2,held,wallet.reserved_balance,
        source_id,reservation,origin,fund,explanation,purchase);
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.'||kind,'credit_ledger',result::text,
        jsonb_build_object('reason',explanation,'source_id',source_id,
            'original_consumption_id',origin,'purchase_id',purchase));
    RETURN result;
END $$;

-- D) Durable webhook inbox. Recording an event and applying it are separate
-- transactions, so a failed application leaves the event reprocessable.
CREATE TABLE psique_stripe_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id text NOT NULL UNIQUE CHECK (stripe_event_id ~ '^evt_[A-Za-z0-9]+$'),
    stripe_account_id text NOT NULL CHECK (stripe_account_id ~ '^acct_[A-Za-z0-9]+$'),
    livemode boolean NOT NULL CHECK (livemode=false),
    event_type text NOT NULL CHECK (length(trim(event_type)) > 0),
    checkout_session_id text CHECK (checkout_session_id IS NULL OR checkout_session_id ~ '^cs_test_[A-Za-z0-9]+$'),
    purchase_id uuid REFERENCES psique_purchases(id) ON DELETE RESTRICT,
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    processing_status text NOT NULL DEFAULT 'received'
        CHECK (processing_status IN ('received','credited','resolved','review','rejected')),
    error_sanitized text,
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz
);
ALTER TABLE psique_stripe_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON psique_stripe_events FROM PUBLIC;

-- E) Command boundary of Phase 2B. The runtime only gets EXECUTE on these;
-- tables and the append primitive stay without direct runtime grants.
CREATE FUNCTION psique_v2_require_billing_member(org uuid, member uuid, actor uuid)
RETURNS void LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
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
    -- Buying credits for the shared wallet is a financial act of the
    -- organization; professionals analyze, owners/administrators purchase.
    IF NOT froid_has_role(ARRAY['owner','administrator']) THEN
        RAISE EXCEPTION 'PSIQUE_BILLING_ADMIN_REQUIRED' USING ERRCODE='42501';
    END IF;
END $$;

CREATE FUNCTION psique_v2_checkout_prepare(org uuid, member uuid, actor uuid,
    code text, version text, account text, idem text)
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
        AND stripe_account_id=account AND livemode=false AND active AND lookup_key IS NOT NULL;
    IF NOT FOUND THEN RAISE EXCEPTION 'STRIPE_TEST_MAPPING_REQUIRED'; END IF;
    INSERT INTO psique_purchases(organization_id,offer_id,pricing_table_id,mapping_id,product_code,
        pricing_version,pricing_hash,currency,credits,total_cents,stripe_account_id,livemode,
        idempotency_key,status,created_by)
    VALUES(org,offer.id,table_row.id,mapping.id,offer.product_code,table_row.version,
        table_row.config_hash,table_row.currency,offer.credits,offer.total_cents,
        mapping.stripe_account_id,false,idem,'CREATED',actor::text)
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

CREATE FUNCTION psique_v2_checkout_attach(org uuid, member uuid, actor uuid,
    purchase_ref uuid, session text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE purchase psique_purchases%ROWTYPE;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT * INTO purchase FROM psique_purchases WHERE id=purchase_ref AND organization_id=org FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'PURCHASE_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF purchase.stripe_checkout_session_id IS NOT NULL THEN
        IF purchase.stripe_checkout_session_id<>session THEN
            RAISE EXCEPTION 'psique_checkout_identity_is_immutable';
        END IF;
        RETURN jsonb_build_object('purchase_id',purchase.id,'status',purchase.status,'attached',false);
    END IF;
    IF purchase.status<>'CREATED' THEN RAISE EXCEPTION 'PURCHASE_NOT_ATTACHABLE'; END IF;
    UPDATE psique_purchases SET stripe_checkout_session_id=session,status='CHECKOUT_CREATED'
        WHERE id=purchase.id RETURNING * INTO purchase;
    RETURN jsonb_build_object('purchase_id',purchase.id,'status',purchase.status,'attached',true);
END $$;

CREATE FUNCTION psique_v2_stripe_event(account text, live boolean, evt text,
    etype text, session text, payload_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE row_record psique_stripe_events%ROWTYPE; linked uuid; inserted boolean;
BEGIN
    IF live IS DISTINCT FROM false THEN RAISE EXCEPTION 'LIVE_EVENT_REFUSED'; END IF;
    SELECT id INTO linked FROM psique_purchases WHERE stripe_checkout_session_id=session;
    INSERT INTO psique_stripe_events(stripe_event_id,stripe_account_id,livemode,event_type,
        checkout_session_id,purchase_id,payload_sha256)
    VALUES(evt,account,false,etype,session,linked,payload_hash)
    ON CONFLICT (stripe_event_id) DO NOTHING;
    inserted:=FOUND;
    SELECT * INTO row_record FROM psique_stripe_events WHERE stripe_event_id=evt;
    IF row_record.payload_sha256<>payload_hash OR row_record.event_type<>etype
        OR row_record.stripe_account_id<>account THEN
        RAISE EXCEPTION 'STRIPE_EVENT_PAYLOAD_MISMATCH';
    END IF;
    RETURN jsonb_build_object('event_row_id',row_record.id,'duplicate',NOT inserted,
        'processing_status',row_record.processing_status,'purchase_id',row_record.purchase_id);
END $$;

CREATE FUNCTION psique_v2_apply_purchase(evt text, session jsonb)
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
    IF (session->>'livemode')::boolean IS DISTINCT FROM false THEN failure:='LIVE_SESSION_REFUSED';
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

CREATE FUNCTION psique_v2_purchase_outcome(evt text, outcome text, note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE inbox psique_stripe_events%ROWTYPE; purchase psique_purchases%ROWTYPE;
    instant timestamptz:=clock_timestamp(); moved boolean:=false;
BEGIN
    IF outcome NOT IN ('EXPIRED','FAILED','REVIEW','RESOLVED') THEN
        RAISE EXCEPTION 'UNKNOWN_EVENT_OUTCOME';
    END IF;
    SELECT * INTO inbox FROM psique_stripe_events WHERE stripe_event_id=evt FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'EVENT_NOT_RECORDED'; END IF;
    IF inbox.processing_status<>'received' THEN
        RETURN jsonb_build_object('applied',false,'code','EVENT_ALREADY_PROCESSED',
            'processing_status',inbox.processing_status);
    END IF;
    IF inbox.checkout_session_id IS NOT NULL THEN
        SELECT * INTO purchase FROM psique_purchases
            WHERE stripe_checkout_session_id=inbox.checkout_session_id FOR UPDATE;
    END IF;
    IF outcome IN ('EXPIRED','FAILED') AND purchase.id IS NOT NULL
        AND purchase.status IN ('CREATED','CHECKOUT_CREATED','PENDING_PAYMENT') THEN
        UPDATE psique_purchases SET status=outcome,status_reason=coalesce(nullif(trim(note),''),outcome)
            WHERE id=purchase.id;
        moved:=true;
    END IF;
    IF outcome='REVIEW' AND purchase.id IS NOT NULL THEN
        INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
        VALUES(gen_random_uuid(),purchase.organization_id,purchase.created_by::uuid,
            'psique.billing.review','psique_purchase',purchase.id::text,
            jsonb_build_object('event',evt,'event_type',inbox.event_type,'note',note));
    END IF;
    UPDATE psique_stripe_events SET
        processing_status=CASE WHEN outcome='REVIEW' THEN 'review' ELSE 'resolved' END,
        processed_at=instant,purchase_id=coalesce(purchase.id,inbox.purchase_id),
        error_sanitized=nullif(trim(note),'') WHERE id=inbox.id;
    RETURN jsonb_build_object('applied',moved,'purchase_id',purchase.id,
        'purchase_status',purchase.status,'outcome',outcome);
END $$;

CREATE FUNCTION psique_v2_purchase_state(org uuid, member uuid, actor uuid, purchase_ref uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE purchase psique_purchases%ROWTYPE;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT * INTO purchase FROM psique_purchases WHERE id=purchase_ref AND organization_id=org;
    IF NOT FOUND THEN RAISE EXCEPTION 'PURCHASE_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    RETURN jsonb_build_object('purchase_id',purchase.id,'status',purchase.status,
        'product_code',purchase.product_code,'credits',purchase.credits,
        'total_cents',purchase.total_cents,'currency',purchase.currency,
        'applied_at',purchase.applied_at,'status_reason',purchase.status_reason);
END $$;

REVOKE ALL ON FUNCTION
    psique_v2_append(uuid,uuid,text,integer,integer,text,uuid,uuid,uuid,text,text,uuid),
    psique_v2_require_billing_member(uuid,uuid,uuid),
    psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text),
    psique_v2_checkout_attach(uuid,uuid,uuid,uuid,text),
    psique_v2_stripe_event(text,boolean,text,text,text,text),
    psique_v2_apply_purchase(text,jsonb),
    psique_v2_purchase_outcome(text,text,text),
    psique_v2_purchase_state(uuid,uuid,uuid,uuid)
    FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION
        psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text),
        psique_v2_checkout_attach(uuid,uuid,uuid,uuid,text),
        psique_v2_stripe_event(text,boolean,text,text,text,text),
        psique_v2_apply_purchase(text,jsonb),
        psique_v2_purchase_outcome(text,text,text),
        psique_v2_purchase_state(uuid,uuid,uuid,uuid)
    TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('039_psique_stripe_test_checkout');
COMMIT;
