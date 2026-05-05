"""
FROID Face - Extrator de Landmarks
MediaPipe Face Mesh (468 pontos) + features geométricas

Fonte: API Facial Parte 4 (landmark_extractor.py) + [facts6.pdf]
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, Optional, Tuple
from src.config import AU_LANDMARK_REGIONS


class LandmarkExtractor:
    """
    Extrai landmarks faciais (468 pontos) e calcula features geométricas.
    Baseado em MediaPipe Face Mesh com refine_landmarks=True.
    """

    def __init__(self, max_faces: int = 1):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_faces,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def extract(self, frame_bgr: np.ndarray) -> Optional[Dict]:
        """
        Extrai landmarks de um frame BGR.

        Returns:
            Dict com pontos, features geométricas e pose, ou None se face não detectada
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)

        if not results.multi_face_landmarks:
            return None

        face = results.multi_face_landmarks[0]
        h, w = frame_bgr.shape[:2]

        # Extrair coordenadas normalizadas e em pixels
        points_norm = np.array([[lm.x, lm.y, lm.z] for lm in face.landmark])
        points_px = np.array([[lm.x * w, lm.y * h, lm.z * w] for lm in face.landmark])

        # Centróide facial [facts6.pdf, Fig. 7]
        centroid = np.mean(points_norm[:, :2], axis=0)

        # Feature vector: magnitude + direção relativa ao centróide
        vectors = points_norm[:, :2] - centroid
        magnitudes = np.linalg.norm(vectors, axis=1)
        directions = np.arctan2(vectors[:, 1], vectors[:, 0])

        # Estimativa de pose (yaw, pitch, roll)
        pose = self._estimate_pose(points_norm)

        # Distâncias regionais para AUs
        au_distances = self._compute_au_distances(points_norm)

        return {
            "points_norm": points_norm,
            "points_px": points_px,
            "centroid": centroid,
            "magnitudes": magnitudes,
            "directions": directions,
            "pose": pose,
            "au_distances": au_distances,
            "point_count": len(points_norm),
            "frame_size": (w, h),
        }

    def _estimate_pose(self, points: np.ndarray) -> Dict[str, float]:
        """Estima pose facial (yaw, pitch, roll) a partir dos landmarks."""
        # Pontos de referência para pose
        nose_tip = points[4]
        chin = points[152]
        left_eye = points[33]
        right_eye = points[263]
        left_mouth = points[61]
        right_mouth = points[291]

        # Yaw: rotação horizontal (baseado em assimetria nariz-olhos)
        eye_center = (left_eye + right_eye) / 2
        yaw = float(np.arctan2(nose_tip[0] - eye_center[0], nose_tip[2] - eye_center[2])) * 57.3

        # Pitch: inclinação vertical
        face_height = np.linalg.norm(nose_tip[:2] - chin[:2])
        pitch = float(np.arctan2(nose_tip[1] - eye_center[1], face_height)) * 57.3

        # Roll: rotação axial
        eye_vec = right_eye[:2] - left_eye[:2]
        roll = float(np.arctan2(eye_vec[1], eye_vec[0])) * 57.3

        return {"yaw": round(yaw, 2), "pitch": round(pitch, 2), "roll": round(roll, 2)}

    def _compute_au_distances(self, points: np.ndarray) -> Dict[str, float]:
        """Calcula distâncias relevantes para estimativa de AUs."""
        distances = {}

        # Abertura do olho (AU5, AU7, AU43, AU45)
        left_eye_open = np.linalg.norm(points[159][:2] - points[145][:2])
        right_eye_open = np.linalg.norm(points[386][:2] - points[374][:2])
        distances["eye_open_left"] = float(left_eye_open)
        distances["eye_open_right"] = float(right_eye_open)

        # Altura da sobrancelha (AU1, AU2, AU4)
        left_brow_height = float(np.mean(points[[105, 66, 107]][:, 1]) - np.mean(points[[159, 145]][:, 1]))
        right_brow_height = float(np.mean(points[[334, 296, 336]][:, 1]) - np.mean(points[[386, 374]][:, 1]))
        distances["brow_height_left"] = left_brow_height
        distances["brow_height_right"] = right_brow_height

        # Largura da boca (AU12, AU20)
        mouth_width = np.linalg.norm(points[61][:2] - points[291][:2])
        distances["mouth_width"] = float(mouth_width)

        # Abertura da boca (AU25, AU26, AU27)
        mouth_open = np.linalg.norm(points[13][:2] - points[14][:2])
        distances["mouth_open"] = float(mouth_open)

        # Distância lábio superior - nariz (AU9, AU10)
        upper_lip_nose = np.linalg.norm(points[0][:2] - points[13][:2])
        distances["upper_lip_nose"] = float(upper_lip_nose)

        # Elevação do queixo (AU17)
        chin_height = np.linalg.norm(points[152][:2] - points[17][:2])
        distances["chin_height"] = float(chin_height)

        # Compressão labial (AU23, AU24)
        lip_compression = np.linalg.norm(points[13][:2] - points[14][:2])
        distances["lip_compression"] = float(lip_compression)

        return distances

    def close(self):
        """Libera recursos do MediaPipe."""
        self.face_mesh.close()
