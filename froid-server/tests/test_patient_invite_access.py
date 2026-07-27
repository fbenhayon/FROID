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

    def test_reduced_patient_payload_is_sent_to_backend(self):
        # Fase de testes: apenas nome, telefone, e-mail, sexo, data de
        # nascimento e o consentimento unico. Sem CPF, confirmacao de e-mail
        # ou senha no fluxo de novo paciente.
        self.assertIn("{ ...patientPayload, consent }", self.invite_page)
        self.assertNotIn("email_confirm", self.invite_page)
        self.assertIn("sex: patientForm.sex", self.invite_page)

    def test_backend_no_longer_requires_email_confirmation(self):
        self.assertNotIn("if email_confirm != patient_email:", self.backend)
        # A senha do paciente continua obrigatoria (minimo 8 caracteres).
        self.assertIn(
            'raise HTTPException(status_code=400, detail="Senha do paciente obrigatória com no minimo 8 caracteres")',
            self.backend,
        )


if __name__ == "__main__":
    unittest.main()
