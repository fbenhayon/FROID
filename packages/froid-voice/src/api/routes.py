"""
FROID Voice - REST API Routes
Endpoints complementares ao WebSocket principal
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/api/voice", tags=["Voice Analysis"])


@router.get("/health")
async def health():
    """Health check do serviço froid-voice."""
    return {
        "service": "froid-voice",
        "status": "healthy",
        "version": "1.0.0",
        "capabilities": {
            "opensmile_egemaps": True,
            "parselmouth_prosody": True,
            "froid_12_zones": True,
            "spectral_7_bands": True,
            "subharmonics_sna": True,
            "colorimetry_7_levels": True,
            "clinical_scoring": True,
            "baseline_calibration": True,
            "sex_adjustment": True,
        },
    }


@router.get("/config")
async def get_config():
    """Retorna configuração atual dos analisadores."""
    from src.config import (
        FROID_ZONES,
        SPECTRAL_BANDS,
        COLOR_MAP,
        CLINICAL_WEIGHTS,
        CLINICAL_THRESHOLDS,
        CALIBRATION_DURATION_SEC,
    )

    return {
        "zones": FROID_ZONES,
        "spectral_bands": SPECTRAL_BANDS,
        "color_map": COLOR_MAP,
        "clinical_constructs": list(CLINICAL_WEIGHTS.keys()),
        "clinical_thresholds": CLINICAL_THRESHOLDS,
        "calibration_duration_sec": CALIBRATION_DURATION_SEC,
    }
