BEGIN;

-- Phase 2A is opt-in per EMPTY wallet. No V1 balance is converted or backfilled.
ALTER TABLE organization_wallets
    ADD COLUMN reserved_balance integer NOT NULL DEFAULT 0,
    ADD COLUMN credit_model text NOT NULL DEFAULT 'v1',
    ADD CONSTRAINT wallet_credit_model_check CHECK (credit_model IN ('v1','psique_v2')),
    ADD CONSTRAINT wallet_reservation_bounds CHECK
        (reserved_balance >= 0 AND reserved_balance <= balance),
    ADD CONSTRAINT wallet_v1_has_no_reservations CHECK
        (credit_model <> 'v1' OR reserved_balance = 0),
    ADD CONSTRAINT wallet_v2_is_shared CHECK
        (credit_model <> 'psique_v2' OR authority='shared');

CREATE TABLE psique_trial_eligibility (
    key_version text NOT NULL CHECK (length(trim(key_version)) > 0),
    email_hmac text NOT NULL CHECK (email_hmac ~ '^[0-9a-f]{64}$'),
    beneficiary_id uuid NOT NULL,
    -- Historical identifiers deliberately survive deletion/anonymization of accounts.
    organization_id uuid NOT NULL,
    eligibility_origin text NOT NULL CHECK (eligibility_origin IN ('V1','V2')),
    evidence_ref text NOT NULL CHECK (length(trim(evidence_ref)) > 0),
    verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (key_version,email_hmac)
);

CREATE TABLE psique_trials (
    organization_id uuid PRIMARY KEY REFERENCES organization_wallets(organization_id) ON DELETE RESTRICT,
    beneficiary_id uuid NOT NULL,
    status text NOT NULL CHECK (status IN ('ACTIVE','EXHAUSTED','EXPIRED','INELIGIBLE')),
    started_at timestamptz,
    expires_at timestamptz,
    credits_granted integer NOT NULL CHECK (credits_granted=0 OR credits_granted=10),
    credits_used integer NOT NULL DEFAULT 0 CHECK (credits_used >= 0),
    credits_reserved integer NOT NULL DEFAULT 0 CHECK (credits_reserved >= 0),
    credits_expired integer NOT NULL DEFAULT 0 CHECK (credits_expired >= 0),
    CHECK (credits_used + credits_reserved + credits_expired <= credits_granted),
    CHECK ((status='INELIGIBLE' AND credits_granted=0 AND started_at IS NULL AND expires_at IS NULL)
        OR (status<>'INELIGIBLE' AND credits_granted=10 AND started_at IS NOT NULL
            AND expires_at=started_at + interval '336 hours'))
);

CREATE TABLE psique_analysis_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organization_wallets(organization_id) ON DELETE RESTRICT,
    owner_membership_id uuid NOT NULL,
    material_key uuid NOT NULL,
    legacy_session_id text NOT NULL CHECK (length(trim(legacy_session_id)) > 0),
    source_kind text NOT NULL CHECK (source_kind IN ('file','stream')),
    source_sha256 text CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (organization_id,owner_membership_id)
        REFERENCES organization_memberships(organization_id,id) ON DELETE RESTRICT,
    UNIQUE (organization_id,material_key),
    UNIQUE (organization_id,id),
    CHECK (source_kind <> 'file' OR source_sha256 IS NOT NULL)
);

CREATE TABLE psique_analysis_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    analysis_source_id uuid NOT NULL,
    execution_key text NOT NULL CHECK (length(trim(execution_key)) > 0),
    status text NOT NULL DEFAULT 'PROCESSING'
        CHECK (status IN ('PROCESSING','DELIVERED','FAILED')),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    lease_until timestamptz NOT NULL,
    technical_completed_at timestamptz,
    delivered_at timestamptz,
    report_id uuid REFERENCES session_reports(id) ON DELETE RESTRICT,
    delivery_sha256 text CHECK (delivery_sha256 ~ '^[0-9a-f]{64}$'),
    failure_reason text,
    FOREIGN KEY (organization_id,analysis_source_id)
        REFERENCES psique_analysis_sources(organization_id,id) ON DELETE RESTRICT,
    UNIQUE (organization_id,id),
    UNIQUE (organization_id,analysis_source_id,id),
    UNIQUE (organization_id,analysis_source_id,execution_key),
    CHECK (lease_until > started_at),
    CHECK ((report_id IS NOT NULL AND delivered_at IS NOT NULL
            AND technical_completed_at IS NOT NULL AND delivery_sha256 IS NOT NULL)
        OR (report_id IS NULL AND delivered_at IS NULL
            AND technical_completed_at IS NULL AND delivery_sha256 IS NULL)),
    CHECK (status<>'DELIVERED' OR report_id IS NOT NULL),
    CHECK (status<>'PROCESSING' OR report_id IS NULL),
    CHECK (status<>'FAILED' OR (failure_reason IS NOT NULL AND length(trim(failure_reason)) > 0))
);
CREATE UNIQUE INDEX psique_one_processing_attempt ON psique_analysis_attempts(analysis_source_id)
    WHERE status='PROCESSING';

