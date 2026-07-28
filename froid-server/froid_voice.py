"""
Extração de biomarcadores vocais REAIS do FROID a partir de PCM.

Todos os marcadores dependentes da voz — vetor espectral de 12 bandas (que
alimenta as Zonas de Percepção), MFCC7/MFCC9, ZCR, loudness (RMS dBFS), jitter
e shimmer (proxies de perturbação), a energia basal 85-165 Hz e o espectro de
MODULAÇÃO do envelope (bandas neuroacústicas delta..gama e sub-harmônicos
5-40 Hz) — são calculados aqui por processamento de sinais determinístico.

Somente numpy. A F0 vem de froid_f0 (YIN). A face/AUs NÃO são tratadas aqui
(pipeline de visão, independente da voz).

Nota de resolução: as bandas de modulação lentas (delta 0.5-4 Hz) exigem uma
janela longa; por isso o motor calcula sobre um buffer rolante de vários
segundos (ver SessionState.ingest_pcm), não sobre um único quadro.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

import froid_f0

EPS = 1e-9

# 12 bandas log-espaçadas de C2 (~65 Hz) a B6 (~1976 Hz) — a escala cromática
# das 12 Zonas. Energia integrada em cada banda forma o "voice_spectral_12".
_ZONE_EDGES = np.geomspace(65.4, 1975.5, 13)

# Bandas de MODULAÇÃO do envelope (Hz). Analogia a voz, não EEG.
_MOD_BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 12.0),
    "beta": (12.0, 30.0),
    "gamma": (30.0, 80.0),
}
_SUBH_BANDS = {
    "sub_5_12": (5.0, 12.0),
    "sub_12_20": (12.0, 20.0),
    "sub_20_40": (20.0, 40.0),
}


def _rfft_power(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Espectro de potência de um sinal já janelado. Retorna (freqs_norm, power).

    freqs_norm em ciclos/amostra (multiplicar por sr para Hz)."""
    n = x.size
    if n < 2:
        return np.zeros(1), np.zeros(1)
    spec = np.fft.rfft(x)
    power = (spec.real ** 2 + spec.imag ** 2) / n
    freqs = np.fft.rfftfreq(n)
    return freqs, power


def _band_energy(freqs_hz: np.ndarray, power: np.ndarray, lo: float, hi: float) -> float:
    mask = (freqs_hz >= lo) & (freqs_hz < hi)
    return float(np.sum(power[mask])) if np.any(mask) else 0.0


