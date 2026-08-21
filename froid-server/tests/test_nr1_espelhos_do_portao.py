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


if __name__ == "__main__":
    unittest.main()
