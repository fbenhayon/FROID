"""
FROID Fusion - Motor de Fusão Multimodal
Combina análise facial + vocal para detecção de incongruência

Ponderação dinâmica por contexto clínico:
- Depressão: face (0.4) + voice (0.6) — voz mais preditiva
- Ansiedade: face (0.7) + voice (0.3) — face mais preditiva
- TEPT: face (0.5) + voice (0.5) — incongruência é o sinal

Fonte: API Facial Parte 4 (fusion_engine.py) + Plano 4B (IPM)
"""

import numpy as np
from typing import Dict, List, Optional


# Ponderação dinâmica por contexto clínico
FUSION_WEIGHTS = {
    "initial_evaluation":    {"face": 0.60, "voice": 0.40},
    "follow_up_depression":  {"face": 0.40, "voice": 0.60},
    "follow_up_anxiety":     {"face": 0.70, "voice": 0.30},
    "ptsd_assessment":       {"face": 0.50, "voice": 0.50},
    "medication_review":     {"face": 0.60, "voice": 0.40},
    "therapy_session":       {"face": 0.55, "voice": 0.45},
    "default":               {"face": 0.60, "voice": 0.40},
}


class MultimodalFusionEngine:
    """
    Fusão dinâmica Face-Voz com detecção de incongruência clínica.
    
    Dois scores de fusão:
    1. Congruence Score (0-1): similaridade de cosseno no espaço valence-arousal
    2. IPM - Índice de Percepção Móvel (0-1): score ponderado FROID proprietário
    """

    def __init__(self):
        self.history: List[Dict] = []

    def fuse(
        self,
        face_data: Dict,
        voice_data: Dict,
        clinical_context: str = "default",
    ) -> Dict:
        """
        Fusão multimodal de dados faciais e vocais.

        Args:
            face_data: {valence, arousal, emotion, confidence, genuineness_score}
            voice_data: {depression_risk, mania_activation, stress_cognitive, f0_mean, ...}
            clinical_context: Contexto clínico para ponderação

        Returns:
            Dict com scores de fusão, incongruência e recomendações
        """
        weights = FUSION_WEIGHTS.get(clinical_context, FUSION_WEIGHTS["default"])

        # ============================================================
        # 1. CONGRUENCE SCORE (similaridade de cosseno)
        # ============================================================
        face_valence = face_data.get("valence", 0.0)
        face_arousal = face_data.get("arousal", 0.2)

        # Derivar valence/arousal da voz a partir dos scores clínicos
        voice_valence = self._voice_to_valence(voice_data)
        voice_arousal = self._voice_to_arousal(voice_data)

        congruence = self._cosine_congruence(
            face_valence, face_arousal, voice_valence, voice_arousal
        )

        # ============================================================
        # 2. IPM - Índice de Percepção Móvel (proprietário FROID)
        # ============================================================
        # IPM = w_face * face_score + w_voice * voice_score
        face_score = self._compute_face_composite(face_data)
        voice_score = self._compute_voice_composite(voice_data)

        ipm = (weights["face"] * face_score + weights["voice"] * voice_score)
        ipm = round(np.clip(ipm, 0.0, 1.0), 3)

        # ============================================================
        # 3. DETECÇÃO DE INCONGRUÊNCIA
        # ============================================================
        incongruence_flag = congruence < 0.5
        severity = "low"
        if congruence < 0.3:
            severity = "critical"
        elif congruence < 0.4:
            severity = "high"
        elif congruence < 0.5:
            severity = "medium"

        # ============================================================
        # 4. FLAGS CLÍNICOS DE FUSÃO
        # ============================================================
        clinical_flags = []

        if incongruence_flag:
            face_emotion = face_data.get("emotion", "neutral")
            voice_affect = self._classify_voice_affect(voice_data)
            clinical_flags.append({
                "flag_type": "incongruence",
                "severity": severity,
                "congruence_score": congruence,
                "description": self._incongruence_description(face_emotion, voice_affect, congruence),
                "face_emotion": face_emotion,
                "voice_affect": voice_affect,
                "face_valence": face_valence,
                "voice_valence": voice_valence,
                "suggested_action": self._suggest_action(face_emotion, voice_affect),
            })

        # Verificar dissimulação (sorriso + voz flat/negativa)
        if (face_data.get("emotion") == "happy" and
            face_data.get("genuineness_score", 1.0) < 0.5):
            clinical_flags.append({
                "flag_type": "low_genuineness",
                "severity": "medium",
                "description": "Sorriso possivelmente não genuíno (genuineness < 0.5). "
                               "Músculos voluntários dominantes sobre involuntários.",
                "genuineness_score": face_data.get("genuineness_score"),
            })

        # ============================================================
        # 5. RESULTADO CONSOLIDADO
        # ============================================================
        result = {
            "congruence_score": round(congruence, 3),
            "ipm": ipm,
            "incongruence_detected": incongruence_flag,
            "incongruence_severity": severity,
            "weights_applied": weights,
            "clinical_context": clinical_context,
            "face_valence": round(face_valence, 3),
            "face_arousal": round(face_arousal, 3),
            "voice_valence": round(voice_valence, 3),
            "voice_arousal": round(voice_arousal, 3),
            "clinical_flags": clinical_flags,
            "clinical_valence": self._overall_valence(face_valence, voice_valence, weights),
            "clinical_arousal": self._overall_arousal(face_arousal, voice_arousal, weights),
        }

        # Adicionar ao histórico para análise de tendência
        self.history.append(result)

        return result

    def _cosine_congruence(self, f_val, f_aro, v_val, v_aro) -> float:
        """Score de congruência via similaridade de cosseno no espaço valence-arousal."""
        vec_face = np.array([f_val, f_aro])
        vec_voice = np.array([v_val, v_aro])

        norm_f = np.linalg.norm(vec_face)
        norm_v = np.linalg.norm(vec_voice)

        if norm_f < 0.01 or norm_v < 0.01:
            return 0.5  # Neutro se vetores muito pequenos

        cos_sim = float(np.dot(vec_face, vec_voice) / (norm_f * norm_v))
        return round((cos_sim + 1.0) / 2.0, 3)  # Normalizar de [-1,1] para [0,1]

    def _voice_to_valence(self, voice_data: Dict) -> float:
        """Deriva valence da voz a partir dos scores clínicos."""
        dep = voice_data.get("depression_risk", 0.5)
        mania = voice_data.get("mania_activation", 0.5)
        # Depressão alta → valence negativa, Mania alta → valence positiva
        return round(np.clip((mania - dep) * 1.5, -1.0, 1.0), 3)

    def _voice_to_arousal(self, voice_data: Dict) -> float:
        """Deriva arousal da voz a partir dos scores clínicos."""
        stress = voice_data.get("stress_cognitive", 0.5)
        mania = voice_data.get("mania_activation", 0.5)
        return round(np.clip((stress + mania) / 2.0, 0.0, 1.0), 3)

    def _compute_face_composite(self, face_data: Dict) -> float:
        """Score composto facial (0-1)."""
        confidence = face_data.get("confidence", 0.5)
        genuineness = face_data.get("genuineness_score", 0.5)
        return (confidence * 0.6 + genuineness * 0.4)

    def _compute_voice_composite(self, voice_data: Dict) -> float:
        """Score composto vocal (0-1) — inverso do risco."""
        dep = voice_data.get("depression_risk", 0.5)
        stress = voice_data.get("stress_cognitive", 0.5)
        return 1.0 - (dep * 0.6 + stress * 0.4)

    def _classify_voice_affect(self, voice_data: Dict) -> str:
        """Classifica affect vocal a partir dos scores."""
        dep = voice_data.get("depression_risk", 0)
        mania = voice_data.get("mania_activation", 0)
        stress = voice_data.get("stress_cognitive", 0)

        if dep > 0.65:
            return "flat/depressed"
        elif mania > 0.60:
            return "elevated/manic"
        elif stress > 0.68:
            return "anxious/stressed"
        else:
            return "neutral"

    def _incongruence_description(self, face_emotion, voice_affect, score) -> str:
        """Gera descrição clínica da incongruência."""
        return (
            f"Incongruência face-voz detectada (score={score:.2f}). "
            f"Face: {face_emotion}, Voz: {voice_affect}. "
            f"Possível dissimulação emocional ou processamento interno conflitante."
        )

    def _suggest_action(self, face_emotion, voice_affect) -> str:
        """Sugere ação ao profissional."""
        if face_emotion == "happy" and "flat" in voice_affect:
            return "Explorar se o paciente está minimizando dificuldades emocionais."
        elif face_emotion == "neutral" and "anxious" in voice_affect:
            return "Investigar ansiedade internalizada não expressa facialmente."
        elif "anger" in face_emotion and "neutral" in voice_affect:
            return "Avaliar possível controle emocional ou raiva contida."
        else:
            return "Explorar conteúdo emocional do relato atual."

    def _overall_valence(self, f_val, v_val, weights) -> str:
        """Classificação geral de valence."""
        combined = f_val * weights["face"] + v_val * weights["voice"]
        if combined > 0.3:
            return "positive"
        elif combined < -0.3:
            return "negative"
        else:
            return "neutral"

    def _overall_arousal(self, f_aro, v_aro, weights) -> str:
        """Classificação geral de arousal."""
        combined = f_aro * weights["face"] + v_aro * weights["voice"]
        if combined > 0.66:
            return "high"
        elif combined > 0.33:
            return "moderate"
        else:
            return "low"

    def get_session_summary(self) -> Dict:
        """Retorna resumo da sessão para relatório."""
        if not self.history:
            return {"total_readings": 0}

        congruences = [h["congruence_score"] for h in self.history]
        ipms = [h["ipm"] for h in self.history]
        incongruent_pct = sum(1 for h in self.history if h["incongruence_detected"]) / len(self.history)

        return {
            "total_readings": len(self.history),
            "avg_congruence": round(float(np.mean(congruences)), 3),
            "min_congruence": round(float(np.min(congruences)), 3),
            "avg_ipm": round(float(np.mean(ipms)), 3),
            "incongruence_percentage": round(incongruent_pct * 100, 1),
            "total_flags": sum(len(h["clinical_flags"]) for h in self.history),
        }
