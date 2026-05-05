"""
FROID Face - Classificador de Emoções (v4.0 Científico)
Mapeamento AU → Emoção usando tabela EXATA fornecida pelo usuário
"""

from typing import Dict, List, Set
from src.config import AU_TO_EMOTION_RULES, ClinicalThresholds


class EmotionClassifier:
    """Classificador de emoções baseado em combinações de Action Units."""

    def __init__(self, min_coverage=0.70, au_activation_threshold=None):
        self.min_coverage = min_coverage
        self.au_threshold = au_activation_threshold or ClinicalThresholds.AU_ACTIVATION_THRESHOLD
        self.rules = AU_TO_EMOTION_RULES

    def classify(self, au_scores, hmm_confidence=1.0, require_apex=True):
        """Classifica emoção baseado em scores de AUs."""
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
            "missing_aus": []
        }
        
        for emotion, rule_sets in self.rules.items():
            for rule_idx, rule in enumerate(rule_sets):
                if not rule:
                    continue
                
                intersection = active_aus.intersection(rule)
                coverage = len(intersection) / len(rule) if len(rule) > 0 else 0.0
                
                if coverage >= self.min_coverage:
                    final_confidence = min(1.0, coverage * hmm_confidence)
                    
                    if final_confidence > best_match["confidence"]:
                        best_match.update({
                            "emotion": emotion,
                            "confidence": round(final_confidence, 3),
                            "matched_rule": sorted(list(rule)),
                            "coverage": round(coverage, 3),
                            "rule_index": rule_idx,
                            "missing_aus": sorted(list(rule - active_aus))
                        })
        
        best_match.update(self._estimate_valence_arousal(best_match["emotion"]))
        return best_match

    def _neutral_result(self, active_aus):
        """Retorna resultado neutral."""
        return {
            "emotion": "neutral",
            "confidence": 1.0,
            "matched_rule": [],
            "coverage": 1.0,
            "rule_index": 0,
            "active_aus": sorted(list(active_aus)),
            "missing_aus": [],
            "valence": 0.0,
            "arousal": 0.0
        }

    def _estimate_valence_arousal(self, emotion):
        """Estima valence e arousal baseado na emoção."""
        mapping = {
            "happy": {"valence": 0.8, "arousal": 0.6},
            "surprise": {"valence": 0.3, "arousal": 0.8},
            "neutral": {"valence": 0.0, "arousal": 0.0},
            "sadness": {"valence": -0.7, "arousal": 0.3},
            "fear": {"valence": -0.6, "arousal": 0.8},
            "anger": {"valence": -0.5, "arousal": 0.9},
            "disgust": {"valence": -0.8, "arousal": 0.5},
            "contempt": {"valence": -0.4, "arousal": 0.4}
        }
        return mapping.get(emotion.lower(), {"valence": 0.0, "arousal": 0.0})

    def get_emotion_description(self, emotion):
        """Retorna descrição textual da emoção em português."""
        descriptions = {
            "happy": "Felicidade/Alegria",
            "sadness": "Tristeza",
            "surprise": "Surpresa",
            "fear": "Medo",
            "anger": "Raiva/Ira",
            "disgust": "Nojo/Desgosto",
            "contempt": "Desprezo",
            "neutral": "Neutro/Sem expressão"
        }
        return descriptions.get(emotion.lower(), "Desconhecido")

    def validate_au_combination(self, aus):
        """Valida quais emoções podem ser expressas com esta combinação de AUs."""
        au_set = set(aus)
        matches = {}
        
        for emotion, rule_sets in self.rules.items():
            emotion_matches = []
            for rule_idx, rule in enumerate(rule_sets):
                if rule.issubset(au_set):
                    emotion_matches.append(f"Rule {rule_idx}: {sorted(list(rule))}")
            
            if emotion_matches:
                matches[emotion] = emotion_matches
        
        return matches

    def get_genuineness_score(self, au_scores):
        """Calcula score de genuinidade baseado em músculos confiáveis vs voluntários."""
        RELIABLE_AUS = {1, 4, 6, 7}
        VOLUNTARY_AUS = {12, 17}
        
        reliable_active = sum(1 for au in RELIABLE_AUS if au in au_scores and au_scores[au] >= self.au_threshold)
        voluntary_active = sum(1 for au in VOLUNTARY_AUS if au in au_scores and au_scores[au] >= self.au_threshold)
        
        total_active = reliable_active + voluntary_active
        
        if total_active == 0:
            return 0.5
        
        genuineness = reliable_active / total_active
        return round(genuineness, 3)
