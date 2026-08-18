"""Cadastro e login de profissional sem conta Google.

Até este módulo existir, toda identidade profissional vinha do Google, que
entregava o e-mail já verificado. Ao abrir o cadastro por senha o FROID passou
a ser o responsável por provar o endereço — e os testes aqui cobrem
exatamente as garantias que o Google prestava de graça e agora são nossas:
o e-mail é provado antes de a conta valer, o token não sobrevive em claro em
lugar nenhum, e o formulário público não vira consulta de quem atende pelo
FROID.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def _trecho(fonte: str, inicio: str, fim: str) -> str:
    comeco = fonte.index(inicio)
    return fonte[comeco : fonte.index(fim, comeco + len(inicio))]


class ProfessionalPasswordAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server = ROOT / "froid-server"
        painel = ROOT / "froid-dashboard" / "src"
        cls.backend = (server / "main.py").read_text(encoding="utf-8")
        cls.mailer = (server / "froid_mailer.py").read_text(encoding="utf-8")
        cls.acesso = (painel / "pages" / "AccountAccessPages.tsx").read_text(
            encoding="utf-8"
        )
        cls.login = (painel / "pages" / "LoginPage.tsx").read_text(encoding="utf-8")
        cls.app = (painel / "App.tsx").read_text(encoding="utf-8")

    # --- cofre de credenciais -------------------------------------------------

    def test_credenciais_ficam_fora_do_perfil_e_sao_persistidas(self):
        self.assertIn("PROFESSIONAL_CREDENTIALS: Dict[str, dict] = {}", self.backend)
        self.assertIn(
            '"professional_credentials": PROFESSIONAL_CREDENTIALS,', self.backend
        )
        self.assertIn('state.get("professional_credentials")', self.backend)
        self.assertIn("    global PROFESSIONAL_CREDENTIALS", self.backend)

    def test_senha_usa_o_mesmo_pbkdf2_com_sal_por_credencial(self):
        trecho = _trecho(
            self.backend,
            "def _set_professional_password(",
            "def _credential_token_hash(",
        )
        self.assertIn("secrets.token_hex(16)", trecho)
        self.assertIn("_password_hash(password, salt)", trecho)
        self.assertIn("secrets.compare_digest", trecho)

    def test_token_de_email_so_existe_em_hash_e_queima_no_uso(self):
        emissao = _trecho(
            self.backend, "def _issue_credential_token(", "def _consume_credential_token("
        )
        self.assertIn("_credential_token_hash(token)", emissao)
        # O token cru é devolvido para virar link, nunca gravado na credencial.
        self.assertNotIn('credential[f"{kind}_token"] =', emissao)

        consumo = _trecho(
            self.backend, "def _consume_credential_token(", "def _revoke_professional_sessions("
        )
        self.assertIn("secrets.compare_digest", consumo)
        # Queima antes de julgar a validade: token expirado não sobrevive à
        # tentativa de uso.
        self.assertLess(
            consumo.index('credential.pop(f"{kind}_token_hash", None)'),
            consumo.index("valido"),
        )

    # --- cadastro -------------------------------------------------------------

    def test_cadastro_responde_igual_para_conta_existente_e_nova(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/register")',
            '@app.post("/api/auth/resend-verification")',
        )
        self.assertEqual(rota.count('resposta = {"status": "verification_sent"}'), 1)
        # Dois desfechos, uma só forma de resposta: nada distingue de fora um
        # e-mail já cadastrado de um inédito.
        self.assertEqual(rota.count("return resposta"), 2)
        self.assertNotIn("já cadastrado", rota.split('"""', 2)[-1])
        self.assertNotIn("status_code=409", rota)

    def test_cadastro_nao_reescreve_senha_de_conta_ja_verificada(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/register")',
            '@app.post("/api/auth/resend-verification")',
        )
        verificada = rota.index('existente.get("email_verified")')
        primeira_gravacao = rota.index("_set_professional_password(credencial")
        # A gravação da senha está depois do desvio que trata conta verificada,
        # e aquele ramo retorna antes de chegar nela.
        self.assertLess(verificada, primeira_gravacao)
        self.assertIn("_send_password_reset_email(existente)", rota)

    def test_cadastro_tem_limite_por_ip_e_por_email(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/register")',
            '@app.post("/api/auth/resend-verification")',
        )
        self.assertIn('"auth_register", _client_ip(request)', rota)
        self.assertIn('"auth_register_email", email', rota)

    def test_cadastro_exige_politica_de_senha_e_pode_ser_desligado(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/register")',
            '@app.post("/api/auth/resend-verification")',
        )
        self.assertIn("if not FROID_REGISTRATION_ENABLED:", rota)
        self.assertIn("_password_policy_error(password)", rota)

        politica = _trecho(
            self.backend, "def _password_policy_error(", "def _set_professional_password("
        )
        self.assertIn("FROID_PASSWORD_MIN_LENGTH", politica)
        self.assertIn("ch.isdigit()", politica)

    def test_log_de_cadastro_nao_carrega_email_nem_senha(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/register")',
            '@app.post("/api/auth/resend-verification")',
        )
        for bloco in rota.split("LOGGER.info")[1:]:
            corpo = bloco[: bloco.index("        )")]
            self.assertNotIn("email", corpo)
            self.assertNotIn("password", corpo)

    # --- verificação e login --------------------------------------------------

    def test_verificacao_marca_o_email_e_devolve_sessao(self):
        rota = _trecho(
            self.backend, '@app.post("/api/auth/verify-email")', '@app.post("/api/auth/login")'
        )
        self.assertIn('_consume_credential_token("verification", token)', rota)
        self.assertIn('credencial["email_verified"] = True', rota)
        self.assertIn("return _issue_session(", rota)

    def test_login_por_senha_exige_email_verificado(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/login")',
            '@app.post("/api/auth/password-reset")',
        )
        self.assertIn("_verify_professional_password(", rota)
        self.assertIn('if not credencial.get("email_verified"):', rota)
        self.assertIn("status_code=403", rota)
        # Credencial inexistente e senha errada dão a mesma resposta.
        self.assertEqual(rota.count('detail="E-mail ou senha inválidos"'), 1)

    def test_formulario_antigo_de_senha_passa_a_consultar_o_cofre(self):
        trecho = _trecho(self.backend, "def _verify_local_login(", "@app.post")
        cofre = trecho.index("PROFESSIONAL_CREDENTIALS.get(email)")
        allowlist = trecho.index("FROID_LOCAL_AUTH_PASSWORD and FROID_LOCAL_AUTH_EMAILS")
        # A conta real vem antes da lista local de desenvolvimento; a lista
        # nunca passa por cima de uma credencial existente.
        self.assertLess(cofre, allowlist)
        self.assertIn('credencial.get("email_verified")', trecho)

    # --- recuperação ----------------------------------------------------------

    def test_recuperacao_responde_igual_exista_ou_nao_a_conta(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/password-reset")',
            '@app.post("/api/auth/password-reset/confirm")',
        )
        self.assertEqual(rota.count('resposta = {"status": "reset_sent"}'), 1)
        self.assertEqual(rota.count("return resposta"), 3)
        self.assertNotIn("status_code=404", rota)

    def test_nova_senha_derruba_as_sessoes_vivas_da_conta(self):
        rota = _trecho(
            self.backend,
            '@app.post("/api/auth/password-reset/confirm")',
            '@app.get("/api/auth/me")',
        )
        self.assertIn('_consume_credential_token("reset", token)', rota)
        self.assertIn("_revoke_professional_sessions(email)", rota)
        self.assertIn('credencial["email_verified"] = True', rota)

        revogacao = _trecho(
            self.backend, "def _revoke_professional_sessions(", "def _public_app_link("
        )
        self.assertIn("SESSION_USERS.pop(token, None)", revogacao)

    # --- entrega de e-mail ----------------------------------------------------

    def test_mailer_nao_registra_destinatario_no_log_de_falha(self):
        chamada = _trecho(self.mailer, "        LOGGER.warning(\n", "        )")
        self.assertIn("SMTP_HOST", chamada)
        self.assertIn("type(exc).__name__", chamada)
        # Nem o endereço nem a exceção crua do smtplib, que costuma carregá-lo.
        self.assertNotIn("destino", chamada)
        self.assertNotIn("to_address", chamada)
        self.assertNotIn("%s", chamada.replace("(host=%s, erro=%s)", ""))

    def test_envio_smtp_sai_do_laco_de_eventos(self):
        self.assertIn(
            "await asyncio.to_thread(\n            froid_mailer.send_email", self.backend
        )

    def test_escotilha_de_dev_so_vale_sem_smtp_configurado(self):
        trecho = _trecho(self.mailer, "def dev_echo_enabled(", "def send_email(")
        self.assertIn("SMTP_DEV_ECHO and not mailer_enabled()", trecho)

    def test_config_nao_oferece_cadastro_sem_canal_de_email(self):
        rota = _trecho(
            self.backend, '@app.get("/api/auth/config")', '@app.post("/api/auth/google")'
        )
        self.assertIn("froid_mailer.mailer_enabled() or froid_mailer.dev_echo_enabled()", rota)
        self.assertIn("FROID_PASSWORD_MIN_LENGTH", rota)

    # --- painel ---------------------------------------------------------------

    def test_rotas_publicas_de_acesso_existem_no_painel(self):
        self.assertIn('path="/registrar"', self.app)
        self.assertIn('path="/verificar-email"', self.app)
        self.assertIn('path="/recuperar-senha"', self.app)
        # Verificação e recuperação não passam por protectedElement: quem chega
        # nelas é justamente quem ainda não tem sessão.
        self.assertIn(
            '<Route path="/verificar-email" element={<VerifyEmailPage onLogin={setUser} />} />',
            self.app,
        )

    def test_entrar_e_criar_acesso_sao_a_mesma_tela(self):
        # /registrar não é uma página separada: é a tela de acesso aberta na
        # aba de cadastro. Uma segunda página faria quem já tem conta ter de
        # voltar, e esconderia o botão do Google — que resolve os dois casos.
        self.assertIn('initialMode="criar"', self.app)
        self.assertNotIn("module.RegisterPage", self.app)
        self.assertIn('postAuthJson("/api/auth/register"', self.login)
        self.assertIn('completeLogin({ email, password }, "/api/auth/login")', self.login)
        self.assertIn('text: "continue_with"', self.login)

    def test_telas_de_email_conversam_com_as_rotas_certas(self):
        self.assertIn('postAuthJson("/api/auth/verify-email"', self.acesso)
        self.assertIn('postAuthJson("/api/auth/resend-verification"', self.acesso)
        self.assertIn('postAuthJson("/api/auth/password-reset"', self.acesso)
        self.assertIn('postAuthJson("/api/auth/password-reset/confirm"', self.acesso)

    def test_campos_de_senha_nao_pedem_autocompletar_de_senha_salva(self):
        # Duas na recuperação (nova senha e confirmação); duas no cadastro.
        self.assertEqual(self.acesso.count('autoComplete="new-password"'), 2)
        self.assertEqual(self.login.count('autoComplete="new-password"'), 2)
        self.assertIn('autoComplete="current-password"', self.login)

    def test_aba_de_cadastro_depende_do_servidor(self):
        self.assertIn("registrationEnabled", self.login)
        self.assertIn("data?.registration_enabled", self.login)
        self.assertIn('to="/recuperar-senha"', self.login)

    def test_piso_de_senha_vem_do_servidor_nas_duas_telas(self):
        for fonte in (self.login, self.acesso):
            self.assertIn("data?.password_min_length", fonte)
            self.assertIn("minLength={senhaMinima}", fonte)


if __name__ == "__main__":
    unittest.main()
