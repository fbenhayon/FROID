"""Uma conta, dois produtos — e a fronteira intacta no meio.

Ate 09/09/2026 um e-mail valia UM produto. A travessia clinico<->empresa era
recusada com 409, e a recusa estava certa: empresa NR-1 e clinica com o MESMO
CNPJ resolvem para o MESMO organization_id, o upsert faz ON CONFLICT DO UPDATE
do organization_type, e converter devolve `patients.read_all` e
`reports.read_all` aos papeis do lado do empregador sobre a empresa inteira.

Decisao do dono ao entrar a fase operacional: quem completar o cadastro acessa
os dois servicos. O que mudou NAO foi a fronteira — foi o mecanismo. O segundo
produto e uma SEGUNDA organizacao, e a conversao continua recusada pela trava
que `test_account_type_boundary` guarda e que nao foi tocada.

Este arquivo cobre o que a mudanca acrescentou, e sobretudo o que ela NAO pode
ter acrescentado:

    o segundo cadastro produz outra organizacao          (nunca converte a 1a)
    o dado clinico fica na organizacao CLINICA           (nunca na enterprise)
    a prontidao e por produto                            (uma regua para cada)
    acrescentar nao reescreve o cadastro que ja existia
"""

import ast
import sys
import typing
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from subscriptions import PAID_SESSION_STATUSES  # noqa: E402
from tenant_access import (  # noqa: E402
    CLINICAL_IDENTIFIED_PERMISSIONS,
    EMPLOYER_SIDE_ROLES,
    effective_role_permissions,
)
from tenant_store import (  # noqa: E402
    organization_id_for_profile,
    organization_type_for_account,
    profile_views,
)

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
ARVORE = ast.parse(MAIN)
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")


def _funcao(nome, ns):
    alvo = next(
        n for n in ARVORE.body if isinstance(n, ast.FunctionDef) and n.name == nome
    )
    exec(ast.get_source_segment(MAIN, alvo), ns)  # noqa: S102
    return ns[nome]


PERFIS: dict = {}
NS = {
    "Any": typing.Any,
    "Optional": typing.Optional,
    "PROFESSIONAL_PROFILES": PERFIS,
    "PAID_SESSION_STATUSES": PAID_SESSION_STATUSES,
    "FROID_MAX_PENDING_SETTLEMENTS": 10,
    "FROID_TRIAL_CONTACT_EMAIL": "froid@froid.com.br",
    "FROID_TRIAL_TIERS": ((100, 20), (100, 10)),
    "FROID_TRIAL_SESSIONS": 10,
    "LOGGER": type("L", (), {"warning": lambda *a, **k: None})(),
    "_is_admin_email": lambda email: False,
}
NS["_local_digits_only"] = _funcao("_local_digits_only", NS)
NS["_local_int"] = _funcao("_local_int", NS)
NS["_normalize_email"] = _funcao("_normalize_email", NS)
NS["_cadastro_clinico"] = _funcao("_cadastro_clinico", NS)
NS["_tipos_de_cadastro"] = _funcao("_tipos_de_cadastro", NS)
NS["_documento_da_empresa_nr1"] = _funcao("_documento_da_empresa_nr1", NS)
NS["_trial_state"] = _funcao("_trial_state", NS)
tipos_de_cadastro = NS["_tipos_de_cadastro"]
documento_nr1 = NS["_documento_da_empresa_nr1"]
estado_de_acesso = _funcao("_professional_access_status", NS)

CNPJ_CLINICA = "11222333000181"
CNPJ_EMPRESA = "99888777000166"


def clinica_com_nr1(**campos):
    """Uma clinica que contratou a avaliacao NR-1 da empresa de um cliente."""
    base = {
        "account_type": "organization",
        "organization_document": CNPJ_CLINICA,
        "lgpd_acknowledged": True,
        "selected_plan": "pro_10",
        "profile_fields": {"legalRepresentativeCpf": "12345678901"},
        "payment_status": "paid",
        "total_sessions": 10,
        "used_sessions": 0,
        "second_account": {
            "account_type": "nr1_company",
            "organization_name": "Cliente S.A.",
            "organization_document": CNPJ_EMPRESA,
        },
    }
    base.update(campos)
    return base


