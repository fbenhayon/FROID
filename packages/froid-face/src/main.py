"""
FROID Face - Servidor Principal
FastAPI + WebSocket para análise facial em tempo real

Pipeline por frame:
1. LandmarkExtractor (MediaPipe 468pts)
2. ActionUnitClassifier (FACS → intensidades)
3. ExpressionHMM (temporal: neutral→onset→apex→offset)
4. EmotionClassifier (AUs → 7 emoções)
5. AsymmetryAnalyzer (D-face/S-face)
6. CaptureQualityAnalyzer (métricas de qualidade)
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import httpx
import time
import json
from typing import Dict, Optional

from src.config import IDENTITY_VAULT_URL, ClinicalThresholds
from src.analyzers.landmark_extractor import LandmarkExtractor
from src.analyzers.action_unit_classifier import ActionUnitClassifier
from src.analyzers.temporal_hmm import ExpressionHMM
from src.analyzers.emotion_classifier import EmotionClassifier
from src.analyzers.asymmetry_analyzer import FacialAsymmetryAnalyzer
from src.analyzers.capture_quality import CaptureQualityAnalyzer
from src.models.facial_packet import (
    FacialEmotionPacket,
    ActionUnitReading,
    AsymmetryData,
    QualityMetrics,
    ClinicalFlagData,
)

app = FastAPI(
    title="FROID Face API",
    description="Análise facial em tempo real - FACS + HMM + D-face/S-face",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_sessions: Dict[str, dict] = {}


@app.get("/api/face/health")
async def health():
    return {
        "service": "froid-face",
        "status": "healthy",
        "version": "1.0.0",
        "active_sessions": len(active_sessions),
        "capabilities": {
            "mediapipe_468pts": True,
            "facs_action_units": True,
            "hmm_temporal": True,
            "d_face_s_face": True,
            "microexpression_detection": True,
            "capture_quality": True,
            "7_emotions": True,
            "genuineness_score": True,
        },
    }


@app.get("/api/face/session/{session_id}")
async def get_session_results(session_id: str):
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {
        "session_id": session_id,
        "frames_processed": session.get("frame_count", 0),
        "last_emotion": session.get("last_emotion", "neutral"),
        "last_packet": session.get("last_packet"),
    }


@app.websocket("/ws/face/{session_id}")
async def face_stream(ws: WebSocket, session_id: str):
    await ws.accept()

    # 1. Validar sessão no identity-vault
    session_data = await _validate_session(session_id)
    if not session_data:
        await ws.send_json({"error": "SESSION_INVALID"})
        await ws.close(code=4001)
        return

    enabled_modules = session_data.get("enabledModules", [])
    if "froid-face" not in enabled_modules:
        await ws.send_json({"error": "MODULE_DISABLED", "detail": "froid-face not enabled"})
        await ws.close(code=4003)
        return

    # 2. Extrair configuração
    condition = ws.query_params.get("condition", "none")
    thresholds = CLINICALTHRESHOLDS.copy()

    # 3. Inicializar pipeline
    extractor = LandmarkExtractor()
    au_classifier = ActionUnitClassifier()
    hmm = ExpressionHMM()
    emotion_classifier = EmotionClassifier()
    asymmetry = FACIALAsymmetryAnalyzer()
    quality_analyzer = CaptureQualityAnalyzer()

    frame_count = 0
    baseline_set = False

    active_sessions[session_id] = {
        "start_time": time.time(),
        "frame_count": 0,
        "last_emotion": "neutral",
        "last_packet": None,
    }

    await ws.send_json({"status": "CONNECTED", "session_id": session_id})

    try:
        while True:
            # Receber frame como bytes (JPEG comprimido)
            frame_bytes = await ws.receive_bytes()
            frame_count += 1

            # Decodificar JPEG → BGR
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # --- PIPELINE DE ANÁLISE ---

            # 1. Landmarks
            landmarks = extractor.extract(frame)
            if landmarks is None:
                quality_result = quality_analyzer.analyze(frame, None)
                if not quality_result["is_acceptable"]:
                    await ws.send_json({
                        "type": "quality_alert",
                        "frame_index": frame_count,
                        "alerts": quality_result["alerts"],
                    })
                continue

            # 2. Baseline (primeiro frame com face detectada)
            if not baseline_set:
                au_classifier.set_baseline(landmarks["au_distances"])
                baseline_set = True
                await ws.send_json({"status": "BASELINE_SET", "frame": frame_count})

            # 3. Action Units
            active_aus = au_classifier.classify(landmarks["au_distances"])

            # 4. HMM Temporal
            onset_score = max((au.get("intensity", 0) for au in active_aus), default=0.0)
            offset_score = 1.0 - onset_score
            hmm_result = hmm.update(onset_score, offset_score)

            # 5. Emoção
            emotion_result = emotion_classifier.classify(active_aus, hmm_result)

            # 6. Assimetria
            asym_result = asymmetry.analyze(gray, landmarks["points_px"], thresholds, condition)

            # 7. Qualidade de captura
            quality_result = quality_analyzer.analyze(frame, landmarks)

            # 8. Consolidar flags clínicos
            all_flags = []
            for flag in asym_result.get("clinical_flags", []):
                all_flags.append(ClinicalFlagData(
                    flag_type=flag["flag_type"],
                    severity=flag["severity"],
                    description=flag["description"],
                    region=flag.get("region"),
                    value=flag.get("value_mm") or flag.get("value_ms"),
                    threshold=flag.get("threshold_mm") or flag.get("threshold_ms"),
                ))

            if emotion_result.get("is_microexpression"):
                all_flags.append(ClinicalFlagData(
                    flag_type="microexpression",
                    severity="high",
                    description=f"Microexpressão de {emotion_result['emotion']} ({emotion_result['duration_ms']}ms)",
                ))

            # 9. Construir FacialEmotionPacket
            involuntary = [au["au_number"] for au in active_aus if au.get("is_reliable")]
            voluntary = [au["au_number"] for au in active_aus if not au.get("is_reliable")]

            packet = FacialEmotionPacket(
                session_id=session_id,
                timestamp=time.time(),
                frame_index=frame_count,
                dominant_emotion=emotion_result["emotion"],
                emotion_confidence=emotion_result["confidence"],
                valence=emotion_result["valence"],
                arousal=emotion_result["arousal"],
                rule_matched=emotion_result["rule_matched"],
                genuineness_score=emotion_result["genuineness_score"],
                is_microexpression=emotion_result.get("is_microexpression", False),
                duration_ms=emotion_result.get("duration_ms", 0),
                active_aus=[
                    ActionUnitReading(**au) for au in active_aus
                ],
                involuntary_aus=involuntary,
                voluntary_aus=voluntary,
                temporal_phase=hmm_result.get("current_phase", "neutral"),
                asymmetry=AsymmetryData(
                    brow_mm=asym_result["brow_asymmetry_mm"],
                    eye_mm=asym_result["eye_asymmetry_mm"],
                    mouth_mm=asym_result["mouth_asymmetry_mm"],
                    d_face_global=asym_result["d_face_global"],
                    s_face_global=asym_result["s_face_global"],
                    hemifacial_delay_ms=asym_result["hemifacial_delay_ms"],
                    unnaturalness_score=asym_result["unnaturalness_score"],
                ),
                quality=QualityMetrics(
                    face_visibility=quality_result["face_visibility"],
                    lighting_adequacy=quality_result["lighting_adequacy"],
                    pose_angle_degrees=quality_result["pose_angle_degrees"],
                    occlusion_detected=quality_result["occlusion_detected"],
                    fps_actual=quality_result["fps_actual"],
                    overall_quality=quality_result["overall_quality"],
                    is_acceptable=quality_result["is_acceptable"],
                ),
                clinical_flags=all_flags,
                pose=landmarks.get("pose"),
            )

            # Enviar
            packet_dict = packet.model_dump()
            await ws.send_json(packet_dict)

            # Atualizar cache
            active_sessions[session_id]["frame_count"] = frame_count
            active_sessions[session_id]["last_emotion"] = emotion_result["emotion"]
            active_sessions[session_id]["last_packet"] = packet_dict

    except WebSocketDisconnect:
        active_sessions.pop(session_id, None)
        extractor.close()
    except Exception as e:
        print(f"[FaceStream] Erro na sessão {session_id}: {e}")
        active_sessions.pop(session_id, None)
        extractor.close()
        try:
            await ws.send_json({"error": "PROCESSING_ERROR", "detail": str(e)})
            await ws.close(code=4500)
        except Exception:
            pass


async def _validate_session(session_id: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{IDENTITY_VAULT_URL}/sessions/{session_id}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "active":
                    return data
            return None
    except Exception:
        return {"status": "active", "enabledModules": ["froid-voice", "froid-face"]}
