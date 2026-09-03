"""Motor FACS real: blendshapes ARKit/MediaPipe -> Unidades de Ação -> dissonâncias
faciais por zona. Só marcações reais; padrões incompatíveis (ex.: sorriso sobre
compressão labial) caracterizam contradição facial-vocal."""
import math
import unittest

import numpy as np

import froid_facs
import froid_voice
from froid_core import SessionState
from froid_f0 import pcm16_bytes_to_float

SR = 16000


def injetar_voz_real(state: SessionState) -> None:
    """Da ao motor um espectro MEDIDO, como em producao.

    Ate 02/09/2026 estes testes rodavam sem voz alguma: o laco entregava um
    espectro gerado e o motor calculava zonas sobre ele. Com a simulacao
    proibida, um tick sem PCM medido nao produz zona nenhuma — corretamente —
    e um teste de dissonancia FACIAL-vocal precisa da metade vocal para ter o
    que contradizer.
    """
    t = np.arange(int(SR * 3.0)) / SR
    sig = sum((1.0 / k) * np.sin(2 * math.pi * 150.0 * k * t) for k in range(1, 13))
    sig = sig / np.max(np.abs(sig))
    pcm = (sig * 30000).astype("<i2").tobytes()
    buffer = state.ingest_pcm(pcm16_bytes_to_float(pcm), SR)
    state.update_voice_features(froid_voice.extract_voice_features(buffer, SR))


def neutral_face() -> dict:
    return {n: 0.0 for names in froid_facs.AU_BLENDSHAPES.values() for n in names}


class ActionUnitTests(unittest.TestCase):
    def test_no_blendshapes_no_aus(self):
        self.assertEqual(froid_facs.compute_action_units({}), {})

    def test_brow_lower_maps_to_au4(self):
        bs = neutral_face()
        bs["browDownLeft"] = 0.8
        bs["browDownRight"] = 0.6
        aus = froid_facs.compute_action_units(bs)
        self.assertAlmostEqual(aus["AU4"], 0.7, places=3)

    def test_smile_maps_to_au12(self):
        bs = neutral_face()
        bs["mouthSmileLeft"] = 0.5
        bs["mouthSmileRight"] = 0.5
        aus = froid_facs.compute_action_units(bs)
        self.assertAlmostEqual(aus["AU12"], 0.5, places=3)


class FacialDissonanceTests(unittest.TestCase):
    def test_suppressed_aversion_zone7(self):
        # Sorriso social (AU12) + compressão labial (AU24) = supressão de aversão.
        bs = neutral_face()
        bs["mouthSmileLeft"] = bs["mouthSmileRight"] = 0.6
        bs["mouthPressLeft"] = bs["mouthPressRight"] = 0.5
        result = froid_facs.process_facial_frame(bs)
        self.assertTrue(result["flags"][7])
        self.assertIn("AU12", result["details"][7]["active_aus"])
        self.assertIn("AU24", result["details"][7]["active_aus"])
        self.assertEqual(result["details"][7]["source"], "real_facs")
        self.assertEqual(result["facs_source"], "real_facs")

    def test_internal_conflict_zone12(self):
        bs = neutral_face()
        bs["browDownLeft"] = bs["browDownRight"] = 0.6
        bs["eyeSquintLeft"] = bs["eyeSquintRight"] = 0.5
        result = froid_facs.process_facial_frame(bs)
        self.assertTrue(result["flags"][12])
        self.assertEqual(set(result["details"][12]["active_aus"]), {"AU4", "AU7"})

    def test_neutral_face_no_dissonance(self):
        result = froid_facs.process_facial_frame(neutral_face())
        self.assertEqual(result["active_zones"], [])
        self.assertFalse(any(result["flags"].values()))

    def test_single_au_below_threshold_silent(self):
        # Um sorriso isolado (sem AU incompatível) não é dissonância.
        bs = neutral_face()
        bs["mouthSmileLeft"] = bs["mouthSmileRight"] = 0.7
        result = froid_facs.process_facial_frame(bs)
        self.assertFalse(any(result["flags"].values()))

    def test_details_have_no_internal_intensity_field(self):
        bs = neutral_face()
        bs["mouthSmileLeft"] = bs["mouthSmileRight"] = 0.6
        bs["mouthPressLeft"] = bs["mouthPressRight"] = 0.5
        result = froid_facs.process_facial_frame(bs)
        self.assertNotIn("intensity", result["details"][7])


class FacsSessionIntegrationTests(unittest.TestCase):
    def _neutral_tick(self, state):
        import numpy as np
        voice = np.ones(12) * 5.0
        flags = {z: False for z in range(1, 13)}
        details = {z: None for z in range(1, 13)}
        return state.process_tick()

    def test_real_facs_rege_o_tick(self):
        state = SessionState(session_id="s")
        injetar_voz_real(state)
        bs = neutral_face()
        bs["mouthSmileLeft"] = bs["mouthSmileRight"] = 0.6
        bs["mouthPressLeft"] = bs["mouthPressRight"] = 0.5
        state.update_facial_features(bs)
        payload = self._neutral_tick(state)
        self.assertEqual(payload["audio_meta"]["facs_source"], "real_facs")
        self.assertIsNotNone(payload["audio_meta"]["facial_action_units"])
        zone7 = next(z for z in payload["perception_zones"] if z["zone"] == 7)
        self.assertTrue(zone7["facial_dissonance_detected"])

    def test_facial_contradiction_feeds_dissonance_engine(self):
        state = SessionState(session_id="s")
        injetar_voz_real(state)
        bs = neutral_face()
        bs["mouthSmileLeft"] = bs["mouthSmileRight"] = 0.6
        bs["mouthPressLeft"] = bs["mouthPressRight"] = 0.5
        state.update_facial_features(bs)
        ev = self._neutral_tick(state)["dissonance_event"]
        keys = {m["key"] for m in ev["evident_markers"]}
        self.assertIn("facial_contradiction", keys)

    def test_sem_face_o_motor_declara_ausencia(self):
        """Era `facs_source == "mock"`, e o mock nao era inerte: as flags
        SORTEADAS regiam o multiplicador 2.5, o dna_flooding e o dna_somato, com
        texto clinico pronto que chegava a tela sem marca de origem."""
        state = SessionState(session_id="s")
        injetar_voz_real(state)
        payload = self._neutral_tick(state)
        self.assertEqual(payload["audio_meta"]["facs_source"], "sem_apuracao")
        self.assertIsNone(payload["audio_meta"]["facial_action_units"])
        # E sem face nenhuma zona pode acusar dissonancia FACIAL.
        for zona in payload["perception_zones"]:
            self.assertFalse(zona["facial_dissonance_detected"])

    def test_face_medida_sem_voz_nao_e_apagada(self):
        """A regra corta dos dois lados: apurar e nao informar tambem e
        defeito. Sem voz nao ha zona contra a qual contradizer, mas a leitura
        facial foi feita e isso e dito."""
        state = SessionState(session_id="s")
        bs = neutral_face()
        bs["mouthSmileLeft"] = bs["mouthSmileRight"] = 0.6
        state.update_facial_features(bs)
        payload = self._neutral_tick(state)
        self.assertFalse(payload["apuracao_disponivel"])
        self.assertTrue(payload["audio_meta"]["facial_real"])
        self.assertEqual(payload["audio_meta"]["facs_source"], "real_facs")
        self.assertIn("referencia vocal", payload["motivo_sem_apuracao"])


if __name__ == "__main__":
    unittest.main()
