# -*- coding: utf-8 -*-
"""As ferramentas do FROID Explica leem so o acervo que recebem, e o laco anda.

Fase 4 (18/10/2026). Tres garantias:

1. cada ferramenta le SOMENTE do `Acervo` que o servidor lhe entrega (o que o
   painel lista); sessao fora do acervo e erro declarado, nunca dado;
2. a tabela por corte montada no servidor e o espelho da que o painel monta
   (`metricasParaOExplica`): o teste le o arquivo TypeScript e confronta
   rotulo, campo e casas, como ja se faz entre o painel e o glossario;
3. o laco de ferramentas no caminho Claude executa os pedidos de um turno,
   devolve todos numa so mensagem, marca erro como erro, e para no teto.

O modulo `anthropic` e um duble; nenhum teste toca a rede.
"""

from __future__ import annotations

import asyncio
import re
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

import explica_clinico  # noqa: E402
import explica_ferramentas as f  # noqa: E402
import main  # noqa: E402

RAIZ = SERVIDOR.parent
HELPER_TS = RAIZ / "froid-dashboard" / "src" / "lib" / "painel-para-o-explica.ts"


def _relatorio(session_id, patient_id, data, ipm=53.98, pmin=59.7, cortes=2, profissional="dra@x.br"):
    return {
        "sessionId": session_id,
        "patientId": patient_id,
        "createdAt": f"{data}T10:00:00",
        "durationSeconds": 1200,
        "professionalEmail": profissional,
        "baseline": {"startSecond": 0, "endSecond": 60, "sampleCount": 60, "ipmAvg": 50, "wordsPerMinute": 57, "f0Mean": 69.89},
        "sessionAverage": {"ipmAvg": ipm, "idmAvg": 0.015, "wordsPerMinute": pmin, "f0Mean": 81.27, "dominantZone": 1, "coherenceStatus": "SEM_APURACAO"},
        "tenMinuteCuts": [
            {"label": f"{i * 10}-{(i + 1) * 10}min (10min)", "startSecond": i * 600, "endSecond": (i + 1) * 600,
             "sampleCount": 590, "ipmAvg": 49.9 + i, "wordsPerMinute": 83.4 - 10 * i, "f0Mean": 96.03}
            for i in range(cortes)
        ],
        "conversationSummaries": [
            {"id": "r1", "startSecond": 0, "endSecond": 600, "startMinute": 0, "endMinute": 10, "theme": "medo de dirigir", "summary": "Descreve o medo na estrada."}
        ],
        "sessionSummary": {"theme": "tema", "summary": "resumo", "generatedAt": "x"},
        "transcript": "PC - oi\nDR - ola\nPC - tudo bem",
        "transcriptLineSeconds": [5, 65, 700],
    }


def _acervo(**extras):
    relatorios = [
        _relatorio("froid-a", "pac-1", "2026-10-14"),
        _relatorio("froid-b", "pac-1", "2026-09-30", ipm=48.0, pmin=70.0),
        _relatorio("froid-c", "pac-2", "2026-10-01", profissional="dr@y.br"),
    ]
    por_id = {r["sessionId"]: r for r in relatorios}
    return f.Acervo(
        relatorios=[{k: v for k, v in r.items() if k not in ("transcript", "transcriptLineSeconds")} for r in relatorios],
        sessao_atual="froid-a",
        paciente_atual="pac-1",
        transcricao_de=lambda sid: por_id.get(sid),
        **extras,
    )


class ATabelaDoServidorEspelhaADoPainel(unittest.TestCase):
    def test_rotulo_campo_e_casas_sao_os_mesmos_do_helper_typescript(self):
        fonte = HELPER_TS.read_text(encoding="utf-8")
        inicio = fonte.index("export function metricasParaOExplica")
        fim = fonte.index("\n}", inicio)
        pares_ts = re.findall(r'\[\s*"([^"]+)",\s*fmt\(snapshot\.(\w+),\s*(\d+)\)\s*\]', fonte[inicio:fim])
        pares_py = [(r, c, str(n)) for r, c, n in f.ROTULOS_DO_SNAPSHOT if n >= 0]
        self.assertEqual(pares_py, pares_ts)
        # Os dois rotulos de texto (ZONAS, TOM) existem nos dois lados.
        self.assertIn('["ZONAS", snapshot.dominantZone', fonte[inicio:fim])
        self.assertIn('["TOM", snapshot.emotionalTone', fonte[inicio:fim])
        self.assertEqual(len(f.ROTULOS_DO_SNAPSHOT), 33)

    def test_ausencia_vira_traco_e_zona_vira_zona(self):
        metricas = f.metricas_do_snapshot({"ipmAvg": 49.91, "dominantZone": 6})
        self.assertEqual(metricas["IPM"], "49.9")
        self.assertEqual(metricas["IDM"], "--")
        self.assertEqual(metricas["ZONAS"], "Zona 6")
        self.assertEqual(metricas["TOM"], "--")


