"""O portao de acesso depois que a liberacao previa acabou.

ESTE ARQUIVO GUARDAVA A DECISAO CONTRARIA. Ate 09/09/2026 ele se chamava
`test_professional_manual_approval` e exigia que todo cadastro novo nascesse
`pending` e esperasse a liberacao manual do FROID — inclusive a tela
"Cadastro aguardando aprovacao FROID" e o contador "Aprovacoes pendentes".

A decisao foi revogada pelo dono ao entrar a fase operacional: cadastro
concluido entra. Reescrito, e nao apagado, porque a metade que continua valendo
e a mais importante — os TRES portoes (middleware HTTP, portao de feature e
websocket) seguem recusando conta cortada, e o corte continua sendo exclusivo do
endpoint administrativo auditado.

A distincao que este arquivo existe para manter viva:

    ESPERA PREVIA (retirada)   ninguem e barrado por ainda nao ter sido olhado
    SUSPENSAO     (mantida)    quem foi cortado por decisao administrativa fica
                               fora, e sabe disso, e sabe para onde escrever

Afrouxar a primeira nao pode afrouxar a segunda. Se um dia os dois portoes
deixarem de recusar conta suspensa, este arquivo reprova.
"""

import ast
import json
import logging
import sys
import typing
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

BACKEND = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
ARVORE = ast.parse(BACKEND)

from subscriptions import PAID_SESSION_STATUSES  # noqa: E402


def _funcao(nome, ns):
    alvo = next(
        n for n in ARVORE.body if isinstance(n, ast.FunctionDef) and n.name == nome
    )
    exec(ast.get_source_segment(BACKEND, alvo), ns)  # noqa: S102
    return ns[nome]


def _trecho(inicio: str, fim: str) -> str:
    i = BACKEND.index(inicio)
    return BACKEND[i : BACKEND.index(fim, i)]


def _sem_comentarios(texto: str) -> str:
    """O que a maquina executa e o que a tela mostra, sem o que o autor anotou.

    Duas asserceos deste arquivo reprovaram na primeira execucao por casar com
    COMENTARIOS que contam por que a regra mudou — exatamente as linhas que a
    higienizacao manda preservar. Proibir a palavra em todo o arquivo proibiria
    registrar o incidente, que e a parte que impede o defeito de voltar.
    """
    linhas = []
    em_bloco = False
    for linha in texto.split("\n"):
        nua = linha.strip()
        if em_bloco:
            if "*/" in nua:
                em_bloco = False
            continue
        if nua.startswith("#") or nua.startswith("//") or nua.startswith("*"):
            continue
        if nua.startswith("{/*") or nua.startswith("/*"):
            if "*/" not in nua:
                em_bloco = True
            continue
        linhas.append(linha)
    return "\n".join(linhas)


class _Registro(logging.Handler):
    def __init__(self):
        super().__init__()
        self.avisos = []

    def emit(self, record):
        if record.levelno >= logging.WARNING:
            # getMessage() ja aplica os args; formatar de novo estoura.
            self.avisos.append(record.getMessage())


# O estado de acesso executado de verdade, e nao afirmado por leitura de texto.
# Importar main exigiria fastapi e cryptography, ausentes do ambiente de teste;
# extrair pela AST garante que o testado e o codigo que vai rodar.
PERFIS: dict = {}
AVISOS = _Registro()
_LOGGER = logging.getLogger("teste.portao")
_LOGGER.addHandler(AVISOS)

NS = {
    "Any": typing.Any,
    "Optional": typing.Optional,
    "PROFESSIONAL_PROFILES": PERFIS,
    "PAID_SESSION_STATUSES": PAID_SESSION_STATUSES,
    "FROID_MAX_PENDING_SETTLEMENTS": 10,
    "FROID_TRIAL_CONTACT_EMAIL": "froid@froid.com.br",
    "FROID_TRIAL_TIERS": ((100, 20), (100, 10)),
    "FROID_TRIAL_SESSIONS": 10,
    "LOGGER": _LOGGER,
    "_is_admin_email": lambda email: False,
}
NS["_local_digits_only"] = _funcao("_local_digits_only", NS)
NS["_local_int"] = _funcao("_local_int", NS)
NS["_normalize_email"] = _funcao("_normalize_email", NS)
NS["_cadastro_clinico"] = _funcao("_cadastro_clinico", NS)
NS["_tipos_de_cadastro"] = _funcao("_tipos_de_cadastro", NS)
NS["_documento_da_empresa_nr1"] = _funcao("_documento_da_empresa_nr1", NS)
NS["_trial_state"] = _funcao("_trial_state", NS)
estado_de_acesso = _funcao("_professional_access_status", NS)


