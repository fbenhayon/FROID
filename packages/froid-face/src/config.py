"""
FROID Face - Configuração Científica v4.0
Thresholds validados + Tabela AU→Emoção VERBATIM

Fontes:
- [FACTS3.pdf]: Thresholds de percepção humana
- [3D FACTS.pdf]: Parâmetros HMM
- Tabela AU fornecida pelo usuário (100% idêntica)
"""

from dataclasses import dataclass
from typing import Dict, List, Set

# =============================================================================
# THRESHOLDS CLÍNICOS (Validados Cientificamente)
# =============================================================================

@dataclass
class ClinicalThresholds:
    """Extratos diretos de [FACTS3.pdf, Results]"""
    EYELID_ASYMMETRY_MM: float = 2.0
    SMILE_ASYMMETRY_MM: float = 3.0
    BROW_ASYMMETRY_MM: float = 3.0
    HEMIFACIAL_DELAY_MS: float = 99.0
    MICROEXPRESSION_MS: float = 500.0
    APEX_CONFIDENCE_MIN: float = 0.75
    AU_ACTIVATION_THRESHOLD: float = 0.3

CONDITION_MULTIPLIERS = {
    "facial_paralysis": {"eyelid": 3.0, "smile": 3.0, "brow": 3.0},
    "bell_palsy": {"eyelid": 2.0, "smile": 2.0, "brow": 2.0},
    "parkinson_disease": {"eyelid": 1.5, "smile": 1.5, "brow": 1.5},
    "stroke": {"eyelid": 2.5, "smile": 2.5, "brow": 2.5},
    "none": {"eyelid": 1.0, "smile": 1.0, "brow": 1.0},
}

# =============================================================================
# PARÂMETROS HMM (3D FACTS.pdf, Sec II.D & Table I)
# =============================================================================

@dataclass
class HMMParams:
    """Parâmetros HMM validados por emoção"""
    WINDOW_WIDTHS = {
        "happy": 12,
        "angry": 8,
        "surprise": 4,
        "fear": 8,
        "sadness": 10,
        "disgust": 10
    }
    STATES = ["neutral", "onset", "apex", "offset"]
    INITIAL_PROBS = [0.60, 0.25, 0.10, 0.05]
    TRANSITION_MATRIX = [
        [0.70, 0.25, 0.05, 0.00],
        [0.00, 0.60, 0.35, 0.05],
        [0.00, 0.00, 0.50, 0.50],
        [0.60, 0.20, 0.00, 0.20]
    ]

# =============================================================================
# TABELA AU → EMOÇÃO (FORNECIDA PELO USUÁRIO - VERBATIM)
# =============================================================================

AU_TO_EMOTION_RULES: Dict[str, List[Set[int]]] = {
    "anger": [
        {4, 5, 7, 10, 22, 23, 25},
        {4, 5, 7, 10, 23, 26},
        {4, 5, 7, 17, 23},
        {4, 5, 7, 24},
        {4, 5},
        {4, 5, 7, 10},
        {17, 24},
        {4, 5, 7}
    ],
    "disgust": [
        {9, 10, 17},
        {9, 10, 16, 25},
        {9, 10, 16, 26},
        {9},
        {10},
        {9, 17},
        {10, 17}
    ],
    "fear": [
        {1, 2, 4, 5, 20, 25},
        {1, 2, 4, 5, 26},
        {1, 2, 4, 5, 27},
        {1, 2, 4, 5},
        {1, 2, 5, 25},
        {1, 2, 5, 26},
        {1, 2, 5, 27},
        {5, 20, 25},
        {5, 20, 26},
        {5, 20, 27},
        {20},
        {1, 2, 4}
    ],
    "happy": [
        {12},
        {6, 12}
    ],
    "sadness": [
        {1, 4, 11, 15},
        {1, 4, 15, 17},
        {6, 15},
        {11, 17},
        {1},
        {1, 4}
    ],
    "surprise": [
        {1, 2, 5, 26},
        {1, 2, 5, 27},
        {1, 2, 5},
        {1, 2, 26},
        {1, 2, 27},
        {5, 26},
        {5, 27},
        {1, 2, 5, 26, 27}
    ],
    "contempt": [
        {12, 14}
    ],
    "neutral": [
        set()
    ]
}

# =============================================================================
# MEDIAPIPE LANDMARKS → AU REGIONS
# =============================================================================

AU_LANDMARK_REGIONS = {
    "brow_inner_left": [105, 66, 107, 55, 65],
    "brow_inner_right": [334, 296, 336, 285, 295],
    "brow_outer_left": [46, 53, 52, 63],
    "brow_outer_right": [276, 283, 282, 293],
    "eye_upper_left": [159, 145, 158, 153],
    "eye_upper_right": [386, 374, 385, 380],
    "eye_lower_left": [144, 163, 7, 33],
    "eye_lower_right": [373, 390, 249, 263],
    "nose": [4, 6, 168, 197, 195, 5],
    "mouth_upper": [37, 39, 40, 185, 61, 267, 269, 270, 409, 291],
    "mouth_lower": [84, 17, 314, 87, 317],
    "mouth_corner_left": [61, 146, 91],
    "mouth_corner_right": [291, 375, 321],
    "chin": [18, 200, 199, 175],
    "jaw": [152, 10, 338, 297, 332, 284],
}

INTENSITY_SCALE = {
    "A": (0.1, 0.2, "Traço mínimo"),
    "B": (0.2, 0.4, "Leve"),
    "C": (0.4, 0.6, "Marcado/pronunciado"),
    "D": (0.6, 0.8, "Severo/extremo"),
    "E": (0.8, 1.0, "Máximo"),
}

# =============================================================================
# INTEGRAÇÃO
# =============================================================================

IDENTITY_VAULT_URL = "http://identity-vault:3001/api"
REDIS_URL = "redis://redis:6379"
FROID_VOICE_URL = "http://froid-voice:3002"
