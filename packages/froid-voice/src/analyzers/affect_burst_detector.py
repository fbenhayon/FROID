"""
FROID Voice - Affect Burst Detector v1.0
Detecta vocalizações não-verbais nas pausas de fala.

FASE 1: Implementação base com 4 categorias de bursts
Testável isoladamente antes de integração.
"""

import numpy as np
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class AffectBurstDetector:
    """
    Detecta e classifica affect bursts (vocalizações não-verbais):
    - Suspiro (tristeza)
    - Estalo/ruído glótico (nojo/rejeição)
    - Riso (alegria)
    - Inalação aguda (medo/choque)
    """
    
    THRESHOLDS = {
        "suspiro": {
            "energy_decay_min": 0.65,
            "f0_std_max": 25,
            "duration_min_ms": 400,
        },
        "nojo": {
            "zcr_min": 0.22,
            "hnr_max": 10,
            "energy_min": 0.008,
        },
        "riso": {
            "f0_std_min": 28,
            "periodic_pulses_min": 3,
            "duration_min_ms": 300,
        },
        "medo": {
            "energy_min": 0.015,
            "zcr_min": 0.28,
            "duration_max_ms": 600,
        }
    }
    
    def __init__(self, sample_rate: int = 16000, enable_logging: bool = True):
        self.sample_rate = sample_rate
        self.enable_logging = enable_logging
        self.stats = {
            "total_analyzed": 0,
            "bursts_detected": 0,
            "by_type": {
                "suspiro": 0,
                "nojo": 0,
                "riso": 0,
                "medo": 0
            }
        }
    
    def detect(
        self, 
        audio: np.ndarray, 
        is_speech: bool,
        prosody_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Detecta burst durante pausa."""
        self.stats["total_analyzed"] += 1
        
        if is_speech or len(audio) < self.sample_rate * 0.25:
            return None
        
        duration_ms = len(audio) / self.sample_rate * 1000
        features = self._extract_features(audio, prosody_data)
        burst_result = self._classify_burst(features, duration_ms)
        
        if burst_result and self.enable_logging:
            logger.info(f"[BurstDetector] {burst_result['type']} detectado")
            self.stats["bursts_detected"] += 1
            burst_key = burst_result["type"].split("[")[1].split("/")[0].strip().lower()
            if burst_key in self.stats["by_type"]:
                self.stats["by_type"][burst_key] += 1
        
        return burst_result
    
    def _extract_features(self, audio: np.ndarray, prosody_data: Optional[Dict] = None) -> Dict:
        """Extrai features acústicas."""
        zcr = self._compute_zcr(audio)
        energy = np.sqrt(np.mean(audio ** 2))
        energy_decay = self._compute_decay_rate(audio)
        
        if prosody_data:
            f0_mean = prosody_data.get("f0_mean", 0)
            f0_std = prosody_data.get("f0_std", 0)
            hnr = prosody_data.get("hnr", 0)
        else:
            f0_mean, f0_std = self._estimate_f0_simple(audio)
            hnr = 0
        
        has_periodic_pulses, pulse_count = self._detect_periodic_pulses(audio)
        
        return {
            "zcr": zcr,
            "energy": energy,
            "energy_decay": energy_decay,
            "f0_mean": f0_mean,
            "f0_std": f0_std,
            "hnr": hnr,
            "has_periodic_pulses": has_periodic_pulses,
            "pulse_count": pulse_count,
        }
    
    def _classify_burst(self, features: Dict, duration_ms: float) -> Optional[Dict]:
        """Classifica tipo de burst."""
        
        if self._is_suspiro(features, duration_ms):
            return {
                "type": "AFFECT BURST [TRISTEZA / SUSPIRO]",
                "confidence": self._compute_suspiro_confidence(features),
                "features": features,
                "category": "suspiro"
            }
        
        if self._is_nojo(features):
            return {
                "type": "AFFECT BURST [NOJO / REJEIÇÃO]",
                "confidence": self._compute_nojo_confidence(features),
                "features": features,
                "category": "nojo"
            }
        
        if self._is_riso(features, duration_ms):
            return {
                "type": "AFFECT BURST [ALEGRIA / RISO]",
                "confidence": self._compute_riso_confidence(features),
                "features": features,
                "category": "riso"
            }
        
        if self._is_medo(features, duration_ms):
            return {
                "type": "AFFECT BURST [MEDO / CHOQUE]",
                "confidence": self._compute_medo_confidence(features),
                "features": features,
                "category": "medo"
            }
        
        return None
    
    def _is_suspiro(self, f: Dict, duration_ms: float) -> bool:
        t = self.THRESHOLDS["suspiro"]
        return (
            f["energy_decay"] > t["energy_decay_min"] and
            f["f0_mean"] > 50 and
            f["f0_std"] < t["f0_std_max"] and
            duration_ms >= t["duration_min_ms"]
        )
    
    def _is_nojo(self, f: Dict) -> bool:
        t = self.THRESHOLDS["nojo"]
        return (
            f["zcr"] > t["zcr_min"] and
            f["hnr"] < t["hnr_max"] and
            f["energy"] > t["energy_min"]
        )
    
    def _is_riso(self, f: Dict, duration_ms: float) -> bool:
        t = self.THRESHOLDS["riso"]
        return (
            f["has_periodic_pulses"] and
            f["pulse_count"] >= t["periodic_pulses_min"] and
            f["f0_std"] > t["f0_std_min"] and
            duration_ms >= t["duration_min_ms"]
        )
    
    def _is_medo(self, f: Dict, duration_ms: float) -> bool:
        t = self.THRESHOLDS["medo"]
        return (
            f["energy"] > t["energy_min"] and
            f["zcr"] > t["zcr_min"] and
            duration_ms < t["duration_max_ms"]
        )
    
    def _compute_suspiro_confidence(self, f: Dict) -> float:
        decay_score = min(f["energy_decay"] / 0.9, 1.0)
        stability_score = max(0, 1.0 - f["f0_std"] / 30)
        return round((decay_score + stability_score) / 2, 3)
    
    def _compute_nojo_confidence(self, f: Dict) -> float:
        zcr_score = min(f["zcr"] / 0.4, 1.0)
        noise_score = max(0, 1.0 - f["hnr"] / 15) if f["hnr"] > 0 else 0.8
        return round((zcr_score + noise_score) / 2, 3)
    
    def _compute_riso_confidence(self, f: Dict) -> float:
        pulse_score = min(f["pulse_count"] / 5, 1.0)
        variation_score = min(f["f0_std"] / 50, 1.0)
        return round((pulse_score + variation_score) / 2, 3)
    
    def _compute_medo_confidence(self, f: Dict) -> float:
        energy_score = min(f["energy"] / 0.04, 1.0)
        zcr_score = min(f["zcr"] / 0.4, 1.0)
        return round((energy_score + zcr_score) / 2, 3)
    
    def _compute_zcr(self, audio: np.ndarray) -> float:
        signs = np.sign(audio)
        zcr = np.mean(np.abs(np.diff(signs))) / 2
        return float(zcr)
    
    def _compute_decay_rate(self, audio: np.ndarray, window_ms: int = 80) -> float:
        window_samples = int(self.sample_rate * window_ms / 1000)
        chunks = []
        for i in range(0, len(audio), window_samples):
            chunk = audio[i:i+window_samples]
            if len(chunk) == window_samples:
                chunks.append(chunk)
        
        if len(chunks) < 2:
            return 0.0
        
        energies = [np.mean(chunk ** 2) for chunk in chunks]
        times = np.arange(len(energies))
        correlation = np.corrcoef(times, energies)[0, 1]
        return float(abs(min(correlation, 0)))
    
    def _estimate_f0_simple(self, audio: np.ndarray) -> Tuple[float, float]:
        autocorr = np.correlate(audio, audio, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        min_lag = int(self.sample_rate / 500)
        max_lag = int(self.sample_rate / 50)
        
        if max_lag >= len(autocorr):
            return 0.0, 0.0
        
        search_range = autocorr[min_lag:max_lag]
        if len(search_range) == 0:
            return 0.0, 0.0
        
        peak_lag = np.argmax(search_range) + min_lag
        f0_mean = self.sample_rate / peak_lag if peak_lag > 0 else 0.0
        f0_std = f0_mean * 0.1
        
        return float(f0_mean), float(f0_std)
    
    def _detect_periodic_pulses(self, audio: np.ndarray, min_pulses: int = 3) -> Tuple[bool, int]:
        autocorr = np.correlate(audio, audio, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        if len(autocorr) == 0 or autocorr[0] == 0:
            return False, 0
        
        autocorr = autocorr / autocorr[0]
        threshold = 0.25
        min_distance = int(self.sample_rate * 0.08)
        
        peaks = []
        for i in range(min_distance, len(autocorr)):
            if autocorr[i] > threshold:
                if i == 0 or (autocorr[i] > autocorr[i-1] and 
                             (i == len(autocorr)-1 or autocorr[i] > autocorr[i+1])):
                    peaks.append(i)
        
        has_pulses = len(peaks) >= min_pulses
        return has_pulses, len(peaks)
    
    def get_stats(self) -> Dict:
        return {
            **self.stats,
            "detection_rate": round(
                self.stats["bursts_detected"] / max(self.stats["total_analyzed"], 1) * 100,
                1
            )
        }
    
    def reset_stats(self):
        self.stats = {
            "total_analyzed": 0,
            "bursts_detected": 0,
            "by_type": {
                "suspiro": 0,
                "nojo": 0,
                "riso": 0,
                "medo": 0
            }
        }
