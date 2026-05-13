"""
FROID Face - Pré-processamento Científico
CLAHE + Normalização Afim + Extração de Features Geométricas

Fonte: [facts6.pdf, Sec 3.2-3.3] e [FACTS4.pdf, Fig 2]
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Optional, Tuple


class FacePreprocessor:
    """
    Pré-processamento científico de imagens faciais.
    
    Pipeline:
    1. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    2. Normalização Afim via triângulo C1-C2-C3
    3. Extração de landmarks MediaPipe 468pts
    4. Feature vector geométrico [x, y, magnitude, direction]
    """

    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def normalize_affine(self, img: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """
        Normalização afim via triângulo C1-C2-C3 [FACTS4.pdf, Sec 2.1]
        
        C1: Canto interno olho direito (landmark 362)
        C2: Canto interno olho esquerdo (landmark 133)
        C3: Ponta do nariz (landmark 2)
        
        Args:
            img: Imagem BGR
            pts: Landmarks normalizados (468, 3)
            
        Returns:
            Imagem normalizada 128×128 grayscale
        """
        h, w = img.shape[:2]
        
        # Pontos de referência MediaPipe
        C1 = pts[362][:2] * [w, h]  # Canto interno olho direito
        C2 = pts[133][:2] * [w, h]  # Canto interno olho esquerdo
        C3 = pts[2][:2] * [w, h]    # Ponta do nariz
        
        # Triângulo destino (padrão 128×128)
        dst = np.float32([[40, 48], [88, 48], [64, 84]])
        src = np.float32([C1, C2, C3])
        
        # Transformação afim
        M = cv2.getAffineTransform(src, dst)
        normalized = cv2.warpAffine(img, M, (128, 128))
        
        # Converter para grayscale se necessário
        if len(normalized.shape) == 3:
            normalized = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
            
        return normalized

    def apply_clahe(self, img: np.ndarray) -> np.ndarray:
        """
        CLAHE para invariância de iluminação [facts6.pdf, Sec 3.2]
        
        Args:
            img: Imagem grayscale
            
        Returns:
            Imagem equalizada
        """
        # Garantir grayscale
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
        # CLAHE com clip limit 2.0 e grid 8×8
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(img)

    def extract_landmarks(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Extração de 468 landmarks MediaPipe [facts6.pdf, Sec 3.3]
        
        Args:
            frame: Imagem BGR
            
        Returns:
            Array (468, 3) com coordenadas [x, y, z] normalizadas ou None
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)
        
        if not results.multi_face_landmarks:
            return None
            
        face = results.multi_face_landmarks[0]
        return np.array([[lm.x, lm.y, lm.z] for lm in face.landmark])

    def geometric_feature_vector(self, pts: np.ndarray) -> np.ndarray:
        """
        Feature vector geométrico [facts6.pdf, Sec 3.4]
        
        Para cada landmark: [x, y, magnitude, direction]
        - magnitude: distância euclidiana do centróide
        - direction: ângulo relativo ao centróide
        
        Args:
            pts: Landmarks (468, 3)
            
        Returns:
            Feature vector (468 × 4,) = (1872,)
        """
        # Centróide facial (média dos pontos 2D)
        centroid = np.mean(pts[:, :2], axis=0)
        
        # Vetores relativos ao centróide
        vecs = pts[:, :2] - centroid
        
        # Magnitude (distância euclidiana)
        mags = np.linalg.norm(vecs, axis=1)
        
        # Direção (ângulo em radianos)
        dirs = np.arctan2(vecs[:, 1], vecs[:, 0])
        
        # Concatenar [x, y, magnitude, direction] por ponto
        features = np.column_stack([pts[:, :2], mags, dirs])
        
        return features.flatten()

    def preprocess_frame(self, frame: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Pipeline completo de pré-processamento.
        
        Args:
            frame: Frame BGR do vídeo
            
        Returns:
            (normalized_frame, landmarks) ou (None, None) se falhar
        """
        # 1. Extrair landmarks
        landmarks = self.extract_landmarks(frame)
        if landmarks is None:
            return None, None
        
        # 2. Normalização afim
        normalized = self.normalize_affine(frame, landmarks)
        
        # 3. CLAHE
        normalized = self.apply_clahe(normalized)
        
        return normalized, landmarks

    def close(self):
        """Libera recursos do MediaPipe."""
        self.face_mesh.close()
