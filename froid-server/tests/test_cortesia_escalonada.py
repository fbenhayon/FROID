"""A promocao dos 100 primeiros: o numero anunciado e o numero concedido.

As paginas institucionais servidas dentro do /app/ — `home.html` e
`profissionais.html` — prometem "Primeiros 100 profissionais: 20 sessoes
gratuitas" e "Proximos 100 profissionais: 10 sessoes gratuitas" desde antes de
existir cortesia nenhuma no servidor. O servidor concedia 5 a todo mundo.

Nao era um numero divergente por descuido: era um rotulo prometendo o dobro do
que o produto entregava, na tela que convida o profissional a se cadastrar. E o
tipo de defeito que ninguem descobre pelo uso — quem recebe 5 nao sabe que lhe
foram prometidas 20.

Decisao do dono em 09/09/2026: cumprir o anuncio, e a promocao vale SO para
profissional autonomo e clinica. A empresa contratante do NR-1 nao compra sessao
nenhuma.

Este arquivo amarra as tres coisas que podem divergir em silencio:

  1. a tabela do servidor e o texto das duas paginas;
  2. o padrao do codigo e o padrao do docker-compose (quem manda de fato e o
     compose, porque ele ENVIA o valor e o os.getenv nunca decide);
  3. a concessao e a fila — vaga gravada, nunca recalculada, e empresa fora.
"""

import ast
import re
import sys
import typing
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

FONTE = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
ARVORE = ast.parse(FONTE)

INSTITUCIONAIS = (
    ROOT / "froid-dashboard" / "src" / "pages" / "institutional" / "home.html",
    ROOT / "froid-dashboard" / "src" / "pages" / "institutional" / "profissionais.html",
)


def _local_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _constante(nome):
    """Le uma atribuicao de modulo pelo parser, e nao por regex.

    Recorte por numero de linha ou por janela de caracteres ja quebrou duas
    vezes neste repositorio por crescimento de comentario.
    """
    for no in ARVORE.body:
        if isinstance(no, ast.Assign):
            alvos = [a.id for a in no.targets if isinstance(a, ast.Name)]
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            alvos = [no.target.id]
        else:
            continue
        if nome in alvos and no.value is not None:
            return ast.literal_eval(no.value)
    raise AssertionError(f"{nome} nao foi encontrada em main.py")


def _padrao_do_getenv(nome):
    """O segundo argumento de os.getenv(nome, PADRAO), como o codigo o escreve."""
    for no in ast.walk(ARVORE):
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "getenv"
            and no.args
            and isinstance(no.args[0], ast.Constant)
            and no.args[0].value == nome
            and len(no.args) > 1
            and isinstance(no.args[1], ast.Constant)
        ):
            return no.args[1].value
    raise AssertionError(f"os.getenv({nome!r}, padrao) nao foi encontrado")


def _funcao(nome, extras=None):
    """Extrai a funcao real de main.py e a executa isolada.

    Importar main exigiria fastapi e cryptography, ausentes do ambiente de
    teste. Extrair pela AST garante que o testado e o codigo que vai rodar.
    """
    alvo = next(
        n for n in ARVORE.body if isinstance(n, ast.FunctionDef) and n.name == nome
    )
    ns = {
        "Optional": typing.Optional,
        "_local_int": _local_int,
        "FROID_TRIAL_TIERS": _constante("FROID_TRIAL_TIERS"),
        "FROID_TRIAL_SESSIONS": int(_padrao_do_getenv("FROID_TRIAL_SESSIONS")),
    }
    ns.update(extras or {})
    exec(ast.get_source_segment(FONTE, alvo), ns)  # noqa: S102
    return ns[nome]


TIERS = _constante("FROID_TRIAL_TIERS")
BASE = int(_padrao_do_getenv("FROID_TRIAL_SESSIONS"))
cortesia_da_vaga = _funcao("_trial_sessions_for_position")
cadastro_clinico = _funcao("_cadastro_clinico")
tipos_de_cadastro = _funcao("_tipos_de_cadastro")


