"""
FROID Voice - Mapeador Clínico
Scoring por constructo (depression_risk, mania_activation, stress_cognitive)

Fontes:
- Di et al. (2024): Marcadores de depressão
- Kaczmarek-Majer et al. (2024): Marcadores de mania
- Schewski et al. (2025): Marcadores de estresse
- Zhao et al. (2022): MFCC/ZCR para depressão/ansiedade
"""

import numpy as np
from typing import Dict, List
from src.config import CLINICAL_WEIGHTS, CLINICAL_THRESHOLDS


class ClinicalMapper:
    """
    Calcula scores clínicos normalizados [0,1] por constructo.
    Usa sigmoid para compressão probabilística dos scores brutos.
    """

    def compute_scores(self, norm_feats: Dict[str, float]) -> Dict[str, float]:
        """
        Gera scores normalizados [0,1] por constructo clínico.
        
        Args:
            norm_feats: Features normalizadas (z-scores suavizados)
            
        Returns:
            Dicionário com scores por constructo
        """
        scores = {}
        for construct, weights in CLINICAL_WEIGHTS.items():
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
        for construct, threshold in CLINICAL_THRESHOLDS.items():
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
        }
        return descriptions.get(construct, f"Score elevado para {construct}: {score:.2f}")
