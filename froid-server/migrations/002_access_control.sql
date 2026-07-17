BEGIN;

CREATE TABLE IF NOT EXISTS membership_invitations (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    invited_email text NOT NULL,
    invited_by_membership_id uuid NOT NULL,
    token_hash text NOT NULL,
    requested_roles jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'expired', 'revoked')),
    expires_at timestamptz NOT NULL,
    accepted_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, token_hash),
    FOREIGN KEY (organization_id, invited_by_membership_id)
        REFERENCES organization_memberships(organization_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS membership_invitations_lookup_idx
    ON membership_invitations (organization_id, lower(invited_email), status);

ALTER TABLE membership_invitations ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION froid_current_organization_id()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
    SELECT nullif(current_setting('app.organization_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION froid_current_membership_id()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
    SELECT nullif(current_setting('app.membership_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION froid_has_role(required_roles text[])
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM organization_memberships membership
        JOIN membership_roles membership_role
          ON membership_role.membership_id = membership.id
        WHERE membership.id = froid_current_membership_id()
          AND membership.organization_id = froid_current_organization_id()
          AND membership.status = 'active'
          AND membership_role.role = ANY(required_roles)
    )
$$;

REVOKE ALL ON FUNCTION froid_has_role(text[]) FROM PUBLIC;

DROP POLICY IF EXISTS tenant_isolation ON membership_invitations;
CREATE POLICY membership_invitations_manage ON membership_invitations
    USING (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator']::text[])
    )
    WITH CHECK (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator']::text[])
    );

-- Replace the broad Phase 1 patient policy with assignment-aware policies.
DROP POLICY IF EXISTS tenant_isolation ON patients;
DROP POLICY IF EXISTS patients_read ON patients;
DROP POLICY IF EXISTS patients_insert ON patients;
DROP POLICY IF EXISTS patients_update ON patients;
DROP POLICY IF EXISTS patients_delete ON patients;

CREATE POLICY patients_read ON patients FOR SELECT
    USING (
        organization_id = froid_current_organization_id()
        AND (
            froid_has_role(ARRAY['owner', 'administrator', 'supervisor']::text[])
            OR EXISTS (
                SELECT 1 FROM patient_assignments assignment
                WHERE assignment.organization_id = patients.organization_id
                  AND assignment.patient_id = patients.id
                  AND assignment.membership_id = froid_current_membership_id()
                  AND assignment.status = 'active'
            )
        )
    );

CREATE POLICY patients_insert ON patients FOR INSERT
    WITH CHECK (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator', 'professional']::text[])
    );

CREATE POLICY patients_update ON patients FOR UPDATE
    USING (
        organization_id = froid_current_organization_id()
        AND (
            froid_has_role(ARRAY['owner', 'administrator']::text[])
            OR EXISTS (
                SELECT 1 FROM patient_assignments assignment
                WHERE assignment.organization_id = patients.organization_id
                  AND assignment.patient_id = patients.id
                  AND assignment.membership_id = froid_current_membership_id()
                  AND assignment.status = 'active'
            )
        )
    )
    WITH CHECK (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator', 'professional']::text[])
    );

CREATE POLICY patients_delete ON patients FOR DELETE
    USING (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator']::text[])
    );

DROP POLICY IF EXISTS tenant_isolation ON patient_assignments;
DROP POLICY IF EXISTS patient_assignments_read ON patient_assignments;
DROP POLICY IF EXISTS patient_assignments_manage ON patient_assignments;

CREATE POLICY patient_assignments_read ON patient_assignments FOR SELECT
    USING (
        organization_id = froid_current_organization_id()
        AND (
            membership_id = froid_current_membership_id()
            OR froid_has_role(ARRAY['owner', 'administrator', 'supervisor']::text[])
        )
    );

CREATE POLICY patient_assignments_manage ON patient_assignments FOR ALL
    USING (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator', 'supervisor']::text[])
    )
    WITH CHECK (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator', 'supervisor']::text[])
    );

-- Reports follow the patient assignment for professionals. Supervisors are
-- read-only; owners and administrators can manage the organization's records.
DROP POLICY IF EXISTS tenant_isolation ON session_reports;
DROP POLICY IF EXISTS session_reports_read ON session_reports;
DROP POLICY IF EXISTS session_reports_insert ON session_reports;
DROP POLICY IF EXISTS session_reports_update ON session_reports;
DROP POLICY IF EXISTS session_reports_delete ON session_reports;

CREATE POLICY session_reports_read ON session_reports FOR SELECT
    USING (
        organization_id = froid_current_organization_id()
        AND (
            froid_has_role(ARRAY['owner', 'administrator', 'supervisor']::text[])
            OR professional_membership_id = froid_current_membership_id()
            OR EXISTS (
                SELECT 1 FROM patient_assignments assignment
                WHERE assignment.organization_id = session_reports.organization_id
                  AND assignment.patient_id = session_reports.patient_id
                  AND assignment.membership_id = froid_current_membership_id()
                  AND assignment.status = 'active'
            )
        )
    );

CREATE POLICY session_reports_insert ON session_reports FOR INSERT
    WITH CHECK (
        organization_id = froid_current_organization_id()
        AND professional_membership_id = froid_current_membership_id()
        AND froid_has_role(ARRAY['owner', 'administrator', 'professional']::text[])
    );

CREATE POLICY session_reports_update ON session_reports FOR UPDATE
    USING (
        organization_id = froid_current_organization_id()
        AND (
            froid_has_role(ARRAY['owner', 'administrator']::text[])
            OR professional_membership_id = froid_current_membership_id()
        )
    )
    WITH CHECK (organization_id = froid_current_organization_id());

CREATE POLICY session_reports_delete ON session_reports FOR DELETE
    USING (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator']::text[])
    );

-- Auditors can read the append-only audit trail but never clinical payloads.
DROP POLICY IF EXISTS tenant_isolation ON audit_events;
DROP POLICY IF EXISTS audit_events_read ON audit_events;
DROP POLICY IF EXISTS audit_events_insert ON audit_events;

CREATE POLICY audit_events_read ON audit_events FOR SELECT
    USING (
        organization_id = froid_current_organization_id()
        AND froid_has_role(ARRAY['owner', 'administrator', 'auditor']::text[])
    );

CREATE POLICY audit_events_insert ON audit_events FOR INSERT
    WITH CHECK (organization_id = froid_current_organization_id());

INSERT INTO schema_migrations (version)
VALUES ('002_access_control')
ON CONFLICT (version) DO NOTHING;

COMMIT;