def perfil_clinico(**campos):
    base = {
        "account_type": "individual",
        "lgpd_acknowledged": True,
        "selected_plan": "trial-froid",
        "profile_fields": {"cpf": "12345678901"},
        "payment_status": "trialing",
        "total_sessions": 10,
        "used_sessions": 0,
        "trial_sessions": 10,
        "trial_position": 7,
    }
    base.update(campos)
    return base


def perfil_empresa(**campos):
    base = {
        "account_type": "nr1_company",
        "lgpd_acknowledged": True,
        "organization_document": "12345678000190",
    }
    base.update(campos)
    return base


class CadastroConcluidoEntra(unittest.TestCase):
    """A metade nova: ninguem espera para ser olhado."""

    def setUp(self):
        PERFIS.clear()
        AVISOS.avisos.clear()

    def test_clinico_recem_cadastrado_nao_e_bloqueado(self):
        PERFIS["novo@psi.com"] = perfil_clinico()
        estado = estado_de_acesso("novo@psi.com")
        self.assertFalse(estado["access_blocked"])
        self.assertEqual(estado["access_block_status"], "")
        self.assertFalse(estado["onboarding_required"])

    def test_empresa_recem_cadastrada_nao_e_bloqueada(self):
        """O caso concreto que a mudanca resolve.

        A empresa recebia 403 com "a liberacao para operar o modulo NR-1 e feita
        pela equipe FROID" no primeiro passo depois do cadastro, e o cadastro
        guiado parava ali.
        """
        PERFIS["rh@empresa.com"] = perfil_empresa()
        estado = estado_de_acesso("rh@empresa.com")
        self.assertFalse(estado["access_blocked"])
        self.assertFalse(estado["onboarding_required"])

    def test_o_pending_gravado_na_fase_antiga_passa_a_entrar(self):
        """A transicao, sem migracao.

        Quem se cadastrou enquanto a liberacao previa existia tem "pending"
        gravado no arquivo de estado. A conversao mora na LEITURA justamente
        para que nenhum dado precise ser reescrito — e para que voltar atras nao
        exija desfazer escrita nenhuma.
        """
        PERFIS["esperando@psi.com"] = perfil_clinico(access_approval_status="pending")
        estado = estado_de_acesso("esperando@psi.com")
        self.assertFalse(estado["access_blocked"])
        self.assertFalse(estado["onboarding_required"])

    def test_conta_sem_perfil_nenhum_nao_e_tratada_como_cortada(self):
        estado = estado_de_acesso("ninguem@psi.com")
        self.assertFalse(estado["access_blocked"])
        # Continua precisando de cadastro — que e outra coisa, e por outro
        # caminho.
        self.assertTrue(estado["onboarding_required"])


class ASuspensaoContinuaValendo(unittest.TestCase):
    """A metade antiga, que nao pode ter sido afrouxada junto."""

    def setUp(self):
        PERFIS.clear()
        AVISOS.avisos.clear()

    def test_conta_suspensa_fica_fora(self):
        PERFIS["cortado@psi.com"] = perfil_clinico(access_approval_status="suspended")
        estado = estado_de_acesso("cortado@psi.com")
        self.assertTrue(estado["access_blocked"])
        self.assertEqual(estado["access_block_status"], "suspended")
        self.assertTrue(estado["onboarding_required"])

    def test_conta_recusada_fica_fora(self):
        PERFIS["recusado@psi.com"] = perfil_clinico(access_approval_status="rejected")
        estado = estado_de_acesso("recusado@psi.com")
        self.assertTrue(estado["access_blocked"])
        self.assertEqual(estado["access_block_status"], "rejected")

    def test_empresa_suspensa_tambem_fica_fora(self):
        # A empresa NR-1 tem regra propria de "pronto para usar" (nao compra
        # sessao). O corte tem de alcancar as duas reguas.
        PERFIS["rh@empresa.com"] = perfil_empresa(access_approval_status="suspended")
        estado = estado_de_acesso("rh@empresa.com")
        self.assertTrue(estado["access_blocked"])
        self.assertTrue(estado["onboarding_required"])

    def test_valor_desconhecido_libera_mas_avisa(self):
        """Nenhum caminho de escrita produz outro valor: se apareceu, e defeito.

        Bloquear por causa dele trancaria um cliente legitimo em cima de um
        estado corrompido. Passar em silencio faria o defeito ser
        indistinguivel de normalidade — por isso libera E avisa.
        """
        PERFIS["estranho@psi.com"] = perfil_clinico(access_approval_status="xpto")
        estado = estado_de_acesso("estranho@psi.com")
        self.assertFalse(estado["access_blocked"])
        self.assertTrue(
            any("estranho@psi.com" in aviso for aviso in AVISOS.avisos),
            f"nenhum aviso registrado; avisos={AVISOS.avisos}",
        )


