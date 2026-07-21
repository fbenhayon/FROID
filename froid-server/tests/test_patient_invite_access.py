import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PatientInviteAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.invite_page = (
            ROOT / "froid-dashboard" / "src" / "pages" / "PatientInvitePage.tsx"
        ).read_text(encoding="utf-8")
        cls.backend = (ROOT / "froid-server" / "main.py").read_text(encoding="utf-8")

    def test_confirmed_email_is_sent_to_backend(self):
        self.assertIn(
            "{ ...patientPayload, email_confirm: patientForm.email_confirm }",
            self.invite_page,
        )

    def test_backend_keeps_server_side_email_confirmation(self):
        self.assertIn(
            'body.get("email_confirm") or body.get("emailConfirmation")',
            self.backend,
        )
        self.assertIn("if email_confirm != patient_email:", self.backend)


if __name__ == "__main__":
    unittest.main()