def empresa_com_psique(**campos):
    """Uma empresa NR-1 que acrescentou o consultorio proprio."""
    base = {
        "account_type": "nr1_company",
        "organization_document": CNPJ_EMPRESA,
        "lgpd_acknowledged": True,
        "profile_fields": {"cpf": "98765432100"},
        "selected_plan": "trial-froid",
        "payment_status": "trialing",
        "total_sessions": 20,
        "used_sessions": 0,
        "trial_sessions": 20,
        "second_account": {"account_type": "individual", "organization_document": ""},
    }
    base.update(campos)
    return base


class OsDoisCadastrosQueAContaCarrega(unittest.TestCase):
    def test_conta_de_um_produto_so_devolve_um_tipo(self):
        self.assertEqual(tipos_de_cadastro({"account_type": "individual"}), ["individual"])
        self.assertEqual(
            tipos_de_cadastro({"account_type": "nr1_company"}), ["nr1_company"]
        )

    def test_o_primario_vem_primeiro(self):
        self.assertEqual(
            tipos_de_cadastro(clinica_com_nr1()), ["organization", "nr1_company"]
        )
        self.assertEqual(
            tipos_de_cadastro(empresa_com_psique()), ["nr1_company", "individual"]
        )

    def test_segundo_cadastro_invalido_e_ignorado(self):
        # Valor que nenhum caminho de escrita produz nao pode virar um produto.
        for lixo in ({}, {"account_type": ""}, {"account_type": "xpto"}, "texto", 7):
            self.assertEqual(
                tipos_de_cadastro({"account_type": "individual", "second_account": lixo}),
                ["individual"],
            )

    def test_perfil_ausente_nao_carrega_produto_nenhum(self):
        self.assertEqual(tipos_de_cadastro(None), [])
        self.assertEqual(tipos_de_cadastro("texto"), [])

    def test_o_cnpj_da_avaliacao_sai_do_lado_certo(self):
        """Uma fonte so para o documento que responde pela avaliacao.

        Quem confere a prontidao do NR-1 e quem provisiona a organizacao
        precisam da mesma resposta. Ler `organization_document` do perfil
        devolveria o CNPJ da CLINICA para uma conta cujo NR-1 e o segundo
        cadastro — e a avaliacao seria arquivada sob a empresa errada.
        """
        self.assertEqual(documento_nr1(clinica_com_nr1()), CNPJ_EMPRESA)
        self.assertEqual(documento_nr1(empresa_com_psique()), CNPJ_EMPRESA)
        self.assertEqual(documento_nr1({"account_type": "individual"}), "")


