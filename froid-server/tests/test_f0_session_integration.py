"""Integração da F0 real no estado da sessão: uma janela de PCM vozeado deve
aparecer no payload do tick como f0_mean/f0_var/f0_source, e o silêncio não
deve zerar a última medida válida."""
import math
import unittest

import numpy as np

import froid_f0
from froid_core import SessionState


def _pcm16(freq: float, sr: int, seconds: float) -> bytes:
    t = np.arange(int(sr * seconds)) / sr
    sig = np.sin(2 * math.pi * freq * t)
    return (sig * 30000).astype("<i2").tobytes()


class F0SessionIntegrationTests(unittest.TestCase):
    SR = 16000

    def _neutral_tick(self, state: SessionState):
        voice = np.clip(np.array([5.0] * 12), 0.5, 25.0)
        flags = {z: False for z in range(1, 13)}
        details = {z: None for z in range(1, 13)}
        return state.process_tick()

    def test_real_f0_flows_into_tick_payload(self):
        state = SessionState(session_id="s")
        signal = froid_f0.pcm16_bytes_to_float(_pcm16(165.0, self.SR, 1.0))
        f0_mean, f0_std, voiced = froid_f0.estimate_f0_series(signal, self.SR)
        state.update_f0(f0_mean, f0_std, voiced)
        audio = self._neutral_tick(state)["audio_meta"]
        self.assertLess(abs(audio["f0_mean"] - 165.0) / 165.0, 0.02)
        self.assertEqual(audio["f0_source"], "yin_pcm")
        self.assertGreater(audio["f0_voiced_ratio"], 0.9)

    def test_silence_preserves_last_valid_f0(self):
        state = SessionState(session_id="s")
        signal = froid_f0.pcm16_bytes_to_float(_pcm16(147.0, self.SR, 1.0))
        state.update_f0(*froid_f0.estimate_f0_series(signal, self.SR))
        before = state.latest_f0_mean
        # Silêncio => estimate retorna 0.0 => update_f0 não deve sobrescrever.
        state.update_f0(0.0, 0.0, 0.0)
        self.assertEqual(state.latest_f0_mean, before)

    def test_sem_audio_algum_a_ausencia_e_declarada(self):
        """Era `f0_source == "pending_audio"`, que dizia "ainda vai chegar".

        A distincao passou a importar: sem espectro medido o tick inteiro nao e
        apurado, e chamar isso de "pendente" sugeriria que os demais campos
        valiam enquanto se espera. Nao valiam — eram gerados.
        """
        state = SessionState(session_id="s")
        payload = self._neutral_tick(state)
        self.assertFalse(payload["apuracao_disponivel"])
        self.assertEqual(payload["audio_meta"]["f0_mean"], 0.0)
        self.assertEqual(payload["audio_meta"]["f0_source"], "sem_apuracao")

    def test_F0_medida_sobrevive_a_falta_de_espectro(self):
        """A regra corta dos DOIS lados: descartar medida existente seria
        inventar ausencia. A F0 chega por endpoint proprio."""
        state = SessionState(session_id="s")
        state.update_f0(172.0, 4.0, 0.8)
        payload = self._neutral_tick(state)
        self.assertFalse(payload["apuracao_disponivel"])
        self.assertEqual(payload["audio_meta"]["f0_source"], "yin_pcm")
        self.assertAlmostEqual(payload["audio_meta"]["f0_mean"], 172.0, places=1)


if __name__ == "__main__":
    unittest.main()
