"""Prova de correção dos biomarcadores vocais reais (froid_voice) com sinais
sintéticos cujas propriedades conhecemos."""
import math
import unittest

import numpy as np

import froid_f0
import froid_voice


SR = 16000


def sine(freq, sec=1.0, amp=1.0):
    t = np.arange(int(SR * sec)) / SR
    return amp * np.sin(2 * math.pi * freq * t)


def glottal(f0, sec=1.0):
    """Pulso glotal sintético (soma harmônica) — mais próximo da voz real."""
    t = np.arange(int(SR * sec)) / SR
    sig = sum((1.0 / k) * np.sin(2 * math.pi * f0 * k * t) for k in range(1, 13))
    return sig / np.max(np.abs(sig))


def am_signal(carrier, mod_hz, sec=2.0, depth=0.6):
    t = np.arange(int(SR * sec)) / SR
    return (1.0 + depth * np.sin(2 * math.pi * mod_hz * t)) * np.sin(2 * math.pi * carrier * t)


class VoiceFeatureTests(unittest.TestCase):
    def test_zcr_of_pure_tone(self):
        # ZCR de um seno puro ~ f/fs.
        for f in (150.0, 300.0, 500.0):
            feats = froid_voice.extract_voice_features(sine(f, 0.5), SR)
            self.assertAlmostEqual(feats["zcr"], f / SR, delta=0.001)

    def test_loudness_tracks_amplitude(self):
        loud = froid_voice.extract_voice_features(sine(200, 0.5, amp=0.8), SR)["loudness_dbfs"]
        soft = froid_voice.extract_voice_features(sine(200, 0.5, amp=0.1), SR)["loudness_dbfs"]
        self.assertGreater(loud, soft)
        # amp 0.5 -> rms 0.3536 -> ~ -9 dBFS
        mid = froid_voice.extract_voice_features(sine(200, 0.5, amp=0.5), SR)["loudness_dbfs"]
        self.assertAlmostEqual(mid, -9.0, delta=1.0)

    def test_spectral_12_concentrates_at_tone_band(self):
        feats = froid_voice.extract_voice_features(sine(500.0, 1.0), SR)
        vec = feats["voice_spectral_12"]
        self.assertEqual(len(vec), 12)
        dominant = int(np.argmax(vec))
        lo, hi = froid_voice._ZONE_EDGES[dominant], froid_voice._ZONE_EDGES[dominant + 1]
        self.assertTrue(lo <= 500.0 <= hi, f"500 Hz deveria cair na banda dominante [{lo:.0f},{hi:.0f}]")

    def test_envelope_modulation_detects_tremor(self):
        # Portadora 200 Hz modulada em amplitude a 6 Hz -> energia de modulacao
        # na faixa sub 5-12 Hz e theta 4-8; quase nada em gamma 30-80.
        feats = froid_voice.extract_voice_features(am_signal(200.0, 6.0, sec=2.0), SR)
        self.assertGreater(feats["sub_5_12"], 0.05)
        self.assertGreater(feats["mod_theta"], feats["mod_gamma"])
        # Um tom NAO modulado tem modulacao desprezivel.
        flat = froid_voice.extract_voice_features(sine(200.0, 2.0), SR)
        self.assertLess(flat["sub_5_12"], feats["sub_5_12"])

    def test_mfcc_is_finite_and_discriminative(self):
        low = froid_voice.extract_voice_features(sine(120.0, 0.5), SR)
        high = froid_voice.extract_voice_features(sine(900.0, 0.5), SR)
        for feats in (low, high):
            self.assertTrue(math.isfinite(feats["mfcc7"]))
            self.assertTrue(math.isfinite(feats["mfcc9"]))
        # Espectros diferentes -> MFCC diferentes.
        self.assertNotAlmostEqual(low["mfcc7"], high["mfcc7"], places=3)

    def test_jitter_shimmer_low_for_stationary_tone(self):
        j, s = froid_voice.jitter_shimmer(sine(150.0, 1.0), SR)
        self.assertLess(j, 0.02)
        self.assertLess(s, 0.05)

    def test_jitter_higher_with_pitch_modulation(self):
        # Vibrato: F0 oscilando -> jitter (perturbacao de periodo) maior.
        t = np.arange(int(SR * 1.0)) / SR
        vibrato = np.sin(2 * math.pi * (150.0 + 8.0 * np.sin(2 * math.pi * 5.0 * t)) * t)
        j_vib, _ = froid_voice.jitter_shimmer(vibrato, SR)
        j_flat, _ = froid_voice.jitter_shimmer(sine(150.0, 1.0), SR)
        self.assertGreater(j_vib, j_flat)


class VectorizationEquivalenceTests(unittest.TestCase):
    """As otimizações de desempenho (matriz DCT em cache + framing vetorizado,
    e YIN por autocorrelação via FFT) devem ser NUMERICAMENTE equivalentes às
    formulações diretas — desempenho jamais pode custar acurácia clínica."""

    def test_mfcc_matches_reference_loop(self):
        signal = glottal(150.0, 1.0)
        emphasized = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])
        frame_len, hop, n_filters, n_mfcc = 400, 160, 26, 13
        n_fft = 512
        fb = froid_voice._mel_filterbank(n_filters, n_fft, SR)
        window = np.hamming(frame_len)
        coeffs = []
        for start in range(0, emphasized.size - frame_len + 1, hop):
            frame = emphasized[start : start + frame_len] * window
            spec = np.fft.rfft(frame, n=n_fft)
            power = (spec.real ** 2 + spec.imag ** 2) / n_fft
            log_mel = np.log(fb @ power + froid_voice.EPS)
            k = np.arange(n_filters)
            coeffs.append(
                [np.sum(log_mel * np.cos(np.pi * i * (2 * k + 1) / (2 * n_filters)))
                 for i in range(n_mfcc)]
            )
        reference = np.mean(np.asarray(coeffs), axis=0)
        np.testing.assert_allclose(
            froid_voice._mfcc_mean(signal, SR), reference, atol=1e-9
        )

    def test_yin_difference_matches_direct_formula(self):
        rng = np.random.default_rng(11)
        for _ in range(4):
            n = int(rng.integers(400, 1000))
            t = np.arange(n) / SR
            x = np.sin(2 * math.pi * rng.uniform(80, 300) * t)
            x = x - x.mean()
            tau_max = min(n - 1, 266)
            direct = np.zeros(tau_max + 1)
            for tau in range(1, tau_max + 1):
                diff = x[: n - tau] - x[tau:]
                direct[tau] = float(np.dot(diff, diff))
            fast = froid_f0._difference_function(x, tau_max)
            scale = max(1e-12, float(np.max(np.abs(direct))))
            self.assertLess(float(np.max(np.abs(direct - fast))) / scale, 1e-9)

    def test_single_pass_f0_matches_series_summary(self):
        # frame_f0_series (passagem única) deve reproduzir o resumo de
        # estimate_f0_series, que agora a consome.
        signal = glottal(180.0, 1.0)
        f0_mean, f0_std, voiced_ratio = froid_f0.estimate_f0_series(signal, SR)
        frames, _ = froid_f0.frame_f0_series(signal, SR)
        voiced = frames[frames > 0.0]
        self.assertAlmostEqual(f0_mean, round(float(np.median(voiced)), 2), places=2)
        self.assertAlmostEqual(
            voiced_ratio, round(float(voiced.size / frames.size), 3), places=3
        )


if __name__ == "__main__":
    unittest.main()
