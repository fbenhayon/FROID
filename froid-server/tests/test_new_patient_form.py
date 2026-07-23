from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class NewPatientFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            ROOT / "froid-dashboard" / "src" / "pages" / "NewPatient.tsx"
        ).read_text(encoding="utf-8")

    def test_each_navigation_resets_patient_identity(self):
        self.assertIn("const location = useLocation();", self.source)
        reset = self.source[
            self.source.index("useEffect(() => {\n    setForm({") :
            self.source.index("const updateForm")
        ]
        self.assertIn("patient_name: patientNamePrefill", reset)
        self.assertIn("patient_email: patientEmailPrefill", reset)
        self.assertIn("patient_phone: patientPhonePrefill", reset)
        self.assertIn("location.key", reset)
        self.assertIn("setInvite(null)", reset)

    def test_browser_autofill_is_disabled_for_new_patient_identity(self):
        self.assertIn('<form autoComplete="off"', self.source)
        self.assertGreaterEqual(self.source.count('autoComplete="off"'), 4)


if __name__ == "__main__":
    unittest.main()
