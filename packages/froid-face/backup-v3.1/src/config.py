"""
FROID Face - Configuração
Thresholds clínicos ajustáveis + mapeamentos AU + referências científicas

Fontes:
- [3D FACTS.pdf]: HMM temporal, GentleBoost, window width
- [FACTS3.pdf]: Thresholds de percepção (eyelid ≥2mm, smile ≥3mm)
- [FACTS4.pdf]: D-face/S-face, normalização afim
- [facts6.pdf]: Landmarks 2D, SVM 89% CK+
"""

# =============================================================================
# INTEGRATION
# =============================================================================
IDENTITY_VAULT_URL = "http://localhost:3001/api"
REDIS_URL = "redis://172.21.208.107:6379"
FROID_VOICE_URL = "http://localhost:3002"

# =============================================================================
# PIPELINE MODES (API Facial)
# =============================================================================
PIPELINE_MODES = {
    "3D_NATIVE": {"accuracy": 0.8193, "description": "Depth sensor (RealSense, Kinect, LiDAR)"},
    "2D_ENHANCED": {"accuracy": 0.791, "description": "Monocular depth + IMU"},
    "2D_BASELINE": {"accuracy": 0.758, "description": "Landmarks 2D apenas (MediaPipe 468pts)"},
}

# =============================================================================
# CLINICAL THRESHOLDS (FACTS3.pdf - validados cientificamente)
# =============================================================================
DEFAULT_THRESHOLDS = {
    "eyelid_threshold_mm": 2.0,       # >90% detecção humana
    "smile_threshold_mm": 3.0,        # >90% detecção humana
    "brow_threshold_mm": 3.0,         # ~80% detecção
    "incongruence_delay_ms": 99,      # >50% detecção temporal
    "microexpression_max_ms": 500,    # Duração máxima para microexpressão
    "apex_confidence_threshold": 0.75, # Confiança mínima para apex
    "au_activation_threshold": 0.3,   # Intensidade mínima para AU ativa
}

# Ajustes por condição clínica
CONDITION_MULTIPLIERS = {
    "facial_paralysis": {"eyelid": 3.0, "smile": 3.0, "brow": 3.0},
    "bell_palsy": {"eyelid": 2.0, "smile": 2.0, "brow": 2.0},
    "parkinson_disease": {"eyelid": 1.5, "smile": 1.5, "brow": 1.5},
    "stroke": {"eyelid": 2.5, "smile": 2.5, "brow": 2.5},
    "none": {"eyelid": 1.0, "smile": 1.0, "brow": 1.0},
}

# =============================================================================
# FUSÃO MULTIMODAL - Ponderação Dinâmica (API Facial Parte 4)
# =============================================================================
FUSION_WEIGHTS_BY_CONTEXT = {
    "initial_evaluation": {"face": 0.6, "voice": 0.4},
    "follow_up_depression": {"face": 0.4, "voice": 0.6},
    "follow_up_anxiety": {"face": 0.7, "voice": 0.3},
    "ptsd_assessment": {"face": 0.5, "voice": 0.5},
    "medication_review": {"face": 0.6, "voice": 0.4},
    "therapy_session": {"face": 0.5, "voice": 0.5},
}

# =============================================================================
# HMM PARAMETERS (3D FACTS.pdf, Sec II.D)
# =============================================================================
HMM_STATES = ["neutral", "onset", "apex", "offset"]
HMM_INITIAL_PROBS = [0.6, 0.3, 0.05, 0.05]
HMM_TRANSITION_MATRIX = [
    [0.70, 0.25, 0.05, 0.00],  # neutral → neutral/onset
    [0.00, 0.60, 0.35, 0.05],  # onset → onset/apex
    [0.00, 0.00, 0.50, 0.50],  # apex → apex/offset
    [0.60, 0.20, 0.00, 0.20],  # offset → neutral/onset/offset
]
HMM_EMISSION_PARAMS = {
    "onset": {
        "neutral": (0.15, 0.1),
        "onset": (0.75, 0.15),
        "apex": (0.45, 0.2),
        "offset": (0.10, 0.08),
    },
    "offset": {
        "neutral": (0.10, 0.08),
        "onset": (0.20, 0.12),
        "apex": (0.30, 0.15),
        "offset": (0.80, 0.1),
    },
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

# Escala de intensidade A-E
INTENSITY_SCALE = {
    "A": (0.1, 0.2, "Traço mínimo"),
    "B": (0.2, 0.4, "Leve"),
    "C": (0.4, 0.6, "Marcado/pronunciado"),
    "D": (0.6, 0.8, "Severo/extremo"),
    "E": (0.8, 1.0, "Máximo"),
}
