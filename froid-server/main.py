import asyncio
import base64
import asyncio
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import secrets
import uuid
from typing import Dict
from urllib.parse import quote
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


def _load_local_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8-sig") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip().lstrip("\ufeff")
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


_load_local_env()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")
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
PATIENTS: Dict[str, dict] = {}
PATIENTS_BY_CONTACT: Dict[str, str] = {}
SESSION_INVITES: Dict[str, dict] = {}
CONSENT_LEDGER: list[dict] = []

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

    async def connect(self, websocket: WebSocket, session_id: str) -> str:
        await websocket.accept()
        connection_id = secrets.token_urlsafe(12)
        self.active_sessions[session_id] = {
            "connection_id": connection_id,
            "ws": websocket,
            "state": SessionState(session_id=session_id),
        }
        return connection_id

    def is_current(self, session_id: str, connection_id: str) -> bool:
        entry = self.active_sessions.get(session_id)
        return bool(entry and entry.get("connection_id") == connection_id)

    def disconnect(self, session_id: str, connection_id: str | None = None):
        entry = self.active_sessions.get(session_id)
        if entry and (connection_id is None or entry.get("connection_id") == connection_id):
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


def _audio_filename(body: dict) -> str:
    filename = (body.get("filename") or "").strip()
    if filename and "." in filename and "/" not in filename and "\\" not in filename:
        return filename

    mime_type = (body.get("mime_type") or "").lower()
    if "mp4" in mime_type or "m4a" in mime_type:
        ext = "m4a"
    elif "mpeg" in mime_type or "mp3" in mime_type:
        ext = "mp3"
    elif "wav" in mime_type:
        ext = "wav"
    elif "ogg" in mime_type:
        ext = "ogg"
    else:
        ext = "webm"
    return f"froid-session.{ext}"


def _limit_words(text: str, max_words: int) -> str:
    return " ".join(str(text or "").split()[:max_words]).strip()