class ASegundaOrganizacaoENuncaAPrimeiraConvertida(unittest.TestCase):
    """O ponto em que a fronteira poderia ter sido perdida."""

    def test_o_cadastro_produz_duas_vistas(self):
        vistas = profile_views(clinica_com_nr1())
        self.assertEqual(len(vistas), 2)
        self.assertEqual(vistas[0]["account_type"], "organization")
        self.assertEqual(vistas[1]["account_type"], "nr1_company")

    def test_um_produto_so_continua_produzindo_uma(self):
        self.assertEqual(len(profile_views({"account_type": "individual"})), 1)

    def test_as_duas_vistas_resolvem_para_organizacoes_DIFERENTES(self):
        """A garantia central. Se colidissem, a segunda reescreveria a primeira.

        `organization_id_for_profile` faz empresa NR-1 e clinica com o mesmo
        CNPJ resolverem para o mesmo id — e o upsert faz ON CONFLICT DO UPDATE
        do organization_type. Duas vistas colidindo nao criariam um segundo
        cadastro: converteriam o unico que existe.
        """
        for perfil in (clinica_com_nr1(), empresa_com_psique()):
            vistas = profile_views(perfil)
            ids = {
                organization_id_for_profile(
                    "dono@exemplo.com",
                    vista["account_type"],
                    vista.get("organization_document"),
                )
                for vista in vistas
            }
            self.assertEqual(len(ids), 2, f"as duas vistas colidiram: {perfil}")

    def test_os_tipos_das_duas_ficam_em_lados_opostos_da_fronteira(self):
        for perfil in (clinica_com_nr1(), empresa_com_psique()):
            tipos = {
                organization_type_for_account(vista["account_type"])
                for vista in profile_views(perfil)
            }
            self.assertEqual(
                {"enterprise"} & tipos, {"enterprise"}, "faltou a organizacao da empresa"
            )
            self.assertTrue(tipos - {"enterprise"}, "faltou a organizacao clinica")

    def test_o_consultorio_proprio_da_empresa_deriva_do_EMAIL(self):
        """E nao do CNPJ da empresa — senao seria a mesma organizacao.

        `organization_document` vazio na vista do segundo cadastro clinico e
        deliberado: sem CNPJ o id sai do e-mail e produz a organizacao 'solo' do
        proprio profissional.
        """
        vistas = profile_views(empresa_com_psique())
        self.assertEqual(vistas[1]["organization_document"], "")
        proprio = organization_id_for_profile("dono@exemplo.com", "individual", "")
        outro = organization_id_for_profile("outro@exemplo.com", "individual", "")
        self.assertNotEqual(proprio, outro)

    def test_a_vista_do_segundo_nao_carrega_um_terceiro(self):
        # Sem isto, uma vista poderia gerar outra vista e o espelho entraria em
        # recursao silenciosa.
        vistas = profile_views(clinica_com_nr1())
        self.assertEqual(len(profile_views(vistas[1])), 1)

    def test_o_empregador_continua_sem_permissao_clinica(self):
        """A fronteira nao se move por a conta ter dois produtos.

        O estreitamento e do organization_type, e nao da pessoa: nos papeis do
        lado do empregador, dentro da organizacao 'enterprise', as permissoes
        clinicas identificadas continuam retiradas — mesmo que o titular tenha
        um consultorio proprio noutra organizacao.
        """
        for papel in sorted(EMPLOYER_SIDE_ROLES):
            self.assertFalse(
                effective_role_permissions(papel, "enterprise")
                & CLINICAL_IDENTIFIED_PERMISSIONS,
                f"{papel} manteve permissao clinica numa organizacao enterprise",
            )


class OEspelhoProvisionaAsDuas(unittest.TestCase):
    """Sem isto o segundo produto ficaria no perfil e em lugar nenhum.

    O padrao de defeito mais frequente desta casa: a peca existe, esta correta,
    e nada a consome. Exercitar `_sync` exige PostgreSQL; o que se afirma aqui e
    a ligacao — que ela e chamada por VISTA, e que o ref do titular fica na
    organizacao clinica.
    """

    def test_provisiona_por_vista_e_nao_por_perfil(self):
        trecho = STORE[STORE.index("owner_refs = {}") : STORE.index("scoped_refs")]
        self.assertIn("profile_views(profile)", trecho)
        self.assertIn("for vista in vistas", trecho)

    def test_o_dado_clinico_e_escopado_pela_organizacao_clinica(self):
        """Se o ref do titular apontasse para a 'enterprise', prontuario,
        paciente e convite seriam gravados dentro da organizacao do
        empregador — que e exatamente o que nao pode existir."""
        trecho = STORE[STORE.index("owner_refs = {}") : STORE.index("scoped_refs")]
        self.assertIn('!= "enterprise"', trecho)
        self.assertIn("organization_type_for_account(vista.get(", trecho)


