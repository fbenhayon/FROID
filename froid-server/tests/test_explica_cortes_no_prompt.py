# -*- coding: utf-8 -*-
"""Os cortes chegam ao FROID Explica, e o que nao chega se declara.

15/10/2026, sessao froid-mv85lqul447x, pagina de relatorio. O profissional
pediu "o valor das palavras por minuto por corte e os percentuais de
variacao". O relatorio tinha oito cortes arquivados, cada um com IPM, IDM,
P/MIN e F0. A resposta foi "nao ha dados de cortes especificos disponiveis
nesta sessao".

Medido dentro do conteiner de producao: a pagina mandava 105.243 caracteres de
JSON; `_format_session_context` guardava os primeiros 5.000, sem marcador. O
corte caia dentro da linha de base. `report_session_average` comecava no
caractere 7.315 e `report_ten_minute_cuts` no 11.631 — nenhum dos dois chegou
ao modelo uma unica vez. E em seis respostas o assistente mandou "reouvir o
trecho", sobre um produto que nao grava audio.

Tres garantias, cada uma com o seu caso:

1. os cortes entram no prompt numa secao propria, compactos, com o desvio
   contra a linha de base calculado pelo servidor (a regra 3 proibe o modelo
   de calcular, e esta certa);
2. todo truncamento — do JSON, da transcricao, da carteira, do resumo de um
   corte, do excedente de cortes — DECLARA o que ficou de fora;
3. a instrucao nao manda reouvir nada: manda reler a transcricao, com o
   instante.

E a carteira: `_compact_report_summary` lia `ipm`, `coherence` e
`dominant_zone` de um arquivo que grava `ipmAvg`, `coherenceStatus` e
`dominantZone`. Nos 20 relatorios mais recentes de producao, 20 de 20 saiam
nulos. O teste le os nomes do arquivo.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

import explica_clinico  # noqa: E402
import main  # noqa: E402

ROTULOS_DA_TABELA = [indice.rotulo for indice in explica_clinico.CATALOGO if indice.chave]


def _metricas(**valores: str) -> dict:
    """Os 33 rotulos da tabela, "--" onde nao houver valor (como a tela)."""
    tabela = {rotulo: "--" for rotulo in ROTULOS_DA_TABELA}
    for rotulo, valor in valores.items():
        tabela[rotulo.replace("_", " ").replace("P MIN", "P/MIN").replace("F0 MED", "F0 MED.")] = valor
    return tabela


# Os oito cortes da sessao real, so os numeros (ipm, idm, p/min, f0 como a
# tela os formata). O corte de 4 segundos e o de 75 segundos sao os que
# existem no arquivo — o teste nao os embeleza.
CORTES_REAIS = [
    ("0-10min (10min)", 0, 600, 594, "49.9", "-0.09", "83.4", "96.03"),
    ("10-11min (10min)", 600, 604, 4, "--", "--", "30.0", "104.54"),
    ("10-12min (manual)", 604, 679, 75, "--", "--", "12.0", "26.35"),
    ("11-22min (10min)", 679, 1279, 592, "49.9", "-0.09", "81.5", "80.55"),
    ("21-32min (10min)", 1279, 1879, 589, "52.7", "0.07", "93.0", "87.30"),
    ("31-42min (10min)", 1879, 2479, 592, "63.0", "0.23", "26.7", "74.94"),
    ("41-52min (10min)", 2479, 3079, 588, "49.7", "-0.33", "38.3", "67.88"),
    ("51-57min (final)", 3079, 3384, 301, "47.2", "-0.35", "24.2", "93.00"),
]


def _corte(rotulo, inicio, fim, amostras, ipm, idm, pmin, f0, tema=None, resumo=None) -> dict:
    return {
        "corte": rotulo,
        "inicio_s": inicio,
        "fim_s": fim,
        "duracao_s": fim - inicio,
        "amostras": amostras,
        "tema": tema,
        "resumo": resumo,
        "metricas": _metricas(IPM=ipm, IDM=idm, P_MIN=pmin, F0_MED=f0),
    }


def _linha_de_base() -> dict:
    return {
        "janela": "0-60 s",
        "amostras": 60,
        "metricas": _metricas(IPM="50.0", IDM="-0.03", P_MIN="57.0", F0_MED="69.89"),
    }


def _contexto_com_cortes(cortes=None) -> dict:
    return {
        "session_id": "froid-teste",
        "panel_metrics": _metricas(IPM="54.0", P_MIN="59.7"),
        "panel_metrics_window": "media da sessao inteira",
        "panel_baseline": _linha_de_base(),
        "panel_cuts": cortes if cortes is not None else [_corte(*linha) for linha in CORTES_REAIS],
        "panel_cuts_window": "cortes desta sessao",
    }


class ATabelaTemOsRotulosDaTela(unittest.TestCase):
    def test_sao_os_33_rotulos_que_o_painel_envia(self):
        self.assertEqual(len(ROTULOS_DA_TABELA), 33)
        self.assertNotIn("CORTE", ROTULOS_DA_TABELA)


class OsCortesEntramNoPrompt(unittest.TestCase):
    def test_cada_corte_vira_uma_linha_com_o_desvio_calculado_pelo_servidor(self):
        bloco = explica_clinico.bloco_dos_cortes(_contexto_com_cortes())
        self.assertIn("CORTES DA SESSAO (cortes desta sessao)", bloco)
        self.assertIn("LINHA DE BASE (0-60 s; amostras 60): IPM=50.0", bloco)
        self.assertIn("8. 51-57min (final) | 3079-3384 s (duracao 305 s) | amostras 301", bloco)
        # 24,2 contra 57,0: -32,8 palavras, -58%. Calculado aqui, nao pelo modelo.
        self.assertIn("P/MIN=24.2 (-58% vs base)", bloco)
        # IPM e IDM saem em pontos, nao em percentual.
        self.assertIn("IPM=47.2 (-2.80 vs base)", bloco)
        self.assertIn("IDM=-0.35 (-0.32 vs base)", bloco)
        self.assertIn("F0 MED.=93.00 (+33% vs base)", bloco)

    def test_ausencia_fica_como_traco_e_nao_ganha_desvio(self):
        bloco = explica_clinico.bloco_dos_cortes(_contexto_com_cortes())
        linha_do_corte_curto = next(
            linha for linha in bloco.splitlines() if linha.startswith("2. 10-11min")
        )
        self.assertIn("amostras 4", linha_do_corte_curto)
        metricas = bloco.splitlines()[bloco.splitlines().index(linha_do_corte_curto) + 1]
        self.assertIn("IPM=--;", metricas)
        self.assertNotIn("IPM=-- (", metricas)

    def test_o_bloco_diz_como_pesar_cortes_de_duracao_diferente(self):
        bloco = explica_clinico.bloco_dos_cortes(_contexto_com_cortes())
        self.assertIn("ponderada pela duracao", bloco)
        self.assertIn("nunca zero", bloco)
        self.assertIn("nao recalcule", bloco)

    def test_tema_e_resumo_entram_e_resumo_longo_se_declara(self):
        resumo = "x" * (explica_clinico.MAX_RESUMO_DO_CORTE + 200)
        cortes = [_corte(*CORTES_REAIS[0], tema="medo de dirigir", resumo=resumo)]
        bloco = explica_clinico.bloco_dos_cortes(_contexto_com_cortes(cortes))
        self.assertIn("tema: medo de dirigir", bloco)
        self.assertIn("[resumo truncado: faltam 200 caracteres]", bloco)

    def test_corte_sem_resumo_declara_a_ausencia(self):
        bloco = explica_clinico.bloco_dos_cortes(_contexto_com_cortes())
        self.assertIn("tema: sem tema registrado", bloco)
        self.assertNotIn("resumo do corte:", bloco)

    def test_excedente_de_cortes_e_declarado_em_numero(self):
        muitos = [_corte(*CORTES_REAIS[0]) for _ in range(explica_clinico.MAX_CORTES_NO_PROMPT + 5)]
        bloco = explica_clinico.bloco_dos_cortes(_contexto_com_cortes(muitos))
        self.assertIn("[5 corte(s) omitido(s) por limite de contexto", bloco)

    def test_sem_cortes_nao_ha_bloco_nem_secao(self):
        self.assertEqual(explica_clinico.bloco_dos_cortes({}), "")
        self.assertEqual(explica_clinico.bloco_dos_cortes(None), "")
        prompt = explica_clinico.montar_prompt(
            pergunta="IPM",
            contexto={"panel_metrics": _metricas(IPM="54.0")},
            contexto_cientifico="",
            contexto_da_sessao="{}",
            transcricao="",
        )
        self.assertNotIn("CORTES DA SESSAO", prompt)

    def test_o_bloco_entra_depois_do_glossario_e_antes_do_contexto_cientifico(self):
        prompt = explica_clinico.montar_prompt(
            pergunta="compare o P/MIN entre os cortes",
            contexto=_contexto_com_cortes(),
            contexto_cientifico="trecho",
            contexto_da_sessao="{}",
            transcricao="",
        )
        self.assertLess(prompt.index("GLOSSARIO DO PAINEL"), prompt.index("CORTES DA SESSAO"))
        self.assertLess(prompt.index("CORTES DA SESSAO"), prompt.index("CONTEXTO CIENTIFICO"))


class NinguemMandaReouvir(unittest.TestCase):
    def test_a_instrucao_manda_reler_a_transcricao_e_diz_que_nao_ha_audio(self):
        instrucao = explica_clinico.instrucao()
        self.assertNotIn("reou", instrucao.lower())
        self.assertIn("NAO GRAVA AUDIO", instrucao)
        self.assertIn("reler", instrucao)
        self.assertIn("mm:ss", instrucao)

    def test_nenhuma_ficha_do_catalogo_manda_reouvir(self):
        for indice in explica_clinico.CATALOGO:
            texto = " ".join([indice.medida, indice.leitura, indice.abre, indice.limite]).lower()
            self.assertNotIn("reou", texto, indice.rotulo)


class OContextoTruncadoSeDeclara(unittest.TestCase):
    def test_contexto_pequeno_sai_inteiro_e_sem_marcador(self):
        texto = main._format_session_context({"session_id": "a", "ipm_score": 53.98})
        self.assertIn('"ipm_score": 53.98', texto)
        self.assertNotIn("CONTEXTO TRUNCADO", texto)

    def test_contexto_grande_declara_a_chave_que_ficou_de_fora_e_mantem_as_outras(self):
        contexto = {
            "session_id": "a",
            "bloco_gigante": "x" * 105_000,
            "panel_metrics": {"IPM": "54.0"},
        }
        texto = main._format_session_context(contexto)
        self.assertIn("[CONTEXTO TRUNCADO pelo servidor", texto)
        self.assertIn("bloco_gigante (", texto)
        self.assertIn('"session_id": "a"', texto)
        # A chave pequena DEPOIS da gigante ainda entra: o corte e por chave.
        self.assertIn('"panel_metrics"', texto)
        self.assertLess(len(texto), main.LIMITE_DO_CONTEXTO_DA_SESSAO + 1_000)

    def test_os_cortes_nao_se_repetem_no_json(self):
        texto = main._format_session_context(_contexto_com_cortes())
        self.assertNotIn("panel_cuts", texto)
        self.assertNotIn("panel_baseline", texto)
        self.assertIn("panel_metrics", texto)

    def test_transcricao_longa_declara_o_que_faltou_e_repete_a_marcacao_de_tempo(self):
        contexto = {
            "transcript_available": True,
            "session_transcript": "y" * (main.LIMITE_DA_TRANSCRICAO_NO_PROMPT + 10_000),
            "transcript_timestamps": "cada linha abre com [mm:ss]",
        }
        texto = main._format_session_transcript(contexto)
        self.assertIn("Instantes: cada linha abre com [mm:ss].", texto)
        self.assertIn("[TRANSCRICAO TRUNCADA pelo servidor: faltam os ultimos 10000 caracteres", texto)

    def test_transcricao_curta_nao_ganha_marcador(self):
        texto = main._format_session_transcript(
            {"transcript_available": True, "session_transcript": "[00:05] PC - oi"}
        )
        self.assertIn("[00:05] PC - oi", texto)
        self.assertNotIn("TRUNCADA", texto)


def _relatorio_como_o_arquivo(**extras) -> dict:
    relatorio = {
        "sessionId": "froid-abc",
        "createdAt": "2026-10-14T14:35:52",
        "patientId": "pac-1",
        "durationSeconds": 3387,
        "baseline": {"ipmAvg": 50, "idmAvg": -0.028, "wordsPerMinute": 57, "f0Mean": 69.89},
        "sessionAverage": {
            "ipmAvg": 53.98,
            "idmAvg": 0.015,
            "wordsPerMinute": 59.7,
            "f0Mean": 81.27,
            "dominantZone": 1,
            "coherenceStatus": "SEM_APURACAO",
        },
        "tenMinuteCuts": [{}] * 8,
        "sessionSummary": {"theme": "tema da sessao", "summary": "resumo da sessao", "generatedAt": "x"},
    }
    relatorio.update(extras)
    return relatorio


class ACarteiraLeOsNomesDoArquivo(unittest.TestCase):
    def test_os_numeros_do_arquivo_chegam_ao_resumo(self):
        resumo = main._compact_report_summary(_relatorio_como_o_arquivo())
        self.assertEqual(resumo["ipm_average"], 53.98)
        self.assertEqual(resumo["ipm_baseline"], 50.0)
        self.assertEqual(resumo["idm_average"], 0.015)
        self.assertEqual(resumo["words_per_minute_average"], 59.7)
        self.assertEqual(resumo["words_per_minute_baseline"], 57.0)
        self.assertEqual(resumo["f0_mean_average"], 81.27)
        self.assertEqual(resumo["dominant_zone"], 1)
        self.assertEqual(resumo["coherence"], "SEM_APURACAO")
        self.assertEqual(resumo["cuts_count"], 8)
        self.assertEqual(resumo["duration_seconds"], 3387.0)
        self.assertEqual(resumo["theme"], "tema da sessao")
        self.assertEqual(resumo["session_summary"], "resumo da sessao")

    def test_zero_medido_continua_zero_e_ausencia_continua_nula(self):
        relatorio = _relatorio_como_o_arquivo(
            sessionAverage={"ipmAvg": 0.0, "idmAvg": None, "dominantZone": None}
        )
        resumo = main._compact_report_summary(relatorio)
        self.assertEqual(resumo["ipm_average"], 0.0)
        self.assertIsNone(resumo["idm_average"])
        self.assertIsNone(resumo["words_per_minute_average"])
        self.assertIsNone(resumo["dominant_zone"])
        self.assertIsNone(resumo["coherence"])

    def test_a_carteira_sai_uma_linha_por_sessao_e_marca_o_paciente_atual(self):
        itens = [main._compact_report_summary(_relatorio_como_o_arquivo()) for _ in range(2)]
        itens[0]["current_patient"] = True
        texto = main._format_portfolio_summary({"portfolio_summary": itens})
        self.assertIn("(2 sessoes;", texto)
        self.assertIn("paciente pac-1 (ESTE PACIENTE) | 56 min | 8 cortes | IPM 54.0 (base 50.0)", texto)
        self.assertIn("P/MIN 59.7 (base 57.0) | F0 MED. 81.3 (base 69.9) | zona 1", texto)
        self.assertEqual(texto.count("(ESTE PACIENTE)"), 1)
        self.assertNotIn("omitida", texto)

    def test_a_carteira_declara_as_sessoes_que_nao_couberam(self):
        itens = [main._compact_report_summary(_relatorio_como_o_arquivo()) for _ in range(60)]
        texto = main._format_portfolio_summary({"portfolio_summary": itens})
        self.assertIn("(60 sessoes;", texto)
        self.assertRegex(texto, r"\[\d+ sessao\(oes\) omitida\(s\) por limite de contexto")
        self.assertLess(len(texto), main.LIMITE_DA_CARTEIRA_NO_PROMPT + 1_000)

    def test_ausencia_na_carteira_e_traco_nunca_zero(self):
        item = main._compact_report_summary(_relatorio_como_o_arquivo(sessionAverage={}, baseline={}))
        texto = main._format_portfolio_summary({"portfolio_summary": [item]})
        self.assertIn("IPM -- (base --)", texto)
        self.assertNotIn("IPM 0.0", texto)


if __name__ == "__main__":
    unittest.main()
