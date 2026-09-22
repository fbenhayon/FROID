"""PCM -> rota real -> estado -> diagnóstico, sem servidor nem dados clínicos.

Executa as definições reais da rota via AST para não inicializar serviços,
credenciais ou banco de produção. A DSP e SessionState não são substituídos.
"""
import ast
import asyncio
import base64
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Optional
import unittest
from unittest.mock import patch

import numpy as np
import froid_f0
import froid_voice
from froid_core import SessionState


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Request:
    query_params = {}

    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


def carregar_rota(state):
    path = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name in {"_sanitized_acoustic_capture", "submit_acoustic_f0"}]
    assert len(nodes) == 2
    for node in nodes:
        node.decorator_list = []
    scope = dict(Request=Request, Optional=Optional, HTTPException=HTTPException,
                 asyncio=asyncio, base64=base64, re=re,
                 froid_f0=froid_f0, froid_voice=froid_voice,
                 SESSION_INVITES={"convite-de-teste": {"status": "accepted", "session_id": "teste"}},
                 SESSION_OWNERS={}, _current_user_from_request=lambda request: None,
                 _normalize_email=lambda email: email.strip().lower(),
                 _rate_limit_guard=lambda *args: None,
                 manager=SimpleNamespace(state_for=lambda session_id: state))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)
    return scope["submit_acoustic_f0"]


def body_pcm(sequence=1, signal=None, stream="captura-teste"):
    if signal is None:
        t = np.arange(16000) / 16000
        signal = 0.3 * np.sin(2 * np.pi * 150 * t)
    return dict(invite="convite-de-teste", sample_rate=16000,
                pcm_base64=base64.b64encode((signal * 32767).astype("<i2").tobytes()).decode(),
                capture_stream_id=stream, capture_sequence=sequence,
                captura_cliente=dict(mesmo_dispositivo=True, audio_bruto=False, canais=2,
                    taxa_amostragem=48000, echo_cancellation=True, noise_suppression=False,
                    auto_gain_control=None, deviceId="nao-deve-sair", label="nao-deve-sair"))


class AcousticTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state = SessionState(session_id="teste")
        self.route = carregar_rota(self.state)

    async def submit(self, body):
        return await self.route("teste", Request(body))

    async def test_fala_atual_nao_e_diluida_por_pausas_anteriores(self):
        await self.submit(body_pcm(1, np.zeros(16000)))
        await self.submit(body_pcm(2, np.zeros(16000)))
        t = np.arange(16000) / 16000
        signal = 0.04 * np.sin(2 * np.pi * 205 * t)
        signal[(t < 0.3) | (t >= 0.7)] = 0
        result = await self.submit(body_pcm(3, signal))
        self.assertEqual(result['source'], 'real_pcm')
        d = result['diagnostico_acustico']
        self.assertGreaterEqual(d['f0_voiced_ratio'], 0.3)
        self.assertLess(d['f0_voiced_ratio'], 0.6)
        result = await self.submit(body_pcm(4, np.zeros(16000)))
        self.assertEqual(result['source'], 'sem_apuracao')
        self.assertEqual(result['diagnostico_acustico']['f0_voiced_ratio'], 0)

    async def test_dados_do_microfone_atravessam_rota_e_tick_sem_identificadores(self):
        body = body_pcm()
        result = await self.submit(body)
        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["source"], "real_pcm")
        diagnostic = result["diagnostico_acustico"]
        expected = {k: v for k, v in body["captura_cliente"].items() if k not in {"deviceId", "label"}}
        self.assertEqual(diagnostic["captura_cliente"], expected)
        self.assertEqual(diagnostic["sample_rate_hz"], 16000)
        self.assertGreater(diagnostic["rms"], 0)
        tick = self.state.process_tick()
        self.assertEqual(tick["audio_meta"]["diagnostico_acustico"]["captura_cliente"], expected)

    async def test_silencio_novo_nao_preserva_f0_anterior(self):
        await self.submit(body_pcm())
        self.assertGreater(self.state.latest_f0_mean, 0)
        result = await self.submit(body_pcm(3, np.zeros(16000)))  # lacuna reinicia janela
        self.assertEqual(result["source"], "sem_apuracao")
        d = result["diagnostico_acustico"]
        self.assertEqual(d["estado"], "sem_vozeamento")
        self.assertEqual(d["rms"], 0)
        self.assertEqual(d["f0_voiced_ratio"], 0)
        self.assertIsNone(d["loudness_dbfs"])
        self.assertIsNone(result["f0_mean"])
        self.assertEqual(self.state.process_tick()["audio_meta"]["f0_source"], "sem_apuracao")

    async def test_duplicata_recusada_sem_alterar_medida_corrente(self):
        await self.submit(body_pcm())
        revision = self.state.pcm_revision
        with self.assertRaises(HTTPException) as error:
            await self.submit(body_pcm())
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.state.pcm_revision, revision)

    async def test_pcm_impar_rejeitado_sem_iniciar_dsp(self):
        body = body_pcm()
        body["pcm_base64"] = base64.b64encode(b"x").decode()
        with self.assertRaises(HTTPException) as error:
            await self.submit(body)
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.state.pcm_revision, 0)

    async def test_nao_autorizado_nao_alimenta_sessao(self):
        body = body_pcm()
        body["invite"] = "invalido"
        with self.assertRaises(HTTPException) as error:
            await self.submit(body)
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(self.state.pcm_revision, 0)

    async def test_diagnostico_nao_inventa_configuracao_ausente(self):
        body = body_pcm()
        del body["captura_cliente"]
        result = await self.submit(body)
        self.assertIsNone(result["diagnostico_acustico"]["captura_cliente"])

    async def test_sessao_inativa_nao_declara_medicao(self):
        result = await carregar_rota(None)("teste", Request(body_pcm()))
        self.assertEqual(result["status"], "session_inactive")
        self.assertIsNone(result["f0_mean"])


class AcousticFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.state = SessionState(session_id="teste")

    def ingest(self, sequence, stream="a", sr=16000):
        return self.state.ingest_pcm(np.ones(160), sr, capture_stream_id=stream, capture_sequence=sequence)

    def test_janela_nova_nao_herda_diagnostico_enquanto_dsp_pendente(self):
        self.ingest(1)
        self.state.update_voice_features({"rms": 0.2, "f0_mean": 150, "f0_voiced_ratio": 1})
        self.ingest(2)
        d = self.state.acoustic_diagnostics()
        self.assertEqual(d["estado"], "analisando")
        self.assertIsNone(d["rms"])
        self.assertIsNone(d["f0_voiced_ratio"])

    def test_resultado_antigo_nao_substitui_janela_nova(self):
        self.ingest(1)
        anterior = self.state.pcm_revision
        self.ingest(2)
        self.assertFalse(self.state.update_voice_features({"f0_mean": 150}, pcm_revision=anterior))
        self.assertEqual(self.state.acoustic_diagnostics()["estado"], "analisando")

    def test_valor_vencido_nao_aparece_como_diagnostico_atual(self):
        self.ingest(1)
        self.state.update_voice_features({"rms": 0.2, "f0_mean": 150, "f0_voiced_ratio": 1})
        with patch("froid_core.time.time", return_value=self.state.pcm_received_at + self.state.VALIDADE_VOZ_S + 1):
            d = self.state.acoustic_diagnostics()
            self.assertEqual(d["estado"], "sem_audio")
            self.assertIsNone(d["rms"])
            self.assertIsNone(d["f0_voiced_ratio"])

    def test_buffer_respeita_continuidade_taxa_e_stream(self):
        self.assertEqual(self.ingest(1).size, 160)
        self.assertEqual(self.ingest(2).size, 320)
        self.assertEqual(self.ingest(4).size, 160)
        self.assertEqual(self.ingest(5, sr=48000).size, 160)
        self.assertEqual(self.ingest(1, stream="b", sr=48000).size, 160)

    def test_vozeamento_zero_nao_usa_razao_positiva_antiga(self):
        self.state.update_f0(150, 1, 1)
        self.state.update_voice_features({"voice_spectral_12": [1] * 12, "f0_voiced_ratio": 0})
        self.assertFalse(self.state.process_tick()["apuracao_disponivel"])


if __name__ == "__main__":
    unittest.main()
