BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT USAGE ON SCHEMA public TO froid_runtime;
        GRANT SELECT ON
            organizations, users, organization_memberships, membership_roles,
            membership_invitations, patients, patient_assignments,
            session_reports, consents, organization_wallets, credit_ledger,
            audit_events
        TO froid_runtime;
        GRANT INSERT, UPDATE ON
            membership_invitations, patients, patient_assignments,
            session_reports, consents, audit_events
        TO froid_runtime;
        GRANT DELETE ON
            membership_roles, patient_assignments, session_reports
        TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_current_organization_id()
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_current_membership_id()
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_has_role(text[])
            TO froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('003_runtime_role_grants')
ON CONFLICT (version) DO NOTHING;

COMMIT;