class CadaFerramentaLeSoDoAcervo(unittest.TestCase):
    def test_cortes_de_sessao_acessivel_saem_no_bloco_do_glossario(self):
        texto, erro = f.executar(_acervo(), "cortes_da_sessao", {"session_id": "froid-a"})
        self.assertFalse(erro)
        self.assertIn("CORTES DA SESSAO (cortes da sessao froid-a)", texto)
        self.assertIn("LINHA DE BASE (0-60 s; amostras 60): IPM=50.0", texto)
        self.assertIn("P/MIN=83.4 (+46% vs base)", texto)
        self.assertIn("tema: medo de dirigir", texto)

    def test_sessao_fora_do_acervo_e_erro_declarado(self):
        texto, erro = f.executar(_acervo(), "cortes_da_sessao", {"session_id": "froid-de-outro"})
        self.assertTrue(erro)
        self.assertIn("nao esta entre as sessoes que voce pode ver", texto)

    def test_sessoes_do_paciente_em_ordem_cronologica_com_marca(self):
        texto, erro = f.executar(_acervo(), "sessoes_do_paciente", {"patient_id": ""})
        self.assertFalse(erro)
        self.assertIn("SESSOES DO PACIENTE pac-1 (2 acessiveis", texto)
        self.assertLess(texto.index("froid-b"), texto.index("froid-a"))
        self.assertIn("(ESTE PACIENTE)", texto)
        self.assertNotIn("pac-2", texto)

    def test_pacientes_do_profissional_conta_por_paciente_com_n(self):
        texto, erro = f.executar(_acervo(), "pacientes_do_profissional", {})
        self.assertFalse(erro)
        self.assertIn("PACIENTES COM SESSAO ACESSIVEL: 2", texto)
        self.assertIn("paciente pac-1 (ESTE PACIENTE) | 2 sessoes | de 2026-09-30 a 2026-10-14 | IPM medio 51.0 (n=2)", texto)
        self.assertIn("paciente pac-2 | 1 sessoes", texto)

    def test_agregado_por_profissional_e_por_clinica(self):
        por_prof, erro = f.executar(_acervo(), "agregado_da_clinica", {"por": "profissional"})
        self.assertFalse(erro)
        self.assertIn("- dra@x.br | 1 pacientes | 2 sessoes", por_prof)
        self.assertIn("- dr@y.br | 1 pacientes | 1 sessoes", por_prof)
        clinica, _ = f.executar(_acervo(), "agregado_da_clinica", {"por": "clinica"})
        self.assertIn("- clinica | 2 pacientes | 3 sessoes", clinica)
        _texto, erro = f.executar(_acervo(), "agregado_da_clinica", {"por": "grupo"})
        self.assertTrue(erro)

    def test_trecho_da_transcricao_por_instante(self):
        texto, erro = f.executar(_acervo(), "trecho_da_transcricao", {"session_id": "", "inicio_s": 0, "fim_s": 100})
        self.assertFalse(erro)
        self.assertIn("DE 00:00 A 01:40 (2 linhas)", texto)
        self.assertIn("[00:05] PC - oi", texto)
        self.assertIn("[01:05] DR - ola", texto)
        self.assertNotIn("tudo bem", texto)

    def test_trecho_de_sessao_fora_do_acervo_e_erro(self):
        _texto, erro = f.executar(_acervo(), "trecho_da_transcricao", {"session_id": "froid-x", "inicio_s": 0, "fim_s": 10})
        self.assertTrue(erro)

    def test_ferramenta_inexistente_e_erro_e_a_chamada_fica_registrada(self):
        acervo = _acervo()
        texto, erro = f.executar(acervo, "apagar_tudo", {"x": 1})
        self.assertTrue(erro)
        self.assertIn("nao existe", texto)
        self.assertEqual(acervo.chamadas, [("apagar_tudo", {"x": 1})])

    def test_os_esquemas_sao_estritos(self):
        for ferramenta in f.definicoes():
            self.assertTrue(ferramenta["strict"], ferramenta["name"])
            self.assertFalse(ferramenta["input_schema"]["additionalProperties"], ferramenta["name"])


# ---------------------------------------------------------------------------
# O laco
# ---------------------------------------------------------------------------


def _resposta(content, parada):
    return SimpleNamespace(content=content, stop_reason=parada, stop_details=None, model="claude-opus-5-5",
                           usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0, cache_creation_input_tokens=0))


