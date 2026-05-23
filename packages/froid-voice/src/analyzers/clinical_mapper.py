"""
FROID Voice - Mapeador Clínico Expandido
Scoring por constructo (9 riscos clínicos)

Constructos:
1. depression_risk - Risco de Depressão
2. mania_activation - Ativação Maníaca
3. stress_cognitive - Estresse Cognitivo
4. anxiety_generalized - Ansiedade Generalizada
5. psychosis_risk - Risco de Psicose
6. trauma_ptsd - Trauma/PTSD
7. suicide_risk - Risco de Suicídio
8. bipolar_pattern - Padrão Bipolar
9. schizophrenia_markers - Marcadores de Esquizofrenia

Fontes:
- Di et al. (2024): Marcadores de depressão
- Kaczmarek-Majer et al. (2024): Marcadores de mania
- Schewski et al. (2025): Marcadores de estresse
- Zhao et al. (2022): MFCC/ZCR para depressão/ansiedade
- Cummins et al. (2015): Marcadores de suicídio
- Cohen et al. (2019): Biomarcadores de psicose
"""
import numpy as np
from typing import Dict, List

# Pesos clínicos expandidos
CLINICAL_WEIGHTS_EXPANDED = {
    "depression_risk": {
        "F0semitoneFrom27.5Hz_sma3nz_amean": -0.4,  # F0 reduzida
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": -0.3,  # Menor variabilidade
        "loudness_sma3_amean": -0.2,  # Intensidade reduzida
        "jitterLocal_sma3nz_amean": 0.2,  # Jitter aumentado
        "shimmerLocaldB_sma3nz_amean": 0.2,  # Shimmer aumentado
    },
    "mania_activation": {
        "F0semitoneFrom27.5Hz_sma3nz_amean": 0.4,  # F0 elevada
        "loudness_sma3_amean": 0.4,  # Intensidade alta
        "spectralFlux_sma3_amean": 0.3,  # Fluxo espectral aumentado
        "jitterLocal_sma3nz_amean": -0.2,  # Jitter reduzido (voz firme)
    },
    "stress_cognitive": {
        "F0semitoneFrom27.5Hz_sma3nz_amean": 0.3,  # F0 elevada
        "loudness_sma3_amean": 0.3,  # Intensidade elevada
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": 0.2,  # Maior variabilidade
        "jitterLocal_sma3nz_amean": 0.2,  # Tensão vocal
    },
    "anxiety_generalized": {
        "F0semitoneFrom27.5Hz_sma3nz_amean": 0.35,  # F0 elevada (tensão)
        "jitterLocal_sma3nz_amean": 0.3,  # Jitter aumentado (tremor)
        "shimmerLocaldB_sma3nz_amean": 0.25,  # Shimmer aumentado
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": 0.3,  # Alta variabilidade (instabilidade)
        "loudness_sma3_amean": 0.2,  # Intensidade variável
    },
    "psychosis_risk": {
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": 0.4,  # Alta variabilidade prosódica
        "jitterLocal_sma3nz_amean": 0.3,  # Controle motor reduzido
        "spectralFlux_sma3_amean": 0.3,  # Instabilidade espectral
        "loudness_sma3_stddevNorm": 0.3,  # Variabilidade de intensidade
    },
    "trauma_ptsd": {
        "F0semitoneFrom27.5Hz_sma3nz_amean": -0.3,  # F0 reduzida (embotamento)
        "loudness_sma3_amean": -0.3,  # Intensidade reduzida
        "jitterLocal_sma3nz_amean": 0.25,  # Tensão vocal residual
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": -0.25,  # Prosódia achatada
    },
    "suicide_risk": {
        "F0semitoneFrom27.5Hz_sma3nz_amean": -0.4,  # F0 muito reduzida (desesperança)
        "loudness_sma3_amean": -0.35,  # Intensidade muito baixa
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": -0.35,  # Prosódia monotônica
        "jitterLocal_sma3nz_amean": 0.2,  # Tensão residual
    },
    "bipolar_pattern": {
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": 0.4,  # Alta instabilidade (ciclagem)
        "loudness_sma3_stddevNorm": 0.4,  # Variabilidade de energia
        "spectralFlux_sma3_stddevNorm": 0.3,  # Fluxo espectral variável
    },
    "schizophrenia_markers": {
        "F0semitoneFrom27.5Hz_sma3nz_stddevNorm": 0.35,  # Desorganização prosódica
        "jitterLocal_sma3nz_amean": 0.3,  # Controle motor comprometido
        "loudness_sma3_stddevNorm": 0.3,  # Variabilidade de intensidade
        "spectralFlux_sma3_amean": 0.25,  # Instabilidade espectral
    },
}

