"""Os espelhos do Portao A nao podem divergir da fonte.

A decisao de liberar resultado e do SQL (froid_nr1_required_sample, migration
025). Mas tres superficies repetem a mesma aritmetica porque precisam avisar
ANTES de existir campanha ou de haver requisicao ao servidor:

  - nr1_compliance.required_sample      — para a API explicar a supressao
  - froid-site/diagnostico-nr1.html     — a calculadora publica de porte
  - froid-dashboard .../nr1-representatividade.ts — o cadastro da empresa

Espelho que diverge e pior que espelho ausente: o diagnostico publico prometia
resultado a partir de ~75 trabalhadores, numero de quando o unico portao era o
de anonimato. Com o portao de representatividade no ar, a mesma empresa de 150
pessoas recebia "liberado" da pagina e painel vazio do banco — exatamente o
contrario do que a pagina existe para fazer.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

REPO = SERVER_DIR.parent
DIAGNOSTICO = REPO / "froid-site" / "diagnostico-nr1.html"
ESPELHO_TS = REPO / "froid-dashboard" / "src" / "lib" / "nr1-representatividade.ts"
# Os espelhos traduzidos. Cada edicao carrega a propria copia dos cinco numeros,
# entao cada idioma e mais uma chance de o piso divergir em silencio. O glob e
# deliberado: idioma novo entra coberto, sem ninguem precisar lembrar.
TRADUCOES = sorted((REPO / "froid-site").glob("*/diagnostico-nr1.html"))

from nr1_compliance import (  # noqa: E402
    CENSUS_THRESHOLD,
    CONFIDENCE_Z,
    MARGIN_OF_ERROR,
    MIN_COHORT_CUT,
    MIN_COHORT_TOTAL,
)


def _numero(texto: str, padrao: str) -> float:
    achado = re.search(padrao, texto)
    if not achado:
        raise AssertionError(f"nao encontrei {padrao!r}")
    return float(achado.group(1))


class ParametrosDaCalculadoraPublica(unittest.TestCase):
    """froid-site/diagnostico-nr1.html espelha os cinco numeros."""

    @classmethod
    def setUpClass(cls):
        cls.html = DIAGNOSTICO.read_text(encoding="utf-8")

    def test_os_pisos_de_anonimato_conferem(self):
        self.assertEqual(
            _numero(self.html, r"var PISO_CAMPANHA = ([0-9.]+);"), MIN_COHORT_TOTAL
        )
        self.assertEqual(
            _numero(self.html, r"var PISO_RECORTE = ([0-9.]+);"), MIN_COHORT_CUT
        )

    def test_os_parametros_de_amostragem_conferem(self):
        self.assertEqual(
            _numero(self.html, r"var AMOSTRA_Z = ([0-9.]+);"), CONFIDENCE_Z
        )
        self.assertEqual(
            _numero(self.html, r"var AMOSTRA_MARGEM = ([0-9.]+);"), MARGIN_OF_ERROR
        )
        self.assertEqual(
            _numero(self.html, r"var AMOSTRA_CORTE_CENSO = ([0-9.]+);"),
            CENSUS_THRESHOLD,
        )

    def test_a_transicao_para_censo_e_decidida_antes_do_teto(self):
        """O defeito de oscilacao nao pode reaparecer na copia.

        Comparar contra a fracao de corte o inteiro ja arredondado fazia a
        exigencia oscilar em torno da fronteira. A calculadora tem de comparar
        o valor continuo, igual ao Python e ao SQL.
        """
        trecho = self.html[self.html.index("function amostraNecessaria") :]
        trecho = trecho[: trecho.index("function exigidoNaCampanha")]
        corte = trecho.index("AMOSTRA_CORTE_CENSO * pop")
        teto = trecho.index("Math.ceil")
        self.assertLess(corte, teto, "o teto nao pode preceder a decisao de censo")

    def test_a_pagina_nao_promete_porte_fixo(self):
        """Nenhum '75 trabalhadores' de volta.

        O numero depende do efetivo desde a migration 025; qualquer constante de
        porte na copy volta a mentir assim que a adesao esperada mudar.
        """
        self.assertNotRegex(self.html, r"7[05]\s*(trabalhadores|pessoas)")


class EspelhosTraduzidos(unittest.TestCase):
    """Ingles, espanhol e frances publicam a MESMA calculadora.

    As tres edicoes nasceram em 04/09/2026 copiando o HTML portugues inteiro,
    script incluido. Passaram a existir como espelho do piso sem que nenhum
    teste olhasse para elas — e o unico sinal foi a lista de cobertura acusando
    arquivo de fora, o que sozinho nao diz se o numero esta certo, so que
    ninguem verificou.

    Divergencia de numero entre idiomas e defeito. Diferenca de idioma nao e.
    """

    def test_existe_pelo_menos_um_espelho_traduzido(self):
        """Se o glob parar de achar, o resto desta classe passa por vacuidade —
        que e a forma mais silenciosa de um teste deixar de proteger."""
        self.assertTrue(TRADUCOES, "nenhuma traducao de diagnostico-nr1.html")

    def test_cada_idioma_repete_os_cinco_numeros_da_fonte(self):
        for caminho in TRADUCOES:
            html = caminho.read_text(encoding="utf-8")
            with self.subTest(idioma=caminho.parent.name):
                self.assertEqual(
                    _numero(html, r"var PISO_CAMPANHA = ([0-9.]+);"), MIN_COHORT_TOTAL
                )
                self.assertEqual(
                    _numero(html, r"var PISO_RECORTE = ([0-9.]+);"), MIN_COHORT_CUT
                )
                self.assertEqual(
                    _numero(html, r"var AMOSTRA_Z = ([0-9.]+);"), CONFIDENCE_Z
                )
                self.assertEqual(
                    _numero(html, r"var AMOSTRA_MARGEM = ([0-9.]+);"), MARGIN_OF_ERROR
                )
                self.assertEqual(
                    _numero(html, r"var AMOSTRA_CORTE_CENSO = ([0-9.]+);"),
                    CENSUS_THRESHOLD,
                )

    def test_a_decisao_de_censo_precede_o_teto_em_cada_idioma(self):
        """O defeito de oscilacao foi corrigido uma vez, no portugues. A copia
        podia ter sido feita de uma versao anterior a correcao."""
        for caminho in TRADUCOES:
            html = caminho.read_text(encoding="utf-8")
            with self.subTest(idioma=caminho.parent.name):
                trecho = html[html.index("function amostraNecessaria") :]
                trecho = trecho[: trecho.index("function exigidoNaCampanha")]
                self.assertLess(
                    trecho.index("AMOSTRA_CORTE_CENSO * pop"),
                    trecho.index("Math.ceil"),
                    "o teto nao pode preceder a decisao de censo",
                )


class EspelhoDoPainel(unittest.TestCase):
    """froid-dashboard/src/lib/nr1-representatividade.ts espelha os mesmos."""

    @classmethod
    def setUpClass(cls):
        cls.ts = ESPELHO_TS.read_text(encoding="utf-8")

    def test_os_cinco_numeros_conferem(self):
        self.assertEqual(
            _numero(self.ts, r"PISO_CAMPANHA = ([0-9.]+);"), MIN_COHORT_TOTAL
        )
        self.assertEqual(
            _numero(self.ts, r"PISO_RECORTE = ([0-9.]+);"), MIN_COHORT_CUT
        )
        self.assertEqual(_numero(self.ts, r"AMOSTRA_Z = ([0-9.]+);"), CONFIDENCE_Z)
        self.assertEqual(
            _numero(self.ts, r"AMOSTRA_MARGEM = ([0-9.]+);"), MARGIN_OF_ERROR
        )
        self.assertEqual(
            _numero(self.ts, r"AMOSTRA_CORTE_CENSO = ([0-9.]+);"), CENSUS_THRESHOLD
        )

    def test_efetivo_nao_declarado_devolve_nulo(self):
        """Zero seria o atalho para desligar o portao, aqui como no SQL."""
        self.assertIn("return null", self.ts)
        self.assertRegex(self.ts, r"populacao\s*<=\s*0.*\n?.*return null")


class NenhumEspelhoFicouDeFora(unittest.TestCase):
    """O quarto espelho existia e este arquivo nao olhava para ele.

    tools/simulador_nr1.py carregava a propria copia do piso de campanha e
    sobreviveu a migration 027 sem quebrar teste nenhum — ou seja, teria posto
    o numero antigo numa planilha de PROPOSTA COMERCIAL, que e o pior lugar
    possivel para um numero desatualizado sair.

    A correcao foi fazer o simulador importar de nr1_compliance. Este teste
    guarda os dois lados: que ele importa, e que ninguem reintroduza uma copia.
    """

    def test_o_simulador_importa_os_pisos_em_vez_de_copia_los(self):
        fonte = (SERVER_DIR / "tools" / "simulador_nr1.py").read_text(encoding="utf-8")
        self.assertIn(
            "from nr1_compliance import MIN_COHORT_CUT, MIN_COHORT_TOTAL", fonte
        )
        self.assertIn("PISO_CAMPANHA = MIN_COHORT_TOTAL", fonte)
        self.assertIn("PISO_RECORTE = MIN_COHORT_CUT", fonte)
        self.assertNotRegex(fonte, r"PISO_CAMPANHA\s*=\s*\d")
        self.assertNotRegex(fonte, r"PISO_RECORTE\s*=\s*\d")

    def test_todo_espelho_conhecido_esta_coberto_por_este_arquivo(self):
        """Lista explicita, para a proxima copia ser uma decisao e nao um acaso.

        Quem criar um quinto espelho e nao o acrescentar aqui esta escolhendo
        deixa-lo divergir. O teste nao impede — nada impede — mas faz a escolha
        aparecer em vez de acontecer sozinha.
        """
        cobertos = {
            DIAGNOSTICO,
            ESPELHO_TS,
            SERVER_DIR / "tools" / "simulador_nr1.py",
            *TRADUCOES,
        }
        for caminho in cobertos:
            with self.subTest(espelho=caminho.name):
                self.assertTrue(caminho.exists(), f"{caminho} sumiu")

        suspeitos = set()
        for raiz, padrao in (
            (REPO / "froid-site", "*.html"),
            (REPO / "froid-dashboard" / "src", "*.ts"),
            (SERVER_DIR / "tools", "*.py"),
        ):
            for arquivo in raiz.rglob(padrao):
                texto = arquivo.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"PISO_CAMPANHA\s*=\s*\d", texto):
                    suspeitos.add(arquivo)
        self.assertEqual(
            suspeitos - cobertos,
            set(),
            "espelho do piso fora da lista coberta: "
            f"{[str(p) for p in suspeitos - cobertos]}",
        )


if __name__ == "__main__":
    unittest.main()
