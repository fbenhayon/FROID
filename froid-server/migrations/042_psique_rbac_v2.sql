BEGIN;

-- Phase 3: RBAC V2 for Psique organizations, opt-in per organization.
-- V1 and NR-1 keep their exact policies: every V2 branch below is guarded by
-- psique_rbac_v2_active(), and the V1 branch is guarded by its negation, so
-- the permissive-OR of policies cannot let a V1 role bypass V2 (the audited
-- incident class this migration exists to prevent).
-- SUPERADMIN is a platform exception, never an organization-grantable role:
-- it is deliberately absent from the role domain.

CREATE TABLE psique_organization_settings (
    organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE RESTRICT,
    rbac_version smallint NOT NULL DEFAULT 1 CHECK (rbac_version IN (1,2)),
    enabled_at timestamptz,
    enabled_by uuid,
    CHECK (rbac_version=1 OR (enabled_at IS NOT NULL AND enabled_by IS NOT NULL))
);

CREATE FUNCTION psique_rbac_settings_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
DECLARE org_type text;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'PSIQUE_RBAC_SETTINGS_IMMUTABLE'; END IF;
    IF TG_OP='UPDATE' AND OLD.rbac_version=2 AND NEW.rbac_version<>2 THEN
        -- Rolling RBAC back would silently widen clinical access.
        RAISE EXCEPTION 'PSIQUE_RBAC_DOWNGRADE_FORBIDDEN';
    END IF;
    SELECT organization_type INTO org_type FROM organizations WHERE id=NEW.organization_id;
    IF org_type IS NULL OR org_type NOT IN ('solo','clinic') THEN
        -- NR-1 organizations never enter the Psique RBAC branch.
        RAISE EXCEPTION 'PSIQUE_RBAC_ORGANIZATION_NOT_SUPPORTED';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER psique_rbac_settings_guard BEFORE INSERT OR UPDATE OR DELETE
    ON psique_organization_settings FOR EACH ROW EXECUTE FUNCTION psique_rbac_settings_guard();

CREATE FUNCTION psique_rbac_v2_active(org uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
    SELECT EXISTS (SELECT 1 FROM psique_organization_settings s
        WHERE s.organization_id=org AND s.rbac_version=2);
$$;

CREATE TABLE psique_membership_role_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    membership_id uuid NOT NULL,
    v2_role text NOT NULL CHECK (v2_role IN
        ('CLINICIAN','SECRETARY','FINANCE','ORG_ADMIN','CLINICAL_SUPERVISOR','AUDITOR_COMPLIANCE')),
    granted_by uuid NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_by uuid,
    revoked_at timestamptz,
    CHECK ((revoked_at IS NULL AND revoked_by IS NULL) OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL)),
    FOREIGN KEY (organization_id,membership_id)
        REFERENCES organization_memberships(organization_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX psique_one_active_role_grant
    ON psique_membership_role_grants(membership_id,v2_role) WHERE revoked_at IS NULL;
CREATE INDEX psique_role_grants_by_org
    ON psique_membership_role_grants(organization_id) WHERE revoked_at IS NULL;

CREATE TABLE psique_supervision_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    supervisor_membership_id uuid NOT NULL,
    supervised_membership_id uuid NOT NULL,
    granted_by uuid NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_by uuid,
    revoked_at timestamptz,
    CHECK (supervisor_membership_id<>supervised_membership_id),
    CHECK ((revoked_at IS NULL AND revoked_by IS NULL) OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL)),
    FOREIGN KEY (organization_id,supervisor_membership_id)
        REFERENCES organization_memberships(organization_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id,supervised_membership_id)
        REFERENCES organization_memberships(organization_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX psique_one_active_supervision
    ON psique_supervision_assignments(supervisor_membership_id,supervised_membership_id)
    WHERE revoked_at IS NULL;
CREATE INDEX psique_supervision_by_supervisor
    ON psique_supervision_assignments(supervisor_membership_id) WHERE revoked_at IS NULL;

CREATE FUNCTION psique_rbac_history_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'PSIQUE_RBAC_HISTORY_IMMUTABLE'; END IF;
    IF OLD.revoked_at IS NOT NULL THEN RAISE EXCEPTION 'PSIQUE_RBAC_GRANT_ALREADY_REVOKED'; END IF;
    IF NEW.revoked_at IS NULL OR (to_jsonb(NEW) - ARRAY['revoked_at','revoked_by'])
        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['revoked_at','revoked_by']) THEN
        RAISE EXCEPTION 'PSIQUE_RBAC_GRANT_IMMUTABLE';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER psique_role_grant_history BEFORE UPDATE OR DELETE
    ON psique_membership_role_grants FOR EACH ROW EXECUTE FUNCTION psique_rbac_history_guard();
CREATE TRIGGER psique_supervision_history BEFORE UPDATE OR DELETE
    ON psique_supervision_assignments FOR EACH ROW EXECUTE FUNCTION psique_rbac_history_guard();

ALTER TABLE psique_organization_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_membership_role_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_supervision_assignments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON psique_organization_settings,psique_membership_role_grants,
    psique_supervision_assignments FROM PUBLIC;

-- Cumulative V2 roles of the CURRENT membership (GUC context), like
-- froid_has_role, but over the V2 grants.
CREATE FUNCTION psique_v2_role_check(required text[]) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM psique_membership_role_grants g
        JOIN organization_memberships m ON m.id=g.membership_id
        WHERE g.membership_id=froid_current_membership_id()
          AND g.organization_id=froid_current_organization_id()
          AND g.revoked_at IS NULL AND m.status='active'
          AND g.v2_role = ANY(required)
    );
$$;

CREATE FUNCTION psique_v2_supervises(target uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM psique_supervision_assignments s
        WHERE s.supervisor_membership_id=froid_current_membership_id()
          AND s.organization_id=froid_current_organization_id()
          AND s.supervised_membership_id=target AND s.revoked_at IS NULL
    );
$$;

-- ---------------------------------------------------------------------------
-- Row level security: V1 branch preserved verbatim behind NOT active(); V2
-- branch is restrictive by role. Administrators/secretaries/finance/auditors
-- of a V2 organization have NO clinical row access here.
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS session_reports_read ON session_reports;
CREATE POLICY session_reports_read ON session_reports FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id) AND (
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
    ))
    OR (psique_rbac_v2_active(organization_id) AND (
      (psique_v2_role_check(ARRAY['CLINICIAN']) AND (
        professional_membership_id=froid_current_membership_id()
        OR EXISTS (
          SELECT 1 FROM patient_assignments assignment
          WHERE assignment.organization_id=session_reports.organization_id
            AND assignment.patient_id=session_reports.patient_id
            AND assignment.membership_id=froid_current_membership_id()
            AND assignment.status='active'
        )
      ))
      OR (psique_v2_role_check(ARRAY['CLINICAL_SUPERVISOR'])
          AND psique_v2_supervises(session_reports.professional_membership_id))
    ))
  )
);

