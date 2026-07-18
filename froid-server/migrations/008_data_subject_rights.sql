BEGIN;

CREATE TABLE IF NOT EXISTS data_subject_requests (
    id uuid PRIMARY KEY,
    request_batch_id uuid NOT NULL,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    patient_id uuid NOT NULL,
    request_type text NOT NULL CHECK (request_type IN (
        'access', 'correction', 'portability', 'processing_information',
        'consent_withdrawal', 'restriction', 'deletion', 'anonymization',
        'automated_review'
    )),
    status text NOT NULL DEFAULT 'submitted' CHECK (status IN (
        'submitted', 'identity_verified', 'in_review', 'awaiting_information',
        'approved', 'partially_approved', 'denied', 'completed', 'cancelled'
    )),
    channel text NOT NULL DEFAULT 'patient_portal',
    request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    response_summary text,
    legal_basis text,
    retention_exception text,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    service_due_at timestamptz NOT NULL DEFAULT (now() + interval '15 days'),
    identity_verified_at timestamptz,
    resolved_at timestamptz,
    resolved_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, patient_id)
        REFERENCES patients(organization_id, id) ON DELETE RESTRICT,
    UNIQUE (organization_id, id)
);

CREATE INDEX IF NOT EXISTS data_subject_requests_patient_idx
    ON data_subject_requests (organization_id, patient_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS data_subject_requests_queue_idx
    ON data_subject_requests (organization_id, status, service_due_at);
CREATE INDEX IF NOT EXISTS data_subject_requests_batch_idx
    ON data_subject_requests (request_batch_id);

CREATE TABLE IF NOT EXISTS data_subject_request_events (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL,
    actor_kind text NOT NULL CHECK (actor_kind IN ('patient', 'professional', 'system')),
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    action text NOT NULL,
    from_status text,
    to_status text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, request_id)
        REFERENCES data_subject_requests(organization_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS data_subject_request_events_idx
    ON data_subject_request_events (organization_id, request_id, occurred_at);

CREATE OR REPLACE FUNCTION prevent_data_subject_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'data_subject_request_events is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS data_subject_request_events_no_update
    ON data_subject_request_events;
CREATE TRIGGER data_subject_request_events_no_update
BEFORE UPDATE OR DELETE ON data_subject_request_events
FOR EACH ROW EXECUTE FUNCTION prevent_data_subject_event_mutation();

ALTER TABLE data_subject_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_subject_request_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS data_subject_requests_read ON data_subject_requests;
DROP POLICY IF EXISTS data_subject_requests_manage ON data_subject_requests;
CREATE POLICY data_subject_requests_read ON data_subject_requests FOR SELECT USING (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND froid_has_role(ARRAY['owner','administrator','supervisor','auditor']::text[])
);
CREATE POLICY data_subject_requests_manage ON data_subject_requests FOR UPDATE
USING (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND froid_has_role(ARRAY['owner','administrator']::text[])
)
WITH CHECK (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
);

DROP POLICY IF EXISTS data_subject_request_events_read ON data_subject_request_events;
DROP POLICY IF EXISTS data_subject_request_events_insert ON data_subject_request_events;
CREATE POLICY data_subject_request_events_read ON data_subject_request_events FOR SELECT USING (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND froid_has_role(ARRAY['owner','administrator','supervisor','auditor']::text[])
);
CREATE POLICY data_subject_request_events_insert ON data_subject_request_events FOR INSERT WITH CHECK (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND froid_has_role(ARRAY['owner','administrator']::text[])
);

DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT SELECT, UPDATE ON data_subject_requests TO froid_runtime;
    GRANT SELECT, INSERT ON data_subject_request_events TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version)
VALUES('008_data_subject_rights') ON CONFLICT DO NOTHING;

COMMIT;
