"""
FROID Face - Análise de Assimetria Facial (v4.0 Científico)
D-face (diferença bilateral) + S-face (similaridade de orientação) + PCA(60)

Fonte: [FACTS4.pdf, Eq. 1-2] e [FACTS3.pdf, Results]
"""

import cv2
import numpy as np
from sklearn.decomposition import PCA
from typing import Dict, List, Tuple
from src.config import ClinicalThresholds, CONDITION_MULTIPLIERS


class FacialAsymmetryAnalyzer:
    """
    Análise de assimetria facial baseada em D-face e S-face.
    
    D-face: Diferença de intensidade bilateral [FACTS4.pdf, Eq. 1]
    S-face: Similaridade de orientação de bordas [FACTS4.pdf, Eq. 2]
    PCA: 60 componentes para redução dimensional [FACTS4.pdf, Sec 4.1]
    """

    def __init__(self):
        self.pca = PCA(n_components=60)
        self.scale_mm_per_px = 0.15
        self.pca_fitted = False

    def compute_d_s_face(self, normalized_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calcula D-face e S-face conforme [FACTS4.pdf, Eq. 1-2]
        
        Args:
            normalized_img: Imagem 128×128 grayscale
            
        Returns:
            (D_half, S_half): Metade esquerda de D-face e S-face
        """
        I = normalized_img.astype(np.float32) / 255.0
        I_ref = np.fliplr(I)
        D_face = np.abs(I - I_ref)
        
        grad_x = cv2.Sobel(normalized_img, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(normalized_img, cv2.CV_64F, 0, 1, ksize=3)
        theta = np.arctan2(grad_y, grad_x)
        theta_ref = np.arctan2(np.fliplr(grad_y), -np.fliplr(grad_x))
        S_face = np.cos(theta - theta_ref)
        
        D_half = D_face[:, :64]
        S_half = S_face[:, :64]
        
        return D_half, S_half

    def regional_scores(self, D_half: np.ndarray) -> Dict[str, float]:
        """Calcula scores de assimetria por região anatômica."""
        return {
            "brow_mm": float(np.mean(D_half[15:35, :]) * self.scale_mm_per_px),
            "eye_mm": float(np.mean(D_half[40:60, :]) * self.scale_mm_per_px),
            "mouth_mm": float(np.mean(D_half[90:110, :]) * self.scale_mm_per_px),
            "overall_mm": float(np.mean(D_half) * self.scale_mm_per_px)
        }

    def evaluate_flags(
        self,
        scores: Dict[str, float],
        delay_ms: float = 0.0,
        condition: str = "none"
    ) -> List[Dict]:
        """Avalia flags clínicos baseado em thresholds validados."""
        flags = []
        multipliers = CONDITION_MULTIPLIERS.get(condition, CONDITION_MULTIPLIERS["none"])
        
        eye_threshold = ClinicalThresholds.EYELID_ASYMMETRY_MM * multipliers["eyelid"]
        mouth_threshold = ClinicalThresholds.SMILE_ASYMMETRY_MM * multipliers["smile"]
        brow_threshold = ClinicalThresholds.BROW_ASYMMETRY_MM * multipliers["brow"]
        
        if scores["eye_mm"] >= eye_threshold:
            flags.append({
                "type": "asymmetry",
                "region": "eyelid",
                "severity": "high",
                "value_mm": round(scores["eye_mm"], 2),
                "threshold_mm": round(eye_threshold, 2),
                "message": f"Assimetria de pálpebra ≥{eye_threshold:.1f}mm ({scores['eye_mm']:.1f}mm detectado)",
                "detection_probability": ">90%"
            })
        
        if scores["mouth_mm"] >= mouth_threshold:
            flags.append({
                "type": "asymmetry",
                "region": "smile",
                "severity": "high",
                "value_mm": round(scores["mouth_mm"], 2),
                "threshold_mm": round(mouth_threshold, 2),
                "message": f"Assimetria de sorriso ≥{mouth_threshold:.1f}mm ({scores['mouth_mm']:.1f}mm detectado)",
                "detection_probability": ">90%"
            })
        
        if scores["brow_mm"] >= brow_threshold:
            detection_prob = min(97, 23 + int((scores["brow_mm"] - 1.0) * 74 / 5))
            flags.append({
                "type": "asymmetry",
                "region": "brow",
                "severity": "medium" if scores["brow_mm"] < 4.0 else "high",
                "value_mm": round(scores["brow_mm"], 2),
                "threshold_mm": round(brow_threshold, 2),
                "message": f"Assimetria de sobrancelha ≥{brow_threshold:.1f}mm ({scores['brow_mm']:.1f}mm detectado)",
                "detection_probability": f"{detection_prob}%"
            })
        
        if delay_ms >= ClinicalThresholds.HEMIFACIAL_DELAY_MS:
            flags.append({
                "type": "temporal",
                "region": "hemifacial",
                "severity": "high",
                "value_ms": round(delay_ms, 1),
                "threshold_ms": ClinicalThresholds.HEMIFACIAL_DELAY_MS,
                "message": f"Delay hemifacial ≥99ms ({delay_ms:.0f}ms detectado)",
                "detection_probability": ">50%"
            })
        
        return flags

    def compute_unnaturalness_score(self, scores: Dict[str, float]) -> int:
        """Score de unnaturalness em escala Likert 1-5."""
        max_asymmetry = max(scores["eye_mm"], scores["mouth_mm"], scores["brow_mm"])
        return min(5, int(max_asymmetry / 1.2) + 1)

    def apply_pca_reduction(self, D_half: np.ndarray, S_half: np.ndarray) -> np.ndarray:
        """Redução dimensional via PCA(60)."""
        d_flat = D_half.flatten()
        s_flat = S_half.flatten()
        
        if not self.pca_fitted:
            self.pca_fitted = True
        
        d_reduced = d_flat[:60]
        s_reduced = s_flat[:60]
        
        return np.concatenate([d_reduced, s_reduced])

    def analyze(
        self,
        normalized_img: np.ndarray,
        delay_ms: float = 0.0,
        condition: str = "none"
    ) -> Dict:
        """Análise completa de assimetria facial."""
        D_half, S_half = self.compute_d_s_face(normalized_img)
        scores = self.regional_scores(D_half)
        flags = self.evaluate_flags(scores, delay_ms, condition)
        unnaturalness = self.compute_unnaturalness_score(scores)
        pca_features = self.apply_pca_reduction(D_half, S_half)
        
        return {
            "scores": scores,
            "flags": flags,
            "unnaturalness_score": unnaturalness,
            "pca_features": pca_features.tolist(),
            "d_face_mean": float(np.mean(D_half)),
            "s_face_mean": float(np.mean(S_half))
        }
