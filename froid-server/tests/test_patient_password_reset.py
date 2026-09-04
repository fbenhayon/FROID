"""Nova senha de acesso ao portal do paciente, pedida por e-mail.

Antes deste caminho existir, a tela de acesso do paciente oferecia uma única
saída a quem esquecia a senha: entrar pelo Google com o mesmo endereço. Quem
não tem conta Google — e quem chegou ao FROID por convite de um profissional
com frequência não tem — ficava trancado do lado de fora sem nenhuma porta na
tela.

Os testes aqui cobrem as garantias que essa porta nova precisa prestar: ela não
diz a um estranho quem é paciente no FROID, o token não sobrevive em claro no
estado persistido nem a uma segunda tentativa, e a troca de senha derruba as
sessões que já estavam abertas naquele cadastro.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def _trecho(fonte: str, inicio: str, fim: str) -> str:
    comeco = fonte.index(inicio)
    return fonte[comeco : fonte.index(fim, comeco + len(inicio))]


class PatientPasswordResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        painel = ROOT / "froid-dashboard" / "src"
        cls.backend = (ROOT / "froid-server" / "main.py").read_text(encoding="utf-8")
        cls.portal = (painel / "pages" / "PatientPortalPage.tsx").read_text(
            encoding="utf-8"
        )
        cls.pagina = (painel / "pages" / "PatientPasswordResetPage.tsx").read_text(
            encoding="utf-8"
        )
        cls.app = (painel / "App.tsx").read_text(encoding="utf-8")
        cls.pedido = _trecho(
            cls.backend,
            '@app.post("/api/patient-auth/password-reset")',
            '@app.post("/api/patient-auth/password-reset/confirm")',
        )
        cls.confirmacao = _trecho(
            cls.backend,
            '@app.post("/api/patient-auth/password-reset/confirm")',
            '@app.put("/api/patient-portal/password")',
        )

    # --- pedido do link -------------------------------------------------------

    def test_pedido_responde_igual_exista_ou_nao_o_cadastro(self):
        # Uma recusa distinta para CPF inexistente transformaria a rota em
        # consulta de quem está em tratamento — o mesmo motivo pelo qual o
        # login do paciente não separa documento errado de senha errada.
        self.assertIn('resposta = {"status": "reset_sent"}', self.pedido)
        self.assertNotIn("raise HTTPException", self.pedido)
        self.assertEqual(self.pedido.count("return resposta"), 3)

    def test_pedido_aceita_cpf_ou_email_no_mesmo_campo(self):
        self.assertIn('identificador = str(payload.document or payload.email or "")', self.pedido)
        self.assertIn('if "@" in identificador:', self.pedido)
        self.assertIn("_find_registered_patient_by_email", self.pedido)
        self.assertIn("_find_registered_patient_by_document", self.pedido)

    def test_pedido_e_limitado_por_ip_e_por_identificador(self):
        self.assertIn('_rate_limit_guard(\n        "patient_reset",', self.pedido)
        self.assertIn('"patient_reset_id"', self.pedido)

    def test_cadastro_sem_email_nao_promete_envio(self):
        # O aceite do convite pode acontecer só com telefone. Sem endereço não
        # há para onde mandar o link, e a resposta continua a mesma das outras.
        self.assertIn('not _normalize_email(patient.get("email") or "")', self.pedido)

    def test_link_do_email_aponta_para_a_tela_do_paciente(self):
        envio = _trecho(
            self.backend,
            "async def _send_patient_password_reset_email(",
            '@app.post("/api/patient-auth/password-reset")',
        )
        self.assertIn('_public_app_link("/paciente/nova-senha?token="', envio)
        self.assertIn("FROID_PASSWORD_RESET_TTL_SECONDS", envio)
        self.assertIn("froid_mailer.dev_echo_enabled()", envio)

    # --- token ----------------------------------------------------------------

    def test_token_e_guardado_apenas_como_hash_e_queimado_no_uso(self):
        consumo = _trecho(
            self.backend,
            "def _consume_patient_reset_token(",
            "def _revoke_patient_portal_sessions(",
        )
        self.assertIn("_credential_token_hash(token)", consumo)
        self.assertIn("secrets.compare_digest(armazenado, token_hash)", consumo)
        # A queima vem antes da checagem de validade: token vencido não
        # sobrevive à tentativa de uso.
        pop = consumo.index('patient.pop(f"{PATIENT_RESET_TOKEN_KIND}_token_hash"')
        validade = consumo.index("valido = float(expira) >= agora")
        self.assertLess(pop, validade)
        self.assertIn("return patient if valido else None", consumo)

    def test_emissao_do_token_reaproveita_o_cofre_que_so_grava_hash(self):
        self.assertIn(
            "token = _issue_credential_token(\n        patient, PATIENT_RESET_TOKEN_KIND, FROID_PASSWORD_RESET_TTL_SECONDS\n    )",
            self.backend,
        )

    # --- confirmação ----------------------------------------------------------

    def test_confirmacao_grava_a_senha_e_derruba_as_sessoes_abertas(self):
        self.assertIn("_consume_patient_reset_token(", self.confirmacao)
        self.assertIn("_set_patient_password(patient, password)", self.confirmacao)
        self.assertIn("_revoke_patient_portal_sessions(patient_id)", self.confirmacao)
        self.assertIn("_save_identity_state()", self.confirmacao)
        self.assertIn('_issue_patient_portal_session(patient, "password")', self.confirmacao)

    def test_confirmacao_exige_o_mesmo_piso_do_aceite_do_convite(self):
        self.assertIn("len(password) < 8 or len(password) > 256", self.confirmacao)
        self.assertIn("A confirmação da senha não confere", self.confirmacao)

    def test_troca_de_senha_avisa_o_titular_depois_do_fato(self):
        self.assertIn(
            'await _notify_patient_password_changed(patient, "email_reset")',
            self.confirmacao,
        )
        aviso = _trecho(
            self.backend,
            "async def _notify_patient_password_changed(",
            "async def _send_patient_password_reset_email(",
        )
        # O aviso informa e só: link ou token dentro dele daria a quem
        # interceptou a mensagem um segundo caminho para a conta.
        self.assertNotIn("_issue_credential_token", aviso)
        self.assertNotIn("_public_app_link", aviso)
        # A senha já está gravada quando isto roda. Falha de SMTP não pode
        # virar erro na resposta, ou a pessoa tentaria de novo com um token
        # que já foi queimado.
        self.assertIn("except froid_mailer.MailerError:", aviso)
        self.assertNotIn("raise", aviso)

    def test_aviso_cobre_toda_troca_de_senha_e_nao_so_a_que_vem_do_email(self):
        troca = _trecho(
            self.backend,
            '@app.put("/api/patient-portal/password")',
            '@app.get("/api/patient-portal/reports")',
        )
        self.assertIn("_notify_patient_password_changed(", troca)

    def test_confirmacao_nao_registra_a_senha_no_log(self):
        registro = _trecho(self.confirmacao, "LOGGER.info(", "ensure_ascii=False")
        self.assertNotIn("payload.password", registro)
        self.assertNotIn('"password"', registro)

    # --- painel ---------------------------------------------------------------

    def test_tela_de_acesso_do_paciente_oferece_o_link_fora_do_google(self):
        # O link mora entre o botão de entrar e o bloco condicional do Google:
        # enquanto a recuperação dependia da chave do Google, um ambiente sem
        # essa chave não mostrava saída nenhuma a quem esquecia a senha.
        entre = _trecho(
            self.portal,
            '{loading ? "Validando..." : "Entrar no portal"}',
            "{googleClientId && (",
        )
        self.assertIn('to="/paciente/nova-senha"', entre)
        self.assertIn("Cadastrar nova senha de acesso", entre)
        # O caminho pelo Google continua na tela, agora como alternativa.
        self.assertIn("mesmo e-mail cadastrado no FROID", self.portal)

    def test_rota_publica_de_nova_senha_existe_no_painel(self):
        self.assertIn(
            '<Route path="/paciente/nova-senha" element={<PatientPasswordResetPage />} />',
            self.app,
        )
        self.assertIn(
            'const PatientPasswordResetPage = lazy(() => import("./pages/PatientPasswordResetPage")',
            self.app,
        )

    def test_pagina_pede_o_link_e_define_a_senha_com_a_sessao_do_portal(self):
        self.assertIn('"/api/patient-auth/password-reset"', self.pagina)
        self.assertIn('"/api/patient-auth/password-reset/confirm"', self.pagina)
        # Mesma chave e mesmo armazenamento do portal: a sessão do paciente
        # morre com a aba, e não pode migrar para localStorage por aqui.
        self.assertIn('const PATIENT_TOKEN_KEY = "froid_patient_token"', self.pagina)
        self.assertIn("window.sessionStorage.setItem(PATIENT_TOKEN_KEY", self.pagina)
        self.assertNotIn("window.localStorage", self.pagina)
        self.assertIn('navigate("/paciente", { replace: true })', self.pagina)


if __name__ == "__main__":
    unittest.main()
