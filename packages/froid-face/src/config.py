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

# =============================================================================
# TABELA AU → EMOÇÃO (EMFACS - Ekman & Friesen, validação científica)
# Regras ordenadas: canônica primeiro, variações depois
# Refs: [Ekman 2002], [PMC3008166], [paulekman.com/facs]
# =============================================================================
AU_TO_EMOTION_RULES: Dict[str, List[Set[int]]] = {
    "happy": [
        {6, 12},        # Canônica: Duchenne smile (AU6 essencial para genuinidade)
        {12},            # Sorriso voluntário (sem Duchenne marker)
    ],
    "sadness": [
        {1, 4, 15},     # Canônica: sobrancelhas oblíquas + cantos da boca descendo
        {1, 4, 15, 17}, # Com chin raiser (intensifica tristeza)
        {1, 4, 11},     # Variação com nasolabial deepener
        {1, 15},         # Mínima: inner brow raise + lip corner depressor
        {1, 4},          # Parcial: sobrancelhas de tristeza
    ],
    "surprise": [
        {1, 2, 5, 26},  # Canônica: sobrancelhas + olhos arregalados + boca aberta
        {1, 2, 5, 27},  # Com mouth stretch (surpresa extrema)
        {1, 2, 5},       # Sem jaw drop (surpresa contida)
        {1, 2, 26},      # Sobrancelhas + jaw drop
    ],
    "fear": [
        {1, 2, 4, 5, 7, 20, 25},  # Canônica completa: tensão multidirecional
        {1, 2, 4, 5, 20},          # Core: brow + olhos + lip stretcher
        {1, 2, 4, 5},              # Mínima: brow raise/lower + upper lid raise
        {1, 4, 20},                # Parcial com lip stretcher
        {5, 20},                    # Mínima: olhos arregalados + lábios esticados
    ],
    "anger": [
        {4, 5, 7, 23},  # Canônica: olhar fixo + lábios estreitados
        {4, 5, 7, 24},  # Variação com lip presser
        {4, 5, 7},       # Core: brow lowerer + lid tightener
        {4, 7, 23},      # Sem upper lid raiser
        {4, 5},           # Mínima: brow lowerer + upper lid raiser
    ],
    "disgust": [
        {9, 17},         # Canônica: nose wrinkler + chin raiser
        {10, 17},        # Variação: upper lip raiser + chin raiser (nojo controlado)
        {9},              # Mínima: nose wrinkler (marcador mais confiável)
        {9, 10},          # Nose wrinkler + upper lip raiser
        {10},             # Mínima: upper lip raiser (nojo leve)
    ],
    "contempt": [
        {12, 14},        # Canônica: UNILATERAL lip corner puller + dimpler
    ],
    "neutral": [
        set()
    ]
}