def _transcribe_sync(audio_bytes: bytes, filename: str, prompt: str = "") -> str:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    kwargs = {
        "model": OPENAI_TRANSCRIBE_MODEL,
        "file": audio_file,
        "language": "pt",
        "response_format": "json",
        "temperature": 0,
    }
    if prompt:
        kwargs["prompt"] = prompt
    if OPENAI_TRANSCRIBE_MODEL.startswith("gpt-4o"):
        kwargs["include"] = ["logprobs"]

    response = client.audio.transcriptions.create(**kwargs)
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        return str(response.get("text") or "").strip()
    text = getattr(response, "text", None)
    return text.strip() if isinstance(text, str) else ""


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digits_only(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _patient_contact_key(email: str = "", phone: str = "") -> str:
    normalized_email = _normalize_email(email)
    normalized_phone = _digits_only(phone)
    if normalized_email:
        return f"email:{normalized_email}"
    if normalized_phone:
        return f"phone:{normalized_phone}"
    return ""


def _public_invite_url(base_url: str, token: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        base = os.getenv("FROID_PUBLIC_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/#/convite/{token}"


def _consent_hash(payload: dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_money_cents(value) -> int:
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(round(value * 100)))
    text = str(value or "").strip()
    if not text:
        return 0
    text = text.replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return max(0, int(round(float(text) * 100)))
    except Exception:
        return 0


def _format_brl(cents: int) -> str:
    cents = max(0, int(cents or 0))
    reais = cents // 100
    centavos = cents % 100
    return f"R$ {reais},{centavos:02d}"


def _build_whatsapp_message(invite: dict) -> str:
    payment = invite.get("payment") or {}
    patient_name = invite.get("patient_name") or "paciente"
    is_known = bool(invite.get("patient_known"))
    lines = [
        f"Ola, {patient_name}. Voce recebeu um convite para uma sessao FROID.",
        f"Sessao: {invite.get('session_id')}",
    ]
    if is_known:
        lines.append(
            "Seu cadastro ja consta no FROID. Use o link abaixo para confirmar o convite e seguir para a sessao:"
        )
    else:
        lines.append(
            "Use o link abaixo para concluir seu cadastro, aceitar os termos LGPD e seguir para a sessao:"
        )
    lines.append(str(invite.get("invite_url") or ""))
    if payment.get("session_value_brl"):
        lines.append(f"Valor da sessao: {payment.get('session_value_brl')}.")
    if payment.get("mode") == "package":
        lines.append(
            f"Formato financeiro: pacote com {payment.get('package_sessions') or 0} sessoes previamente acertadas."
        )
        if payment.get("package_total_brl"):
            lines.append(f"Valor total do pacote: {payment.get('package_total_brl')}.")
    elif payment.get("mode") == "single":
        lines.append("Formato financeiro: sessao avulsa.")
        if payment.get("pix_code"):
            lines.append(f"PIX copia e cola: {payment.get('pix_code')}")
    lines.append("Antes da sessao, confirme seu cadastro e aceite os termos LGPD no link.")
    return "\n".join(lines)


async def _transcribe_with_openai(
    audio_bytes: bytes,
    fallback_text: str = "",
    filename: str = "froid-session.webm",
    prompt: str = "",
) -> tuple[str, str]:
    if not audio_bytes:
        return fallback_text, ""
    if not OPENAI_API_KEY:
        return fallback_text, "OPENAI_API_KEY ausente no backend"
    try:
        transcript = await asyncio.to_thread(
            _transcribe_sync,
            audio_bytes,
            filename,
            prompt,
        )
        if transcript:
            return transcript, ""
    except Exception as exc:
        return fallback_text, str(exc)
    return fallback_text, ""


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


async def froid_stream_loop(session_id: str, connection_id: str):
    entry = manager.active_sessions.get(session_id)
    if not entry: return
    state: SessionState = entry["state"]
    while manager.is_current(session_id, connection_id):
        voice_12 = MockBiometricStream.generate_voice_spectral()
        facs_flags, facs_details = MockBiometricStream.generate_facs_dissonance()
        payload = state.process_tick(voice_12, facs_flags, facs_details)
        await manager.broadcast_payload(session_id, payload)
        await asyncio.sleep(0.5)

@app.websocket("/ws/fusion/{session_id}")
async def websocket_fusion(websocket: WebSocket, session_id: str):
    connection_id = await manager.connect(websocket, session_id)
    task = asyncio.create_task(froid_stream_loop(session_id, connection_id))
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping": await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(session_id, connection_id); task.cancel()
    except Exception:
        manager.disconnect(session_id, connection_id); task.cancel()

@app.get("/health")
def health(): return {"status": "ok", "active_sessions": len(manager.active_sessions)}

@app.post("/session/create")
def create_session(): return {"session_id": str(uuid.uuid4())}

@app.post("/api/session-invites")
async def create_session_invite(request: Request):
    body = await request.json()
    patient_name = str(body.get("patient_name") or "").strip()
    patient_email = _normalize_email(body.get("patient_email") or "")
    patient_phone = _digits_only(body.get("patient_phone") or "")
    payment_mode = str(body.get("payment_mode") or "").strip().lower()
    pix_code = str(body.get("pix_code") or "").strip()
    package_sessions = int(body.get("package_sessions") or 0)
    session_value_cents = _parse_money_cents(
        body.get("session_value_cents")
        if body.get("session_value_cents") is not None
        else body.get("session_value")
    )
    session_id = str(body.get("session_id") or f"froid-{uuid.uuid4().hex[:12]}")

    if not patient_name:
        raise HTTPException(status_code=400, detail="Nome do paciente obrigatorio")
    if not patient_email and not patient_phone:
        raise HTTPException(status_code=400, detail="Informe email ou WhatsApp do paciente")
    if payment_mode not in {"package", "single"}:
        raise HTTPException(status_code=400, detail="payment_mode deve ser package ou single")
    if session_value_cents <= 0:
        raise HTTPException(status_code=400, detail="Informe o valor da sessao")
    if payment_mode == "package" and package_sessions <= 0:
        raise HTTPException(status_code=400, detail="Informe o numero de sessoes do pacote")
    if payment_mode == "single" and not pix_code:
        raise HTTPException(status_code=400, detail="Codigo PIX obrigatorio para sessao avulsa")

    contact_key = _patient_contact_key(patient_email, patient_phone)
    known_patient_id = PATIENTS_BY_CONTACT.get(contact_key)
    token = secrets.token_urlsafe(24)
    invite_url = _public_invite_url(body.get("base_url") or "", token)
    now = _utc_now_iso()
    package_total_cents = (
        session_value_cents * package_sessions if payment_mode == "package" else session_value_cents
    )
    invite = {
        "id": str(uuid.uuid4()),
        "token": token,
        "session_id": session_id,
        "status": "pending",
        "patient_id": known_patient_id,
        "patient_known": bool(known_patient_id),
        "patient_name": patient_name,
        "patient_email": patient_email,
        "patient_phone": patient_phone,
        "payment": {
            "mode": payment_mode,
            "package_sessions": package_sessions if payment_mode == "package" else 0,
            "session_value_cents": session_value_cents,
            "session_value_brl": _format_brl(session_value_cents),
            "package_total_cents": package_total_cents,
            "package_total_brl": _format_brl(package_total_cents),
            "pix_code": pix_code if payment_mode == "single" else "",
            "payment_status": "prearranged" if payment_mode == "package" else "pending_pix",
        },
        "invite_url": invite_url,
        "created_at": now,
        "expires_at": body.get("expires_at") or "",
        "accepted_at": "",
    }
    invite["whatsapp_message"] = _build_whatsapp_message(invite)
    invite["whatsapp_url"] = (
        f"https://wa.me/{patient_phone}?text={quote(invite['whatsapp_message'])}"
        if patient_phone
        else ""
    )
    SESSION_INVITES[token] = invite
    return invite


@app.get("/api/session-invites/{token}")
async def get_session_invite(token: str):
    invite = SESSION_INVITES.get(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Convite nao encontrado")
    return invite


@app.post("/api/session-invites/{token}/accept")
async def accept_session_invite(token: str, request: Request):
    invite = SESSION_INVITES.get(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Convite nao encontrado")
    if invite.get("status") == "accepted":
        return invite

    body = await request.json()
    patient_name = str(body.get("name") or invite.get("patient_name") or "").strip()
    patient_email = _normalize_email(body.get("email") or invite.get("patient_email") or "")
    patient_phone = _digits_only(body.get("phone") or invite.get("patient_phone") or "")
    document = _digits_only(body.get("document") or "")
    birth_date = str(body.get("birth_date") or "").strip()
    consent = body.get("consent") or {}

    required_consents = [
        "terms_of_use",
        "privacy_policy",
        "sensitive_data_processing",
        "audio_video_processing",
    ]
    missing = [key for key in required_consents if consent.get(key) is not True]
    if missing:
        raise HTTPException(status_code=400, detail=f"Consentimentos obrigatorios ausentes: {', '.join(missing)}")
    if not patient_name:
        raise HTTPException(status_code=400, detail="Nome do paciente obrigatorio")
    if not patient_email and not patient_phone:
        raise HTTPException(status_code=400, detail="Informe email ou WhatsApp do paciente")

    contact_key = _patient_contact_key(patient_email, patient_phone)
    patient_id = invite.get("patient_id") or PATIENTS_BY_CONTACT.get(contact_key) or str(uuid.uuid4())
    now = _utc_now_iso()
    patient = {
        "id": patient_id,
        "name": patient_name,
        "email": patient_email,
        "phone": patient_phone,
        "document": document,
        "birth_date": birth_date,
        "created_at": PATIENTS.get(patient_id, {}).get("created_at") or now,
        "updated_at": now,
        "lgpd_consent_version": "FROID-LGPD-v1.0",
        "lgpd_consent_at": now,
    }
    PATIENTS[patient_id] = patient
    if contact_key:
        PATIENTS_BY_CONTACT[contact_key] = patient_id

    ledger_payload = {
        "patient_id": patient_id,
        "invite_id": invite.get("id"),
        "session_id": invite.get("session_id"),
        "consent": consent,
        "version": "FROID-LGPD-v1.0",
        "accepted_at": now,
        "remote_addr": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", ""),
    }
    ledger_entry = {
        **ledger_payload,
        "hash": _consent_hash(ledger_payload),
    }
    CONSENT_LEDGER.append(ledger_entry)

    invite.update(
        {
            "status": "accepted",
            "patient_id": patient_id,
            "patient_known": True,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "patient_phone": patient_phone,
            "accepted_at": now,
            "consent_hash": ledger_entry["hash"],
            "session_url": f"/session/{invite.get('session_id')}",
        }
    )
    return {
        **invite,
        "patient": patient,
        "consent": ledger_entry,
    }

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
    filename = _audio_filename(body)
    prompt = body.get("prompt") or (
        "Transcreva literalmente em portugues do Brasil com pontuacao clinica clara. "
        "Vocabulario obrigatorio: FROID deve ser grafado FROID, nunca Freud; IPM, IDM, "
        "biomarcadores, sub-harmonicos, bioacustica, dissonancias, paciente e profissional."
    )
    transcript, error = await _transcribe_with_openai(
        audio_bytes,
        fallback_text,
        filename,
        prompt,
    )
    provider = (
        f"openai-{OPENAI_TRANSCRIBE_MODEL}"
        if OPENAI_API_KEY and audio_bytes and not error
        else "local-fallback"
    )
    return {
        "status": "ok" if transcript and not error else "empty" if not error else "error",
        "text": transcript or fallback_text,
        "provider": provider,
        "model": OPENAI_TRANSCRIBE_MODEL,
        "filename": filename,
        "error": error,
    }

@app.post("/api/session-summary")
async def session_summary(request: Request):
    body = await request.json()
    transcript = str(body.get("transcript") or "").strip()
    start_minute = int(body.get("start_minute") or 0)
    end_minute = int(body.get("end_minute") or start_minute + 10)

    if not transcript:
        return {
            "status": "empty",
            "theme": "Sem fala transcrita",
            "summary": "Nenhuma fala foi transcrita neste intervalo.",
            "start_minute": start_minute,
            "end_minute": end_minute,
            "model": OPENAI_MODEL,
        }

    fallback = {
        "status": "fallback",
        "theme": "Tema em apuração",
        "summary": _limit_words(transcript, 200),
        "start_minute": start_minute,
        "end_minute": end_minute,
        "model": OPENAI_MODEL,
    }

    if not OPENAI_API_KEY:
        return fallback

    prompt = (
        "Analise a transcricao clinica abaixo e responda somente em JSON valido "
        "com as chaves theme e summary. theme deve ser resultado direto do assunto tratado, "
        "nao pode vir de lista predefinida e deve ter no maximo 5 palavras. "
        "summary deve ter entre 100 e 200 palavras, em portugues do Brasil, sem diagnostico, "
        "sem inventar fatos e preservando apenas o que foi falado no intervalo. "
        "Se a transcricao tiver menos conteudo do que 100 palavras, resuma apenas o material real disponivel. "
        f"Intervalo: {start_minute}-{end_minute} minutos.\n\nTranscricao:\n{transcript}"
    )

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Voce resume conversas clinicas para apoio ao profissional, sem diagnosticar nem inventar conteudo.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 520,
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        parsed = _parse_json_object(content)
        theme = _limit_words(str(parsed.get("theme") or fallback["theme"]).strip(), 5)
        summary_text = str(parsed.get("summary") or fallback["summary"]).strip()
        return {
            "status": "ok",
            "theme": theme,
            "summary": _limit_words(summary_text, 200),
            "start_minute": start_minute,
            "end_minute": end_minute,
            "model": OPENAI_MODEL,
        }
    except Exception:
        return fallback