class ATabelaEAFonteDoNumero(unittest.TestCase):
    def test_a_base_subiu_de_cinco_para_dez(self):
        self.assertEqual(BASE, 10)

    def test_as_faixas_sao_as_anunciadas(self):
        self.assertEqual(tuple(tuple(t) for t in TIERS), ((100, 20), (100, 10)))

    def test_a_primeira_vaga_e_a_centesima_recebem_o_lote_maior(self):
        self.assertEqual(cortesia_da_vaga(1), 20)
        self.assertEqual(cortesia_da_vaga(100), 20)

    def test_a_centesima_primeira_ja_esta_na_faixa_seguinte(self):
        self.assertEqual(cortesia_da_vaga(101), 10)
        self.assertEqual(cortesia_da_vaga(200), 10)

    def test_fora_das_vagas_anunciadas_vale_a_base(self):
        self.assertEqual(cortesia_da_vaga(201), BASE)
        self.assertEqual(cortesia_da_vaga(5000), BASE)

    def test_vaga_ausente_ou_corrompida_nao_quebra(self):
        for entrada in (0, -3, None, "", "texto"):
            self.assertEqual(cortesia_da_vaga(entrada), 20)

    def test_a_chave_em_zero_desliga_o_programa_inteiro(self):
        """A tabela nao pode sobreviver a chave que desliga a cortesia.

        Se sobrevivesse, por a variavel em 0 continuaria concedendo 20 as 100
        primeiras vagas — uma chave que nao desliga e pior do que nenhuma.
        """
        desligado = _funcao(
            "_trial_sessions_for_position", extras={"FROID_TRIAL_SESSIONS": 0}
        )
        for vaga in (1, 100, 101, 201):
            self.assertEqual(desligado(vaga), 0)


class OTextoAnunciadoEOQueOServidorConcede(unittest.TestCase):
    """O espelho que custou o defeito: prosa comercial nao tem quem a confira.

    Nao basta o algarismo aparecer na pagina. O que se verifica e a FORMA DE
    AFIRMACAO — quando a pagina diz "primeiros N profissionais: M sessoes
    gratuitas", N e M tem de sair da tabela.
    """

    PADRAO = re.compile(
        r"(Primeiros|Próximos)\s+(\d+)\s+profissionais.*?(\d+)\s+sessões\s+gratuitas",
        re.S,
    )

    def test_as_paginas_existem_e_sao_servidas(self):
        # Se um dia deixarem de ser importadas, o teste passa a defender um
        # arquivo morto. InstitutionalStaticPage e quem as renderiza.
        pagina = (
            ROOT / "froid-dashboard" / "src" / "pages" / "InstitutionalStaticPage.tsx"
        ).read_text(encoding="utf-8")
        for arquivo in INSTITUCIONAIS:
            self.assertTrue(arquivo.exists(), arquivo)
            self.assertIn(f"institutional/{arquivo.name}", pagina)

    def test_cada_pagina_anuncia_exatamente_as_faixas_da_tabela(self):
        esperado = [(str(vagas), str(sessoes)) for vagas, sessoes in TIERS]
        for arquivo in INSTITUCIONAIS:
            texto = arquivo.read_text(encoding="utf-8")
            achados = [
                (vagas, sessoes)
                for _, vagas, sessoes in self.PADRAO.findall(texto)
            ]
            self.assertTrue(
                achados,
                f"{arquivo.name} nao anuncia mais o programa — se ele foi "
                "retirado de proposito, retire tambem este teste",
            )
            self.assertEqual(
                achados,
                esperado,
                f"{arquivo.name} anuncia {achados}, a tabela do servidor diz "
                f"{esperado}",
            )


