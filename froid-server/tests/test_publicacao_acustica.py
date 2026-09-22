"""Concorrencia real entre recepcao PCM, DSP em thread e envio ao painel."""
import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

import froid_voice
from tests.test_acoustic_transport_contract import AcousticTransportTests, body_pcm

class PublicacaoAcusticaTests(AcousticTransportTests):
    async def test_tick_aguarda_dsp_em_andamento_sem_publicar_ausencia_transitoria(self):
        started = threading.Event()
        release = threading.Event()
        delivered = asyncio.Event()
        payloads = []
        original = froid_voice.extract_voice_features
        def blocked(*args, **kwargs):
            started.set()
            if not release.wait(5):
                raise TimeoutError("teste nao liberou DSP")
            return original(*args, **kwargs)
        async def broadcast(session_id, payload):
            payloads.append(payload)
            delivered.set()
        manager = SimpleNamespace(active_sessions={"teste": {"state": self.state}},
            is_current=lambda *args: True, broadcast_payload=broadcast)
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "froid_stream_loop")
        scope = dict(manager=manager, asyncio=asyncio, STREAM_LOGGER=logging.getLogger("test"))
        exec(compile(ast.Module(body=[node], type_ignores=[]), "main.py", "exec"), scope)
        loop_task = None
        with patch.object(froid_voice, "extract_voice_features", blocked):
            request_task = asyncio.create_task(self.submit(body_pcm()))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                loop_task = asyncio.create_task(scope["froid_stream_loop"]("teste", "conexao"))
                await asyncio.sleep(0.05)
                self.assertEqual(payloads, [], "nao publicar ausencia enquanto DSP calcula a janela recebida")
                release.set()
                await request_task
                await asyncio.wait_for(delivered.wait(), 2)
                # `apuracao_disponivel` so EXISTE no payload de ausencia, com
                # valor False — o payload medido nao carrega a chave. Era por
                # isso que a versao anterior desta linha levantava KeyError
                # contra um tique perfeitamente medido: ela afirmava um
                # contrato que o motor nao tem. Quem confere ausencia compara
                # com False, como o painel faz em `apuracao_disponivel ===
                # false`; quem confere medida le os marcadores de procedencia.
                medido = payloads[0]
                self.assertIsNot(medido.get("apuracao_disponivel"), False,
                    "apos a DSP, o tique publica medida — nao ausencia")
                self.assertEqual(medido["audio_meta"]["estado_da_captura"], "medida")
                self.assertEqual(medido["audio_meta"]["voice_features_source"], "real_pcm")
            finally:
                release.set()
                await request_task
                if loop_task:
                    loop_task.cancel()
                    try:
                        await loop_task
                    except asyncio.CancelledError:
                        pass

if __name__ == "__main__":
    unittest.main()
