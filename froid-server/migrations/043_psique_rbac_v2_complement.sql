BEGIN;

-- Pre-Phase 4 review (30/09/2026): the RLS inventory found three tables with
-- patient-linked or governance content whose policies had no V2 branch:
--   patient_research_consent  - tenant-only, NO role at all: any active
--                               member could read research-consent state;
--   validation_administrations/observations - tenant-only, clinical research
--                               scores per patient;
--   data_subject_requests(+events) - LGPD requests readable by the wide V1
--                               supervisor/auditor without a V2 mapping.
-- Same two-branch pattern as migration 042: the V1 body stays verbatim
-- behind NOT psique_rbac_v2_active(); the V2 branch is role-scoped.

DROP POLICY IF EXISTS patient_research_consent_tenant ON patient_research_consent;
CREATE POLICY patient_research_consent_tenant ON patient_research_consent FOR ALL
USING (
  organization_id = current_setting('app.organization_id', TRUE)::uuid
  AND (
    NOT psique_rbac_v2_active(organization_id)
    OR (psique_v2_role_check(ARRAY['CLINICIAN'])
      AND EXISTS (
        SELECT 1 FROM patient_assignments assignment
        WHERE assignment.organization_id=patient_research_consent.organization_id
          AND assignment.patient_id=patient_research_consent.patient_id
          AND assignment.membership_id=froid_current_membership_id()
          AND assignment.status='active'
      ))
  )
)
WITH CHECK (
  organization_id = current_setting('app.organization_id', TRUE)::uuid
  AND (
    NOT psique_rbac_v2_active(organization_id)
    OR psique_v2_role_check(ARRAY['CLINICIAN'])
  )
);

DROP POLICY IF EXISTS validation_admin_tenant ON validation_administrations;
CREATE POLICY validation_admin_tenant ON validation_administrations FOR ALL
USING (
  organization_id = current_setting('app.organization_id', TRUE)::uuid
  AND (
    NOT psique_rbac_v2_active(organization_id)
    OR (psique_v2_role_check(ARRAY['CLINICIAN'])
      AND EXISTS (
        SELECT 1 FROM patient_assignments assignment
        WHERE assignment.organization_id=validation_administrations.organization_id
          AND assignment.patient_id=validation_administrations.patient_id
          AND assignment.membership_id=froid_current_membership_id()
          AND assignment.status='active'
      ))
  )
)
WITH CHECK (
  organization_id = current_setting('app.organization_id', TRUE)::uuid
  AND (
    NOT psique_rbac_v2_active(organization_id)
    OR psique_v2_role_check(ARRAY['CLINICIAN'])
  )
);

DROP POLICY IF EXISTS validation_obs_tenant ON validation_observations;
CREATE POLICY validation_obs_tenant ON validation_observations FOR ALL
USING (EXISTS (
    SELECT 1 FROM validation_administrations a
    WHERE a.id = validation_observations.administration_id
      AND a.organization_id = current_setting('app.organization_id', TRUE)::uuid
      AND (
        NOT psique_rbac_v2_active(a.organization_id)
        OR (psique_v2_role_check(ARRAY['CLINICIAN'])
          AND EXISTS (
            SELECT 1 FROM patient_assignments assignment
            WHERE assignment.organization_id=a.organization_id
              AND assignment.patient_id=a.patient_id
              AND assignment.membership_id=froid_current_membership_id()
              AND assignment.status='active'
          ))
      )
));

DROP POLICY IF EXISTS data_subject_requests_read ON data_subject_requests;
CREATE POLICY data_subject_requests_read ON data_subject_requests FOR SELECT USING (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND (
      (NOT psique_rbac_v2_active(organization_id)
        AND froid_has_role(ARRAY['owner','administrator','supervisor','auditor']::text[]))
      OR (psique_rbac_v2_active(organization_id)
        AND psique_v2_role_check(ARRAY['ORG_ADMIN','AUDITOR_COMPLIANCE']))
    )
);

DROP POLICY IF EXISTS data_subject_requests_manage ON data_subject_requests;
CREATE POLICY data_subject_requests_manage ON data_subject_requests FOR UPDATE
USING (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND (
      (NOT psique_rbac_v2_active(organization_id)
        AND froid_has_role(ARRAY['owner','administrator']::text[]))
      OR (psique_rbac_v2_active(organization_id)
        AND psique_v2_role_check(ARRAY['ORG_ADMIN']))
    )
)
WITH CHECK (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
);

DROP POLICY IF EXISTS data_subject_request_events_read ON data_subject_request_events;
CREATE POLICY data_subject_request_events_read ON data_subject_request_events FOR SELECT USING (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND (
      (NOT psique_rbac_v2_active(organization_id)
        AND froid_has_role(ARRAY['owner','administrator','supervisor','auditor']::text[]))
      OR (psique_rbac_v2_active(organization_id)
        AND psique_v2_role_check(ARRAY['ORG_ADMIN','AUDITOR_COMPLIANCE']))
    )
);

DROP POLICY IF EXISTS data_subject_request_events_insert ON data_subject_request_events;
CREATE POLICY data_subject_request_events_insert ON data_subject_request_events FOR INSERT WITH CHECK (
    organization_id=froid_current_organization_id()
    AND froid_membership_is_active()
    AND (
      (NOT psique_rbac_v2_active(organization_id)
        AND froid_has_role(ARRAY['owner','administrator']::text[]))
      OR (psique_rbac_v2_active(organization_id)
        AND psique_v2_role_check(ARRAY['ORG_ADMIN']))
    )
);

INSERT INTO schema_migrations(version) VALUES('043_psique_rbac_v2_complement');
COMMIT;
