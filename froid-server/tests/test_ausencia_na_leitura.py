"""Gravar NULL nao basta: quem le precisa saber que o NULL existe.

O RISCO QUE ESTE ARQUIVO GUARDA
-------------------------------
Ate a v3 do acervo, ausencia de medida era gravada como `0.0` e entrava na
media puxando-a para baixo. Desde a v4 e NULL — o que e correto e, sozinho,
perigoso: `AVG()` ignora NULL em silencio.

Uma coorte de 100 sessoes das quais 30 nao tiveram voz medida responderia
`cohort_size = 100` com uma media calculada sobre 70, e NADA na resposta
acusaria. Seria trocar uma mentira (zero que ninguem mediu) por outra (media de
um subconjunto apresentada como media da coorte) — e a segunda e pior, porque
parece certa.

Os tres consumidores de leitura mapeados em 04/09/2026:
  C5  `_fallback_analytics_sql`   — toda media mostra o proprio N
  C6  instrucao de SQL ao modelo  — declara o NULL e proibe `coalesce(...,0)`
  C7  `_format_query_table`       — a celula vazia diz o que e
"""

import ast
import re
import sys
import types
import unittest
from pathlib import Path
from typing import List

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN_SRC = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
MAIN_TREE = ast.parse(MAIN_SRC)


def _fonte_da_funcao(nome: str) -> str:
    """Recorte pelo PARSER, por nome de definicao — nunca por janela de linhas."""
    for no in MAIN_TREE.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(MAIN_SRC, no) or ""
    raise AssertionError(f"nao achei a definicao de {nome}")


class TodaMediaMostraOProprioN(unittest.TestCase):
    """C5 — as consultas de queda do Data-FROID."""

    def setUp(self):
        self.fonte = _fonte_da_funcao("_fallback_analytics_sql")

    def test_cada_avg_tem_o_count_da_mesma_coluna(self):
        colunas_com_media = set(re.findall(r"AVG\((\w+)\)", self.fonte))
        self.assertTrue(colunas_com_media, "nenhum AVG encontrado — funcao mudou de forma")
        colunas_com_contagem = set(re.findall(r"COUNT\((\w+)\)", self.fonte))
        # `session_duration` e preenchida sempre (vem do relogio da sessao, nao
        # de apuracao acustica) e nao carrega NULL — nao precisa de N proprio.
        sem_contagem = colunas_com_media - colunas_com_contagem - {"session_duration"}
        self.assertEqual(
            set(),
            sem_contagem,
            "media sem N ao lado — AVG ignora NULL e o leitor nao ve o denominador: "
            + ", ".join(sorted(sem_contagem)),
        )

    def test_nenhuma_consulta_de_queda_reintroduz_zero(self):
        for proibido in ("coalesce(ipm", "coalesce(idm", "ifnull(", "IFNULL("):
            self.assertNotIn(proibido, self.fonte)


class OModeloERAvisadoDoNull(unittest.TestCase):
    """C6 — sem este paragrafo, o acervo honesto produz resposta desonesta."""

    def setUp(self):
        self.fonte = _fonte_da_funcao("_query_froid_analytics")

    def test_a_instrucao_declara_o_que_null_significa(self):
        self.assertIn("NULL significa NAO APURADO", self.fonte)

    def test_a_instrucao_exige_count_ao_lado_de_toda_media(self):
        self.assertIn("COUNT(<coluna>) AS n_<coluna>", self.fonte)

    def test_a_instrucao_proibe_reintroduzir_o_zero(self):
        self.assertIn("coalesce(<coluna de medida>, 0)", self.fonte)
        self.assertIn("Nunca use", self.fonte)

    def test_a_instrucao_separa_as_duas_eras_do_acervo(self):
        self.assertIn("anonymous_datamart_v4", self.fonte)
        self.assertIn("anonymous_datamart_v3", self.fonte)

    def test_o_narrador_e_avisado_de_que_celula_vazia_nao_e_zero(self):
        self.assertIn("nao as leia", self.fonte)
        self.assertIn("sem apuracao", self.fonte)


class ACelulaVaziaDizOQueE(unittest.TestCase):
    """C7 — `str(None)` imprimia o literal `None` para o modelo e para a tela."""

    def setUp(self):
        modulo = types.ModuleType("tabela")
        modulo.__dict__["List"] = List
        modulo.__dict__["SEM_APURACAO_NA_TABELA"] = "sem apuracao"
        exec(compile(_fonte_da_funcao("_format_query_table"), "<main.py>", "exec"), modulo.__dict__)
        self.formata = modulo.__dict__["_format_query_table"]

    def test_none_vira_sem_apuracao(self):
        saida = self.formata(["zona", "ipm_medio"], [(3, None)])
        self.assertIn("sem apuracao", saida)
        self.assertNotIn("None", saida)

    def test_zero_medido_continua_aparecendo_como_zero(self):
        saida = self.formata(["zona", "ipm_medio"], [(3, 0.0)])
        self.assertIn("0.0", saida)
        self.assertNotIn("sem apuracao", saida)

    def test_sem_linhas_continua_dizendo_que_nao_houve_linha(self):
        self.assertEqual("Sem linhas retornadas.", self.formata(["a"], []))


class OAcervoDeclaraAPropriaEra(unittest.TestCase):
    """Sem a versao, linhas com 0.0 e linhas com NULL convivem no mesmo AVG."""

    def test_a_gravacao_usa_a_versao_v4(self):
        self.assertIn('"anonymous_datamart_v4"', MAIN_SRC)

    def test_a_versao_antiga_nao_e_mais_gravada(self):
        gravacoes = re.findall(r'^\s*"anonymous_datamart_v3",\s*$', MAIN_SRC, re.MULTILINE)
        self.assertEqual([], gravacoes, "v3 ainda sendo gravada como schema_version")


if __name__ == "__main__":
    unittest.main()
