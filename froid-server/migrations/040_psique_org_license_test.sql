BEGIN;

-- Phase 2C: organizational license over Stripe TEST. Additive only.
-- V2.1 rules: clinical activation is operational and immediate; billing is a
-- separate, versioned preview/confirm step. Increases accrue proration to the
-- next invoice (never always_invoice); reductions bill on the next cycle.
-- The license never grants credits; non-clinical members never count.

CREATE TABLE psique_clinical_memberships (
    membership_id uuid PRIMARY KEY REFERENCES organization_memberships(id) ON DELETE RESTRICT,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    clinical_status text NOT NULL CHECK (clinical_status IN ('ACTIVE','INACTIVE')),
    activated_at timestamptz,
    deactivated_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE psique_organization_licenses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE RESTRICT,
    pricing_version text NOT NULL,
    pricing_hash text NOT NULL CHECK (pricing_hash ~ '^[0-9a-f]{64}$'),
    currency text NOT NULL CHECK (currency='brl'),
    stripe_account_id text NOT NULL CHECK (stripe_account_id ~ '^acct_[A-Za-z0-9]+$'),
    livemode boolean NOT NULL CHECK (livemode=false),
    stripe_customer_id text NOT NULL CHECK (stripe_customer_id ~ '^cus_[A-Za-z0-9]+$'),
    stripe_subscription_id text NOT NULL UNIQUE CHECK (stripe_subscription_id ~ '^sub_[A-Za-z0-9]+$'),
    stripe_subscription_item_id text NOT NULL CHECK (stripe_subscription_item_id ~ '^si_[A-Za-z0-9]+$'),
    stripe_price_id text NOT NULL CHECK (stripe_price_id ~ '^price_[A-Za-z0-9]+$'),
    license_status text NOT NULL CHECK (license_status IN
        ('ACTIVE','PENDING_PAYMENT','PAST_DUE','CANCEL_AT_PERIOD_END','CANCELED')),
    billed_clinical_seat_count integer NOT NULL CHECK (billed_clinical_seat_count >= 0),
    next_cycle_clinical_seat_count integer NOT NULL CHECK (next_cycle_clinical_seat_count >= 0),
    current_period_end timestamptz,
    status_reason text,
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_by text NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE psique_seat_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    license_id uuid REFERENCES psique_organization_licenses(id) ON DELETE RESTRICT,
    license_version bigint,
    from_billed integer NOT NULL CHECK (from_billed >= 0),
    to_active integer NOT NULL CHECK (to_active >= 0),
    quote_monthly_cents bigint CHECK (quote_monthly_cents IS NULL OR quote_monthly_cents >= 0),
    pricing_version text NOT NULL,
    pricing_hash text NOT NULL CHECK (pricing_hash ~ '^[0-9a-f]{64}$'),
    change_status text NOT NULL DEFAULT 'PREVIEWED'
        CHECK (change_status IN ('PREVIEWED','CONFIRMED','SUPERSEDED','ABORTED')),
    stripe_result jsonb,
    created_by text NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz
);

CREATE OR REPLACE FUNCTION psique_v2_license_identity_guard()
RETURNS trigger LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'psique_license_history_is_immutable';
    END IF;
    IF (to_jsonb(NEW) - ARRAY['license_status','billed_clinical_seat_count',
            'next_cycle_clinical_seat_count','current_period_end','status_reason',
            'version','updated_at'])
        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['license_status','billed_clinical_seat_count',
            'next_cycle_clinical_seat_count','current_period_end','status_reason',
            'version','updated_at']) THEN
        RAISE EXCEPTION 'psique_license_identity_is_immutable';
    END IF;
    IF NEW.version < OLD.version THEN
        RAISE EXCEPTION 'psique_license_version_must_advance';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER psique_license_guard BEFORE UPDATE OR DELETE
    ON psique_organization_licenses FOR EACH ROW EXECUTE FUNCTION psique_v2_license_identity_guard();

ALTER TABLE psique_clinical_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_organization_licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_seat_changes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON psique_clinical_memberships, psique_organization_licenses, psique_seat_changes FROM PUBLIC;

-- Only ACTIVE clinical memberships of active members count; a user holds one
-- membership per organization, so a professional in two units counts once.
CREATE FUNCTION psique_v2_active_clinical_count(org uuid)
RETURNS integer LANGUAGE sql STABLE SET search_path=public,pg_temp AS $$
    SELECT count(*)::integer FROM psique_clinical_memberships c
    JOIN organization_memberships m ON m.id=c.membership_id
    JOIN users u ON u.id=m.user_id
    WHERE c.organization_id=org AND c.clinical_status='ACTIVE'
        AND m.status='active' AND u.status='active';
$$;