DROP POLICY IF EXISTS session_reports_insert ON session_reports;
CREATE POLICY session_reports_insert ON session_reports FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND professional_membership_id=froid_current_membership_id()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
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
      ))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['CLINICIAN'])
      AND (
        patient_id IS NULL
        OR EXISTS (
          SELECT 1 FROM patient_assignments assignment
          WHERE assignment.organization_id=session_reports.organization_id
            AND assignment.patient_id=session_reports.patient_id
            AND assignment.membership_id=froid_current_membership_id()
            AND assignment.status='active'
        )
      ))
  )
);

DROP POLICY IF EXISTS session_reports_update ON session_reports;
CREATE POLICY session_reports_update ON session_reports FOR UPDATE
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id) AND (
      froid_has_role(ARRAY['owner','administrator']::text[])
      OR (
        professional_membership_id=froid_current_membership_id()
        AND froid_has_role(ARRAY['professional']::text[])
      )
    ))
    OR (psique_rbac_v2_active(organization_id)
      AND professional_membership_id=froid_current_membership_id()
      AND psique_v2_role_check(ARRAY['CLINICIAN']))
  )
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id) AND (
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
    ))
    OR (psique_rbac_v2_active(organization_id)
      AND professional_membership_id=froid_current_membership_id()
      AND psique_v2_role_check(ARRAY['CLINICIAN'])
      AND (
        patient_id IS NULL
        OR EXISTS (
          SELECT 1 FROM patient_assignments assignment
          WHERE assignment.organization_id=session_reports.organization_id
            AND assignment.patient_id=session_reports.patient_id
            AND assignment.membership_id=froid_current_membership_id()
            AND assignment.status='active'
        )
      ))
  )
);

DROP POLICY IF EXISTS session_reports_delete ON session_reports;
CREATE POLICY session_reports_delete ON session_reports FOR DELETE USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  -- V2 organizations: clinical history is never deleted through RLS; a
  -- future explicit retention procedure owns that decision.
  AND NOT psique_rbac_v2_active(organization_id)
  AND froid_has_role(ARRAY['owner','administrator']::text[])
);

DROP POLICY IF EXISTS patients_read ON patients;
CREATE POLICY patients_read ON patients FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id) AND (
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
    ))
    OR (psique_rbac_v2_active(organization_id) AND (
      (psique_v2_role_check(ARRAY['CLINICIAN'])
        AND EXISTS (
          SELECT 1 FROM patient_assignments assignment
          WHERE assignment.organization_id=patients.organization_id
            AND assignment.patient_id=patients.id
            AND assignment.membership_id=froid_current_membership_id()
            AND assignment.status='active'
        ))
      OR (psique_v2_role_check(ARRAY['CLINICAL_SUPERVISOR'])
        AND EXISTS (
          SELECT 1 FROM patient_assignments assignment
          WHERE assignment.organization_id=patients.organization_id
            AND assignment.patient_id=patients.id
            AND assignment.status='active'
            AND psique_v2_supervises(assignment.membership_id)
        ))
    ))
  )
);

DROP POLICY IF EXISTS patients_insert ON patients;
CREATE POLICY patients_insert ON patients FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','professional']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['CLINICIAN']))
  )
);

DROP POLICY IF EXISTS patients_update ON patients;
CREATE POLICY patients_update ON patients FOR UPDATE
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id) AND (
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
    ))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['CLINICIAN'])
      AND EXISTS (
        SELECT 1 FROM patient_assignments assignment
        WHERE assignment.organization_id=patients.organization_id
          AND assignment.patient_id=patients.id
          AND assignment.membership_id=froid_current_membership_id()
          AND assignment.status='active'
      ))
  )
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','professional']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['CLINICIAN']))
  )
);

DROP POLICY IF EXISTS patients_delete ON patients;
CREATE POLICY patients_delete ON patients FOR DELETE USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND NOT psique_rbac_v2_active(organization_id)
  AND froid_has_role(ARRAY['owner','administrator']::text[])
);

DROP POLICY IF EXISTS patient_assignments_read ON patient_assignments;
CREATE POLICY patient_assignments_read ON patient_assignments FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id) AND (
      froid_has_role(ARRAY['owner','administrator','supervisor']::text[])
      OR (
        membership_id=froid_current_membership_id()
        AND froid_has_role(ARRAY['professional']::text[])
      )
    ))
    OR (psique_rbac_v2_active(organization_id) AND (
      psique_v2_role_check(ARRAY['ORG_ADMIN'])
      OR (membership_id=froid_current_membership_id()
          AND psique_v2_role_check(ARRAY['CLINICIAN']))
      OR (psique_v2_role_check(ARRAY['CLINICAL_SUPERVISOR'])
          AND psique_v2_supervises(membership_id))
    ))
  )
);

DROP POLICY IF EXISTS patient_assignments_manage ON patient_assignments;
CREATE POLICY patient_assignments_manage ON patient_assignments FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','supervisor']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['ORG_ADMIN']))
  )
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','supervisor']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['ORG_ADMIN']))
  )
);

DROP POLICY IF EXISTS consents_read ON consents;
CREATE POLICY consents_read ON consents FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id) AND (
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
    ))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['CLINICIAN'])
      AND EXISTS (
        SELECT 1 FROM patient_assignments assignment
        WHERE assignment.organization_id=consents.organization_id
          AND assignment.patient_id=consents.patient_id
          AND assignment.membership_id=froid_current_membership_id()
          AND assignment.status='active'
      ))
  )
);

DROP POLICY IF EXISTS consents_insert ON consents;
CREATE POLICY consents_insert ON consents FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','professional']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['CLINICIAN']))
  )
);

DROP POLICY IF EXISTS consents_update ON consents;
CREATE POLICY consents_update ON consents FOR UPDATE
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['CLINICIAN']))
  )
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);

DROP POLICY IF EXISTS organization_wallets_read ON organization_wallets;
CREATE POLICY organization_wallets_read ON organization_wallets FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','professional']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['ORG_ADMIN','FINANCE','CLINICIAN']))
  )
);

