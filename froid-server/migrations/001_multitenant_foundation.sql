BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organizations (
    id uuid PRIMARY KEY,
    organization_type text NOT NULL DEFAULT 'clinic'
        CHECK (organization_type IN ('solo', 'clinic', 'enterprise', 'legacy')),
    legal_name text NOT NULL,
    display_name text NOT NULL,
    document text,
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'suspended', 'archived')),
    legacy_owner_email text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS organizations_document_idx
    ON organizations (document) WHERE document IS NOT NULL AND document <> '';
CREATE UNIQUE INDEX IF NOT EXISTS organizations_legacy_owner_unique
    ON organizations (legacy_owner_email)
    WHERE legacy_owner_email IS NOT NULL AND legacy_owner_email <> '';

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY,
    email text NOT NULL,
    display_name text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('invited', 'active', 'disabled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users (lower(email));

CREATE TABLE IF NOT EXISTS organization_memberships (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('invited', 'active', 'suspended', 'revoked')),
    joined_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, user_id),
    UNIQUE (organization_id, id)
);

CREATE TABLE IF NOT EXISTS membership_roles (
    membership_id uuid NOT NULL REFERENCES organization_memberships(id) ON DELETE CASCADE,
    role text NOT NULL
        CHECK (role IN ('owner', 'administrator', 'supervisor', 'professional', 'auditor')),
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (membership_id, role)
);

CREATE TABLE IF NOT EXISTS patients (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    legacy_patient_id text,
    full_name text NOT NULL,
    email text,
    phone text,
    document text,
    birth_date text,
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'restricted', 'deleted')),
    legacy_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, legacy_patient_id),
    UNIQUE (organization_id, id)
);

CREATE INDEX IF NOT EXISTS patients_organization_idx ON patients (organization_id);
CREATE INDEX IF NOT EXISTS patients_email_idx ON patients (organization_id, lower(email));
CREATE INDEX IF NOT EXISTS patients_document_idx ON patients (organization_id, document);

CREATE TABLE IF NOT EXISTS patient_assignments (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    patient_id uuid NOT NULL,
    membership_id uuid NOT NULL,
    assignment_type text NOT NULL DEFAULT 'primary'
        CHECK (assignment_type IN ('primary', 'care_team', 'supervisor', 'read_only')),
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked')),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    UNIQUE (patient_id, membership_id, assignment_type),
    FOREIGN KEY (organization_id, patient_id)
        REFERENCES patients(organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, membership_id)
        REFERENCES organization_memberships(organization_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS patient_assignments_scope_idx
    ON patient_assignments (organization_id, membership_id, status);

CREATE TABLE IF NOT EXISTS session_reports (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    legacy_session_id text NOT NULL,
    patient_id uuid,
    professional_membership_id uuid,
    report_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (organization_id, legacy_session_id),
    FOREIGN KEY (organization_id, patient_id)
        REFERENCES patients(organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, professional_membership_id)
        REFERENCES organization_memberships(organization_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS session_reports_scope_idx
    ON session_reports (organization_id, patient_id, created_at DESC);

CREATE TABLE IF NOT EXISTS consents (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    patient_id uuid,
    legacy_invite_id text,
    legacy_session_id text,
    consent_version text NOT NULL,
    consent_hash text NOT NULL,
    accepted_at timestamptz NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, consent_hash),
    FOREIGN KEY (organization_id, patient_id)
        REFERENCES patients(organization_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS organization_wallets (
    organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE RESTRICT,
    balance integer NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    delta integer NOT NULL,
    balance_after integer NOT NULL CHECK (balance_after >= 0),
    event_type text NOT NULL
        CHECK (event_type IN ('purchase', 'consumption', 'refund', 'adjustment', 'migration_opening')),
    legacy_session_id text,
    idempotency_key text NOT NULL,
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    outcome text NOT NULL DEFAULT 'success',
    ip_address inet,
    user_agent text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_scope_idx
    ON audit_events (organization_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events;
CREATE TRIGGER audit_events_no_update
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

CREATE TABLE IF NOT EXISTS migration_runs (
    id uuid PRIMARY KEY,
    migration_version text NOT NULL,
    mode text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    source_fingerprint text,
    counters jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

-- RLS is enabled now so restricted database roles can enforce tenant boundaries.
-- The migration/application owner intentionally retains PostgreSQL's owner bypass
-- during Phase 1. A non-owner runtime role becomes mandatory before cutover.
DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'organization_memberships', 'patients', 'patient_assignments',
        'session_reports', 'consents', 'organization_wallets',
        'credit_ledger', 'audit_events'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', table_name);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING '
            || '(organization_id = nullif(current_setting(''app.organization_id'', true), '''')::uuid) '
            || 'WITH CHECK (organization_id = nullif(current_setting(''app.organization_id'', true), '''')::uuid)',
            table_name
        );
    END LOOP;
END $$;

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON organizations;
CREATE POLICY tenant_isolation ON organizations
    USING (id = nullif(current_setting('app.organization_id', true), '')::uuid)
    WITH CHECK (id = nullif(current_setting('app.organization_id', true), '')::uuid);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_members_only ON users;
CREATE POLICY tenant_members_only ON users
    USING (EXISTS (
        SELECT 1 FROM organization_memberships membership
        WHERE membership.user_id = users.id
          AND membership.organization_id =
              nullif(current_setting('app.organization_id', true), '')::uuid
    ));

ALTER TABLE membership_roles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_membership_roles ON membership_roles;
CREATE POLICY tenant_membership_roles ON membership_roles
    USING (EXISTS (
        SELECT 1 FROM organization_memberships membership
        WHERE membership.id = membership_roles.membership_id
          AND membership.organization_id =
              nullif(current_setting('app.organization_id', true), '')::uuid
    ));

INSERT INTO schema_migrations (version)
VALUES ('001_multitenant_foundation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
