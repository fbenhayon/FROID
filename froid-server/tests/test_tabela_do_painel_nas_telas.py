# -*- coding: utf-8 -*-
"""A tabela de metricas chega ao FROID Explica em TODAS as telas que a mostram.

07/09/2026. Lendo um relatorio de sessao encerrada, o profissional perguntou
"qual a utilidade desse marcador MFCC7". A resposta abriu com "O valor do MFCC7
nesta sessao nao foi enviado pelo painel" — verdade, e inutil: o numero estava
impresso na mesma tela, tres centimetros acima da caixa de pergunta.

A causa e o padrao 2.1 outra vez. So o `LiveSession` passava `getLiveContext`
ao `AIInsights`; as telas de relatorio e de paciente montam a mesma tabela, do
mesmo `MetricSnapshot`, e mandavam ao Explica tudo menos ela.

E a armadilha que vem junto: cada tela escreve o rotulo do seu jeito — `TOM`
contra `Tom`, `JITTER` contra `Jitter idx.`, `DELTA` contra `Delta 0.5-4Hz`. O
glossario do servidor casa por rotulo, entao um terceiro dialeto faria a busca
falhar em silencio e devolver de novo "nao foi enviado" sobre numero presente.
Por isso existe UM produtor (`lib/painel-para-o-explica.ts`) com os rotulos
canonicos, e este arquivo o confronta com a tabela que o `LiveSession`
renderiza.
"""

from __future__ import annotations

import io
import re
import sys
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

RAIZ = SERVIDOR.parent
LIVE_SESSION = RAIZ / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
PARA_O_EXPLICA = RAIZ / "froid-dashboard" / "src" / "lib" / "painel-para-o-explica.ts"
SESSION_REPORT = RAIZ / "froid-dashboard" / "src" / "pages" / "SessionReport.tsx"
PATIENT_DETAIL = RAIZ / "froid-dashboard" / "src" / "pages" / "PatientDetail.tsx"

import explica_clinico  # noqa: E402


def _ler(caminho: Path) -> str:
    with io.open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


PAINEL = _ler(LIVE_SESSION)
HELPER = _ler(PARA_O_EXPLICA)
RELATORIO = _ler(SESSION_REPORT)
FICHA_DO_PACIENTE = _ler(PATIENT_DETAIL)


def _bloco(fonte: str, abertura: str, fechamento: str) -> str:
    inicio = fonte.index(abertura)
    fim = fonte.index(fechamento, inicio)
    return fonte[inicio:fim]


def pares_da_tabela_ao_vivo() -> list[tuple[str, str, str]]:
    """(rotulo, campo do snapshot, casas decimais) da tabela do LiveSession."""
    bloco = _bloco(PAINEL, "const simplifiedMetricEntries", "\n  ];")
    return re.findall(
        r'\[\s*"([^"]+)",\s*formatMetricValue\(simplifiedSnapshot\.(\w+),\s*(\d+)\)\s*\]',
        bloco,
    )


def pares_do_helper() -> list[tuple[str, str, str]]:
    bloco = _bloco(HELPER, "export function metricasParaOExplica", "\n}")
    return re.findall(r'\[\s*"([^"]+)",\s*fmt\(snapshot\.(\w+),\s*(\d+)\)\s*\]', bloco)


class ATelaDeRelatorioTambemEnviaATabela(unittest.TestCase):
    """07/09/2026: lendo um relatorio fechado, a pergunta "qual a utilidade do
    MFCC7" foi respondida com "o valor nao foi enviado pelo painel" — sobre um
    numero impresso na mesma tela, tres centimetros acima.

    So o LiveSession passava `getLiveContext`. As telas de relatorio e de
    paciente montam a mesma tabela, do mesmo MetricSnapshot, e mandavam ao
    Explica tudo menos ela.
    """

    def test_o_relatorio_envia_a_tabela(self):
        self.assertIn("contextoDaTabela", RELATORIO)
        self.assertIn("painel-para-o-explica", RELATORIO)

    def test_a_ficha_do_paciente_envia_a_tabela(self):
        self.assertIn("contextoDaTabela", FICHA_DO_PACIENTE)
        self.assertIn("painel-para-o-explica", FICHA_DO_PACIENTE)

    def test_o_helper_fala_o_mesmo_dialeto_da_sessao_ao_vivo(self):
        """Cada tela escreve o rotulo do seu jeito, e o glossario casa por rotulo.

        `TOM` contra `Tom`, `JITTER` contra `Jitter idx.`, `DELTA` contra
        `Delta 0.5-4Hz`. Um terceiro dialeto faria a busca falhar em silencio e
        devolver "nao foi enviado" sobre um numero presente — o defeito que
        este arquivo inteiro existe para impedir.
        """
        ao_vivo = pares_da_tabela_ao_vivo()
        helper = pares_do_helper()
        self.assertTrue(ao_vivo, "a tabela do LiveSession mudou de forma")
        self.assertEqual(
            [(r, c) for r, _campo, c in ao_vivo],
            [(r, c) for r, _campo, c in helper],
            "rotulo ou casas decimais divergem entre a tela ao vivo e o helper",
        )

    def test_o_helper_le_os_mesmos_campos_do_snapshot(self):
        self.assertEqual(
            [campo for _r, campo, _c in pares_da_tabela_ao_vivo()],
            [campo for _r, campo, _c in pares_do_helper()],
        )

    def test_todo_rotulo_do_helper_tem_ficha(self):
        faltando = [
            rotulo
            for rotulo, _campo, _casas in pares_do_helper()
            if rotulo not in explica_clinico.INDICE_POR_ROTULO
        ]
        self.assertEqual(faltando, [])

    def test_o_helper_declara_de_que_recorte_sao_os_numeros(self):
        # Media da sessao inteira, media do ultimo relatorio e corte aberto sao
        # grandezas diferentes sob os mesmos rotulos.
        self.assertIn("panel_metrics_window", HELPER)
        self.assertIn("panel_metrics_window", PAINEL)

    def test_o_glossario_repete_o_recorte_declarado(self):
        texto = explica_clinico.glossario_do_painel(
            "MFCC7",
            {"panel_metrics": {"MFCC7": "1.234"}, "panel_metrics_window": "media da sessao inteira"},
        )
        self.assertIn("na tela: media da sessao inteira", texto)

    def test_recorte_nao_declarado_nao_vira_corte_atual(self):
        # Antes o texto afirmava "media do corte atual" para qualquer tela.
        texto = explica_clinico.glossario_do_painel("MFCC7", {"panel_metrics": {"MFCC7": "1.234"}})
        self.assertIn("recorte nao declarado", texto)
        self.assertNotIn("corte atual", texto)


if __name__ == "__main__":
    unittest.main()
