"""Um profissional tambem pode ser paciente de outro profissional.

Nao e caso de borda: e a situacao normal de quem trabalha na area e faz
terapia. O mesmo e-mail passa a existir nas duas pontas do sistema, e as duas
sessoes podem estar abertas no mesmo navegador ao mesmo tempo.

O que estes testes protegem: as duas identidades nao se sobrescrevem, e o
portal do paciente tem por onde entrar. O aceite do convite deixou de exigir
CPF; se o login do portal so aceitasse CPF, quem entrou sem informar documento
ficaria trancado para fora do proprio prontuario.
"""

from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent


class DuasIdentidadesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        painel = ROOT / "froid-dashboard" / "src"
        cls.backend = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.portal = (painel / "pages" / "PatientPortalPage.tsx").read_text(
            encoding="utf-8"
        )
        cls.convite = (painel / "pages" / "PatientInvitePage.tsx").read_text(
            encoding="utf-8"
        )
        cls.app = (painel / "App.tsx").read_text(encoding="utf-8")
        inicio = cls.backend.index('@app.post("/api/patient-auth/login")')
        cls.login = cls.backend[
            inicio : cls.backend.index('@app.post("/api/patient-auth/google")', inicio)
        ]

    # --- as duas sessoes nao colidem -----------------------------------------

    def test_servidor_guarda_as_duas_sessoes_em_stores_separados(self):
        self.assertIn("SESSION_USERS = {}", self.backend)
        self.assertIn("PATIENT_PORTAL_SESSIONS: Dict[str, dict] = {}", self.backend)
        # A sessao de paciente nunca e resolvida no store do profissional.
        contexto = self.backend[
            self.backend.index("def _current_patient_from_request(") :
        ][:900]
        self.assertIn("PATIENT_PORTAL_SESSIONS.get(token)", contexto)
        self.assertNotIn("SESSION_USERS", contexto)

    def test_navegador_usa_chaves_e_armazenamentos_distintos(self):
        # Profissional em localStorage (sobrevive ao fechar a aba);
        # paciente em sessionStorage (morre com a aba, porque dado clinico em
        # aparelho compartilhado nao deve sobreviver a visita).
        self.assertIn('localStorage.getItem("froid_token")', self.app)
        self.assertIn('const PATIENT_TOKEN_KEY = "froid_patient_token"', self.portal)
        self.assertIn("window.sessionStorage.getItem(PATIENT_TOKEN_KEY)", self.portal)
        self.assertIn(
            'sessionStorage.setItem("froid_patient_token"', self.convite
        )
        # A chave do paciente nunca e gravada onde vive a do profissional.
        self.assertNotIn('sessionStorage.setItem("froid_token"', self.convite)
        self.assertNotIn('localStorage.setItem("froid_token"', self.convite)
        self.assertNotIn("localStorage.setItem(PATIENT_TOKEN_KEY", self.portal)

    def test_aceitar_convite_nao_toca_na_sessao_do_profissional(self):
        # Quem esta logado como profissional e abre o proprio convite continua
        # logado depois de aceitar: sao armazenamentos diferentes.
        self.assertNotIn("froid_token", self.convite)

    # --- o portal tem por onde entrar ----------------------------------------

    def test_login_do_portal_aceita_cpf_ou_email(self):
        self.assertIn("_find_registered_patient_by_document(document)", self.login)
        self.assertIn("_find_registered_patient_by_email(email)", self.login)
        # O "@" decide a leitura. Aplicar _digits_only num e-mail extrairia
        # digitos avulsos e consultaria um documento que ninguem digitou.
        self.assertIn('if "@" in identificador:', self.login)
        self.assertLess(
            self.login.index('if "@" in identificador:'),
            self.login.index("_digits_only(identificador)"),
        )

    def test_modelo_do_login_declara_os_dois_campos(self):
        modelo = self.backend[
            self.backend.index("class PatientPortalLoginRequest(BaseModel):") :
        ][:400]
        self.assertIn("document: str", modelo)
        self.assertIn("email: str", modelo)

    def test_recusa_do_portal_e_uniforme(self):
        """Identificador inexistente e senha errada respondem igual.

        Duas mensagens distintas transformavam a rota em consulta de quem e
        paciente no FROID.
        """
        self.assertEqual(self.login.count("status_code=401"), 1)
        self.assertNotIn("Paciente não localizado", self.login)
        self.assertIn("not patient or not _verify_patient_password(", self.login)

    def test_limite_de_tentativas_cobre_os_dois_identificadores(self):
        self.assertIn("{remote_reference}:{document or email}", self.login)
        self.assertIn("status_code=429", self.login)

    def test_google_do_portal_exige_paciente_ja_cadastrado(self):
        """O profissional-paciente entra pelo Google apenas se o e-mail do
        convite for o mesmo da conta Google — e o vinculo fica fixado."""
        rota = self.backend[
            self.backend.index('@app.post("/api/patient-auth/google")') :
        ][:1600]
        self.assertIn("_find_registered_patient_by_email(", rota)
        self.assertIn("bound_google_sub", rota)
        self.assertIn("status_code=403", rota)

    def test_busca_por_email_recusa_ambiguidade(self):
        """Dois pacientes com o mesmo e-mail nao autenticam nenhum dos dois.

        Escolher "o primeiro" entregaria o prontuario de um a outro.
        """
        finder = self.backend[
            self.backend.index("def _find_registered_patient_by_email(") :
        ][:700]
        self.assertIn("if len(matches) != 1:", finder)
        self.assertIn("return None", finder)


if __name__ == "__main__":
    unittest.main()
