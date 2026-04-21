"""
FROID Voice - Normalizador de Sessão
Baseline 60s + Ajuste por Sexo Biológico + EMA Smoothing

Fontes:
- Aguiar et al. (2025): z-score por baseline individual
- Kaczmarek-Majer et al. (2024): Inversão de sinal por sexo em TB
"""

import numpy as np
from collections import defaultdict
from typing import Dict, Optional
from src.config import SEX_INVERT_PARAMS, SEX_INVERT_FACTOR, EMA_ALPHA


class SessionNormalizer:
    """
    Normaliza features vocais contra a baseline individual do paciente.
    
    Fluxo:
    1. Primeiros 60s: acumula samples para calibração
    2. Após calibração: normaliza (delta = valor - baseline)
    3. Aplica inversão por sexo se necessário
    4. Suaviza com EMA (Exponential Moving Average)
    """

    def __init__(self, session_id: str, sex: str = "M"):
        self.session_id = session_id
        self.sex = sex.upper()
        self.baseline_samples: Dict[str, list] = defaultdict(list)
        self.baseline_means: Dict[str, float] = {}
        self.baseline_stds: Dict[str, float] = {}
        self.is_calibrated = False
        self.ema: Dict[str, float] = {}
        self.alpha = EMA_ALPHA
        self.sample_count = 0

    def add_baseline_sample(self, feats: Dict[str, float]):
        """Acumula amostra durante fase de calibração (primeiros 60s)."""
        self.sample_count += 1
        for k, v in feats.items():
            if isinstance(v, (int, float)) and not np.isnan(v):
                self.baseline_samples[k].append(v)

    def calibrate(self) -> Dict[str, float]:
        """
        Calcula médias e desvios da baseline.
        Chamado automaticamente após 60s de coleta.
        
        Returns:
            Dicionário com médias da baseline
        """
        for k, values in self.baseline_samples.items():
            if len(values) > 0:
                self.baseline_means[k] = float(np.mean(values))
                self.baseline_stds[k] = float(np.std(values)) if len(values) > 1 else 1.0
            else:
                self.baseline_means[k] = 0.0
                self.baseline_stds[k] = 1.0

        # Inicializar EMA em zero (delta = 0 no início)
        for k in self.baseline_means:
            self.ema[k] = 0.0

        self.is_calibrated = True
        return dict(self.baseline_means)

    def normalize_and_smooth(self, raw_feats: Dict[str, float]) -> Dict[str, float]:
        """
        Normaliza features contra baseline, ajusta por sexo e aplica EMA.
        
        Args:
            raw_feats: Features brutas extraídas pelo openSMILE
            
        Returns:
            Features normalizadas e suavizadas
        """
        if not self.is_calibrated:
            return {}

        norm_feats = {}
        for k, v in raw_feats.items():
            if k not in self.baseline_means:
                continue

            # Delta: quanto o valor atual difere da baseline
            baseline_val = self.baseline_means[k]
            baseline_std = self.baseline_stds[k]

            # Z-score normalizado (Aguiar et al., 2025)
            if baseline_std > 0.001:
                delta = (v - baseline_val) / baseline_std
            else:
                delta = v - baseline_val

            # Inversão por sexo biológico (Kaczmarek-Majer et al., 2024)
            # Em transtorno bipolar, mulheres exibem padrões inversos
            # em F0, Intensidade e Fluxo Espectral
            if self.sex == "F" and k in SEX_INVERT_PARAMS:
                delta *= SEX_INVERT_FACTOR

            # Suavização EMA (reduz ruído frame-a-frame)
            previous = self.ema.get(k, delta)
            smoothed = self.alpha * delta + (1 - self.alpha) * previous
            self.ema[k] = smoothed

            norm_feats[k] = smoothed

        return norm_feats

    def get_calibration_progress(self, elapsed_sec: float, target_sec: float = 60.0) -> float:
        """Retorna progresso da calibração (0.0 a 1.0)."""
        return min(1.0, elapsed_sec / target_sec)

    def get_baseline_summary(self) -> Dict[str, Dict[str, float]]:
        """Retorna resumo da baseline para debug/relatório."""
        return {
            k: {"mean": self.baseline_means.get(k, 0), "std": self.baseline_stds.get(k, 0)}
            for k in self.baseline_means
        }