class ProntidaoEPorProduto(unittest.TestCase):
    def setUp(self):
        PERFIS.clear()

    def test_a_clinica_pronta_no_nr1_antes_de_comprar_pacote(self):
        """A regua trocada, agora dentro de uma conta so.

        Com um `access_ready` unico, a clinica que contratou o NR-1 e ainda nao
        comprou sessao seria devolvida do painel de conformidade por falta de
        credito CLINICO.
        """
        PERFIS["clinica@x.com"] = clinica_com_nr1(
            selected_plan="", payment_status="not_started", total_sessions=0
        )
        estado = estado_de_acesso("clinica@x.com")
        self.assertTrue(estado["products"]["nr1"]["ready"])
        self.assertFalse(estado["products"]["clinical"]["ready"])
        self.assertFalse(estado["onboarding_required"])

    def test_a_empresa_com_psique_fica_pronta_nos_dois(self):
        PERFIS["rh@x.com"] = empresa_com_psique()
        estado = estado_de_acesso("rh@x.com")
        self.assertTrue(estado["products"]["nr1"]["ready"])
        self.assertTrue(estado["products"]["clinical"]["ready"])

    def test_conta_de_um_produto_so_nao_ganha_o_outro(self):
        PERFIS["so@clinico.com"] = {
            "account_type": "individual",
            "lgpd_acknowledged": True,
            "selected_plan": "pro_10",
            "profile_fields": {"cpf": "12345678901"},
            "payment_status": "paid",
            "total_sessions": 10,
        }
        estado = estado_de_acesso("so@clinico.com")
        self.assertTrue(estado["products"]["clinical"]["available"])
        self.assertFalse(estado["products"]["nr1"]["available"])
        self.assertFalse(estado["products"]["nr1"]["ready"])

    def test_saldo_zerado_fecha_o_clinico_e_NAO_a_conformidade(self):
        """Suspender a conformidade por saldo de consultorio deixaria a empresa
        sem o inventario que a fiscalizacao cobra dela."""
        PERFIS["clinica@x.com"] = clinica_com_nr1(
            total_sessions=10, used_sessions=10, pending_settlement_count=99
        )
        estado = estado_de_acesso("clinica@x.com")
        self.assertFalse(estado["products"]["clinical"]["ready"])
        self.assertTrue(estado["products"]["nr1"]["ready"])

    def test_suspensao_fecha_os_DOIS(self):
        # O corte administrativo e da conta, e nao de um produto.
        PERFIS["clinica@x.com"] = clinica_com_nr1(access_approval_status="suspended")
        estado = estado_de_acesso("clinica@x.com")
        self.assertFalse(estado["products"]["clinical"]["ready"])
        self.assertFalse(estado["products"]["nr1"]["ready"])
        self.assertTrue(estado["onboarding_required"])

    def test_a_chave_de_conferencia_acompanha_o_lado_clinico(self):
        # A empresa que acrescenta o Psique responde por CNPJ no NR-1 e por CPF
        # no consultorio; sem isto ela ficaria com `cpf_required` para sempre.
        PERFIS["rh@x.com"] = empresa_com_psique()
        self.assertFalse(estado_de_acesso("rh@x.com")["cpf_required"])
        PERFIS["rh2@x.com"] = empresa_com_psique(profile_fields={})
        self.assertTrue(estado_de_acesso("rh2@x.com")["cpf_required"])

    def test_a_tela_de_escolha_recebe_os_dois_tipos(self):
        PERFIS["clinica@x.com"] = clinica_com_nr1()
        self.assertEqual(
            estado_de_acesso("clinica@x.com")["account_types"],
            ["organization", "nr1_company"],
        )
        # E o primario continua sendo o que decide a casa da conta.
        self.assertEqual(estado_de_acesso("clinica@x.com")["account_type"], "organization")

    def test_sem_perfil_nao_ha_tipo_nenhum(self):
        self.assertEqual(estado_de_acesso("ninguem@x.com")["account_types"], [])


