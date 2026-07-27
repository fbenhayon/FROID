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
    """d(tau) = sum_j (x[j] - x[j+tau])^2, para tau em [0, tau_max]."""
    n = x.size
    d = np.zeros(tau_max + 1, dtype=np.float64)
    for tau in range(1, tau_max + 1):
        diff = x[: n - tau] - x[tau:]
        d[tau] = float(np.dot(diff, diff))
    return d


def _cumulative_mean_normalized(d: np.ndarray) -> np.ndarray:
    """d'(tau): função de diferença com média cumulativa normalizada (YIN)."""
    dprime = np.ones_like(d)
    running_sum = 0.0
    for tau in range(1, d.size):
        running_sum += d[tau]
        dprime[tau] = d[tau] * tau / running_sum if running_sum > 0 else 1.0
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

    voiced: list[float] = []
    total = 0
    for start in range(0, x.size - frame_len + 1, hop_len):
        total += 1
        f0 = estimate_f0_frame(x[start : start + frame_len], sample_rate, fmin, fmax, threshold)
        if f0 > 0.0:
            voiced.append(f0)
    if not voiced:
        return 0.0, 0.0, 0.0
    arr = np.asarray(voiced, dtype=np.float64)
    f0_mean = float(np.median(arr))
    f0_std = float(np.std(arr)) if arr.size > 1 else 0.0
    voiced_ratio = float(len(voiced) / total) if total else 0.0
    return round(f0_mean, 2), round(f0_std, 2), round(voiced_ratio, 3)


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
