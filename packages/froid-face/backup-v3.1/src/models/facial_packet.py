"""
FROID Face - Modelos de Dados
FacialEmotionPacket emitido por frame processado
"""

from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime


class ActionUnitReading(BaseModel):
    au_number: int
    au_name: str
    intensity: float
    intensity_scale: str  # A-E
    confidence: float
    is_reliable: bool
    muscle_type: str  # "involuntary" ou "voluntary"


class AsymmetryData(BaseModel):
    brow_mm: float = 0.0
    eye_mm: float = 0.0
    mouth_mm: float = 0.0
    d_face_global: float = 0.0
    s_face_global: float = 0.0
    hemifacial_delay_ms: int = 0
    unnaturalness_score: int = 1


class QualityMetrics(BaseModel):
    face_visibility: float = 0.0
    lighting_adequacy: float = 0.0
    pose_angle_degrees: float = 0.0
    occlusion_detected: bool = False
    fps_actual: float = 0.0
    overall_quality: float = 0.0
    is_acceptable: bool = True


class ClinicalFlagData(BaseModel):
    flag_type: str
    severity: str
    description: str
    region: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None


class FacialEmotionPacket(BaseModel):
    """Pacote emitido por frame processado (30 FPS target)."""
    session_id: str
    timestamp: float
    frame_index: int

    # Emoção dominante
    dominant_emotion: str
    emotion_confidence: float
    valence: float
    arousal: float
    rule_matched: str

    # Genuineness
    genuineness_score: float
    is_microexpression: bool
    duration_ms: int = 0

    # Action Units ativas
    active_aus: List[ActionUnitReading]
    involuntary_aus: List[int]
    voluntary_aus: List[int]

    # Fase temporal (HMM)
    temporal_phase: str  # neutral, onset, apex, offset

    # Assimetria
    asymmetry: AsymmetryData

    # Qualidade
    quality: QualityMetrics

    # Flags clínicos
    clinical_flags: List[ClinicalFlagData]

    # Pose
    pose: Optional[Dict[str, float]] = None