def _texto(t):
    return SimpleNamespace(type="text", text=t)


def _pedido(id_, nome, entrada):
    return SimpleNamespace(type="tool_use", id=id_, name=nome, input=entrada)


class _Mensagens:
    def __init__(self, registro):
        self._registro = registro

    def create(self, **kwargs):
        self._registro["chamadas"].append(kwargs)
        fila = self._registro["fila"]
        return fila.pop(0) if fila else _resposta([_texto("fim")], "end_turn")


class _ClienteFalso:
    registro = {"chamadas": [], "fila": []}

    def __init__(self, **kwargs):
        self.messages = _Mensagens(type(self).registro)
        self.beta = SimpleNamespace(messages=_Mensagens(type(self).registro))


class OLacoDeFerramentas(unittest.TestCase):
    def setUp(self):
        _ClienteFalso.registro = {"chamadas": [], "fila": []}
        self._original = sys.modules.get("anthropic")
        modulo = types.ModuleType("anthropic")
        modulo.Anthropic = _ClienteFalso
        sys.modules["anthropic"] = modulo
        self._chaves = patch.multiple(main, ANTHROPIC_API_KEY="k", GEMINI_API_KEY="", OPENAI_API_KEY="")
        self._chaves.start()

    def tearDown(self):
        self._chaves.stop()
        if self._original is not None:
            sys.modules["anthropic"] = self._original
        else:
            sys.modules.pop("anthropic", None)

    def _perguntar(self, acervo):
        return asyncio.run(main._generate_froid_explain_text("I", "P", max_tokens=800, acervo=acervo))

    def test_executa_os_pedidos_do_turno_e_devolve_todos_numa_so_mensagem(self):
        _ClienteFalso.registro["fila"] = [
            _resposta([_pedido("t1", "pacientes_do_profissional", {}), _pedido("t2", "cortes_da_sessao", {"session_id": "froid-x"})], "tool_use"),
            _resposta([_texto("leitura comparada")], "end_turn"),
        ]
        acervo = _acervo()
        texto, motor = self._perguntar(acervo)
        self.assertEqual(texto, "leitura comparada")
        self.assertEqual(motor, "Claude (claude-opus-5-5)")
        chamadas = _ClienteFalso.registro["chamadas"]
        self.assertEqual(len(chamadas), 2)
        self.assertEqual([t["name"] for t in chamadas[0]["tools"]], [t["name"] for t in f.definicoes()])
        segunda = chamadas[1]["messages"]
        self.assertEqual(segunda[1]["role"], "assistant")
        resultados = segunda[2]["content"]
        self.assertEqual(segunda[2]["role"], "user")
        self.assertEqual([r["tool_use_id"] for r in resultados], ["t1", "t2"])
        self.assertNotIn("is_error", resultados[0])
        self.assertTrue(resultados[1]["is_error"])
        self.assertIn("PACIENTES COM SESSAO ACESSIVEL", resultados[0]["content"])
        self.assertEqual([nome for nome, _ in acervo.chamadas], ["pacientes_do_profissional", "cortes_da_sessao"])

    def test_sem_acervo_nao_manda_ferramentas(self):
        _ClienteFalso.registro["fila"] = [_resposta([_texto("ok")], "end_turn")]
        self._perguntar(None)
        self.assertNotIn("tools", _ClienteFalso.registro["chamadas"][0])

    def test_para_no_teto_de_turnos_e_avisa(self):
        _ClienteFalso.registro["fila"] = [
            _resposta([_pedido(f"t{i}", "pacientes_do_profissional", {})], "tool_use")
            for i in range(main.MAX_TURNOS_DE_FERRAMENTA + 3)
        ]
        with self.assertLogs("froid.persistence", level="WARNING") as log:
            texto, _motor = self._perguntar(_acervo())
        self.assertEqual(texto, "")
        self.assertTrue(any("teto de 6 turnos de ferramenta" in linha for linha in log.output))
        self.assertEqual(len(_ClienteFalso.registro["chamadas"]), main.MAX_TURNOS_DE_FERRAMENTA + 1)


class AInstrucaoSoFalaDeFerramentasQuandoElasExistem(unittest.TestCase):
    def test_bloco_de_ferramentas_e_condicional(self):
        self.assertNotIn("FERRAMENTAS.", explica_clinico.instrucao())
        com = explica_clinico.instrucao(com_ferramentas=True)
        self.assertIn("FERRAMENTAS.", com)
        self.assertIn("ja pode ver no painel", com)


if __name__ == "__main__":
    unittest.main()