class OPadraoDoCodigoEODoCompose(unittest.TestCase):
    def test_compose_encaminha_a_chave_ao_contentor(self):
        """Sem a linha, a chave no .env do servidor nao chega ao backend.

        O froid-backend recebe lista explicita em `environment:`, e nao
        env_file. Ja custou uma sessao inteira com FROID_DATAMART_FALA_PROFISSIONAL.
        """
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn(
            "FROID_TRIAL_SESSIONS=${FROID_TRIAL_SESSIONS:-", compose
        )

    def test_os_dois_padroes_sao_o_mesmo_numero(self):
        """Divergir aqui faz o valor do codigo virar decoracao.

        Com a variavel ausente do .env o compose ENVIA o padrao dele, e o
        os.getenv de main.py nunca decide nada.
        """
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        achado = re.search(
            r"FROID_TRIAL_SESSIONS=\$\{FROID_TRIAL_SESSIONS:-(\d+)\}", compose
        )
        self.assertIsNotNone(achado, "padrao do compose nao encontrado")
        self.assertEqual(int(achado.group(1)), BASE)


class AEmpresaNr1FicaForaDaCortesia(unittest.TestCase):
    def test_a_funcao_separa_quem_consome_sessao(self):
        self.assertTrue(cadastro_clinico("individual"))
        self.assertTrue(cadastro_clinico("organization"))
        self.assertTrue(cadastro_clinico(None))
        self.assertFalse(cadastro_clinico("nr1_company"))
        self.assertFalse(cadastro_clinico("NR1_Company"))

    def test_a_concessao_exige_cadastro_clinico(self):
        inicio = FONTE.index("conceder_cortesia = ")
        # Ate o fim da atribuicao, e nao ate o fim da linha: a condicao ocupa
        # varias linhas, e recortar por "\n" leria so o parentese.
        expressao = FONTE[inicio : FONTE.index("\n    if conceder_cortesia:", inicio)]
        self.assertIn("FROID_TRIAL_SESSIONS > 0", expressao)
        self.assertIn("_cadastro_clinico(account_type)", expressao)
        # Era `not existing` — "so na criacao do perfil". Deixou de bastar em
        # 09/09/2026, quando a empresa NR-1 passou a poder acrescentar o Psique:
        # para ela o perfil JA existe, e a regra antiga a deixaria com o painel
        # clinico aberto e zero sessao, sem nunca ter recebido a cortesia. A
        # regra sempre foi "a primeira vez que a conta ganha o lado clinico".
        self.assertIn("not ja_tinha_lado_clinico", expressao)

    def test_a_cortesia_continua_valendo_uma_vez_so(self):
        """A garantia que a condicao antiga protegia, dita pelo que a sustenta.

        `ja_tinha_lado_clinico` le os tipos que a conta JA carrega. Nao existe
        caminho que retire o lado clinico de uma conta, entao uma vez concedida
        a cortesia a condicao nunca volta a ser verdadeira — regravar o cadastro
        continua nao renovando nada.
        """
        inicio = FONTE.index("ja_tinha_lado_clinico = ")
        linha = FONTE[inicio : FONTE.index("\n", inicio)]
        self.assertIn("_tipos_de_cadastro(existing)", FONTE)
        self.assertIn("_cadastro_clinico(t)", linha)
        self.assertIn(
            'total_sessions = max(0, _local_int(existing.get("total_sessions")))',
            FONTE,
        )

    def test_a_empresa_nao_entra_no_plano_de_cortesia_nem_em_trialing(self):
        """selected_plan e payment_status dependem de conceder_cortesia.

        Com a empresa fora da concessao, ela deixa de nascer com
        `selected_plan='trial-froid'` e `payment_status='trialing'` — que era o
        que punha "Saldo: 5 sessoes" no painel de quem nao compra sessao.
        """
        for campo in ('"selected_plan": (', '"payment_status": ('):
            inicio = FONTE.index(campo)
            trecho = FONTE[inicio : FONTE.index("),\n", inicio)]
            self.assertIn("conceder_cortesia", trecho)


