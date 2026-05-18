"""
FROID Face - Servidor Principal
FastAPI + WebSocket para análise facial em tempo real

Pipeline por frame:
1. LandmarkExtractor (MediaPipe 468pts)
2. ActionUnitClassifier (FACS -> intensidades)
3. ExpressionHMM (temporal: neutral->onset->apex->offset)
4. EmotionClassifier (AUs -> 7 emocoes)
5. AsymmetryAnalyzer (D-face/S-face)
6. CaptureQualityAnalyzer (metricas de qualidade)
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

app = FastAPI(
    title="FROID Face API",
    description="Analise facial em tempo real - FACS + HMM + D-face/S-face",
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
    }


@app.websocket("/ws/face/{session_id}")
async def face_stream(ws: WebSocket, session_id: str):
    await ws.accept()
    print(f"[FACE] WebSocket accepted for session {session_id}")

    # Inicializar pipeline
    try:
        extractor = LandmarkExtractor()
        au_classifier = ActionUnitClassifier()
        hmm = ExpressionHMM()
        emotion_classifier = EmotionClassifier()
        asymmetry = FacialAsymmetryAnalyzer()
        quality_analyzer = CaptureQualityAnalyzer()
        print("[FACE] All analyzers initialized OK")
    except Exception as e:
        print(f"[FACE] Analyzer init error: {e}")
        await ws.send_json({"error": "INIT_ERROR", "detail": str(e)})
        await ws.close(code=4500)
        return

    frame_count = 0
    baseline_set = False

    active_sessions[session_id] = {
        "start_time": time.time(),
        "frame_count": 0,
        "last_emotion": "neutral",
    }

    await ws.send_json({"status": "CONNECTED", "session_id": session_id})

    try:
        while True:
            frame_bytes = await ws.receive_bytes()
            frame_count += 1

            # Decodificar JPEG -> BGR
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            if frame_count % 30 == 0:
                print(f"[FACE] Frame {frame_count}, size={len(frame_bytes)} bytes")

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 1. Landmarks
            try:
                landmarks = extractor.extract(frame)
            except Exception as e:
                print(f"[FACE] Landmark error: {e}")
                continue

            if landmarks is None:
                # Sem face detectada
                try:
                    quality_result = quality_analyzer.analyze(frame, None)
                    if not quality_result.get("is_acceptable", True) is False:
                        await ws.send_json({
                            "type": "quality_alert",
                            "frame_index": frame_count,
                        })
                except Exception:
                    pass
                continue

            # 2. Baseline
            if not baseline_set:
                try:
                    au_classifier.set_baseline(landmarks["au_distances"])
                    baseline_set = True
                    await ws.send_json({"status": "BASELINE_SET", "frame": frame_count})
                    print(f"[FACE] Baseline set at frame {frame_count}")
                except Exception as e:
                    print(f"[FACE] Baseline error: {e}")

            # 3. Action Units -> retorna List[Dict] com au_number, intensity, etc
            active_aus = []
            try:
                active_aus = au_classifier.classify(landmarks["au_distances"])
            except Exception as e:
                print(f"[FACE] AU error: {e}")

            # 4. HMM Temporal - precisa de (onset_score, offset_score)
            hmm_result = {}
            try:
                onset_score = max((au.get("intensity", 0) for au in active_aus), default=0.0)
                offset_score = 1.0 - onset_score
                hmm_result = hmm.update(onset_score, offset_score)
            except Exception as e:
                print(f"[FACE] HMM error: {e}")
                hmm_result = {"current_phase": "neutral", "apex_confidence": 0.0, "detected": False}

            # 5. Emocao - precisa de dict {au_number: intensity}, nao lista
            emotion_result = {}
            try:
                au_scores_dict = {au["au_number"]: au["intensity"] for au in active_aus}
                hmm_confidence = hmm_result.get("apex_confidence", 0.0)
                emotion_result = emotion_classifier.classify(au_scores_dict, hmm_confidence)
            except Exception as e:
                print(f"[FACE] Emotion error: {e}")
                emotion_result = {"emotion": "neutral", "confidence": 0.0, "valence": 0.0, "arousal": 0.0}

            # 6. Assimetria - precisa de imagem numpy 128x128, nao landmarks
            asym_result = {}
            try:
                # Normalizar imagem para 128x128 grayscale
                normalized = cv2.resize(gray, (128, 128))
                asym_result = asymmetry.analyze(normalized)
            except Exception as e:
                print(f"[FACE] Asymmetry error: {e}")
                asym_result = {"scores": {}, "flags": [], "unnaturalness_score": 1}

            # 7. Genuineness score
            genuineness = 0.5
            try:
                au_scores_dict = {au["au_number"]: au["intensity"] for au in active_aus}
                genuineness = emotion_classifier.get_genuineness_score(au_scores_dict)
            except Exception:
                pass

            # Construir pacote de resposta
            scores = asym_result.get("scores", {})
            packet = {
                "type": "analysis",
                "session_id": session_id,
                "timestamp": time.time(),
                "frame_index": frame_count,
                "dominant_emotion": emotion_result.get("emotion", "neutral"),
                "emotion_confidence": emotion_result.get("confidence", 0.0),
                "valence": emotion_result.get("valence", 0.0),
                "arousal": emotion_result.get("arousal", 0.0),
                "genuineness_score": genuineness,
                "active_aus": [
                    {"au": au["au_number"], "intensity": au["intensity"], "name": au.get("au_name", "")}
                    for au in active_aus
                ],
                "temporal_phase": hmm_result.get("current_phase", "neutral"),
                "is_microexpression": hmm_result.get("is_microexpression", False),
                "asymmetry": {
                    "brow_mm": scores.get("brow_mm", 0.0),
                    "eye_mm": scores.get("eye_mm", 0.0),
                    "mouth_mm": scores.get("mouth_mm", 0.0),
                    "unnaturalness": asym_result.get("unnaturalness_score", 1),
                },
                "clinical_flags": asym_result.get("flags", []),
            }

            await ws.send_json(packet)

            # Atualizar cache
            active_sessions[session_id]["frame_count"] = frame_count
            active_sessions[session_id]["last_emotion"] = emotion_result.get("emotion", "neutral")

    except WebSocketDisconnect:
        print(f"[FACE] Client disconnected: {session_id}")
    except Exception as e:
        print(f"[FACE] Error in session {session_id}: {e}")
        try:
            await ws.send_json({"error": "PROCESSING_ERROR", "detail": str(e)})
            await ws.close(code=4500)
        except Exception:
            pass
    finally:
        active_sessions.pop(session_id, None)
        try:
            extractor.close()
        except Exception:
            pass