class OsTresPortoesContinuamRecusando(unittest.TestCase):
    """Onde a recusa e aplicada. Perder um destes reabre o acesso cortado."""

    def test_middleware_http(self):
        middleware = _trecho(
            "async def security_audit_middleware",
            "def _require_active_subscription_for_context",
        )
        self.assertIn('request.url.path.startswith("/api/")', middleware)
        self.assertIn('approval.get("access_blocked")', middleware)
        self.assertIn("status_code = 403", middleware)
        # As rotas isentas continuam isentas: sem elas a pessoa suspensa nao
        # consegue nem ler o proprio estado para saber que esta suspensa.
        self.assertIn('"/api/auth/"', middleware)
        self.assertIn('"/api/subscriptions/"', middleware)

    def test_portao_das_features_profissionais(self):
        portao = _trecho(
            "def _require_professional_feature_access",
            "def _require_professional_websocket_access",
        )
        self.assertIn('approval.get("access_blocked")', portao)
        self.assertIn("status_code=403", portao)

    def test_portao_do_websocket(self):
        portao = _trecho(
            "def _require_professional_websocket_access", "def _session_matches_context"
        )
        self.assertIn('approval.get("access_blocked")', portao)
        self.assertIn("status_code=403", portao)

    def test_a_mensagem_nao_manda_mais_ninguem_esperar(self):
        """Dizer "aguardando aprovacao" a quem foi cortado manda a pessoa
        esperar uma coisa que nao vai chegar sozinha."""
        self.assertNotIn("aguardando aprovação FROID", BACKEND)
        self.assertNotIn("approval_pending", BACKEND)


class SoOAdministradorCorta(unittest.TestCase):
    def setUp(self):
        self.rota = _trecho(
            '@app.post("/api/admin/professionals/{professional_email}/access-approval")',
            '@app.get("/api/session-invites/{token}")',
        )

    def test_exige_administrador_e_registra_auditoria(self):
        self.assertIn("_require_admin_user(request)", self.rota)
        self.assertIn('action="admin_professional_access_approval"', self.rota)

    def test_pending_deixou_de_ser_um_destino(self):
        # Aceita-lo seria oferecer ao operador um botao que nao faz nada e que a
        # tela apresentaria como se tivesse feito.
        self.assertIn('{"approved", "rejected", "suspended"}', self.rota)
        self.assertNotIn('"pending"', _sem_comentarios(self.rota))

    def test_persiste_a_decisao(self):
        # Aprovar so em memoria fazia a suspensao evaporar no proximo
        # `docker compose up` — e o sintoma parecia "o botao nao fez nada".
        self.assertIn("_save_identity_state()", self.rota)

    def test_regravar_o_cadastro_nao_desfaz_a_suspensao(self):
        criacao = _trecho(
            "    approval_status = str(existing.get",
            '        approval_status = "approved"',
        )
        self.assertIn('{"suspended", "rejected"}', criacao)


