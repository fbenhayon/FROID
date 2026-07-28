"""Motor FACS real: blendshapes ARKit/MediaPipe -> Unidades de Ação -> dissonâncias
faciais por zona. Só marcações reais; padrões incompatíveis (ex.: sorriso sobre
compressão labial) caracterizam contradição facial-vocal."""
import unittest

import froid_facs
from froid_core import SessionState


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
        return state.process_tick(voice, flags, details)

    def test_real_facs_overrides_mock_in_tick(self):
        state = SessionState(session_id="s")
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
        bs = neutral_face()
        bs["mouthSmileLeft"] = bs["mouthSmileRight"] = 0.6
        bs["mouthPressLeft"] = bs["mouthPressRight"] = 0.5
        state.update_facial_features(bs)
        ev = self._neutral_tick(state)["dissonance_event"]
        keys = {m["key"] for m in ev["evident_markers"]}
        self.assertIn("facial_contradiction", keys)

    def test_no_face_stays_mock(self):
        state = SessionState(session_id="s")
        payload = self._neutral_tick(state)
        self.assertEqual(payload["audio_meta"]["facs_source"], "mock")
        self.assertIsNone(payload["audio_meta"]["facial_action_units"])


if __name__ == "__main__":
    unittest.main()
