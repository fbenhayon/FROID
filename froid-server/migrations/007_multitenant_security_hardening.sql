BEGIN;

-- The application serializes primary assignment changes by patient. This
-- index also preserves the invariant under concurrent workers and scripts.
CREATE UNIQUE INDEX IF NOT EXISTS patient_assignments_one_active_primary
  ON patient_assignments(organization_id, patient_id)
  WHERE assignment_type='primary' AND status='active';

-- All restricted-role policies now require a real active membership. Session
-- settings select the tenant, but they are not treated as proof of membership.
DROP POLICY IF EXISTS tenant_isolation ON organizations;
DROP POLICY IF EXISTS organizations_read ON organizations;
CREATE POLICY organizations_read ON organizations FOR SELECT USING (
  id=froid_current_organization_id() AND froid_membership_is_active()
);

DROP POLICY IF EXISTS tenant_members_only ON users;
DROP POLICY IF EXISTS users_read ON users;
CREATE POLICY users_read ON users FOR SELECT USING (
  froid_membership_is_active() AND EXISTS (
    SELECT 1 FROM organization_memberships membership
    WHERE membership.user_id=users.id
      AND membership.organization_id=froid_current_organization_id()
  )
);

DROP POLICY IF EXISTS tenant_isolation ON organization_memberships;
DROP POLICY IF EXISTS organization_memberships_read ON organization_memberships;
CREATE POLICY organization_memberships_read ON organization_memberships FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);

DROP POLICY IF EXISTS tenant_membership_roles ON membership_roles;
DROP POLICY IF EXISTS membership_roles_read ON membership_roles;
CREATE POLICY membership_roles_read ON membership_roles FOR SELECT USING (
  froid_membership_is_active() AND EXISTS (
    SELECT 1 FROM organization_memberships membership
    WHERE membership.id=membership_roles.membership_id
      AND membership.organization_id=froid_current_organization_id()
  )
);

DROP POLICY IF EXISTS membership_invitations_manage ON membership_invitations;
CREATE POLICY membership_invitations_manage ON membership_invitations FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator']::text[])
);

DROP POLICY IF EXISTS patients_read ON patients;
DROP POLICY IF EXISTS patients_insert ON patients;
DROP POLICY IF EXISTS patients_update ON patients;
DROP POLICY IF EXISTS patients_delete ON patients;

CREATE POLICY patients_read ON patients FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    froid_has_role(ARRAY['owner','administrator','supervisor']::text[])
    OR (
      froid_has_role(ARRAY['professional']::text[])
      AND EXISTS (
        SELECT 1 FROM patient_assignments assignment
        WHERE assignment.organization_id=patients.organization_id
          AND assignment.patient_id=patients.id
          AND assignment.membership_id=froid_current_membership_id()
          AND assignment.status='active'
      )
    )
  )
);

CREATE POLICY patients_insert ON patients FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','professional']::text[])
);

CREATE POLICY patients_update ON patients FOR UPDATE
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    froid_has_role(ARRAY['owner','administrator']::text[])
    OR (
      froid_has_role(ARRAY['professional']::text[])
      AND EXISTS (
        SELECT 1 FROM patient_assignments assignment
        WHERE assignment.organization_id=patients.organization_id
          AND assignment.patient_id=patients.id
          AND assignment.membership_id=froid_current_membership_id()
          AND assignment.status='active'
      )
    )
  )
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','professional']::text[])
);

CREATE POLICY patients_delete ON patients FOR DELETE USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator']::text[])
);

DROP POLICY IF EXISTS patient_assignments_read ON patient_assignments;
DROP POLICY IF EXISTS patient_assignments_manage ON patient_assignments;
CREATE POLICY patient_assignments_read ON patient_assignments FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    froid_has_role(ARRAY['owner','administrator','supervisor']::text[])
    OR (
      membership_id=froid_current_membership_id()
      AND froid_has_role(ARRAY['professional']::text[])
    )
  )
);
CREATE POLICY patient_assignments_manage ON patient_assignments FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','supervisor']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','supervisor']::text[])
);