class AChaveRetiradaNaoVoltaEmSilencio(unittest.TestCase):
    def test_o_codigo_nao_le_mais_a_variavel(self):
        lapide = "# LAPIDE: FROID_PROFESSIONAL_APPROVAL_REQUIRED"
        self.assertIn(lapide, BACKEND)
        # A lapide e a UNICA mencao: qualquer outra seria leitura viva.
        self.assertEqual(BACKEND.count("FROID_PROFESSIONAL_APPROVAL_REQUIRED"), 1)

    def test_o_compose_nao_encaminha_mais_a_chave(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("FROID_PROFESSIONAL_APPROVAL_REQUIRED", compose)

    def test_os_campos_antigos_sairam_do_contrato(self):
        """`manual_approval_ready` afirmaria que uma aprovacao manual esta
        pronta num sistema onde ela nao existe."""
        for campo in (
            '"manual_approval_required"',
            '"manual_approval_pending"',
            '"manual_approval_ready"',
            '"manual_approval_status"',
        ):
            self.assertNotIn(campo, BACKEND)


class ATransicaoEDeclarada(unittest.TestCase):
    """Transicao que nao aparece e indistinguivel de transicao que nao houve."""

    def test_o_arranque_relata_quem_saiu_da_espera_e_quem_continua_fora(self):
        corpo = _trecho("def _report_access_gate_state", "\n_report_access_gate_state()")
        self.assertIn('"released_from_pending"', corpo)
        self.assertIn('"blocked_accounts"', corpo)
        # E de fato chamado: funcao de relatorio que ninguem invoca e o mesmo
        # que nao ter relatorio.
        self.assertIn("\n_report_access_gate_state()\n", BACKEND)

    def test_o_relatorio_e_uma_linha_legivel_por_maquina(self):
        PERFIS.clear()
        PERFIS.update(
            {
                "a@psi.com": {"access_approval_status": "pending"},
                "b@psi.com": {"access_approval_status": "suspended"},
                "c@psi.com": {"access_approval_status": "approved"},
            }
        )
        registro = []
        ns = dict(NS)
        ns["LOGGER"] = type("L", (), {"info": lambda _self, m: registro.append(m)})()
        ns["json"] = json
        ns["_contas_bloqueadas"] = _funcao("_contas_bloqueadas", ns)
        _funcao("_report_access_gate_state", ns)()
        evento = json.loads(registro[0])
        self.assertEqual(evento["gate"], "suspension_only")
        self.assertEqual(evento["released_from_pending"], 1)
        self.assertEqual(evento["released_accounts"], ["a@psi.com"])
        self.assertEqual(evento["blocked"], 1)
        self.assertEqual(evento["blocked_accounts"], ["b@psi.com:suspended"])

    def test_a_sonda_publica_o_portao_que_existe(self):
        # Uma sonda que continuasse vigiando a chave retirada concluiria, do
        # silencio, que esta tudo como antes.
        self.assertIn('result["professional_access_gate"] = "suspension_only"', BACKEND)
        self.assertIn('result["blocked_professional_access"]', BACKEND)
        self.assertNotIn("professional_approval_required", BACKEND)


class AsTelasDizemOQueDeFatoAconteceu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = ROOT / "froid-dashboard" / "src" / "pages"
        cls.onboarding = (d / "ProfessionalOnboarding.tsx").read_text(encoding="utf-8")
        cls.empresa = (d / "Nr1CompanyOnboarding.tsx").read_text(encoding="utf-8")
        cls.admin_detail = (d / "AdminProfessionalDetail.tsx").read_text(encoding="utf-8")
        cls.admin_dashboard = (d / "AdminDashboard.tsx").read_text(encoding="utf-8")

    def test_nenhuma_tela_manda_esperar_aprovacao(self):
        for nome, texto in (
            ("ProfessionalOnboarding", self.onboarding),
            ("Nr1CompanyOnboarding", self.empresa),
            ("AdminProfessionalDetail", self.admin_detail),
            ("AdminDashboard", self.admin_dashboard),
        ):
            visivel = _sem_comentarios(texto)
            self.assertNotIn("aguardando aprovação", visivel, nome)
            self.assertNotIn("Aguardando aprovação", visivel, nome)
            self.assertNotIn("liberação da equipe FROID", visivel, nome)

    def test_a_tela_do_cortado_continua_existindo_e_evita_pagamento_duplo(self):
        """A necessidade que a tela antiga atendia era real.

        Sem ela, o titular cortado cai no formulario de cadastro e conclui que
        precisa pagar de novo. O aviso muda de motivo, nao de existencia.
        """
        self.assertIn("accessStatus?.access_blocked", self.onboarding)
        self.assertIn("Não realize novo pagamento", self.onboarding)
        self.assertIn("froid@froid.com.br", self.onboarding)

    def test_o_operador_ve_o_corte_e_a_volta(self):
        self.assertIn("Suspender acesso", self.admin_detail)
        self.assertIn("Restabelecer acesso", self.admin_detail)
        self.assertIn("blocked_professional_access", self.admin_dashboard)

    def test_a_lista_de_status_pagos_escrita_a_mao_saiu_da_tela(self):
        # Era `["paid","active","trialing"]`, ja sem os dois status que o
        # proprio servidor grava ao creditar sem Stripe. Mesmo defeito que
        # PAID_SESSION_STATUSES resolveu no backend, um andar acima.
        self.assertNotIn('["paid", "active", "trialing"]', self.onboarding)

    def test_a_ficha_administrativa_continua_compacta(self):
        self.assertIn("grid min-w-[980px] grid-cols-7", self.admin_detail)
        self.assertIn("reports.slice(0, 3)", self.admin_detail)
        self.assertIn("receivables.slice(0, 3)", self.admin_detail)


if __name__ == "__main__":
    unittest.main()
