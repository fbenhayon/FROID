from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]


class MultitenantMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase_one = (
            SERVER_DIR / "migrations" / "001_multitenant_foundation.sql"
        ).read_text(encoding="utf-8")
        cls.phase_two = (
            SERVER_DIR / "migrations" / "002_access_control.sql"
        ).read_text(encoding="utf-8")
        cls.runtime_grants = (
            SERVER_DIR / "migrations" / "003_runtime_role_grants.sql"
        ).read_text(encoding="utf-8")

    def test_cross_organization_foreign_keys_are_present(self):
        self.assertGreaterEqual(
            self.phase_one.count("FOREIGN KEY (organization_id"), 5
        )

    def test_patient_read_and_write_policies_are_separate(self):
        self.assertIn("patients_read ON patients FOR SELECT", self.phase_two)
        self.assertIn("patients_insert ON patients FOR INSERT", self.phase_two)
        self.assertIn("patients_update ON patients FOR UPDATE", self.phase_two)
        self.assertIn("patients_delete ON patients FOR DELETE", self.phase_two)
        self.assertNotIn("patients_write ON patients FOR ALL", self.phase_two)

    def test_auditor_policy_does_not_grant_clinical_report_access(self):
        report_policy_start = self.phase_two.index(
            "CREATE POLICY session_reports_read"
        )
        report_policy_end = self.phase_two.index(
            "CREATE POLICY session_reports_insert"
        )
        report_policy = self.phase_two[report_policy_start:report_policy_end]
        self.assertNotIn("auditor", report_policy)
        self.assertIn("auditor", self.phase_two)

    def test_audit_table_remains_append_only(self):
        self.assertIn("prevent_audit_mutation", self.phase_one)
        self.assertIn("audit_events_read", self.phase_two)

    def test_runtime_role_gets_rls_functions_but_not_schema_ownership(self):
        self.assertIn("GRANT EXECUTE ON FUNCTION froid_has_role", self.runtime_grants)
        self.assertNotIn("ALTER TABLE", self.runtime_grants)
        self.assertNotIn("CREATE ROLE", self.runtime_grants)


if __name__ == "__main__":
    unittest.main()
