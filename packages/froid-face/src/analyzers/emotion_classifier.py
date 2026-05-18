"""
FROID Face - Classificador de Emoções (v5.0 EMFACS Científico)
Mapeamento AU -> Emoção baseado em EMFACS (Ekman & Friesen)
Refs: PMC3008166, PMC4157835, paulekman.com/facs

Inclui:
- Classificação das 7 emoções universais + neutral
- Detecção de blends (mesclas emocionais)
- Score de genuinidade (Duchenne markers)
- Detecção de incoerência/vazamento emocional
- Tooltips científicos para profissionais
"""

from typing import Dict, List, Set, Optional
from src.config import (
    AU_TO_EMOTION_RULES,
    EMOTION_DESCRIPTIONS,
    COHERENCE_MARKERS,
    ClinicalThresholds,
)


class EmotionClassifier:
    """Classificador de emoções baseado em EMFACS com detecção de incoerência."""

    def __init__(self, min_coverage=0.50, au_activation_threshold=None):
        self.min_coverage = min_coverage
        self.au_threshold = au_activation_threshold or ClinicalThresholds.AU_ACTIVATION_THRESHOLD
        self.rules = AU_TO_EMOTION_RULES
        self.descriptions = EMOTION_DESCRIPTIONS
        self.coherence = COHERENCE_MARKERS

    def classify(self, au_scores: Dict[int, float], hmm_confidence: float = 1.0,
                 require_apex: bool = False) -> dict:
        """
        Classifica emoção baseado em scores de AUs.
        Prioriza regras canônicas (index 0) com bonus de confiança.
        """
        active_aus = {au for au, score in au_scores.items() if score >= self.au_threshold}

        if require_apex and hmm_confidence < ClinicalThresholds.APEX_CONFIDENCE_MIN:
            return self._neutral_result(active_aus)

        best_match = {
            "emotion": "neutral",
            "confidence": 0.0,
            "matched_rule": [],
            "coverage": 0.0,
            "rule_index": -1,
            "active_aus": sorted(list(active_aus)),
            "missing_aus": [],
            "is_canonical": False,
        }

        for emotion, rule_sets in self.rules.items():
            for rule_idx, rule in enumerate(rule_sets):
                if not rule:
                    continue

                intersection = active_aus.intersection(rule)
                coverage = len(intersection) / len(rule) if len(rule) > 0 else 0.0

                if coverage >= self.min_coverage:
                    # Bonus para regra canônica (index 0)
                    canonical_bonus = 0.15 if rule_idx == 0 else 0.0
                    # Bonus para cobertura completa
                    complete_bonus = 0.10 if coverage >= 1.0 else 0.0
                    final_confidence = min(1.0, coverage * hmm_confidence + canonical_bonus + complete_bonus)

                    if final_confidence > best_match["confidence"]:
                        best_match.update({
                            "emotion": emotion,
                            "confidence": round(final_confidence, 3),
                            "matched_rule": sorted(list(rule)),
                            "coverage": round(coverage, 3),
                            "rule_index": rule_idx,
                            "missing_aus": sorted(list(rule - active_aus)),
                            "is_canonical": rule_idx == 0,
                        })

        # Enriquecer com valence/arousal e descrição
        best_match.update(self._estimate_valence_arousal(best_match["emotion"]))

        # Detecção de blend (mescla emocional)
        blend = self._detect_blend(active_aus, best_match["emotion"])
        if blend:
            best_match["blend"] = blend

        # Genuinidade
        best_match["genuineness"] = self.get_genuineness_score(au_scores)

        # Incoerência/vazamento
        leakage = self._detect_leakage(au_scores, best_match["emotion"])
        if leakage:
            best_match["leakage_flags"] = leakage

        return best_match

    def _detect_blend(self, active_aus: Set[int], primary_emotion: str) -> Optional[dict]:
        """Detecta mesclas emocionais (ex: nostalgia = alegria + tristeza)."""
        secondary_matches = []

        for emotion, rule_sets in self.rules.items():
            if emotion == primary_emotion or emotion == "neutral":
                continue
            for rule in rule_sets:
                if not rule:
                    continue
                coverage = len(active_aus.intersection(rule)) / len(rule) if rule else 0
                if coverage >= 0.60:
                    secondary_matches.append({
                        "emotion": emotion,
                        "coverage": round(coverage, 2),
                    })
                    break  # Pegar apenas a melhor regra por emoção

        if secondary_matches:
            return {
                "is_blend": True,
                "secondary_emotions": secondary_matches,
                "interpretation": self._interpret_blend(primary_emotion, secondary_matches),
            }
        return None

    def _interpret_blend(self, primary: str, secondaries: list) -> str:
        """Interpreta blends comuns."""
        secondary_names = {s["emotion"] for s in secondaries}
        blends = {
            frozenset({"happy", "sadness"}): "Nostalgia / Saudade",
            frozenset({"happy", "anger"}): "Possível crueldade / Schadenfreude",
            frozenset({"fear", "surprise"}): "Susto / Alarme",
            frozenset({"anger", "disgust"}): "Indignação moral",
            frozenset({"sadness", "anger"}): "Frustração profunda",
        }
        combo = frozenset({primary} | secondary_names)
        for key, interpretation in blends.items():
            if key.issubset(combo):
                return interpretation
        return "Mescla emocional complexa"

    def _detect_leakage(self, au_scores: Dict[int, float], detected_emotion: str) -> list:
        """Detecta vazamento emocional (AUs involuntárias inconsistentes com emoção declarada)."""
        flags = []
        reliable = self.coherence["reliable_muscles"]
        leakage_aus = self.coherence["leakage_aus"]

        active_reliable = {au for au in reliable if au in au_scores and au_scores[au] >= self.au_threshold}
        active_leakage = {au for au in leakage_aus if au in au_scores and au_scores[au] >= self.au_threshold}

        # AU 1 durante discurso positivo/neutro = possível vazamento de tristeza
        if 1 in active_leakage and detected_emotion in ("happy", "neutral"):
            flags.append({
                "type": "emotional_leakage",
                "au": 1,
                "description": "AU 1 (Inner Brow Raiser) durante expressão positiva/neutra - possível tristeza suprimida",
            })

        # AU 23 durante sorriso = possível raiva contida
        if 23 in active_reliable and detected_emotion == "happy":
            flags.append({
                "type": "suppression",
                "au": 23,
                "description": "AU 23 (Lip Tightener) durante sorriso - possível raiva/contenção",
            })

        # False smile indicators durante happy
        if detected_emotion == "happy":
            false_indicators = self.coherence["false_smile_indicators"]
            active_false = {au for au in false_indicators if au in au_scores and au_scores[au] >= self.au_threshold}
            if active_false and 6 not in au_scores:
                flags.append({
                    "type": "false_smile",
                    "aus": sorted(list(active_false)),
                    "description": "Sorriso sem Duchenne marker (AU 6) com tensão palpebral - sorriso voluntário/mascarado",
                })

        return flags

    def _neutral_result(self, active_aus: Set[int]) -> dict:
        """Retorna resultado neutral."""
        return {
            "emotion": "neutral",
            "confidence": 1.0,
            "matched_rule": [],
            "coverage": 1.0,
            "rule_index": 0,
            "active_aus": sorted(list(active_aus)),
            "missing_aus": [],
            "is_canonical": True,
            "valence": 0.0,
            "arousal": 0.0,
            "genuineness": 0.5,
        }

    def _estimate_valence_arousal(self, emotion: str) -> dict:
        """Estima valence e arousal baseado na emoção (Russell's circumplex model)."""
        mapping = {
            "happy":    {"valence":  0.8, "arousal": 0.6},
            "surprise": {"valence":  0.3, "arousal": 0.8},
            "neutral":  {"valence":  0.0, "arousal": 0.0},
            "sadness":  {"valence": -0.7, "arousal": 0.3},
            "fear":     {"valence": -0.6, "arousal": 0.8},
            "anger":    {"valence": -0.5, "arousal": 0.9},
            "disgust":  {"valence": -0.8, "arousal": 0.5},
            "contempt": {"valence": -0.4, "arousal": 0.4},
        }
        return mapping.get(emotion.lower(), {"valence": 0.0, "arousal": 0.0})

    def get_emotion_description(self, emotion: str) -> dict:
        """Retorna descrição científica completa para tooltip do profissional."""
        return self.descriptions.get(emotion.lower(), {
            "label": "Desconhecido",
            "canonical_aus": "",
            "description": "",
            "markers": [],
        })

    def get_all_descriptions(self) -> Dict[str, dict]:
        """Retorna todas as descrições para popular tooltips no frontend."""
        return self.descriptions

    def get_genuineness_score(self, au_scores: Dict[int, float]) -> float:
        """
        Calcula score de genuinidade baseado em músculos confiáveis vs voluntários.
        Músculos confiáveis (involuntários) indicam expressão genuína.
        """
        reliable = self.coherence["reliable_muscles"]
        voluntary = self.coherence["voluntary_muscles"]

        reliable_active = sum(1 for au in reliable if au in au_scores and au_scores[au] >= self.au_threshold)
        voluntary_active = sum(1 for au in voluntary if au in au_scores and au_scores[au] >= self.au_threshold)

        total_active = reliable_active + voluntary_active

        if total_active == 0:
            return 0.5

        genuineness = reliable_active / total_active
        return round(genuineness, 3)

    def validate_au_combination(self, aus: list) -> dict:
        """Valida quais emoções podem ser expressas com esta combinação de AUs."""
        au_set = set(aus)
        matches = {}

        for emotion, rule_sets in self.rules.items():
            emotion_matches = []
            for rule_idx, rule in enumerate(rule_sets):
                if rule.issubset(au_set):
                    label = "CANÔNICA" if rule_idx == 0 else f"Variação {rule_idx}"
                    emotion_matches.append(f"{label}: {sorted(list(rule))}")

            if emotion_matches:
                matches[emotion] = emotion_matches

        return matches
