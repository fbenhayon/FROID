"""
FROID Voice - Servidor Principal (v2.0 Clean Rewrite)
FastAPI + WebSocket para analise vocal em tempo real

Pipeline:
1. AudioPipeline (VAD + openSMILE eGeMAPS)
2. SessionNormalizer (baseline 60s + z-score + EMA)
3. ZonalAnalyzer (12 Zonas FROID)
4. SpectralAnalyzer (7 Bandas)
5. SubharmonicAnalyzer (tremor 5-20Hz)
6. ProsodyAnalyzer (F0, Jitter, Shimmer, HNR)
7. ClinicalMapper (depression, mania, stress)
8. ColorMapper (7 niveis colorimetricos)
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import math
import time
from typing import Dict

from src.config import (
    SAMPLE_RATE,
    CALIBRATION_DURATION_SEC,
    SLICE_SEC,
    CLINICAL_THRESHOLDS,
)
from src.analyzers.pipeline import AudioPipeline
from src.analyzers.normalizer import SessionNormalizer
from src.analyzers.clinical_mapper import ClinicalMapper
from src.analyzers.prosody_analyzer import ProsodyAnalyzer
from src.analyzers.spectral_analyzer import SpectralAnalyzer
from src.analyzers.zonal_analyzer import ZonalAnalyzer
from src.analyzers.subharmonic_analyzer import SubharmonicAnalyzer
from src.colorimetry.color_mapper import ColorMapper


# =====================================================
# NaN sanitizer - Python float('nan') breaks JSON.parse
# =====================================================
def sanitize(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj


app = FastAPI(title="FROID Voice API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_sessions: Dict[str, dict] = {}


@app.get("/api/voice/health")
async def health():
    return {
        "service": "froid-voice",
        "status": "healthy",
        "version": "2.0.0",
        "active_sessions": len(active_sessions),
    }


@app.websocket("/ws/voice/{session_id}")
async def voice_stream(ws: WebSocket, session_id: str):
    await ws.accept()
    print(f"[VOICE] Session {session_id} connected")

    # Initialize all analyzers
    try:
        pipeline = AudioPipeline(sample_rate=SAMPLE_RATE)
        sex = ws.query_params.get("sex", "M")
        normalizer = SessionNormalizer(session_id, sex)
        clinical_mapper = ClinicalMapper()
        prosody = ProsodyAnalyzer(sample_rate=SAMPLE_RATE)
        spectral = SpectralAnalyzer()
        zonal = ZonalAnalyzer()
        subharmonic = SubharmonicAnalyzer()
        color_mapper = ColorMapper()
        print("[VOICE] All analyzers initialized OK")
    except Exception as e:
        print(f"[VOICE] Init error: {e}")
        await ws.send_json({"error": str(e)})
        await ws.close(code=4500)
        return

    start_time = time.time()
    last_slice_time = start_time
    audio_accumulator = []
    calibration_notified = False

    active_sessions[session_id] = {"start_time": start_time}

    await ws.send_json(sanitize({
        "status": "CONNECTED",
        "session_id": session_id,
        "calibration_target_sec": CALIBRATION_DURATION_SEC,
    }))

    try:
        while True:
            pcm_bytes = await ws.receive_bytes()
            elapsed = time.time() - start_time

            # Convert PCM16 to float32
            audio_chunk = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            audio_accumulator.extend(audio_chunk.tolist())

            # Process through openSMILE pipeline
            try:
                is_speech, raw_feats = pipeline.process_chunk(pcm_bytes)
            except Exception as e:
                print(f"[VOICE] Pipeline error: {e}")
                is_speech = False
                raw_feats = {}

            # =========================================
            # PHASE 1: CALIBRATION (first 60s)
            # =========================================
            if not normalizer.is_calibrated:
                if is_speech and raw_feats:
                    normalizer.add_baseline_sample(raw_feats)

                # Send calibration progress every ~2s
                if int(elapsed * 2) % 4 == 0:
                    progress = normalizer.get_calibration_progress(elapsed, CALIBRATION_DURATION_SEC)
                    await ws.send_json(sanitize({
                        "type": "calibration",
                        "status": "calibrating",
                        "progress": round(progress, 2),
                        "elapsed_sec": round(elapsed, 1),
                    }))

                # Calibrate after target duration
                if elapsed >= CALIBRATION_DURATION_SEC:
                    try:
                        normalizer.calibrate()
                        calibration_notified = True
                        print(f"[VOICE] Calibration complete at {round(elapsed,1)}s, samples={normalizer.sample_count}")
                        await ws.send_json(sanitize({
                            "type": "calibration",
                            "status": "CALIBRATION_COMPLETE",
                            "session_id": session_id,
                        }))
                    except Exception as e:
                        print(f"[VOICE] Calibration error: {e}")
                        # Force calibrate even with no data
                        normalizer.is_calibrated = True
                        calibration_notified = True

                continue

            # =========================================
            # PHASE 2: REAL-TIME ANALYSIS (every 10s)
            # =========================================
            time_since_slice = time.time() - last_slice_time
            if time_since_slice < SLICE_SEC:
                continue

            last_slice_time = time.time()
            print(f"[VOICE] Emitting analysis packet at {round(elapsed,1)}s")

            # Get accumulated audio for spectral analysis
            audio_array = np.array(audio_accumulator[-SAMPLE_RATE * int(SLICE_SEC):], dtype=np.float32)
            audio_accumulator = audio_accumulator[-SAMPLE_RATE * 30:]  # Keep last 30s

            # --- Zonal Analysis (12 FROID Zones) ---
            try:
                zonal_result = zonal.analyze(audio_array)
            except Exception as e:
                print(f"[VOICE] Zonal error: {e}")
                zonal_result = zonal._empty_result()

            # --- Spectral Analysis (7 Bands) ---
            try:
                spectral_result = spectral.analyze(audio_array)
            except Exception as e:
                print(f"[VOICE] Spectral error: {e}")
                spectral_result = spectral._empty_result()

            # --- Subharmonics (tremor) ---
            try:
                subharm_result = subharmonic.analyze(audio_array)
            except Exception as e:
                print(f"[VOICE] Subharmonic error: {e}")
                subharm_result = subharmonic._empty_result()

            # --- Prosody (F0, Jitter, Shimmer) ---
            try:
                prosody_result = prosody.analyze(audio_array, sex)
            except Exception as e:
                print(f"[VOICE] Prosody error: {e}")
                prosody_result = prosody._empty_result()

            # --- Clinical Scores ---
            clinical_scores = {"depression_risk": 0.5, "mania_activation": 0.5, "stress_cognitive": 0.5}
            clinical_flags = []
            try:
                if is_speech and raw_feats:
                    norm_feats = normalizer.normalize_and_smooth(raw_feats)
                    if norm_feats:
                        clinical_scores = clinical_mapper.compute_scores(norm_feats)
                        clinical_flags = clinical_mapper.get_flags(clinical_scores)
            except Exception as e:
                print(f"[VOICE] Clinical error: {e}")

            # --- Colorimetry ---
            try:
                color_map = color_mapper.map_zones(zonal_result.get("zones", []))
                overall_color = color_mapper.get_overall_color(zonal_result.get("zones", []))
            except Exception as e:
                print(f"[VOICE] Color error: {e}")
                color_map = ["#FFD700"] * 12
                overall_color = "#FFD700"

            # --- Build packet matching frontend expectations ---
            zones_for_frontend = [
                {
                    "zone": z.get("zone", 0),
                    "note": z.get("note", ""),
                    "energy_normalized": z.get("energy_normalized", 0.0),
                }
                for z in zonal_result.get("zones", [])
            ]

            bands_for_frontend = [
                {
                    "band": b.get("band", 0),
                    "range_hz": b.get("range_hz", ""),
                    "correlate": b.get("correlate", ""),
                    "energy_normalized": b.get("energy_normalized", 0.0),
                }
                for b in spectral_result.get("bands", [])
            ]

            # Compute IPM score (congruence index)
            try:
                zone_energies = [z.get("energy_normalized", 0) for z in zonal_result.get("zones", [])]
                zone_std = float(np.std(zone_energies)) if zone_energies else 0
                ipm_score = round(min(1.0, zone_std * 10), 2)
            except Exception:
                ipm_score = 0.0

            # Colorimetry level (1-7, where 4 = neutral)
            try:
                dom_zone_energy = max(zone_energies) if zone_energies else 0
                mean_energy = sum(zone_energies) / len(zone_energies) if zone_energies else 0
                ratio = dom_zone_energy / mean_energy if mean_energy > 0.001 else 1.0
                if ratio > 2.0: colorimetry_level = 1
                elif ratio > 1.5: colorimetry_level = 2
                elif ratio > 1.1: colorimetry_level = 3
                elif ratio > 0.9: colorimetry_level = 4
                elif ratio > 0.6: colorimetry_level = 5
                elif ratio > 0.3: colorimetry_level = 6
                else: colorimetry_level = 7
            except Exception:
                colorimetry_level = 4

            packet = {
                "type": "analysis",
                "session_id": session_id,
                "timestamp": time.time(),

                # Frontend: setCurrentZone
                "dominant_zone": zonal_result.get("dominant_zone", 0),
                "dominant_note": zonal_result.get("dominant_note", ""),

                # Frontend: setZoneData
                "zones": zones_for_frontend,

                # Frontend: setSpectralBands
                "spectral_bands": bands_for_frontend,

                # Frontend: setRiskScores (expects object, not list!)
                "clinical_scores": {
                    "depression_risk": clinical_scores.get("depression_risk", 0.5),
                    "mania_activation": clinical_scores.get("mania_activation", 0.5),
                    "stress_cognitive": clinical_scores.get("stress_cognitive", 0.5),
                },

                # Frontend: setColorimetryLevel
                "colorimetry_level": colorimetry_level,

                # Frontend: setIpmScore
                "ipm_score": ipm_score,

                # Extra data
                "prosody": prosody_result,
                "subharmonics": subharm_result,
                "clinical_flags": clinical_flags,
                "color_map": color_map,
                "overall_color": overall_color,
            }

            print(f"[DEBUG] Sending zones={len(zones_for_frontend)}, bands={len(bands_for_frontend)}, zone_energies={[round(z.get("energy_normalized",0)*100) for z in zones_for_frontend]}")
            print(f"[DEBUG] zones={len(zones_for_frontend)}, bands={len(bands_for_frontend)}, zone_vals={[round(z.get('energy_normalized',0)*100,1) for z in zones_for_frontend[:3]]}...")
            await ws.send_json(sanitize(packet))

    except WebSocketDisconnect:
        print(f"[VOICE] Client disconnected: {session_id}")
    except Exception as e:
        print(f"[VOICE] Error in session {session_id}: {e}")
        import traceback
        traceback.print_exc()
        try:
            await ws.send_json(sanitize({"error": str(e)}))
            await ws.close(code=4500)
        except Exception:
            pass
    finally:
        active_sessions.pop(session_id, None)
