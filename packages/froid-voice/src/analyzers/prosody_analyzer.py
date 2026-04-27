"""
FROID Voice - Analisador de Prosódia
F0 (pitch), Jitter, Shimmer, HNR via Parselmouth (wrapper Praat)

Atualizado a cada 500ms para gráficos dinâmicos no dashboard.
Fonte: Plano 4B original
"""

import numpy as np
# import parselmouth  # Comentado temporariamente para build
# sound = parselmouth.Sound(...)  # Exemplo
# from parselmouth.praat import call  # Comentado temporariamente!
from typing import Dict, Optional


class ProsodyAnalyzer:
    """
    Extrai parâmetros prosódicos via Parselmouth (Praat):
    - F0 (pitch): média, desvio padrão, contorno temporal
    - Jitter: perturbação de frequência (instabilidade vocal → estresse)
    - Shimmer: perturbação de amplitude (fadiga neurológica)
    - HNR: Harmonics-to-Noise Ratio (tensão na fonação)
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        # Faixas de pitch por sexo (Praat recomendado)
        self.pitch_floor = {"M": 75, "F": 100, "default": 75}
        self.pitch_ceiling = {"M": 300, "F": 500, "default": 500}

    def analyze(self, audio: np.ndarray, sex: str = "M") -> Dict[str, float]:
        """
        Analisa prosódia de um segmento de áudio.
        
        Args:
            audio: Array float32 normalizado [-1, 1]
            sex: "M" ou "F" para ajustar faixas de pitch
            
        Returns:
            Dicionário com métricas prosódicas
        """
        if audio is None or len(audio) < self.sample_rate * 0.5:  # Mínimo 500ms
            return self._empty_result()

        try:
            # Criar objeto Sound do Parselmouth
            snd = parselmouth.Sound(audio, sampling_frequency=self.sample_rate)

            floor = self.pitch_floor.get(sex.upper(), 75)
            ceiling = self.pitch_ceiling.get(sex.upper(), 500)

            # Extração de Pitch (F0)
            pitch = call(snd, "To Pitch", 0.0, floor, ceiling)
            f0_mean = call(pitch, "Get mean", 0, 0, "Hertz")
            f0_std = call(pitch, "Get standard deviation", 0, 0, "Hertz")
            f0_min = call(pitch, "Get minimum", 0, 0, "Hertz", "Parabolic")
            f0_max = call(pitch, "Get maximum", 0, 0, "Hertz", "Parabolic")

            # Point Process para Jitter/Shimmer
            point_process = call(snd, "To PointProcess (periodic, cc)", floor, ceiling)

            # Jitter (perturbação de frequência)
            jitter_local = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
            jitter_rap = call(point_process, "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3)

            # Shimmer (perturbação de amplitude)
            shimmer_local = call([snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
            shimmer_apq3 = call([snd, point_process], "Get shimmer (apq3)", 0, 0, 0.0001, 0.02, 1.3, 1.6)

            # HNR (Harmonics-to-Noise Ratio)
            harmonicity = call(snd, "To Harmonicity (cc)", 0.01, floor, 0.1, 1.0)
            hnr = call(harmonicity, "Get mean", 0, 0)

            # Tratar NaN
            def safe(val, default=0.0):
                return float(val) if val is not None and not np.isnan(val) else default

            return {
                "f0_mean": safe(f0_mean),
                "f0_std": safe(f0_std),
                "f0_min": safe(f0_min),
                "f0_max": safe(f0_max),
                "f0_range": safe(f0_max, 0) - safe(f0_min, 0),
                "jitter_local": safe(jitter_local),
                "jitter_rap": safe(jitter_rap),
                "shimmer_local": safe(shimmer_local),
                "shimmer_apq3": safe(shimmer_apq3),
                "hnr": safe(hnr),
            }

        except Exception as e:
            print(f"[ProsodyAnalyzer] Erro: {e}")
            return self._empty_result()

    def _empty_result(self) -> Dict[str, float]:
        return {
            "f0_mean": 0.0,
            "f0_std": 0.0,
            "f0_min": 0.0,
            "f0_max": 0.0,
            "f0_range": 0.0,
            "jitter_local": 0.0,
            "jitter_rap": 0.0,
            "shimmer_local": 0.0,
            "shimmer_apq3": 0.0,
            "hnr": 0.0,
        }
