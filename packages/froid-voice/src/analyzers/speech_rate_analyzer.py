"""
FROID Voice - Analisador de Taxa de Fala
Detecção de sílabas via librosa onset detection

Aceleração → ansiedade / Desaceleração → depressão
Fonte: Plano 4B + Schewski et al. (2025)
"""

import numpy as np
import librosa
from typing import Dict
from src.config import SAMPLE_RATE


class SpeechRateAnalyzer:
    """
    Analisa taxa de fala, pausas e ritmo usando librosa.
    - Sílabas por segundo (onset detection)
    - Duração e frequência dos silêncios
    - Razão fala/silêncio
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate

    def analyze(self, audio: np.ndarray) -> Dict:
        """
        Analisa taxa de fala do segmento de áudio.
        
        Args:
            audio: Array float32, mínimo 2s
            
        Returns:
            Dicionário com métricas de taxa de fala
        """
        if audio is None or len(audio) < self.sample_rate * 2:
            return self._empty_result()

        try:
            duration_sec = len(audio) / self.sample_rate

            # 1. Detecção de onsets (aproximação de sílabas)
            onset_frames = librosa.onset.onset_detect(
                y=audio,
                sr=self.sample_rate,
                units="frames",
                hop_length=512,
                backtrack=True,
            )
            onset_times = librosa.frames_to_time(onset_frames, sr=self.sample_rate, hop_length=512)

            n_syllables = len(onset_times)
            syllables_per_sec = n_syllables / duration_sec if duration_sec > 0 else 0.0

            # 2. Análise de pausas (segmentos de silêncio)
            rms = librosa.feature.rms(y=audio, hop_length=512)[0]
            silence_threshold = np.mean(rms) * 0.3  # 30% da energia média
            is_silence = rms < silence_threshold

            # Contar segmentos de silêncio
            silence_segments = []
            in_silence = False
            start_idx = 0
            hop_duration = 512 / self.sample_rate

            for i, silent in enumerate(is_silence):
                if silent and not in_silence:
                    start_idx = i
                    in_silence = True
                elif not silent and in_silence:
                    duration_ms = (i - start_idx) * hop_duration * 1000
                    if duration_ms > 100:  # Pausas > 100ms
                        silence_segments.append(duration_ms)
                    in_silence = False

            # 3. Métricas de pausa
            total_silence_ms = sum(silence_segments)
            total_duration_ms = duration_sec * 1000
            silence_ratio = total_silence_ms / total_duration_ms if total_duration_ms > 0 else 0.0
            avg_pause_ms = np.mean(silence_segments) if silence_segments else 0.0
            n_pauses = len(silence_segments)

            # 4. Classificação clínica
            clinical_pattern = self._classify_pattern(syllables_per_sec, silence_ratio)

            return {
                "syllables_per_sec": round(syllables_per_sec, 2),
                "n_syllables": n_syllables,
                "duration_sec": round(duration_sec, 2),
                "silence_ratio": round(silence_ratio, 3),
                "n_pauses": n_pauses,
                "avg_pause_ms": round(avg_pause_ms, 1),
                "total_silence_ms": round(total_silence_ms, 1),
                "clinical_pattern": clinical_pattern,
            }

        except Exception as e:
            print(f"[SpeechRateAnalyzer] Erro: {e}")
            return self._empty_result()

    def _classify_pattern(self, sps: float, silence_ratio: float) -> str:
        """Classifica padrão de fala para indicação clínica."""
        if sps < 2.0 and silence_ratio > 0.4:
            return "lentificado_com_pausas"  # Sugestivo de depressão
        elif sps < 3.0:
            return "lentificado"  # Possível fadiga ou depressão leve
        elif sps > 6.0:
            return "acelerado"  # Possível ansiedade ou mania
        elif sps > 8.0:
            return "taquilalia"  # Forte indicador de mania
        else:
            return "normal"  # 3-6 sílabas/s é faixa normal

    def _empty_result(self) -> Dict:
        return {
            "syllables_per_sec": 0.0,
            "n_syllables": 0,
            "duration_sec": 0.0,
            "silence_ratio": 0.0,
            "n_pauses": 0,
            "avg_pause_ms": 0.0,
            "total_silence_ms": 0.0,
            "clinical_pattern": "indeterminado",
        }
