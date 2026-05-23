"""
FROID Voice - Analisador de Sub-harmônicos (5-20 Hz)
Detecção de infrassom vocal do Sistema Nervoso Autônomo

Detecta modulação de amplitude na faixa 5-20 Hz que indica
tremor vocal involuntário (marcador de ansiedade, estresse, Parkinson).

Fonte: Plano 4B original
"""

import numpy as np
from scipy.signal import hilbert, butter, filtfilt
from typing import Dict
from src.config import SUBHARMONIC_RANGE, TREMOR_THRESHOLD, SAMPLE_RATE


class SubharmonicAnalyzer:
    """
    Detecta sub-harmônicos (5-20 Hz) via demodulação do envelope de amplitude.
    O tremor vocal involuntário opera nesta faixa e é indicador do SNA.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.low, self.high = SUBHARMONIC_RANGE

    def analyze(self, audio: np.ndarray) -> Dict:
        """
        Analisa sub-harmônicos via demodulação do envelope.
        
        Args:
            audio: Array float32, mínimo 2s
            
        Returns:
            Dicionário com energia sub-harmônica e detecção de tremor
        """
        if audio is None or len(audio) < self.sample_rate * 2:
            return self._empty_result()

        try:
            # 1. Extrair envelope via transformada de Hilbert
            analytic_signal = hilbert(audio)
            envelope = np.abs(analytic_signal)

            # 2. Filtrar envelope na faixa 5-20 Hz (sub-harmônicos)
            nyq = self.sample_rate / 2
            if self.high >= nyq:
                return self._empty_result()

            b, a = butter(4, [self.low / nyq, self.high / nyq], btype="band")
            filtered_envelope = filtfilt(b, a, envelope)

            # 3. Calcular energia na faixa sub-harmônica
            subharmonic_energy = float(np.sqrt(np.mean(filtered_envelope ** 2)))

            # 4. Energia total do envelope para normalização
            total_envelope_energy = float(np.sqrt(np.mean(envelope ** 2)))

            # 5. Razão normalizada
            if total_envelope_energy > 0.001:
                energy_ratio = subharmonic_energy / total_envelope_energy
            else:
                energy_ratio = 0.0

            # 6. Detecção de tremor (limiar configurável)
            tremor_detected = energy_ratio > TREMOR_THRESHOLD

            # 7. Frequência dominante do tremor (se detectado)
            tremor_freq = 0.0
            if tremor_detected:
                fft_env = np.abs(np.fft.rfft(filtered_envelope))
                freqs_env = np.fft.rfftfreq(len(filtered_envelope), d=1.0 / self.sample_rate)
                mask = (freqs_env >= self.low) & (freqs_env <= self.high)
                if mask.any():
                    peak_idx = np.argmax(fft_env[mask])
                    tremor_freq = float(freqs_env[mask][peak_idx])

            return {
                "subharmonic_energy": round(subharmonic_energy, 6),
                "energy_ratio": round(energy_ratio, 4),
                "tremor_detected": tremor_detected,
                "tremor_frequency_hz": round(tremor_freq, 2),
                "range_hz": f"{self.low}-{self.high}",
                "clinical_note": self._get_clinical_note(tremor_detected, tremor_freq),
            }

        except Exception as e:
            print(f"[SubharmonicAnalyzer] Erro: {e}")
            return self._empty_result()

    def _get_clinical_note(self, tremor: bool, freq: float) -> str:
        if not tremor:
            return "Sem tremor vocal detectado na faixa 5-20 Hz."
        if freq < 8:
            return f"Tremor vocal lento ({freq:.1f} Hz) - possível indicador de fadiga/depressão."
        elif freq < 12:
            return f"Tremor vocal ({freq:.1f} Hz) - possível indicador de ansiedade/estresse."
        else:
            return f"Tremor vocal rápido ({freq:.1f} Hz) - avaliar condição neurológica."

    def _empty_result(self) -> Dict:
        return {
            "subharmonic_energy": 0.0,
            "energy_ratio": 0.0,
            "tremor_detected": False,
            "tremor_frequency_hz": 0.0,
            "range_hz": f"{self.low}-{self.high}",
            "clinical_note": "Dados insuficientes para análise.",
        }