CLINICAL_THRESHOLDS_EXPANDED = {
    "depression_risk": 0.65,
    "mania_activation": 0.70,
    "stress_cognitive": 0.60,
    "anxiety_generalized": 0.60,
    "psychosis_risk": 0.75,
    "trauma_ptsd": 0.70,
    "suicide_risk": 0.80,  # Threshold alto (alta especificidade)
    "bipolar_pattern": 0.70,
    "schizophrenia_markers": 0.75,
}

class ClinicalMapper:
    """
    Calcula scores clínicos normalizados [0,1] para 9 constructos.
    Usa sigmoid para compressão probabilística dos scores brutos.
    """
    
    def compute_scores(self, norm_feats: Dict[str, float]) -> Dict[str, float]:
        """
        Gera scores normalizados [0,1] por constructo clínico.
        
        Args:
            norm_feats: Features normalizadas (z-scores suavizados)
            
        Returns:
            Dicionário com scores por constructo (9 riscos)
        """
        scores = {}
        for construct, weights in CLINICAL_WEIGHTS_EXPANDED.items():
            # Soma ponderada das features normalizadas
            raw = sum(norm_feats.get(k, 0.0) * w for k, w in weights.items())
            # Sigmoid para compressão em [0, 1]
            score = float(1.0 / (1.0 + np.exp(-raw)))
            scores[construct] = round(np.clip(score, 0.0, 1.0), 3)
        
        return scores
    
    def get_flags(self, scores: Dict[str, float]) -> List[Dict[str, str]]:
        """
        Retorna flags clínicos ativos quando scores excedem thresholds.
        
        Returns:
            Lista de flags com tipo, severidade e descrição
        """
        flags = []
        for construct, threshold in CLINICAL_THRESHOLDS_EXPANDED.items():
            score = scores.get(construct, 0.0)
            if score > threshold:
                severity = "high" if score > threshold + 0.15 else "medium"
                flags.append({
                    "flag_type": f"voice_{construct}",
                    "severity": severity,
                    "score": score,
                    "threshold": threshold,
                    "description": self._get_description(construct, score),
                    "clinical_note": "BIOMARCADOR SUPORTIVO. VALIDAÇÃO PROSPECTIVA NECESSÁRIA.",
                })
        
        return flags
    
    def _get_description(self, construct: str, score: float) -> str:
        """Gera descrição clínica legível para o profissional."""
        descriptions = {
            "depression_risk": (
                f"Indicadores vocais sugestivos de risco depressivo (score={score:.2f}). "
                f"Padrão: F0 reduzida, menor variabilidade, MFCC alterados. "
                f"Ref: Di et al. (2024), Zhao et al. (2022)."
            ),
            "mania_activation": (
                f"Indicadores vocais sugestivos de ativação maníaca (score={score:.2f}). "
                f"Padrão: Intensidade elevada, F0 alta, fluxo espectral aumentado. "
                f"Ref: Kaczmarek-Majer et al. (2024)."
            ),
            "stress_cognitive": (
                f"Indicadores vocais sugestivos de estresse cognitivo (score={score:.2f}). "
                f"Padrão: F0 elevada, intensidade alta, taxa de fala reduzida. "
                f"Ref: Schewski et al. (2025)."
            ),
            "anxiety_generalized": (
                f"Indicadores vocais sugestivos de ansiedade generalizada (score={score:.2f}). "
                f"Padrão: F0 elevada com alta variabilidade, jitter/shimmer aumentados. "
                f"Ref: Zhao et al. (2022)."
            ),
            "psychosis_risk": (
                f"Indicadores vocais sugestivos de risco psicótico (score={score:.2f}). "
                f"Padrão: Alta variabilidade prosódica, instabilidade espectral. "
                f"Ref: Cohen et al. (2019)."
            ),
            "trauma_ptsd": (
                f"Indicadores vocais sugestivos de trauma/PTSD (score={score:.2f}). "
                f"Padrão: F0 reduzida, prosódia achatada, embotamento afetivo. "
                f"Ref: Cummins et al. (2015)."
            ),
            "suicide_risk": (
                f"Indicadores vocais sugestivos de risco de suicídio (score={score:.2f}). "
                f"ATENÇÃO: Threshold alto para alta especificidade. Avaliação clínica imediata recomendada. "
                f"Padrão: F0 muito reduzida, monotonia, desesperança. "
                f"Ref: Cummins et al. (2015)."
            ),
            "bipolar_pattern": (
                f"Indicadores vocais sugestivos de padrão bipolar (score={score:.2f}). "
                f"Padrão: Alta instabilidade prosódica e energética (ciclagem). "
                f"Ref: Kaczmarek-Majer et al. (2024)."
            ),
            "schizophrenia_markers": (
                f"Indicadores vocais sugestivos de marcadores de esquizofrenia (score={score:.2f}). "
                f"Padrão: Desorganização prosódica, controle motor comprometido. "
                f"Ref: Cohen et al. (2019)."
            ),
        }
        return descriptions.get(construct, f"Score elevado para {construct}: {score:.2f}")
