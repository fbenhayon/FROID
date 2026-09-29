BEGIN;

-- Phase 1 only: no public API, activation, legacy price replacement or credits.
-- Apply explicitly with tools/migrate_schema.py, never through ensure_schema.
CREATE TABLE IF NOT EXISTS psique_pricing_tables (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL CHECK (code = 'FROID_PSIQUE_V2'),
    version text NOT NULL CHECK (length(trim(version)) > 0),
    currency text NOT NULL CHECK (currency = 'brl'),
    valid_from timestamptz,
    valid_to timestamptz,
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','active','inactive','archived')),
    canonical_json text NOT NULL,
    config_hash text NOT NULL CHECK (config_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NOT NULL CHECK (length(trim(created_by)) > 0),
    UNIQUE (code, version),
    UNIQUE (id, version, config_hash, currency),
    CHECK (encode(digest(canonical_json, 'sha256'), 'hex') = config_hash),
    CHECK ((canonical_json::jsonb ->> 'code') IS NOT DISTINCT FROM code),
    CHECK ((canonical_json::jsonb ->> 'version') IS NOT DISTINCT FROM version),
    CHECK ((canonical_json::jsonb ->> 'currency') IS NOT DISTINCT FROM currency),
    CHECK (status = 'draft' OR valid_from IS NOT NULL),
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to > valid_from))
);

CREATE UNIQUE INDEX IF NOT EXISTS psique_pricing_one_active
    ON psique_pricing_tables(code, currency) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS psique_pricing_offers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pricing_table_id uuid NOT NULL REFERENCES psique_pricing_tables(id) ON DELETE RESTRICT,
    product_code text NOT NULL,
    name text NOT NULL,
    credits integer,
    total_cents bigint,
    billing_type text NOT NULL
        CHECK (billing_type IN ('one_time','usage','monthly_graduated')),
    active boolean NOT NULL,
    public boolean NOT NULL DEFAULT false,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (pricing_table_id, product_code),
    UNIQUE (id, pricing_table_id),
    CHECK (
        (billing_type = 'one_time' AND credits IS NOT NULL AND credits > 0
            AND total_cents IS NOT NULL AND total_cents > 0)
        OR (billing_type = 'usage' AND credits IS NULL
            AND total_cents IS NOT NULL AND total_cents > 0)
        OR (billing_type = 'monthly_graduated' AND credits IS NULL AND total_cents IS NULL)
    )
);

CREATE OR REPLACE FUNCTION psique_v2_catalog_immutable()
RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'psique_pricing_history_is_immutable';
    END IF;
    IF TG_TABLE_NAME = 'psique_pricing_tables' THEN
        IF OLD.status <> 'draft' AND NEW.status = 'draft' THEN
            RAISE EXCEPTION 'psique_pricing_cannot_return_to_draft';
        END IF;
        IF (to_jsonb(NEW) - ARRAY['status','valid_from','valid_to'])
           IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','valid_from','valid_to']) THEN
            RAISE EXCEPTION 'psique_pricing_new_version_required';
        END IF;
        IF OLD.status <> 'draft' AND
           (NEW.valid_from IS DISTINCT FROM OLD.valid_from OR NEW.valid_to IS DISTINCT FROM OLD.valid_to) THEN
            RAISE EXCEPTION 'psique_pricing_validity_is_immutable';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'psique_pricing_new_version_required';
END;
$$;

CREATE OR REPLACE FUNCTION psique_v2_offer_matches_catalog()
RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE expected jsonb;
BEGIN
    SELECT offer INTO expected
    FROM psique_pricing_tables parent,
         jsonb_array_elements(parent.canonical_json::jsonb -> 'offers') offer
    WHERE parent.id=NEW.pricing_table_id AND offer->>'product_code'=NEW.product_code;
    IF expected IS NULL OR expected IS DISTINCT FROM jsonb_build_object(
        'product_code', NEW.product_code, 'name', NEW.name, 'credits', NEW.credits,
        'total_cents', NEW.total_cents, 'billing_type', NEW.billing_type,
        'active', NEW.active, 'public', NEW.public
    ) OR NEW.metadata <> '{}'::jsonb THEN
        RAISE EXCEPTION 'psique_offer_does_not_match_hashed_catalog';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER psique_pricing_tables_immutable BEFORE UPDATE OR DELETE
    ON psique_pricing_tables FOR EACH ROW EXECUTE FUNCTION psique_v2_catalog_immutable();
CREATE TRIGGER psique_pricing_offers_immutable BEFORE UPDATE OR DELETE
    ON psique_pricing_offers FOR EACH ROW EXECUTE FUNCTION psique_v2_catalog_immutable();
CREATE TRIGGER psique_pricing_offer_content BEFORE INSERT
    ON psique_pricing_offers FOR EACH ROW EXECUTE FUNCTION psique_v2_offer_matches_catalog();

ALTER TABLE psique_pricing_tables ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_pricing_offers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON psique_pricing_tables, psique_pricing_offers FROM PUBLIC;
REVOKE ALL ON FUNCTION psique_v2_catalog_immutable() FROM PUBLIC;
REVOKE ALL ON FUNCTION psique_v2_offer_matches_catalog() FROM PUBLIC;

INSERT INTO schema_migrations(version) VALUES ('035_psique_v2_pricing')
ON CONFLICT (version) DO NOTHING;
COMMIT;
