BEGIN;

CREATE TABLE IF NOT EXISTS legal_acceptance_events (
    id uuid PRIMARY KEY,
    organization_id uuid,
    subject_kind text NOT NULL CHECK (subject_kind IN ('professional', 'organization', 'patient')),
    subject_reference_hash char(64) NOT NULL,
    document_key text NOT NULL,
    document_version text NOT NULL,
    document_sha256 char(64) NOT NULL,
    acceptance_context text NOT NULL,
    commercial_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    request_fingerprint_hash char(64),
    accepted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS legal_acceptance_subject_idx
    ON legal_acceptance_events
    (subject_reference_hash, document_key, accepted_at DESC);
CREATE INDEX IF NOT EXISTS legal_acceptance_organization_idx
    ON legal_acceptance_events
    (organization_id, accepted_at DESC)
    WHERE organization_id IS NOT NULL;

CREATE OR REPLACE FUNCTION prevent_legal_acceptance_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'legal_acceptance_events is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS legal_acceptance_events_no_mutation
    ON legal_acceptance_events;
CREATE TRIGGER legal_acceptance_events_no_mutation
BEFORE UPDATE OR DELETE ON legal_acceptance_events
FOR EACH ROW EXECUTE FUNCTION prevent_legal_acceptance_mutation();

ALTER TABLE legal_acceptance_events ENABLE ROW LEVEL SECURITY;

-- Runtime users never write legal evidence. The application owner records it
-- server-side after authenticating the subject and validating the document hash.
REVOKE ALL ON legal_acceptance_events FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    REVOKE ALL ON legal_acceptance_events FROM froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version)
VALUES('009_legal_acceptance_ledger') ON CONFLICT DO NOTHING;

COMMIT;
