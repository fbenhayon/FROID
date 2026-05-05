"""
FROID Face - Classificador de Emoções
Mapeia combinações de AUs ativas para 7 emoções universais + contempt

Regra: Emoção válida APENAS se HMM detectou apex (via ExpressionHMM)
"""

import numpy as np
from typing import Dict, List, Optional
from src.facs.au_definitions import EMOTION_AU_RULES, EMOTION_VALENCE_AROUSAL


class EmotionClassifier:
    """
    Classifica emoções baseado em combinações de AUs detectadas.
    Usa regras FACS validadas + scoring de cobertura.
    """

    def classify(self, active_aus: List[Dict], hmm_result: Dict = None) -> Dict:
        """
        Classifica emoção dominante a partir das AUs ativas.

        Args:
            active_aus: Lista de AUs ativas (do ActionUnitClassifier)
            hmm_result: Resultado do ExpressionHMM (se disponível)

        Returns:
            Dict com emoção dominante, confiança, valence/arousal
        """
        if not active_aus:
            return self._neutral_result()

        # Se HMM disponível e não detectou apex → neutro
        if hmm_result and not hmm_result.get("detected", True):
            return self._neutral_result()

        # Extrair números das AUs ativas
        active_au_numbers = set(au["au_number"] for au in active_aus)
        au_intensities = {au["au_number"]: au["intensity"] for au in active_aus}

        # Avaliar cada emoção
        candidates = []
        for emotion, rules in EMOTION_AU_RULES.items():
            if emotion == "neutral":
                continue

            for rule in rules:
                required_aus = set(rule["aus"])
                if not required_aus:
                    continue

                # Cobertura: quantos AUs da regra estão presentes
                matched = required_aus & active_au_numbers
                coverage = len(matched) / len(required_aus) if required_aus else 0

                if coverage >= 0.6:  # Pelo menos 60% dos AUs necessários
                    # Confiança: cobertura × média de intensidade dos AUs matched
                    avg_intensity = np.mean([au_intensities.get(au, 0) for au in matched])
                    confidence = coverage * avg_intensity

                    candidates.append({
                        "emotion": emotion,
                        "rule_name": rule["name"],
                        "coverage": coverage,
                        "confidence": round(float(confidence), 3),
                        "matched_aus": sorted(list(matched)),
                        "required_aus": sorted(list(required_aus)),
                        "is_unilateral": rule.get("unilateral", False),
                    })

        if not candidates:
            return self._neutral_result()

        # Selecionar candidato com maior confiança
        best = max(candidates, key=lambda c: c["confidence"])

        # Valence e arousal
        va = EMOTION_VALENCE_AROUSAL.get(best["emotion"], {"valence": 0, "arousal": 0.2})

        # Genuineness score (baseado em músculos confiáveis)
        reliable_aus = [au for au in active_aus if au.get("is_reliable", False)]
        genuineness = len(reliable_aus) / max(len(active_aus), 1)

        # Microexpressão (do HMM)
        is_micro = hmm_result.get("is_microexpression", False) if hmm_result else False
        duration_ms = hmm_result.get("duration_ms", 0) if hmm_result else 0

        return {
            "emotion": best["emotion"],
            "confidence": best["confidence"],
            "rule_matched": best["rule_name"],
            "matched_aus": best["matched_aus"],
            "coverage": best["coverage"],
            "valence": va["valence"],
            "arousal": va["arousal"],
            "genuineness_score": round(genuineness, 3),
            "is_microexpression": is_micro,
            "duration_ms": duration_ms,
            "all_candidates": candidates,
        }

    def _neutral_result(self) -> Dict:
        return {
            "emotion": "neutral",
            "confidence": 1.0,
            "rule_matched": "neutral_baseline",
            "matched_aus": [],
            "coverage": 1.0,
            "valence": 0.0,
            "arousal": 0.2,
            "genuineness_score": 1.0,
            "is_microexpression": False,
            "duration_ms": 0,
            "all_candidates": [],
        }
