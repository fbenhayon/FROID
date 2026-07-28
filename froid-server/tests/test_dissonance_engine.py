"""Motor de dissonâncias evidentes: cada marcador real tem uma métrica base
(banda mín/máx); só quando DUAS OU MAIS ultrapassam simultaneamente o evento é
sinalizado (is_multi_dissonance) para a listagem detalhada."""
import math
import unittest

import numpy as np

import froid_dissonance
import froid_voice
from froid_core import SessionState
from froid_f0 import pcm16_bytes_to_float

SR = 16000


def glottal_pcm(f0: float, seconds: float, amp: float = 30000.0) -> bytes:
    t = np.arange(int(SR * seconds)) / SR
    sig = sum((1.0 / k) * np.sin(2 * math.pi * f0 * k * t) for k in range(1, 13))
    sig = sig / np.max(np.abs(sig))
    return (sig * amp).astype("<i2").tobytes()


def neutral_tick(state: SessionState):
    voice = np.ones(12) * 5.0
    flags = {z: False for z in range(1, 13)}
    details = {z: None for z in range(1, 13)}
    return state.process_tick(voice, flags, details)


class DissonanceEngineUnitTests(unittest.TestCase):
    def test_single_breach_is_not_multi(self):
        snap = {
            "voice_real": True,
            "baseline_locked": True,
            "jitter": 0.5,  # muito acima de 0.02
            "shimmer": 0.0,
            "f0_mean": 150.0,
            "f0_var": 15.0,  # CV 0.1 -> dentro da banda
            "baseline_f0": 150.0,
            "loudness_dbfs": -20.0,
            "baseline_loudness": -20.0,
            "zcr": 0.05,
            "baseline_zcr": 0.05,
            "mfcc7_delta_delta": 0.0,
            "mfcc9_delta_delta": 0.0,
            "dna_autonomic_flooding": 0.0,
            "dna_dissociative_shutdown": 0.0,
            "dna_somatoaffective_dissonance": 0.0,
            "zone_deviations": [0.0] * 12,
            "ipm_score": 10.0,
        }
        ev = froid_dissonance.evaluate(snap)
        self.assertEqual(ev["evident_count"], 1)
        self.assertFalse(ev["is_multi_dissonance"])
        self.assertEqual(ev["summary"], "")

    def test_two_breaches_flag_multi(self):
        snap = {
            "voice_real": True,
            "baseline_locked": True,
            "jitter": 0.5,  # breach
            "shimmer": 0.5,  # breach
            "f0_mean": 150.0,
            "f0_var": 15.0,
            "baseline_f0": 150.0,
            "loudness_dbfs": -20.0,
            "baseline_loudness": -20.0,
            "zcr": 0.05,
            "baseline_zcr": 0.05,
            "mfcc7_delta_delta": 0.0,
            "mfcc9_delta_delta": 0.0,
            "dna_autonomic_flooding": 0.0,
            "dna_dissociative_shutdown": 0.0,
            "dna_somatoaffective_dissonance": 0.0,
            "zone_deviations": [0.0] * 12,
            "ipm_score": 10.0,
        }
        ev = froid_dissonance.evaluate(snap)
        self.assertGreaterEqual(ev["evident_count"], 2)
        self.assertTrue(ev["is_multi_dissonance"])
        self.assertIn("métrica base", ev["summary"])
        keys = {m["key"] for m in ev["evident_markers"]}
        self.assertIn("jitter", keys)
        self.assertIn("shimmer", keys)

    def test_voice_markers_gated_on_real(self):
        # Com voz simulada (voice_real False), jitter/shimmer altos NÃO contam.
        snap = {
            "voice_real": False,
            "baseline_locked": True,
            "jitter": 0.9,
            "shimmer": 0.9,
            "f0_mean": 0.0,
            "f0_var": 0.0,
            "baseline_f0": 0.0,
            "loudness_dbfs": None,
            "baseline_loudness": None,
            "zcr": None,
            "baseline_zcr": 0.0,
            "mfcc7_delta_delta": 5.0,
            "mfcc9_delta_delta": 5.0,
            "dna_autonomic_flooding": 0.0,
            "dna_dissociative_shutdown": 0.0,
            "dna_somatoaffective_dissonance": 0.0,
            "zone_deviations": [0.0] * 12,
            "ipm_score": 10.0,
        }
        ev = froid_dissonance.evaluate(snap)
        keys = {m["key"] for m in ev["evident_markers"]}
        self.assertNotIn("jitter", keys)
        self.assertNotIn("shimmer", keys)
        self.assertNotIn("mfcc9_spastic", keys)

    def test_baseline_relative_ignored_without_baseline(self):
        snap = {
            "voice_real": True,
            "baseline_locked": False,  # sem baseline travada
            "jitter": 0.0,
            "shimmer": 0.0,
            "f0_mean": 300.0,
            "f0_var": 15.0,
            "baseline_f0": 150.0,
            "loudness_dbfs": -5.0,
            "baseline_loudness": -30.0,
            "zcr": 0.2,
            "baseline_zcr": 0.05,
            "mfcc7_delta_delta": 0.0,
            "mfcc9_delta_delta": 0.0,
            "dna_autonomic_flooding": 0.0,
            "dna_dissociative_shutdown": 0.0,
            "dna_somatoaffective_dissonance": 0.0,
            "zone_deviations": [0.0] * 12,
            "ipm_score": 10.0,
        }
        ev = froid_dissonance.evaluate(snap)
        keys = {m["key"] for m in ev["evident_markers"]}
        # Marcadores relativos à baseline não disparam sem referência travada.
        self.assertNotIn("f0_baseline_dev", keys)
        self.assertNotIn("loudness_dev", keys)
        self.assertNotIn("zcr_dev", keys)

    def test_dna_and_structural_always_evaluated(self):
        snap = {
            "voice_real": False,
            "baseline_locked": True,
            "jitter": 0.0,
            "shimmer": 0.0,
            "f0_mean": 0.0,
            "f0_var": 0.0,
            "baseline_f0": 0.0,
            "loudness_dbfs": None,
            "baseline_loudness": None,
            "zcr": None,
            "baseline_zcr": 0.0,
            "mfcc7_delta_delta": 0.0,
            "mfcc9_delta_delta": 0.0,
            "dna_autonomic_flooding": 0.9,  # breach
            "dna_dissociative_shutdown": 0.0,
            "dna_somatoaffective_dissonance": 0.0,
            "zone_deviations": [0.0] * 11 + [4.0],  # breach extremo
            "ipm_score": 95.0,  # breach IPM
        }
        ev = froid_dissonance.evaluate(snap)
        keys = {m["key"] for m in ev["evident_markers"]}
        self.assertIn("dna_flooding", keys)
        self.assertIn("zone_extreme", keys)
        self.assertIn("ipm_hyper", keys)
        self.assertTrue(ev["is_multi_dissonance"])


class DissonanceSessionIntegrationTests(unittest.TestCase):
    def test_tick_payload_includes_event(self):
        state = SessionState(session_id="s")
        payload = neutral_tick(state)
        self.assertIn("dissonance_event", payload)
        ev = payload["dissonance_event"]
        self.assertIn("is_multi_dissonance", ev)
        self.assertIn("evident_markers", ev)
        self.assertIn("peak_zone", ev)

    def test_healthy_voice_no_multi_dissonance(self):
        state = SessionState(session_id="s")
        buf = state.ingest_pcm(pcm16_bytes_to_float(glottal_pcm(150.0, 3.0)), SR)
        state.update_voice_features(froid_voice.extract_voice_features(buf, SR))
        ev = neutral_tick(state)["dissonance_event"]
        self.assertEqual(ev["voice_features_source"], "real_pcm")
        # Voz limpa e periódica não deve gerar dissonância múltipla.
        self.assertFalse(ev["is_multi_dissonance"])


if __name__ == "__main__":
    unittest.main()
