import asyncio
import uuid
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from froid_core import SessionState, MockBiometricStream
import httpx

app = FastAPI(title="FROID Fusion Server", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

OPENAI_API_KEY = "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"

KNOWLEDGE_BASE = {
    "froid_zonas": "As 12 Zonas de Percepção FROID mapeiam conflitos subconscientes via bioacústica e FACS.",
    "intervencoes": "TCC de terceira onda, DBT, EMDR e análise focalizada são eficazes para perfis com Zonas 7 e 12 ativas.",
    "populacao": "Base anônima: 12.000+ perfis clínicos. Média de IPM: 48.5. Desvio padrão: 14.2.",
    "riscos": "Dissonância facial-vocal >2.5x com Zona 12 >4.0 indica risco de decompensação emocional.",
    "notebooklm": "Contexto integrado do NotebookLM FROID: pacientes com supressão crônica (Zona 9) respondem melhor à intervenção somática.",
}

class ConnectionManager:
    def __init__(self):
        self.active_sessions: Dict[str, Dict] = {}
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_sessions[session_id] = {"ws": websocket, "state": SessionState(session_id=session_id)}
    def disconnect(self, session_id: str):
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
    async def broadcast_payload(self, session_id: str, payload: dict):
        if session_id in self.active_sessions:
            try:
                await self.active_sessions[session_id]["ws"].send_json(payload)
            except Exception:
                pass

manager = ConnectionManager()

async def froid_stream_loop(session_id: str):
    entry = manager.active_sessions.get(session_id)
    if not entry: return
    state: SessionState = entry["state"]
    while session_id in manager.active_sessions:
        voice_12 = MockBiometricStream.generate_voice_spectral()
        facs_flags, facs_details = MockBiometricStream.generate_facs_dissonance()
        payload = state.process_tick(voice_12, facs_flags, facs_details)
        await manager.broadcast_payload(session_id, payload)
        await asyncio.sleep(0.5)

@app.websocket("/ws/fusion/{session_id}")
async def websocket_fusion(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    task = asyncio.create_task(froid_stream_loop(session_id))
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping": await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(session_id); task.cancel()
    except Exception:
        manager.disconnect(session_id); task.cancel()

@app.get("/health")
def health(): return {"status": "ok", "active_sessions": len(manager.active_sessions)}

@app.post("/session/create")
def create_session(): return {"session_id": str(uuid.uuid4())}

@app.post("/api/insights")
async def insights_proxy(request: Request):
    try:
        body = await request.json()
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": body.get("model", "gpt-4o-mini"), "messages": body.get("messages", []), "temperature": 0.4, "max_tokens": 700}
            )
            return r.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/knowledge")
async def knowledge_base(q: str = ""):
    results = []
    qlower = q.lower()
    for k, v in KNOWLEDGE_BASE.items():
        if qlower in k or qlower in v.lower() or not q:
            results.append({"source": k, "content": v})
    return {"query": q, "results": results}

@app.post("/api/transcribe")
async def transcribe_audio(request: Request):
    """Endpoint reservado para integração com gpt-realtime-whisper. Recebe audio_chunk e retorna transcrição."""
    body = await request.json()
    # Placeholder: em produção, enviar bytes para OpenAI Realtime API
    return {"status": "mock", "text": body.get("fallback_text", ""), "provider": "openai-realtime-whisper-placeholder"}