CREATE TABLE psique_credit_reservations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    analysis_source_id uuid NOT NULL,
    analysis_attempt_id uuid NOT NULL UNIQUE,
    funding text NOT NULL CHECK (funding IN ('TRIAL','PAID')),
    status text NOT NULL DEFAULT 'RESERVED' CHECK (status IN ('RESERVED','CONSUMED','RELEASED')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    resolved_at timestamptz,
    FOREIGN KEY (organization_id,analysis_source_id,analysis_attempt_id)
        REFERENCES psique_analysis_attempts(organization_id,analysis_source_id,id) ON DELETE RESTRICT,
    UNIQUE (organization_id,id),
    CHECK ((status='RESERVED' AND resolved_at IS NULL) OR (status<>'RESERVED' AND resolved_at IS NOT NULL))
);
CREATE UNIQUE INDEX psique_one_reserved_credit ON psique_credit_reservations(analysis_source_id)
    WHERE status='RESERVED';

ALTER TABLE credit_ledger
    ADD COLUMN ledger_version smallint NOT NULL DEFAULT 1 CHECK (ledger_version BETWEEN 1 AND 2),
    ADD COLUMN reserved_delta integer NOT NULL DEFAULT 0,
    ADD COLUMN reserved_after integer NOT NULL DEFAULT 0 CHECK (reserved_after >= 0),
    ADD COLUMN analysis_source_id uuid,
    ADD COLUMN reservation_id uuid,
    ADD COLUMN original_consumption_id uuid REFERENCES credit_ledger(id) ON DELETE RESTRICT,
    ADD COLUMN funding text CHECK (funding IN ('TRIAL','PAID')),
    ADD COLUMN reason text;
ALTER TABLE credit_ledger DROP CONSTRAINT credit_ledger_event_type_check;
ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_event_type_check CHECK (event_type IN (
    'purchase','consumption','refund','adjustment','migration_opening',
    'TRIAL_GRANT','TRIAL_EXPIRATION','CREDIT_RESERVATION','CREDIT_CONSUMPTION',
    'CREDIT_RELEASE','CREDIT_RESTORE','MANUAL_ADJUSTMENT','CREDIT_PURCHASE'));
ALTER TABLE credit_ledger
    ADD FOREIGN KEY (organization_id,analysis_source_id)
        REFERENCES psique_analysis_sources(organization_id,id) ON DELETE RESTRICT,
    ADD FOREIGN KEY (organization_id,reservation_id)
        REFERENCES psique_credit_reservations(organization_id,id) ON DELETE RESTRICT,
    ADD CONSTRAINT credit_ledger_version_semantics CHECK (
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
        ))
    );
CREATE UNIQUE INDEX psique_one_consumption_per_source ON credit_ledger(analysis_source_id)
    WHERE ledger_version=2 AND event_type='CREDIT_CONSUMPTION';
CREATE UNIQUE INDEX psique_one_restore_per_consumption ON credit_ledger(original_consumption_id)
    WHERE ledger_version=2 AND event_type='CREDIT_RESTORE';

CREATE FUNCTION psique_credit_history_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
DECLARE model text;
BEGIN
    IF TG_OP<>'INSERT' THEN
        IF OLD.ledger_version=2 THEN RAISE EXCEPTION 'PSIQUE_LEDGER_IMMUTABLE'; END IF;
        IF TG_OP='UPDATE' AND NEW.ledger_version<>OLD.ledger_version THEN
            RAISE EXCEPTION 'LEDGER_VERSION_IMMUTABLE';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;
    SELECT credit_model INTO model FROM organization_wallets WHERE organization_id=NEW.organization_id;
    IF (NEW.ledger_version=2 AND model IS DISTINCT FROM 'psique_v2') OR
        (NEW.ledger_version=1 AND model='psique_v2') THEN
        RAISE EXCEPTION 'WALLET_CREDIT_MODEL_MISMATCH';
    END IF;
    IF NEW.ledger_version=2 AND NEW.event_type IN ('CREDIT_RESERVATION','CREDIT_CONSUMPTION','CREDIT_RELEASE','CREDIT_RESTORE')
        AND (NEW.analysis_source_id IS NULL OR NEW.funding IS NULL) THEN
        RAISE EXCEPTION 'SOURCE_AND_FUNDING_REQUIRED';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER psique_credit_history BEFORE INSERT OR UPDATE OR DELETE ON credit_ledger
    FOR EACH ROW EXECUTE FUNCTION psique_credit_history_guard();

CREATE FUNCTION psique_identity_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN RAISE EXCEPTION 'PSIQUE_IDENTITY_IMMUTABLE'; END $$;
CREATE TRIGGER psique_source_immutable BEFORE UPDATE OR DELETE ON psique_analysis_sources
    FOR EACH ROW EXECUTE FUNCTION psique_identity_immutable();
CREATE TRIGGER psique_eligibility_immutable BEFORE UPDATE OR DELETE ON psique_trial_eligibility
    FOR EACH ROW EXECUTE FUNCTION psique_identity_immutable();

ALTER TABLE psique_trials ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_trial_eligibility ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_analysis_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_analysis_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_credit_reservations ENABLE ROW LEVEL SECURITY;
-- All access goes through the scoped functions in the next explicit migration.
REVOKE ALL ON psique_trials,psique_trial_eligibility,psique_analysis_sources,
    psique_analysis_attempts,psique_credit_reservations FROM PUBLIC;
REVOKE ALL ON FUNCTION psique_credit_history_guard(),psique_identity_immutable() FROM PUBLIC;

INSERT INTO schema_migrations(version) VALUES('037_psique_trial_credit_state');
COMMIT;
