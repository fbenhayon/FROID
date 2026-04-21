"""
FROID Face - Definições FACS
46 Action Units + mapeamento Emoção → combinação de AUs

Fontes:
- Ekman & Friesen FACS Manual
- API Facial Parte 1 (combinações validadas)
- Tabela AU fornecida pelo usuário
"""

# 46 Action Units com músculos associados
AU_DEFINITIONS = {
    1:  {"name": "Inner brow raiser",     "muscle": "Frontalis (pars medialis)",          "reliable": True},
    2:  {"name": "Outer brow raiser",     "muscle": "Frontalis (pars lateralis)",         "reliable": True},
    4:  {"name": "Brow lowerer",          "muscle": "Corrugator supercilii",              "reliable": True},
    5:  {"name": "Upper lid raiser",      "muscle": "Levator palpebrae superioris",       "reliable": True},
    6:  {"name": "Cheek raiser",          "muscle": "Orbicularis oculi (pars orbitalis)", "reliable": True},
    7:  {"name": "Lid tightener",         "muscle": "Orbicularis oculi (pars palpebralis)", "reliable": True},
    9:  {"name": "Nose wrinkler",         "muscle": "Levator labii superioris alaeque nasi", "reliable": True},
    10: {"name": "Upper lip raiser",      "muscle": "Levator labii superioris",           "reliable": False},
    11: {"name": "Nasolabial deepener",   "muscle": "Zygomaticus minor",                 "reliable": False},
    12: {"name": "Lip corner puller",     "muscle": "Zygomaticus major",                 "reliable": False},
    13: {"name": "Sharp lip puller",      "muscle": "Levator anguli oris",               "reliable": False},
    14: {"name": "Dimpler",               "muscle": "Buccinator",                         "reliable": False},
    15: {"name": "Lip corner depressor",  "muscle": "Depressor anguli oris",             "reliable": False},
    17: {"name": "Chin raiser",           "muscle": "Mentalis",                           "reliable": False},
    20: {"name": "Lip stretcher",         "muscle": "Risorius with platysma",            "reliable": False},
    23: {"name": "Lip tightener",         "muscle": "Orbicularis oris",                  "reliable": False},
    24: {"name": "Lip pressor",           "muscle": "Orbicularis oris",                  "reliable": False},
    25: {"name": "Lips part",             "muscle": "Depressor labii inferioris",         "reliable": False},
    26: {"name": "Jaw drop",             "muscle": "Masseter, pterygoids",               "reliable": False},
    27: {"name": "Mouth stretch",         "muscle": "Pterygoids, digastric",             "reliable": False},
    43: {"name": "Eyes closed",           "muscle": "Orbicularis oculi",                  "reliable": True},
    45: {"name": "Blink",                 "muscle": "Orbicularis oculi",                  "reliable": True},
}

# Músculos CONFIÁVEIS (involuntários/extrapiramidais) - dificil de simular
RELIABLE_MUSCLES = {
    1: "Frontalis medial",       # Tristeza genuína
    4: "Corrugator supercilii",  # Preocupação real
    6: "Orbicularis oculi orb.", # Sorriso de Duchenne
    7: "Orbicularis oculi palp.",# Tensão genuína
    43: "Orbicularis oculi",     # Fechamento involuntário
}

# Músculos VOLUNTÁRIOS (piramidais) - podem ser simulados
VOLUNTARY_MUSCLES = {
    12: "Zygomaticus major",     # Sorriso social
    17: "Mentalis",              # Expressão deliberada
    24: "Orbicularis oris",      # Controle labial
}

# Mapeamento Emoção → Combinações de AUs (API Facial + tabela fornecida)
EMOTION_AU_RULES = {
    "happy": [
        {"aus": [12], "name": "happy_simple"},
        {"aus": [6, 12], "name": "happy_duchenne"},
    ],
    "sadness": [
        {"aus": [1, 4, 15], "name": "sadness_1"},
        {"aus": [1, 4, 11], "name": "sadness_2"},
        {"aus": [1, 4, 15, 17], "name": "sadness_full"},
        {"aus": [6, 15], "name": "sadness_3"},
    ],
    "surprise": [
        {"aus": [1, 2, 5, 26], "name": "surprise_full"},
        {"aus": [1, 2, 5, 27], "name": "surprise_intense"},
        {"aus": [1, 2, 5], "name": "surprise_basic"},
        {"aus": [5, 26], "name": "surprise_minimal"},
    ],
    "fear": [
        {"aus": [1, 2, 4, 5, 20, 26], "name": "fear_full"},
        {"aus": [1, 2, 4, 5, 20, 25], "name": "fear_variant"},
        {"aus": [1, 2, 4, 5], "name": "fear_basic"},
        {"aus": [5, 20, 26], "name": "fear_minimal"},
    ],
    "anger": [
        {"aus": [4, 5, 7, 23, 24], "name": "anger_controlled"},
        {"aus": [4, 5, 7, 10, 22, 23, 25], "name": "anger_full"},
        {"aus": [4, 5, 7, 17, 23], "name": "anger_chin"},
    ],
    "disgust": [
        {"aus": [9, 17], "name": "disgust_nose"},
        {"aus": [10, 17], "name": "disgust_lip"},
        {"aus": [9, 16, 25], "name": "disgust_full"},
    ],
    "contempt": [
        {"aus": [12, 14], "name": "contempt_unilateral", "unilateral": True},
    ],
    "neutral": [
        {"aus": [], "name": "neutral_baseline"},
    ],
}

# Mapeamento de valence e arousal por emoção
EMOTION_VALENCE_AROUSAL = {
    "happy":    {"valence": 0.8,  "arousal": 0.7},
    "sadness":  {"valence": -0.7, "arousal": 0.3},
    "surprise": {"valence": 0.2,  "arousal": 0.9},
    "fear":     {"valence": -0.6, "arousal": 0.85},
    "anger":    {"valence": -0.8, "arousal": 0.8},
    "disgust":  {"valence": -0.9, "arousal": 0.55},
    "contempt": {"valence": -0.5, "arousal": 0.4},
    "neutral":  {"valence": 0.0,  "arousal": 0.2},
}