CREATE FUNCTION psique_v2_clinical_set(org uuid, member uuid, actor uuid,
    target uuid, make_active boolean)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE target_row organization_memberships%ROWTYPE; current_row psique_clinical_memberships%ROWTYPE;
    instant timestamptz:=clock_timestamp(); changed boolean:=false;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT * INTO target_row FROM organization_memberships
        WHERE id=target AND organization_id=org AND status='active' FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'CLINICAL_TARGET_MEMBERSHIP_REQUIRED' USING ERRCODE='42501'; END IF;
    SELECT * INTO current_row FROM psique_clinical_memberships WHERE membership_id=target FOR UPDATE;
    IF make_active THEN
        IF NOT FOUND THEN
            INSERT INTO psique_clinical_memberships(membership_id,organization_id,clinical_status,activated_at,updated_at)
                VALUES(target,org,'ACTIVE',instant,instant);
            changed:=true;
        ELSIF current_row.clinical_status<>'ACTIVE' THEN
            UPDATE psique_clinical_memberships SET clinical_status='ACTIVE',activated_at=instant,
                deactivated_at=NULL,updated_at=instant WHERE membership_id=target;
            changed:=true;
        END IF;
    ELSIF FOUND AND current_row.clinical_status='ACTIVE' THEN
        UPDATE psique_clinical_memberships SET clinical_status='INACTIVE',deactivated_at=instant,
            updated_at=instant WHERE membership_id=target;
        changed:=true;
    END IF;
    IF changed THEN
        INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
        VALUES(gen_random_uuid(),org,actor,
            CASE WHEN make_active THEN 'psique.clinical.activate' ELSE 'psique.clinical.deactivate' END,
            'organization_membership',target::text,
            jsonb_build_object('active_clinical_seat_count',psique_v2_active_clinical_count(org)));
    END IF;
    -- Operational effect is immediate; billing follows via preview/confirm.
    RETURN jsonb_build_object('membership_id',target,'changed',changed,
        'clinical_status',CASE WHEN make_active THEN 'ACTIVE' ELSE 'INACTIVE' END,
        'active_clinical_seat_count',psique_v2_active_clinical_count(org));
END $$;

