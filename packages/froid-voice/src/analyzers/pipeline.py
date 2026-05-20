"""
FROID Voice - Pipeline de Áudio
VAD (Voice Activity Detection) + Extração openSMILE eGeMAPS

Fonte: API Voice (Qwen) + openSMILE 88 features eGeMAPS
"""

import numpy as np
import opensmile
import webrtcvad
from typing import Dict, Tuple, Optional


class AudioPipeline:
    """
    Pipeline de processamento de áudio em tempo real.
    - VAD com webrtcvad (agressividade 3 para ambiente clínico)
    - Extração de 88 features eGeMAPS via openSMILE
    - Buffer circular com janela deslizante
    """

    def __init__(self, sample_rate: int = 16000, window_sec: float = 2.0, stride_sec: float = 0.5):
        self.sample_rate = sample_rate
        self.window_samples = int(window_sec * sample_rate)
        self.stride_samples = int(stride_sec * sample_rate)

        # VAD - agressividade 3 (máxima filtragem de silêncio)
        self.vad = webrtcvad.Vad(1)

        # openSMILE - eGeMAPS v02 (88 features)
        self.smile = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.Functionals,
            sampling_rate=sample_rate,
        )

        self.buffer = []

    def process_chunk(self, pcm_bytes: bytes) -> Tuple[bool, Dict[str, float]]:
        """
        Processa chunk de áudio PCM 16-bit mono.
        
        Args:
            pcm_bytes: Bytes de áudio PCM 16-bit mono no sample_rate configurado
            
        Returns:
            Tuple (is_speech, features_dict)
            - is_speech: True se fala detectada
            - features_dict: Dicionário com features extraídas (vazio se silêncio)
        """
        # Converter PCM para float32 normalizado
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self.buffer.extend(audio.tolist())

        # Verificar se temos dados suficientes para uma janela
        if len(self.buffer) < self.window_samples:
            return False, {}

        # Extrair janela e avançar stride
        chunk = np.array(self.buffer[: self.window_samples], dtype=np.float32)
        self.buffer = self.buffer[self.stride_samples:]

        # VAD: verificar se há fala na janela
        try:
            # webrtcvad espera int16
            chunk_int16 = (chunk * 32768).astype(np.int16).tobytes()
            # VAD opera em frames de 10/20/30ms
            frame_duration_ms = 30
            frame_size = int(self.sample_rate * frame_duration_ms / 1000)
            speech_frames = 0
            total_frames = 0
            for i in range(0, len(chunk) - frame_size, frame_size):
                frame = chunk_int16[i * 2: (i + frame_size) * 2]
                if len(frame) == frame_size * 2:
                    total_frames += 1
                    if self.vad.is_speech(frame, self.sample_rate):
                        speech_frames += 1

            # Considerar fala se >10% dos frames contêm voz
            if total_frames == 0 or (speech_frames / total_frames) < 0.3:
                return False, {}
        except Exception:
            # Se VAD falhar, prosseguir com a análise
            pass

        # Extração openSMILE
        try:
            feats_df = self.smile.process_signal(chunk, self.sample_rate)
            if feats_df.empty:
                return False, {}

            feats = feats_df.iloc[0].to_dict()

            # Mapear nomes openSMILE para nomes internos FROID
            clean_feats = self._map_features(feats)
            return True, clean_feats

        except Exception as e:
            print(f"[AudioPipeline] Erro na extração: {e}")
            return False, {}

    def _map_features(self, raw_feats: dict) -> Dict[str, float]:
        """Mapeia nomes do openSMILE para nomenclatura interna FROID."""
        return {
            "F0_mean": raw_feats.get("F0semitoneFrom27.5Hz_sma3nz_amean", 0.0),
            "F0_std": raw_feats.get("F0semitoneFrom27.5Hz_sma3nz_stddevNorm", 0.0),
            "F0_var": raw_feats.get("F0semitoneFrom27.5Hz_sma3nz_percentile80.0", 0.0),
            "Intensity_mean": raw_feats.get("loudness_sma3_amean", 0.0),
            "Spectral_flux": raw_feats.get("spectralFlux_sma3_amean", 0.0),
            "Jitter_local": raw_feats.get("jitterLocal_sma3nz_amean", 0.0),
            "Shimmer_local": raw_feats.get("shimmerLocaldB_sma3nz_amean", 0.0),
            "HNR": raw_feats.get("HNRdBACF_sma3nz_amean", 0.0),
            "Speech_rate": raw_feats.get("VoicedSegmentsPerSec", 0.0),
            "ZCR": raw_feats.get("Loudness_sma3_amean", 0.0),  # Proxy
            "MFCC1": raw_feats.get("mfcc1_sma3_amean", 0.0),
            "MFCC2": raw_feats.get("mfcc2_sma3_amean", 0.0),
            "MFCC3": raw_feats.get("mfcc3_sma3_amean", 0.0),
            "MFCC4": raw_feats.get("mfcc4_sma3_amean", 0.0),
            "MFCC5": raw_feats.get("mfcc5V_sma3nz_amean", 0.0),
            "MFCC6": raw_feats.get("mfcc6V_sma3nz_amean", 0.0),
            "MFCC7": raw_feats.get("mfcc7V_sma3nz_amean", 0.0),
            "F0_upleveltime90": raw_feats.get("F0semitoneFrom27.5Hz_sma3nz_percentile90.0", 0.0),
            "ΔF0_iqr1-3": raw_feats.get("F0semitoneFrom27.5Hz_sma3nz_pctlrange0-2", 0.0),
            "Duration_VV_zscore": raw_feats.get("StddevVoicedSegmentLengthSec", 0.0),
        }

    def get_raw_audio(self, duration_sec: float) -> Optional[np.ndarray]:
        """Retorna os últimos N segundos de áudio do buffer para análises espectrais."""
        samples_needed = int(duration_sec * self.sample_rate)
        if len(self.buffer) < samples_needed:
            return None
        return np.array(self.buffer[-samples_needed:], dtype=np.float32)

    def reset(self):
        """Limpa o buffer de áudio."""
        self.buffer = []
