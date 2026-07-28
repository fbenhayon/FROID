"""Integração dos biomarcadores vocais reais no tick da sessão: com features
reais injetadas, o payload passa a refletir a voz medida (voice_features_source
= real_pcm), e sem elas mantém o modo simulado."""
import math
import unittest

import numpy as np

import froid_voice
from froid_core import SessionState
from froid_f0 import pcm16_bytes_to_float


SR = 16000


def glottal_pcm(f0: float, seconds: float) -> bytes:
    t = np.arange(int(SR * seconds)) / SR
    sig = sum((1.0 / k) * np.sin(2 * math.pi * f0 * k * t) for k in range(1, 13))
    sig = sig / np.max(np.abs(sig))
    return (sig * 30000).astype("<i2").tobytes()


def neutral_tick(state: SessionState):
    voice = np.ones(12) * 5.0
    flags = {z: False for z in range(1, 13)}
    details = {z: None for z in range(1, 13)}
    return state.process_tick(voice, flags, details)


class VoiceSessionIntegrationTests(unittest.TestCase):
    def test_real_markers_flow_into_tick(self):
        state = SessionState(session_id="s")
        buffer = state.ingest_pcm(pcm16_bytes_to_float(glottal_pcm(150.0, 3.0)), SR)
        state.update_voice_features(froid_voice.extract_voice_features(buffer, SR))
        audio = neutral_tick(state)["audio_meta"]
        self.assertEqual(audio["voice_features_source"], "real_pcm")
        self.assertLess(abs(audio["f0_mean"] - 150.0) / 150.0, 0.02)
        # MFCC reais podem ser negativos (o proxy antigo era sempre >= 0).
        self.assertTrue(isinstance(audio["mfcc7"], float))
        self.assertIsNotNone(audio["zcr"])
        self.assertIsNotNone(audio["loudness_dbfs"])
        self.assertLess(audio["loudness_dbfs"], 0.0)

    def test_mock_mode_without_features(self):
        state = SessionState(session_id="s")
        audio = neutral_tick(state)["audio_meta"]
        self.assertEqual(audio["voice_features_source"], "mock")
        self.assertIsNone(audio["zcr"])

    def test_real_voice_spectral_drives_zones(self):
        state = SessionState(session_id="s")
        buffer = state.ingest_pcm(pcm16_bytes_to_float(glottal_pcm(150.0, 3.0)), SR)
        feats = froid_voice.extract_voice_features(buffer, SR)
        state.update_voice_features(feats)
        payload = neutral_tick(state)
        # O vetor real de 12 bandas (não o mock) deve reger as zonas.
        self.assertEqual(len(payload["perception_zones"]), 12)
        self.assertIn("voice_spectral_12", feats)
        self.assertEqual(len(feats["voice_spectral_12"]), 12)


if __name__ == "__main__":
    unittest.main()