CREATE FUNCTION psique_v2_license_state(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE lic psique_organization_licenses%ROWTYPE;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT * INTO lic FROM psique_organization_licenses WHERE organization_id=org;
    RETURN jsonb_build_object(
        'active_clinical_seat_count',psique_v2_active_clinical_count(org),
        'billed_clinical_seat_count',lic.billed_clinical_seat_count,
        'next_cycle_clinical_seat_count',lic.next_cycle_clinical_seat_count,
        'license_status',lic.license_status,'license_version',lic.version,
        'current_period_end',lic.current_period_end,'status_reason',lic.status_reason,
        'stripe_subscription_id',lic.stripe_subscription_id,
        'stripe_subscription_item_id',lic.stripe_subscription_item_id,
        'pricing_version',lic.pricing_version,'pricing_hash',lic.pricing_hash);
END $$;

CREATE FUNCTION psique_v2_license_price_mapping(org uuid, member uuid, actor uuid,
    catalog_version text, account text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE price text;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT m.stripe_price_id INTO price FROM psique_stripe_price_mappings m
        JOIN psique_pricing_offers o ON o.id=m.offer_id
        JOIN psique_pricing_tables t ON t.id=m.pricing_table_id
        WHERE o.product_code='FROID_ORG_LICENSE' AND t.version=catalog_version
        AND m.stripe_account_id=account AND m.livemode=false AND m.active
        AND m.lookup_key IS NOT NULL;
    IF price IS NULL THEN RAISE EXCEPTION 'LICENSE_PRICE_MAPPING_REQUIRED'; END IF;
    RETURN jsonb_build_object('price_id',price);
END $$;

CREATE FUNCTION psique_v2_seat_preview(org uuid, member uuid, actor uuid, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE lic psique_organization_licenses%ROWTYPE; preview psique_seat_changes%ROWTYPE;
    active_now integer; billed_now integer:=0;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    IF coalesce(args->>'pricing_version','')='' OR coalesce(args->>'pricing_hash','') !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'PRICING_SNAPSHOT_REQUIRED';
    END IF;
    SELECT * INTO lic FROM psique_organization_licenses WHERE organization_id=org FOR UPDATE;
    IF FOUND THEN billed_now:=lic.billed_clinical_seat_count; END IF;
    active_now:=psique_v2_active_clinical_count(org);
    -- The quote was computed by the backend for a specific count; if the
    -- derived count moved meanwhile, the caller must re-quote, not guess.
    IF (args->>'expected_active')::integer IS DISTINCT FROM active_now THEN
        RAISE EXCEPTION 'SEAT_COUNT_CHANGED_RETRY';
    END IF;
    IF (args->>'quote_monthly_cents') IS NULL AND active_now>0 THEN
        RAISE EXCEPTION 'ENTERPRISE_REQUIRED_NO_SELF_SERVICE';
    END IF;
    UPDATE psique_seat_changes SET change_status='SUPERSEDED',resolved_at=clock_timestamp()
        WHERE organization_id=org AND change_status='PREVIEWED';
    INSERT INTO psique_seat_changes(organization_id,license_id,license_version,from_billed,
        to_active,quote_monthly_cents,pricing_version,pricing_hash,created_by)
    VALUES(org,lic.id,lic.version,billed_now,active_now,
        (args->>'quote_monthly_cents')::bigint,args->>'pricing_version',args->>'pricing_hash',actor::text)
    RETURNING * INTO preview;
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.license.preview','psique_seat_change',preview.id::text,
        jsonb_build_object('from_billed',billed_now,'to_active',active_now,
            'quote_monthly_cents',preview.quote_monthly_cents));
    RETURN jsonb_build_object('preview_id',preview.id,'license_version',lic.version,
        'from_billed',billed_now,'to_active',active_now,
        'quote_monthly_cents',preview.quote_monthly_cents,
        'requires_stripe_quantity_update',active_now>billed_now,
        'reduction_effective_next_cycle',active_now<billed_now,
        'license_exists',lic.id IS NOT NULL);
END $$;

CREATE FUNCTION psique_v2_seat_confirm(org uuid, member uuid, actor uuid, args jsonb)
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
        IF payload IS NULL OR (payload->>'livemode')::boolean IS DISTINCT FROM false
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
        VALUES(org,preview.pricing_version,preview.pricing_hash,'brl',payload->>'account_id',false,
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

CREATE FUNCTION psique_v2_license_sync(args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE lic psique_organization_licenses%ROWTYPE; mapped text; quantity integer;
BEGIN
    SELECT * INTO lic FROM psique_organization_licenses
        WHERE stripe_subscription_id=args->>'subscription_id' FOR UPDATE;
    IF NOT FOUND THEN RETURN jsonb_build_object('synced',false,'code','LICENSE_NOT_FOUND'); END IF;
    mapped:=CASE args->>'stripe_status'
        WHEN 'active' THEN 'ACTIVE' WHEN 'past_due' THEN 'PAST_DUE'
        WHEN 'canceled' THEN 'CANCELED'
        WHEN 'incomplete' THEN 'PENDING_PAYMENT' WHEN 'unpaid' THEN 'PAST_DUE'
        ELSE NULL END;
    IF mapped='ACTIVE' AND (args->>'cancel_at_period_end')::boolean IS TRUE THEN
        mapped:='CANCEL_AT_PERIOD_END';
    END IF;
    quantity:=nullif(args->>'quantity','')::integer;
    UPDATE psique_organization_licenses SET
        license_status=coalesce(mapped,license_status),
        current_period_end=coalesce(nullif(args->>'current_period_end','')::timestamptz,current_period_end),
        status_reason=CASE WHEN quantity IS NOT NULL AND quantity<>billed_clinical_seat_count
            AND quantity<>next_cycle_clinical_seat_count
            THEN 'STRIPE_QUANTITY_DIVERGENT:'||quantity ELSE status_reason END,
        version=version+1,updated_at=clock_timestamp()
        WHERE id=lic.id RETURNING * INTO lic;
    -- Billing state never suspends the professional: clinical_status is not
    -- touched here, whatever the invoice outcome.
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),lic.organization_id,lic.created_by::uuid,'psique.license.sync',
        'psique_organization_license',lic.id::text,
        jsonb_build_object('license_status',lic.license_status,'status_reason',lic.status_reason));
    RETURN jsonb_build_object('synced',true,'license_status',lic.license_status,
        'status_reason',lic.status_reason);
END $$;

REVOKE ALL ON FUNCTION
    psique_v2_active_clinical_count(uuid),
    psique_v2_clinical_set(uuid,uuid,uuid,uuid,boolean),
    psique_v2_license_state(uuid,uuid,uuid),
    psique_v2_license_price_mapping(uuid,uuid,uuid,text,text),
    psique_v2_seat_preview(uuid,uuid,uuid,jsonb),
    psique_v2_seat_confirm(uuid,uuid,uuid,jsonb),
    psique_v2_license_sync(jsonb)
    FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION
        psique_v2_clinical_set(uuid,uuid,uuid,uuid,boolean),
        psique_v2_license_state(uuid,uuid,uuid),
        psique_v2_license_price_mapping(uuid,uuid,uuid,text,text),
        psique_v2_seat_preview(uuid,uuid,uuid,jsonb),
        psique_v2_seat_confirm(uuid,uuid,uuid,jsonb),
        psique_v2_license_sync(jsonb)
    TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('040_psique_org_license_test');
COMMIT;
