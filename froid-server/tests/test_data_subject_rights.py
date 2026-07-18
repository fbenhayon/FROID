from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_access import AccessContext, decide  # noqa: E402


class DataSubjectRightsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.store = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        cls.migration = (
            SERVER_DIR / "migrations" / "008_data_subject_rights.sql"
        ).read_text(encoding="utf-8")
        cls.patient_portal = (
            SERVER_DIR.parent / "froid-dashboard" / "src" / "pages" / "PatientPortalPage.tsx"
        ).read_text(encoding="utf-8")

    @staticmethod
    def context(role: str) -> AccessContext:
        return AccessContext.create("org", "membership", "user", [role])

    def test_patient_portal_exposes_rights_and_export(self):
        self.assertIn('/api/patient-portal/privacy"', self.main)
        self.assertIn('/api/patient-portal/privacy/requests"', self.main)
        self.assertIn('/api/patient-portal/privacy/export"', self.main)

    def test_request_details_and_response_are_encrypted(self):
        self.assertIn("_protect_data_subject_details", self.main)
        self.assertIn("details_encrypted", self.main)
        self.assertIn("_protect_data_subject_response", self.main)
        self.assertIn("response_encrypted", self.main)

    def test_only_owner_and_administrator_manage_requests(self):
        self.assertTrue(decide(self.context("owner"), "privacy.manage").allowed)
        self.assertTrue(decide(self.context("administrator"), "privacy.manage").allowed)
        self.assertTrue(decide(self.context("supervisor"), "privacy.read").allowed)
        self.assertFalse(decide(self.context("supervisor"), "privacy.manage").allowed)
        self.assertTrue(decide(self.context("auditor"), "privacy.read").allowed)

    def test_request_events_are_append_only_and_tenant_scoped(self):
        self.assertIn("data_subject_request_events is append-only", self.migration)
        self.assertIn("ALTER TABLE data_subject_requests ENABLE ROW LEVEL SECURITY", self.migration)
        self.assertIn("froid_current_organization_id()", self.migration)
        self.assertIn("request_batch_id", self.migration)
        self.assertIn("REFERENCES data_subject_requests(organization_id, id)", self.migration)

    def test_patient_identity_is_bound_to_document_and_session_storage(self):
        self.assertIn("regexp_replace(coalesce(patient.document, '')", self.store)
        self.assertIn("identity_document", self.store)
        self.assertIn("window.sessionStorage.getItem(PATIENT_TOKEN_KEY)", self.patient_portal)
        self.assertNotIn("window.localStorage.setItem(PATIENT_TOKEN_KEY", self.patient_portal)

    def test_immediate_export_excludes_free_clinical_text(self):
        export_helper = self.main.split("def _privacy_export_report", 1)[1].split(
            "def _safe_float", 1
        )[0]
        self.assertNotIn('"clinicalNotes"', export_helper)
        self.assertNotIn('"conversationSummaries"', export_helper)
        self.assertNotIn('"professionalEmail"', export_helper)

    def test_restrictive_decision_requires_documented_basis(self):
        self.assertIn('status in {"denied", "partially_approved"}', self.main)
        self.assertIn("retention_exception", self.main)


if __name__ == "__main__":
    unittest.main()