DROP POLICY IF EXISTS credit_ledger_read ON credit_ledger;
CREATE POLICY credit_ledger_read ON credit_ledger FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','professional']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['ORG_ADMIN','FINANCE']))
  )
);

DROP POLICY IF EXISTS audit_events_read ON audit_events;
CREATE POLICY audit_events_read ON audit_events FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND (
    (NOT psique_rbac_v2_active(organization_id)
      AND froid_has_role(ARRAY['owner','administrator','auditor']::text[]))
    OR (psique_rbac_v2_active(organization_id)
      AND psique_v2_role_check(ARRAY['ORG_ADMIN','AUDITOR_COMPLIANCE']))
  )
);

-- ---------------------------------------------------------------------------
-- Command boundary
-- ---------------------------------------------------------------------------

CREATE FUNCTION psique_v2_rbac_require_member(org uuid, member uuid, actor uuid)
RETURNS void LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    IF froid_current_organization_id() IS DISTINCT FROM org OR
        froid_current_membership_id() IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'PSIQUE_CONTEXT_MISMATCH' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM organization_memberships m JOIN organizations o ON o.id=m.organization_id
        JOIN users u ON u.id=m.user_id WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
        AND m.status='active' AND u.status='active' AND o.status='active'
        AND o.organization_type IN ('solo','clinic')) THEN
        RAISE EXCEPTION 'PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED' USING ERRCODE='42501';
    END IF;
END $$;

CREATE FUNCTION psique_v2_rbac_enable(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE clinicians integer:=0; admins integer:=0;
BEGIN
    PERFORM psique_v2_rbac_require_member(org,member,actor);
    -- The V1 owner authorizes the migration of their own organization.
    IF NOT froid_has_role(ARRAY['owner']) THEN
        RAISE EXCEPTION 'RBAC_ENABLE_OWNER_REQUIRED' USING ERRCODE='42501';
    END IF;
    -- Serializa ativacoes concorrentes da mesma organizacao.
    PERFORM 1 FROM organizations WHERE id=org FOR UPDATE;
    IF psique_rbac_v2_active(org) THEN RETURN jsonb_build_object('enabled',false); END IF;
    INSERT INTO psique_organization_settings(organization_id,rbac_version,enabled_at,enabled_by)
        VALUES(org,2,clock_timestamp(),actor)
        ON CONFLICT (organization_id) DO UPDATE
            SET rbac_version=2,enabled_at=clock_timestamp(),enabled_by=actor
            WHERE psique_organization_settings.rbac_version=1;
    -- Explicit snapshot: whoever practiced keeps practicing, whoever managed
    -- keeps managing. Nothing else is inferred; no one gains clinical access.
    WITH members AS (
        SELECT m.id, r.role FROM organization_memberships m
        JOIN membership_roles r ON r.membership_id=m.id
        WHERE m.organization_id=org AND m.status='active'
    ), grants AS (
        INSERT INTO psique_membership_role_grants(organization_id,membership_id,v2_role,granted_by)
        SELECT DISTINCT org, id,
            CASE WHEN role='professional' THEN 'CLINICIAN' ELSE 'ORG_ADMIN' END, actor
        FROM members WHERE role IN ('professional','owner','administrator')
        ON CONFLICT DO NOTHING
        RETURNING v2_role
    )
    SELECT count(*) FILTER (WHERE v2_role='CLINICIAN'),
           count(*) FILTER (WHERE v2_role='ORG_ADMIN')
        INTO clinicians, admins FROM grants;
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.rbac.enable','psique_organization_settings',org::text,
        jsonb_build_object('clinician_grants',clinicians,'org_admin_grants',admins));
    RETURN jsonb_build_object('enabled',true,'clinician_grants',clinicians,'org_admin_grants',admins);
END $$;

CREATE FUNCTION psique_v2_role_grant(org uuid, member uuid, actor uuid, target uuid, new_role text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE grant_row psique_membership_role_grants%ROWTYPE;
BEGIN
    PERFORM psique_v2_rbac_require_member(org,member,actor);
    IF NOT psique_rbac_v2_active(org) THEN RAISE EXCEPTION 'RBAC_V2_NOT_ENABLED'; END IF;
    IF NOT psique_v2_role_check(ARRAY['ORG_ADMIN']) THEN
        RAISE EXCEPTION 'PSIQUE_ORG_ADMIN_REQUIRED' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM organization_memberships m
        WHERE m.id=target AND m.organization_id=org AND m.status='active') THEN
        RAISE EXCEPTION 'RBAC_TARGET_MEMBERSHIP_REQUIRED' USING ERRCODE='42501';
    END IF;
    SELECT * INTO grant_row FROM psique_membership_role_grants
        WHERE membership_id=target AND v2_role=new_role AND revoked_at IS NULL;
    IF FOUND THEN RETURN jsonb_build_object('granted',false,'grant_id',grant_row.id); END IF;
    INSERT INTO psique_membership_role_grants(organization_id,membership_id,v2_role,granted_by)
        VALUES(org,target,new_role,actor) RETURNING * INTO grant_row;
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.rbac.grant','psique_membership_role_grant',
        grant_row.id::text,jsonb_build_object('membership_id',target,'v2_role',new_role));
    RETURN jsonb_build_object('granted',true,'grant_id',grant_row.id);
END $$;

CREATE FUNCTION psique_v2_role_revoke(org uuid, member uuid, actor uuid, target uuid, old_role text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE grant_row psique_membership_role_grants%ROWTYPE;
BEGIN
    PERFORM psique_v2_rbac_require_member(org,member,actor);
    IF NOT psique_v2_role_check(ARRAY['ORG_ADMIN']) THEN
        RAISE EXCEPTION 'PSIQUE_ORG_ADMIN_REQUIRED' USING ERRCODE='42501';
    END IF;
    SELECT * INTO grant_row FROM psique_membership_role_grants
        WHERE membership_id=target AND organization_id=org AND v2_role=old_role
        AND revoked_at IS NULL FOR UPDATE;
    IF NOT FOUND THEN RETURN jsonb_build_object('revoked',false); END IF;
    IF old_role='ORG_ADMIN' AND NOT EXISTS (
        SELECT 1 FROM psique_membership_role_grants g
        JOIN organization_memberships m ON m.id=g.membership_id AND m.status='active'
        WHERE g.organization_id=org AND g.v2_role='ORG_ADMIN'
          AND g.revoked_at IS NULL AND g.membership_id<>target) THEN
        -- The strictest rule would lock the organization out of itself.
        RAISE EXCEPTION 'LAST_ORG_ADMIN_PROTECTED';
    END IF;
    UPDATE psique_membership_role_grants SET revoked_at=clock_timestamp(),revoked_by=actor
        WHERE id=grant_row.id;
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.rbac.revoke','psique_membership_role_grant',
        grant_row.id::text,jsonb_build_object('membership_id',target,'v2_role',old_role));
    RETURN jsonb_build_object('revoked',true,'grant_id',grant_row.id);
