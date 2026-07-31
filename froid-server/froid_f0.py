"""
Estimação da Frequência Fundamental (F0) do FROID.

F0 é o pitch da voz — a taxa de vibração das pregas vocais. É um valor de
processamento de sinais bem definido e determinístico, calculado aqui pelo
algoritmo YIN (de Cheveigné & Kawahara, 2002, "YIN, a fundamental frequency
estimator for speech and music", JASA 111(4)), que é o padrão-ouro para voz
por ser robusto a erros de oitava.

Requisito de entrada: uma forma de onda PCM mono (float) e a taxa de
amostragem (sample_rate) em Hz. NÃO opera sobre o vetor espectral de 12 bandas
(que não é uma forma de onda) nem sobre áudio comprimido (Opus/WebM/MP3) — este
precisa ser decodificado para PCM antes (WAV/PCM cru é decodificável só com a
biblioteca padrão; ver read_wav_mono).

Somente numpy é usado.
"""
from __future__ import annotations

import io
import wave
from typing import Tuple

import numpy as np

# Faixa fisiológica da F0 da voz humana falada. Cobre com folga vozes graves
# masculinas (~80 Hz) e agudas femininas/infantis (~400 Hz).
DEFAULT_FMIN = 60.0
DEFAULT_FMAX = 400.0
# Limiar absoluto do YIN. 0.10-0.15 é a faixa recomendada no artigo original.
DEFAULT_THRESHOLD = 0.12


def _difference_function(x: np.ndarray, tau_max: int) -> np.ndarray:
    """d(tau) = sum_j (x[j] - x[j+tau])^2, para tau em [0, tau_max].

    Formulação equivalente via autocorrelação (padrão na literatura do YIN):
        d(tau) = S[n-tau] + (S[n] - S[tau]) - 2*r(tau)
    onde S é a soma cumulativa de x^2 e r a autocorrelação, obtida por FFT.
    Substitui o laço O(n*tau_max) por O(n log n) — o mesmo resultado, muito
    mais rápido (esta função é o ponto mais quente da análise de voz, chamada
    ~150x por janela no cálculo de jitter/shimmer).
    """
    n = x.size
    # Autocorrelação linear via FFT (zero-padding para evitar wrap-around).
    size = 1
    while size < 2 * n:
        size *= 2
    spec = np.fft.rfft(x, n=size)
    corr = np.fft.irfft(spec * np.conjugate(spec), n=size)[: tau_max + 1]

    power = np.concatenate(([0.0], np.cumsum(x * x)))
    taus = np.arange(tau_max + 1)
    d = power[n - taus] + (power[n] - power[taus]) - 2.0 * corr
    d[0] = 0.0
    # Erros de arredondamento da FFT podem gerar valores levemente negativos.
    return np.maximum(d, 0.0)


def _cumulative_mean_normalized(d: np.ndarray) -> np.ndarray:
    """d'(tau): função de diferença com média cumulativa normalizada (YIN)."""
    dprime = np.ones_like(d)
    if d.size > 1:
        taus = np.arange(1, d.size)
        running = np.cumsum(d[1:])
        with np.errstate(divide="ignore", invalid="ignore"):
            values = np.where(running > 0, d[1:] * taus / running, 1.0)
        dprime[1:] = values
    return dprime


def _absolute_threshold(
    dprime: np.ndarray, tau_min: int, tau_max: int, threshold: float
) -> int | None:
    """Menor tau cujo d'(tau) fica abaixo do limiar (descendo ao mínimo local).

    Retorna None quando nenhum vale abaixo do limiar existe no intervalo, o que
    indica quadro não-vozeado (sem periodicidade confiável).
    """
    tau = tau_min
    while tau <= tau_max:
        if dprime[tau] < threshold:
            while tau + 1 <= tau_max and dprime[tau + 1] < dprime[tau]:
                tau += 1
            return tau
        tau += 1
    return None


def _parabolic_interpolation(dprime: np.ndarray, tau: int) -> float:
    """Refina o tau para precisão sub-amostral com parábola nos 3 pontos."""
    if tau <= 0 or tau >= dprime.size - 1:
        return float(tau)
    a, b, c = dprime[tau - 1], dprime[tau], dprime[tau + 1]
    denom = a + c - 2.0 * b
    if denom == 0.0:
        return float(tau)
    shift = 0.5 * (a - c) / denom
    # A correção parabólica válida fica em (-1, 1) amostra.
    if shift < -1.0 or shift > 1.0:
        return float(tau)
    return tau + shift


def estimate_f0_frame(
    frame: np.ndarray,
    sample_rate: float,
    fmin: float = DEFAULT_FMIN,
    fmax: float = DEFAULT_FMAX,
    threshold: float = DEFAULT_THRESHOLD,
) -> float:
    """F0 (Hz) de um único quadro de voz. 0.0 = não-vozeado/sem periodicidade."""
    x = np.asarray(frame, dtype=np.float64)
    n = x.size
    if n < 4 or sample_rate <= 0 or fmax <= fmin:
        return 0.0
    # Remove o nível DC (offset) que enviesa a função de diferença.
    x = x - float(np.mean(x))
    if not np.any(x):
        return 0.0

    tau_min = max(1, int(np.floor(sample_rate / fmax)))
    tau_max = min(n - 1, int(np.ceil(sample_rate / fmin)))
    if tau_max <= tau_min:
        return 0.0

    d = _difference_function(x, tau_max)
    dprime = _cumulative_mean_normalized(d)
    tau = _absolute_threshold(dprime, tau_min, tau_max, threshold)
    if tau is None:
        return 0.0
    tau_refined = _parabolic_interpolation(dprime, tau)
    if tau_refined <= 0:
        return 0.0
    f0 = sample_rate / tau_refined
    if f0 < fmin or f0 > fmax:
        return 0.0
    return float(f0)


