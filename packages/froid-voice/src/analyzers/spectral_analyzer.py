"""
FROID Voice - Analisador Espectral (7 Bandas)
Correlatos neurológicos por faixa de frequência

Bandas:
1: 85-150 Hz   → Tronco cerebral, regulação autonômica
2: 150-250 Hz  → Sistema límbico, emoções primárias
3: 250-400 Hz  → Córtex pré-frontal, regulação emocional
4: 400-600 Hz  → Equilíbrio, serenidade
5: 600-900 Hz  → Expressão emocional, vulnerabilidade
6: 900-1200 Hz → Introspecção, tristeza
7: 1200-2000 Hz → Criatividade, insight

Fonte: Plano 4B original
"""

import numpy as np
from scipy.signal import welch
from typing import Dict, List
from src.config import SPECTRAL_BANDS, SAMPLE_RATE


class SpectralAnalyzer:
    """
    Calcula energia por banda espectral usando FFT com janela de Hamming.
    Retorna energia normalizada e banda dominante.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate

    def analyze(self, audio: np.ndarray) -> Dict:
        """
        Analisa distribuição espectral do áudio em 7 bandas.
        
        Args:
            audio: Array float32 normalizado [-1, 1], mínimo 1s
            
        Returns:
            Dicionário com energia por banda e banda dominante
        """
        if audio is None or len(audio) < self.sample_rate:
            return self._empty_result()

        try:
            # PSD via método de Welch (janela Hamming)
            freqs, psd = welch(
                audio,
                fs=self.sample_rate,
                window="hamming",
                nperseg=min(4096, len(audio)),
                noverlap=None,
                scaling="density",
            )

            # Calcular energia por banda
            bands = []
            total_energy = 0.0

            for band_info in SPECTRAL_BANDS:
                low, high = band_info["range"]
                mask = (freqs >= low) & (freqs < high)
                energy = float(np.trapz(psd[mask], freqs[mask])) if mask.any() else 0.0
                total_energy += energy

                bands.append({
                    "band": band_info["band"],
                    "range_hz": f"{low}-{high}",
                    "correlate": band_info["correlate"],
                    "energy_raw": energy,
                })

            # Normalizar energias (0-1)
            if total_energy > 0:
                for b in bands:
                    b["energy_normalized"] = round(b["energy_raw"] / total_energy, 4)
            else:
                for b in bands:
                    b["energy_normalized"] = 0.0

            # Banda dominante
            dominant_idx = max(range(len(bands)), key=lambda i: bands[i]["energy_raw"])

            return {
                "bands": bands,
                "dominant_band": bands[dominant_idx]["band"],
                "dominant_correlate": bands[dominant_idx]["correlate"],
                "total_energy": total_energy,
            }

        except Exception as e:
            print(f"[SpectralAnalyzer] Erro: {e}")
            return self._empty_result()

    def _empty_result(self) -> Dict:
        return {
            "bands": [
                {"band": b["band"], "range_hz": f"{b['range'][0]}-{b['range'][1]}",
                 "correlate": b["correlate"], "energy_raw": 0.0, "energy_normalized": 0.0}
                for b in SPECTRAL_BANDS
            ],
            "dominant_band": 0,
            "dominant_correlate": "",
            "total_energy": 0.0,
        }