def _analytic_envelope(x: np.ndarray) -> np.ndarray:
    """Envelope de amplitude via sinal analítico (transformada de Hilbert por FFT)."""
    n = x.size
    if n < 2:
        return np.abs(x)
    xf = np.fft.fft(x)
    h = np.zeros(n)
    if n % 2 == 0:
        h[0] = 1.0
        h[n // 2] = 1.0
        h[1 : n // 2] = 2.0
    else:
        h[0] = 1.0
        h[1 : (n + 1) // 2] = 2.0
    analytic = np.fft.ifft(xf * h)
    return np.abs(analytic)


def _hz_to_mel(f: np.ndarray | float) -> np.ndarray | float:
    return 2595.0 * np.log10(1.0 + np.asarray(f, dtype=np.float64) / 700.0)


def _mel_to_hz(m: np.ndarray) -> np.ndarray:
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def _mel_filterbank(n_filters: int, n_fft: int, sr: float) -> np.ndarray:
    fmax = sr / 2.0
    mel_points = np.linspace(_hz_to_mel(0.0), _hz_to_mel(fmax), n_filters + 2)
    hz_points = _mel_to_hz(mel_points)
    bins = np.floor((n_fft + 1) * hz_points / sr).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)
    fb = np.zeros((n_filters, n_fft // 2 + 1))
    for m in range(1, n_filters + 1):
        left, center, right = bins[m - 1], bins[m], bins[m + 1]
        if center > left:
            fb[m - 1, left:center] = (np.arange(left, center) - left) / (center - left)
        if right > center:
            fb[m - 1, center:right] = (right - np.arange(center, right)) / (right - center)
    return fb


def _dct2(x: np.ndarray, n_out: int) -> np.ndarray:
    n = x.size
    k = np.arange(n)
    out = np.zeros(n_out)
    for i in range(n_out):
        out[i] = np.sum(x * np.cos(np.pi * i * (2 * k + 1) / (2 * n)))
    return out


def _mfcc_mean(signal: np.ndarray, sr: float, n_mfcc: int = 13, n_filters: int = 26) -> np.ndarray:
    """MFCC médio da janela (framing 25ms/10ms, pré-ênfase, Mel, log, DCT-II)."""
    if signal.size < int(0.025 * sr):
        return np.zeros(n_mfcc)
    emphasized = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])
    frame_len = max(8, int(round(0.025 * sr)))
    hop = max(1, int(round(0.010 * sr)))
    n_fft = 1
    while n_fft < frame_len:
        n_fft *= 2
    fb = _mel_filterbank(n_filters, n_fft, sr)
    window = np.hamming(frame_len)
    coeffs = []
    for start in range(0, emphasized.size - frame_len + 1, hop):
        frame = emphasized[start : start + frame_len] * window
        spec = np.fft.rfft(frame, n=n_fft)
        power = (spec.real ** 2 + spec.imag ** 2) / n_fft
        mel_energy = np.dot(fb, power)
        log_mel = np.log(mel_energy + EPS)
        coeffs.append(_dct2(log_mel, n_mfcc))
    if not coeffs:
        return np.zeros(n_mfcc)
    return np.mean(np.asarray(coeffs), axis=0)


def extract_voice_features(signal: np.ndarray, sample_rate: float) -> Dict[str, float]:
    """Calcula todos os biomarcadores vocais reais de uma janela PCM mono."""
    x = np.asarray(signal, dtype=np.float64)
    n = x.size
    features: Dict[str, float] = {}
    if n < 8 or sample_rate <= 0:
        return features
    x = x - float(np.mean(x))
    if not np.any(x):
        return features

    # F0, jitter e shimmer (por quadro).
    f0_mean, f0_std, voiced_ratio = froid_f0.estimate_f0_series(x, sample_rate)
    features["f0_mean"] = f0_mean
    features["f0_var"] = f0_std
    features["f0_voiced_ratio"] = voiced_ratio

    # ZCR — taxa de cruzamento por zero (real).
    signs = np.sign(x)
    signs[signs == 0] = 1
    zcr = float(np.count_nonzero(np.diff(signs)) / (2.0 * n))
    features["zcr"] = round(zcr, 5)

    # Loudness — RMS em dBFS (0 dB = fundo de escala).
    rms = float(np.sqrt(np.mean(x ** 2)))
    features["loudness_dbfs"] = round(float(20.0 * np.log10(rms + EPS)), 2)
    features["rms"] = round(rms, 6)

    # Espectro de áudio (janela de Hamming) -> vetor de 12 bandas e energia basal.
    windowed = x * np.hamming(n)
    freqs_norm, power = _rfft_power(windowed)
    freqs_hz = freqs_norm * sample_rate
    zone_energy = np.array(
        [_band_energy(freqs_hz, power, _ZONE_EDGES[i], _ZONE_EDGES[i + 1]) for i in range(12)]
    )
    # Escala robusta para a faixa de trabalho do colorímetro (0.5-25 arbitrária),
    # preservando as proporções entre bandas (o desvio relativo é invariante).
    peak = float(np.max(zone_energy)) if np.max(zone_energy) > 0 else 1.0
    voice_spectral_12 = np.clip(0.5 + (zone_energy / peak) * 24.5, 0.5, 25.0)
    features["voice_spectral_12"] = [round(float(v), 4) for v in voice_spectral_12]
    features["energy_85_165"] = round(_band_energy(freqs_hz, power, 85.0, 165.0), 6)

    # Espectro de MODULAÇÃO do envelope -> bandas neuroacústicas e sub-harmônicos.
    envelope = _analytic_envelope(x)
    envelope = envelope - float(np.mean(envelope))
    env_windowed = envelope * np.hamming(n)
    env_freqs_norm, env_power = _rfft_power(env_windowed)
    env_freqs_hz = env_freqs_norm * sample_rate
    total_mod = float(np.sum(env_power)) + EPS
    for name, (lo, hi) in _MOD_BANDS.items():
        features[f"mod_{name}"] = round(_band_energy(env_freqs_hz, env_power, lo, hi) / total_mod, 5)
    for name, (lo, hi) in _SUBH_BANDS.items():
        features[name] = round(_band_energy(env_freqs_hz, env_power, lo, hi) / total_mod, 5)

    # MFCC reais (coeficientes 7 e 9, 1-indexados).
    mfcc = _mfcc_mean(x, sample_rate)
    features["mfcc7"] = round(float(mfcc[7]) if mfcc.size > 7 else 0.0, 4)
    features["mfcc9"] = round(float(mfcc[9]) if mfcc.size > 9 else 0.0, 4)

    # Jitter e shimmer (perturbação ciclo-a-ciclo de período e amplitude).
    jitter, shimmer = jitter_shimmer(x, sample_rate)
    features["jitter"] = jitter
    features["shimmer"] = shimmer

    return features


def voiced_frame_series(signal: np.ndarray, sample_rate: float, frame_ms: float = 40.0, hop_ms: float = 20.0):
    """Séries por quadro de F0 (período) e amplitude RMS, para jitter/shimmer."""
    x = np.asarray(signal, dtype=np.float64)
    frame_len = max(4, int(round(sample_rate * frame_ms / 1000.0)))
    hop = max(1, int(round(sample_rate * hop_ms / 1000.0)))
    periods = []
    amplitudes = []
    for start in range(0, x.size - frame_len + 1, hop):
        frame = x[start : start + frame_len]
        f0 = froid_f0.estimate_f0_frame(frame, sample_rate)
        if f0 > 0.0:
            periods.append(1.0 / f0)
            amplitudes.append(float(np.sqrt(np.mean(frame ** 2))))
    return np.asarray(periods), np.asarray(amplitudes)


def jitter_shimmer(signal: np.ndarray, sample_rate: float) -> tuple[float, float]:
    """Jitter (perturbação relativa do período) e shimmer (da amplitude), locais.

    Proxies normalizados [0,~], consistentes com o rótulo interno do FROID —
    porém agora derivados da voz REAL, não de ruído simulado.
    """
    periods, amplitudes = voiced_frame_series(signal, sample_rate)
    jitter = 0.0
    shimmer = 0.0
    if periods.size >= 2:
        jitter = float(np.mean(np.abs(np.diff(periods))) / (np.mean(periods) + EPS))
    if amplitudes.size >= 2:
        shimmer = float(np.mean(np.abs(np.diff(amplitudes))) / (np.mean(amplitudes) + EPS))
    return round(jitter, 5), round(shimmer, 5)