END $$;

CREATE FUNCTION psique_v2_supervision_set(org uuid, member uuid, actor uuid,
    supervisor uuid, supervised uuid, make_active boolean)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE assignment psique_supervision_assignments%ROWTYPE;
BEGIN
    PERFORM psique_v2_rbac_require_member(org,member,actor);
    IF NOT psique_rbac_v2_active(org) THEN RAISE EXCEPTION 'RBAC_V2_NOT_ENABLED'; END IF;
    IF NOT psique_v2_role_check(ARRAY['ORG_ADMIN']) THEN
        RAISE EXCEPTION 'PSIQUE_ORG_ADMIN_REQUIRED' USING ERRCODE='42501';
    END IF;
    SELECT * INTO assignment FROM psique_supervision_assignments
        WHERE organization_id=org AND supervisor_membership_id=supervisor
        AND supervised_membership_id=supervised AND revoked_at IS NULL FOR UPDATE;
    IF NOT make_active THEN
        IF NOT FOUND THEN RETURN jsonb_build_object('changed',false); END IF;
        UPDATE psique_supervision_assignments SET revoked_at=clock_timestamp(),revoked_by=actor
            WHERE id=assignment.id;
        INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id)
        VALUES(gen_random_uuid(),org,actor,'psique.rbac.supervision.revoke',
            'psique_supervision_assignment',assignment.id::text);
        RETURN jsonb_build_object('changed',true);
    END IF;
    IF FOUND THEN RETURN jsonb_build_object('changed',false,'assignment_id',assignment.id); END IF;
    IF NOT EXISTS (SELECT 1 FROM psique_membership_role_grants
        WHERE membership_id=supervisor AND organization_id=org
        AND v2_role='CLINICAL_SUPERVISOR' AND revoked_at IS NULL) THEN
        RAISE EXCEPTION 'SUPERVISOR_ROLE_REQUIRED';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM psique_membership_role_grants
        WHERE membership_id=supervised AND organization_id=org
        AND v2_role='CLINICIAN' AND revoked_at IS NULL) THEN
        RAISE EXCEPTION 'SUPERVISED_CLINICIAN_REQUIRED';
    END IF;
    INSERT INTO psique_supervision_assignments(organization_id,supervisor_membership_id,
        supervised_membership_id,granted_by)
        VALUES(org,supervisor,supervised,actor) RETURNING * INTO assignment;
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.rbac.supervision.grant',
        'psique_supervision_assignment',assignment.id::text,
        jsonb_build_object('supervisor',supervisor,'supervised',supervised));
    RETURN jsonb_build_object('changed',true,'assignment_id',assignment.id);
END $$;

