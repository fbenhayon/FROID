from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PatientGoogleRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (ROOT / "froid-server" / "main.py").read_text(encoding="utf-8")
        cls.portal = (
            ROOT / "froid-dashboard" / "src" / "pages" / "PatientPortalPage.tsx"
        ).read_text(encoding="utf-8")

    def test_google_recovery_requires_verified_froid_google_credential(self):
        route_start = self.backend.index('@app.post("/api/patient-auth/google")')
        route_end = self.backend.index(
            '@app.get("/api/patient-auth/me")', route_start
        )
        route = self.backend[route_start:route_end]
        self.assertIn("await _verify_google_credential", route)
        self.assertIn("_find_registered_patient_by_email", route)
        self.assertIn("bound_google_sub", route)
        self.assertIn('_issue_patient_portal_session(patient, "google")', route)
        self.assertNotIn("_set_patient_password", route)

    def test_password_recovery_is_allowed_only_after_google_or_current_password(self):
        route_start = self.backend.index('@app.put("/api/patient-portal/password")')
        route_end = self.backend.index(
            '@app.get("/api/patient-portal/reports")', route_start
        )
        route = self.backend[route_start:route_end]
        self.assertIn('== "google"', route)
        self.assertIn("_verify_patient_password", route)
        self.assertIn("_set_patient_password", route)
        self.assertIn("PATIENT_PORTAL_SESSIONS.pop", route)
        self.assertNotIn("payload.new_password", route.split("LOGGER.info", 1)[-1])

    def test_patient_portal_exposes_google_recovery_and_new_password(self):
        self.assertIn('apiUrl("/api/patient-auth/google")', self.portal)
        self.assertIn("mesmo e-mail cadastrado no FROID", self.portal)
        self.assertIn('apiUrl("/api/patient-portal/password")', self.portal)
        self.assertEqual(self.portal.count('autoComplete="new-password"'), 2)


if __name__ == "__main__":
    unittest.main()
