"""
FROID Face - Analisador de Qualidade de Captura
Métricas em tempo real para garantir análise confiável

Fonte: API Facial Parte 1 (CaptureQuality schema)
"""

import cv2
import numpy as np
from typing import Dict, Optional


class CaptureQualityAnalyzer:
    """
    Avalia qualidade da captura de vídeo em tempo real.
    Alerta o profissional quando condições comprometem a análise.
    """

    def analyze(self, frame: np.ndarray, landmarks: Optional[Dict], fps_actual: float = 30.0) -> Dict:
        """
        Analisa qualidade do frame atual.

        Returns:
            Dict com métricas de qualidade e alertas
        """
        if frame is None:
            return self._empty_result()

        h, w = frame.shape[:2]

        # 1. Visibilidade facial
        face_visibility = 0.0
        if landmarks and landmarks.get("points_px") is not None:
            pts = landmarks["points_px"]
            face_area = self._compute_face_area(pts)
            frame_area = w * h
            face_visibility = min(1.0, face_area / (frame_area * 0.15))

        # 2. Iluminação
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        mean_brightness = float(np.mean(gray))
        std_brightness = float(np.std(gray))
        lighting_adequacy = self._assess_lighting(mean_brightness, std_brightness)

        # 3. Ângulo de pose
        pose_angle = 0.0
        if landmarks and "pose" in landmarks:
            yaw = abs(landmarks["pose"].get("yaw", 0))
            pitch = abs(landmarks["pose"].get("pitch", 0))
            pose_angle = max(yaw, pitch)

        # 4. Oclusão
        occlusion = face_visibility < 0.7

        # 5. Resolução
        resolution = self._get_resolution_label(h)

        # 6. Score geral
        overall = self._compute_overall(face_visibility, lighting_adequacy, pose_angle, fps_actual)

        # 7. Alertas
        alerts = []
        if face_visibility < 0.5:
            alerts.append("Face insuficientemente visível. Ajustar posição.")
        if lighting_adequacy < 0.4:
            alerts.append("Iluminação insuficiente. Melhorar iluminação frontal.")
        if pose_angle > 30:
            alerts.append("Ângulo facial excessivo. Olhar para a câmera.")
        if occlusion:
            alerts.append("Oclusão facial detectada.")
        if fps_actual < 15:
            alerts.append("FPS baixo. Análise temporal comprometida.")

        return {
            "face_visibility": round(face_visibility, 3),
            "lighting_adequacy": round(lighting_adequacy, 3),
            "pose_angle_degrees": round(pose_angle, 2),
            "occlusion_detected": occlusion,
            "resolution": resolution,
            "fps_actual": round(fps_actual, 1),
            "overall_quality": round(overall, 3),
            "alerts": alerts,
            "is_acceptable": overall >= 0.5 and face_visibility >= 0.5,
        }

    def _compute_face_area(self, pts: np.ndarray) -> float:
        x_range = np.max(pts[:, 0]) - np.min(pts[:, 0])
        y_range = np.max(pts[:, 1]) - np.min(pts[:, 1])
        return float(x_range * y_range)

    def _assess_lighting(self, mean_b: float, std_b: float) -> float:
        brightness_score = min(1.0, mean_b / 150.0) if mean_b < 200 else max(0.0, 1.0 - (mean_b - 200) / 55.0)
        uniformity_score = min(1.0, std_b / 50.0) if std_b < 80 else max(0.0, 1.0 - (std_b - 80) / 80.0)
        return (brightness_score * 0.6 + uniformity_score * 0.4)

    def _get_resolution_label(self, height: int) -> str:
        if height >= 2160: return "4K"
        if height >= 1080: return "1080p"
        if height >= 720: return "720p"
        if height >= 480: return "480p"
        return "240p"

    def _compute_overall(self, visibility, lighting, pose_angle, fps) -> float:
        pose_score = max(0.0, 1.0 - pose_angle / 45.0)
        fps_score = min(1.0, fps / 30.0)
        return visibility * 0.35 + lighting * 0.25 + pose_score * 0.25 + fps_score * 0.15

    def _empty_result(self) -> Dict:
        return {
            "face_visibility": 0.0, "lighting_adequacy": 0.0,
            "pose_angle_degrees": 0.0, "occlusion_detected": True,
            "resolution": "unknown", "fps_actual": 0.0,
            "overall_quality": 0.0, "alerts": ["Sem frame para análise"],
            "is_acceptable": False,
        }
