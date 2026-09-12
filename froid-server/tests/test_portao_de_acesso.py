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
from datetime import datetime, timedelta, timezone
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


def _constante(nome):
    """Le uma constante de modulo do main.py sem importar o main.py inteiro.

    Importar traria FastAPI, banco e chaves; o que precisamos e um literal.
    """
    for no in ARVORE.body:
        if isinstance(no, ast.Assign) and any(
            getattr(alvo, "id", "") == nome for alvo in no.targets
        ):
            return eval(compile(ast.Expression(no.value), "<main>", "eval"))  # noqa: S307
    raise AssertionError(f"constante {nome} nao encontrada em main.py")


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


class AGuardaDocumentalSobreviveAoFimDoPlano(unittest.TestCase):
    """Plano vencido para de cobrar servico novo; nao confisca prontuario.

    O CASO, 12/09/2026. `_authorize_tenant_request` chamava o portao de
    assinatura na PRIMEIRA linha, antes de saber o que estava sendo pedido.
    Plano vencido devolvia 402 para tudo — inclusive para LER a sessao que o
    profissional ja tinha realizado e ja havia pago.

    Isso nao e alavanca comercial: a obrigacao de guarda documental e do
    profissional perante o conselho dele, e nao some porque a fatura atrasou.
    Decisao do dono: noventa dias de leitura contados do fim do periodo pago.

    A armadilha que este arquivo existe para travar e a do VOCABULARIO. O
    primeiro rascunho da lista trazia `patients.read_all` e `reports.read_all`
    — que sao CONCESSOES de papel, nao acoes pedidas. O que chega ao portao e
    `reports.read`. A lista errada nao casaria com pedido nenhum, a janela
    nunca abriria, e NADA acusaria erro: o sintoma seria o 402 de sempre, agora
    com um pedaco de codigo morto jurando que resolvia.
    """

    @classmethod
    def setUpClass(cls):
        ns = {
            "datetime": datetime,
            "timezone": timezone,
            "timedelta": timedelta,
            "Optional": typing.Optional,
        }
        ns["LEITURA_APOS_ENCERRAMENTO_DIAS"] = _constante(
            "LEITURA_APOS_ENCERRAMENTO_DIAS"
        )
        # staticmethod: sem isto o atributo de classe vira metodo e o
        # dicionario da assinatura chegaria como `self`.
        cls.dentro = staticmethod(_funcao("_dentro_da_janela_de_guarda", ns))
        cls.dias = ns["LEITURA_APOS_ENCERRAMENTO_DIAS"]

    def _venceu_ha(self, dias):
        return {
            "status": "canceled",
            "current_period_end": datetime.now(timezone.utc) - timedelta(days=dias),
        }

    def test_a_janela_e_de_noventa_dias(self):
        self.assertEqual(90, self.dias)

    def test_logo_depois_do_vencimento_ainda_le(self):
        self.assertTrue(self.dentro(self._venceu_ha(1)))

    def test_na_vespera_do_nonagesimo_dia_ainda_le(self):
        self.assertTrue(self.dentro(self._venceu_ha(89)))

    def test_passados_os_noventa_dias_fecha(self):
        self.assertFalse(self.dentro(self._venceu_ha(91)))

    def test_sem_data_de_fim_a_janela_NAO_abre(self):
        """Nao saber quando terminou nao e motivo para liberar.

        Falhar fechado vale aqui igual a todo o resto: a janela tem de nascer
        de uma data apurada. Abrir porque o campo veio vazio seria supor a
        data, que e exatamente o que esta casa nao faz.
        """
        self.assertFalse(self.dentro(None))
        self.assertFalse(self.dentro({"status": "canceled"}))
        self.assertFalse(self.dentro({"current_period_end": None}))
        self.assertFalse(self.dentro({"current_period_end": "ontem de manha"}))
        self.assertFalse(self.dentro({"current_period_end": 1757635200}))

    def test_data_sem_fuso_e_lida_como_UTC_e_nao_descartada(self):
        """Coluna `timestamp` sem fuso nao pode virar recusa silenciosa."""
        ingenua = (datetime.now(timezone.utc) - timedelta(days=2)).replace(tzinfo=None)
        self.assertTrue(self.dentro({"current_period_end": ingenua}))

    def test_texto_ISO_com_Z_e_aceito(self):
        iso = (datetime.now(timezone.utc) - timedelta(days=3)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self.assertTrue(self.dentro({"current_period_end": iso}))


class AJanelaAbreSOAquiloQueJaFoiPago(unittest.TestCase):
    """O que a janela alcanca, e o que ela nao pode alcancar nunca."""

    LEITURA = {"organization.read", "reports.read"}
    JAMAIS = {
        "reports.write",
        "reports.update",
        "reports.delete",
        "audit.read",
    }

    @classmethod
    def setUpClass(cls):
        cls.conjunto = _constante("PERMISSOES_DE_GUARDA_DOCUMENTAL")

    def test_a_lista_e_exatamente_a_leitura_do_que_ja_existe(self):
        self.assertEqual(self.LEITURA, set(self.conjunto))

    def test_escrever_alterar_apagar_e_auditar_continuam_fechados(self):
        for acao in self.JAMAIS:
            with self.subTest(acao=acao):
                self.assertNotIn(acao, self.conjunto)

    def test_todo_nome_da_lista_E_um_pedido_que_o_portao_recebe(self):
        """A trava do vocabulario: comparar por IGUALDADE, nao por parecenca.

        Concessao de papel (`reports.read_all`) e acao pedida (`reports.read`)
        sao vocabularios diferentes que se parecem. Este teste confronta a
        lista com as acoes que as rotas de fato passam; nome que nao chega ao
        portao e codigo morto que nao abre janela nenhuma.
        """
        pedidas = set()
        for no in ast.walk(ARVORE):
            if isinstance(no, ast.Call) and getattr(no.func, "id", "") == "_authorize_tenant_request":
                if len(no.args) >= 2 and isinstance(no.args[1], ast.Constant):
                    pedidas.add(no.args[1].value)
        self.assertTrue(pedidas, "nenhuma chamada de _authorize_tenant_request lida")
        orfaos = sorted(set(self.conjunto) - pedidas)
        self.assertEqual(
            [],
            orfaos,
            "nome na janela que rota nenhuma pede (a janela nunca abriria): "
            + ", ".join(orfaos),
        )

    def test_os_DOIS_portoes_que_sabem_o_pedido_informam_pedido_e_verbo(self):
        """Um dos dois e facil de esquecer, e fecharia a janela em silencio.

        Sao DUAS funcoes diferentes, e nao duas chamadas na mesma: a leitura
        clinica passa por `_authorize_tenant_request`, e a leitura dos
        comprovantes de aceite passa por `_require_tenant_management_context`.
        Esqueceu uma, aquela metade da janela nunca abre — e o sintoma e o 402
        de sempre, sem erro nenhum apontando a causa.

        Conferido pelo parser, e nao por contagem de texto: a primeira versao
        deste teste contava ocorrencias num RECORTE e reprovou porque as duas
        chamadas nao moram na mesma funcao.
        """
        for nome in ("_authorize_tenant_request", "_require_tenant_management_context"):
            alvo = next(
                n for n in ARVORE.body
                if isinstance(n, ast.FunctionDef) and n.name == nome
            )
            chamadas = [
                no for no in ast.walk(alvo)
                if isinstance(no, ast.Call)
                and getattr(no.func, "id", "") == "_require_active_subscription_for_context"
            ]
            with self.subTest(portao=nome):
                self.assertEqual(1, len(chamadas), "numero de chamadas mudou")
                argumentos = [ast.unparse(a) for a in chamadas[0].args]
                self.assertEqual(
                    ["context", "permission", "request.method"], argumentos
                )

    def test_a_janela_exige_o_VERBO_de_leitura_e_nao_so_o_nome(self):
        """Sem o verbo, "somente leitura" seria coincidencia de vocabulario.

        `organization.read` tambem chega ao portao vindo de
        `renew_organization_legal_acceptances`, que e um POST que GRAVA aceite.
        Exigir GET faz a promessa de leitura ser verdade por construcao.
        """
        alvo = next(
            n for n in ARVORE.body
            if isinstance(n, ast.FunctionDef)
            and n.name == "_require_active_subscription_for_context"
        )
        condicoes = [
            ast.unparse(no.test) for no in ast.walk(alvo)
            if isinstance(no, ast.If)
            and "PERMISSOES_DE_GUARDA_DOCUMENTAL" in ast.unparse(no.test)
        ]
        self.assertEqual(1, len(condicoes), "a janela deixou de ser um `if` unico")
        self.assertIn("metodo == 'GET'", condicoes[0])

    def test_os_portoes_que_nao_sabem_o_pedido_continuam_fechando(self):
        """Feature profissional, websocket e evento de auditoria do cliente.

        Nenhum dos tres informa permissao, entao caem no default vazio e
        recusam como sempre recusaram. Sessao, transcricao, insights, agenda e
        o FROID Explica ficam de fora da janela por causa disto — e nao por uma
        lista propria que alguem teria de lembrar de manter.
        """
        fora = BACKEND.count("_require_active_subscription_for_context(context)")
        self.assertEqual(3, fora, "numero de portoes cegos mudou; confira quais")
        for portao in (
            "def _require_professional_feature_access",
            "def _require_professional_websocket_access",
        ):
            with self.subTest(portao=portao):
                i = BACKEND.index(portao)
                self.assertIn(
                    "_require_active_subscription_for_context(context)",
                    BACKEND[i : i + 1400],
                )


if __name__ == "__main__":
    unittest.main()