def estimate_f0_series(
    signal: np.ndarray,
    sample_rate: float,
    fmin: float = DEFAULT_FMIN,
    fmax: float = DEFAULT_FMAX,
    threshold: float = DEFAULT_THRESHOLD,
    frame_ms: float = 40.0,
    hop_ms: float = 20.0,
) -> Tuple[float, float, float]:
    """Percorre o sinal em quadros e resume a F0.

    Retorna (f0_mean, f0_std, voiced_ratio):
      * f0_mean: mediana das F0 dos quadros vozeados (robusta a outliers), em Hz;
        0.0 se não houver quadro vozeado.
      * f0_std: desvio-padrão das F0 vozeadas (jitter de pitch de longo prazo).
      * voiced_ratio: fração de quadros considerados vozeados (0-1).
    """
    x = np.asarray(signal, dtype=np.float64)
    if x.size == 0 or sample_rate <= 0:
        return 0.0, 0.0, 0.0
    frame_len = max(4, int(round(sample_rate * frame_ms / 1000.0)))
    hop_len = max(1, int(round(sample_rate * hop_ms / 1000.0)))
    if x.size < frame_len:
        f0 = estimate_f0_frame(x, sample_rate, fmin, fmax, threshold)
        return (f0, 0.0, 1.0 if f0 > 0 else 0.0)

    f0_per_frame, _ = frame_f0_series(
        x, sample_rate, fmin, fmax, threshold, frame_ms, hop_ms
    )
    total = f0_per_frame.size
    arr = f0_per_frame[f0_per_frame > 0.0]
    if arr.size == 0:
        return 0.0, 0.0, 0.0
    f0_mean = float(np.median(arr))
    f0_std = float(np.std(arr)) if arr.size > 1 else 0.0
    voiced_ratio = float(arr.size / total) if total else 0.0
    return round(f0_mean, 2), round(f0_std, 2), round(voiced_ratio, 3)


def frame_f0_series(
    signal: np.ndarray,
    sample_rate: float,
    fmin: float = DEFAULT_FMIN,
    fmax: float = DEFAULT_FMAX,
    threshold: float = DEFAULT_THRESHOLD,
    frame_ms: float = 40.0,
    hop_ms: float = 20.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Passagem ÚNICA de F0 por quadro, retornando (f0_por_quadro, rms_por_quadro).

    Antes, estimate_f0_series e jitter_shimmer percorriam o sinal com os
    MESMOS parâmetros (40ms/20ms), estimando F0 duas vezes sobre os mesmos
    quadros. Esta função concentra a passagem; ambos os consumidores a
    reaproveitam. F0 = 0.0 marca quadro não-vozeado.
    """
    x = np.asarray(signal, dtype=np.float64)
    frame_len = max(4, int(round(sample_rate * frame_ms / 1000.0)))
    hop_len = max(1, int(round(sample_rate * hop_ms / 1000.0)))
    if x.size < frame_len:
        f0 = estimate_f0_frame(x, sample_rate, fmin, fmax, threshold)
        rms = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
        return np.asarray([f0], dtype=np.float64), np.asarray([rms], dtype=np.float64)

    n_frames = 1 + (x.size - frame_len) // hop_len
    frames = np.lib.stride_tricks.as_strided(
        x,
        shape=(n_frames, frame_len),
        strides=(x.strides[0] * hop_len, x.strides[0]),
        writeable=False,
    )
    f0_values = np.empty(n_frames, dtype=np.float64)
    for i in range(n_frames):
        f0_values[i] = estimate_f0_frame(frames[i], sample_rate, fmin, fmax, threshold)
    rms_values = np.sqrt(np.mean(frames ** 2, axis=1))
    return f0_values, rms_values


def pcm16_bytes_to_float(pcm_bytes: bytes) -> np.ndarray:
    """Converte PCM 16-bit little-endian assinado em float normalizado [-1, 1]."""
    if not pcm_bytes:
        return np.zeros(0, dtype=np.float64)
    samples = np.frombuffer(pcm_bytes, dtype="<i2").astype(np.float64)
    return samples / 32768.0


def read_wav_mono(wav_bytes: bytes) -> Tuple[np.ndarray, int]:
    """Decodifica WAV/PCM (sem dependências externas) para (mono float, sr).

    Suporta apenas WAV PCM não comprimido — que é o formato decodificável com a
    biblioteca padrão. Áudio Opus/WebM/MP3 exige um decodificador externo
    (ffmpeg/av/librosa) que NÃO está disponível neste ambiente.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        sample_rate = wav.getframerate()
        n_channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())
    if sample_width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    elif sample_width == 1:
        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif sample_width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"Largura de amostra não suportada: {sample_width} bytes")
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    return data, int(sample_rate)
