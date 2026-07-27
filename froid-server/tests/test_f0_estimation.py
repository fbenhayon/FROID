"""Prova de correção do estimador de F0 (froid_f0) com sinais sintéticos de
frequência conhecida. Se o estimador devolve a frequência que sabemos ter
gerado, a matemática está correta."""
import io
import math
import struct
import unittest
import wave

import numpy as np

from froid_f0 import (
    estimate_f0_frame,
    estimate_f0_series,
    read_wav_mono,
)


def sine(freq: float, sr: int, seconds: float) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return np.sin(2 * math.pi * freq * t)


def glottal_like(f0: float, sr: int, seconds: float, harmonics: int = 12) -> np.ndarray:
    """Soma de harmônicos com decaimento 1/k — aproxima a riqueza espectral de
    uma vogal vozeada e testa a robustez a erro de oitava."""
    t = np.arange(int(sr * seconds)) / sr
    signal = np.zeros_like(t)
    for k in range(1, harmonics + 1):
        signal += (1.0 / k) * np.sin(2 * math.pi * f0 * k * t)
    return signal / np.max(np.abs(signal))


class F0EstimationTests(unittest.TestCase):
    SR = 16000

    def test_pure_sines_are_recovered_within_1pct(self):
        for freq in (100.0, 130.0, 150.0, 220.0, 330.0):
            frame = sine(freq, self.SR, 0.05)  # 50 ms
            est = estimate_f0_frame(frame, self.SR)
            self.assertGreater(est, 0.0, f"quadro deveria ser vozeado em {freq} Hz")
            self.assertLess(
                abs(est - freq) / freq,
                0.01,
                f"F0 estimado {est:.2f} distante de {freq} Hz (>1%)",
            )

    def test_harmonic_voice_avoids_octave_error(self):
        # Sinal rico em harmônicos a 120 Hz: autocorrelação ingênua erraria a
        # oitava (240/60 Hz); o YIN deve acertar o fundamental.
        for f0 in (110.0, 120.0, 200.0):
            frame = glottal_like(f0, self.SR, 0.06)
            est = estimate_f0_frame(frame, self.SR)
            self.assertLess(
                abs(est - f0) / f0,
                0.02,
                f"F0 harmônico {est:.2f} distante de {f0} Hz (>2%)",
            )

    def test_silence_and_noise_are_unvoiced(self):
        self.assertEqual(estimate_f0_frame(np.zeros(800), self.SR), 0.0)
        rng = np.random.default_rng(7)
        noise = rng.normal(0, 1, 800)
        # Ruído branco não tem periodicidade -> quase sempre 0. Toleramos que,
        # se retornar algo, esteja dentro da faixa (não deve travar/estourar).
        est = estimate_f0_frame(noise, self.SR)
        self.assertTrue(est == 0.0 or 60.0 <= est <= 400.0)

    def test_series_median_matches_true_f0(self):
        signal = glottal_like(147.0, self.SR, 1.0)  # ~1 s de voz sintética
        f0_mean, f0_std, voiced_ratio = estimate_f0_series(signal, self.SR)
        self.assertLess(abs(f0_mean - 147.0) / 147.0, 0.02)
        self.assertGreater(voiced_ratio, 0.9)
        self.assertLess(f0_std, 5.0)  # sinal estacionário -> baixa dispersão

    def test_sample_rate_invariance(self):
        # A mesma frequência em taxas diferentes deve dar o mesmo F0.
        for sr in (8000, 16000, 44100, 48000):
            est = estimate_f0_frame(sine(180.0, sr, 0.05), sr)
            self.assertLess(abs(est - 180.0) / 180.0, 0.01, f"sr={sr}")

    def test_wav_pcm_roundtrip(self):
        # Prova o caminho real: WAV PCM -> decodificação stdlib -> F0.
        freq = 165.0
        samples = (sine(freq, self.SR, 0.5) * 30000).astype("<i2")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.SR)
            wav.writeframes(samples.tobytes())
        signal, sr = read_wav_mono(buffer.getvalue())
        self.assertEqual(sr, self.SR)
        f0_mean, _, _ = estimate_f0_series(signal, sr)
        self.assertLess(abs(f0_mean - freq) / freq, 0.01)


if __name__ == "__main__":
    unittest.main()
