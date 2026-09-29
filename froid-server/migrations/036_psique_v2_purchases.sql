BEGIN;

-- TEST-only preparation. No paid state, webhook handling or wallet mutation.
-- LIVE requires a later explicitly authorized release, not a flag bypass.
CREATE TABLE IF NOT EXISTS psique_stripe_price_mappings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pricing_table_id uuid NOT NULL,
    offer_id uuid NOT NULL,
    stripe_account_id text NOT NULL CHECK (stripe_account_id ~ '^acct_[A-Za-z0-9]+$'),
    livemode boolean NOT NULL CHECK (livemode = false),
    stripe_product_id text NOT NULL CHECK (stripe_product_id ~ '^prod_[A-Za-z0-9]+$'),
    stripe_price_id text NOT NULL CHECK (stripe_price_id ~ '^price_[A-Za-z0-9]+$'),
    verified_at timestamptz NOT NULL,
    verified_by text NOT NULL CHECK (length(trim(verified_by)) > 0),
    FOREIGN KEY (offer_id,pricing_table_id)
        REFERENCES psique_pricing_offers(id,pricing_table_id) ON DELETE RESTRICT,
    UNIQUE (stripe_account_id,livemode,stripe_price_id),
    UNIQUE (offer_id,stripe_account_id,livemode),
    UNIQUE (id,offer_id,pricing_table_id,stripe_account_id,livemode)
);

CREATE TABLE IF NOT EXISTS psique_purchases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    offer_id uuid NOT NULL,
    pricing_table_id uuid NOT NULL,
    mapping_id uuid NOT NULL,
    product_code text NOT NULL,
    pricing_version text NOT NULL,
    pricing_hash text NOT NULL,
    currency text NOT NULL CHECK (currency='brl'),
    credits integer NOT NULL CHECK (credits > 0),
    total_cents bigint NOT NULL CHECK (total_cents > 0),
    stripe_account_id text NOT NULL,
    livemode boolean NOT NULL CHECK (livemode=false),
    stripe_checkout_session_id text UNIQUE,
    idempotency_key text NOT NULL CHECK (length(trim(idempotency_key)) > 0),
    status text NOT NULL DEFAULT 'prepared' CHECK (status IN ('prepared','canceled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NOT NULL CHECK (length(trim(created_by)) > 0),
    FOREIGN KEY (pricing_table_id,pricing_version,pricing_hash,currency)
        REFERENCES psique_pricing_tables(id,version,config_hash,currency) ON DELETE RESTRICT,
    FOREIGN KEY (mapping_id,offer_id,pricing_table_id,stripe_account_id,livemode)
        REFERENCES psique_stripe_price_mappings(id,offer_id,pricing_table_id,stripe_account_id,livemode)
        ON DELETE RESTRICT,
    UNIQUE (organization_id,idempotency_key),
    CHECK (stripe_checkout_session_id IS NULL OR stripe_checkout_session_id ~ '^cs_test_[A-Za-z0-9]+$')
);

CREATE OR REPLACE FUNCTION psique_v2_purchase_snapshot_guard()
RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE offer psique_pricing_offers%ROWTYPE; org_type text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'psique_purchase_history_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND (to_jsonb(NEW) - ARRAY['status','stripe_checkout_session_id'])
        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','stripe_checkout_session_id']) THEN
        RAISE EXCEPTION 'psique_purchase_snapshot_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.stripe_checkout_session_id IS NOT NULL
        AND NEW.stripe_checkout_session_id IS DISTINCT FROM OLD.stripe_checkout_session_id THEN
        RAISE EXCEPTION 'psique_checkout_identity_is_immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status='canceled' AND NEW.status<>OLD.status THEN
        RAISE EXCEPTION 'psique_canceled_purchase_is_terminal';
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

CREATE TRIGGER psique_purchase_guard BEFORE INSERT OR UPDATE OR DELETE
    ON psique_purchases FOR EACH ROW EXECUTE FUNCTION psique_v2_purchase_snapshot_guard();
CREATE TRIGGER psique_mapping_immutable BEFORE UPDATE OR DELETE
    ON psique_stripe_price_mappings FOR EACH ROW EXECUTE FUNCTION psique_v2_catalog_immutable();

ALTER TABLE psique_stripe_price_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_purchases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON psique_stripe_price_mappings, psique_purchases FROM PUBLIC;
REVOKE ALL ON FUNCTION psique_v2_purchase_snapshot_guard() FROM PUBLIC;

INSERT INTO schema_migrations(version) VALUES ('036_psique_v2_purchases')
ON CONFLICT (version) DO NOTHING;
COMMIT;