class AcrescentarNaoReescreve(unittest.TestCase):
    """O corpo que chega descreve a organizacao NOVA."""

    def setUp(self):
        self.montagem = MAIN[
            MAIN.index("def _perfil_com_segundo_produto(") : MAIN.index("    return perfil")
        ]

    def test_parte_do_cadastro_existente(self):
        self.assertIn("perfil = dict(existing)", self.montagem)

    def test_nao_toca_no_tipo_do_cadastro_primario(self):
        # Tocar aqui faria a organizacao primaria mudar de tipo no espelho, e a
        # trava da travessia viraria decoracao: o perigo entraria por dentro.
        self.assertNotIn('perfil["account_type"]', self.montagem)

    def test_nao_toca_no_nome_nem_no_documento_do_cadastro_primario(self):
        # A empresa manda razao social e responsavel; a clinica, CPF e conselho.
        # Aplicar um por cima do outro trocaria o nome que sai no relatorio.
        for campo in (
            'perfil["owner_name"]',
            'perfil["phone"]',
            'perfil["document"]',
            'perfil["organization_name"]',
            'perfil["organization_document"]',
        ):
            with self.subTest(campo=campo):
                self.assertNotIn(campo, self.montagem)

    def test_os_aceites_se_somam_e_nao_se_substituem(self):
        # O contrato do NR-1 nao revoga o do Psique.
        self.assertIn("**(anteriores if isinstance(anteriores, dict) else {})", self.montagem)

    def test_a_data_de_criacao_do_segundo_cadastro_e_preservada(self):
        self.assertIn('str(anterior.get("created_at") or now)', self.montagem)

    def test_a_resposta_devolve_a_organizacao_do_produto_gravado(self):
        """`contextos[0]` deixou de ser a resposta certa.

        O cadastro guiado da empresa monta a chamada seguinte como
        /api/organizations/<id>/nr1/units. Receber ali o id da CLINICA
        devolveria 409 sobre um cadastro que acabou de ser aceito.
        """
        inicio = MAIN.index("contextos = _tenant_contexts_for_email(owner_email)")
        trecho = MAIN[inicio : MAIN.index('"status": "ok"', inicio)]
        self.assertIn("quer_enterprise", trecho)
        # Normalizado: a condicao ocupa duas linhas, e afirmar o recuo faria o
        # teste reprovar numa reformatacao sem que nada tivesse mudado.
        corrida = " ".join(trecho.split())
        self.assertIn('== "enterprise") == quer_enterprise', corrida)


class AsPortasExistem(unittest.TestCase):
    """Peca construida sem quem a consuma e o defeito mais comum desta casa.

    O mecanismo inteiro seria inalcancavel se /access/produto continuasse
    fechado para conta concluida — era a unica tela que oferece o cadastro do
    segundo produto.
    """

    @classmethod
    def setUpClass(cls):
        d = ROOT / "froid-dashboard" / "src"
        cls.app = (d / "App.tsx").read_text(encoding="utf-8")
        cls.dashboard = (d / "pages" / "Dashboard.tsx").read_text(encoding="utf-8")
        cls.nr1 = (d / "pages" / "Nr1Dashboard.tsx").read_text(encoding="utf-8")

    def test_a_tela_de_escolha_abre_para_quem_pode_acrescentar(self):
        self.assertIn("!produtoQuePodeSerAcrescentado(user)", self.app)

    def test_o_painel_clinico_oferece_contratar_o_nr1(self):
        self.assertIn("Contratar NR-1", self.dashboard)
        self.assertIn('nav("/access/produto")', self.dashboard)

    def test_o_painel_nr1_oferece_acrescentar_o_psique(self):
        self.assertIn("Adicionar FROID Psique", self.nr1)
        self.assertIn('nav("/access/produto")', self.nr1)

    def test_a_porta_do_nr1_leva_a_organizacao_junto(self):
        """`nav("/nr1")` mudava so a URL.

        A organizacao ativa continuava sendo a clinica, e
        `_require_enterprise_context` devolve 409 para ela. Numa conta de um
        produto so isso nunca apareceu, porque a unica organizacao ja era a
        certa — e um defeito que so nasce quando a segunda existe.
        """
        self.assertIn("const abrirNr1 = async () =>", self.dashboard)
        self.assertIn("irParaContexto(empresa.organization_id", self.dashboard)
        self.assertIn("organizacoesNr1(user)", self.dashboard)

    def test_a_falha_da_troca_de_contexto_aparece_na_tela(self):
        # Navegar assim mesmo levaria a um painel NR-1 vazio, indistinguivel de
        # "esta empresa nao tem nada".
        self.assertIn("setErroContexto(erro)", self.dashboard)
        self.assertIn("{erroContexto}", self.dashboard)

    def test_a_porta_do_nr1_nao_depende_mais_do_tipo_primario(self):
        # Lia `account_type === "nr1_company"`, e a porta sumia justamente para
        # a clinica que acabara de contratar a avaliacao.
        self.assertNotIn(
            'String(user?.access_status?.account_type || "") === "nr1_company"',
            self.dashboard,
        )


if __name__ == "__main__":
    unittest.main()
