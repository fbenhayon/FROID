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

    def test_no_teto_de_turnos_atende_o_ultimo_pedido_e_pede_a_resposta_final(self):
        """Ate 20/10/2026 o teto descartava os turnos pagos e devolvia vazio.
        Agora o ultimo turno e atendido e a chamada seguinte vai com
        tool_choice none: a resposta sai com o que ha."""
        _ClienteFalso.registro["fila"] = [
            _resposta([_pedido(f"t{i}", "pacientes_do_profissional", {})], "tool_use")
            for i in range(main.MAX_TURNOS_DE_FERRAMENTA + 1)
        ] + [_resposta([_texto("com o que ha")], "end_turn")]
        acervo = _acervo()
        with self.assertLogs("froid.persistence", level="WARNING") as log:
            texto, _motor = self._perguntar(acervo)
        self.assertEqual(texto, "com o que ha")
        self.assertTrue(any("teto de 6 turnos de ferramenta" in linha for linha in log.output))
        chamadas = _ClienteFalso.registro["chamadas"]
        self.assertEqual(len(chamadas), main.MAX_TURNOS_DE_FERRAMENTA + 2)
        self.assertTrue(all("tool_choice" not in c for c in chamadas[:-1]))
        self.assertEqual(chamadas[-1]["tool_choice"], {"type": "none"})
        self.assertIn("tools", chamadas[-1])  # a API exige as definicoes com tool_use no historico
        self.assertEqual(len(acervo.chamadas), main.MAX_TURNOS_DE_FERRAMENTA + 1)

    def test_se_o_modelo_insiste_na_ferramenta_depois_do_pedido_final_o_motor_nao_responde(self):
        _ClienteFalso.registro["fila"] = [
            _resposta([_pedido(f"t{i}", "pacientes_do_profissional", {})], "tool_use")
            for i in range(main.MAX_TURNOS_DE_FERRAMENTA + 3)
        ]
        with self.assertLogs("froid.persistence", level="WARNING") as log:
            texto, _motor = self._perguntar(_acervo())
        self.assertEqual(texto, "")
        self.assertTrue(any("depois do pedido de resposta final" in linha for linha in log.output))
        self.assertEqual(len(_ClienteFalso.registro["chamadas"]), main.MAX_TURNOS_DE_FERRAMENTA + 2)

    def test_o_prompt_vai_como_bloco_em_cache_e_o_cliente_e_um_so(self):
        """Revisao 20/10/2026, item 17: o prompt e reenviado a cada turno; em
        cache, a releitura custa um decimo. E um cliente por processo."""
        _ClienteFalso.registro["fila"] = [_resposta([_texto("ok")], "end_turn")]
        self._perguntar(_acervo())
        self._perguntar(_acervo())
        chamadas = _ClienteFalso.registro["chamadas"]
        bloco = chamadas[0]["messages"][0]["content"][0]
        self.assertEqual(bloco["type"], "text")
        self.assertEqual(bloco["text"], "P")
        self.assertEqual(bloco["cache_control"], {"type": "ephemeral"})
        self.assertEqual(chamadas[0]["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertIs(main._CLIENTE_CLAUDE["cliente"], main._cliente_claude(sys.modules["anthropic"]))

    def test_o_orcamento_de_tempo_pede_a_resposta_final(self):
        """Item 19: esgotado o orcamento, nao se abre mais um turno."""
        _ClienteFalso.registro["fila"] = [
            _resposta([_pedido("t1", "pacientes_do_profissional", {})], "tool_use"),
            _resposta([_texto("no tempo")], "end_turn"),
        ]
        with patch.object(main, "FROID_EXPLICA_ORCAMENTO_S", 0.0):
            with self.assertLogs("froid.persistence", level="WARNING") as log:
                texto, _motor = self._perguntar(_acervo())
        self.assertEqual(texto, "no tempo")
        self.assertTrue(any("orcamento de 0 s esgotado apos 1 turnos" in linha for linha in log.output))
        chamadas = _ClienteFalso.registro["chamadas"]
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(chamadas[1]["tool_choice"], {"type": "none"})

    def test_esforco_e_piso_sao_por_chamada(self):
        """Item 20: o SQL do Data-FROID vai com esforco baixo e piso curto; o
        caminho clinico continua no esforco e no piso do modulo."""
        _ClienteFalso.registro["fila"] = [
            _resposta([_texto("{}")], "end_turn"),
            _resposta([_texto("clinico")], "end_turn"),
        ]
        asyncio.run(main._generate_froid_explain_text(
            "I", "P", max_tokens=500, json_mode=True, json_schema={"type": "object"},
            esforco="low", piso_de_tokens=2_000))
        asyncio.run(main._generate_froid_explain_text("I", "P", max_tokens=800))
        sql, clinico = _ClienteFalso.registro["chamadas"]
        self.assertEqual(sql["output_config"]["effort"], "low")
        self.assertEqual(sql["max_tokens"], 2_000)
        self.assertEqual(clinico["output_config"]["effort"], main.FROID_EXPLICA_CLAUDE_EFFORT)
        self.assertEqual(clinico["max_tokens"], main.FROID_EXPLICA_CLAUDE_MAX_TOKENS)

    def test_a_instrucao_sem_ferramentas_e_a_que_vai_aos_outros_motores(self):
        """O Gemini nao tem laco: recebe a instrucao sem o bloco FERRAMENTAS."""
        recebido = {}

        class _Config:
            def __init__(self, **kwargs):
                recebido.update(kwargs)

        class _Modelos:
            def generate_content(self, **kwargs):
                return SimpleNamespace(text="do gemini")

        class _Cliente:
            def __init__(self, **kwargs):
                self.models = _Modelos()

        google = types.ModuleType("google")
        genai = types.ModuleType("google.genai")
        genai.Client = _Cliente
        tipos = types.ModuleType("google.genai.types")
        tipos.GenerateContentConfig = _Config
        genai.types = tipos
        google.genai = genai
        with patch.dict(sys.modules, {"google": google, "google.genai": genai, "google.genai.types": tipos}):
            with patch.multiple(main, ANTHROPIC_API_KEY="", GEMINI_API_KEY="g", OPENAI_API_KEY=""):
                texto, _motor = asyncio.run(main._generate_froid_explain_text(
                    "I com FERRAMENTAS.", "P", max_tokens=800, acervo=_acervo(),
                    instrucao_sem_ferramentas="I sem"))
        self.assertEqual(texto, "do gemini")
        self.assertEqual(recebido["system_instruction"], "I sem")


class OAcervoELidoUmaVezPorPergunta(unittest.TestCase):
    """Item 18: o resumo da carteira e as ferramentas leem o acervo uma vez na
    mesma requisicao, e a transcricao e decifrada so para a sessao pedida."""

    def _relatorios(self):
        return [
            {"sessionId": "froid-a", "transcript": "CIFRADO", "transcript_encrypted": True, "patient": {"id": "pac-1", "name": "A"}},
            {"sessionId": "froid-b", "transcript": "DR: em claro\nPC: tudo", "patient": {"id": "pac-2", "name": "B"}},
        ]

    def test_uma_leitura_para_a_carteira_e_as_ferramentas(self):
        leituras = []

        def acessiveis(request, *, reveal_transcripts=False):
            leituras.append(reveal_transcripts)
            return [dict(r) for r in self._relatorios()], None

        pedido = SimpleNamespace(state=SimpleNamespace())
        carga = SimpleNamespace(session_id="froid-a", patient_id="pac-1", context={})
        with patch.object(main, "_accessible_session_reports", acessiveis),                 patch.object(main, "SESSION_INVITES", {"tok": {"session_id": "froid-b", "patient_id": "pac-2"}}),                 patch.object(main, "CLINICAL_TEXT_CIPHER", None):
            carteira = main._build_portfolio_summary(pedido, "pac-1")
            acervo = main._acervo_do_explica(pedido, carga)
            self.assertEqual(len(carteira), 2)
            self.assertEqual([r["sessionId"] for r in acervo.relatorios], ["froid-a", "froid-b"])
            em_claro = acervo.transcricao_de("froid-b")
            trancado = acervo.transcricao_de("froid-a")
            self.assertIsNone(acervo.transcricao_de("froid-z"))
        self.assertEqual(leituras, [False])  # uma leitura, sem decifrar o acervo inteiro
        self.assertEqual(em_claro["transcript"], "DR: em claro\nPC: tudo")
        # Sem cifra configurada o registro sai trancado e declarado, nunca o texto cifrado.
        self.assertEqual(trancado["transcript"], "")
        self.assertTrue(trancado["transcript_storage_locked"])
        # O acervo em memoria nao foi alterado pela decifragem de uma copia.
        self.assertEqual(acervo.relatorio("froid-a")["transcript"], "CIFRADO")


class AReferenciaPopulacional(unittest.TestCase):
    """Fase 5: a ferramenta existe no esquema, repassa a entrada ao que main
    injeta, e declara a ausencia do Data-FROID em vez de inventar numero."""

    def test_a_ferramenta_esta_no_esquema_com_a_lista_fechada_de_medidas(self):
        import data_froid_referencia
        definicao = next(d for d in f.definicoes() if d["name"] == "referencia_populacional")
        self.assertTrue(definicao["strict"])
        self.assertEqual(tuple(definicao["input_schema"]["properties"]["medida"]["enum"]), data_froid_referencia.NOMES_DAS_MEDIDAS)
        self.assertEqual(set(definicao["input_schema"]["required"]), set(definicao["input_schema"]["properties"]))

    def test_sem_data_froid_a_ferramenta_declara(self):
        texto, erro = f.executar(_acervo(), "referencia_populacional", {"medida": "ipm_sessao", "valor_do_paciente": "", "age_bucket": "", "gender": "", "session_modality": ""})
        self.assertTrue(erro)
        self.assertIn("nao esta disponivel neste servidor", texto)

    def test_com_data_froid_a_entrada_vai_inteira_e_o_texto_volta(self):
        recebido = {}

        def consulta(entrada):
            recebido.update(entrada)
            return "REFERENCIA POPULACIONAL (teste)"

        acervo = _acervo(referencia_populacional=consulta)
        entrada = {"medida": "f0_corte", "valor_do_paciente": "101.5", "age_bucket": "30-39", "gender": "", "session_modality": ""}
        texto, erro = f.executar(acervo, "referencia_populacional", entrada)
        self.assertFalse(erro)
        self.assertEqual(texto, "REFERENCIA POPULACIONAL (teste)")
        self.assertEqual(recebido, entrada)
        self.assertEqual(acervo.chamadas[-1][0], "referencia_populacional")

    def test_a_injecao_de_main_le_o_acervo_pelo_piso_e_pelas_versoes_do_servidor(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb ausente")
        import tempfile, os
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "acervo.duckdb")
        conn = duckdb.connect(caminho)
        conn.execute("CREATE TABLE anonymous_sessions(session_hash VARCHAR, schema_version VARCHAR, ipm_score DOUBLE, age_bucket VARCHAR, gender VARCHAR, session_modality VARCHAR)")
        conn.execute("CREATE TABLE anonymous_session_cuts(session_hash VARCHAR, ipm_avg DOUBLE)")
        for i in range(8):
            conn.execute("INSERT INTO anonymous_sessions VALUES (?, 'anonymous_datamart_v5', ?, '30-39', 'F', 'remota')", [f"s{i}", 40.0 + i])
        conn.close()
        entrada = {"medida": "ipm_sessao", "valor_do_paciente": "44", "age_bucket": "", "gender": "", "session_modality": ""}
        with patch.object(main, "FROID_DUCKDB_PATH", caminho), patch.object(main, "FROID_ANALYTICS_MIN_K", 7):
            texto = main._referencia_populacional_do_data_froid(entrada)
            self.assertIn("sessoes distintas: 8 (piso de coorte 7)", texto)
            self.assertIn("fica acima de 50%", texto)
            with patch.object(main, "FROID_ANALYTICS_MIN_K", 9):
                with self.assertRaises(f.ErroDeFerramenta) as erro:
                    main._referencia_populacional_do_data_froid(entrada)
                self.assertIn("menos de 9 sessoes", str(erro.exception))
                self.assertNotIn("8", str(erro.exception))
            with self.assertRaises(f.ErroDeFerramenta):
                main._referencia_populacional_do_data_froid({**entrada, "valor_do_paciente": "alto"})
            with self.assertRaises(f.ErroDeFerramenta):
                main._referencia_populacional_do_data_froid({**entrada, "medida": "summary_text_anon"})
        # Sem o arquivo do acervo, main nao injeta a referencia.
        with patch.object(main, "FROID_DUCKDB_PATH", os.path.join(pasta, "nao-existe.duckdb")):
            with patch.object(main, "_relatorios_acessiveis_da_requisicao", lambda request: []):
                acervo = main._acervo_do_explica(SimpleNamespace(state=SimpleNamespace()), SimpleNamespace(session_id="", patient_id="", context={}))
        self.assertIsNone(acervo.referencia_populacional)


class AFronteiraDeAcessoDoAcervo(unittest.TestCase):
    """Revisao 20/10/2026, item 27: dois usuarios, cada um com o seu acervo;
    a transcricao de um nao sai pelo acervo do outro, nem por id adivinhado."""

    def test_um_usuario_nao_decifra_a_sessao_do_outro(self):
        por_usuario = {
            "ana@x.br": [{"sessionId": "froid-ana", "transcript": "DR: so da Ana", "patient": {"id": "p1"}}],
            "bia@x.br": [{"sessionId": "froid-bia", "transcript": "DR: so da Bia", "patient": {"id": "p2"}}],
        }

        def acessiveis(request, *, reveal_transcripts=False):
            return [dict(r) for r in por_usuario[request.state.usuario]], None

        def pedido(usuario):
            return SimpleNamespace(state=SimpleNamespace(usuario=usuario))

        carga = SimpleNamespace(session_id="", patient_id="", context={})
        with patch.object(main, "_accessible_session_reports", acessiveis),                 patch.object(main, "SESSION_INVITES", {}), patch.object(main, "CLINICAL_TEXT_CIPHER", None):
            ana = main._acervo_do_explica(pedido("ana@x.br"), carga)
            bia = main._acervo_do_explica(pedido("bia@x.br"), carga)
            self.assertEqual(ana.transcricao_de("froid-ana")["transcript"], "DR: so da Ana")
            self.assertIsNone(ana.transcricao_de("froid-bia"))
            self.assertIsNone(bia.transcricao_de("froid-ana"))
            self.assertIsNone(ana.relatorio("froid-bia"))
            # Pela ferramenta, o id alheio e recusado como "nao esta entre as sessoes que voce pode ver".
            texto, erro = f.executar(ana, "trecho_da_transcricao", {"session_id": "froid-bia", "inicio_s": 0, "fim_s": 10})
            self.assertTrue(erro)
            self.assertIn("nao esta entre as sessoes que voce pode ver", texto)
            texto, erro = f.executar(ana, "cortes_da_sessao", {"session_id": "froid-bia"})
            self.assertTrue(erro)


class OTrechoCortaEmLinhasInteiras(unittest.TestCase):
    """Revisao 20/10/2026, item 16: o corte por caractere deixava a ultima
    linha pela metade; agora e por linha inteira e declara as omitidas."""

    def test_declara_as_linhas_omitidas_e_nenhuma_sai_pela_metade(self):
        linhas = [f"PC: fala numero {i} " + "x" * 40 for i in range(200)]
        relatorio = {"transcript": "\n".join(linhas), "transcriptLineSeconds": [float(i) for i in range(200)]}
        acervo = _acervo()
        acervo.transcricao_de = lambda sid: relatorio
        texto, erro = f.executar(acervo, "trecho_da_transcricao", {"session_id": "froid-a", "inicio_s": 0, "fim_s": 200})
        self.assertFalse(erro)
        corpo = texto.split("\n")[1:]
        self.assertTrue(corpo[-1].startswith("[trecho truncado: "))
        self.assertIn("linhas omitidas depois de ", corpo[-1])
        entregues = corpo[:-1]
        self.assertTrue(all(l.startswith("[") and l.endswith("x" * 40) for l in entregues), "linha pela metade")
        omitidas = int(corpo[-1].split("truncado: ")[1].split(" ")[0])
        self.assertEqual(len(entregues) + omitidas, 200)
        self.assertLessEqual(len("\n".join(entregues)), f.LIMITE_DO_TRECHO)

    def test_dentro_do_limite_nao_ha_aviso(self):
        relatorio = {"transcript": "PC: a\nDR: b", "transcriptLineSeconds": [1.0, 2.0]}
        acervo = _acervo()
        acervo.transcricao_de = lambda sid: relatorio
        texto, _erro = f.executar(acervo, "trecho_da_transcricao", {"session_id": "froid-a", "inicio_s": 0, "fim_s": 10})
        self.assertNotIn("truncado", texto)
        self.assertEqual(texto.split("\n")[1:], ["[00:01] PC: a", "[00:02] DR: b"])


class OCorteSemInstanteNaoViraZero(unittest.TestCase):
    """Regra 1.1 (revisao 20/10/2026, item 6): startSecond ausente virava 0 e a
    linha do corte saia "0-0 s (duracao 0 s)", um numero com cara de medida."""

    def test_corte_compacto_propaga_a_ausencia(self):
        compacto = f.corte_compacto({"label": "manual", "sampleCount": 3}, None)
        self.assertIsNone(compacto["inicio_s"])
        self.assertIsNone(compacto["fim_s"])
        self.assertIsNone(compacto["duracao_s"])
        self.assertEqual(compacto["corte"], "manual")
        self.assertEqual(f.corte_compacto({}, None)["corte"], "corte sem instante")
        com = f.corte_compacto({"startSecond": 60, "endSecond": 130}, None)
        self.assertEqual((com["inicio_s"], com["fim_s"], com["duracao_s"]), (60, 130, 70))

    def test_a_linha_do_corte_declara_o_instante_nao_registrado(self):
        bloco = explica_clinico.bloco_dos_cortes({
            "panel_cuts": [f.corte_compacto({"label": "manual", "sampleCount": 3}, None)],
            "panel_cuts_window": "cortes desta sessao",
        })
        self.assertIn("instante nao registrado", bloco)
        self.assertNotIn("0-0 s", bloco)
        self.assertNotIn("None", bloco)

    def test_resumo_sem_instante_nao_casa_com_o_primeiro_corte(self):
        resumos = [{"theme": "sem instante", "summary": "x"}, {"startSecond": 0, "endSecond": 100, "theme": "certo"}]
        self.assertEqual(f._resumo_do_corte({"startSecond": 0, "endSecond": 50}, resumos)["theme"], "certo")
        self.assertIsNone(f._resumo_do_corte({"startSecond": 0, "endSecond": 50}, resumos[:1]))
        self.assertIsNone(f._resumo_do_corte({"label": "sem instante"}, resumos))


class AInstrucaoSoFalaDeFerramentasQuandoElasExistem(unittest.TestCase):
    def test_bloco_de_ferramentas_e_condicional(self):
        self.assertNotIn("FERRAMENTAS.", explica_clinico.instrucao())
        com = explica_clinico.instrucao(com_ferramentas=True)
        self.assertIn("FERRAMENTAS.", com)
        self.assertIn("ja pode ver no painel", com)


if __name__ == "__main__":
    unittest.main()
