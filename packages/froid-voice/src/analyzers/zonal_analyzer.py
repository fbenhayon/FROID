"""
FROID Voice - Analisador Zonal (12 Zonas FROID)
Mapeamento proprietário: notas musicais → dicotomias psíquicas

Cada zona corresponde a uma nota musical (C→B) com frequência fundamental
e harmônicos (2x, 3x, 4x). A energia em cada zona indica ativação de
um eixo psíquico específico (positivo ↔ negativo).

PROPRIETÁRIO FROID - Frequency Recognition of Internal Dynamics
"""

import numpy as np
from scipy.signal import welch
from typing import Dict, List
from src.config import FROID_ZONES, ZONE_TOLERANCE_RATIO, HARMONICS, SAMPLE_RATE


class ZonalAnalyzer:
    """
    Analisa energia vocal nas 12 Zonas FROID.
    Cada zona é uma nota musical com tolerância de ±1.5% da frequência central.
    Inclui análise de harmônicos (2x, 3x, 4x).
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate

    def analyze(self, audio: np.ndarray) -> Dict:
        """
        Analisa energia nas 12 Zonas FROID.
        
        Args:
            audio: Array float32, mínimo 2s para resolução espectral adequada
            
        Returns:
            Dicionário com energia por zona, zona dominante e dados de harmônicos
        """
        if audio is None or len(audio) < self.sample_rate * 2:
            return self._empty_result()

        try:
            # FFT com alta resolução (~1 Hz)
            n_fft = max(8192, len(audio))
            freqs = np.fft.rfftfreq(n_fft, d=1.0 / self.sample_rate)
            spectrum = np.abs(np.fft.rfft(audio * np.hamming(len(audio)), n=n_fft))
            psd = spectrum ** 2

            zones = []
            total_energy = 0.0

            for zone_info in FROID_ZONES:
                freq = zone_info["freq"]
                tolerance = freq * ZONE_TOLERANCE_RATIO

                # Energia na frequência fundamental
                fundamental_energy = self._band_energy(freqs, psd, freq, tolerance)

                # Energia nos harmônicos
                harmonic_energy = 0.0
                harmonic_details = []
                for h in HARMONICS:
                    h_freq = freq * h
                    if h_freq < self.sample_rate / 2:  # Nyquist
                        h_energy = self._band_energy(freqs, psd, h_freq, h_freq * ZONE_TOLERANCE_RATIO)
                        harmonic_energy += h_energy
                        harmonic_details.append({"harmonic": h, "freq": h_freq, "energy": h_energy})

                # Energia total da zona (fundamental + harmônicos ponderados)
                zone_energy = fundamental_energy + harmonic_energy * 0.5
                total_energy += zone_energy

                zones.append({
                    "zone": zone_info["zone"],
                    "note": zone_info["note"],
                    "freq_hz": zone_info["freq"],
                    "positive": zone_info["positive"],
                    "negative": zone_info["negative"],
                    "fundamental_energy": fundamental_energy,
                    "harmonic_energy": harmonic_energy,
                    "total_energy": zone_energy,
                    "harmonics": harmonic_details,
                })

            # Normalizar energias (0-1)
            if total_energy > 0:
                for z in zones:
                    z["energy_normalized"] = round(z["total_energy"] / total_energy, 4)
            else:
                for z in zones:
                    z["energy_normalized"] = 0.0

            # Zona dominante
            dominant_idx = max(range(len(zones)), key=lambda i: zones[i]["total_energy"])

            return {
                "zones": zones,
                "dominant_zone": zones[dominant_idx]["zone"],
                "dominant_note": zones[dominant_idx]["note"],
                "dominant_dichotomy": {
                    "positive": zones[dominant_idx]["positive"],
                    "negative": zones[dominant_idx]["negative"],
                },
                "total_energy": total_energy,
            }

        except Exception as e:
            print(f"[ZonalAnalyzer] Erro: {e}")
            return self._empty_result()

    def _band_energy(self, freqs: np.ndarray, psd: np.ndarray, center: float, tolerance: float) -> float:
        """Calcula energia em uma banda estreita centrada em 'center' ± tolerance."""
        mask = (freqs >= center - tolerance) & (freqs <= center + tolerance)
        if not mask.any():
            return 0.0
        return float(np.sum(psd[mask]))

    def _empty_result(self) -> Dict:
        return {
            "zones": [
                {
                    "zone": z["zone"], "note": z["note"], "freq_hz": z["freq"],
                    "positive": z["positive"], "negative": z["negative"],
                    "fundamental_energy": 0.0, "harmonic_energy": 0.0,
                    "total_energy": 0.0, "energy_normalized": 0.0, "harmonics": [],
                }
                for z in FROID_ZONES
            ],
            "dominant_zone": 0,
            "dominant_note": "",
            "dominant_dichotomy": {"positive": "", "negative": ""},
            "total_energy": 0.0,
        }