class AFilaNaoAndaParaTras(unittest.TestCase):
    def _fila(self, perfis):
        proxima = _funcao(
            "_next_trial_position",
            extras={
                "PROFESSIONAL_PROFILES": perfis,
                "_cadastro_clinico": cadastro_clinico,
                "_tipos_de_cadastro": tipos_de_cadastro,
            },
        )
        return proxima()

    def test_base_vazia_comeca_na_primeira_vaga(self):
        self.assertEqual(self._fila({}), 1)

    def test_cadastros_anteriores_ao_programa_ocupam_as_vagas_que_ocuparam(self):
        """"Os 100 primeiros" sao os primeiros da plataforma.

        Quem se cadastrou antes desta mudanca nao ganha credito retroativo — mas
        tambem nao deixa de contar, senao a vaga 1 seria dada a alguem que e o
        trigesimo profissional a entrar.
        """
        perfis = {f"p{i}@x.com": {"account_type": "individual"} for i in range(30)}
        self.assertEqual(self._fila(perfis), 31)

    def test_a_empresa_que_acrescentou_o_psique_OCUPA_a_vaga(self):
        """Ela recebe a cortesia, entao tem de ocupar a vaga.

        A fila lia so `account_type`. Uma conta cujo lado clinico e o SEGUNDO
        cadastro recebia o lote, gravava a vaga — e ficava invisivel aqui, de
        modo que o profissional seguinte receberia o MESMO numero. Duas contas
        na mesma vaga tornam a promocao inauditavel, que e a unica coisa que a
        vaga existe para garantir.
        """
        perfis = {
            "a@x.com": {"account_type": "individual", "trial_position": 1},
            "rh@empresa.com": {
                "account_type": "nr1_company",
                "trial_position": 2,
                "second_account": {"account_type": "individual"},
            },
        }
        self.assertEqual(self._fila(perfis), 3)

    def test_empresa_nr1_sem_psique_nao_ocupa_vaga(self):
        perfis = {
            "a@x.com": {"account_type": "individual"},
            "rh@empresa.com": {"account_type": "nr1_company"},
            "rh2@empresa.com": {"account_type": "nr1_company"},
        }
        self.assertEqual(self._fila(perfis), 2)

    def test_perfil_removido_nao_devolve_a_vaga(self):
        """Duas pessoas nunca recebem o mesmo numero.

        Se a fila fosse so contagem, apagar um cadastro faria a proxima pessoa
        repetir a vaga de alguem — e a auditoria da promocao passaria a ter dois
        donos para a mesma posicao.
        """
        perfis = {"unico@x.com": {"account_type": "individual", "trial_position": 87}}
        self.assertEqual(self._fila(perfis), 88)

    def test_entrada_corrompida_nao_quebra_a_fila(self):
        perfis = {
            "a@x.com": None,
            "b@x.com": "texto",
            "c@x.com": {"account_type": "individual", "trial_position": "abc"},
        }
        self.assertEqual(self._fila(perfis), 2)


class OAvisoDizOLoteDaConta(unittest.TestCase):
    """Com lotes diferentes, ler a constante do modulo passou a ser mentira."""

    def _corpo(self, nome):
        alvo = next(
            n for n in ARVORE.body if isinstance(n, ast.FunctionDef) and n.name == nome
        )
        return ast.get_source_segment(FONTE, alvo)

    def test_a_mensagem_le_o_perfil_e_nao_a_constante(self):
        corpo = self._corpo("_trial_block_detail")
        self.assertIn("_trial_state(", corpo)
        self.assertNotIn("FROID_TRIAL_SESSIONS", corpo)

    def test_sem_lote_conhecido_a_frase_sai_sem_numero(self):
        # Preencher com o padrao seria afirmar uma concessao nao apurada.
        corpo = self._corpo("_trial_block_detail")
        self.assertIn('"As sessões"', corpo)

    def test_os_dois_chamadores_passam_o_email(self):
        self.assertEqual(FONTE.count("_trial_block_detail()"), 0)
        self.assertEqual(FONTE.count("_trial_block_detail("), 3)


if __name__ == "__main__":
    unittest.main()
