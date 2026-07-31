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


def _dct2_matrix(n_in: int, n_out: int) -> np.ndarray:
    """Matriz da DCT-II (n_out x n_in). Depende só das dimensões, então é
    calculada uma vez e reaproveitada (ver _DCT_CACHE)."""
    k = np.arange(n_in)
    i = np.arange(n_out).reshape(-1, 1)
    return np.cos(np.pi * i * (2 * k + 1) / (2 * n_in))


# Caches de matrizes que dependem apenas dos parâmetros (não do sinal). Sem
# eles, a matriz DCT era reconstruída a cada quadro — ~100 mil cossenos
# redundantes por segundo de áudio, por paciente.
_DCT_CACHE: Dict[tuple, np.ndarray] = {}
_MEL_CACHE: Dict[tuple, np.ndarray] = {}


def _dct2(x: np.ndarray, n_out: int) -> np.ndarray:
    """DCT-II de um vetor (mantida para compatibilidade e testes)."""
    key = (int(x.size), int(n_out))
    matrix = _DCT_CACHE.get(key)
    if matrix is None:
        matrix = _dct2_matrix(int(x.size), int(n_out))
        _DCT_CACHE[key] = matrix
    return matrix @ x


def _mfcc_mean(signal: np.ndarray, sr: float, n_mfcc: int = 13, n_filters: int = 26) -> np.ndarray:
    """MFCC médio da janela (framing 25ms/10ms, pré-ênfase, Mel, log, DCT-II).

    Totalmente vetorizado: o framing usa stride tricks e a FFT/DCT rodam em
    lote sobre todos os quadros. Matematicamente idêntico ao laço quadro a
    quadro anterior, porém muito mais rápido — relevante porque roda a cada
    ~1s por paciente e antes bloqueava tempo de CPU proporcional à janela.
    """
    if signal.size < int(0.025 * sr):
        return np.zeros(n_mfcc)
    emphasized = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])
    frame_len = max(8, int(round(0.025 * sr)))
    hop = max(1, int(round(0.010 * sr)))
    n_frames = 1 + (emphasized.size - frame_len) // hop
    if n_frames < 1:
        return np.zeros(n_mfcc)
    n_fft = 1
    while n_fft < frame_len:
        n_fft *= 2

    mel_key = (int(n_filters), int(n_fft), float(sr))
    fb = _MEL_CACHE.get(mel_key)
    if fb is None:
        fb = _mel_filterbank(n_filters, n_fft, sr)
        _MEL_CACHE[mel_key] = fb

    # Framing sem cópia (visão com stride) + janela de Hamming.
    frames = np.lib.stride_tricks.as_strided(
        emphasized,
        shape=(n_frames, frame_len),
        strides=(emphasized.strides[0] * hop, emphasized.strides[0]),
        writeable=False,
    ) * np.hamming(frame_len)

    spec = np.fft.rfft(frames, n=n_fft, axis=1)
    power = (spec.real ** 2 + spec.imag ** 2) / n_fft
    log_mel = np.log(power @ fb.T + EPS)

    dct_key = (int(n_filters), int(n_mfcc))
    dct_matrix = _DCT_CACHE.get(dct_key)
    if dct_matrix is None:
        dct_matrix = _dct2_matrix(int(n_filters), int(n_mfcc))
        _DCT_CACHE[dct_key] = dct_matrix
    return np.mean(log_mel @ dct_matrix.T, axis=0)


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

    # Passagem ÚNICA de F0 por quadro — alimenta tanto o resumo de F0 quanto
    # o jitter/shimmer (que antes refaziam a mesma estimativa por quadro).
    f0_frames, rms_frames = froid_f0.frame_f0_series(x, sample_rate)
    voiced_mask = f0_frames > 0.0
    voiced_f0 = f0_frames[voiced_mask]
    if voiced_f0.size:
        features["f0_mean"] = round(float(np.median(voiced_f0)), 2)
        features["f0_var"] = round(float(np.std(voiced_f0)) if voiced_f0.size > 1 else 0.0, 2)
        features["f0_voiced_ratio"] = round(float(voiced_f0.size / f0_frames.size), 3)
    else:
        features["f0_mean"] = 0.0
        features["f0_var"] = 0.0
        features["f0_voiced_ratio"] = 0.0

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

    # Jitter e shimmer, calculados sobre os MESMOS quadros já estimados acima
    # (sem refazer a passagem de F0, que é o trecho mais caro da análise).
    periods = 1.0 / voiced_f0 if voiced_f0.size else np.zeros(0)
    amplitudes = rms_frames[voiced_mask] if voiced_f0.size else np.zeros(0)
    jitter, shimmer = _perturbation(periods, amplitudes)
    features["jitter"] = jitter
    features["shimmer"] = shimmer

    return features


def _perturbation(periods: np.ndarray, amplitudes: np.ndarray) -> tuple[float, float]:
    """Jitter (perturbação relativa do período) e shimmer (da amplitude)."""
    jitter = 0.0
    shimmer = 0.0
    if periods.size >= 2:
        jitter = float(np.mean(np.abs(np.diff(periods))) / (np.mean(periods) + EPS))
    if amplitudes.size >= 2:
        shimmer = float(np.mean(np.abs(np.diff(amplitudes))) / (np.mean(amplitudes) + EPS))
    return round(jitter, 5), round(shimmer, 5)


def voiced_frame_series(signal: np.ndarray, sample_rate: float, frame_ms: float = 40.0, hop_ms: float = 20.0):
    """Séries por quadro de F0 (período) e amplitude RMS, para jitter/shimmer.

    Reaproveita a passagem única de froid_f0.frame_f0_series — antes esta
    função reestimava a F0 sobre exatamente os mesmos quadros já percorridos
    por estimate_f0_series, duplicando o trabalho mais caro da análise.
    """
    f0_values, rms_values = froid_f0.frame_f0_series(
        signal, sample_rate, frame_ms=frame_ms, hop_ms=hop_ms
    )
    voiced = f0_values > 0.0
    periods = 1.0 / f0_values[voiced] if np.any(voiced) else np.zeros(0)
    amplitudes = rms_values[voiced] if np.any(voiced) else np.zeros(0)
    return periods, amplitudes


def jitter_shimmer(signal: np.ndarray, sample_rate: float) -> tuple[float, float]:
    """Jitter (perturbação relativa do período) e shimmer (da amplitude), locais.

    Proxies normalizados [0,~], consistentes com o rótulo interno do FROID —
    porém agora derivados da voz REAL, não de ruído simulado.
    """
    periods, amplitudes = voiced_frame_series(signal, sample_rate)
    return _perturbation(periods, amplitudes)
