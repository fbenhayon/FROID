"""
FROID Voice - Modelos de Dados
ZonalEnergyPacket (emitido a cada 10s) e VoiceAnalysisResult consolidado
"""

from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime


class ZoneEnergy(BaseModel):
    zone: int
    note: str
    freq_hz: float
    positive: str
    negative: str
    energy_normalized: float
    color_hex: str


class BandEnergy(BaseModel):
    band: int
    range_hz: str
    correlate: str
    energy_normalized: float


class ClinicalScore(BaseModel):
    construct: str
    score: float
    threshold: float
    is_alert: bool
    description: str


class ProsodyData(BaseModel):
    f0_mean: float = 0.0
    f0_std: float = 0.0
    f0_range: float = 0.0
    jitter_local: float = 0.0
    shimmer_local: float = 0.0
    hnr: float = 0.0
    speech_rate: float = 0.0
    silence_ratio: float = 0.0
    clinical_pattern: str = "indeterminado"


class SubharmonicData(BaseModel):
    energy_ratio: float = 0.0
    tremor_detected: bool = False
    tremor_frequency_hz: float = 0.0
    clinical_note: str = ""


class ZonalEnergyPacket(BaseModel):
    """Pacote emitido a cada 10 segundos de análise vocal."""
    session_id: str
    timestamp: datetime
    slice_index: int
    slice_duration_ms: int = 10000

    # 12 Zonas FROID
    zones: List[ZoneEnergy]
    dominant_zone: int
    dominant_note: str
    dominant_dichotomy: Dict[str, str]

    # 7 Bandas Espectrais
    spectral_bands: List[BandEnergy]
    dominant_band: int
    dominant_correlate: str

    # Prosódia (último valor da fatia)
    prosody: ProsodyData

    # Sub-harmônicos
    subharmonics: SubharmonicData

    # Scoring Clínico (API Voice)
    clinical_scores: List[ClinicalScore]
    clinical_flags: List[Dict]

    # Colorimetria
    color_map: List[str]  # 12 cores hex
    overall_color: str    # Cor dominante da fatia

    # eGeMAPS brutas (para persistência)
    egemaps_raw: Optional[Dict] = None

    # Calibração
    is_calibrated: bool = True
    calibration_progress: Optional[float] = None


class CalibrationStatus(BaseModel):
    """Status da calibração (fase dos primeiros 60s)."""
    session_id: str
    status: str  # "calibrating" ou "complete"
    progress: float  # 0.0 a 1.0
    elapsed_sec: float
    target_sec: float = 60.0
    baseline_summary: Optional[Dict] = None
