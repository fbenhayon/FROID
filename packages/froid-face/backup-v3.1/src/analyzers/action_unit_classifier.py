"""
FROID Face - Classificador de Action Units
Estima intensidade de AUs a partir de distâncias geométricas entre landmarks

Escala de intensidade A-E:
A: 0.1-0.2 (traço), B: 0.2-0.4 (leve), C: 0.4-0.6 (marcado),
D: 0.6-0.8 (severo), E: 0.8-1.0 (máximo)
"""

import numpy as np
from typing import Dict, List, Optional
from src.config import DEFAULT_THRESHOLDS, INTENSITY_SCALE
from src.facs.au_definitions import AU_DEFINITIONS, RELIABLE_MUSCLES, VOLUNTARY_MUSCLES


class ActionUnitClassifier:
    """
    Classifica Action Units baseado em distâncias geométricas entre landmarks.
    Usa heurísticas calibradas para MediaPipe 468 pontos.
    """

    def __init__(self):
        self.activation_threshold = DEFAULT_THRESHOLDS["au_activation_threshold"]
        # Calibração de repouso (atualizada por sessão)
        self.baseline_distances: Optional[Dict[str, float]] = None

    def set_baseline(self, distances: Dict[str, float]):
        """Define distâncias de repouso para normalização relativa."""
        self.baseline_distances = distances

    def classify(self, au_distances: Dict[str, float]) -> List[Dict]:
        """
        Classifica AUs ativas a partir das distâncias entre landmarks.

        Args:
            au_distances: Distâncias calculadas pelo LandmarkExtractor

        Returns:
            Lista de AUs ativas com intensidade e classificação
        """
        active_aus = []

        # Normalizar contra baseline se disponível
        if self.baseline_distances:
            norm_distances = {}
            for k, v in au_distances.items():
                baseline = self.baseline_distances.get(k, v)
                if baseline > 0.001:
                    norm_distances[k] = (v - baseline) / baseline
                else:
                    norm_distances[k] = 0.0
        else:
            norm_distances = au_distances

        # AU1: Inner Brow Raiser (sobrancelha interna elevada)
        brow_raise = abs(norm_distances.get("brow_height_left", 0))
        if brow_raise > 0.05:
            intensity = min(1.0, brow_raise / 0.15)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(1, intensity))

        # AU4: Brow Lowerer (sobrancelha abaixada)
        brow_lower = -norm_distances.get("brow_height_left", 0)
        if brow_lower > 0.03:
            intensity = min(1.0, brow_lower / 0.12)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(4, intensity))

        # AU5: Upper Lid Raiser (pálpebra superior elevada)
        eye_open_l = norm_distances.get("eye_open_left", 0)
        if eye_open_l > 0.05:
            intensity = min(1.0, eye_open_l / 0.15)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(5, intensity))

        # AU6: Cheek Raiser (bochechas elevadas - sorriso Duchenne)
        # Detectado quando olho se fecha ligeiramente + boca sorri
        eye_squeeze = -norm_distances.get("eye_open_left", 0)
        mouth_w = norm_distances.get("mouth_width", 0)
        if eye_squeeze > 0.02 and mouth_w > 0.03:
            intensity = min(1.0, (eye_squeeze + mouth_w) / 0.15)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(6, intensity))

        # AU7: Lid Tightener
        if eye_squeeze > 0.03:
            intensity = min(1.0, eye_squeeze / 0.10)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(7, intensity))

        # AU9: Nose Wrinkler
        nose_dist = norm_distances.get("upper_lip_nose", 0)
        if nose_dist < -0.03:
            intensity = min(1.0, abs(nose_dist) / 0.10)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(9, intensity))

        # AU12: Lip Corner Puller (sorriso)
        if mouth_w > 0.05:
            intensity = min(1.0, mouth_w / 0.15)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(12, intensity))

        # AU15: Lip Corner Depressor (tristeza)
        if mouth_w < -0.03:
            intensity = min(1.0, abs(mouth_w) / 0.12)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(15, intensity))

        # AU17: Chin Raiser
        chin = norm_distances.get("chin_height", 0)
        if chin < -0.03:
            intensity = min(1.0, abs(chin) / 0.10)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(17, intensity))

        # AU20: Lip Stretcher
        if mouth_w > 0.04 and norm_distances.get("mouth_open", 0) < 0.01:
            intensity = min(1.0, mouth_w / 0.12)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(20, intensity))

        # AU25: Lips Part
        mouth_open = norm_distances.get("mouth_open", 0)
        if mouth_open > 0.02:
            intensity = min(1.0, mouth_open / 0.08)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(25, intensity))

        # AU26: Jaw Drop
        if mouth_open > 0.06:
            intensity = min(1.0, mouth_open / 0.15)
            if intensity > self.activation_threshold:
                active_aus.append(self._make_au(26, intensity))

        return active_aus

    def _make_au(self, au_number: int, intensity: float) -> Dict:
        """Cria dicionário de AU com metadados."""
        au_def = AU_DEFINITIONS.get(au_number, {})
        intensity_label = self._intensity_to_scale(intensity)
        is_reliable = au_number in RELIABLE_MUSCLES

        return {
            "au_number": au_number,
            "au_name": au_def.get("name", f"AU{au_number}"),
            "muscle": au_def.get("muscle", "Unknown"),
            "intensity": round(intensity, 3),
            "intensity_scale": intensity_label,
            "confidence": round(min(1.0, intensity * 1.2), 3),
            "is_reliable": is_reliable,
            "muscle_type": "involuntary" if is_reliable else "voluntary",
        }

    def _intensity_to_scale(self, intensity: float) -> str:
        """Converte intensidade numérica para escala FACS A-E."""
        for label, (low, high, _) in INTENSITY_SCALE.items():
            if low <= intensity < high:
                return label
        return "E" if intensity >= 0.8 else "A"
