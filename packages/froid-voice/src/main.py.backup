"""
FROID Voice - Servidor Principal
FastAPI + WebSocket para análise vocal em tempo real

Integração:
- identity-vault (porta 3001): validação de sessão e módulos habilitados
- Redis: cache e pub/sub para comunicação com froid-face

Fluxo:
1. WebSocket conecta com session_id
2. Valida sessão no identity-vault (status=active, froid-voice em enabledModules)
3. Primeiros 60s: calibração (baseline do paciente)
4. Após calibração: análise contínua com ZonalEnergyPacket a cada 10s
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import numpy as np
import time
import json
from typing import Dict, Optional

from src.config import (
    IDENTITY_VAULT_URL,
    CALIBRATION_DURATION_SEC,
    SAMPLE_RATE,
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
from src.analyzers.speech_rate_analyzer import SpeechRateAnalyzer
from src.colorimetry.color_mapper import ColorMapper
from src.models.voice_packet import (
    ZonalEnergyPacket,
    ZoneEnergy,
    BandEnergy,
    ClinicalScore,
    ProsodyData,
    SubharmonicData,
    CalibrationStatus,
)

app = FastAPI(
    title="FROID Voice API",
    description="Análise vocal em tempo real - 12 Zonas FROID + 7 Bandas Espectrais + Scoring Clínico",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache de sessões ativas
active_sessions: Dict[str, dict] = {}


# ===========================================================================
# REST ENDPOINTS
# ===========================================================================

@app.get("/api/voice/health")
async def health():
    return {
        "service": "froid-voice",
        "status": "healthy",
        "version": "1.0.0",
        "active_sessions": len(active_sessions),
    }


@app.get("/api/voice/session/{session_id}")
async def get_session_results(session_id: str):
    """Retorna resultados acumulados de uma sessão."""
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {
        "session_id": session_id,
        "is_calibrated": session["normalizer"].is_calibrated,
        "slices_processed": session.get("slice_count", 0),
        "last_packet": session.get("last_packet"),
    }


# ===========================================================================
# WEBSOCKET - STREAMING EM TEMPO REAL
# ===========================================================================

@app.websocket("/ws/voice/{session_id}")
async def voice_stream(ws: WebSocket, session_id: str):
    await ws.accept()

    # 1. Validar sessão no identity-vault
    session_data = await _validate_session(session_id)
    if not session_data:
        await ws.send_json({
            "error": "SESSION_INVALID",
            "detail": f"Session {session_id} not found or not active",
        })
        await ws.close(code=4001)
        return

    # 2. Verificar se froid-voice está em enabledModules
    enabled_modules = session_data.get("enabledModules", [])
    if "froid-voice" not in enabled_modules:
        await ws.send_json({
            "error": "MODULE_DISABLED",
            "detail": "froid-voice not in enabledModules for this session",
        })
        await ws.close(code=4003)
        return

    # 3. Extrair sexo do paciente (para ajuste de normalização)
    sex = ws.query_params.get("sex", "M")

    # 4. Inicializar analisadores
    pipeline = AudioPipeline()
    normalizer = SessionNormalizer(session_id, sex)
    clinical_mapper = ClinicalMapper()
    prosody = ProsodyAnalyzer()
    spectral = SpectralAnalyzer()
    zonal = ZonalAnalyzer()
    subharmonic = SubharmonicAnalyzer()
    speech_rate = SpeechRateAnalyzer()
    color_mapper = ColorMapper()

    start_time = time.time()
    slice_count = 0
    last_slice_time = start_time
    audio_accumulator = []

    active_sessions[session_id] = {
        "start_time": start_time,
        "normalizer": normalizer,
        "pipeline": pipeline,
        "slice_count": 0,
        "last_packet": None,
    }

    await ws.send_json({
        "status": "CONNECTED",
        "session_id": session_id,
        "sex": sex,
        "calibration_target_sec": CALIBRATION_DURATION_SEC,
    })

    try:
        while True:
            # Receber áudio PCM 16-bit mono
            pcm_bytes = await ws.receive_bytes()
            elapsed = time.time() - start_time

            # Processar chunk no pipeline openSMILE
            is_speech, raw_feats = pipeline.process_chunk(pcm_bytes)

            # Acumular áudio bruto para análises espectrais (fatias de 10s)
            audio_chunk = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            audio_accumulator.extend(audio_chunk.tolist())

            # ============================================================
            # FASE 1: CALIBRAÇÃO (primeiros 60s)
            # ============================================================
            if not normalizer.is_calibrated:
                if is_speech:
                    normalizer.add_baseline_sample(raw_feats)

                progress = normalizer.get_calibration_progress(elapsed, CALIBRATION_DURATION_SEC)

                # Enviar status de calibração a cada 5s
                if int(elapsed) % 5 == 0:
                    cal_status = CalibrationStatus(
                        session_id=session_id,
                        status="calibrating",
                        progress=progress,
                        elapsed_sec=round(elapsed, 1),
                    )
                    await ws.send_json(cal_status.model_dump())

                # Calibrar quando atingir 60s
                if elapsed >= CALIBRATION_DURATION_SEC:
                    baseline = normalizer.calibrate()
                    await ws.send_json({
                        "status": "CALIBRATION_COMPLETE",
                        "session_id": session_id,
                        "baseline_summary": normalizer.get_baseline_summary(),
                    })

                continue

            # ============================================================
            # FASE 2: ANÁLISE EM TEMPO REAL
            # ============================================================

            # Verificar se é hora de emitir um ZonalEnergyPacket (a cada 10s)
            time_since_last_slice = time.time() - last_slice_time
            if time_since_last_slice < SLICE_SEC:
                continue

            last_slice_time = time.time()
            slice_count += 1

            # Extrair áudio acumulado da fatia
            slice_samples = int(SLICE_SEC * SAMPLE_RATE)
            if len(audio_accumulator) < slice_samples:
                continue

            audio_slice = np.array(audio_accumulator[:slice_samples], dtype=np.float32)
            audio_accumulator = audio_accumulator[slice_samples:]

            # ---- Executar todos os analisadores ----

            # openSMILE + Normalização + Scoring Clínico
            norm_feats = normalizer.normalize_and_smooth(raw_feats) if is_speech else {}
            clinical_scores_raw = clinical_mapper.compute_scores(norm_feats) if norm_feats else {}
            clinical_flags = clinical_mapper.get_flags(clinical_scores_raw) if norm_feats else []

            # Prosódia (Parselmouth)
            prosody_data = prosody.analyze(audio_slice, sex)

            # 7 Bandas Espectrais
            spectral_data = spectral.analyze(audio_slice)

            # 12 Zonas FROID
            zonal_data = zonal.analyze(audio_slice)

            # Sub-harmônicos (SNA)
            subharmonic_data = subharmonic.analyze(audio_slice)

            # Taxa de fala (librosa)
            speech_data = speech_rate.analyze(audio_slice)

            # Colorimetria
            colors = color_mapper.map_zones(zonal_data.get("zones", []))
            overall_color = color_mapper.get_overall_color(zonal_data.get("zones", []))

            # ---- Construir ZonalEnergyPacket ----
            packet = ZonalEnergyPacket(
                session_id=session_id,
                timestamp=time.time(),
                slice_index=slice_count,
                # 12 Zonas
                zones=[
                    ZoneEnergy(
                        zone=z["zone"],
                        note=z["note"],
                        freq_hz=z["freq_hz"],
                        positive=z["positive"],
                        negative=z["negative"],
                        energy_normalized=z["energy_normalized"],
                        color_hex=colors[i] if i < len(colors) else "#FFD700",
                    )
                    for i, z in enumerate(zonal_data.get("zones", []))
                ],
                dominant_zone=zonal_data.get("dominant_zone", 0),
                dominant_note=zonal_data.get("dominant_note", ""),
                dominant_dichotomy=zonal_data.get("dominant_dichotomy", {}),
                # 7 Bandas
                spectral_bands=[
                    BandEnergy(
                        band=b["band"],
                        range_hz=b["range_hz"],
                        correlate=b["correlate"],
                        energy_normalized=b["energy_normalized"],
                    )
                    for b in spectral_data.get("bands", [])
                ],
                dominant_band=spectral_data.get("dominant_band", 0),
                dominant_correlate=spectral_data.get("dominant_correlate", ""),
                # Prosódia
                prosody=ProsodyData(
                    f0_mean=prosody_data["f0_mean"],
                    f0_std=prosody_data["f0_std"],
                    f0_range=prosody_data["f0_range"],
                    jitter_local=prosody_data["jitter_local"],
                    shimmer_local=prosody_data["shimmer_local"],
                    hnr=prosody_data["hnr"],
                    speech_rate=speech_data["syllables_per_sec"],
                    silence_ratio=speech_data["silence_ratio"],
                    clinical_pattern=speech_data["clinical_pattern"],
                ),
                # Sub-harmônicos
                subharmonics=SubharmonicData(
                    energy_ratio=subharmonic_data["energy_ratio"],
                    tremor_detected=subharmonic_data["tremor_detected"],
                    tremor_frequency_hz=subharmonic_data["tremor_frequency_hz"],
                    clinical_note=subharmonic_data["clinical_note"],
                ),
                # Scoring Clínico
                clinical_scores=[
                    ClinicalScore(
                        construct=k,
                        score=v,
                        threshold=CLINICAL_THRESHOLDS.get(k, 0.5),
                        is_alert=v > CLINICAL_THRESHOLDS.get(k, 0.5),
                        description=f"{k}: {v:.3f}",
                    )
                    for k, v in clinical_scores_raw.items()
                ],
                clinical_flags=clinical_flags,
                # Colorimetria
                color_map=colors,
                overall_color=overall_color,
                # eGeMAPS brutas
                egemaps_raw=raw_feats if is_speech else None,
            )

            # Enviar via WebSocket
            packet_dict = packet.model_dump()
            packet_dict["timestamp"] = str(packet.timestamp)
            await ws.send_json(packet_dict)

            # Atualizar cache
            active_sessions[session_id]["slice_count"] = slice_count
            active_sessions[session_id]["last_packet"] = packet_dict

    except WebSocketDisconnect:
        active_sessions.pop(session_id, None)
    except Exception as e:
        print(f"[VoiceStream] Erro na sessão {session_id}: {e}")
        active_sessions.pop(session_id, None)
        try:
            await ws.send_json({"error": "PROCESSING_ERROR", "detail": str(e)})
            await ws.close(code=4500)
        except Exception:
            pass


async def _validate_session(session_id: str) -> Optional[dict]:
    """Valida sessão no identity-vault."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{IDENTITY_VAULT_URL}/sessions/{session_id}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "active":
                    return data
            return None
    except Exception as e:
        print(f"[ValidateSession] Erro ao consultar identity-vault: {e}")
        # Em desenvolvimento, permitir sem validação
        return {"status": "active", "enabledModules": ["froid-voice", "froid-face"]}