DROP POLICY IF EXISTS session_reports_read ON session_reports;
DROP POLICY IF EXISTS session_reports_insert ON session_reports;
DROP POLICY IF EXISTS session_reports_update ON session_reports;
DROP POLICY IF EXISTS session_reports_delete ON session_reports;

CREATE POLICY session_reports_read ON session_reports FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    froid_has_role(ARRAY['owner','administrator','supervisor']::text[])
    OR (
      froid_has_role(ARRAY['professional']::text[])
      AND (
        professional_membership_id=froid_current_membership_id()
        OR EXISTS (
          SELECT 1 FROM patient_assignments assignment
          WHERE assignment.organization_id=session_reports.organization_id
            AND assignment.patient_id=session_reports.patient_id
            AND assignment.membership_id=froid_current_membership_id()
            AND assignment.status='active'
        )
      )
    )
  )
);

CREATE POLICY session_reports_insert ON session_reports FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND professional_membership_id=froid_current_membership_id()
  AND froid_has_role(ARRAY['owner','administrator','professional']::text[])
  AND (
    froid_has_role(ARRAY['owner','administrator']::text[])
    OR patient_id IS NULL
    OR EXISTS (
      SELECT 1 FROM patient_assignments assignment
      WHERE assignment.organization_id=session_reports.organization_id
        AND assignment.patient_id=session_reports.patient_id
        AND assignment.membership_id=froid_current_membership_id()
        AND assignment.status='active'
    )
  )
);

CREATE POLICY session_reports_update ON session_reports FOR UPDATE
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    froid_has_role(ARRAY['owner','administrator']::text[])
    OR (
      professional_membership_id=froid_current_membership_id()
      AND froid_has_role(ARRAY['professional']::text[])
    )
  )
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    froid_has_role(ARRAY['owner','administrator']::text[])
    OR (
      professional_membership_id=froid_current_membership_id()
      AND froid_has_role(ARRAY['professional']::text[])
      AND (
        patient_id IS NULL
        OR EXISTS (
          SELECT 1 FROM patient_assignments assignment
          WHERE assignment.organization_id=session_reports.organization_id
            AND assignment.patient_id=session_reports.patient_id
            AND assignment.membership_id=froid_current_membership_id()
            AND assignment.status='active'
        )
      )
    )
  )
);

CREATE POLICY session_reports_delete ON session_reports FOR DELETE USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator']::text[])
);

DROP POLICY IF EXISTS tenant_isolation ON consents;
DROP POLICY IF EXISTS consents_read ON consents;
DROP POLICY IF EXISTS consents_insert ON consents;
DROP POLICY IF EXISTS consents_update ON consents;
CREATE POLICY consents_read ON consents FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    froid_has_role(ARRAY['owner','administrator','supervisor']::text[])
    OR (
      froid_has_role(ARRAY['professional']::text[])
      AND EXISTS (
        SELECT 1 FROM patient_assignments assignment
        WHERE assignment.organization_id=consents.organization_id
          AND assignment.patient_id=consents.patient_id
          AND assignment.membership_id=froid_current_membership_id()
          AND assignment.status='active'
      )
    )
  )
);
CREATE POLICY consents_insert ON consents FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','professional']::text[])
);
CREATE POLICY consents_update ON consents FOR UPDATE
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);

DROP POLICY IF EXISTS tenant_isolation ON organization_wallets;
DROP POLICY IF EXISTS organization_wallets_read ON organization_wallets;
CREATE POLICY organization_wallets_read ON organization_wallets FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','professional']::text[])
);

DROP POLICY IF EXISTS tenant_isolation ON credit_ledger;
DROP POLICY IF EXISTS credit_ledger_read ON credit_ledger;
CREATE POLICY credit_ledger_read ON credit_ledger FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','professional']::text[])
);

DROP POLICY IF EXISTS audit_events_read ON audit_events;
DROP POLICY IF EXISTS audit_events_insert ON audit_events;
CREATE POLICY audit_events_read ON audit_events FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','auditor']::text[])
);
CREATE POLICY audit_events_insert ON audit_events FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);

DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
  REVOKE DELETE ON membership_roles FROM froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version)
VALUES('007_multitenant_security_hardening') ON CONFLICT DO NOTHING;
COMMIT;
