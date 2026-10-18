# -*- coding: utf-8 -*-
"""Um contrato por modo: ao vivo e curto, analise abre com a tabela.

Fase 3 (18/10/2026). O contrato de 200 palavras foi escrito para a sessao ao
vivo e proibia lista; o bloco de cortes mandava enumerar. Na pagina de
relatorio as duas instrucoes se contradiziam no mesmo prompt. Agora o painel
declara o modo, a instrucao traz o contrato do modo, e o teto de saida
acompanha. Decisao do dono (15/10/2026): dado primeiro, tamanho depois.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

import explica_clinico  # noqa: E402
import main  # noqa: E402

RAIZ = SERVIDOR.parent


def _corrido(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


class OContratoDependeDoModo(unittest.TestCase):
    def test_ao_vivo_continua_curto_e_e_o_padrao(self):
        instrucao = _corrido(explica_clinico.instrucao())
        self.assertIn("No maximo 200 palavras", instrucao)
        self.assertNotIn("MODO DE ANALISE", instrucao)

    def test_analise_abre_com_a_tabela_e_nao_tem_teto_fixo(self):
        instrucao = _corrido(explica_clinico.instrucao(modo=explica_clinico.MODO_DE_ANALISE))
        self.assertIn("MODO DE ANALISE", instrucao)
        self.assertIn("TABELA em markdown", instrucao)
        self.assertIn("SEM TETO FIXO DE PALAVRAS", instrucao)
        self.assertIn("nao recalcule", instrucao)
        self.assertNotIn("No maximo 200 palavras", instrucao)

    def test_o_resto_da_instrucao_e_o_mesmo_nos_dois_modos(self):
        ao_vivo = explica_clinico.instrucao()
        analise = explica_clinico.instrucao(modo=explica_clinico.MODO_DE_ANALISE)
        for bloco in (explica_clinico._REGRAS, explica_clinico._INTEGRACAO, explica_clinico._TRANSCRICAO):
            self.assertIn(bloco, ao_vivo)
            self.assertIn(bloco, analise)

    def test_modo_invalido_cai_no_curto(self):
        instrucao = _corrido(explica_clinico.instrucao(modo="qualquer"))
        self.assertIn("No maximo 200 palavras", instrucao)


class OModoVemDoPainel(unittest.TestCase):
    def test_declarado_vence(self):
        self.assertEqual(explica_clinico.modo_do_contexto({"explica_mode": "analise"}), "analise")
        self.assertEqual(
            explica_clinico.modo_do_contexto({"explica_mode": "ao_vivo", "panel_cuts": [{}]}),
            "ao_vivo",
        )

    def test_sem_declaracao_cortes_significam_analise(self):
        self.assertEqual(explica_clinico.modo_do_contexto({"panel_cuts": [{"corte": "x"}]}), "analise")

    def test_sem_declaracao_e_sem_cortes_e_ao_vivo(self):
        self.assertEqual(explica_clinico.modo_do_contexto({}), "ao_vivo")
        self.assertEqual(explica_clinico.modo_do_contexto(None), "ao_vivo")
        self.assertEqual(explica_clinico.modo_do_contexto({"explica_mode": "errado"}), "ao_vivo")


class OTetoAcompanhaOModo(unittest.TestCase):
    def test_teto_por_modo(self):
        self.assertEqual(main._modo_e_teto({"explica_mode": "analise"}), ("analise", main.FROID_EXPLICA_MAX_TOKENS_ANALISE))
        self.assertEqual(main._modo_e_teto({}), ("ao_vivo", main.FROID_EXPLICA_MAX_TOKENS))
        self.assertGreater(main.FROID_EXPLICA_MAX_TOKENS_ANALISE, main.FROID_EXPLICA_MAX_TOKENS)

    def test_o_padrao_do_compose_e_o_do_codigo(self):
        compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
        codigo = (SERVIDOR / "main.py").read_text(encoding="utf-8")
        no_compose = re.search(r"FROID_EXPLICA_MAX_TOKENS_ANALISE=\$\{FROID_EXPLICA_MAX_TOKENS_ANALISE:-(\d+)\}", compose)
        no_codigo = re.search(r'FROID_EXPLICA_MAX_TOKENS_ANALISE = int\(os\.getenv\("FROID_EXPLICA_MAX_TOKENS_ANALISE", "(\d+)"\)\)', codigo)
        self.assertIsNotNone(no_compose)
        self.assertIsNotNone(no_codigo)
        self.assertEqual(no_compose.group(1), no_codigo.group(1))


class AsTelasDeclaramOModo(unittest.TestCase):
    def _fonte(self, nome):
        return (RAIZ / "froid-dashboard" / "src" / nome).read_text(encoding="utf-8")

    def test_relatorio_e_ficha_declaram_analise(self):
        self.assertIn('explica_mode: "analise"', self._fonte("pages/SessionReport.tsx"))
        self.assertIn('explica_mode: "analise"', self._fonte("pages/PatientDetail.tsx"))

    def test_sessao_ao_vivo_declara_ao_vivo(self):
        self.assertIn('explica_mode: "ao_vivo"', self._fonte("pages/LiveSession.tsx"))

    def test_o_painel_desenha_a_tabela(self):
        self.assertIn("blocosDaResposta", self._fonte("components/panels/AIInsights.tsx"))


if __name__ == "__main__":
    unittest.main()