# =============================================================================
# DESCRIÇÕES CIENTÍFICAS DAS EMOÇÕES (tooltips para profissionais)
# Refs: EMFACS, Ekman & Friesen (2002), PMC3008166, PMC4157835
# =============================================================================
EMOTION_DESCRIPTIONS: Dict[str, dict] = {
    "happy": {
        "label": "Felicidade",
        "canonical_aus": "AU 6 + AU 12",
        "description": (
            'O "Duchenne Marker" (AU 6) é essencial. Sem a contração da pálpebra '
            "inferior e a elevação da bochecha, o sorriso é classificado como "
            "voluntário/não-sentido. A presença de AU 6 distingue alegria genuína "
            "de sorrisos sociais ou mascarados."
        ),
        "markers": ["AU 6: Cheek Raiser (orbicularis oculi, pars orbitalis)",
                     "AU 12: Lip Corner Puller (zygomaticus major)"],
    },
    "sadness": {
        "label": "Tristeza",
        "canonical_aus": "AU 1 + AU 4 + AU 15",
        "description": (
            "A elevação oblíqua das sobrancelhas internas (AU 1) combinada com o "
            "abaixamento dos cantos da boca (AU 15) é quase impossível de falsificar "
            "com precisão. AU 1 é um músculo confiável (involuntário), tornando-se "
            "um marcador de vazamento emocional quando presente em discurso neutro."
        ),
        "markers": ["AU 1: Inner Brow Raiser (frontalis, pars medialis)",
                     "AU 4: Brow Lowerer (corrugator supercilii)",
                     "AU 15: Lip Corner Depressor (depressor anguli oris)"],
    },
    "surprise": {
        "label": "Surpresa",
        "canonical_aus": "AU 1 + AU 2 + AU 5 + AU 26/27",
        "description": (
            "Caracterizada por um movimento rápido e simétrico. Se durar mais de "
            "um segundo, é provável que seja uma paródia ou surpresa fingida. "
            "A velocidade do onset é critério de genuinidade — surpresa real tem "
            "onset < 500ms."
        ),
        "markers": ["AU 1: Inner Brow Raiser", "AU 2: Outer Brow Raiser",
                     "AU 5: Upper Lid Raiser", "AU 26: Jaw Drop / AU 27: Mouth Stretch"],
    },
    "fear": {
        "label": "Medo",
        "canonical_aus": "AU 1 + AU 2 + AU 4 + AU 5 + AU 7 + AU 20 + AU 25",
        "description": (
            "Combina o arregalar de olhos (AU 5) com o esticamento horizontal dos "
            "lábios (AU 20), criando uma tensão facial multidirecional. A co-ocorrência "
            "de AU 1+2 (elevação) com AU 4 (abaixamento) nas sobrancelhas cria o "
            "padrão de conflito muscular característico do medo."
        ),
        "markers": ["AU 5: Upper Lid Raiser (levator palpebrae superioris)",
                     "AU 20: Lip Stretcher (risorius, platysma)",
                     "AU 4: Brow Lowerer (corrugator supercilii)"],
    },
    "anger": {
        "label": "Raiva",
        "canonical_aus": "AU 4 + AU 5 + AU 7 + AU 23/24",
        "description": (
            "O foco está no olhar fixo (AU 5/7) e no estreitamento dos lábios "
            "(AU 23), que sinaliza a preparação para a agressão ou a supressão do "
            "grito. AU 23 (lip tightener) é um marcador de contenção, enquanto "
            "AU 24 (lip presser) indica compressão ativa."
        ),
        "markers": ["AU 4: Brow Lowerer (corrugator supercilii)",
                     "AU 5: Upper Lid Raiser", "AU 7: Lid Tightener",
                     "AU 23: Lip Tightener / AU 24: Lip Presser"],
    },
    "disgust": {
        "label": "Nojo",
        "canonical_aus": "AU 9 / AU 10 + AU 17",
        "description": (
            "O enrugamento do nariz (AU 9) é o sinal mais confiável de nojo. "
            "A AU 10 é frequentemente usada como uma versão mais leve ou controlada. "
            "AU 17 (chin raiser) cria a textura granulada no queixo que acompanha "
            "a rejeição visceral."
        ),
        "markers": ["AU 9: Nose Wrinkler (levator labii superioris alaeque nasi)",
                     "AU 10: Upper Lip Raiser (levator labii superioris)",
                     "AU 17: Chin Raiser (mentalis)"],
    },
    "contempt": {
        "label": "Desprezo",
        "canonical_aus": "R12A / R14A (Unilateral)",
        "description": (
            "É a única emoção universal definida por sua assimetria. O puxão "
            "unilateral do canto da boca é o marcador técnico do desdém. "
            "A lateralidade (direita vs esquerda) pode indicar o alvo do desprezo."
        ),
        "markers": ["AU 12R: Unilateral Lip Corner Puller",
                     "AU 14R: Unilateral Dimpler (buccinator)"],
    },
    "neutral": {
        "label": "Neutro",
        "canonical_aus": "Nenhuma AU ativa",
        "description": (
            "Estado de repouso facial sem ativação muscular significativa. "
            "Serve como baseline para medição de todas as outras expressões. "
            "Características anatômicas permanentes não devem ser confundidas "
            "com sinais emocionais."
        ),
        "markers": [],
    },
}

# =============================================================================
# MARCADORES DE INCOERÊNCIA (Deception & Leakage Detection)
# =============================================================================
COHERENCE_MARKERS = {
    "reliable_muscles": {1, 4, 6, 7, 23},   # Difíceis de controlar voluntariamente
    "voluntary_muscles": {12, 14, 17, 20},   # Fáceis de controlar
    "false_smile_indicators": {7, 24},        # Tensão palpebral + lip press durante sorriso
    "leakage_aus": {1, 23},                   # Aparecem involuntariamente durante engano
    "max_genuine_surprise_ms": 1000,          # Surpresa > 1s = provável fabricação
    "symmetry_threshold_mm": 3.0,             # Assimetria > 3mm = possível desprezo/engano
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

IDENTITY_VAULT_URL = "http://identity-vault:3001"
REDIS_URL = "redis://redis:6379"
FROID_VOICE_URL = "http://froid-voice:3002"
