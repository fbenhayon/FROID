"""
FROID Voice - Configuração Unificada
Fusão: API Voice (scoring clínico) + Plano 4B (12 Zonas, 7 Bandas, Colorimetria)

Referências Científicas:
- Aguiar et al. (2025) [PT-BR]: z-score duração, F0, intensidade, taxa de elocução
- Kaczmarek-Majer et al. (2024) [BD]: Inversão de sinal por sexo
- Di et al. (2024) [MDD]: ΔF0_iqr1-3, F0_upleveltime90
- Zhao et al. (2022) [MDD/Ansiedade]: MFCC4/7, ZCR
- Schewski et al. (2025) [Estresse]: F0, Intensidade, Speech_rate
- Kamiloğlu et al. (2020) [Emoções Positivas]: Famílias epistemológicas
"""

# =============================================================================
# CONSTANTES DE PIPELINE
# =============================================================================
SAMPLE_RATE = 16000
WINDOW_SEC = 2.0            # Janela de análise openSMILE (API Voice)
STRIDE_SEC = 0.5            # Stride de processamento
SLICE_SEC = 10.0            # Fatia para ZonalEnergyPacket (Plano 4B)
CALIBRATION_DURATION_SEC = 60  # Baseline do paciente (API Voice)
PROSODY_UPDATE_MS = 500     # Atualização de F0/Jitter/Shimmer (Plano 4B)

# =============================================================================
# IDENTITY VAULT INTEGRATION
# =============================================================================
IDENTITY_VAULT_URL = "http://identity-vault:3001"
REDIS_URL = "redis://redis:6379"

# =============================================================================
# CLINICAL SCORING WEIGHTS (API Voice - referências científicas)
# =============================================================================
CLINICAL_WEIGHTS = {
    "depression_risk": {
        "ΔF0_iqr1-3": -0.40,       # Di et al. (2024)
        "F0_upleveltime90": -0.30,  # Di et al. (2024)
        "F0_mean": -0.20,
        "Intensity_mean": -0.20,
        "Spectral_flux": -0.15,     # Kaczmarek-Majer et al. (2024)
        "MFCC4": 0.15,              # Zhao et al. (2022)
        "MFCC7": 0.15,              # Zhao et al. (2022)
        "Duration_VV_zscore": 0.20, # Aguiar et al. (2025)
    },
    "mania_activation": {
        "Intensity_mean": 0.35,     # Kaczmarek-Majer (β=1.6 homens)
        "F0_mean": 0.30,            # Kaczmarek-Majer (β=0.71 homens)
        "Spectral_flux": 0.25,      # Kaczmarek-Majer (β=1.35 homens)
        "Jitter_local": 0.20,
        "Shimmer_local": 0.15,
        "Speech_rate": 0.15,
    },
    "stress_cognitive": {
        "F0_mean": 0.25,
        "Intensity_mean": 0.25,
        "Speech_rate": -0.15,       # Schewski et al. (2025)
        "ZCR": 0.20,                # Zhao et al. (2022)
    },
}

# Inversão de sinal para mulheres (Kaczmarek-Majer et al., 2024)
SEX_INVERT_PARAMS = ["Intensity_mean", "F0_mean", "Spectral_flux"]
SEX_INVERT_FACTOR = -0.85

# Thresholds de alerta clínico
CLINICAL_THRESHOLDS = {
    "depression_risk": 0.65,
    "mania_activation": 0.60,
    "stress_cognitive": 0.68,
}

# EMA smoothing alpha
EMA_ALPHA = 0.3

# =============================================================================
# 12 ZONAS FROID (Plano 4B - proprietário)
# Notas musicais com dicotomias psíquicas
# =============================================================================
FROID_ZONES = [
    {"zone": 1,  "note": "C",  "freq": 130.81, "positive": "Segurança",     "negative": "Medo"},
    {"zone": 2,  "note": "C#", "freq": 138.59, "positive": "Valor pessoal",  "negative": "Vergonha"},
    {"zone": 3,  "note": "D",  "freq": 146.83, "positive": "Poder",          "negative": "Impotência"},
    {"zone": 4,  "note": "D#", "freq": 155.56, "positive": "Amor",           "negative": "Ódio"},
    {"zone": 5,  "note": "E",  "freq": 164.81, "positive": "Expressão",      "negative": "Repressão"},
    {"zone": 6,  "note": "F",  "freq": 174.61, "positive": "Intuição",       "negative": "Confusão"},
    {"zone": 7,  "note": "F#", "freq": 185.00, "positive": "Conexão espiritual", "negative": "Desconexão"},
    {"zone": 8,  "note": "G",  "freq": 196.00, "positive": "Responsabilidade", "negative": "Culpa"},
    {"zone": 9,  "note": "G#", "freq": 207.65, "positive": "Verdade",        "negative": "Negação"},
    {"zone": 10, "note": "A",  "freq": 220.00, "positive": "Aceitação",      "negative": "Resistência"},
    {"zone": 11, "note": "A#", "freq": 233.08, "positive": "Gratidão",       "negative": "Ressentimento"},
    {"zone": 12, "note": "B",  "freq": 246.94, "positive": "Transcendência", "negative": "Apego"},
]

# Tolerância em Hz para detecção de zona (± semitom/4)
ZONE_TOLERANCE_RATIO = 0.015  # 1.5% da frequência central

# Harmônicos a considerar (2x, 3x, 4x)
HARMONICS = [2, 3, 4]

# =============================================================================
# 7 BANDAS ESPECTRAIS (Plano 4B - correlatos neurológicos)
# =============================================================================
SPECTRAL_BANDS = [
    {"band": 1, "range": (85, 150),   "correlate": "Tronco cerebral, regulação autonômica"},
    {"band": 2, "range": (150, 250),  "correlate": "Sistema límbico, emoções primárias"},
    {"band": 3, "range": (250, 400),  "correlate": "Córtex pré-frontal, regulação emocional"},
    {"band": 4, "range": (400, 600),  "correlate": "Equilíbrio, serenidade"},
    {"band": 5, "range": (600, 900),  "correlate": "Expressão emocional, vulnerabilidade"},
    {"band": 6, "range": (900, 1200), "correlate": "Introspecção, tristeza"},
    {"band": 7, "range": (1200, 2000), "correlate": "Criatividade, insight"},
]

# =============================================================================
# COLORIMETRIA QUANTITATIVA (Plano 4B - 7 níveis)
# =============================================================================
COLOR_MAP = {
    1: {"hex": "#006400", "label": "Verde escuro",   "meaning": "Zona muito ativa positivamente"},
    2: {"hex": "#32CD32", "label": "Verde claro",    "meaning": "Zona ativa positivamente"},
    3: {"hex": "#9ACD32", "label": "Amarelo-verde",  "meaning": "Leve ativação positiva"},
    4: {"hex": "#FFD700", "label": "Amarelo",         "meaning": "Zona neutra / equilibrada"},
    5: {"hex": "#FF8C00", "label": "Laranja",         "meaning": "Ativação negativa leve"},
    6: {"hex": "#FF4500", "label": "Vermelho claro",  "meaning": "Zona ativa negativamente"},
    7: {"hex": "#8B0000", "label": "Vermelho escuro", "meaning": "Zona muito ativa negativamente"},
}

# =============================================================================
# SUB-HARMÔNICOS (Plano 4B - Sistema Nervoso Autônomo)
# =============================================================================
SUBHARMONIC_RANGE = (5, 20)  # Hz - infrassom vocal
TREMOR_THRESHOLD = 0.3       # Energia normalizada para detecção de tremor
