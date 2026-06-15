import asyncio
import base64
import io
import os
import secrets
import uuid
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_AUTH_DEV_FALLBACK = os.getenv("GOOGLE_AUTH_DEV_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}
FROID_LOCAL_AUTH_PASSWORD = os.getenv("FROID_LOCAL_AUTH_PASSWORD", "")
FROID_LOCAL_AUTH_EMAILS = {
    email.strip().lower()
    for email in os.getenv("FROID_LOCAL_AUTH_EMAILS", "").split(",")
    if email.strip()
}

SESSION_USERS = {}

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


def _decode_audio_bytes(body: dict):
    for key in ("audio_bytes", "audio", "audio_chunk", "file"):
        value = body.get(key)
        if isinstance(value, bytes):
            return value
        if isinstance(value, str) and value:
            try:
                return base64.b64decode(value, validate=True)
            except Exception:
                return None
    if isinstance(body.get("audio_base64"), str) and body.get("audio_base64"):
        try:
            return base64.b64decode(body["audio_base64"], validate=True)
        except Exception:
            return None
    if isinstance(body.get("audio_chunks"), list):
        chunks = []
        for chunk in body["audio_chunks"]:
            if isinstance(chunk, str):
                try:
                    chunks.append(base64.b64decode(chunk, validate=True))
                except Exception:
                    continue
            elif isinstance(chunk, bytes):
                chunks.append(chunk)
        if chunks:
            return b"".join(chunks)
    return None


async def _transcribe_with_openai(audio_bytes: bytes, fallback_text: str = "") -> str:
    if not audio_bytes or not OPENAI_API_KEY:
        return fallback_text
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "froid-session.wav"
        response = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception:
        pass
    return fallback_text


def _issue_session(user: dict):
    token = secrets.token_urlsafe(32)
    SESSION_USERS[token] = user
    return {"token": token, "user": user}


def _verify_local_login(body: dict) -> dict:
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email:
        raise HTTPException(status_code=400, detail="email obrigatorio")

    if FROID_LOCAL_AUTH_PASSWORD:
        if not secrets.compare_digest(password, FROID_LOCAL_AUTH_PASSWORD):
            raise HTTPException(status_code=401, detail="senha invalida")
        if FROID_LOCAL_AUTH_EMAILS and email not in FROID_LOCAL_AUTH_EMAILS:
            raise HTTPException(status_code=403, detail="email nao autorizado")
    elif not GOOGLE_AUTH_DEV_FALLBACK:
        raise HTTPException(status_code=400, detail="Credencial Google obrigatoria")

    return {
        "email": email,
        "provider": "local-dev",
        "name": body.get("name") or email.split("@", 1)[0],
    }


async def _verify_google_credential(credential: str) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID nao configurado")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Credencial Google invalida")

    profile = response.json()
    if profile.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Credencial Google de outro aplicativo")
    if str(profile.get("email_verified", "")).lower() != "true":
        raise HTTPException(status_code=401, detail="E-mail Google nao verificado")

    email = (profile.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Credencial Google sem e-mail")

    return {
        "email": email,
        "name": profile.get("name") or email.split("@", 1)[0],
        "picture": profile.get("picture") or "",
        "provider": "google",
        "google_sub": profile.get("sub") or "",
    }


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

@app.get("/api/auth/config")
def auth_config():
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "dev_fallback_enabled": GOOGLE_AUTH_DEV_FALLBACK,
        "local_login_enabled": bool(FROID_LOCAL_AUTH_PASSWORD or GOOGLE_AUTH_DEV_FALLBACK),
    }

@app.post("/api/auth/google")
async def auth_google(request: Request):
    body = await request.json()
    credential = body.get("credential") or body.get("id_token") or body.get("token")
    if credential:
        user = await _verify_google_credential(credential)
        return _issue_session(user)

    return _issue_session(_verify_local_login(body))

@app.post("/api/auth/google-dev")
async def auth_google_dev(request: Request):
    body = await request.json()
    return _issue_session(_verify_local_login(body))

@app.get("/api/auth/me")
async def auth_me(request: Request):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    user = SESSION_USERS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    return user

@app.post("/api/insights")
async def insights_proxy(request: Request):
    try:
        body = await request.json()
        if not OPENAI_API_KEY:
            return {"choices": [{"message": {"content": f"[FROID-IA local] {body.get('messages', [{}])[-1].get('content', 'Sem resposta.')}"}}]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": body.get("model", OPENAI_MODEL), "messages": body.get("messages", []), "temperature": 0.4, "max_tokens": 700}
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
    """Endpoint de transcrição vocal com fallback local para uso clínico e testes."""
    body = await request.json()
    fallback_text = body.get("fallback_text") or body.get("text") or ""
    audio_bytes = _decode_audio_bytes(body)
    transcript = await _transcribe_with_openai(audio_bytes, fallback_text)
    return {
        "status": "ok" if transcript else "mock",
        "text": transcript or fallback_text,
        "provider": "openai-whisper" if OPENAI_API_KEY and audio_bytes else "local-fallback",
    }
