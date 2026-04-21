"""
FROID Face - Analisador de Assimetria (D-face / S-face)
Baseado em [FACTS4.pdf] Liu et al. + [FACTS3.pdf] thresholds

D-face: D(x,y) = |I(x,y) - I'(x,y)| — diferença de intensidade bilateral
S-face: S(x,y) = cos(θ_Ie, θ_I'e) — similaridade de orientação de bordas
"""

import cv2
import numpy as np
from typing import Dict, List
from src.config import DEFAULT_THRESHOLDS, CONDITION_MULTIPLIERS


class AsymmetryAnalyzer:
    """
    Calcula assimetria facial D-face e S-face para detecção clínica.
    Thresholds baseados em [FACTS3.pdf]:
    - Eyelid ≥2mm → >90% detecção humana
    - Smile ≥3mm → >90% detecção humana
    - Brow 1-6mm → 23%-97% detecção progressiva
    """

    def __init__(self):
        self.scale_factor = 0.15  # mm/pixel calibrado para resolução padrão

    def analyze(self, frame_gray: np.ndarray, points_px: np.ndarray,
                thresholds: Dict = None, condition: str = "none") -> Dict:
        """
        Analisa assimetria facial completa.

        Args:
            frame_gray: Frame em escala de cinza
            points_px: Landmarks em pixels (468 pontos)
            thresholds: Thresholds personalizados (opcional)
            condition: Condição clínica para ajuste de thresholds

        Returns:
            Dict com scores de assimetria, flags clínicos e D-face/S-face
        """
        if frame_gray is None or points_px is None:
            return self._empty_result()

        th = thresholds or DEFAULT_THRESHOLDS

        # Ajustar thresholds por condição clínica
        multipliers = CONDITION_MULTIPLIERS.get(condition, CONDITION_MULTIPLIERS["none"])

        try:
            # 1. Normalizar face (crop + resize 128x128)
            normalized = self._normalize_face(frame_gray, points_px)
            if normalized is None:
                return self._empty_result()

            # 2. Calcular D-face e S-face
            d_face, s_face = self._compute_d_s_face(normalized)

            # 3. Assimetria regional em mm
            brow_mm = float(np.mean(np.abs(d_face[15:35, :]))) * self.scale_factor
            eye_mm = float(np.mean(np.abs(d_face[40:60, :]))) * self.scale_factor
            mouth_mm = float(np.mean(np.abs(d_face[90:110, :]))) * self.scale_factor

            # 4. Scores globais
            d_face_global = float(np.mean(np.abs(d_face)))
            s_face_global = float(np.mean(s_face))

            # 5. Delay hemifacial (baseado em landmarks)
            hemifacial_delay_ms = self._compute_hemifacial_delay(points_px)

            # 6. Flags clínicos
            flags = self._evaluate_flags(
                brow_mm, eye_mm, mouth_mm, hemifacial_delay_ms,
                th, multipliers
            )

            # 7. Unnaturalness score (Likert 1-5) [FACTS3.pdf]
            max_asym = max(eye_mm, mouth_mm, brow_mm)
            unnaturalness = min(5, int(max_asym / 1.2) + 1)

            return {
                "brow_asymmetry_mm": round(brow_mm, 2),
                "eye_asymmetry_mm": round(eye_mm, 2),
                "mouth_asymmetry_mm": round(mouth_mm, 2),
                "d_face_global": round(d_face_global, 4),
                "s_face_global": round(s_face_global, 4),
                "hemifacial_delay_ms": hemifacial_delay_ms,
                "unnaturalness_score": unnaturalness,
                "clinical_flags": flags,
                "condition_applied": condition,
            }

        except Exception as e:
            print(f"[AsymmetryAnalyzer] Erro: {e}")
            return self._empty_result()

    def _normalize_face(self, gray: np.ndarray, points: np.ndarray) -> np.ndarray:
        """Normalização afim via 3 pontos [FACTS4.pdf, Fig. 2]."""
        try:
            # C1: canto interno olho esq, C2: canto interno olho dir, C3: ponta do nariz
            c1 = points[133][:2].astype(np.float32)
            c2 = points[362][:2].astype(np.float32)
            c3 = points[4][:2].astype(np.float32)

            src_tri = np.array([c1, c2, c3], dtype=np.float32)
            dst_tri = np.array([[40, 48], [88, 48], [64, 84]], dtype=np.float32)

            warp_mat = cv2.getAffineTransform(src_tri, dst_tri)
            return cv2.warpAffine(gray, warp_mat, (128, 128))
        except Exception:
            return None

    def _compute_d_s_face(self, normalized: np.ndarray):
        """
        Calcula D-face e S-face [FACTS4.pdf, Eq. 1-2].
        D-face: diferença de intensidade bilateral
        S-face: similaridade de orientação de bordas (cosseno)
        """
        I = normalized.astype(np.float32) / 255.0
        I_ref = np.fliplr(I)

        # D-face: |I - I'|
        d_face = I - I_ref

        # S-face: cos(θ, θ')
        grad_x = cv2.Sobel(normalized, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(normalized, cv2.CV_64F, 0, 1, ksize=3)
        theta = np.arctan2(grad_y, grad_x)

        grad_x_ref = -np.fliplr(grad_x)  # Inverter X para espelhamento
        grad_y_ref = np.fliplr(grad_y)
        theta_ref = np.arctan2(grad_y_ref, grad_x_ref)

        s_face = np.cos(theta - theta_ref)

        return d_face, s_face

    def _compute_hemifacial_delay(self, points: np.ndarray) -> int:
        """Estima delay hemifacial baseado em assimetria de landmarks."""
        # Simplificação: usar diferença de posição vertical entre landmarks simétricos
        left_mouth = points[61][:2]
        right_mouth = points[291][:2]
        diff = abs(left_mouth[1] - right_mouth[1])
        # Mapear diferença para ms (aproximação)
        return int(diff * 100)  # Fator empírico

    def _evaluate_flags(self, brow_mm, eye_mm, mouth_mm, delay_ms,
                        thresholds, multipliers) -> List[Dict]:
        """Aplica thresholds de percepção humana [FACTS3.pdf]."""
        flags = []

        eye_th = thresholds["eyelid_threshold_mm"] * multipliers["eyelid"]
        if eye_mm >= eye_th:
            flags.append({
                "flag_type": "asymmetry",
                "region": "eyelid",
                "severity": "high",
                "value_mm": eye_mm,
                "threshold_mm": eye_th,
                "description": f"Assimetria palpebral {eye_mm:.1f}mm (threshold: {eye_th:.1f}mm)",
            })

        smile_th = thresholds["smile_threshold_mm"] * multipliers["smile"]
        if mouth_mm >= smile_th:
            flags.append({
                "flag_type": "asymmetry",
                "region": "smile",
                "severity": "high",
                "value_mm": mouth_mm,
                "threshold_mm": smile_th,
                "description": f"Assimetria de sorriso {mouth_mm:.1f}mm (threshold: {smile_th:.1f}mm)",
            })

        brow_th = thresholds["brow_threshold_mm"] * multipliers["brow"]
        if brow_mm >= brow_th:
            flags.append({
                "flag_type": "asymmetry",
                "region": "brow",
                "severity": "medium",
                "value_mm": brow_mm,
                "threshold_mm": brow_th,
                "description": f"Assimetria de sobrancelha {brow_mm:.1f}mm (threshold: {brow_th:.1f}mm)",
            })

        if delay_ms >= thresholds["incongruence_delay_ms"]:
            flags.append({
                "flag_type": "temporal_anomaly",
                "region": "hemifacial",
                "severity": "medium",
                "value_ms": delay_ms,
                "threshold_ms": thresholds["incongruence_delay_ms"],
                "description": f"Delay hemifacial {delay_ms}ms (threshold: {thresholds['incongruence_delay_ms']}ms)",
            })

        return flags

    def _empty_result(self) -> Dict:
        return {
            "brow_asymmetry_mm": 0.0,
            "eye_asymmetry_mm": 0.0,
            "mouth_asymmetry_mm": 0.0,
            "d_face_global": 0.0,
            "s_face_global": 0.0,
            "hemifacial_delay_ms": 0,
            "unnaturalness_score": 1,
            "clinical_flags": [],
            "condition_applied": "none",
        }