CREATE FUNCTION psique_v2_capabilities(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE v2 boolean; v2_roles jsonb; v1_roles jsonb; supervised jsonb;
BEGIN
    PERFORM psique_v2_rbac_require_member(org,member,actor);
    v2:=psique_rbac_v2_active(org);
    SELECT coalesce(jsonb_agg(DISTINCT role),'[]'::jsonb) INTO v1_roles
        FROM membership_roles WHERE membership_id=member;
    SELECT coalesce(jsonb_agg(DISTINCT v2_role),'[]'::jsonb) INTO v2_roles
        FROM psique_membership_role_grants
        WHERE membership_id=member AND revoked_at IS NULL;
    SELECT coalesce(jsonb_agg(supervised_membership_id),'[]'::jsonb) INTO supervised
        FROM psique_supervision_assignments
        WHERE supervisor_membership_id=member AND organization_id=org AND revoked_at IS NULL;
    RETURN jsonb_build_object(
        'rbac_version',CASE WHEN v2 THEN 2 ELSE 1 END,
        'v1_roles',v1_roles,'v2_roles',v2_roles,'supervised_membership_ids',supervised,
        'capabilities',jsonb_build_object(
            'clinical_analysis', CASE WHEN v2 THEN v2_roles ? 'CLINICIAN'
                ELSE froid_has_role(ARRAY['owner','administrator','professional']) END,
            'purchase_credits', CASE WHEN v2 THEN (v2_roles ? 'ORG_ADMIN' OR v2_roles ? 'FINANCE')
                ELSE froid_has_role(ARRAY['owner','administrator']) END,
            'manage_roles', CASE WHEN v2 THEN v2_roles ? 'ORG_ADMIN'
                ELSE froid_has_role(ARRAY['owner']) END,
            'read_audit', CASE WHEN v2 THEN (v2_roles ? 'ORG_ADMIN' OR v2_roles ? 'AUDITOR_COMPLIANCE')
                ELSE froid_has_role(ARRAY['owner','administrator','auditor']) END,
            'supervise', v2 AND v2_roles ? 'CLINICAL_SUPERVISOR'));
END $$;

-- Billing gate: in a V2 organization the V1 breadth stops counting.
CREATE OR REPLACE FUNCTION psique_v2_require_billing_member(org uuid, member uuid, actor uuid)
RETURNS void LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    PERFORM psique_v2_rbac_require_member(org,member,actor);
    IF psique_rbac_v2_active(org) THEN
        IF NOT psique_v2_role_check(ARRAY['ORG_ADMIN','FINANCE']) THEN
            RAISE EXCEPTION 'PSIQUE_BILLING_ADMIN_REQUIRED' USING ERRCODE='42501';
        END IF;
    ELSIF NOT froid_has_role(ARRAY['owner','administrator']) THEN
        RAISE EXCEPTION 'PSIQUE_BILLING_ADMIN_REQUIRED' USING ERRCODE='42501';
    END IF;
END $$;

-- Credit command role gates, per command group. Content commands require the
-- CLINICIAN grant in V2 organizations; FINANCE never reaches READ_DELIVERY.
CREATE FUNCTION psique_v2_credit_command_roles(org uuid, command text)
RETURNS void LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    IF psique_rbac_v2_active(org) THEN
        IF command IN ('ENROLL','GRANT_TRIAL','RESTORE','ADJUST') THEN
            IF NOT psique_v2_role_check(ARRAY['ORG_ADMIN']) THEN
                RAISE EXCEPTION 'PSIQUE_ORG_ADMIN_REQUIRED' USING ERRCODE='42501';
            END IF;
        ELSIF command IN ('BALANCE','EXPIRE','IDENTITY','KEY_VERSIONS') THEN
            IF NOT psique_v2_role_check(ARRAY['CLINICIAN','ORG_ADMIN','FINANCE']) THEN
                RAISE EXCEPTION 'PSIQUE_ROLE_DENIED' USING ERRCODE='42501';
            END IF;
        ELSIF NOT psique_v2_role_check(ARRAY['CLINICIAN']) THEN
            RAISE EXCEPTION 'PSIQUE_CLINICIAN_REQUIRED' USING ERRCODE='42501';
        END IF;
    ELSE
        IF NOT froid_has_role(ARRAY['owner','administrator','professional']) THEN
            RAISE EXCEPTION 'PSIQUE_ROLE_DENIED' USING ERRCODE='42501';
        END IF;
        IF command IN ('ENROLL','GRANT_TRIAL') AND NOT froid_has_role(ARRAY['owner']) THEN
            RAISE EXCEPTION 'TRIAL_OWNER_REQUIRED' USING ERRCODE='42501';
        END IF;
        IF command IN ('RESTORE','ADJUST') AND NOT froid_has_role(ARRAY['owner','administrator']) THEN
            RAISE EXCEPTION 'PSIQUE_CREDIT_ADMIN_REQUIRED' USING ERRCODE='42501';
        END IF;
    END IF;
END $$;

REVOKE ALL ON FUNCTION psique_rbac_settings_guard(),psique_rbac_history_guard(),
    psique_rbac_v2_active(uuid),psique_v2_role_check(text[]),psique_v2_supervises(uuid),
    psique_v2_rbac_require_member(uuid,uuid,uuid),
    psique_v2_rbac_enable(uuid,uuid,uuid),
    psique_v2_role_grant(uuid,uuid,uuid,uuid,text),
    psique_v2_role_revoke(uuid,uuid,uuid,uuid,text),
    psique_v2_supervision_set(uuid,uuid,uuid,uuid,uuid,boolean),
    psique_v2_capabilities(uuid,uuid,uuid),
    psique_v2_require_billing_member(uuid,uuid,uuid),
    psique_v2_credit_command_roles(uuid,text)
    FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION
        psique_rbac_v2_active(uuid),psique_v2_role_check(text[]),psique_v2_supervises(uuid),
        psique_v2_rbac_enable(uuid,uuid,uuid),
        psique_v2_role_grant(uuid,uuid,uuid,uuid,text),
        psique_v2_role_revoke(uuid,uuid,uuid,uuid,text),
        psique_v2_supervision_set(uuid,uuid,uuid,uuid,uuid,boolean),
        psique_v2_capabilities(uuid,uuid,uuid)
    TO froid_runtime;
END IF; END $$;

-- The credit command of migration 038, verbatim except for the role gate,
-- which now branches per RBAC version through the function above.
CREATE OR REPLACE FUNCTION psique_v2_credit_command(org uuid, member uuid, actor uuid, command text, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE
    wallet organization_wallets%ROWTYPE; trial psique_trials%ROWTYPE;
    source psique_analysis_sources%ROWTYPE; attempt psique_analysis_attempts%ROWTYPE;
    reservation psique_credit_reservations%ROWTYPE; entry credit_ledger%ROWTYPE;
    previous credit_ledger%ROWTYPE; saved_report session_reports%ROWTYPE;
    instant timestamptz; free integer; paid_free integer; amount integer;
    event_id uuid; source_id uuid; attempt_id uuid; beneficiary uuid; report_key text;
    explanation text; idem text; funding_source text; token jsonb; evidence text;
    verified timestamptz; origin text; payload jsonb; digest_value text; actor_email text;
BEGIN
    IF froid_current_organization_id() IS DISTINCT FROM org OR
        froid_current_membership_id() IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'PSIQUE_CONTEXT_MISMATCH' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM organization_memberships m JOIN organizations o ON o.id=m.organization_id
        JOIN users u ON u.id=m.user_id WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
        AND m.status='active' AND u.status='active' AND o.status='active'
        AND o.organization_type IN ('solo','clinic')) THEN
        RAISE EXCEPTION 'PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED' USING ERRCODE='42501';
    END IF;
    PERFORM psique_v2_credit_command_roles(org, command);
    IF command='ENROLL' THEN
        INSERT INTO organization_wallets(organization_id,balance) VALUES(org,0)
            ON CONFLICT(organization_id) DO NOTHING;
    END IF;
    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;
    instant:=clock_timestamp(); -- after the lock, so wait time never extends Trial eligibility
    IF command='ENROLL' THEN
        IF wallet.credit_model='psique_v2' THEN RETURN jsonb_build_object('enrolled',false); END IF;
        IF wallet.balance<>0 OR EXISTS(SELECT 1 FROM credit_ledger WHERE organization_id=org) THEN
            RAISE EXCEPTION 'V1_WALLET_CONVERSION_NOT_AUTHORIZED';
        END IF;
        UPDATE organization_wallets SET credit_model='psique_v2',authority='shared',version=version+1
            WHERE organization_id=org;
        INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id)
            VALUES(gen_random_uuid(),org,actor,'psique.wallet.enroll','organization_wallet',org::text);
        RETURN jsonb_build_object('enrolled',true);
    END IF;
    IF wallet.credit_model<>'psique_v2' THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;

    IF command='KEY_VERSIONS' THEN
        RETURN jsonb_build_object('versions',coalesce((SELECT jsonb_agg(key_version) FROM
            (SELECT DISTINCT key_version FROM psique_trial_eligibility) keys),'[]'::jsonb));
    END IF;
    IF command='PENDING_ATTEMPTS' THEN
        RETURN jsonb_build_object('attempt_ids',coalesce((SELECT jsonb_agg(a.id)
            FROM psique_analysis_attempts a JOIN psique_analysis_sources s ON s.id=a.analysis_source_id
            WHERE a.organization_id=org AND s.owner_membership_id=member AND
                ((a.status='PROCESSING' AND a.lease_until<=instant) OR
                 (a.status='DELIVERED' AND EXISTS(SELECT 1 FROM psique_credit_reservations r
                    WHERE r.analysis_attempt_id=a.id AND r.status='RESERVED')))), '[]'::jsonb));
    END IF;
    IF command='GRANT_TRIAL' THEN
        verified:=(args->>'verified_at')::timestamptz;
        evidence:=trim(args->>'evidence_ref');
        IF verified IS NULL OR verified>instant OR coalesce(evidence,'')='' OR
            jsonb_typeof(args->'tokens') IS DISTINCT FROM 'array' OR jsonb_array_length(args->'tokens')=0 THEN
            RAISE EXCEPTION 'VERIFIED_IDENTITY_REQUIRED';
        END IF;
        IF EXISTS(SELECT key_version FROM psique_trial_eligibility
            EXCEPT SELECT item->>'version' FROM jsonb_array_elements(args->'tokens') item) THEN
            RAISE EXCEPTION 'TRIAL_HISTORICAL_KEY_REQUIRED';
        END IF;
        SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
        IF FOUND THEN RETURN jsonb_build_object('granted',false,'status',trial.status); END IF;
        FOR token IN SELECT value FROM jsonb_array_elements(args->'tokens') ORDER BY value->>'version' LOOP
            IF coalesce(token->>'version','')='' OR coalesce(token->>'hmac','') !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'INVALID_ELIGIBILITY_TOKEN';
            END IF;
            PERFORM pg_advisory_xact_lock(hashtextextended((token->>'version')||':'||(token->>'hmac'),0));
        END LOOP;
        SELECT e.beneficiary_id INTO beneficiary FROM psique_trial_eligibility e
            JOIN jsonb_array_elements(args->'tokens') item
            ON e.key_version=item->>'version' AND e.email_hmac=item->>'hmac' LIMIT 1;
        origin:=CASE WHEN beneficiary IS NOT NULL OR args->>'legacy_benefit'='true' THEN 'V1' ELSE 'V2' END;
        -- Prior V2 eligibility also blocks a new benefit; preserve its original provenance.
        IF beneficiary IS NOT NULL THEN
            SELECT eligibility_origin INTO origin FROM psique_trial_eligibility
                WHERE beneficiary_id=beneficiary LIMIT 1;
            INSERT INTO psique_trials(organization_id,beneficiary_id,status,credits_granted)
                VALUES(org,beneficiary,'INELIGIBLE',0);
        ELSE
            beneficiary:=gen_random_uuid();
            IF origin='V1' THEN
                INSERT INTO psique_trials(organization_id,beneficiary_id,status,credits_granted)
                    VALUES(org,beneficiary,'INELIGIBLE',0);
            ELSE
                INSERT INTO psique_trials(organization_id,beneficiary_id,status,started_at,expires_at,credits_granted)
                    VALUES(org,beneficiary,'ACTIVE',instant,instant+interval '336 hours',10);
                PERFORM psique_v2_append(org,actor,'TRIAL_GRANT',10,0,'trial-grant:'||beneficiary,fund=>'TRIAL');
            END IF;
        END IF;
        FOR token IN SELECT value FROM jsonb_array_elements(args->'tokens') LOOP
            INSERT INTO psique_trial_eligibility(key_version,email_hmac,beneficiary_id,organization_id,
                eligibility_origin,evidence_ref,verified_at)
                VALUES(token->>'version',token->>'hmac',beneficiary,org,origin,evidence,verified)
                ON CONFLICT(key_version,email_hmac) DO NOTHING;
        END LOOP;
        SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
        INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
            VALUES(gen_random_uuid(),org,actor,'psique.trial.eligibility','psique_trial',beneficiary::text,
                jsonb_build_object('status',trial.status,'evidence_ref',evidence));
        RETURN jsonb_build_object('granted',trial.credits_granted=10,'status',trial.status);
    END IF;

    PERFORM psique_v2_expire(org,actor,instant);
    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org;
    SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
    free:=CASE WHEN trial.status IN ('ACTIVE','EXHAUSTED') THEN
        trial.credits_granted-trial.credits_used-trial.credits_reserved-trial.credits_expired ELSE 0 END;

    IF command IN ('BALANCE','EXPIRE') THEN
        RETURN jsonb_build_object('balance',wallet.balance,'reserved_balance',wallet.reserved_balance,
            'available_balance',wallet.balance-wallet.reserved_balance,'trial_status',trial.status,
            'trial_free_remaining',free,'trial_expires_at',trial.expires_at);
    ELSIF command='IDENTITY' THEN
        SELECT email INTO actor_email FROM users WHERE id=actor;
        RETURN jsonb_build_object('email',actor_email);
    ELSIF command='REGISTER_SOURCE' THEN
        INSERT INTO psique_analysis_sources(organization_id,owner_membership_id,material_key,
            legacy_session_id,source_kind,source_sha256)
        VALUES(org,member,(args->>'material_key')::uuid,args->>'session_id',args->>'source_kind',args->>'source_sha256')
        ON CONFLICT(organization_id,material_key) DO NOTHING;
        SELECT * INTO source FROM psique_analysis_sources
            WHERE organization_id=org AND material_key=(args->>'material_key')::uuid;
        IF source.owner_membership_id<>member OR source.legacy_session_id IS DISTINCT FROM args->>'session_id'
            OR source.source_kind IS DISTINCT FROM args->>'source_kind'
            OR source.source_sha256 IS DISTINCT FROM args->>'source_sha256' THEN
            RAISE EXCEPTION 'SOURCE_IDENTITY_MISMATCH' USING ERRCODE='42501';
        END IF;
        RETURN jsonb_build_object('analysis_source_id',source.id,'source_sha256',source.source_sha256);
    ELSIF command='ADJUST' THEN
        amount:=(args->>'delta')::integer; explanation:=trim(args->>'reason'); idem:=trim(args->>'idempotency_key');
        IF amount IS NULL OR amount=0 OR coalesce(explanation,'')='' OR coalesce(idem,'')='' THEN
            RAISE EXCEPTION 'ADJUSTMENT_REASON_AND_AMOUNT_REQUIRED';
        END IF;
        SELECT * INTO previous FROM credit_ledger WHERE organization_id=org AND idempotency_key='adjust:'||idem;
        IF FOUND THEN
            IF previous.delta<>amount OR previous.reason<>explanation THEN RAISE EXCEPTION 'IDEMPOTENCY_MISMATCH'; END IF;
            RETURN jsonb_build_object('ledger_id',previous.id,'applied',false);
        END IF;
        paid_free:=wallet.balance-wallet.reserved_balance-free;
        IF amount<0 AND paid_free+amount<0 THEN RAISE EXCEPTION 'INSUFFICIENT_PAID_CREDITS'; END IF;
        event_id:=psique_v2_append(org,actor,'MANUAL_ADJUSTMENT',amount,0,'adjust:'||idem,
            fund=>'PAID',explanation=>explanation);
        RETURN jsonb_build_object('ledger_id',event_id,'applied',true);
    ELSIF command='RESTORE' THEN
        explanation:=trim(args->>'reason'); evidence:=trim(args->>'evidence_ref');
        IF coalesce(explanation,'')='' OR coalesce(evidence,'')='' THEN RAISE EXCEPTION 'RESTORE_EVIDENCE_REQUIRED'; END IF;
        SELECT * INTO entry FROM credit_ledger WHERE id=(args->>'consumption_id')::uuid
            AND organization_id=org AND event_type='CREDIT_CONSUMPTION' AND ledger_version=2;
        IF NOT FOUND THEN RAISE EXCEPTION 'ORIGINAL_CONSUMPTION_REQUIRED' USING ERRCODE='42501'; END IF;
        SELECT * INTO previous FROM credit_ledger WHERE original_consumption_id=entry.id AND event_type='CREDIT_RESTORE';
        IF FOUND THEN RETURN jsonb_build_object('ledger_id',previous.id,'applied',false); END IF;
        IF entry.funding='TRIAL' THEN
            UPDATE psique_trials SET credits_used=credits_used-1 WHERE organization_id=org;
        END IF;
        event_id:=psique_v2_append(org,actor,'CREDIT_RESTORE',1,0,'restore:'||entry.id,
            entry.analysis_source_id,entry.reservation_id,entry.id,entry.funding,explanation||' ['||evidence||']');
        PERFORM psique_v2_expire(org,actor,instant);
        RETURN jsonb_build_object('ledger_id',event_id,'applied',true);
    END IF;

    IF command='BEGIN' THEN
        SELECT * INTO source FROM psique_analysis_sources
            WHERE organization_id=org AND id=(args->>'source_id')::uuid AND owner_membership_id=member;
        IF NOT FOUND THEN RAISE EXCEPTION 'SOURCE_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
        SELECT * INTO attempt FROM psique_analysis_attempts WHERE organization_id=org
            AND analysis_source_id=source.id AND execution_key=args->>'execution_key';
        IF FOUND THEN RETURN jsonb_build_object('attempt_id',attempt.id,'status',attempt.status,'started',false); END IF;
        IF EXISTS(SELECT 1 FROM psique_analysis_attempts WHERE analysis_source_id=source.id AND status='PROCESSING')
            OR EXISTS(SELECT 1 FROM psique_credit_reservations WHERE analysis_source_id=source.id AND status='RESERVED') THEN
            RETURN jsonb_build_object('started',false,'reason','SOURCE_IN_PROGRESS');
        END IF;
        SELECT * INTO entry FROM credit_ledger WHERE analysis_source_id=source.id AND event_type='CREDIT_CONSUMPTION';
        IF NOT FOUND AND wallet.balance-wallet.reserved_balance<1 THEN
            RETURN jsonb_build_object('started',false,'reason','INSUFFICIENT_CREDITS');
        END IF;
        INSERT INTO psique_analysis_attempts(organization_id,analysis_source_id,execution_key,started_at,lease_until)
            VALUES(org,source.id,args->>'execution_key',instant,(args->>'lease_until')::timestamptz)
            RETURNING * INTO attempt;
        IF entry.id IS NULL THEN
            funding_source:=CASE WHEN free>0 THEN 'TRIAL' ELSE 'PAID' END;
            INSERT INTO psique_credit_reservations(organization_id,analysis_source_id,analysis_attempt_id,funding)
                VALUES(org,source.id,attempt.id,funding_source) RETURNING * INTO reservation;
            IF funding_source='TRIAL' THEN
                UPDATE psique_trials SET credits_reserved=credits_reserved+1 WHERE organization_id=org;
            END IF;
            PERFORM psique_v2_append(org,actor,'CREDIT_RESERVATION',0,1,'reserve:'||attempt.id,
                source.id,reservation.id,fund=>funding_source);
            PERFORM psique_v2_expire(org,actor,instant);
        END IF;
        RETURN jsonb_build_object('attempt_id',attempt.id,'status',attempt.status,'started',true,'chargeable',entry.id IS NULL);
    END IF;

    SELECT * INTO attempt FROM psique_analysis_attempts WHERE organization_id=org AND id=(args->>'attempt_id')::uuid;
    SELECT * INTO source FROM psique_analysis_sources WHERE organization_id=org AND id=attempt.analysis_source_id
        AND owner_membership_id=member;
    IF attempt.id IS NULL OR source.id IS NULL THEN RAISE EXCEPTION 'ATTEMPT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    SELECT * INTO reservation FROM psique_credit_reservations WHERE analysis_attempt_id=attempt.id;
    IF command='RECONCILE' THEN
        IF attempt.status='DELIVERED' THEN command:='CONSUME';
        ELSIF attempt.status='PROCESSING' AND attempt.lease_until<=instant THEN
            command:='RELEASE'; args:=args||jsonb_build_object('reason','WORKER_LEASE_EXPIRED');
        ELSE RETURN jsonb_build_object('status',attempt.status,'applied',false); END IF;
    END IF;
    IF command='HEARTBEAT' THEN
        IF attempt.status<>'PROCESSING' OR attempt.lease_until<=instant THEN RAISE EXCEPTION 'ATTEMPT_NOT_RUNNING'; END IF;
        IF (args->>'lease_until')::timestamptz<=attempt.lease_until THEN RAISE EXCEPTION 'LEASE_MUST_ADVANCE'; END IF;
        UPDATE psique_analysis_attempts SET lease_until=(args->>'lease_until')::timestamptz WHERE id=attempt.id;
        RETURN jsonb_build_object('status','PROCESSING');
    ELSIF command='DELIVER' THEN
        IF attempt.status='DELIVERED' THEN RETURN jsonb_build_object('report_id',attempt.report_id,'applied',false); END IF;
        IF attempt.status<>'PROCESSING' OR attempt.lease_until<=instant THEN RAISE EXCEPTION 'ATTEMPT_NOT_RUNNING'; END IF;
        payload:=args->'protected_report';
        IF args->>'technical_complete' IS DISTINCT FROM 'true' OR args->>'minimum_result_verified' IS DISTINCT FROM 'true'
            OR jsonb_typeof(payload) IS DISTINCT FROM 'object' OR payload='{}'::jsonb THEN
            RAISE EXCEPTION 'DELIVERY_CONTRACT_NOT_MET';
        END IF;
        IF coalesce(payload->>'transcript','')<>'' THEN RAISE EXCEPTION 'PROTECTED_REPORT_REQUIRED'; END IF;
        SELECT email INTO actor_email FROM users WHERE id=actor;
        report_key:='psique-v2:'||source.id;
        payload:=payload||jsonb_build_object('sessionId',report_key,'organizationId',org,
            'professionalEmail',actor_email,'analysisSourceId',source.id,'analysisAttemptId',attempt.id);
        INSERT INTO session_reports(id,organization_id,legacy_session_id,professional_membership_id,report_payload)
            VALUES(gen_random_uuid(),org,report_key,member,payload)
            ON CONFLICT(organization_id,legacy_session_id) DO UPDATE SET
                report_payload=EXCLUDED.report_payload,updated_at=clock_timestamp(),deleted_at=NULL
            WHERE session_reports.professional_membership_id=member
            RETURNING * INTO saved_report;
        IF NOT FOUND THEN RAISE EXCEPTION 'DELIVERY_OWNER_MISMATCH' USING ERRCODE='42501'; END IF;
        digest_value:=encode(digest(saved_report.report_payload::text,'sha256'),'hex');
        UPDATE psique_analysis_attempts SET status='DELIVERED',technical_completed_at=instant,
            delivered_at=instant,report_id=saved_report.id,delivery_sha256=digest_value WHERE id=attempt.id;
        RETURN jsonb_build_object('report_id',saved_report.id,'applied',true);
    ELSIF command='READ_DELIVERY' THEN
        SELECT * INTO saved_report FROM session_reports WHERE id=attempt.report_id AND organization_id=org
            AND professional_membership_id=member AND deleted_at IS NULL;
        IF attempt.status<>'DELIVERED' OR saved_report.id IS NULL THEN RAISE EXCEPTION 'DELIVERY_UNAVAILABLE'; END IF;
        RETURN jsonb_build_object('report_id',saved_report.id,'report',saved_report.report_payload);
    ELSIF command='CONSUME' THEN
        SELECT * INTO entry FROM credit_ledger WHERE analysis_source_id=source.id AND event_type='CREDIT_CONSUMPTION';
        IF entry.id IS NOT NULL THEN RETURN jsonb_build_object('ledger_id',entry.id,'applied',false); END IF;
        IF attempt.status<>'DELIVERED' OR reservation.id IS NULL OR reservation.status<>'RESERVED' THEN
            RAISE EXCEPTION 'DURABLE_DELIVERY_REQUIRED';
        END IF;
        SELECT * INTO saved_report FROM session_reports WHERE id=attempt.report_id AND organization_id=org
            AND professional_membership_id=member AND deleted_at IS NULL FOR SHARE;
        IF saved_report.id IS NULL OR encode(digest(saved_report.report_payload::text,'sha256'),'hex')<>attempt.delivery_sha256 THEN
            RAISE EXCEPTION 'DELIVERY_UNAVAILABLE';
        END IF;
        UPDATE psique_credit_reservations SET status='CONSUMED',resolved_at=instant WHERE id=reservation.id;
        IF reservation.funding='TRIAL' THEN
            UPDATE psique_trials SET credits_reserved=credits_reserved-1,credits_used=credits_used+1 WHERE organization_id=org;
        END IF;
        event_id:=psique_v2_append(org,actor,'CREDIT_CONSUMPTION',-1,-1,'consume:'||source.id,
            source.id,reservation.id,fund=>reservation.funding);
        PERFORM psique_v2_expire(org,actor,instant);
        RETURN jsonb_build_object('ledger_id',event_id,'applied',true);
    ELSIF command='RELEASE' THEN
        explanation:=trim(args->>'reason');
        IF coalesce(explanation,'')='' THEN RAISE EXCEPTION 'RELEASE_REASON_REQUIRED'; END IF;
        IF attempt.status='DELIVERED' THEN
            SELECT * INTO saved_report FROM session_reports WHERE id=attempt.report_id AND organization_id=org
                AND professional_membership_id=member AND deleted_at IS NULL FOR SHARE;
            IF saved_report.id IS NOT NULL AND
                encode(digest(saved_report.report_payload::text,'sha256'),'hex')=attempt.delivery_sha256 THEN
                RAISE EXCEPTION 'DELIVERED_REQUIRES_SETTLEMENT';
            END IF;
            IF reservation.status='CONSUMED' OR EXISTS(SELECT 1 FROM credit_ledger
                WHERE analysis_source_id=source.id AND event_type='CREDIT_CONSUMPTION') THEN
                RAISE EXCEPTION 'CONSUMED_REQUIRES_RESTORE';
            END IF;
            -- Failed availability before settlement: release without deleting
            -- the report or the historical delivery receipt.
        END IF;
        IF attempt.status='FAILED' THEN RETURN jsonb_build_object('applied',false,'status','FAILED'); END IF;
        UPDATE psique_analysis_attempts SET status='FAILED',failure_reason=explanation WHERE id=attempt.id;
        IF reservation.status='RESERVED' THEN
            UPDATE psique_credit_reservations SET status='RELEASED',resolved_at=instant WHERE id=reservation.id;
            IF reservation.funding='TRIAL' THEN
                UPDATE psique_trials SET credits_reserved=credits_reserved-1 WHERE organization_id=org;
            END IF;
            PERFORM psique_v2_append(org,actor,'CREDIT_RELEASE',0,-1,'release:'||attempt.id,
                source.id,reservation.id,fund=>reservation.funding,explanation=>explanation);
            PERFORM psique_v2_expire(org,actor,instant);
        END IF;
        RETURN jsonb_build_object('applied',true,'status','FAILED');
    END IF;
    RAISE EXCEPTION 'UNKNOWN_PSIQUE_COMMAND';
END $$;

-- Clinical activation of migration 040, verbatim plus the V2 ORG_ADMIN gate.
CREATE OR REPLACE FUNCTION psique_v2_clinical_set(org uuid, member uuid, actor uuid,
    target uuid, make_active boolean)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE target_row organization_memberships%ROWTYPE; current_row psique_clinical_memberships%ROWTYPE;
    instant timestamptz:=clock_timestamp(); changed boolean:=false;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    -- Habilitacao clinica e governanca clinica: em organizacao V2 exige
    -- ORG_ADMIN; FINANCE compra creditos, nao habilita profissional.
    IF psique_rbac_v2_active(org) AND NOT psique_v2_role_check(ARRAY['ORG_ADMIN']) THEN
        RAISE EXCEPTION 'PSIQUE_ORG_ADMIN_REQUIRED' USING ERRCODE='42501';
    END IF;
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

INSERT INTO schema_migrations(version) VALUES('042_psique_rbac_v2');
COMMIT;
