import asyncio
import base64
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
import unicodedata
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urlencode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from froid_core import SessionState, MockBiometricStream
import froid_f0
import froid_mailer
import froid_voice
from froid_metrics_engine import calculate_report_metrics
from tenant_access import (
    AccessContext,
    VALID_MODES as TENANT_AUTHORIZATION_MODES,
    VALID_ROLES as TENANT_ROLES,
    decide,
    should_block,
)
from tenant_store import (
    TenantStore,
    organization_id_for_profile as tenant_organization_id_for_profile,
    organization_type_for_account as tenant_organization_type_for_account,
    stable_uuid,
)
import explica_embeddings
import nr1_explica
import froid_validation
import lgpd_registry
import nr1_compliance
import nr1_effectiveness
from subscriptions import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    AUTO_REPLENISH_TERMS_VERSION,
    PAID_SESSION_STATUSES,
    SESSION_PACKAGES,
    SUPPORTED_BILLING_CURRENCIES,
    SUBSCRIPTION_PLANS,
    StripeSignatureError,
    public_plan_catalog,
    public_package_catalog,
    verify_stripe_event,
    package_price,
)
from secure_tokens import (
    TOKEN_FIELDS, TextCipher, TokenCipher, TokenEncryptionError,
)
from localization import (
    normalize_session_locale,
    session_language,
    summary_prompt,
    summary_system_prompt,
    transcription_prompt,
)
from legal_documents import (
    LEGAL_DOCUMENT_VERSION,
    public_legal_catalog,
    required_document_keys,
)
import httpx

app = FastAPI(title="FROID Fusion Server", version="3.0.0")
LOGGER = logging.getLogger("froid.persistence")
# ``uvicorn.access`` uses a formatter that requires Uvicorn's internal
# five-item request tuple. Audit events are ordinary structured messages, so
# they must use the general server logger instead.
AUDIT_LOGGER = logging.getLogger("uvicorn.error")
STREAM_LOGGER = logging.getLogger("froid.stream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "FROID_ALLOWED_ORIGINS",
            "https://www.froid.com.br,https://froid.com.br,http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["Content-Disposition"],
    max_age=600,
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FROID_EXPLICA_MODEL = os.getenv("FROID_EXPLICA_MODEL", "gemini-1.5-pro")
FROID_CHROMA_PATH = os.getenv("FROID_CHROMA_PATH", "/data/chroma_db")
FROID_CHROMA_COLLECTION = os.getenv(
    "FROID_CHROMA_COLLECTION",
    "froid_clinical_knowledge",
)
FROID_APPROVED_KNOWLEDGE_DIR = os.getenv(
    "FROID_APPROVED_KNOWLEDGE_DIR",
    os.path.join(os.path.dirname(__file__), "knowledge", "approved"),
)
FROID_DUCKDB_PATH = os.getenv(
    "FROID_DUCKDB_PATH",
    "/data/datamart_anonymous_v3.duckdb",
)
FROID_ALGORITHM_VERSION = os.getenv("FROID_ALGORITHM_VERSION", app.version)
FROID_ANALYTICS_MIN_K = int(os.getenv("FROID_ANALYTICS_MIN_K", "50") or "50")
FROID_ANALYTICS_MAX_SUPPRESSION_RATIO = min(
    0.10,
    max(0.0, float(os.getenv("FROID_ANALYTICS_MAX_SUPPRESSION_RATIO", "0.10") or "0.10")),
)
FROID_DATAMART_PSEUDONYM_KEY = os.getenv(
    "FROID_DATAMART_PSEUDONYM_KEY", ""
).strip()
# Minimo de 32 bytes, a mesma regua que FROID_LEGAL_AUDIT_HMAC_KEY sempre teve.
#
# A inconsistencia era real e tinha consequencia: qualquer string nao-vazia
# passava por "configurada", e esta chave e a que sustenta o anonimato do
# trabalhador no NR-1 — e o HMAC da matricula. Chave curta se reconstroi por
# forca bruta a partir da folha de pagamento que o empregador ja tem, e ai o
# pseudonimo deixa de pseudonimizar. "Existe" nao era resposta suficiente.
FROID_DATAMART_PSEUDONYM_KEY_FORTE = (
    len(FROID_DATAMART_PSEUDONYM_KEY.encode("utf-8")) >= 32
)
FROID_TURN_URLS = [
    url.strip()
    for url in os.getenv("FROID_TURN_URLS", "").split(",")
    if url.strip().startswith(("turn:", "turns:"))
]
FROID_TURN_SECRET = os.getenv("FROID_TURN_SECRET", "").strip()
FROID_TURN_CREDENTIAL_TTL_SECONDS = max(
    300,
    min(86400, int(os.getenv("FROID_TURN_CREDENTIAL_TTL_SECONDS", "3600") or "3600")),
)
FROID_ICE_TRANSPORT_POLICY = os.getenv(
    "FROID_ICE_TRANSPORT_POLICY", "all"
).strip().lower()
if FROID_ICE_TRANSPORT_POLICY not in {"all", "relay"}:
    FROID_ICE_TRANSPORT_POLICY = "all"
FROID_REQUIRE_TURN = os.getenv("FROID_REQUIRE_TURN", "false").strip().lower() == "true"
FROID_TURN_PROBE_TTL_SECONDS = max(
    10, min(600, int(os.getenv("FROID_TURN_PROBE_TTL_SECONDS", "60") or "60"))
)
# Resultado da ultima sonda: (momento, alcancavel, detalhe).
_TURN_PROBE_CACHE: tuple[float, bool, str] = (0.0, False, "ainda nao sondado")


def _turn_endpoints() -> list[tuple[str, int]]:
    """Host e porta de cada URL de TURN configurada.

    `turn:200.0.0.1:3478?transport=udp` -> ("200.0.0.1", 3478). Aceita tambem
    a forma sem porta, que por RFC vale 3478.
    """
    destinos: list[tuple[str, int]] = []
    for url in FROID_TURN_URLS:
        corpo = url.split(":", 1)[1] if ":" in url else url
        corpo = corpo.split("?", 1)[0]
        if corpo.count(":") == 1:
            host, _, porta = corpo.partition(":")
        else:
            host, porta = corpo, "3478"
        host = host.strip("[]").strip()
        try:
            destinos.append((host, int(porta)))
        except ValueError:
            continue
    return destinos


def _probe_turn_once(host: str, porta: int, timeout: float = 1.5) -> bool:
    """Pergunta ao servidor TURN se ele esta vivo, e espera a resposta.

    STUN Binding Request cru: 20 bytes de cabecalho, sem autenticacao. O
    coturn responde a isso mesmo com `use-auth-secret` ligado — autenticacao so
    e exigida para alocar relay, nao para o binding. Se nada volta, ninguem
    atende naquela porta.

    Existe porque `turn_configured` conferia apenas se as variaveis estavam
    preenchidas. Numa consulta real, elas estavam — e o contêiner do coturn
    nunca havia subido, porque o servico tem `profiles: ["webrtc"]` no compose
    e nao entra em `docker compose up` comum. A checagem dizia "configurado" e
    a chamada nao conectava; nada no sistema ligava as duas coisas.
    """
    transacao = secrets.token_bytes(12)
    # tipo=0x0001 (Binding Request), comprimento=0, magic cookie, transacao.
    # Escrito em hexadecimal de proposito: literal de byte com escapes e
    # exatamente o que se corrompe quando este arquivo e editado por
    # script — e foi o que aconteceu ao escrever esta funcao, no mesmo dia
    # em que a varredura de bytes de controle nasceu. bytes.fromhex nao tem
    # escape nenhum, entao nao ha o que corromper.
    #   0001 = Binding Request | 0000 = comprimento | 2112a442 = magic cookie
    pedido = bytes.fromhex("00010000" "2112a442") + transacao
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(pedido, (host, porta))
        resposta, _ = sock.recvfrom(1024)
        # 0x0101 = Binding Success. Conferir a transacao impede aceitar
        # pacote perdido de outra conversa como se fosse resposta nossa.
        return (
            len(resposta) >= 20
            and resposta[0:2] == bytes.fromhex("0101")
            and resposta[8:20] == transacao
        )
    except Exception:
        return False
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def turn_reachable() -> tuple[bool, str]:
    """O TURN responde? Com cache curto, para nao sondar a cada /health."""
    global _TURN_PROBE_CACHE
    if not FROID_TURN_URLS or not FROID_TURN_SECRET:
        return False, "TURN nao configurado"
    agora = time.time()
    quando, alcancavel, detalhe = _TURN_PROBE_CACHE
    if agora - quando < FROID_TURN_PROBE_TTL_SECONDS:
        return alcancavel, detalhe
    destinos = _turn_endpoints()
    if not destinos:
        _TURN_PROBE_CACHE = (agora, False, "nenhuma URL de TURN interpretavel")
        return _TURN_PROBE_CACHE[1], _TURN_PROBE_CACHE[2]
    respondendo = [f"{h}:{p}" for h, p in destinos if _probe_turn_once(h, p)]
    if respondendo:
        _TURN_PROBE_CACHE = (agora, True, f"responde: {', '.join(respondendo)}")
    else:
        alvos = ", ".join(f"{h}:{p}" for h, p in destinos)
        _TURN_PROBE_CACHE = (
            agora,
            False,
            f"nenhum servidor TURN respondeu ao STUN binding em {alvos} — "
            "o contêiner do relay pode não estar no ar (o serviço froid-turn "
            "tem profiles:[webrtc] e não sobe em 'docker compose up' comum), "
            "ou as portas 3478/udp e 49160-49200/udp podem estar fechadas",
        )
    return _TURN_PROBE_CACHE[1], _TURN_PROBE_CACHE[2]

FROID_SESSION_REPORTS_PATH = os.getenv(
    "FROID_SESSION_REPORTS_PATH",
    "/data/session_reports.json",
)
FROID_IDENTITY_STATE_PATH = os.getenv(
    "FROID_IDENTITY_STATE_PATH",
    "/data/identity_state.json",
)
FROID_LEGACY_REPORT_OWNER = os.getenv(
    "FROID_LEGACY_REPORT_OWNER",
    "fbenhayon@gmail.com",
)
FROID_ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("FROID_ADMIN_EMAILS", "fbenhayon@gmail.com").split(",")
    if email.strip()
}
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_AUTH_CLIENT_ID = (
    os.getenv("GOOGLE_AUTH_CLIENT_ID", "").strip() or GOOGLE_CLIENT_ID
)
GOOGLE_CALENDAR_CLIENT_ID = (
    os.getenv("GOOGLE_CALENDAR_CLIENT_ID", "").strip() or GOOGLE_CLIENT_ID
)
GOOGLE_CALENDAR_CLIENT_SECRET = (
    os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip() or GOOGLE_CLIENT_SECRET
)
GOOGLE_AUTH_DEV_FALLBACK = os.getenv("GOOGLE_AUTH_DEV_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}
GOOGLE_CALENDAR_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
]
FROID_LOCAL_AUTH_PASSWORD = os.getenv("FROID_LOCAL_AUTH_PASSWORD", "")
FROID_LOCAL_AUTH_EMAILS = {
    email.strip().lower()
    for email in os.getenv("FROID_LOCAL_AUTH_EMAILS", "").split(",")
    if email.strip()
}
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "brl")
STRIPE_SUBSCRIPTION_PRICE_IDS = {
    code: os.getenv(f"STRIPE_PRICE_{code.upper()}", "").strip()
    for code in SESSION_PACKAGES
}
FROID_SUBSCRIPTIONS_REQUIRED = os.getenv(
    "FROID_SUBSCRIPTIONS_REQUIRED", "false"
).lower() in {"1", "true", "yes", "on"}
FROID_PROFESSIONAL_APPROVAL_REQUIRED = os.getenv(
    "FROID_PROFESSIONAL_APPROVAL_REQUIRED", "false"
).lower() in {"1", "true", "yes", "on"}
# Cadastro proprio (sem Google). Desligar aqui fecha /api/auth/register sem
# derrubar quem ja tem senha: o login continua valendo.
FROID_REGISTRATION_ENABLED = os.getenv(
    "FROID_REGISTRATION_ENABLED", "true"
).lower() in {"1", "true", "yes", "on"}
# Piso de 6 por decisao de produto: cadastro curto perde menos gente na porta.
# O que sustenta a credencial nao e o comprimento e sim o resto do conjunto —
# e-mail verificado antes de a conta valer, PBKDF2 com 120k iteracoes, limite
# de 10 tentativas por e-mail a cada 15 min e exigencia de letra e numero, que
# tira do caminho justamente "123456" e "senha".
FROID_PASSWORD_MIN_LENGTH = max(
    6, int(os.getenv("FROID_PASSWORD_MIN_LENGTH", "6") or "6")
)
FROID_EMAIL_VERIFICATION_TTL_SECONDS = max(
    900, int(os.getenv("FROID_EMAIL_VERIFICATION_TTL_SECONDS", "86400") or "86400")
)
FROID_PASSWORD_RESET_TTL_SECONDS = max(
    300, int(os.getenv("FROID_PASSWORD_RESET_TTL_SECONDS", "3600") or "3600")
)
FROID_ALLOW_LOCAL_BILLING_FALLBACK = os.getenv(
    "FROID_ALLOW_LOCAL_BILLING_FALLBACK", "false"
).lower() in {"1", "true", "yes", "on"}
# Sessoes de cortesia concedidas no cadastro, para o profissional ou a clinica
# conhecer o produto antes de contratar. Ao esgotar, o acesso volta a seleccao
# de pacotes.
#
# A concessao acontece UMA vez, na criacao do perfil. Regravar o cadastro nao
# renova nada: total_sessions e sempre lido do perfil existente.
#
# Cortesia nao acumula pendencia. Um cliente pagante que fica sem saldo tem a
# sessao entregue e registrada como pendente de acerto — promessa publicada em
# precos.html e que continua valendo para ele. Quem ainda nao comprou nada nao
# tem com o que acertar depois, entao o teste para no numero combinado em vez de
# virar credito nao cobravel.
try:
    FROID_TRIAL_SESSIONS = max(0, int(os.getenv("FROID_TRIAL_SESSIONS", "5")))
except ValueError:
    FROID_TRIAL_SESSIONS = 5
FROID_TRIAL_PLAN_ID = "trial-froid"
FROID_TRIAL_CONTACT_EMAIL = "froid@froid.com.br"

# Teto de sessoes entregues sem credito (pendentes de acerto). Ao atingi-lo, o
# profissional/clinica nao inicia novas sessoes ate o administrador regularizar.
# A sessao ja realizada nunca e recusada nem descartada por causa deste limite.
try:
    FROID_MAX_PENDING_SETTLEMENTS = max(
        1, int(os.getenv("FROID_MAX_PENDING_SETTLEMENTS", "10"))
    )
except ValueError:
    FROID_MAX_PENDING_SETTLEMENTS = 10
FROID_LEGAL_ACCEPTANCE_REQUIRED = os.getenv(
    "FROID_LEGAL_ACCEPTANCE_REQUIRED", "false"
).lower() in {"1", "true", "yes", "on"}
FROID_LEGAL_ACCEPTANCE_REQUIRED_BY_JURISDICTION = {
    jurisdiction: os.getenv(
        f"FROID_LEGAL_ACCEPTANCE_REQUIRED_{jurisdiction}",
        "true" if FROID_LEGAL_ACCEPTANCE_REQUIRED else "false",
    ).lower() in {"1", "true", "yes", "on"}
    for jurisdiction in ("BR", "ES", "FR", "US")
}
FROID_LEGAL_AUDIT_HMAC_KEY = os.getenv(
    "FROID_LEGAL_AUDIT_HMAC_KEY", ""
).strip()
TOKEN_CIPHER = TokenCipher.from_csv(os.getenv("FROID_TOKEN_ENCRYPTION_KEYS", ""))
CLINICAL_TEXT_CIPHER = TextCipher.from_csv(
    os.getenv("FROID_CLINICAL_RECORD_ENCRYPTION_KEYS", "")
)
TENANT_STORE = TenantStore.from_env()
FROID_TENANT_AUTHORIZATION_MODE = os.getenv(
    "FROID_TENANT_AUTHORIZATION_MODE", "off"
).strip().lower()
FROID_TENANT_ENFORCEMENT_ORGANIZATIONS = {
    organization_id.strip()
    for organization_id in os.getenv(
        "FROID_TENANT_ENFORCEMENT_ORGANIZATIONS", ""
    ).split(",")
    if organization_id.strip()
}
FROID_SHARED_CREDITS_MODE = os.getenv(
    "FROID_SHARED_CREDITS_MODE", "off"
).strip().lower()
FROID_SHARED_CREDITS_ORGANIZATIONS = {
    organization_id.strip()
    for organization_id in os.getenv(
        "FROID_SHARED_CREDITS_ORGANIZATIONS", ""
    ).split(",")
    if organization_id.strip()
}
if FROID_TENANT_AUTHORIZATION_MODE not in TENANT_AUTHORIZATION_MODES:
    raise RuntimeError(
        "FROID_TENANT_AUTHORIZATION_MODE must be off, observe or enforce"
    )
if FROID_TENANT_AUTHORIZATION_MODE == "enforce" and not TENANT_STORE.enabled:
    raise RuntimeError(
        "Tenant authorization enforcement requires FROID_PERSISTENCE_MODE=dual"
    )
if (
    FROID_TENANT_AUTHORIZATION_MODE == "enforce"
    and not FROID_TENANT_ENFORCEMENT_ORGANIZATIONS
):
    raise RuntimeError(
        "Enforcement requires at least one organization in "
        "FROID_TENANT_ENFORCEMENT_ORGANIZATIONS"
    )
if FROID_SHARED_CREDITS_MODE not in TENANT_AUTHORIZATION_MODES:
    raise RuntimeError("FROID_SHARED_CREDITS_MODE must be off, observe or enforce")
if FROID_SHARED_CREDITS_MODE == "enforce" and (
    not TENANT_STORE.enabled
    or not TENANT_STORE.runtime_database_url
    or not FROID_SHARED_CREDITS_ORGANIZATIONS
):
    raise RuntimeError(
        "Shared credit enforcement requires dual persistence, runtime database "
        "URL and FROID_SHARED_CREDITS_ORGANIZATIONS"
    )

SESSION_USERS = {}
FROID_SESSION_TOKEN_TTL_SECONDS = max(
    300, int(os.getenv("FROID_SESSION_TOKEN_TTL_SECONDS", "28800") or "28800")
)
PATIENT_PORTAL_SESSIONS: Dict[str, dict] = {}
PATIENT_LOGIN_ATTEMPTS: Dict[str, list[float]] = {}

# Baldes genéricos de limitação de taxa (em memória, por processo). Suficiente
# para o servidor único atual; ao escalar para múltiplos workers deve migrar
# para store compartilhado (ver auditoria de segurança).
RATE_LIMIT_BUCKETS: Dict[str, Dict[str, list[float]]] = {}


def _rate_limit_guard(
    bucket: str, key: str, max_hits: int, window_seconds: float, message: str
) -> None:
    """Levanta HTTP 429 se `key` exceder `max_hits` em `window_seconds`.

    Mitiga força bruta em autenticação e enxurradas nos endpoints de ingestão.
    """
    import time as _time

    now = _time.time()
    store = RATE_LIMIT_BUCKETS.setdefault(bucket, {})
    recent = [t for t in store.get(key, []) if t >= now - window_seconds]
    if len(recent) >= max_hits:
        raise HTTPException(status_code=429, detail=message)
    recent.append(now)
    store[key] = recent
    # Poda oportunista para o balde não crescer indefinidamente.
    if len(store) > 4096:
        for k in [k for k, v in store.items() if not v or v[-1] < now - window_seconds]:
            store.pop(k, None)


def _client_ip(request: Request) -> str:
    """IP do cliente considerando o proxy Caddy (X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
FROID_PATIENT_SESSION_TTL_SECONDS = max(
    900, int(os.getenv("FROID_PATIENT_SESSION_TTL_SECONDS", "7200") or "7200")
)
PROFESSIONAL_PROFILES: Dict[str, dict] = {}
# Cofre de credenciais de quem NAO entra pelo Google. Fica separado do
# perfil de proposito: o perfil e cadastro comercial e clinico, e some
# quando a pessoa refaz o onboarding; a credencial e identidade e nao pode
# ser reescrita por um POST de formulario.
PROFESSIONAL_CREDENTIALS: Dict[str, dict] = {}
PATIENTS: Dict[str, dict] = {}
PATIENTS_BY_CONTACT: Dict[str, str] = {}
SESSION_INVITES: Dict[str, dict] = {}
SESSION_OWNERS: Dict[str, str] = {}
SESSION_ORGANIZATIONS: Dict[str, str] = {}
CONSENT_LEDGER: list[dict] = []
PATIENT_SESSION_ENTRIES: Dict[str, list[dict]] = {}
SESSION_EVENTS: list[dict] = []
SESSION_EVENT_COUNTER = 0
GOOGLE_CALENDAR_CONNECTIONS: Dict[str, dict] = {}
GOOGLE_CALENDAR_OAUTH_STATES: Dict[str, dict] = {}
CALENDAR_TOKEN_MIGRATION_REQUIRED = False
IDENTITY_STATE_LOCK = threading.Lock()


def _local_digits_only(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _local_normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _local_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _patient_contact_keys(patient: dict) -> list[str]:
    keys = []
    email = _local_normalize_email(patient.get("email") or "")
    phone = _local_digits_only(patient.get("phone") or "")
    document = _local_digits_only(patient.get("document") or "")
    if email:
        keys.append(f"email:{email}")
    if phone:
        keys.append(f"phone:{phone}")
    if document:
        keys.append(f"document:{document}")
    return keys


def _rebuild_patient_contact_index(
    patients: Dict[str, dict],
    persisted_index: Dict[str, str] | None = None,
) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for contact_key, patient_id in (persisted_index or {}).items():
        if contact_key and str(patient_id) in patients:
            index[str(contact_key)] = str(patient_id)
    for patient_id, patient in patients.items():
        if not isinstance(patient, dict):
            continue
        for contact_key in _patient_contact_keys(patient):
            index[contact_key] = str(patient_id)
    return index


def _load_identity_state() -> None:
    global PROFESSIONAL_PROFILES
    global PROFESSIONAL_CREDENTIALS
    global PATIENTS
    global PATIENTS_BY_CONTACT
    global SESSION_INVITES
    global SESSION_OWNERS
    global SESSION_ORGANIZATIONS
    global CONSENT_LEDGER
    global PATIENT_SESSION_ENTRIES
    global SESSION_EVENTS
    global SESSION_EVENT_COUNTER
    global GOOGLE_CALENDAR_CONNECTIONS
    global CALENDAR_TOKEN_MIGRATION_REQUIRED

    if not FROID_IDENTITY_STATE_PATH or not os.path.exists(FROID_IDENTITY_STATE_PATH):
        return
    try:
        with open(FROID_IDENTITY_STATE_PATH, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except Exception:
        return
    if not isinstance(state, dict):
        return

    raw_profiles = state.get("professional_profiles")
    if isinstance(raw_profiles, dict):
        PROFESSIONAL_PROFILES = {
            _local_normalize_email(email): profile
            for email, profile in raw_profiles.items()
            if _local_normalize_email(email) and isinstance(profile, dict)
        }

    raw_credentials = state.get("professional_credentials")
    if isinstance(raw_credentials, dict):
        PROFESSIONAL_CREDENTIALS = {
            _local_normalize_email(email): credential
            for email, credential in raw_credentials.items()
            if _local_normalize_email(email) and isinstance(credential, dict)
        }

    raw_patients = state.get("patients")
    if isinstance(raw_patients, dict):
        PATIENTS = {
            str(patient_id): patient
            for patient_id, patient in raw_patients.items()
            if patient_id and isinstance(patient, dict)
        }

    persisted_contact_index = state.get("patients_by_contact")
    PATIENTS_BY_CONTACT = _rebuild_patient_contact_index(
        PATIENTS,
        persisted_contact_index if isinstance(persisted_contact_index, dict) else {},
    )

    raw_invites = state.get("session_invites")
    raw_session_owners = state.get("session_owners")
    if isinstance(raw_session_owners, dict):
        SESSION_OWNERS = {
            str(session_id): _local_normalize_email(email)
            for session_id, email in raw_session_owners.items()
            if session_id and _local_normalize_email(email)
        }
    raw_session_organizations = state.get("session_organizations")
    if isinstance(raw_session_organizations, dict):
        SESSION_ORGANIZATIONS = {
            str(session_id): str(organization_id)
            for session_id, organization_id in raw_session_organizations.items()
            if session_id and organization_id
        }
    if isinstance(raw_invites, dict):
        SESSION_INVITES = {
            str(token): invite
            for token, invite in raw_invites.items()
            if token and isinstance(invite, dict)
        }
        for invite in SESSION_INVITES.values():
            session_id = str(invite.get("session_id") or "")
            owner_email = _local_normalize_email(invite.get("professional_email") or "")
            if session_id and owner_email:
                SESSION_OWNERS[session_id] = owner_email
            organization_id = str(invite.get("organization_id") or "")
            if session_id and organization_id:
                SESSION_ORGANIZATIONS[session_id] = organization_id

    raw_ledger = state.get("consent_ledger")
    if isinstance(raw_ledger, list):
        CONSENT_LEDGER = [item for item in raw_ledger if isinstance(item, dict)]

    raw_entries = state.get("patient_session_entries")
    if isinstance(raw_entries, dict):
        PATIENT_SESSION_ENTRIES = {
            str(session_id): [item for item in entries if isinstance(item, dict)]
            for session_id, entries in raw_entries.items()
            if isinstance(entries, list)
        }

    raw_events = state.get("session_events")
    if isinstance(raw_events, list):
        SESSION_EVENTS = [item for item in raw_events if isinstance(item, dict)][-500:]

    # ADMIN_AUDIT_EVENTS is now stored in PostgreSQL; not loaded into memory.

    max_event_id = max(
        [_local_int(event.get("id")) for event in SESSION_EVENTS if isinstance(event, dict)]
        or [0]
    )
    SESSION_EVENT_COUNTER = max(_local_int(state.get("session_event_counter")), max_event_id)

    raw_calendar_connections = state.get("google_calendar_connections")
    if isinstance(raw_calendar_connections, dict):
        GOOGLE_CALENDAR_CONNECTIONS = {}
        for email, connection in raw_calendar_connections.items():
            normalized_email = _local_normalize_email(email)
            if not normalized_email or not isinstance(connection, dict):
                continue
            has_plaintext = any(connection.get(field) for field in TOKEN_FIELDS)
            if TOKEN_CIPHER:
                try:
                    revealed = TOKEN_CIPHER.reveal(connection)
                    revealed.pop("token_storage_locked", None)
                    revealed.pop("token_storage_error", None)
                    GOOGLE_CALENDAR_CONNECTIONS[normalized_email] = revealed
                    CALENDAR_TOKEN_MIGRATION_REQUIRED = (
                        CALENDAR_TOKEN_MIGRATION_REQUIRED
                        or has_plaintext
                        or TOKEN_CIPHER.needs_rotation(connection)
                    )
                except TokenEncryptionError:
                    LOGGER.exception("Unable to decrypt stored Google OAuth tokens")
                    locked = {
                        key: value for key, value in connection.items()
                        if key not in TOKEN_FIELDS
                    }
                    locked["token_storage_locked"] = True
                    locked["token_storage_error"] = True
                    GOOGLE_CALENDAR_CONNECTIONS[normalized_email] = locked
            else:
                metadata = {
                    key: value for key, value in connection.items()
                    if key not in TOKEN_FIELDS
                }
                metadata["token_storage_locked"] = True
                GOOGLE_CALENDAR_CONNECTIONS[normalized_email] = metadata


def _identity_state_snapshot() -> dict:
    calendar_connections = {}
    for email, connection in GOOGLE_CALENDAR_CONNECTIONS.items():
        if TOKEN_CIPHER:
            calendar_connections[email] = TOKEN_CIPHER.protect(connection)
        else:
            calendar_connections[email] = {
                key: value for key, value in connection.items()
                if key not in TOKEN_FIELDS
            }
    return {
        "schema_version": "froid-identity-state-v1",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "professional_profiles": PROFESSIONAL_PROFILES,
        "professional_credentials": PROFESSIONAL_CREDENTIALS,
        "patients": PATIENTS,
        "patients_by_contact": PATIENTS_BY_CONTACT,
        "session_invites": SESSION_INVITES,
        "session_owners": SESSION_OWNERS,
        "session_organizations": SESSION_ORGANIZATIONS,
        "consent_ledger": CONSENT_LEDGER[-2000:],
        "patient_session_entries": PATIENT_SESSION_ENTRIES,
        "session_events": SESSION_EVENTS[-500:],
        "session_event_counter": SESSION_EVENT_COUNTER,
        "google_calendar_connections": calendar_connections,
    }


def _save_identity_state() -> None:
    if not FROID_IDENTITY_STATE_PATH:
        return
    with IDENTITY_STATE_LOCK:
        state_dir = os.path.dirname(FROID_IDENTITY_STATE_PATH) or "."
        os.makedirs(state_dir, exist_ok=True)
        tmp_path = f"{FROID_IDENTITY_STATE_PATH}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as state_file:
            json.dump(_identity_state_snapshot(), state_file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, FROID_IDENTITY_STATE_PATH)
        os.chmod(FROID_IDENTITY_STATE_PATH, 0o600)
    _mirror_legacy_state_to_postgres()


_load_identity_state()

KNOWLEDGE_BASE = {
    "froid_zonas": "As 12 Zonas de Percepcao FROID organizam padroes de desequilibrio facial-vocal e orientam a leitura clinica por temas, tensoes e dissonancias.",
    "ipm_velocimetro": "O IPM indica a intensidade ou energia global da sessao. Ele funciona como velocimetro emocional e nao define sozinho a direcao do desequilibrio.",
    "idm_direcao": "O IDM aponta a direcao do desequilibrio entre marcadores negativos e positivos, enquanto o IPM mede a energia global empregada.",
    "mfcc7_depressao": "MFCC7 elevado durante conteudos semanticamente negativos, associado a pausas, menor variacao de F0 e retardo psicomotor, contribui para risco depressivo.",
    "mfcc9_ansiedade": "MFCC9 em discurso neutro pode ter relacao inversa com ansiedade somatica; quedas acusticas podem indicar tensao autonoma latente.",
    "shimmer_bioacustico": "Shimmer no FROID e atualmente um indice proxy interno normalizado da variacao relativa do envelope RMS, nao uma medida em dB. Deve ser interpretado contra baseline individual, cortes temporais, Jitter proxy, F0, ZCR, energia, pausas, tema semantico e dissonancias; isoladamente nao define estado emocional.",
    "jitter_bioacustico": "Jitter no FROID e atualmente um indice proxy interno normalizado derivado de ZCR escalado, nao uma medida percentual normativa. Quando sustentado junto a Shimmer proxy, alteracoes de F0, pausas e tensao vocal, pode apoiar hipotese de instabilidade laringea ou carga autonomica.",
    "f0_bioacustico": "F0 e a frequencia fundamental da voz. Elevacoes, quedas ou reducao de variabilidade devem ser comparadas ao baseline de 60 segundos e ao contexto semantico da fala.",
    "zcr_bioacustico": "ZCR, taxa de cruzamento por zero, apoia leitura de aspereza, ruido, energia de alta frequencia e alteracoes acusticas quando combinado a MFCCs, F0, Jitter proxy e Shimmer proxy.",
    "ref_mfcc_davis_mermelstein": "Referencia cientifica: Davis e Mermelstein (1980) introduzem representacoes cepstrais em escala Mel para modelagem espectral da fala, fundamento conceitual dos MFCCs.",
    "ref_opensmile_eyben": "Referencia cientifica: Eyben, Wollmer e Schuller (2010) descrevem o openSMILE como toolkit para extracao de features acusticas em fala, musica e reconhecimento afetivo.",
    "ref_facs_ekman": "Referencia cientifica: Ekman, Friesen e Hager consolidam o Facial Action Coding System (FACS), base para codificacao de unidades de acao facial, intensidade e combinacoes expressivas.",
    "ref_praat_boersma": "Referencia cientifica: Boersma e Weenink/Praat sustentam analises acusticas como F0, Jitter, Shimmer e parametros fonatorios em fonetica computacional.",
    "ref_phq9_kroenke": "Referencia cientifica: Kroenke, Spitzer e Williams (2001) validam o PHQ-9 como medida breve de gravidade depressiva.",
    "ref_hamilton_hamd": "Referencia cientifica: Hamilton (1960) estabelece escala clinica para depressao, incluindo sintomas somaticos, retardo e ansiedade.",
    "ref_ymrs_young": "Referencia cientifica: Young, Biggs, Ziegler e Meyer (1978) apresentam a Young Mania Rating Scale para avaliacao de severidade maniforme.",
    "mania_ativacao": "A ativacao de mania acompanha pitch/F0 elevado, loudness, taxa acelerada de fala e fluxo espectral mais incisivo.",
    "sub_harmonicos": "Sub-harmonicos vocais entre 5 e 12 Hz podem refletir tremores do sistema nervoso autonomo quando cruzados com FACS e tensao vocal basal.",
    "facs_trauma": "A combinacao AU15, AU20, dor facial, angustia e tensao vocal pode sinalizar flooding, sobrecarga autonomica ou retraumatizacao.",
    "governanca_lgpd": "Benchmarks populacionais devem usar dados anonimizados e agregados. O FROID aplica k-anonimato minimo para reduzir risco de reidentificacao.",
}


KNOWLEDGE_SOURCE_LABELS = {
    "froid_zonas": "Fonte interna FROID: Zonas de Percepcao",
    "ipm_velocimetro": "Fonte interna FROID: IPM",
    "idm_direcao": "Fonte interna FROID: IDM",
    "mfcc7_depressao": "Fonte interna FROID: MFCC7 e risco depressivo",
    "mfcc9_ansiedade": "Fonte interna FROID: MFCC9 e ansiedade somatica",
    "shimmer_bioacustico": "Fonte interna FROID: Shimmer bioacustico",
    "jitter_bioacustico": "Fonte interna FROID: Jitter bioacustico",
    "f0_bioacustico": "Fonte interna FROID: F0 bioacustico",
    "zcr_bioacustico": "Fonte interna FROID: ZCR bioacustico",
    "ref_mfcc_davis_mermelstein": "Referencia cientifica: Davis e Mermelstein (1980), MFCC",
    "ref_opensmile_eyben": "Referencia cientifica: Eyben, Wollmer e Schuller (2010), openSMILE",
    "ref_facs_ekman": "Referencia cientifica: Ekman, Friesen e Hager, FACS",
    "ref_praat_boersma": "Referencia cientifica: Boersma e Weenink, Praat/acustica vocal",
    "ref_phq9_kroenke": "Referencia cientifica: Kroenke, Spitzer e Williams (2001), PHQ-9",
    "ref_hamilton_hamd": "Referencia cientifica: Hamilton (1960), HAM-D",
    "ref_ymrs_young": "Referencia cientifica: Young et al. (1978), YMRS",
}


SCIENTIFIC_CITATION_MARKERS = {
    "referencia cientifica",
    "referência científica",
    "davis",
    "mermelstein",
    "eyben",
    "wollmer",
    "schuller",
    "opensmile",
    "ekman",
    "friesen",
    "hager",
    "facs",
    "boersma",
    "weenink",
    "praat",
    "kroenke",
    "spitzer",
    "williams",
    "phq-9",
    "phq9",
    "hamilton",
    "ham-d",
    "hamd",
    "young",
    "ymrs",
    "doi",
    "pubmed",
    "journal",
    "bibliografia cientifica",
    "artigo",
    "paper",
}


def _is_scientific_citation(citation: str) -> bool:
    normalized = _normalize_search_text(citation)
    return any(marker in normalized for marker in SCIENTIFIC_CITATION_MARKERS)


def _scientific_citations(citations: List[str]) -> List[str]:
    return sorted(
        {
            str(citation or "").strip()
            for citation in citations
            if str(citation or "").strip() and _is_scientific_citation(str(citation))
        }
    )


def _sanitize_reference_sections(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return value
    match = re.search(r"\n\s*refer[^\n]*utilizad[^\n]*\n", value, flags=re.IGNORECASE)
    if not match:
        return value
    before = value[: match.start()].rstrip()
    reference_block = value[match.end() :].strip()
    lines = [
        line.strip()
        for line in reference_block.splitlines()
        if line.strip().startswith(("-", "*"))
    ]
    scientific_lines = [
        line
        for line in lines
        if _is_scientific_citation(line)
    ]
    if not scientific_lines:
        return before
    return f"{before}\n\nReferencias utilizadas:\n" + "\n".join(scientific_lines)


class FroidExplicaQuery(BaseModel):
    query_text: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    response_locale: str = "pt-BR"


class FroidExplicaResponse(BaseModel):
    result_text: str
    engine_used: str
    citations: List[str] = Field(default_factory=list)
    safety_check_passed: bool
    intent: str = "knowledge"


class PatientPortalLoginRequest(BaseModel):
    # Aceita CPF OU e-mail no mesmo campo. O aceite do convite deixou de exigir
    # CPF, e sem esta alternativa quem entrou sem informar documento nunca mais
    # consegue voltar ao portal.
    document: str = ""
    email: str = ""
    password: str = ""


class PatientGoogleLoginRequest(BaseModel):
    credential: str = Field(..., min_length=20)


class PatientPasswordUpdate(BaseModel):
    current_password: str = ""
    new_password: str = Field(..., min_length=8, max_length=256)
    password_confirm: str = Field(..., min_length=8, max_length=256)


class PatientPortalProfileUpdate(BaseModel):
    name: str = ""
    phone: str = ""
    document: str = ""
    birth_date: str = ""


class PatientConsentPreferences(BaseModel):
    patient_tcle: bool = False
    terms_of_use: bool
    privacy_policy: bool
    sensitive_data_processing: bool
    audio_video_processing: bool
    research_anonymized: bool = False


class ClinicalNoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class DataSubjectRequestCreate(BaseModel):
    request_type: str
    organization_id: str = ""
    details: str = Field(default="", max_length=4000)


class DataSubjectRequestUpdate(BaseModel):
    status: str
    response_summary: str = Field(default="", max_length=4000)
    legal_basis: str = Field(default="", max_length=1000)
    retention_exception: str = Field(default="", max_length=2000)


DATA_SUBJECT_REQUEST_TYPES = {
    "access", "correction", "portability", "processing_information",
    "consent_withdrawal", "restriction", "deletion", "anonymization",
    "automated_review",
}
DATA_SUBJECT_REQUEST_STATUSES = {
    "submitted", "identity_verified", "in_review", "awaiting_information",
    "approved", "partially_approved", "denied", "completed", "cancelled",
}


def _clean_llm_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if "\n" in cleaned:
            first, rest = cleaned.split("\n", 1)
            cleaned = rest if first.strip().lower() in {"json", "sql"} else cleaned
    return cleaned.strip()


def _normalize_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


async def _generate_froid_explain_text(
    system_instruction: str,
    prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 900,
    json_mode: bool = False,
) -> Tuple[str, str]:
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            def _run_gemini() -> str:
                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model=FROID_EXPLICA_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                return str(getattr(response, "text", "") or "").strip()

            text = await asyncio.to_thread(_run_gemini)
            if text:
                return _clean_llm_text(text), f"Gemini ({FROID_EXPLICA_MODEL})"
        except Exception:
            pass

    if OPENAI_API_KEY:
        try:
            payload: Dict[str, Any] = {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if text:
                return _clean_llm_text(text), f"OpenAI ({OPENAI_MODEL})"
        except Exception:
            pass

    return "", "local-fallback"


APPROVED_KNOWLEDGE_CACHE: Optional[List[Tuple[str, str]]] = None


def _title_from_markdown_text(path: str, text: str) -> str:
    for line in str(text or "").splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()[:180]
    return os.path.splitext(os.path.basename(path))[0].replace("_", " ")[:180]


def _chunk_approved_markdown(text: str, words_per_chunk: int = 700, overlap: int = 100) -> List[str]:
    clean = re.sub(r"```.*?```", " ", str(text or ""), flags=re.DOTALL)
    clean = re.sub(r"\s+", " ", clean).strip()
    words = clean.split()
    if not words:
        return []
    chunks: List[str] = []
    step = max(1, words_per_chunk - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + words_per_chunk]).strip()
        if len(chunk) >= 80:
            chunks.append(chunk)
        if start + words_per_chunk >= len(words):
            break
    return chunks


def _load_approved_knowledge_docs() -> List[Tuple[str, str]]:
    global APPROVED_KNOWLEDGE_CACHE
    if APPROVED_KNOWLEDGE_CACHE is not None:
        return APPROVED_KNOWLEDGE_CACHE
    docs: List[Tuple[str, str]] = []
    root = FROID_APPROVED_KNOWLEDGE_DIR
    if os.path.exists(root):
        for dirpath, _, filenames in os.walk(root):
            for filename in sorted(filenames):
                if not filename.lower().endswith(".md"):
                    continue
                path = os.path.join(dirpath, filename)
                try:
                    with open(path, "r", encoding="utf-8-sig", errors="ignore") as file:
                        text = file.read()
                    title = _title_from_markdown_text(path, text)
                    for index, chunk in enumerate(_chunk_approved_markdown(text)):
                        label = title if index == 0 else f"{title} (parte {index + 1})"
                        docs.append((label, chunk))
                except Exception:
                    continue
    APPROVED_KNOWLEDGE_CACHE = docs
    return docs


def _query_local_froid_knowledge(query_text: str, limit: int = 4) -> Tuple[List[str], List[str]]:
    query = _normalize_search_text(query_text)
    tokens = {token for token in re.split(r"\W+", query) if len(token) >= 4}
    ranked: List[Tuple[int, str, str]] = []
    for source, content in KNOWLEDGE_BASE.items():
        haystack = _normalize_search_text(f"{source} {content}")
        score = sum(1 for token in tokens if token in haystack)
        if not tokens or score > 0:
            ranked.append((score, source, content))
    for source, content in _load_approved_knowledge_docs():
        haystack = _normalize_search_text(f"{source} {content}")
        score = sum(1 for token in tokens if token in haystack)
        if not tokens or score > 0:
            ranked.append((score, source, content))
    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = [item for item in ranked if item[0] > 0][:limit]
    if not selected:
        return [], []
    return [
        item[2] for item in selected
    ], [
        KNOWLEDGE_SOURCE_LABELS.get(item[1], item[1]) for item in selected
    ]


def _query_chroma_froid_knowledge(query_text: str, limit: int = 4) -> Tuple[List[str], List[str]]:
    if not os.path.exists(FROID_CHROMA_PATH):
        return [], []
    try:
        from chromadb import PersistentClient

        chroma_client = PersistentClient(path=FROID_CHROMA_PATH)
        # O MESMO modelo da indexação, obrigatoriamente. Sem isto a consulta
        # usa o modelo padrão da ChromaDB e o vetor da pergunta sai com
        # dimensão diferente da do índice — o erro cai no except abaixo e o
        # FROID Explica passa a responder sem consultar a base, em silêncio,
        # como se nada tivesse acontecido.
        collection, _ = explica_embeddings.collection_for(
            chroma_client, FROID_CHROMA_COLLECTION
        )
        results = collection.query(query_texts=[query_text], n_results=limit)
        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        citations = [
            str((metadata or {}).get("title") or (metadata or {}).get("source") or "Manual FROID")
            for metadata in metadatas
        ]
        return [str(document) for document in documents if document], citations
    except Exception:
        # Registrado em vez de engolido: uma base de conhecimento que parou de
        # responder é indistinguível de uma que não tinha resposta, e foi assim
        # que uma troca de modelo derrubou a consulta sem ninguém perceber.
        LOGGER.exception("FROID Explica nao conseguiu consultar a base de conhecimento")
        return [], []


# Campos volumosos/textuais tratados em secoes proprias do prompt, fora do
# dump JSON de metricas (evita truncar tudo no limite de caracteres).
_SESSION_TEXT_FIELDS = {
    "session_transcript",
    "patient_speech",
    "professional_speech",
    "portfolio_summary",
}


def _format_session_context(context: Dict[str, Any]) -> str:
    if not context:
        return "Sem contexto de sessao enviado pelo painel."
    safe_context = {
        key: value
        for key, value in context.items()
        if key not in {"patient_name", "email", "phone", "document"}
        and key not in _SESSION_TEXT_FIELDS
    }
    return json.dumps(safe_context, ensure_ascii=False, indent=2)[:5000]


def _format_session_transcript(context: Dict[str, Any]) -> str:
    """Transcricao da sessao atual com fala do paciente e do profissional
    separadas e identificadas, para o FROID Explica consultar diretamente."""
    if not isinstance(context, dict):
        return "Sem transcricao disponivel nesta sessao."
    if not context.get("transcript_available"):
        return (
            "Nenhuma transcricao foi capturada ainda nesta sessao "
            "(a fala e transcrita quando o audio do paciente esta ativo)."
        )
    legend = str(
        context.get("transcript_speaker_legend")
        or "DR = profissional; PC/PAC = paciente."
    )
    transcript = str(context.get("session_transcript") or "").strip()
    patient_speech = str(context.get("patient_speech") or "").strip()
    professional_speech = str(context.get("professional_speech") or "").strip()
    parts = [f"Legenda de locutores: {legend}"]
    if transcript:
        parts.append(f"TRANSCRICAO CRONOLOGICA DA SESSAO:\n{transcript[:8000]}")
    if patient_speech:
        parts.append(f"APENAS FALA DO PACIENTE:\n{patient_speech[:4000]}")
    if professional_speech:
        parts.append(
            f"APENAS FALA DO PROFISSIONAL (recomendacoes, intervencoes):\n"
            f"{professional_speech[:4000]}"
        )
    return "\n\n".join(parts)


_COMPARATIVE_QUERY_MARKERS = (
    "compar",
    "outras sess",
    "sessoes anteriores",
    "sessões anteriores",
    "sessoes ja realizadas",
    "sessões já realizadas",
    "carteira",
    "portfolio",
    "portfólio",
    "historico",
    "histórico",
    "evolu",
    "media das sess",
    "média das sess",
    "outros pacientes",
    "casos similares",
    "base populac",
    "ultimas sess",
    "últimas sess",
)


def _is_comparative_question(query_text: str) -> bool:
    normalized = _normalize_search_text(query_text)
    return any(marker in normalized for marker in _COMPARATIVE_QUERY_MARKERS)


def _compact_report_summary(report: dict) -> dict:
    """Resumo minimo e seguro de uma sessao para comparacao: sem transcricao
    bruta de outras sessoes, apenas metricas agregadas e identificadores."""
    metrics = report.get("metricsAnalysis") if isinstance(report, dict) else None
    average = report.get("sessionAverage") if isinstance(report, dict) else None
    summary_source = metrics if isinstance(metrics, dict) else {}
    average_source = average if isinstance(average, dict) else {}
    return {
        "session_id": str(report.get("sessionId") or report.get("session_id") or ""),
        "date": str(report.get("createdAt") or report.get("created_at") or "")[:10],
        "patient_id": str(report.get("patientId") or ""),
        "ipm_average": average_source.get("ipm")
        or summary_source.get("ipm_average")
        or summary_source.get("average_ipm"),
        "dominant_zone": summary_source.get("dominant_zone")
        or summary_source.get("dominantZone"),
        "coherence": average_source.get("coherence")
        or summary_source.get("coherence_status"),
        "session_summary": str(report.get("sessionSummary") or "")[:400],
    }


def _build_portfolio_summary(
    request: Request, current_patient_id: str
) -> list[dict]:
    """Resumos compactos das sessoes que o profissional pode ver (RLS aplicado),
    priorizando o mesmo paciente. Nunca inclui transcricao bruta de outras
    sessoes; respeita os acessos definidos pelo admin em planos multiprofissionais."""
    try:
        accessible, _context = _accessible_session_reports(
            request, reveal_transcripts=False
        )
    except HTTPException:
        return []
    summaries = [
        _compact_report_summary(_enrich_report_patient(report))
        for report in accessible
        if isinstance(report, dict)
    ]
    summaries.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    patient_id = str(current_patient_id or "").strip()
    if patient_id:
        same_patient = [s for s in summaries if s.get("patient_id") == patient_id]
        others = [s for s in summaries if s.get("patient_id") != patient_id]
        summaries = same_patient[:12] + others[:8]
    else:
        summaries = summaries[:15]
    return summaries


def _format_portfolio_summary(context: Dict[str, Any]) -> str:
    summaries = context.get("portfolio_summary") if isinstance(context, dict) else None
    if not summaries:
        return ""
    return (
        "SESSOES DA CARTEIRA DO PROFISSIONAL (resumo agregado, sem transcricao "
        "das outras sessoes; use para comparar evolucao e casos):\n"
        + json.dumps(summaries, ensure_ascii=False, indent=2)[:4000]
    )


def _format_conversation_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return "Sem historico conversacional enviado."
    lines: List[str] = []
    for message in history[-6:]:
        role = str(message.get("role") or "").strip().lower()
        label = "Profissional" if role == "user" else "FROID Explica"
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{label}: {content[:1200]}")
    return "\n\n".join(lines)[:5000] or "Sem historico conversacional util."


def _is_source_followup(query_text: str) -> bool:
    query = _normalize_search_text(query_text)
    source_markers = {
        "quais fontes",
        "qual fonte",
        "fontes utilizadas",
        "fontes usadas",
        "de onde",
        "referencias",
        "referencias utilizadas",
        "bibliografia",
        "base utilizada",
    }
    return any(marker in query for marker in source_markers)


def _is_contextual_followup(query_text: str) -> bool:
    query = _normalize_search_text(query_text)
    contextual_markers = {
        "essa metrica",
        "esta metrica",
        "dessa metrica",
        "desta metrica",
        "esse resultado",
        "este resultado",
        "desse resultado",
        "deste resultado",
        "esse parametro",
        "este parametro",
        "desse parametro",
        "deste parametro",
        "esse indice",
        "este indice",
        "desse indice",
        "deste indice",
        "isso representa",
        "isso significa",
        "como posso integrar",
        "como integrar",
        "como incorporar",
        "incorporar nos meus atendimentos",
        "usar isso",
        "utilizar isso",
        "aplicar isso",
        "na pratica",
        "na consulta",
        "em minhas consultas",
        "nos atendimentos",
    }
    return any(marker in query for marker in contextual_markers)


def _is_operational_question(query_text: str) -> bool:
    query = _normalize_search_text(query_text)
    operational_markers = {
        "quantos pacientes",
        "pacientes ativos",
        "pacientes inativos",
        "minha relacao",
        "minha relação",
        "lista de pacientes",
        "relacao de pacientes",
        "relação de pacientes",
        "meus pacientes",
        "paciente selecionado",
        "paciente atual",
        "este paciente",
        "desse paciente",
        "deste paciente",
        "agenda",
        "convites pendentes",
        "sessoes agendadas",
        "sessões agendadas",
    }
    return any(marker in query for marker in operational_markers)


def _retrieval_query_for_payload(payload: "FroidExplicaQuery") -> str:
    if not (
        _is_source_followup(payload.query_text)
        or _is_contextual_followup(payload.query_text)
    ):
        return payload.query_text
    previous = " ".join(
        str(message.get("content") or "")
        for message in payload.conversation_history[-4:]
    )
    return f"{previous}\n\nPergunta atual: {payload.query_text}".strip()


def _operational_fallback_result(query_text: str, context: Dict[str, Any]) -> Optional[str]:
    if not _is_operational_question(query_text):
        return None
    query = _normalize_search_text(query_text)
    if "paciente" in query:
        selected_patient = context.get("selected_patient")
        if isinstance(selected_patient, dict) and (
            "selecionado" in query
            or "este paciente" in query
            or "desse paciente" in query
            or "deste paciente" in query
            or "paciente atual" in query
        ):
            name = selected_patient.get("patient_name") or "Paciente selecionado"
            return (
                "1. Paciente em contexto\n"
                f"- {name}.\n"
                f"- Sessões registradas: {selected_patient.get('total_sessions', '--')}.\n"
                f"- Sessões ativas: {selected_patient.get('active_sessions', '--')}.\n"
                f"- Prioridade: {selected_patient.get('priority', '--')}.\n"
                f"- Estado FROID: {selected_patient.get('state', '--')}.\n"
                f"- Ação sugerida: {selected_patient.get('action', '--')}.\n\n"
                "2. Como utilizar\n"
                "- Use esses dados como resumo operacional do dashboard para decidir revisão, "
                "continuidade, convite de nova sessão ou abertura do histórico individual.\n\n"
                "Referências utilizadas\n"
                "- Contexto operacional do dashboard profissional."
            )
        active_count = _find_context_metric(
            context,
            {"active_patients_count", "activepatientscount", "pacientes_ativos", "active_patients"},
        )
        total_count = _find_context_metric(
            context,
            {"patients_count", "patientscount", "total_patients", "pacientes_total"},
        )
        if active_count is not None:
            return (
                "1. Resultado disponível\n"
                f"- Pacientes ativos identificados no contexto atual: {active_count}.\n"
                f"{f'- Total de pacientes no contexto atual: {total_count}.\\n' if total_count is not None else ''}\n"
                "2. Como interpretar\n"
                "- Este número vem do contexto operacional enviado pelo painel, não de uma fonte científica.\n\n"
                "Referências utilizadas\n"
                "- Contexto operacional do dashboard profissional."
            )
        return (
            "1. Resultado\n"
            "- Não tenho, nesta conversa, acesso direto à sua relação administrativa de pacientes "
            "nem a um contador operacional enviado pelo dashboard.\n\n"
            "2. O que falta\n"
            "- Para responder com precisão, o painel profissional precisa enviar ao FROID Explica "
            "um campo como `active_patients_count` ou a lista administrativa de pacientes com status ativo.\n\n"
            "3. Próximo passo técnico\n"
            "- Recomendo conectar o FROID Explica ao resumo operacional do dashboard profissional, "
            "permitindo responder perguntas como pacientes ativos, pacientes em revisão, convites pendentes "
            "e sessões recentes.\n\n"
            "Referências utilizadas\n"
            "- Nenhuma referência científica foi usada, pois a pergunta é administrativa/operacional."
        )
    return None


def _find_context_metric(context: Any, names: set[str]) -> Any:
    if isinstance(context, dict):
        for key, value in context.items():
            if str(key).lower() in names:
                return value
        for value in context.values():
            found = _find_context_metric(value, names)
            if found is not None:
                return found
    elif isinstance(context, list):
        for item in context:
            found = _find_context_metric(item, names)
            if found is not None:
                return found
    return None


def _classify_froid_explica_intent(query_text: str) -> str:
    query = _normalize_search_text(query_text)

    current_session_markers = {
        "sessao atual",
        "desta sessao",
        "da sessao",
        "nesta sessao",
        "media da sessao",
        "media das metricas",
        "metricas da sessao",
        "corte atual",
        "neste corte",
        "deste corte",
        "baseline",
        "ipm",
        "idm",
        "mfcc",
        "mfcc7",
        "mfcc9",
        "f0",
        "zcr",
        "jitter",
        "shimmer",
        "sub-harmonico",
        "sub harmonico",
        "biomarcador",
        "biomarcadores",
        "dissonancia",
        "dissonancias",
        "zona dominante",
        "tom",
        "palavras por minuto",
    }
    if any(marker in query for marker in current_session_markers):
        return "knowledge"

    explicit_analytics_markers = {
        "base anonima",
        "base anonimizada",
        "base populacional",
        "data mart",
        "benchmark",
        "populacional",
        "populacao",
        "coorte",
        "percentil",
        "demografico",
        "casos similares",
        "pacientes similares",
        "comparar com outros pacientes",
        "comparacao com outros pacientes",
        "comparar com a populacao",
        "comparacao populacional",
        "estatistica populacional",
        "estatisticas populacionais",
    }
    if any(marker in query for marker in explicit_analytics_markers):
        return "analytics"
    return "knowledge"


def _fallback_froid_explica_result(query_text: str, context: Dict[str, Any]) -> str:
    query = _normalize_search_text(query_text)
    ipm = context.get("ipm_score", "--")
    coherence = context.get("coherence_status", "--")
    dominant = context.get("dominant_zone") or {}
    zone_label = (
        f"Zona {dominant.get('zone')} ({dominant.get('theme')})"
        if isinstance(dominant, dict) and dominant.get("zone")
        else "zona dominante ainda indefinida"
    )

    def _metric_response(
        metric_label: str,
        value_names: set[str],
        concept: str,
        interpretation: str,
        integration: str,
        references: str,
    ) -> str:
        metric_value = _find_context_metric(context, value_names)
        tone = _find_context_metric(
            context,
            {"tone", "emotional_tone", "baseline_tone", "tom"},
        )
        return (
            f"Leitura local do {metric_label} na sessao atual.\n\n"
            "1. Valor contextual\n"
            f"- {metric_label}: {metric_value if metric_value is not None else '--'}"
            f"{f' | tom: {tone}' if tone is not None else ''}\n\n"
            "2. O que a metrica representa\n"
            f"- {concept}\n\n"
            "3. Como interpretar no FROID\n"
            f"- {interpretation}\n\n"
            "4. Como incorporar na avaliacao clinica\n"
            f"- {integration}\n\n"
            "5. Limite clinico\n"
            "- Use como marcador de apoio e nunca como conclusao isolada. A leitura deve ser "
            "validada pela escuta, pelo contexto da fala, pelo baseline de 60 segundos, pelos "
            "cortes temporais e pelo julgamento do profissional.\n\n"
            "Referencias utilizadas\n"
            f"- {references}\n"
            "- Contexto da sessao atual enviado ao FROID Explica.\n"
            "- Base local FROID de biomarcadores vocais."
        )

    if "mfcc7" in query:
        mfcc7_value = _find_context_metric(
            context,
            {"mfcc7", "mfcc7_avg", "average_mfcc7", "mfcc7mean"},
        )
        mfcc9_value = _find_context_metric(
            context,
            {"mfcc9", "mfcc9_avg", "average_mfcc9", "mfcc9mean"},
        )
        tone = _find_context_metric(
            context,
            {"tone", "emotional_tone", "baseline_tone", "tom"},
        )
        return (
            "Leitura local do MFCC7 na sessao atual.\n\n"
            "1. Valor contextual\n"
            f"- MFCC7: {mfcc7_value if mfcc7_value is not None else '--'}"
            f"{f' | MFCC9: {mfcc9_value}' if mfcc9_value is not None else ''}"
            f"{f' | tom: {tone}' if tone is not None else ''}\n\n"
            "2. O que a metrica representa\n"
            "- MFCC7 e um coeficiente cepstral em escala Mel, associado a componentes espectrais "
            "da voz. No FROID, ele e usado como biomarcador acustico de apoio, especialmente "
            "quando aparece em fala de valencia semantica negativa.\n\n"
            "3. Como interpretar no FROID\n"
            "- O MFCC7 ganha relevancia quando se eleva junto de pausas prolongadas, menor "
            "variacao de F0, alteracoes de ZCR, Jitter/Shimmer ou sinais de retardo/tensao vocal.\n\n"
            "4. Como incorporar na avaliacao clinica\n"
            "- Compare com o baseline de 60 segundos, com os cortes de 10 minutos, com o tema "
            "do trecho e com as dissonancias registradas. Se o valor estiver sustentado, use-o "
            "para formular perguntas clinicas mais cuidadosas sobre carga afetiva, perda, "
            "desesperanca, inibicao emocional ou defesa.\n\n"
            "5. Limite clinico\n"
            "- Nao use o MFCC7 como conclusao isolada. Ele deve apoiar, e nao substituir, a "
            "escuta e o julgamento profissional.\n\n"
            "Referencias utilizadas\n"
            "- Base local FROID: mfcc7_depressao.\n"
            "- Contexto da sessao atual enviado ao FROID Explica.\n"
            "- Referencia cientifica: Davis e Mermelstein (1980), MFCC."
        )

    if "shimmer" in query:
        return _metric_response(
            "Shimmer",
            {"shimmer", "shimmer_avg", "average_shimmer", "shimmermean"},
            "No dashboard atual, Shimmer e um indice proxy interno normalizado da variacao relativa do envelope RMS da voz do paciente. Ele nao deve ser lido como shimmer em dB.",
            "Compare esse indice com o baseline individual e com os cortes posteriores. Ele se torna mais informativo quando aparece junto de Jitter proxy, alteracoes de F0, energia, pausas, ZCR, tensao vocal ou dissonancias faciais-vocais.",
            "Use o Shimmer idx. para observar instabilidade relativa de energia vocal, esforco, tensao afetiva ou controle respiratorio/vocal. Para aplicar limiares normativos em dB, sera necessaria uma camada fisica especifica de extracao validada.",
            "Base local FROID: shimmer_bioacustico; Referencia cientifica conceitual: Boersma e Weenink/Praat para shimmer fisico em analise acustica vocal.",
        )

    if "jitter" in query:
        return _metric_response(
            "Jitter",
            {"jitter", "jitter_avg", "average_jitter", "jittermean"},
            "No dashboard atual, Jitter e um indice proxy interno normalizado derivado da taxa de cruzamento por zero escalada. Ele nao deve ser lido como jitter percentual normativo.",
            "No FROID, Jitter idx. ganha relevancia quando aparece sustentado com Shimmer idx., alteracoes de F0, pausas, tensao vocal, queda de fluidez ou mudanca de tom emocional.",
            "Use o Jitter idx. como apoio para investigar instabilidade vocal relativa, carga autonomica possivel ou esforco de controle emocional, sempre relacionando com o conteudo verbal e com o baseline. Para aplicar limiares percentuais normativos, sera necessaria uma camada fisica especifica de extracao validada.",
            "Base local FROID: jitter_bioacustico; Referencia cientifica conceitual: Boersma e Weenink/Praat para jitter fisico em analise acustica vocal.",
        )

    if "zcr" in query or "cruzamento por zero" in query:
        return _metric_response(
            "ZCR",
            {"zcr", "zcr_avg", "average_zcr", "zcrmean"},
            "ZCR e a taxa de cruzamento por zero do sinal acustico, usada para observar caracteristicas de ruido, aspereza e energia de alta frequencia.",
            "No FROID, ZCR deve ser lido junto de MFCCs, F0, Jitter idx., Shimmer idx., pausas e intensidade. Alteracoes isoladas podem refletir artefato, microfone, fricativas ou mudanca real de qualidade vocal.",
            "Use o ZCR para apoiar a leitura de tensao, aspereza vocal ou mudancas acusticas durante temas especificos, sempre conferindo qualidade do audio e contexto semantico.",
            "Base local FROID: zcr_bioacustico; Referencia cientifica: Eyben, Wollmer e Schuller (2010), openSMILE/features acusticas.",
        )

    if "f0" in query or "frequencia fundamental" in query:
        return _metric_response(
            "F0",
            {"f0", "f0_mean", "average_f0", "f0mean"},
            "F0 e a frequencia fundamental da voz, relacionada ao pitch percebido e a dinamica de ativacao vocal.",
            "No FROID, F0 e sua variabilidade devem ser comparados ao baseline individual. Elevacao, queda ou achatamento de variabilidade ganham sentido quando cruzados com energia, fala acelerada, pausas, tom e tema.",
            "Use F0 para acompanhar ativacao, retardo, tensao ou reducao expressiva, sempre cruzando com IPM, IDM, biomarcadores acusticos e dissonancias.",
            "Base local FROID: f0_bioacustico; Referencia cientifica: Boersma e Weenink/Praat para F0 e fonetica computacional.",
        )
    return (
        "FROID Explica em modo local. "
        f"Pergunta recebida: {query_text}. "
        f"Contexto atual: IPM {ipm}, coerencia {coherence}, {zone_label}. "
        "Para resposta cientifica ancorada em RAG, configure GEMINI_API_KEY e/ou OPENAI_API_KEY "
        "e carregue a base ChromaDB dos manuais FROID."
    )


async def _query_froid_knowledge(payload: FroidExplicaQuery) -> FroidExplicaResponse:
    response_locale = normalize_session_locale(payload.response_locale)
    operational_result = (
        _operational_fallback_result(payload.query_text, payload.context)
        if response_locale == "pt-BR"
        else ""
    )
    if operational_result:
        return FroidExplicaResponse(
            result_text=operational_result,
            engine_used="FROID Explica Operacional - local",
            citations=[],
            safety_check_passed=True,
            intent="knowledge",
        )

    retrieval_query = _retrieval_query_for_payload(payload)
    chroma_docs, chroma_citations = _query_chroma_froid_knowledge(retrieval_query)
    local_docs, local_citations = _query_local_froid_knowledge(retrieval_query)
    context_chunks = (chroma_docs + local_docs)[:8]
    context_labels = (chroma_citations + local_citations)[:8]
    citations = _scientific_citations(context_labels)
    context_str = "\n\n".join(
        f"[Fonte: {source}]\n{doc}"
        for source, doc in zip(context_labels, context_chunks)
    )
    session_context = _format_session_context(payload.context)
    session_transcript = _format_session_transcript(payload.context)
    portfolio_summary = _format_portfolio_summary(payload.context)
    conversation_history = _format_conversation_history(payload.conversation_history)
    system_instruction = (
        "Voce e o FROID Explica, uma inteligencia clinica de apoio ao profissional. "
        f"{session_language(response_locale).summary_instruction}, de modo objetivo, sem diagnosticar e sem inventar. "
        "Voce TEM acesso, nesta sessao, a transcricao do que foi falado, com a fala do "
        "PACIENTE e do PROFISSIONAL separadas e identificadas (secao TRANSCRICAO), e aos "
        "biomarcadores e metricas da sessao (secao CONTEXTO DA SESSAO). Quando o profissional "
        "perguntar sobre o que foi dito, recomendacoes dadas, falas do paciente ou do "
        "profissional, responda com base nessa transcricao, citando o trecho pertinente. "
        "So diga que nao tem acesso se a secao TRANSCRICAO indicar que nenhuma fala foi "
        "capturada. Avalie metricas e fala do paciente e do profissional de forma separada "
        "quando solicitado. "
        "Use estritamente o contexto cientifico disponivel, o contexto da sessao, a transcricao "
        "e o historico conversacional. Se a pergunta for de seguimento, como 'quais fontes?', responda sobre "
        "a resposta anterior, nao sobre um tema novo. Se o profissional disser 'essa metrica', "
        "'esse resultado', 'isso', 'como integrar' ou expressao equivalente, identifique no "
        "historico qual foi a ultima metrica ou tema discutido e continue exatamente desse ponto. "
        "Nao substitua a metrica anterior por IPM, IDM ou zonas se o assunto anterior era MFCC7, "
        "Shimmer, Jitter, F0, ZCR ou outro biomarcador especifico. Nao cite LGPD ou governanca se o assunto "
        "anterior era biomarcador vocal, FACS, IPM, IDM ou outra metrica clinica. "
        "Use documentos internos FROID apenas como contexto tecnico, sem lista-los espontaneamente "
        "como referencias finais. Ao final, em 'Referencias utilizadas', liste somente referencias "
        "cientificas/documentos cientificos diretamente relacionados ao tema. Nao inclua base "
        "operacional, campos anonimizados, proximas acoes, familia/relacionamentos, dashboard, "
        "contexto da sessao ou documentos internos nao cientificos nessa secao. Se nao houver "
        "referencia cientifica relacionada ao tema perguntado, omita a secao de referencias. "
        "Se as fontes forem insuficientes, diga claramente o que falta. "
    )
    prompt = (
        f"CONTEXTO CIENTIFICO FROID:\n{context_str or 'Base cientifica nao carregada.'}\n\n"
        f"CONTEXTO DA SESSAO ATUAL (metricas e biomarcadores):\n{session_context}\n\n"
        f"TRANSCRICAO DA SESSAO ATUAL:\n{session_transcript}\n\n"
        + (f"{portfolio_summary}\n\n" if portfolio_summary else "")
        + f"HISTORICO RECENTE DO FROID EXPLICA:\n{conversation_history}\n\n"
        f"PERGUNTA DO PROFISSIONAL:\n{payload.query_text}"
    )
    text, engine = await _generate_froid_explain_text(
        system_instruction,
        prompt,
        temperature=0.1,
        max_tokens=900,
    )
    if not text:
        text = _fallback_froid_explica_result(payload.query_text, payload.context)
    return FroidExplicaResponse(
        result_text=text,
        engine_used=f"FROID Explica RAG - {engine}",
        citations=citations,
        safety_check_passed=True,
        intent="knowledge",
    )


SQL_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma|export|import|read_csv|read_parquet|load|install)\b",
    re.IGNORECASE,
)


def _strip_sql(sql_text: str) -> str:
    sql = _clean_llm_text(sql_text)
    sql = sql.replace("```sql", "").replace("```", "").strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return sql


def _validate_duckdb_select(sql_text: str) -> str:
    sql = _strip_sql(sql_text)
    lowered = sql.lower()
    if not re.match(r"^\s*(select|with)\b", lowered):
        raise HTTPException(status_code=400, detail="SQL bloqueado: apenas SELECT e WITH são permitidos")
    if ";" in sql:
        raise HTTPException(status_code=400, detail="SQL bloqueado: multiplas instrucoes não são permitidas")
    if SQL_FORBIDDEN_RE.search(sql):
        raise HTTPException(status_code=400, detail="SQL bloqueado por conter comando não permitido")
    allowed_tables = {"anonymous_sessions", "anonymous_session_cuts"}
    if not any(table in lowered for table in allowed_tables):
        raise HTTPException(
            status_code=400,
            detail="SQL deve consultar apenas anonymous_sessions ou anonymous_session_cuts",
        )
    return sql


def _duckdb_connection():
    if not os.path.exists(FROID_DUCKDB_PATH):
        return None
    try:
        import duckdb

        return duckdb.connect(database=FROID_DUCKDB_PATH, read_only=True)
    except Exception:
        return None


def _fallback_analytics_sql(query_text: str) -> Dict[str, str]:
    query = _normalize_search_text(query_text)
    if "corte" in query or "10 minuto" in query or "janela" in query:
        result_sql = (
            "SELECT cut_label, COUNT(DISTINCT session_hash) AS sessoes, "
            "AVG(ipm_avg) AS ipm_medio, AVG(idm_avg) AS idm_medio, "
            "AVG(words_per_minute) AS palavras_por_minuto_media, "
            "AVG(dissonance_count) AS dissonancias_medias "
            "FROM anonymous_session_cuts GROUP BY cut_label ORDER BY cut_label"
        )
        cohort_sql = "SELECT COUNT(DISTINCT session_hash) AS cohort_size FROM anonymous_session_cuts"
    elif "zona" in query:
        result_sql = (
            "SELECT dominant_zone, COUNT(*) AS sessoes, AVG(ipm_score) AS ipm_medio, "
            "AVG(vocal_tension) AS tensao_vocal_media "
            "FROM anonymous_sessions GROUP BY dominant_zone ORDER BY sessoes DESC LIMIT 12"
        )
        cohort_sql = "SELECT COUNT(DISTINCT session_hash) AS cohort_size FROM anonymous_sessions"
    elif "medic" in query or "ssri" in query:
        result_sql = (
            "SELECT ssri_medication, COUNT(*) AS sessoes, AVG(ipm_score) AS ipm_medio, "
            "AVG(vocal_tension) AS tensao_vocal_media "
            "FROM anonymous_sessions GROUP BY ssri_medication ORDER BY sessoes DESC"
        )
        cohort_sql = "SELECT COUNT(DISTINCT session_hash) AS cohort_size FROM anonymous_sessions"
    else:
        result_sql = (
            "SELECT age_bucket, gender, COUNT(*) AS sessoes, AVG(ipm_score) AS ipm_medio, "
            "AVG(vocal_tension) AS tensao_vocal_media, AVG(session_duration) AS duracao_media "
            "FROM anonymous_sessions GROUP BY age_bucket, gender ORDER BY sessoes DESC LIMIT 20"
        )
        cohort_sql = "SELECT COUNT(DISTINCT session_hash) AS cohort_size FROM anonymous_sessions"
    return {
        "result_sql": result_sql,
        "cohort_sql": cohort_sql,
    }


def _parse_analytics_sql_payload(text: str, query_text: str) -> Dict[str, str]:
    if not text:
        return _fallback_analytics_sql(query_text)
    try:
        parsed = _parse_json_object(text)
        result_sql = str(parsed.get("result_sql") or parsed.get("sql") or "").strip()
        cohort_sql = str(parsed.get("cohort_sql") or "").strip()
        if result_sql and cohort_sql:
            return {"result_sql": result_sql, "cohort_sql": cohort_sql}
    except Exception:
        pass
    result_sql = _strip_sql(text)
    return {
        "result_sql": result_sql,
        "cohort_sql": f"SELECT COUNT(*) AS cohort_size FROM ({result_sql}) AS target_cohort",
    }


def _format_query_table(columns: List[str], rows: List[tuple], limit: int = 50) -> str:
    if not rows:
        return "Sem linhas retornadas."
    selected_rows = rows[:limit]
    lines = [" | ".join(columns)]
    for row in selected_rows:
        lines.append(" | ".join(str(value) for value in row))
    return "\n".join(lines)


async def _query_froid_analytics(payload: FroidExplicaQuery) -> FroidExplicaResponse:
    conn = _duckdb_connection()
    if conn is None:
        return FroidExplicaResponse(
            result_text=(
                "Data mart anonimo ainda nao esta disponivel no servidor. "
                f"Configure FROID_DUCKDB_PATH apontando para {FROID_DUCKDB_PATH} "
                "com a tabela anonymous_sessions para habilitar benchmarks populacionais."
            ),
            engine_used="FROID Explica Analytics - offline",
            citations=["Data Mart Populacional Anonimizado"],
            safety_check_passed=False,
            intent="analytics",
        )

    sql_instruction = (
        "Voce traduz perguntas clinicas agregadas para DuckDB com seguranca LGPD. "
        "Existem duas tabelas anonimas: anonymous_sessions e anonymous_session_cuts. "
        "anonymous_sessions contem: session_hash VARCHAR, age_bucket VARCHAR, gender VARCHAR, "
        "ipm_score DOUBLE, dominant_zone INTEGER, vocal_tension DOUBLE, ssri_medication BOOLEAN, "
        "session_duration INTEGER, schema_version VARCHAR, created_at VARCHAR, session_modality VARCHAR, "
        "spoken_language VARCHAR, analysis_language VARCHAR, report_locale VARCHAR, "
        "session_kind VARCHAR, treatment_phase VARCHAR, session_ordinal INTEGER, "
        "interval_since_previous_days DOUBLE, baseline_ipm DOUBLE, baseline_idm DOUBLE, "
        "baseline_zone INTEGER, baseline_tone VARCHAR, baseline_words_per_minute DOUBLE, "
        "average_idm DOUBLE, average_words_per_minute DOUBLE, dissonance_count INTEGER, "
        "average_spectral_beta DOUBLE, average_spectral_gamma DOUBLE, average_spectral_band_index DOUBLE, "
        "average_mfcc7_delta DOUBLE, average_mfcc9_delta_delta DOUBLE, "
        "baseline_spectral_beta DOUBLE, baseline_spectral_gamma DOUBLE, "
        "cuts_count INTEGER, clinical_notes_count INTEGER, summary_theme VARCHAR, "
        "summary_text_anon VARCHAR, stt_model VARCHAR, llm_model VARCHAR, algorithm_version VARCHAR, "
        "audio_quality VARCHAR, media_interruptions INTEGER, confidence_score DOUBLE, "
        "consent_anonymous_research BOOLEAN, session_type VARCHAR, previous_sessions_count INTEGER, "
        "delta_ipm_from_session_baseline DOUBLE, delta_idm_from_session_baseline DOUBLE, "
        "delta_ipm_vs_last3 DOUBLE, delta_idm_vs_last3 DOUBLE, delta_ipm_vs_historical DOUBLE, "
        "delta_idm_vs_historical DOUBLE, longitudinal_trend VARCHAR, emotional_stability VARCHAR, "
        "recurring_themes VARCHAR, recurring_zones VARCHAR, recurring_risks VARCHAR, metrics_version VARCHAR, "
        "weights_version VARCHAR, privacy_tier VARCHAR, pii_excluded BOOLEAN, raw_audio_retained BOOLEAN, "
        "literal_transcript_retained BOOLEAN, media_loss_events INTEGER. "
        "anonymous_session_cuts contem: session_hash VARCHAR, cut_hash VARCHAR, cut_index INTEGER, cut_label VARCHAR, "
        "start_second INTEGER, end_second INTEGER, duration_seconds INTEGER, relative_position DOUBLE, "
        "sample_count INTEGER, speech_density DOUBLE, patient_professional_word_ratio DOUBLE, ipm_avg DOUBLE, "
        "idm_avg DOUBLE, dominant_zone INTEGER, coherence_status VARCHAR, emotional_tone VARCHAR, "
        "words_per_minute DOUBLE, theme VARCHAR, dissonance_count INTEGER, mfcc7 DOUBLE, mfcc9 DOUBLE, "
        "f0_mean DOUBLE, zcr DOUBLE, jitter DOUBLE, shimmer DOUBLE, "
        "jitter_proxy_index DOUBLE, shimmer_proxy_index DOUBLE, jitter_unit VARCHAR, shimmer_unit VARCHAR, "
        "subharmonic_5_12 DOUBLE, "
        "subharmonic_12_20 DOUBLE, subharmonic_20_40 DOUBLE, vocal_basal_85_165 DOUBLE, "
        "spectral_delta_0_4 DOUBLE, spectral_theta_4_8 DOUBLE, spectral_alpha_8_12 DOUBLE, "
        "spectral_beta_12_30 DOUBLE, spectral_gamma_30_80 DOUBLE, spectral_band_index DOUBLE, "
        "mfcc7_delta DOUBLE, mfcc9_delta DOUBLE, mfcc7_delta_delta DOUBLE, mfcc9_delta_delta DOUBLE, "
        "cut_trigger VARCHAR, cut_summary_anon VARCHAR, "
        "patient_summary_anon VARCHAR, professional_summary_anon VARCHAR, patient_word_count INTEGER, "
        "professional_word_count INTEGER, intervention_category VARCHAR, patient_response VARCHAR, "
        "ipm_delta_from_baseline DOUBLE, idm_delta_from_baseline DOUBLE, "
        "dissonance_delta_from_baseline DOUBLE, ipm_delta_previous_cut DOUBLE, "
        "idm_delta_previous_cut DOUBLE, dissonance_delta_previous_cut DOUBLE, "
        "quality_confidence DOUBLE, stt_model VARCHAR, llm_model VARCHAR, algorithm_version VARCHAR, "
        "audio_quality VARCHAR, theme_predominant VARCHAR, relevant_dissonances VARCHAR, "
        "ipm_delta_after_intervention DOUBLE, "
        "idm_delta_after_intervention DOUBLE, dissonance_delta_after_intervention DOUBLE, "
        "dominant_zone_shift VARCHAR, emotional_tone_shift VARCHAR, cadence_shift VARCHAR, "
        "semantic_coherence_shift VARCHAR, biomarker_snapshot_json VARCHAR, subharmonic_snapshot_json VARCHAR, "
        "cut_context_json VARCHAR, previous_cut_context VARCHAR, next_cut_context VARCHAR, "
        "response_ipm_direction VARCHAR, response_idm_direction VARCHAR, response_dissonance_direction VARCHAR, "
        "metrics_version VARCHAR, weights_version VARCHAR, media_loss_events INTEGER. "
        "Retorne somente JSON valido com result_sql e cohort_sql. "
        "result_sql deve ser SELECT agregado, sem dados individuais. "
        "cohort_sql deve retornar COUNT(DISTINCT session_hash) AS cohort_size a partir da coorte consultada "
        "com os mesmos filtros de coorte usados no result_sql. Nao use markdown."
    )
    sql_text, sql_engine = await _generate_froid_explain_text(
        sql_instruction,
        payload.query_text,
        temperature=0.0,
        max_tokens=500,
        json_mode=True,
    )
    sql_payload = _parse_analytics_sql_payload(sql_text, payload.query_text)
    result_sql = _validate_duckdb_select(sql_payload["result_sql"])
    cohort_sql = _validate_duckdb_select(sql_payload["cohort_sql"])

    try:
        cohort_row = conn.execute(cohort_sql).fetchone()
        cohort_size = int(cohort_row[0] if cohort_row else 0)
    except Exception as exc:
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Erro de validacao SQL: {exc}")

    if cohort_size <= FROID_ANALYTICS_MIN_K:
        try:
            conn.close()
        except Exception:
            pass
        return FroidExplicaResponse(
            result_text=(
                "Acesso bloqueado por governanca de dados e LGPD. "
                f"A coorte resultante contém {cohort_size} registros. O Data-FROID "
                f"exige coortes maiores que {FROID_ANALYTICS_MIN_K}. Refine para uma "
                "coorte maior ou use apenas a leitura qualitativa da sessão atual."
            ),
            engine_used=f"FROID Explica Analytics - {sql_engine}",
            citations=["Data Mart Populacional Anonimizado"],
            safety_check_passed=False,
            intent="analytics",
        )

    try:
        result = conn.execute(result_sql)
        columns = [description[0] for description in result.description]
        rows = result.fetchmany(50)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erro ao executar SQL analitico: {exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    table_text = _format_query_table(columns, rows)
    report_instruction = (
        "Voce e o estatistico medico do FROID. Analise somente dados agregados anonimizados. "
        "Explique padroes, limites e implicacoes clinicas sem diagnosticar individuos."
    )
    report_prompt = (
        f"Pergunta original: {payload.query_text}\n"
        f"Coorte aprovada: n={cohort_size}\n"
        f"Resultado agregado:\n{table_text}"
    )
    report_text, report_engine = await _generate_froid_explain_text(
        report_instruction,
        report_prompt,
        temperature=0.25,
        max_tokens=900,
    )
    if not report_text:
        report_text = (
            f"Coorte aprovada com n={cohort_size}. Resultado agregado:\n{table_text}"
        )

    return FroidExplicaResponse(
        result_text=report_text,
        engine_used=f"FROID Explica Analytics - {report_engine}",
        citations=["Data Mart Populacional Anonimizado"],
        safety_check_passed=True,
        intent="analytics",
    )


def _load_session_reports(*, reveal_transcripts: bool = True) -> Dict[str, dict]:
    try:
        if not os.path.exists(FROID_SESSION_REPORTS_PATH):
            return {}
        with open(FROID_SESSION_REPORTS_PATH, "r", encoding="utf-8") as report_file:
            data = json.load(report_file)
        if not isinstance(data, dict):
            return {}
        reports = {}
        for session_id, report in data.items():
            if not isinstance(report, dict):
                continue
            if report.get("transcript_encrypted"):
                if not reveal_transcripts:
                    reports[session_id] = dict(report)
                    continue
                if not CLINICAL_TEXT_CIPHER:
                    locked = dict(report)
                    locked["transcript"] = ""
                    locked["transcript_storage_locked"] = True
                    reports[session_id] = locked
                    continue
                try:
                    report = CLINICAL_TEXT_CIPHER.reveal(
                        report, "transcript", "transcript_encrypted"
                    )
                    report.pop("transcript_storage_locked", None)
                    report.pop("transcript_storage_error", None)
                except TokenEncryptionError:
                    LOGGER.exception("Unable to decrypt clinical transcript")
                    locked = dict(report)
                    locked["transcript"] = ""
                    locked["transcript_storage_locked"] = True
                    locked["transcript_storage_error"] = True
                    reports[session_id] = locked
                    continue
            reports[session_id] = report
        return reports
    except Exception:
        LOGGER.exception("Unable to load persisted session reports")
        return {}


def _save_session_reports(reports: Dict[str, dict]) -> None:
    protected_reports = {}
    for session_id, report in reports.items():
        protected = dict(report)
        if protected.get("transcript"):
            if not CLINICAL_TEXT_CIPHER:
                raise RuntimeError("FROID_CLINICAL_RECORD_ENCRYPTION_KEYS is required")
            protected = CLINICAL_TEXT_CIPHER.protect(
                protected, "transcript", "transcript_encrypted"
            )
        protected_reports[session_id] = protected
    report_dir = os.path.dirname(FROID_SESSION_REPORTS_PATH) or "."
    os.makedirs(report_dir, exist_ok=True)
    tmp_path = f"{FROID_SESSION_REPORTS_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as report_file:
        json.dump(protected_reports, report_file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, FROID_SESSION_REPORTS_PATH)
    os.chmod(FROID_SESSION_REPORTS_PATH, 0o600)
    _mirror_legacy_state_to_postgres(protected_reports)


def _report_for_api(report: dict) -> dict:
    public_report = dict(report or {})
    public_report.pop("transcript_encrypted", None)
    return public_report


def _mirror_legacy_state_to_postgres(reports: Optional[Dict[str, dict]] = None) -> None:
    """Best-effort Phase 1 mirror; legacy JSON remains authoritative."""
    if not TENANT_STORE.enabled:
        return
    try:
        TENANT_STORE.sync_all(
            _identity_state_snapshot(),
            reports
            if reports is not None
            else _load_session_reports(reveal_transcripts=False),
        )
    except Exception:
        LOGGER.exception(
            "PostgreSQL mirror failed; the authoritative legacy write was preserved"
        )


# The migration can mirror safely only after the mirror helper has been defined.
if CALENDAR_TOKEN_MIGRATION_REQUIRED:
    _save_identity_state()


def _trial_state(profile: Optional[dict]) -> dict:
    """Onde a conta esta no periodo de cortesia.

    Conta "em cortesia" e a que recebeu as sessoes de teste e NUNCA comprou.
    Assim que houver uma compra registrada, ela deixa de estar em cortesia para
    sempre — inclusive se o saldo comprado zerar depois. E a partir dai vale a
    regra do cliente pagante: sessao entregue vira pendencia de acerto, nunca
    recusa.
    """
    vazio = {
        "on_trial": False,
        "trial_sessions": 0,
        "trial_used": 0,
        "trial_remaining": 0,
        "trial_exhausted": False,
    }
    if not isinstance(profile, dict):
        return vazio
    concedidas = max(0, _local_int(profile.get("trial_sessions")))
    if concedidas <= 0:
        return vazio
    compras = profile.get("session_credit_purchases")
    if isinstance(compras, list) and compras:
        return vazio
    usadas = max(0, _local_int(profile.get("used_sessions")))
    restantes = max(0, concedidas - usadas)
    return {
        "on_trial": True,
        "trial_sessions": concedidas,
        "trial_used": min(usadas, concedidas),
        "trial_remaining": restantes,
        "trial_exhausted": restantes <= 0,
    }


def _trial_blocks_new_session(email: str) -> bool:
    """Se a cortesia acabou e nada foi comprado, nao se inicia outra sessao.

    Esta e a UNICA recusa nova do modulo, e ela vale so para conta que nunca
    comprou. Nao alcanca o salvamento de relatorio — /api/session-reports nao
    passa por portao nenhum de assinatura, de proposito, para que uma sessao ja
    atendida nunca seja descartada.
    """
    estado = _trial_state(PROFESSIONAL_PROFILES.get(_normalize_email(email)))
    return bool(estado["on_trial"] and estado["trial_exhausted"])


def _trial_block_detail() -> str:
    return (
        f"As {FROID_TRIAL_SESSIONS} sessões de cortesia foram utilizadas. "
        "Escolha um pacote para continuar. Outras configurações podem ser "
        f"tratadas por {FROID_TRIAL_CONTACT_EMAIL}."
    )


def _professional_access_status(email: str) -> dict:
    owner_email = _normalize_email(email)
    profile = PROFESSIONAL_PROFILES.get(owner_email) if owner_email else None
    selected_plan = str((profile or {}).get("selected_plan") or "").strip()
    lgpd_acknowledged = bool((profile or {}).get("lgpd_acknowledged"))
    has_profile = bool(profile)
    profile_fields = (profile or {}).get("profile_fields")
    profile_fields = profile_fields if isinstance(profile_fields, dict) else {}
    account_type = str((profile or {}).get("account_type") or "individual").lower()
    professional_cpf = _local_digits_only(
        profile_fields.get("legalRepresentativeCpf")
        if account_type == "organization"
        else profile_fields.get("cpf") or (profile or {}).get("document")
    )
    payment_status = str((profile or {}).get("payment_status") or "").lower()
    total_sessions = max(0, _local_int((profile or {}).get("total_sessions")))
    used_sessions = max(0, _local_int((profile or {}).get("used_sessions")))
    remaining_sessions = max(
        0,
        _local_int((profile or {}).get("remaining_sessions") if profile else 0)
        if (profile or {}).get("remaining_sessions") is not None
        else total_sessions - used_sessions,
    )
    approval_status = str(
        (profile or {}).get("access_approval_status")
        or ("approved" if profile else "pending")
    ).strip().lower()
    if approval_status not in {"pending", "approved", "rejected", "suspended"}:
        approval_status = "pending"
    approval_ready = approval_status == "approved" or (
        not FROID_PROFESSIONAL_APPROVAL_REQUIRED and approval_status == "pending"
    )
    # "Pronto para usar" significa coisas diferentes para produtos diferentes, e
    # aplicar a régua do clínico à empresa mantinha o cadastro NR-1 preso em
    # onboarding para sempre.
    #
    # O produto clínico é vendido por pacote de sessões: sem plano escolhido, sem
    # pagamento e sem crédito restante não há o que liberar, porque cada sessão
    # consome um crédito.
    #
    # A empresa contratante do NR-1 não compra sessão nenhuma. Ela contrata a
    # avaliação de riscos psicossociais, cujo preço acompanha o efetivo e corre
    # por contrato, não por consumo. Exigir dela plano, pagamento de pacote e
    # crédito de sessão é exigir o que o produto dela não tem — e o efeito era
    # concreto: `onboarding_required` nunca ficava falso, e a empresa era
    # devolvida do painel NR-1 toda vez que tentava entrar.
    #
    # O que faz sentido exigir dela: existir, ter declarado o CNPJ que responde
    # pela avaliação, ter reconhecido o tratamento de dados, e ter passado pela
    # aprovação quando ela é exigida.
    is_nr1_company = account_type == "nr1_company"
    organization_document = _local_digits_only(
        (profile or {}).get("organization_document")
    )
    if is_nr1_company:
        access_ready = (
            has_profile
            and lgpd_acknowledged
            and len(organization_document) == 14
            and approval_ready
        )
    else:
        access_ready = (
            has_profile
            and lgpd_acknowledged
            and bool(selected_plan)
            and bool(professional_cpf)
            and payment_status in PAID_SESSION_STATUSES
            and remaining_sessions > 0
            and approval_ready
        )
    # Sessoes entregues sem credito disponivel. O atendimento nunca e bloqueado
    # nem o registro clinico descartado por questao de credito: a pendencia fica
    # registrada e e avisada a cada acesso para o administrador acertar.
    pending_settlement = max(
        0, _local_int((profile or {}).get("pending_settlement_count"))
    )
    settlement_blocked = pending_settlement >= FROID_MAX_PENDING_SETTLEMENTS
    if settlement_blocked:
        # Bloqueia o INICIO de novas sessoes; nunca a gravacao de uma ja feita.
        access_ready = False
    trial = _trial_state(profile)
    if trial["trial_exhausted"]:
        # Mesmo efeito: o painel devolve a pessoa para a selecao de pacotes.
        # access_ready ja seria falso por remaining_sessions == 0; declarar aqui
        # deixa a razao explicita para quem for ler este trecho depois.
        access_ready = False
    return {
        "has_profile": has_profile,
        # O tipo ja escolhido viaja com o estado de acesso para que a tela de
        # escolha saiba, ANTES do formulario, que a travessia clinico<->empresa
        # sera recusada. Sem isto a pessoa preenche o cadastro guiado inteiro e
        # so leva o "nao" no fim, com o trabalho ja feito. Vazio quando ainda
        # nao ha perfil.
        "account_type": account_type if has_profile else "",
        "lgpd_acknowledged": lgpd_acknowledged,
        "selected_plan": selected_plan,
        "payment_status": payment_status or ("pending_checkout" if selected_plan else "not_started"),
        "onboarding_required": not access_ready,
        "total_sessions": total_sessions,
        "used_sessions": used_sessions,
        "remaining_sessions": remaining_sessions,
        "pending_settlement_count": pending_settlement,
        "pending_settlement_limit": FROID_MAX_PENDING_SETTLEMENTS,
        "settlement_pending": pending_settlement > 0,
        "settlement_blocked": settlement_blocked,
        "settlement_warning": (
            (
                f"Limite de {FROID_MAX_PENDING_SETTLEMENTS} sessões em aberto atingido. "
                "Renove o plano para liberar novas sessões; as pendentes serão "
                "creditadas automaticamente ao FROID na renovação."
            )
            if settlement_blocked
            else (
                f"{pending_settlement} de {FROID_MAX_PENDING_SETTLEMENTS} sessão(ões) "
                "realizada(s) sem crédito disponível aguardam acerto."
            )
            if pending_settlement
            else ""
        ),
        **trial,
        "trial_contact_email": FROID_TRIAL_CONTACT_EMAIL,
        "trial_notice": (
            (
                f"As {trial['trial_sessions']} sessões de cortesia foram "
                "utilizadas. Escolha um pacote para continuar."
            )
            if trial["trial_exhausted"]
            else (
                f"{trial['trial_remaining']} de {trial['trial_sessions']} "
                "sessões de cortesia disponíveis."
            )
            if trial["on_trial"]
            else ""
        ),
        "admin": _is_admin_email(owner_email),
        # A empresa NR-1 nao tem CPF a informar: a chave dela e o CNPJ, e
        # pedi-lo seria coletar dado pessoal sem finalidade.
        "cpf_required": not is_nr1_company and not bool(professional_cpf),
        "company_document_required": is_nr1_company
        and len(organization_document) != 14,
        "manual_approval_required": FROID_PROFESSIONAL_APPROVAL_REQUIRED,
        "manual_approval_status": approval_status,
        "manual_approval_pending": (
            FROID_PROFESSIONAL_APPROVAL_REQUIRED and approval_status == "pending"
        ),
        "manual_approval_ready": approval_ready,
    }


def _settle_pending_sessions(profile: dict, already_deducted: bool) -> int:
    """Credita ao FROID as sessões em aberto assim que o plano é renovado.

    ``already_deducted`` distingue os dois caminhos de compra:

    * Troca de plano recalcula ``remaining = total - used``. Como
      ``_register_pending_settlement`` já incrementou ``used_sessions`` quando
      entregou a sessão sem crédito, essa conta **já** desconta as pendentes —
      descontar de novo cobraria a mesma sessão duas vezes. Aqui só limpamos.
    * Compra avulsa soma ``remaining += total``, partindo de zero, e portanto
      não desconta nada; nesse caso a quitação sai dos créditos novos.

    Devolve quantas sessões foram quitadas.
    """
    pending = profile.get("pending_settlement_session_ids")
    pending = pending if isinstance(pending, list) else []
    if not pending:
        profile["pending_settlement_count"] = 0
        return 0
    settled = len(pending)
    if not already_deducted:
        remaining = max(0, _local_int(profile.get("remaining_sessions")))
        settled = min(settled, remaining)
        if settled <= 0:
            profile["pending_settlement_count"] = len(pending)
            return 0
        profile["remaining_sessions"] = remaining - settled
    profile["pending_settlement_session_ids"] = pending[settled:]
    profile["pending_settlement_count"] = len(pending) - settled
    history = profile.get("settlement_history")
    history = history if isinstance(history, list) else []
    history.append(
        {
            "settled_sessions": settled,
            "settled_session_ids": pending[:settled],
            "charged_against_new_credits": not already_deducted,
            "settled_at": _utc_now_iso(),
        }
    )
    profile["settlement_history"] = history[-200:]
    return settled


def _register_pending_settlement(email: str, session_id: str, profile: dict) -> dict:
    """Contabiliza uma sessao entregue sem credito, para acerto posterior.

    Nunca levanta erro: o relatorio clinico e o atendimento tem precedencia
    sobre a cobranca. A divida fica explicita no status de acesso.
    """
    pending = profile.get("pending_settlement_session_ids")
    pending = pending if isinstance(pending, list) else []
    if session_id not in {str(item) for item in pending}:
        pending = [*pending, session_id]
    consumed = profile.get("consumed_session_ids")
    consumed = consumed if isinstance(consumed, list) else []
    if session_id not in {str(item) for item in consumed}:
        consumed = [*consumed, session_id]
    profile["pending_settlement_session_ids"] = pending[-500:]
    profile["pending_settlement_count"] = len(pending)
    profile["consumed_session_ids"] = consumed[-500:]
    profile["used_sessions"] = max(0, _local_int(profile.get("used_sessions"))) + 1
    profile["remaining_sessions"] = 0
    profile["last_session_consumed_at"] = _utc_now_iso()
    PROFESSIONAL_PROFILES[email] = profile
    _save_identity_state()
    LOGGER.warning(
        "Sessão %s entregue sem crédito disponível para %s; pendente de acerto.",
        session_id,
        email,
    )
    return _professional_access_status(email)


def _consume_professional_session_credit(owner_email: str, session_id: str) -> dict:
    email = _normalize_email(owner_email)
    if not email or not session_id:
        return {}
    profile = PROFESSIONAL_PROFILES.get(email)
    if not isinstance(profile, dict):
        return {}
    consumed = profile.get("consumed_session_ids")
    if not isinstance(consumed, list):
        consumed = []
    if session_id in {str(item) for item in consumed}:
        return _professional_access_status(email)

    if max(0, _local_int(profile.get("remaining_sessions"))) <= 0:
        # Esgotamento nao pode custar o registro clinico nem interromper o
        # atendimento: a sessao e contabilizada como pendente de acerto e o
        # aviso acompanha cada acesso ate o administrador resolver.
        return _register_pending_settlement(email, session_id, profile)

    total_sessions = max(0, _local_int(profile.get("total_sessions")))
    used_sessions = max(0, _local_int(profile.get("used_sessions"))) + 1
    profile["used_sessions"] = used_sessions
    profile["remaining_sessions"] = max(0, total_sessions - used_sessions)
    profile["last_session_consumed_at"] = _utc_now_iso()
    profile["consumed_session_ids"] = [*consumed, session_id][-500:]
    PROFESSIONAL_PROFILES[email] = profile
    _save_identity_state()
    return _professional_access_status(email)


def _apply_shared_wallet_compatibility(
    owner_email: str, session_id: str, wallet_result: dict
) -> dict:
    email = _normalize_email(owner_email)
    profile = PROFESSIONAL_PROFILES.get(email)
    if not isinstance(profile, dict):
        return {
            "remaining_sessions": max(0, _local_int(wallet_result.get("balance"))),
            "shared_wallet": wallet_result,
        }
    consumed = profile.get("consumed_session_ids")
    consumed = consumed if isinstance(consumed, list) else []
    if session_id not in {str(item) for item in consumed}:
        consumed = [*consumed, session_id][-500:]
    balance = max(0, _local_int(wallet_result.get("balance")))
    total = max(0, _local_int(profile.get("total_sessions")))
    profile["remaining_sessions"] = balance
    profile["used_sessions"] = max(0, total - balance)
    profile["consumed_session_ids"] = consumed
    profile["last_session_consumed_at"] = _utc_now_iso()
    PROFESSIONAL_PROFILES[email] = profile
    _save_identity_state()
    return {
        **_professional_access_status(email),
        "shared_wallet": wallet_result,
    }


def _consume_session_credit(
    context: Optional[AccessContext], owner_email: str, session_id: str
) -> dict:
    organization_id = context.organization_id if context else ""
    mode = _shared_credit_mode_for(organization_id)
    if mode != "enforce":
        status = _consume_professional_session_credit(owner_email, session_id)
        status["shared_credit_mode"] = mode
        if mode == "observe" and context:
            try:
                wallet = TENANT_STORE.wallet_status(
                    organization_id=context.organization_id,
                    membership_id=context.membership_id,
                )
                status["shared_wallet_observation"] = {
                    "balance": wallet["balance"],
                    "authority": wallet["authority"],
                    "matches_legacy": wallet["balance"]
                    == max(0, _local_int(status.get("remaining_sessions"))),
                }
            except Exception:
                LOGGER.exception("Unable to observe shared wallet reconciliation")
        return status
    if context is None:
        raise HTTPException(status_code=403, detail="contexto organizacional ausente")
    try:
        result = TENANT_STORE.apply_credit_event(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            actor_user_id=context.user_id,
            delta=-1,
            event_type="consumption",
            idempotency_key=f"session:{session_id}",
            session_id=session_id,
            metadata={"source": "session_report"},
        )
    except Exception as exc:
        message = str(exc).lower()
        if "insufficient" in message:
            # Pool da organizacao zerado: entrega a sessao, registra a pendencia
            # e avisa. O saldo compartilhado permanece em zero (nunca negativo),
            # preservando a invariante provada da carteira.
            profile = PROFESSIONAL_PROFILES.get(_normalize_email(owner_email))
            status = (
                _register_pending_settlement(
                    _normalize_email(owner_email), session_id, profile
                )
                if isinstance(profile, dict)
                else {"settlement_pending": True, "pending_settlement_count": 1}
            )
            status["shared_credit_mode"] = "enforce"
            status["organization_pool_exhausted"] = True
            return status
        if "not active" in message:
            raise HTTPException(status_code=409, detail="carteira compartilhada ainda não ativada")
        LOGGER.exception("Shared wallet consumption failed")
        raise HTTPException(status_code=503, detail="falha ao consumir crédito organizacional")
    status = _apply_shared_wallet_compatibility(owner_email, session_id, result)
    status["shared_credit_mode"] = "enforce"
    if int(result.get("balance") or 0) == 0:
        try:
            asyncio.get_running_loop().create_task(
                _run_automatic_recharge(context.organization_id)
            )
            status["automatic_recharge"] = "scheduled"
        except RuntimeError:
            LOGGER.exception("Unable to schedule automatic recharge")
    return status


def _report_owner_email(report: dict) -> str:
    direct = _normalize_email(
        report.get("professionalEmail")
        or report.get("professional_email")
        or ((report.get("professional") or {}) if isinstance(report.get("professional"), dict) else {}).get("email")
        or ""
    )
    if direct:
        return direct
    return _normalize_email(FROID_LEGACY_REPORT_OWNER)


def _report_organization_id(report: dict) -> str:
    direct = str(
        report.get("organizationId") or report.get("organization_id") or ""
    ).strip()
    if direct:
        return direct
    return str(stable_uuid("organization", _report_owner_email(report)))


def _can_access_report(report: dict, owner_email: str) -> bool:
    return _report_owner_email(report) == _normalize_email(owner_email)


def _find_invite_by_session(session_id: str) -> Optional[dict]:
    if not session_id:
        return None
    for invite in SESSION_INVITES.values():
        if str(invite.get("session_id") or "") == str(session_id):
            return invite
    return None


def _invite_patient_key(invite: dict) -> str:
    patient_id = str(invite.get("patient_id") or "").strip()
    if patient_id:
        return f"id:{patient_id}"
    email = _normalize_email(invite.get("patient_email") or "")
    if email:
        return f"email:{email}"
    phone = _digits_only(invite.get("patient_phone") or "")
    if phone:
        return f"phone:{phone}"
    return f"name:{str(invite.get('patient_name') or 'paciente').strip().lower()}"


def _invite_patient_identity(invite: dict) -> dict:
    patient_id = str(invite.get("patient_id") or "").strip()
    patient = PATIENTS.get(patient_id) if patient_id else {}
    patient = patient if isinstance(patient, dict) else {}
    return {
        "id": patient_id,
        "name": patient.get("name") or invite.get("patient_name") or "Paciente sem nome",
        "email": patient.get("email") or invite.get("patient_email") or "",
        "phone": patient.get("phone") or invite.get("patient_phone") or "",
        "document": patient.get("document") or "",
    }


def _receivable_item(invite: dict) -> dict:
    payment = invite.get("payment") if isinstance(invite.get("payment"), dict) else {}
    due_cents = _receivable_due_cents(invite)
    received_cents = min(_receivable_received_cents(invite), due_cents)
    return {
        "invite_id": invite.get("id") or "",
        "session_id": invite.get("session_id") or "",
        "created_at": invite.get("created_at") or "",
        "accepted_at": invite.get("accepted_at") or "",
        "session_count": max(1, _local_int(payment.get("package_sessions") or 1)),
        "payment_mode": payment.get("mode") or "",
        "payment_status": payment.get("payment_status") or "",
        "session_value_cents": _local_int(payment.get("session_value_cents") or 0),
        "session_value_brl": payment.get("session_value_brl") or _format_brl(_local_int(payment.get("session_value_cents") or 0)),
        "due_cents": due_cents,
        "received_cents": received_cents,
        "pending_cents": max(0, due_cents - received_cents),
        "due_brl": _format_brl(due_cents),
        "received_brl": _format_brl(received_cents),
        "pending_brl": _format_brl(max(0, due_cents - received_cents)),
        "received_at": payment.get("received_at") or "",
    }


def _receivable_due_cents(invite: dict) -> int:
    payment = invite.get("payment") if isinstance(invite.get("payment"), dict) else {}
    return max(
        0,
        _local_int(payment.get("package_total_cents") or payment.get("session_value_cents") or 0),
    )


def _receivable_received_cents(invite: dict) -> int:
    payment = invite.get("payment") if isinstance(invite.get("payment"), dict) else {}
    explicit = payment.get("received_cents")
    if explicit is not None:
        return max(0, _local_int(explicit))
    status = str(payment.get("payment_status") or "").lower()
    if status in {"paid", "received", "recebido", "completed"}:
        return _receivable_due_cents(invite)
    return 0


def _receivable_status(due_cents: int, received_cents: int) -> str:
    if due_cents <= 0:
        return "sem_valor"
    if received_cents >= due_cents:
        return "recebido"
    if received_cents > 0:
        return "parcial"
    return "pendente"


def _invite_organization_id(invite: dict) -> str:
    explicit = str((invite or {}).get("organization_id") or "").strip()
    if explicit:
        return explicit
    owner_email = _normalize_email((invite or {}).get("professional_email") or "")
    return str(stable_uuid("organization", owner_email)) if owner_email else ""


def _can_access_invite_finance(
    invite: dict, owner_email: str, organization_id: str = ""
) -> bool:
    invite_owner = _normalize_email(invite.get("professional_email") or "")
    owner_matches = (
        invite_owner == _normalize_email(owner_email)
        if invite_owner
        else _normalize_email(owner_email) == _normalize_email(FROID_LEGACY_REPORT_OWNER)
    )
    return owner_matches and (
        not organization_id
        or _invite_organization_id(invite) == str(organization_id)
    )


def _patient_payload_from_invite(invite: Optional[dict]) -> dict:
    if not invite:
        return {}
    patient_id = str(invite.get("patient_id") or "")
    registered = (PATIENTS.get(patient_id) if patient_id else {}) or {}
    return {
        "id": patient_id or registered.get("id") or "",
        "name": registered.get("name") or invite.get("patient_name") or "",
        "email": registered.get("email") or invite.get("patient_email") or "",
        "phone": registered.get("phone") or invite.get("patient_phone") or "",
        "document": registered.get("document") or "",
    }


def _enrich_report_patient(report: dict) -> dict:
    if not isinstance(report, dict):
        return report
    session_id = str(report.get("sessionId") or report.get("session_id") or "")
    existing = report.get("patient") if isinstance(report.get("patient"), dict) else {}
    invite_patient = _patient_payload_from_invite(_find_invite_by_session(session_id))
    patient = {
        **invite_patient,
        **existing,
    }
    patient_id = patient.get("id") or report.get("patientId") or ""
    patient_name = patient.get("name") or report.get("patientName") or ""
    patient_document = patient.get("document") or report.get("patientDocument") or ""
    if patient_id or patient_name or patient_document:
        patient.update(
            {
                "id": patient_id,
                "name": patient_name,
                "document": patient_document,
            }
        )
        report["patient"] = patient
        report["patientId"] = patient_id
        report["patientName"] = patient_name
        report["patientDocument"] = patient_document
    return report


def _patient_public_identity(patient: dict) -> dict:
    if not isinstance(patient, dict):
        return {}
    return {
        "id": str(patient.get("id") or ""),
        "name": str(patient.get("name") or ""),
        "email": _normalize_email(patient.get("email") or ""),
        "phone": _digits_only(patient.get("phone") or ""),
        "document": _digits_only(patient.get("document") or ""),
        "birth_date": str(patient.get("birth_date") or ""),
        "created_at": str(patient.get("created_at") or ""),
        "updated_at": str(patient.get("updated_at") or ""),
    }


def _patient_identity_matches(candidate: dict, email: str, document: str, phone: str) -> bool:
    if not isinstance(candidate, dict):
        return False
    candidate_email = _normalize_email(candidate.get("email") or "")
    candidate_document = _digits_only(candidate.get("document") or "")
    candidate_phone = _digits_only(candidate.get("phone") or "")
    email_match = bool(email and candidate_email and candidate_email == email)
    document_match = bool(document and candidate_document and candidate_document == document)
    phone_match = bool(phone and candidate_phone and candidate_phone == phone)
    return email_match and (document_match or phone_match)


def _patient_identity_from_report(report: dict) -> dict:
    enriched = _enrich_report_patient(dict(report or {}))
    patient = enriched.get("patient") if isinstance(enriched.get("patient"), dict) else {}
    return _patient_public_identity(
        {
            **patient,
            "id": patient.get("id") or enriched.get("patientId") or "",
            "name": patient.get("name") or enriched.get("patientName") or "",
            "document": patient.get("document") or enriched.get("patientDocument") or "",
        }
    )


def _patient_record_for_report(report: dict) -> Optional[dict]:
    """Cadastro do paciente a que um relatório pertence, se houver.

    Um relatório pode existir sem cadastro correspondente — sessão avulsa, ou
    paciente que nunca aceitou o convite. Quem chama precisa tratar o None: a
    ausência de cadastro não é erro, é um estado normal do produto.
    """
    enriched = _enrich_report_patient(dict(report or {}))
    patient = enriched.get("patient") if isinstance(enriched.get("patient"), dict) else {}

    patient_id = str(patient.get("id") or enriched.get("patientId") or "").strip()
    if patient_id and isinstance(PATIENTS.get(patient_id), dict):
        return PATIENTS[patient_id]

    document = _digits_only(patient.get("document") or enriched.get("patientDocument") or "")
    if document:
        found = _find_registered_patient_by_document(document)
        if found:
            return found

    contact_key = _patient_contact_key(
        _normalize_email(patient.get("email") or ""),
        _digits_only(patient.get("phone") or ""),
    )
    if contact_key:
        mapped = PATIENTS_BY_CONTACT.get(contact_key)
        if mapped and isinstance(PATIENTS.get(mapped), dict):
            return PATIENTS[mapped]
    return None


def _professional_linked_to_patient(owner_email: str, patient_id: str) -> bool:
    """Este profissional atendeu este paciente?

    Sem esta checagem qualquer profissional autenticado leria e alteraria o
    acesso de qualquer paciente da base, bastando o id. Vale convite emitido por
    ele, ou relatório que ele possa acessar.
    """
    if not owner_email or not patient_id:
        return False
    for invite in SESSION_INVITES.values():
        if (
            _normalize_email(invite.get("professional_email") or "") == owner_email
            and str(invite.get("patient_id") or "") == patient_id
        ):
            return True
    for report in _load_session_reports().values():
        if not isinstance(report, dict):
            continue
        if not _can_access_report(report, owner_email):
            continue
        if (_patient_record_for_report(report) or {}).get("id") == patient_id:
            return True
    return False


def _find_registered_patient_by_document(document: str) -> Optional[dict]:
    normalized_document = _digits_only(document)
    if not normalized_document:
        return None
    patient_id = PATIENTS_BY_CONTACT.get(f"document:{normalized_document}")
    if patient_id and isinstance(PATIENTS.get(patient_id), dict):
        return PATIENTS[patient_id]
    for patient in PATIENTS.values():
        if _digits_only(patient.get("document") or "") == normalized_document:
            return patient
    return None


def _find_registered_patient_by_email(email: str) -> Optional[dict]:
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return None
    matches = {
        str(patient.get("id") or patient_id): patient
        for patient_id, patient in PATIENTS.items()
        if isinstance(patient, dict)
        and _normalize_email(patient.get("email") or "") == normalized_email
    }
    if len(matches) != 1:
        return None
    return next(iter(matches.values()))


def _patient_session_matches_report(report: dict, patient_session: dict) -> bool:
    patient = _patient_identity_from_report(report)
    session_patient_id = str(patient_session.get("id") or "")
    if session_patient_id and patient.get("id") and session_patient_id == str(patient.get("id")):
        return True
    return _patient_identity_matches(
        patient,
        _normalize_email(patient_session.get("email") or ""),
        _digits_only(patient_session.get("document") or ""),
        _digits_only(patient_session.get("phone") or ""),
    )


# Blocos de conteúdo que o profissional pode marcar ou desmarcar no documento do
# paciente. A chave é a mesma do relatório, então a seleção age no lugar onde o
# dado realmente está — não há uma segunda lista para sair de sincronia.
#
# O que NÃO está aqui é deliberado: id, sessionId, createdAt, durationSeconds,
# patient, professional, professionalEmail e transcriptRetention identificam o
# documento e a quem ele pertence. Sem eles o paciente teria um relatório que não
# diz de quem é, de quando é, nem quem o assina — e a retenção de transcrição é
# informação que a LGPD manda estar disponível ao titular.
# A ORDEM AQUI É A ORDEM DAS SEÇÕES NO DOCUMENTO, e o rótulo é o que o
# profissional lê no checklist. Espelhada em PATIENT_ITEM_KEYS, no gerador do
# painel — se as duas divergirem, o profissional marca numa ordem e o documento
# sai em outra.
#
# Os rótulos descrevem o que o PACIENTE vai ver, e não o nome técnico do campo:
# quem marca precisa saber o que está entregando.
PATIENT_REPORT_ITEMS: tuple[tuple[str, str], ...] = (
    ("baseline", "A referência do dia (calibração de 60 s)"),
    ("sessionAverage", "A sessão no conjunto (índices médios)"),
    ("sessionSummary", "Resumo da sessão"),
    ("conversationSummaries", "Percurso da sessão, trecho a trecho"),
    ("tenMinuteCuts", "Medidas a cada dez minutos"),
    ("dissonances", "Sinais registrados"),
    ("metricsAnalysis", "Medidas detalhadas"),
    ("clinicalNotes", "Observações registradas durante a sessão"),
    ("professionalNotes", "Anotações do seu profissional (o texto que você redigiu)"),
)

# O QUE NÃO ESTÁ NO CATÁLOGO, e por quê.
#
# Uma única seção fica fora e é sempre entregue: "O que este documento não é" —
# não é diagnóstico, não é avaliação sobre quem a pessoa é, não substitui o
# profissional. O produto inteiro se define por essa fronteira, e o risco que ela
# cobre não é o profissional decidir retirá-la: é retirá-la por descuido, num dia
# corrido. Torná-la opcional abriria caminho para o sistema produzir exatamente o
# documento que ele nega ser.
#
# "Como ler este documento" também fica fora, mas é CONDICIONAL: só entra quando
# o documento leva alguma medida, porque é dela que a seção fala. Num documento
# só de texto ela explicaria números que não estão lá.
#
# "Anotações do seu profissional" ESTAVA fora e voltou para o catálogo. Ser a
# palavra do profissional justifica a seção existir, não ser obrigatória — e sem
# texto redigido ela imprimia uma caixa dizendo que não havia nada, o que é pior
# do que não imprimir. Mandar só as medidas, sem recado, é decisão clínica.

PATIENT_REPORT_ITEM_KEYS: tuple[str, ...] = tuple(key for key, _ in PATIENT_REPORT_ITEMS)

# Chaves que entram sempre, independentemente do checklist.
PATIENT_REPORT_ALWAYS: tuple[str, ...] = (
    "id",
    "sessionId",
    "createdAt",
    "durationSeconds",
    "patient",
    "professional",
    "professionalEmail",
    "transcriptRetention",
    "metricsAnalysisError",
)


def _normalize_patient_report_items(value) -> list[str]:
    """Filtra a seleção contra a lista conhecida, preservando a ordem canônica.

    Vem do cliente, então nada aqui confia na entrada: chave desconhecida é
    descartada em silêncio em vez de virar campo extra no documento.
    """
    if not isinstance(value, (list, tuple, set)):
        return []
    chosen = {str(item) for item in value}
    return [key for key in PATIENT_REPORT_ITEM_KEYS if key in chosen]


def _patient_results_enabled(patient: dict | None) -> bool:
    """O paciente pode ver sessões e relatórios na área dele?

    Decisão do profissional, tomada no convite e alterável depois. A ausência do
    campo significa cadastro anterior a este controle: mantém o acesso que já
    tinha, porque tirar acesso em silêncio de quem já via seria pior do que o
    contrário. O padrão para convite NOVO é definido na criação, não aqui.
    """
    if not isinstance(patient, dict):
        return False
    value = patient.get("portal_results_enabled")
    if value is None:
        return True
    return bool(value)


def _report_patient_release(report: dict) -> dict:
    """Estado de liberação do relatório para o paciente.

    Relatório sem o campo é anterior a este controle e conta como liberado com
    todos os itens — mesma razão da função acima.
    """
    raw = report.get("patientRelease") if isinstance(report, dict) else None
    if not isinstance(raw, dict):
        return {
            "released": True,
            "items": list(PATIENT_REPORT_ITEM_KEYS),
            "releasedAt": "",
            "releasedBy": "",
            "notes": "",
            "legacy": True,
        }
    items = _normalize_patient_report_items(raw.get("items"))
    return {
        "released": bool(raw.get("released")),
        "items": items,
        "releasedAt": str(raw.get("releasedAt") or ""),
        "releasedBy": str(raw.get("releasedBy") or ""),
        "notes": str(raw.get("notes") or ""),
        "legacy": False,
    }


def _sanitize_report_for_patient(report: dict, items: list[str] | None = None) -> dict:
    enriched = _enrich_report_patient(dict(report or {}))
    selected = (
        list(PATIENT_REPORT_ITEM_KEYS)
        if items is None
        else _normalize_patient_report_items(items)
    )
    allowed_keys = list(PATIENT_REPORT_ALWAYS) + selected
    sanitized = {key: enriched.get(key) for key in allowed_keys if key in enriched}
    sanitized["patient"] = _patient_identity_from_report(enriched)
    sanitized["patientReportItems"] = selected
    return sanitized


def _reports_for_patient_session(patient_session: dict) -> list[dict]:
    """Relatórios que o PACIENTE pode ver.

    Dois portões, e os dois vivem aqui no servidor e não na tela: a permissão do
    paciente e a liberação daquela sessão específica. Item não selecionado não é
    escondido no cliente — ele não sai daqui.
    """
    patient_id = str(patient_session.get("id") or "") if isinstance(patient_session, dict) else ""
    patient = PATIENTS.get(patient_id) if patient_id else None
    if not _patient_results_enabled(patient):
        return []

    reports = []
    for report in _load_session_reports().values():
        if not isinstance(report, dict):
            continue
        if not _patient_session_matches_report(report, patient_session):
            continue
        release = _report_patient_release(report)
        if not release["released"]:
            continue
        sanitized = _sanitize_report_for_patient(report, release["items"])
        # Texto congelado na liberação. Vai como patientNotes e não como o campo
        # do profissional, para deixar explícito que é a versão liberada — e só
        # vai se o item correspondente estiver marcado, como qualquer outro.
        sanitized["patientNotes"] = (
            release["notes"] if "professionalNotes" in release["items"] else ""
        )
        reports.append(sanitized)

    reports.sort(
        key=lambda report: str(report.get("createdAt") or report.get("created_at") or ""),
        reverse=True,
    )
    return reports


def _reports_for_patient_privacy_export(patient_session: dict) -> list[dict]:
    """Relatórios do titular para a exportação LGPD — SEM os dois portões.

    Portabilidade é direito do titular sobre o dado dele, e não uma vista de
    produto que o profissional configura. A permissão de acesso aos resultados e
    a liberação por sessão governam o que aparece na ÁREA do paciente; nenhuma
    das duas pode reduzir o que ele leva embora quando exerce o direito.

    Sem esta função a exportação passaria por _reports_for_patient_session e um
    paciente com o acesso desligado exportaria zero sessões — o que seria um
    defeito de conformidade, não uma decisão de produto.
    """
    reports = [
        _sanitize_report_for_patient(report)
        for report in _load_session_reports().values()
        if isinstance(report, dict) and _patient_session_matches_report(report, patient_session)
    ]
    reports.sort(
        key=lambda report: str(report.get("createdAt") or report.get("created_at") or ""),
        reverse=True,
    )
    return reports


def _privacy_export_report(report: dict) -> dict:
    """Return immediate portable results without free clinical text or third-party data."""
    allowed_keys = (
        "id", "sessionId", "createdAt", "durationSeconds", "patient",
        "baseline", "sessionAverage", "metricsAnalysis", "metricsAnalysisError",
        "transcriptRetention",
    )
    return {key: report.get(key) for key in allowed_keys if key in report}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_str(value, max_chars: int = 4000) -> str:
    text = str(value or "").strip()
    return text[:max_chars]


def _safe_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "sim", "on", "paid", "pago"}:
        return True
    if text in {"0", "false", "no", "nao", "não", "off"}:
        return False
    return default


def _anonymous_session_hash(report: dict) -> str:
    if not FROID_DATAMART_PSEUDONYM_KEY:
        raise RuntimeError("FROID_DATAMART_PSEUDONYM_KEY is required")
    session_id = str(report.get("sessionId") or report.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("Data-FROID requires a technical session identifier")
    raw = f"{session_id}:{report.get('createdAt') or ''}"
    return hmac.new(
        FROID_DATAMART_PSEUDONYM_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _anonymous_cut_hash(session_hash: str, cut_index: int, start_second: int, end_second: int) -> str:
    raw = f"{session_hash}:{cut_index}:{start_second}:{end_second}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _anonymous_category(value: Any, default: str = "nao_classificado") -> str:
    """Keep taxonomy labels while rejecting text that can carry literal speech or PII."""
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not text:
        return default
    if len(text) > 80 or len(text.split()) > 6:
        return default
    pii_patterns = (
        r"@", r"https?://", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
        r"\b\+?\d[\d\s().-]{7,}\d\b", r"\b\d{2}/\d{2}/\d{4}\b",
    )
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in pii_patterns):
        return default
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    safe_tokens = {
        "a", "ao", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos",
        "unknown", "nao", "informada", "informado", "apurada", "apurado", "classificado",
        "automatico", "baseline", "cut", "fim", "sessao", "seguimento", "inicial", "remota", "presencial",
        "ansiedade", "depressao", "estresse", "trauma", "dissociacao", "mania", "ativacao", "regulacao",
        "emocional", "estabilidade", "instabilidade", "neutro", "positivo", "negativo", "triste", "alegre",
        "raiva", "medo", "culpa", "vergonha", "luto", "relacionamento", "familia", "trabalho", "sono",
        "saude", "dor", "conflito", "mudanca", "perda", "autocuidado", "acolhimento", "silencio",
        "terapeutico", "grounding", "psicoeducacao", "reestruturacao", "cognitiva", "validacao", "pergunta",
        "aberta", "orientacao", "pratica", "confrontacao", "encerramento", "sintese", "intervencao", "geral",
        "melhora", "aumento", "resposta", "coerente", "incoerente", "estavel", "crescente", "decrescente",
        "feminino", "masculino", "nao_binario", "binario", "online", "hibrida", "boa", "regular", "baixa",
    }
    tokens = [token for token in normalized.split("_") if token and not token.isdigit()]
    if not tokens or any(token not in safe_tokens for token in tokens):
        return default
    return normalized[:80] or default


def _anonymous_age_bucket(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "")
    if re.fullmatch(r"\d{1,3}[-_]\d{1,3}", text):
        return text.replace("-", "_")
    return "unknown"


def _safe_technical_id(value: Any, default: str, max_chars: int = 120) -> str:
    text = str(value or "").strip()
    return text[:max_chars] if re.fullmatch(r"[A-Za-z0-9._:/+-]{1,120}", text) else default


def _anonymous_category_list(value: Any, limit: int = 20) -> list[str]:
    raw_items = value if isinstance(value, list) else []
    categories = []
    for item in raw_items[:limit]:
        category = _anonymous_category(item, "")
        if category and category not in categories:
            categories.append(category)
    return categories


def _ensure_duckdb_column(conn, table: str, column: str, definition: str) -> None:
    try:
        columns = {
            str(row[1]).lower()
            for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        }
        if column.lower() not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except Exception:
        pass


def _ensure_duckdb_columns(conn, table: str, columns: Dict[str, str]) -> None:
    for column, definition in columns.items():
        _ensure_duckdb_column(conn, table, column, definition)


def _session_context(report: dict) -> dict:
    context = report.get("anonymizedContext")
    return context if isinstance(context, dict) else {}


def _summary_for_cut(report: dict, start_minute: int, end_minute: int) -> dict:
    for item in report.get("conversationSummaries") or []:
        if not isinstance(item, dict):
            continue
        if _safe_int(item.get("startMinute")) == start_minute and _safe_int(item.get("endMinute")) == end_minute:
            return item
    return {}


def _transcript_for_range(report: dict, start_second: int, end_second: int) -> str:
    transcript = str(report.get("transcript") or "")
    if not transcript.strip():
        return ""
    # Relatorios antigos salvam apenas texto linear; usamos o trecho inteiro como fallback anonimo.
    return transcript


def _speaker_text(transcript: str, speaker: str) -> str:
    if not transcript:
        return ""
    pattern = r"(?:^|\n)\s*" + re.escape(speaker) + r"\s*-\s*([^\n]+)"
    parts = re.findall(pattern, transcript, flags=re.IGNORECASE)
    return " ".join(part.strip() for part in parts if part.strip())


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ÿ]{2,}\b", str(text or ""), flags=re.UNICODE))


def _infer_intervention_category(text: str) -> str:
    clean = str(text or "").lower()
    if not clean:
        return "nao_classificada"
    buckets = [
        ("acolhimento", ["estou aqui", "vamos com calma", "pode falar", "te escuto", "acolho"]),
        ("silencio_terapeutico", ["pausa", "silencio", "podemos esperar", "sem pressa"]),
        ("grounding_regulacao", ["respira", "aterrar", "grounding", "corpo", "observe", "presenca"]),
        ("psicoeducacao", ["explicar", "psicoeduc", "entenda", "funciona", "modelo", "sistema nervoso"]),
        ("reestruturacao_cognitiva", ["pensamento", "crenca", "evidencia", "alternativa", "reinterpretar"]),
        ("validacao_emocional", ["faz sentido", "compreendo", "valido", "acolho", "natural sentir"]),
        ("pergunta_aberta", ["como", "quando", "o que", "qual", "pode falar", "?"]),
        ("orientacao_pratica", ["tarefa", "exercicio", "praticar", "anotar", "combinado"]),
        ("confrontacao_terapeutica", ["percebe", "contradicao", "padrao", "evita", "resistencia"]),
        ("encerramento_sintese", ["resumindo", "sintese", "encerrar", "proxima sessao", "combinamos"]),
    ]
    scores = [
        (category, sum(1 for needle in needles if needle in clean))
        for category, needles in buckets
    ]
    best = max(scores, key=lambda item: item[1])
    return best[0] if best[1] > 0 else "intervencao_geral"


def _infer_patient_response(cut: dict, previous_cut: Optional[dict], baseline: dict) -> str:
    ipm = _safe_float(cut.get("ipmAvg"))
    dissonance = _safe_float(cut.get("dissonanceCount"))
    reference_ipm = _safe_float((previous_cut or {}).get("ipmAvg"), _safe_float(baseline.get("ipmAvg")))
    reference_dissonance = _safe_float(
        (previous_cut or {}).get("dissonanceCount"),
        _safe_float(baseline.get("dissonanceCount")),
    )
    ipm_delta = ipm - reference_ipm
    dissonance_delta = dissonance - reference_dissonance
    if ipm_delta <= -0.5 and dissonance_delta <= 0:
        return "melhora_regulacao"
    if ipm_delta >= 0.5 or dissonance_delta > 0:
        return "aumento_ativacao"
    return "estabilidade"


def _cut_confidence(cut: dict) -> float:
    sample_count = _safe_float(cut.get("sampleCount"))
    duration = max(1.0, _safe_float(cut.get("endSecond")) - _safe_float(cut.get("startSecond")))
    coverage = min(1.0, sample_count / max(1.0, duration / 10.0))
    speech = min(1.0, _safe_float(cut.get("wordsPerMinute")) / 80.0)
    return round((coverage * 0.65) + (speech * 0.35), 3)


def _append_anonymous_datamart_row(report: dict) -> None:
    conn = None
    transaction_started = False
    session_hash = ""
    try:
        import duckdb

        context = _session_context(report)
        os.makedirs(os.path.dirname(FROID_DUCKDB_PATH) or ".", exist_ok=True)
        conn = duckdb.connect(database=FROID_DUCKDB_PATH, read_only=False)
        session_hash = _anonymous_session_hash(report)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS privacy_ingestion_audit (
                session_hash VARCHAR,
                accepted BOOLEAN,
                reason VARCHAR,
                checked_at VARCHAR,
                pipeline_version VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS anonymous_sessions (
                session_hash VARCHAR,
                age_bucket VARCHAR,
                gender VARCHAR,
                ipm_score DOUBLE,
                dominant_zone INTEGER,
                vocal_tension DOUBLE,
                ssri_medication BOOLEAN,
                session_duration INTEGER,
                schema_version VARCHAR,
                created_at VARCHAR,
                session_modality VARCHAR,
                spoken_language VARCHAR,
                analysis_language VARCHAR,
                report_locale VARCHAR,
                session_kind VARCHAR,
                treatment_phase VARCHAR,
                session_ordinal INTEGER,
                interval_since_previous_days DOUBLE,
                baseline_ipm DOUBLE,
                baseline_idm DOUBLE,
                baseline_zone INTEGER,
                baseline_tone VARCHAR,
                baseline_words_per_minute DOUBLE,
                average_idm DOUBLE,
                average_words_per_minute DOUBLE,
                dissonance_count INTEGER,
                cuts_count INTEGER,
                clinical_notes_count INTEGER,
                summary_theme VARCHAR,
                summary_text_anon VARCHAR,
                stt_model VARCHAR,
                llm_model VARCHAR,
                algorithm_version VARCHAR,
                audio_quality VARCHAR,
                media_interruptions INTEGER,
                confidence_score DOUBLE,
                consent_anonymous_research BOOLEAN,
                session_type VARCHAR,
                previous_sessions_count INTEGER,
                delta_ipm_from_session_baseline DOUBLE,
                delta_idm_from_session_baseline DOUBLE,
                delta_ipm_vs_last3 DOUBLE,
                delta_idm_vs_last3 DOUBLE,
                delta_ipm_vs_historical DOUBLE,
                delta_idm_vs_historical DOUBLE,
                longitudinal_trend VARCHAR,
                emotional_stability VARCHAR,
                recurring_themes VARCHAR,
                recurring_zones VARCHAR,
                recurring_risks VARCHAR,
                metrics_version VARCHAR,
                weights_version VARCHAR,
                privacy_tier VARCHAR,
                pii_excluded BOOLEAN,
                raw_audio_retained BOOLEAN,
                literal_transcript_retained BOOLEAN,
                media_loss_events INTEGER,
                average_spectral_beta DOUBLE,
                average_spectral_gamma DOUBLE,
                average_spectral_band_index DOUBLE,
                average_mfcc7_delta DOUBLE,
                average_mfcc9_delta_delta DOUBLE,
                baseline_spectral_beta DOUBLE,
                baseline_spectral_gamma DOUBLE,
                ingestion_basis VARCHAR
            )
            """
        )
        _ensure_duckdb_columns(
            conn,
            "anonymous_sessions",
            {
                "session_hash": "VARCHAR",
                "schema_version": "VARCHAR",
                "created_at": "VARCHAR",
                "session_modality": "VARCHAR",
                "spoken_language": "VARCHAR",
                "analysis_language": "VARCHAR",
                "report_locale": "VARCHAR",
                "session_kind": "VARCHAR",
                "treatment_phase": "VARCHAR",
                "session_ordinal": "INTEGER",
                "interval_since_previous_days": "DOUBLE",
                "baseline_ipm": "DOUBLE",
                "baseline_idm": "DOUBLE",
                "baseline_zone": "INTEGER",
                "baseline_tone": "VARCHAR",
                "baseline_words_per_minute": "DOUBLE",
                "average_idm": "DOUBLE",
                "average_words_per_minute": "DOUBLE",
                "dissonance_count": "INTEGER",
                "cuts_count": "INTEGER",
                "clinical_notes_count": "INTEGER",
                "summary_theme": "VARCHAR",
                "summary_text_anon": "VARCHAR",
                "stt_model": "VARCHAR",
                "llm_model": "VARCHAR",
                "algorithm_version": "VARCHAR",
                "audio_quality": "VARCHAR",
                "media_interruptions": "INTEGER",
                "confidence_score": "DOUBLE",
                "consent_anonymous_research": "BOOLEAN",
                "session_type": "VARCHAR",
                "previous_sessions_count": "INTEGER",
                "delta_ipm_from_session_baseline": "DOUBLE",
                "delta_idm_from_session_baseline": "DOUBLE",
                "delta_ipm_vs_last3": "DOUBLE",
                "delta_idm_vs_last3": "DOUBLE",
                "delta_ipm_vs_historical": "DOUBLE",
                "delta_idm_vs_historical": "DOUBLE",
                "longitudinal_trend": "VARCHAR",
                "emotional_stability": "VARCHAR",
                "recurring_themes": "VARCHAR",
                "recurring_zones": "VARCHAR",
                "recurring_risks": "VARCHAR",
                "metrics_version": "VARCHAR",
                "weights_version": "VARCHAR",
                "privacy_tier": "VARCHAR",
                "pii_excluded": "BOOLEAN",
                "raw_audio_retained": "BOOLEAN",
                "literal_transcript_retained": "BOOLEAN",
                "media_loss_events": "INTEGER",
                "average_spectral_beta": "DOUBLE",
                "average_spectral_gamma": "DOUBLE",
                "average_spectral_band_index": "DOUBLE",
                "average_mfcc7_delta": "DOUBLE",
                "average_mfcc9_delta_delta": "DOUBLE",
                "baseline_spectral_beta": "DOUBLE",
                "baseline_spectral_gamma": "DOUBLE",
                "ingestion_basis": "VARCHAR",
            },
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS anonymous_session_cuts (
                session_hash VARCHAR,
                cut_hash VARCHAR,
                cut_index INTEGER,
                cut_label VARCHAR,
                start_second INTEGER,
                end_second INTEGER,
                duration_seconds INTEGER,
                relative_position DOUBLE,
                sample_count INTEGER,
                speech_density DOUBLE,
                patient_professional_word_ratio DOUBLE,
                ipm_avg DOUBLE,
                idm_avg DOUBLE,
                dominant_zone INTEGER,
                dominant_theme VARCHAR,
                coherence_status VARCHAR,
                emotional_tone VARCHAR,
                words_per_minute DOUBLE,
                theme VARCHAR,
                dissonance_count INTEGER,
                mfcc7 DOUBLE,
                mfcc9 DOUBLE,
                f0_mean DOUBLE,
                zcr DOUBLE,
                jitter DOUBLE,
                shimmer DOUBLE,
                jitter_proxy_index DOUBLE,
                shimmer_proxy_index DOUBLE,
                jitter_unit VARCHAR,
                shimmer_unit VARCHAR,
                subharmonic_5_12 DOUBLE,
                subharmonic_12_20 DOUBLE,
                subharmonic_20_40 DOUBLE,
                vocal_basal_85_165 DOUBLE,
                spectral_delta_0_4 DOUBLE,
                spectral_theta_4_8 DOUBLE,
                spectral_alpha_8_12 DOUBLE,
                spectral_beta_12_30 DOUBLE,
                spectral_gamma_30_80 DOUBLE,
                spectral_band_index DOUBLE,
                mfcc7_delta DOUBLE,
                mfcc9_delta DOUBLE,
                mfcc7_delta_delta DOUBLE,
                mfcc9_delta_delta DOUBLE,
                cut_trigger VARCHAR,
                cut_summary_anon VARCHAR,
                patient_summary_anon VARCHAR,
                professional_summary_anon VARCHAR,
                patient_word_count INTEGER,
                professional_word_count INTEGER,
                intervention_category VARCHAR,
                patient_response VARCHAR,
                ipm_delta_from_baseline DOUBLE,
                idm_delta_from_baseline DOUBLE,
                dissonance_delta_from_baseline DOUBLE,
                ipm_delta_previous_cut DOUBLE,
                idm_delta_previous_cut DOUBLE,
                dissonance_delta_previous_cut DOUBLE,
                quality_confidence DOUBLE,
                stt_model VARCHAR,
                llm_model VARCHAR,
                algorithm_version VARCHAR,
                audio_quality VARCHAR,
                theme_predominant VARCHAR,
                relevant_dissonances VARCHAR,
                ipm_delta_after_intervention DOUBLE,
                idm_delta_after_intervention DOUBLE,
                dissonance_delta_after_intervention DOUBLE,
                dominant_zone_shift VARCHAR,
                emotional_tone_shift VARCHAR,
                cadence_shift VARCHAR,
                semantic_coherence_shift VARCHAR,
                biomarker_snapshot_json VARCHAR,
                subharmonic_snapshot_json VARCHAR,
                cut_context_json VARCHAR,
                previous_cut_context VARCHAR,
                next_cut_context VARCHAR,
                response_ipm_direction VARCHAR,
                response_idm_direction VARCHAR,
                response_dissonance_direction VARCHAR,
                metrics_version VARCHAR,
                weights_version VARCHAR,
                media_loss_events INTEGER
            )
            """
        )
        _ensure_duckdb_columns(
            conn,
            "anonymous_session_cuts",
            {
                "cut_hash": "VARCHAR",
                "duration_seconds": "INTEGER",
                "relative_position": "DOUBLE",
                "speech_density": "DOUBLE",
                "patient_professional_word_ratio": "DOUBLE",
                "cut_trigger": "VARCHAR",
                "cut_summary_anon": "VARCHAR",
                "patient_summary_anon": "VARCHAR",
                "professional_summary_anon": "VARCHAR",
                "patient_word_count": "INTEGER",
                "professional_word_count": "INTEGER",
                "intervention_category": "VARCHAR",
                "patient_response": "VARCHAR",
                "ipm_delta_from_baseline": "DOUBLE",
                "idm_delta_from_baseline": "DOUBLE",
                "dissonance_delta_from_baseline": "DOUBLE",
                "ipm_delta_previous_cut": "DOUBLE",
                "idm_delta_previous_cut": "DOUBLE",
                "dissonance_delta_previous_cut": "DOUBLE",
                "quality_confidence": "DOUBLE",
                "stt_model": "VARCHAR",
                "llm_model": "VARCHAR",
                "algorithm_version": "VARCHAR",
                "audio_quality": "VARCHAR",
                "theme_predominant": "VARCHAR",
                "relevant_dissonances": "VARCHAR",
                "ipm_delta_after_intervention": "DOUBLE",
                "idm_delta_after_intervention": "DOUBLE",
                "dissonance_delta_after_intervention": "DOUBLE",
                "dominant_zone_shift": "VARCHAR",
                "emotional_tone_shift": "VARCHAR",
                "cadence_shift": "VARCHAR",
                "semantic_coherence_shift": "VARCHAR",
                "biomarker_snapshot_json": "VARCHAR",
                "subharmonic_snapshot_json": "VARCHAR",
                "subharmonic_20_40": "DOUBLE",
                "vocal_basal_85_165": "DOUBLE",
                "spectral_delta_0_4": "DOUBLE",
                "spectral_theta_4_8": "DOUBLE",
                "spectral_alpha_8_12": "DOUBLE",
                "spectral_beta_12_30": "DOUBLE",
                "spectral_gamma_30_80": "DOUBLE",
                "spectral_band_index": "DOUBLE",
                "jitter_proxy_index": "DOUBLE",
                "shimmer_proxy_index": "DOUBLE",
                "jitter_unit": "VARCHAR",
                "shimmer_unit": "VARCHAR",
                "mfcc7_delta": "DOUBLE",
                "mfcc9_delta": "DOUBLE",
                "mfcc7_delta_delta": "DOUBLE",
                "mfcc9_delta_delta": "DOUBLE",
                "cut_context_json": "VARCHAR",
                "previous_cut_context": "VARCHAR",
                "next_cut_context": "VARCHAR",
                "response_ipm_direction": "VARCHAR",
                "response_idm_direction": "VARCHAR",
                "response_dissonance_direction": "VARCHAR",
                "metrics_version": "VARCHAR",
                "weights_version": "VARCHAR",
                "media_loss_events": "INTEGER",
            },
        )
        conn.execute("BEGIN TRANSACTION")
        transaction_started = True
        average = report.get("sessionAverage") or {}
        baseline = report.get("baseline") or {}
        session_summary = report.get("sessionSummary") or {}
        ten_minute_cuts = [
            cut for cut in (report.get("tenMinuteCuts") or []) if isinstance(cut, dict)
        ]
        dominant_zone = average.get("dominantZone") or baseline.get("dominantZone")
        vocal_tension = (
            average.get("jitter")
            or average.get("shimmer")
            or average.get("subharmonic5_12")
            or 0
        )
        cuts_confidence = [_cut_confidence(cut) for cut in ten_minute_cuts]
        confidence_score = (
            sum(cuts_confidence) / len(cuts_confidence) if cuts_confidence else 0.0
        )
        audio_quality = _anonymous_category(
            context.get("audio_quality") or context.get("audioQuality") or "nao_informada",
            "nao_informada",
        )
        consent_research = False
        conn.execute("DELETE FROM anonymous_session_cuts WHERE session_hash = ?", [session_hash])
        try:
            conn.execute("DELETE FROM anonymous_sessions WHERE session_hash = ?", [session_hash])
        except Exception:
            pass
        conn.execute(
            """
            INSERT INTO anonymous_sessions (
                session_hash, age_bucket, gender, ipm_score, dominant_zone, vocal_tension,
                ssri_medication, session_duration, schema_version, created_at,
                session_modality, spoken_language, analysis_language, report_locale,
                session_kind, treatment_phase, session_ordinal,
                interval_since_previous_days, baseline_ipm, baseline_idm, baseline_zone,
                baseline_tone, baseline_words_per_minute, average_idm,
                average_words_per_minute, dissonance_count, cuts_count,
                clinical_notes_count, summary_theme, summary_text_anon, stt_model,
                llm_model, algorithm_version, audio_quality, media_interruptions,
                confidence_score, consent_anonymous_research
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session_hash,
                _anonymous_age_bucket(context.get("age_bucket") or context.get("ageBucket")),
                _anonymous_category(context.get("gender") or "unknown", "unknown"),
                _safe_float(average.get("ipmAvg")),
                _safe_int(dominant_zone),
                _safe_float(vocal_tension),
                _safe_bool(context.get("ssri_medication") or context.get("ssriMedication"), False),
                _safe_int(report.get("durationSeconds")),
                "anonymous_datamart_v3",
                _safe_str(report.get("createdAt") or datetime.now(timezone.utc).isoformat(), 80),
                _anonymous_category(context.get("session_modality") or context.get("sessionModality") or "unknown", "unknown"),
                normalize_session_locale(context.get("spoken_language") or context.get("spokenLanguage") or report.get("spokenLanguage")),
                normalize_session_locale(context.get("analysis_language") or context.get("analysisLanguage") or report.get("analysisLanguage")),
                normalize_session_locale(context.get("report_locale") or context.get("reportLocale") or report.get("reportLocale")),
                _anonymous_category(context.get("session_kind") or context.get("sessionKind") or "seguimento", "seguimento"),
                _anonymous_category(context.get("treatment_phase") or context.get("treatmentPhase") or "nao_informada", "nao_informada"),
                _safe_int(context.get("session_ordinal") or context.get("sessionOrdinal")),
                _safe_float(context.get("interval_since_previous_days") or context.get("intervalSincePreviousDays")),
                _safe_float(baseline.get("ipmAvg")),
                _safe_float(baseline.get("idmAvg")),
                _safe_int(baseline.get("dominantZone")),
                _anonymous_category(baseline.get("emotionalTone") or ""),
                _safe_float(baseline.get("wordsPerMinute")),
                _safe_float(average.get("idmAvg")),
                _safe_float(average.get("wordsPerMinute")),
                _safe_int(average.get("dissonanceCount")),
                len(ten_minute_cuts),
                len(report.get("clinicalNotes") or []),
                _anonymous_category(session_summary.get("theme") or average.get("theme") or ""),
                "",
                _safe_technical_id(context.get("stt_model") or context.get("sttModel") or OPENAI_TRANSCRIBE_MODEL, OPENAI_TRANSCRIBE_MODEL),
                _safe_technical_id(context.get("llm_model") or context.get("llmModel") or FROID_EXPLICA_MODEL, FROID_EXPLICA_MODEL),
                _safe_technical_id(context.get("algorithm_version") or context.get("algorithmVersion") or FROID_ALGORITHM_VERSION, FROID_ALGORITHM_VERSION, 80),
                audio_quality,
                _safe_int(context.get("media_interruptions") or context.get("mediaInterruptions")),
                _safe_float(confidence_score),
                consent_research,
            ],
        )
        conn.execute(
            """
            UPDATE anonymous_sessions SET
                session_type = ?, previous_sessions_count = ?,
                delta_ipm_from_session_baseline = ?, delta_idm_from_session_baseline = ?,
                delta_ipm_vs_last3 = ?, delta_idm_vs_last3 = ?,
                delta_ipm_vs_historical = ?, delta_idm_vs_historical = ?,
                longitudinal_trend = ?, emotional_stability = ?,
                recurring_themes = ?, recurring_zones = ?, recurring_risks = ?,
                metrics_version = ?, weights_version = ?, privacy_tier = ?,
                pii_excluded = ?, raw_audio_retained = ?, literal_transcript_retained = ?,
                media_loss_events = ?, average_spectral_beta = ?,
                average_spectral_gamma = ?, average_spectral_band_index = ?,
                average_mfcc7_delta = ?, average_mfcc9_delta_delta = ?,
                baseline_spectral_beta = ?, baseline_spectral_gamma = ?
            WHERE session_hash = ?
            """,
            [
                _anonymous_category(
                    context.get("session_type")
                    or context.get("sessionType")
                    or context.get("session_kind")
                    or context.get("sessionKind")
                    or "seguimento",
                    "seguimento",
                ),
                _safe_int(context.get("previous_sessions_count") or context.get("previousSessionsCount")),
                _safe_float(context.get("delta_ipm_from_session_baseline") or context.get("deltaIpmFromSessionBaseline")),
                _safe_float(context.get("delta_idm_from_session_baseline") or context.get("deltaIdmFromSessionBaseline")),
                _safe_float(context.get("delta_ipm_vs_last3") or context.get("deltaIpmVsLast3")),
                _safe_float(context.get("delta_idm_vs_last3") or context.get("deltaIdmVsLast3")),
                _safe_float(context.get("delta_ipm_vs_historical") or context.get("deltaIpmVsHistorical")),
                _safe_float(context.get("delta_idm_vs_historical") or context.get("deltaIdmVsHistorical")),
                _anonymous_category(context.get("longitudinal_trend") or context.get("longitudinalTrend") or "nao_apurado", "nao_apurado"),
                _anonymous_category(context.get("emotional_stability") or context.get("emotionalStability") or "nao_apurada", "nao_apurada"),
                _safe_str(json.dumps(_anonymous_category_list(context.get("recurring_themes") or context.get("recurringThemes") or []), ensure_ascii=False), 1200),
                _safe_str(json.dumps(_anonymous_category_list(context.get("recurring_zones") or context.get("recurringZones") or []), ensure_ascii=False), 1200),
                _safe_str(json.dumps(_anonymous_category_list(context.get("recurring_risks") or context.get("recurringRisks") or []), ensure_ascii=False), 1200),
                _safe_technical_id(
                    context.get("metrics_version") or context.get("metricsVersion") or "froid-metrics-v3",
                    "froid-metrics-v3",
                    80,
                ),
                _safe_technical_id(
                    context.get("weights_version") or context.get("weightsVersion") or "froid-weights-v1",
                    "froid-weights-v1",
                    80,
                ),
                "anonymous_research_datamart",
                True,
                False,
                False,
                _safe_int(context.get("media_loss_events") or context.get("mediaLossEvents") or context.get("media_interruptions") or context.get("mediaInterruptions")),
                _safe_float(average.get("spectralBeta12_30")),
                _safe_float(average.get("spectralGamma30_80")),
                _safe_float(average.get("spectralBandIndex")),
                _safe_float(average.get("mfcc7Delta")),
                _safe_float(average.get("mfcc9DeltaDelta")),
                _safe_float(baseline.get("spectralBeta12_30")),
                _safe_float(baseline.get("spectralGamma30_80")),
                session_hash,
            ],
        )
        conn.execute(
            "UPDATE anonymous_sessions SET ingestion_basis='post_anonymization' WHERE session_hash=?",
            [session_hash],
        )
        previous_cut: Optional[dict] = None
        for index, cut in enumerate(ten_minute_cuts):
            start_second = _safe_int(cut.get("startSecond"))
            end_second = _safe_int(cut.get("endSecond"))
            start_minute = int(start_second / 60)
            end_minute = max(start_minute + 1, int(round(end_second / 60)))
            summary = _summary_for_cut(report, start_minute, end_minute)
            transcript = _transcript_for_range(report, start_second, end_second)
            patient_text = _speaker_text(transcript, "PC")
            professional_text = _speaker_text(transcript, "DR.")
            if not patient_text and not professional_text:
                patient_text = transcript
            patient_word_count = _word_count(patient_text)
            professional_word_count = _word_count(professional_text)
            duration_seconds = max(1, end_second - start_second)
            relative_position = (
                round(start_second / max(1, _safe_int(report.get("durationSeconds"))), 4)
                if _safe_int(report.get("durationSeconds")) > 0
                else 0.0
            )
            speech_density = round(
                (patient_word_count + professional_word_count) / max(1.0, duration_seconds / 60.0),
                3,
            )
            patient_professional_word_ratio = round(
                patient_word_count / max(1, professional_word_count),
                3,
            )
            cut_hash = _anonymous_cut_hash(session_hash, index, start_second, end_second)
            cut_context = {}
            if isinstance(context.get("cuts"), list) and index < len(context.get("cuts") or []):
                maybe_cut_context = (context.get("cuts") or [])[index]
                if isinstance(maybe_cut_context, dict):
                    cut_context = maybe_cut_context
            intervention_category = _anonymous_category(
                cut_context.get("intervention_category")
                or cut_context.get("interventionCategory")
                or _infer_intervention_category(professional_text),
                "intervencao_geral",
            )
            patient_response = _anonymous_category(
                cut_context.get("patient_response")
                or cut_context.get("patientResponse")
                or _infer_patient_response(cut, previous_cut, baseline),
                "estabilidade",
            )
            baseline_dissonance = _safe_float(baseline.get("dissonanceCount"))
            previous_ipm = _safe_float((previous_cut or {}).get("ipmAvg"), _safe_float(baseline.get("ipmAvg")))
            previous_idm = _safe_float((previous_cut or {}).get("idmAvg"), _safe_float(baseline.get("idmAvg")))
            previous_dissonance = _safe_float((previous_cut or {}).get("dissonanceCount"), baseline_dissonance)
            conn.execute(
                """
                INSERT INTO anonymous_session_cuts (
                    session_hash, cut_index, cut_label, start_second, end_second,
                    sample_count, ipm_avg, idm_avg, dominant_zone, dominant_theme,
                    coherence_status, emotional_tone, words_per_minute, theme,
                    dissonance_count, mfcc7, mfcc9, f0_mean, zcr, jitter, shimmer,
                    subharmonic_5_12, subharmonic_12_20, subharmonic_20_40,
                    vocal_basal_85_165, spectral_delta_0_4, spectral_theta_4_8,
                    spectral_alpha_8_12, spectral_beta_12_30, spectral_gamma_30_80,
                    spectral_band_index, mfcc7_delta, mfcc9_delta,
                    mfcc7_delta_delta, mfcc9_delta_delta, cut_trigger,
                    cut_summary_anon, patient_summary_anon, professional_summary_anon,
                    patient_word_count, professional_word_count, intervention_category,
                    patient_response, ipm_delta_from_baseline, idm_delta_from_baseline,
                    dissonance_delta_from_baseline, ipm_delta_previous_cut,
                    idm_delta_previous_cut, dissonance_delta_previous_cut,
                    quality_confidence, stt_model, llm_model, algorithm_version, audio_quality
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    session_hash,
                    index,
                    _anonymous_category(cut.get("label") or "", "cut"),
                    start_second,
                    end_second,
                    _safe_int(cut.get("sampleCount")),
                    _safe_float(cut.get("ipmAvg")),
                    _safe_float(cut.get("idmAvg")),
                    _safe_int(cut.get("dominantZone")),
                    _anonymous_category(cut.get("dominantTheme") or ""),
                    _anonymous_category(cut.get("coherenceStatus") or ""),
                    _anonymous_category(cut.get("emotionalTone") or ""),
                    _safe_float(cut.get("wordsPerMinute")),
                    _anonymous_category(cut.get("theme") or ""),
                    _safe_int(cut.get("dissonanceCount")),
                    _safe_float(cut.get("mfcc7")),
                    _safe_float(cut.get("mfcc9")),
                    _safe_float(cut.get("f0Mean")),
                    _safe_float(cut.get("zcr")),
                    _safe_float(cut.get("jitter")),
                    _safe_float(cut.get("shimmer")),
                    _safe_float(cut.get("subharmonic5_12")),
                    _safe_float(cut.get("subharmonic12_20")),
                    _safe_float(cut.get("subharmonic20_40")),
                    _safe_float(cut.get("vocalBasal85_165")),
                    _safe_float(cut.get("spectralDelta0_4")),
                    _safe_float(cut.get("spectralTheta4_8")),
                    _safe_float(cut.get("spectralAlpha8_12")),
                    _safe_float(cut.get("spectralBeta12_30")),
                    _safe_float(cut.get("spectralGamma30_80")),
                    _safe_float(cut.get("spectralBandIndex")),
                    _safe_float(cut.get("mfcc7Delta")),
                    _safe_float(cut.get("mfcc9Delta")),
                    _safe_float(cut.get("mfcc7DeltaDelta")),
                    _safe_float(cut.get("mfcc9DeltaDelta")),
                    _anonymous_category(cut_context.get("cut_trigger") or cut_context.get("cutTrigger") or "automatico", "automatico"),
                    "",
                    "",
                    "",
                    patient_word_count,
                    professional_word_count,
                    intervention_category,
                    patient_response,
                    _safe_float(cut.get("ipmAvg")) - _safe_float(baseline.get("ipmAvg")),
                    _safe_float(cut.get("idmAvg")) - _safe_float(baseline.get("idmAvg")),
                    _safe_float(cut.get("dissonanceCount")) - baseline_dissonance,
                    _safe_float(cut.get("ipmAvg")) - previous_ipm,
                    _safe_float(cut.get("idmAvg")) - previous_idm,
                    _safe_float(cut.get("dissonanceCount")) - previous_dissonance,
                    _cut_confidence(cut),
                    _safe_technical_id(cut_context.get("stt_model") or cut_context.get("sttModel") or OPENAI_TRANSCRIBE_MODEL, OPENAI_TRANSCRIBE_MODEL),
                    _safe_technical_id(cut_context.get("llm_model") or cut_context.get("llmModel") or FROID_EXPLICA_MODEL, FROID_EXPLICA_MODEL),
                    _safe_technical_id(cut_context.get("algorithm_version") or cut_context.get("algorithmVersion") or FROID_ALGORITHM_VERSION, FROID_ALGORITHM_VERSION, 80),
                    _anonymous_category(cut_context.get("audio_quality") or cut_context.get("audioQuality") or audio_quality, "nao_informada"),
                ],
            )
            biomarker_snapshot = {
                "mfcc7": cut.get("mfcc7"),
                "mfcc9": cut.get("mfcc9"),
                "mfcc7_delta": cut.get("mfcc7Delta"),
                "mfcc9_delta": cut.get("mfcc9Delta"),
                "mfcc7_delta_delta": cut.get("mfcc7DeltaDelta"),
                "mfcc9_delta_delta": cut.get("mfcc9DeltaDelta"),
                "f0_mean": cut.get("f0Mean"),
                "zcr": cut.get("zcr"),
                "jitter": cut.get("jitter"),
                "shimmer": cut.get("shimmer"),
                "jitter_proxy_index": cut.get("jitter"),
                "shimmer_proxy_index": cut.get("shimmer"),
                "jitter_unit": "internal_proxy_0_1_zcr_scaled",
                "shimmer_unit": "internal_proxy_0_1_envelope_cv",
                "spectral_delta_0_4": cut.get("spectralDelta0_4"),
                "spectral_theta_4_8": cut.get("spectralTheta4_8"),
                "spectral_alpha_8_12": cut.get("spectralAlpha8_12"),
                "spectral_beta_12_30": cut.get("spectralBeta12_30"),
                "spectral_gamma_30_80": cut.get("spectralGamma30_80"),
                "spectral_band_index": cut.get("spectralBandIndex"),
            }
            subharmonic_snapshot = {
                "subharmonic_5_12": cut.get("subharmonic5_12"),
                "subharmonic_12_20": cut.get("subharmonic12_20"),
                "subharmonic_20_40": cut.get("subharmonic20_40"),
                "vocal_basal_85_165": cut.get("vocalBasal85_165"),
                "dna_infrasound_nuclear": cut.get("dnaInfrasoundNuclear"),
                "dna_limbic_modulation": cut.get("dnaLimbicModulation"),
                "dna_vocal_basal_tension": cut.get("dnaVocalBasalTension"),
                "dna_autonomic_flooding": cut.get("dnaAutonomicFlooding"),
                "dna_dissociative_shutdown": cut.get("dnaDissociativeShutdown"),
                "dna_neurogenic_resonance": cut.get("dnaNeurogenicResonance"),
                "dna_somatoaffective_dissonance": cut.get("dnaSomatoaffectiveDissonance"),
                "dna_subharmonic_index": cut.get("dnaSubharmonicIndex"),
            }
            previous_context_label = f"cut_{index - 1}" if previous_cut else "baseline"
            next_cut = ten_minute_cuts[index + 1] if index + 1 < len(ten_minute_cuts) else None
            next_context_label = (
                f"cut_{index + 1}"
                if isinstance(next_cut, dict)
                else "fim_sessao"
            )
            cut_context_vector = {
                "schema": "anonymous_cut_context_v1",
                "cut_hash": cut_hash,
                "cut_index": index,
                "cut_label": _anonymous_category(cut.get("label") or "", "cut"),
                "time": {
                    "start_second": start_second,
                    "end_second": end_second,
                    "duration_seconds": duration_seconds,
                    "relative_position": relative_position,
                    "trigger": _anonymous_category(cut_context.get("cut_trigger") or cut_context.get("cutTrigger") or "automatico", "automatico"),
                },
                "semantic": {
                    "theme": _anonymous_category(cut.get("theme") or ""),
                    "theme_predominant": _anonymous_category(cut_context.get("theme_predominant") or cut_context.get("themePredominant") or cut.get("theme") or ""),
                    "coherence_status": _anonymous_category(cut.get("coherenceStatus") or ""),
                    "patient_word_count": patient_word_count,
                    "professional_word_count": professional_word_count,
                    "speech_density": speech_density,
                    "patient_professional_word_ratio": patient_professional_word_ratio,
                },
                "intervention": {
                    "category": intervention_category,
                    "patient_response": patient_response,
                    "response_ipm_direction": _anonymous_category(cut_context.get("response_ipm_direction") or cut_context.get("responseIpmDirection") or "nao_apurado", "nao_apurado"),
                    "response_idm_direction": _anonymous_category(cut_context.get("response_idm_direction") or cut_context.get("responseIdmDirection") or "nao_apurado", "nao_apurado"),
                    "response_dissonance_direction": _anonymous_category(cut_context.get("response_dissonance_direction") or cut_context.get("responseDissonanceDirection") or "nao_apurado", "nao_apurado"),
                },
                "metrics": {
                    "ipm_avg": cut.get("ipmAvg"),
                    "idm_avg": cut.get("idmAvg"),
                    "dominant_zone": cut.get("dominantZone"),
                    "dominant_theme": _anonymous_category(cut.get("dominantTheme") or ""),
                    "emotional_tone": _anonymous_category(cut.get("emotionalTone") or ""),
                    "words_per_minute": cut.get("wordsPerMinute"),
                    "dissonance_count": cut.get("dissonanceCount"),
                    "jitter_proxy_index": cut.get("jitter"),
                    "shimmer_proxy_index": cut.get("shimmer"),
                    "jitter_unit": "internal_proxy_0_1_zcr_scaled",
                    "shimmer_unit": "internal_proxy_0_1_envelope_cv",
                    "spectral_band_context": "voice_modulation_not_eeg",
                    "spectral_delta_0_4": cut.get("spectralDelta0_4"),
                    "spectral_theta_4_8": cut.get("spectralTheta4_8"),
                    "spectral_alpha_8_12": cut.get("spectralAlpha8_12"),
                    "spectral_beta_12_30": cut.get("spectralBeta12_30"),
                    "spectral_gamma_30_80": cut.get("spectralGamma30_80"),
                    "spectral_band_index": cut.get("spectralBandIndex"),
                    "mfcc7_delta": cut.get("mfcc7Delta"),
                    "mfcc9_delta": cut.get("mfcc9Delta"),
                    "mfcc7_delta_delta": cut.get("mfcc7DeltaDelta"),
                    "mfcc9_delta_delta": cut.get("mfcc9DeltaDelta"),
                    "quality_confidence": _cut_confidence(cut),
                },
                "deltas": {
                    "ipm_from_baseline": _safe_float(cut.get("ipmAvg")) - _safe_float(baseline.get("ipmAvg")),
                    "idm_from_baseline": _safe_float(cut.get("idmAvg")) - _safe_float(baseline.get("idmAvg")),
                    "dissonance_from_baseline": _safe_float(cut.get("dissonanceCount")) - baseline_dissonance,
                    "ipm_previous_cut": _safe_float(cut.get("ipmAvg")) - previous_ipm,
                    "idm_previous_cut": _safe_float(cut.get("idmAvg")) - previous_idm,
                    "dissonance_previous_cut": _safe_float(cut.get("dissonanceCount")) - previous_dissonance,
                },
                "bioacoustics": biomarker_snapshot,
                "subharmonics": subharmonic_snapshot,
                "context_links": {
                    "previous_cut_context": previous_context_label,
                    "next_cut_context": next_context_label,
                },
                "quality": {
                    "audio_quality": _anonymous_category(cut_context.get("audio_quality") or cut_context.get("audioQuality") or audio_quality, "nao_informada"),
                    "media_loss_events": _safe_int(cut_context.get("media_loss_events") or cut_context.get("mediaLossEvents") or context.get("media_loss_events") or context.get("mediaLossEvents")),
                    "stt_model": _safe_technical_id(cut_context.get("stt_model") or cut_context.get("sttModel") or OPENAI_TRANSCRIBE_MODEL, OPENAI_TRANSCRIBE_MODEL),
                    "llm_model": _safe_technical_id(cut_context.get("llm_model") or cut_context.get("llmModel") or FROID_EXPLICA_MODEL, FROID_EXPLICA_MODEL),
                    "algorithm_version": _safe_technical_id(cut_context.get("algorithm_version") or cut_context.get("algorithmVersion") or FROID_ALGORITHM_VERSION, FROID_ALGORITHM_VERSION, 80),
                },
            }
            conn.execute(
                """
                UPDATE anonymous_session_cuts SET
                    cut_hash = ?, duration_seconds = ?, relative_position = ?,
                    speech_density = ?, patient_professional_word_ratio = ?,
                    theme_predominant = ?, relevant_dissonances = ?,
                    ipm_delta_after_intervention = ?,
                    idm_delta_after_intervention = ?, dissonance_delta_after_intervention = ?,
                    dominant_zone_shift = ?, emotional_tone_shift = ?, cadence_shift = ?,
                    semantic_coherence_shift = ?, biomarker_snapshot_json = ?,
                    subharmonic_snapshot_json = ?, cut_context_json = ?,
                    jitter_proxy_index = ?, shimmer_proxy_index = ?,
                    jitter_unit = ?, shimmer_unit = ?,
                    previous_cut_context = ?, next_cut_context = ?, response_ipm_direction = ?,
                    response_idm_direction = ?, response_dissonance_direction = ?,
                    metrics_version = ?, weights_version = ?, media_loss_events = ?
                WHERE session_hash = ? AND cut_index = ?
                """,
                [
                    cut_hash,
                    duration_seconds,
                    relative_position,
                    speech_density,
                    patient_professional_word_ratio,
                    _anonymous_category(cut_context.get("theme_predominant") or cut_context.get("themePredominant") or cut.get("theme") or ""),
                    "",
                    _safe_float(cut_context.get("ipm_delta_after_intervention") or cut_context.get("ipmDeltaAfterIntervention")),
                    _safe_float(cut_context.get("idm_delta_after_intervention") or cut_context.get("idmDeltaAfterIntervention")),
                    _safe_float(cut_context.get("dissonance_delta_after_intervention") or cut_context.get("dissonanceDeltaAfterIntervention")),
                    _anonymous_category(cut_context.get("dominant_zone_shift") or cut_context.get("dominantZoneShift") or "nao_apurado", "nao_apurado"),
                    _anonymous_category(cut_context.get("emotional_tone_shift") or cut_context.get("emotionalToneShift") or "nao_apurado", "nao_apurado"),
                    _anonymous_category(cut_context.get("cadence_shift") or cut_context.get("cadenceShift") or "nao_apurado", "nao_apurado"),
                    _anonymous_category(cut_context.get("semantic_coherence_shift") or cut_context.get("semanticCoherenceShift") or "nao_apurado", "nao_apurado"),
                    _safe_str(json.dumps(biomarker_snapshot, ensure_ascii=False, sort_keys=True), 1200),
                    _safe_str(json.dumps(subharmonic_snapshot, ensure_ascii=False, sort_keys=True), 1200),
                    _safe_str(json.dumps(cut_context_vector, ensure_ascii=False, sort_keys=True), 6000),
                    _safe_float(cut.get("jitter")),
                    _safe_float(cut.get("shimmer")),
                    "internal_proxy_0_1_zcr_scaled",
                    "internal_proxy_0_1_envelope_cv",
                    _safe_str(previous_context_label, 240),
                    _safe_str(next_context_label, 240),
                    _anonymous_category(cut_context.get("response_ipm_direction") or cut_context.get("responseIpmDirection") or "nao_apurado", "nao_apurado"),
                    _anonymous_category(cut_context.get("response_idm_direction") or cut_context.get("responseIdmDirection") or "nao_apurado", "nao_apurado"),
                    _anonymous_category(cut_context.get("response_dissonance_direction") or cut_context.get("responseDissonanceDirection") or "nao_apurado", "nao_apurado"),
                    _safe_technical_id(cut_context.get("metrics_version") or cut_context.get("metricsVersion") or context.get("metrics_version") or context.get("metricsVersion") or "froid-metrics-v3", "froid-metrics-v3", 80),
                    _safe_technical_id(cut_context.get("weights_version") or cut_context.get("weightsVersion") or context.get("weights_version") or context.get("weightsVersion") or "froid-weights-v1", "froid-weights-v1", 80),
                    _safe_int(cut_context.get("media_loss_events") or cut_context.get("mediaLossEvents") or context.get("media_loss_events") or context.get("mediaLossEvents")),
                    session_hash,
                    index,
                ],
            )
            previous_cut = cut
        conn.execute(
            "DELETE FROM privacy_ingestion_audit WHERE session_hash=?",
            [session_hash],
        )
        conn.execute(
            "INSERT INTO privacy_ingestion_audit VALUES (?, true, 'approved', ?, 'data-froid-privacy-v3')",
            [session_hash, datetime.now(timezone.utc).isoformat()],
        )
        conn.execute("COMMIT")
        transaction_started = False
        conn.close()
    except Exception as exc:
        try:
            if conn is not None:
                if transaction_started:
                    conn.execute("ROLLBACK")
                conn.close()
            if session_hash and os.path.exists(FROID_DUCKDB_PATH):
                import duckdb
                audit_connection = duckdb.connect(database=FROID_DUCKDB_PATH, read_only=False)
                audit_connection.execute(
                    "DELETE FROM privacy_ingestion_audit WHERE session_hash=?",
                    [session_hash],
                )
                audit_connection.execute(
                    "INSERT INTO privacy_ingestion_audit VALUES (?, false, ?, ?, 'data-froid-privacy-v3')",
                    [session_hash, type(exc).__name__, datetime.now(timezone.utc).isoformat()],
                )
                audit_connection.close()
        except Exception:
            LOGGER.exception("Unable to record Data-FROID quarantine event")
        LOGGER.exception("Data-FROID anonymization gate rejected session")


def _attach_metrics_analysis(report: dict) -> dict:
    try:
        report["metricsAnalysis"] = calculate_report_metrics(report)
        report.pop("metricsAnalysisError", None)
    except Exception as exc:
        report["metricsAnalysisError"] = str(exc)
    return report


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


class RtcSignalManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str, role: str):
        await websocket.accept()
        room = self.rooms.setdefault(session_id, {})
        old_socket = room.get(role)
        if old_socket and old_socket is not websocket:
            try:
                await old_socket.close(code=4000)
            except Exception:
                pass
        room[role] = websocket
        peer_role = "patient" if role == "professional" else "professional"
        peer_socket = room.get(peer_role)
        await websocket.send_json(
            {
                "type": "signal-ready",
                "role": role,
                "peer_connected": bool(peer_socket),
            }
        )
        if peer_socket:
            await self._safe_send(
                peer_socket,
                {"type": "peer-joined", "role": role},
            )

    def disconnect(self, session_id: str, role: str, websocket: WebSocket):
        room = self.rooms.get(session_id)
        if not room or room.get(role) is not websocket:
            return None
        del room[role]
        peer_role = "patient" if role == "professional" else "professional"
        peer_socket = room.get(peer_role)
        if not room:
            self.rooms.pop(session_id, None)
        return peer_socket

    def role_connected(self, session_id: str, role: str) -> bool:
        return bool((self.rooms.get(session_id) or {}).get(role))

    async def relay(self, session_id: str, role: str, message: dict):
        room = self.rooms.get(session_id) or {}
        peer_role = "patient" if role == "professional" else "professional"
        peer_socket = room.get(peer_role)
        if not peer_socket:
            own_socket = room.get(role)
            if own_socket:
                await self._safe_send(own_socket, {"type": "peer-waiting"})
            return
        payload = dict(message or {})
        payload["from"] = role
        if await self._safe_send(peer_socket, payload):
            return
        if room.get(peer_role) is peer_socket:
            del room[peer_role]
        own_socket = room.get(role)
        if own_socket:
            await self._safe_send(own_socket, {"type": "peer-waiting"})

    async def _safe_send(self, websocket: WebSocket, payload: dict):
        try:
            await websocket.send_json(payload)
            return True
        except Exception:
            return False


rtc_signals = RtcSignalManager()


@app.get("/api/rtc/config")
async def rtc_configuration(
    request: Request,
    session_id: str = "",
    invite: str = "",
):
    professional = _current_user_from_request(request)
    invite_record = SESSION_INVITES.get(invite) if invite else None
    patient_authorized = bool(
        invite_record
        and invite_record.get("status") == "accepted"
        and str(invite_record.get("session_id") or "") == session_id
    )
    professional_authorized = bool(
        professional
        and session_id
        and _normalize_email(SESSION_OWNERS.get(session_id) or "")
        == _normalize_email(professional.get("email") or "")
    )
    if not patient_authorized and not professional_authorized:
        raise HTTPException(status_code=401, detail="acesso RTC não autorizado")
    ice_servers: list[dict[str, Any]] = [
        {"urls": ["stun:stun.l.google.com:19302"]}
    ]
    expires_at = 0
    if FROID_TURN_URLS and FROID_TURN_SECRET:
        expires_at = int(time.time()) + FROID_TURN_CREDENTIAL_TTL_SECONDS
        username = f"{expires_at}:{secrets.token_urlsafe(8)}"
        credential = base64.b64encode(
            hmac.new(
                FROID_TURN_SECRET.encode("utf-8"),
                username.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("ascii")
        ice_servers.append(
            {
                "urls": FROID_TURN_URLS,
                "username": username,
                "credential": credential,
                "credentialType": "password",
            }
        )
    return JSONResponse(
        content={
            "iceServers": ice_servers,
            "iceTransportPolicy": (
                FROID_ICE_TRANSPORT_POLICY
                if FROID_TURN_URLS and FROID_TURN_SECRET
                else "all"
            ),
            "turnConfigured": bool(FROID_TURN_URLS and FROID_TURN_SECRET),
            "credentialExpiresAt": expires_at,
        },
        headers={"Cache-Control": "no-store, max-age=0"},
    )


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


def _transcribe_sync(
    audio_bytes: bytes,
    filename: str,
    prompt: str = "",
    spoken_locale: str = "pt-BR",
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    kwargs = {
        "model": OPENAI_TRANSCRIBE_MODEL,
        "file": audio_file,
        "language": session_language(spoken_locale).provider_language,
        "response_format": "json",
        "temperature": 0,
    }
    if prompt:
        kwargs["prompt"] = prompt
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


def _record_session_event(event_type: str, invite: dict, extra: dict | None = None) -> dict:
    global SESSION_EVENT_COUNTER
    SESSION_EVENT_COUNTER += 1
    event = {
        "id": SESSION_EVENT_COUNTER,
        "type": event_type,
        "session_id": invite.get("session_id"),
        "invite_id": invite.get("id"),
        "professional_email": _normalize_email(invite.get("professional_email") or ""),
        "organization_id": _invite_organization_id(invite),
        "patient_name": invite.get("patient_name"),
        "patient_known": bool(invite.get("patient_known")),
        "created_at": _utc_now_iso(),
    }
    if extra:
        event.update(extra)
    SESSION_EVENTS.append(event)
    if len(SESSION_EVENTS) > 500:
        del SESSION_EVENTS[: len(SESSION_EVENTS) - 500]
    _save_identity_state()
    return event


def _digits_only(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        str(salt or "").encode("utf-8"),
        120_000,
    ).hex()


def _set_patient_password(patient: dict, password: str) -> None:
    salt = secrets.token_hex(16)
    patient["password_salt"] = salt
    patient["password_hash"] = _password_hash(password, salt)
    patient["password_set_at"] = _utc_now_iso()


def _verify_patient_password(patient: dict, password: str) -> bool:
    if not isinstance(patient, dict):
        return False
    salt = str(patient.get("password_salt") or "")
    expected = str(patient.get("password_hash") or "")
    if not salt or not expected or not password:
        return False
    return secrets.compare_digest(_password_hash(password, salt), expected)


def _issue_patient_portal_session(
    patient: dict, auth_provider: str = "password"
) -> dict:
    token = secrets.token_urlsafe(32)
    patient_session = {
        **_patient_public_identity(patient),
        "role": "patient",
        "_auth_provider": str(auth_provider or "password"),
        "issued_at": _utc_now_iso(),
        "_session_expires_at": datetime.now(timezone.utc).timestamp()
        + FROID_PATIENT_SESSION_TTL_SECONDS,
    }
    PATIENT_PORTAL_SESSIONS[token] = patient_session
    return {"token": token, "patient": _patient_public_identity(patient_session)}


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
    if not base.endswith("/app"):
        base = f"{base}/app"
    return f"{base}/#/convite/{token}"


def _public_patient_session_url(base_url: str, session_id: str, token: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        base = os.getenv("FROID_PUBLIC_URL", "http://localhost:5173").rstrip("/")
    if not base.endswith("/app"):
        base = f"{base}/app"
    return f"{base}/#/paciente/sessao/{session_id}?invite={token}"


def _consent_hash(payload: dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _legal_audit_key_configured() -> bool:
    return len(FROID_LEGAL_AUDIT_HMAC_KEY.encode("utf-8")) >= 32


def _legal_hmac(value: str) -> str:
    if not _legal_audit_key_configured():
        return ""
    return hmac.new(
        FROID_LEGAL_AUDIT_HMAC_KEY.encode("utf-8"),
        str(value or "").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _legal_request_fingerprint(request: Request) -> str:
    remote = request.client.host if request.client else ""
    agent = request.headers.get("user-agent", "")[:1000]
    return _legal_hmac(f"{remote}|{agent}")


def _normalize_legal_jurisdiction(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    token = normalized.strip().lower().replace("_", "-")
    if token in {"es", "es-es", "esp", "espanha", "espana", "spain"}:
        return "ES"
    if token in {"fr", "fr-fr", "franca", "france"}:
        return "FR"
    if token in {"us", "en-us", "usa", "estados unidos", "united states", "united states of america"}:
        return "US"
    return "BR"


def _legal_acceptance_required(jurisdiction: object) -> bool:
    return FROID_LEGAL_ACCEPTANCE_REQUIRED_BY_JURISDICTION.get(
        _normalize_legal_jurisdiction(jurisdiction),
        False,
    )


def _validated_legal_acceptances(
    payload: object, account_type: str, *, required: bool
) -> dict[str, dict]:
    submitted = payload if isinstance(payload, dict) else {}
    catalog = public_legal_catalog()
    if required and not (
        catalog["supplier"].get("configured")
        and _legal_audit_key_configured()
        and TENANT_STORE.enabled
    ):
        raise HTTPException(
            status_code=503,
            detail="configuração jurídica do fornecedor incompleta",
        )
    documents = catalog["documents"]
    accepted: dict[str, dict] = {}
    for key in required_document_keys(account_type):
        candidate = submitted.get(key) if isinstance(submitted.get(key), dict) else {}
        document = documents[key]
        valid = (
            candidate.get("accepted") is True
            and candidate.get("version") == document["version"]
            and candidate.get("sha256") == document["sha256"]
        )
        if required and not valid:
            raise HTTPException(
                status_code=428,
                detail=f"aceite jurídico atual obrigatório: {key}",
            )
        if valid:
            accepted[key] = {
                "version": document["version"],
                "sha256": document["sha256"],
                "accepted_at": _utc_now_iso(),
            }
    return accepted


def _record_legal_documents(
    *, request: Request, subject_reference: str, subject_kind: str,
    organization_id: str, acceptances: dict[str, dict], context: str,
    commercial_snapshot: Optional[dict] = None,
) -> None:
    subject_hash = _legal_hmac(subject_reference)
    if not subject_hash:
        # `_legal_hmac` devolve vazio quando FROID_LEGAL_AUDIT_HMAC_KEY tem
        # menos de 32 bytes. Sair em silencio aqui gravava o cadastro com
        # sucesso e o aceite em lugar nenhum: a pessoa marca a caixa, a tela
        # confirma, e nao existe prova de que marcou. E o defeito que so
        # aparece quando alguem pede o comprovante — meses depois, e do lado
        # errado de uma discussao.
        #
        # /ready ja publica `legal_audit_hmac_configured`; o que faltava era o
        # caminho de gravacao recusar em vez de seguir.
        raise HTTPException(
            status_code=503,
            detail=(
                "registro de aceite indisponivel: FROID_LEGAL_AUDIT_HMAC_KEY "
                "precisa ter ao menos 32 bytes no servidor. O cadastro nao foi "
                "concluido para nao produzir contratacao sem prova de aceite."
            ),
        )
    fingerprint = _legal_request_fingerprint(request)
    for key, acceptance in acceptances.items():
        TENANT_STORE.record_legal_acceptance(
            organization_id=organization_id,
            subject_kind=subject_kind,
            subject_reference_hash=subject_hash,
            document_key=key,
            document_version=str(acceptance.get("version") or ""),
            document_sha256=str(acceptance.get("sha256") or ""),
            acceptance_context=context,
            commercial_snapshot=commercial_snapshot or {},
            request_fingerprint_hash=fingerprint,
            accepted_at=str(acceptance.get("accepted_at") or ""),
        )


def _patient_consent_preferences(patient: dict) -> dict:
    preferences = patient.get("consent_preferences")
    if isinstance(preferences, dict) and preferences:
        return dict(preferences)
    patient_id = str(patient.get("id") or "")
    for entry in reversed(CONSENT_LEDGER):
        if str(entry.get("patient_id") or "") == patient_id:
            consent = entry.get("consent")
            if isinstance(consent, dict) and consent:
                return dict(consent)
    return {}


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


def _format_brl(cents: int, currency: str = "brl") -> str:
    cents = max(0, int(cents or 0))
    reais = cents // 100
    centavos = cents % 100
    if str(currency or "").lower() == "usd":
        return f"US$ {reais}.{centavos:02d}"
    if str(currency or "").lower() == "eur":
        return f"€ {reais},{centavos:02d}"
    if str(currency or "").lower() == "cny":
        return f"CNY {reais}.{centavos:02d}"
    return f"R$ {reais},{centavos:02d}"


def _normalize_stripe_currency(value: Any) -> str:
    currency = str(value or "").strip().lower()
    return currency if currency in SUPPORTED_BILLING_CURRENCIES else ""


def _commercial_order_snapshot(
    package_code: str,
    package: dict,
    currency: str,
    commercial_price: dict,
    auto_replenish: bool,
) -> dict:
    return {
        "package_code": package_code,
        "plan_code": str(package["plan_code"]),
        "sessions": int(package["sessions"]),
        "currency": currency,
        "unit_amount_minor": int(commercial_price["unit_amount_minor"]),
        "total_amount_minor": int(commercial_price["total_amount_minor"]),
        "auto_replenish": bool(auto_replenish),
    }


def _commercial_order_sha256(snapshot: dict) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_checkout_legal_metadata(
    metadata: dict,
    *,
    package_code: str,
    package: dict,
    currency: str,
    commercial_price: dict,
    auto_replenish: bool,
) -> None:
    if metadata.get("legal_acceptance_required") != "true":
        return
    expected_snapshot = _commercial_order_snapshot(
        package_code, package, currency, commercial_price, auto_replenish
    )
    if (
        metadata.get("legal_terms_version") != LEGAL_DOCUMENT_VERSION
        or not hmac.compare_digest(
            str(metadata.get("order_sha256") or ""),
            _commercial_order_sha256(expected_snapshot),
        )
    ):
        raise HTTPException(
            status_code=409,
            detail="evidência jurídica do checkout não confere",
        )


def _plan_amount_for_currency(plan: dict, currency: str) -> int:
    prices = plan.get("prices") if isinstance(plan.get("prices"), dict) else {}
    normalized = _normalize_stripe_currency(currency) or _normalize_stripe_currency(plan.get("currency")) or "usd"
    if normalized in prices:
        return max(0, _local_int(prices.get(normalized)))
    return max(0, _local_int(plan.get("amount_cents")))


def _plan_public(plan: dict, currency: str = "") -> dict:
    normalized = _normalize_stripe_currency(currency) or _normalize_stripe_currency(plan.get("currency")) or "usd"
    amount_cents = _plan_amount_for_currency(plan, normalized)
    return {
        **plan,
        "currency": normalized,
        "amount_cents": amount_cents,
        "amount_brl": _format_brl(amount_cents, normalized),
    }


FROID_ACCESS_PLANS = {
    "single_session": {
        "id": "single_session",
        "name": "Sessao avulsa FROID",
        "description": "Credito individual para uma sessao FROID.",
        "session_credits": 1,
        "amount_cents": 0,
        "prices": {"usd": 0, "eur": 0, "brl": 0},
        "currency": "usd",
    },
    "professional_pack_25": {
        "id": "professional_pack_25",
        "name": "Pacote profissional 25 sessoes",
        "description": "Pacote mensal com 25 sessoes FROID.",
        "session_credits": 25,
        "amount_cents": 150,
        "prices": {"usd": 150, "eur": 150, "brl": 800},
        "currency": "usd",
    },
    "developer_pack_25": {
        "id": "developer_pack_25",
        "name": "Pacote desenvolvedor 25 sessoes",
        "description": "Pacote tecnico de desenvolvimento e testes com 25 sessoes.",
        "session_credits": 25,
        "amount_cents": 250,
        "prices": {"usd": 250, "eur": 250, "brl": 1300},
        "currency": "usd",
    },
}


def _apply_session_credit_purchase(
    email: str,
    plan_id: str,
    purchase_type: str,
    contracted_sessions: int,
    bonus_sessions: int,
    total_sessions: int,
    unit_amount_cents: int,
    package_total_cents: int,
    status: str,
    checkout_session_id: str = "",
) -> dict:
    owner_email = _normalize_email(email)
    if not owner_email:
        return {}
    profile = PROFESSIONAL_PROFILES.get(owner_email)
    if not isinstance(profile, dict):
        return {}
    purchases = profile.get("session_credit_purchases")
    if not isinstance(purchases, list):
        purchases = []
    if checkout_session_id and any(
        str(item.get("checkout_session_id") or "") == checkout_session_id
        for item in purchases
        if isinstance(item, dict)
    ):
        return profile

    current_total = max(0, _local_int(profile.get("total_sessions")))
    current_contracted = max(0, _local_int(profile.get("contracted_sessions")))
    current_bonus = max(0, _local_int(profile.get("bonus_sessions")))
    total_sessions = max(0, _local_int(total_sessions))
    contracted_sessions = max(0, _local_int(contracted_sessions))
    bonus_sessions = max(0, _local_int(bonus_sessions))
    if purchase_type == "add_sessions":
        profile["contracted_sessions"] = current_contracted + contracted_sessions
        profile["bonus_sessions"] = current_bonus + bonus_sessions
        profile["total_sessions"] = current_total + total_sessions
        profile["remaining_sessions"] = max(
            0,
            _local_int(profile.get("remaining_sessions")) + total_sessions,
        )
        # Sessoes entregues sem credito sao cobradas destes creditos novos.
        settled_sessions = _settle_pending_sessions(profile, already_deducted=False)
    else:
        profile["contracted_sessions"] = contracted_sessions
        profile["bonus_sessions"] = bonus_sessions
        profile["total_sessions"] = total_sessions
        profile["remaining_sessions"] = max(
            0,
            total_sessions - max(0, _local_int(profile.get("used_sessions"))),
        )
        # (total - usadas) ja desconta as pendentes: so registra a quitacao.
        settled_sessions = _settle_pending_sessions(profile, already_deducted=True)
    profile["selected_plan"] = plan_id
    profile["session_unit_amount_cents"] = max(0, _local_int(unit_amount_cents))
    profile["package_total_cents"] = max(0, _local_int(package_total_cents))
    profile["payment_status"] = status
    profile["updated_at"] = _utc_now_iso()
    purchases.append(
        {
            "id": f"purchase-{uuid.uuid4().hex[:12]}",
            "plan_id": plan_id,
            "purchase_type": purchase_type,
            "contracted_sessions": contracted_sessions,
            "bonus_sessions": bonus_sessions,
            "total_sessions": total_sessions,
            "package_total_cents": max(0, _local_int(package_total_cents)),
            "status": status,
            "checkout_session_id": checkout_session_id,
            "settled_pending_sessions": settled_sessions,
            "created_at": _utc_now_iso(),
        }
    )
    profile["session_credit_purchases"] = purchases[-200:]
    PROFESSIONAL_PROFILES[owner_email] = profile
    _save_identity_state()
    return profile


def _public_app_base_url(base_url: str = "") -> str:
    base = str(base_url or "").strip().rstrip("/")
    if base:
        return base
    return os.getenv("FROID_PUBLIC_URL", "http://localhost:5173").rstrip("/")


def _public_google_calendar_redirect_uri(base_url: str = "") -> str:
    return f"{_public_app_base_url(base_url)}/api/google-calendar/callback"


def _current_user_from_request(request: Request) -> Optional[dict]:
    auth_header = request.headers.get("authorization", "")
    token = (
        auth_header.replace("Bearer ", "", 1).strip()
        if auth_header.startswith("Bearer ")
        else ""
    )
    if not token:
        return None
    return _session_user_for_token(token)


def _session_user_for_token(token: str) -> Optional[dict]:
    if not token:
        return None
    user = SESSION_USERS.get(token)
    if not isinstance(user, dict):
        return None
    if float(user.get("_session_expires_at") or 0) <= datetime.now(timezone.utc).timestamp():
        SESSION_USERS.pop(token, None)
        return None
    return user


def _require_current_user(request: Request) -> dict:
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    return user


def _legacy_tenant_context(email: str) -> dict:
    normalized_email = _normalize_email(email)
    organization_id = stable_uuid("organization", normalized_email)
    user_id = stable_uuid("user", normalized_email)
    membership_id = stable_uuid("membership", organization_id, user_id)
    profile = PROFESSIONAL_PROFILES.get(normalized_email) or {}
    return {
        "organization_id": str(organization_id),
        "organization_name": str(
            profile.get("organization_name")
            or profile.get("owner_name")
            or normalized_email
        ),
        "membership_id": str(membership_id),
        "user_id": str(user_id),
        "status": "active",
        "roles": ["owner", "professional"],
        "organization_type": "legacy",
        "legacy_fallback": True,
    }


def _tenant_contexts_for_email(email: str) -> list[dict]:
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return []
    if TENANT_STORE.enabled:
        try:
            contexts = TENANT_STORE.access_contexts(normalized_email)
            if contexts:
                return contexts
        except Exception:
            LOGGER.exception("Unable to load tenant access contexts")
            if FROID_TENANT_AUTHORIZATION_MODE == "enforce":
                return []
    if FROID_TENANT_AUTHORIZATION_MODE == "enforce":
        return []
    return [_legacy_tenant_context(normalized_email)]


def _tenant_authorization_mode_for(organization_id: str) -> str:
    if FROID_TENANT_AUTHORIZATION_MODE != "enforce":
        return FROID_TENANT_AUTHORIZATION_MODE
    return (
        "enforce"
        if str(organization_id or "") in FROID_TENANT_ENFORCEMENT_ORGANIZATIONS
        else "observe"
    )


def _shared_credit_mode_for(organization_id: str) -> str:
    if FROID_SHARED_CREDITS_MODE != "enforce":
        return FROID_SHARED_CREDITS_MODE
    return (
        "enforce"
        if str(organization_id or "") in FROID_SHARED_CREDITS_ORGANIZATIONS
        else "observe"
    )


def _attach_tenant_contexts(user: dict) -> dict:
    enriched = dict(user or {})
    contexts = _tenant_contexts_for_email(enriched.get("email") or "")
    active_id = str(enriched.get("active_organization_id") or "")
    if not any(item.get("organization_id") == active_id for item in contexts):
        active_id = str((contexts[0] if contexts else {}).get("organization_id") or "")
    enriched["organizations"] = [
        {
            **context,
            "authorization_mode": _tenant_authorization_mode_for(
                context.get("organization_id") or ""
            ),
        }
        for context in contexts
    ]
    enriched["active_organization_id"] = active_id
    enriched["tenant_authorization_mode"] = FROID_TENANT_AUTHORIZATION_MODE
    return enriched


def _tenant_context_from_request(request: Request) -> Optional[AccessContext]:
    user = _require_current_user(request)
    contexts = user.get("organizations")
    # Memberships and roles are security state, not durable session claims.
    # Refresh from PostgreSQL so revocation/offboarding takes effect immediately.
    if TENANT_STORE.enabled:
        refreshed = _attach_tenant_contexts(user)
        user.update(refreshed)
        contexts = refreshed.get("organizations") or []
    elif not isinstance(contexts, list) or not contexts:
        refreshed = _attach_tenant_contexts(user)
        user.update(refreshed)
        contexts = refreshed.get("organizations") or []
    requested_id = str(
        request.headers.get("x-froid-organization-id")
        or user.get("active_organization_id")
        or ""
    )
    selected = next(
        (
            item
            for item in contexts
            if isinstance(item, dict)
            and str(item.get("organization_id") or "") == requested_id
        ),
        None,
    )
    if selected is None and len(contexts) == 1 and isinstance(contexts[0], dict):
        selected = contexts[0]
    if selected is None:
        return None
    return AccessContext.create(
        organization_id=selected.get("organization_id") or "",
        membership_id=selected.get("membership_id") or "",
        user_id=selected.get("user_id") or "",
        roles=selected.get("roles") or [],
        status=selected.get("status") or "",
        organization_type=selected.get("organization_type") or "clinic",
    )


def _audit_context_from_session(user: Optional[dict]) -> Optional[dict]:
    """Read non-sensitive audit identifiers without trusting them for access."""
    if not isinstance(user, dict):
        return None
    contexts = user.get("organizations")
    if not isinstance(contexts, list):
        return None
    active_id = str(user.get("active_organization_id") or "")
    selected = next(
        (
            item
            for item in contexts
            if isinstance(item, dict)
            and str(item.get("organization_id") or "") == active_id
        ),
        contexts[0] if len(contexts) == 1 and isinstance(contexts[0], dict) else None,
    )
    return selected if isinstance(selected, dict) else None


@app.middleware("http")
async def security_audit_middleware(request: Request, call_next):
    """Correlate every HTTP action without copying clinical or secret payloads."""
    started = time.perf_counter()
    supplied_request_id = str(request.headers.get("x-request-id") or "").strip()
    request_id = (
        supplied_request_id
        if re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", supplied_request_id)
        else uuid.uuid4().hex
    )
    user = _current_user_from_request(request)
    audit_context = _audit_context_from_session(user)
    response = None
    status_code = 500
    try:
        approval_exempt = (
            "/api/auth/",
            "/api/legal/",
            "/api/professional/profile",
            "/api/professional/legal-acceptances",
            "/api/subscriptions/",
            "/api/billing/",
        )
        approval = (
            _professional_access_status(user.get("email") or "")
            if isinstance(user, dict)
            else {}
        )
        if (
            user
            and request.url.path.startswith("/api/")
            and not _is_admin_email(user.get("email") or "")
            and not any(request.url.path.startswith(prefix) for prefix in approval_exempt)
            and not approval.get("manual_approval_ready")
        ):
            status_code = 403
            # A mensagem precisa dizer a verdade para QUEM a lê. Uma empresa que
            # acabou de se cadastrar para contratar a avaliação NR-1 recebia
            # "acesso profissional aguardando aprovação" — palavra errada, e
            # nenhuma indicação do que fazer a seguir. Ela não é profissional,
            # não pediu acesso clínico, e o que está pendente é a liberação
            # comercial do contrato.
            response = JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "cadastro da empresa recebido. A liberação para operar o "
                        "módulo NR-1 é feita pela equipe FROID — escreva para "
                        "froid@froid.com.br para concluir a contratação."
                        if approval.get("account_type") == "nr1_company"
                        else "acesso profissional aguardando aprovação FROID"
                    ),
                    "approval_pending": True,
                    "account_type": approval.get("account_type") or "",
                },
            )
            response.headers["x-request-id"] = request_id
            return response
        response = await call_next(request)
        status_code = int(response.status_code)
        response.headers["x-request-id"] = request_id
        return response
    finally:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        route = request.scope.get("route")
        route_template = str(getattr(route, "path", "") or "unmatched")[:300]
        outcome = (
            "success" if status_code < 400
            else "denied" if status_code in {401, 402, 403}
            else "error"
        )
        event = {
            "event": "froid.http_audit",
            "request_id": request_id,
            "method": request.method,
            "route": route_template,
            "status_code": status_code,
            "outcome": outcome,
            "duration_ms": elapsed_ms,
            "organization_id": str((audit_context or {}).get("organization_id") or ""),
            "actor_user_id": str((audit_context or {}).get("user_id") or ""),
        }
        AUDIT_LOGGER.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
        if audit_context and TENANT_STORE.enabled:
            try:
                await asyncio.to_thread(
                    TENANT_STORE.record_access_audit,
                    organization_id=str(audit_context.get("organization_id") or ""),
                    actor_user_id=str(audit_context.get("user_id") or ""),
                    action=f"http.{request.method.lower()}",
                    resource_type="api_route",
                    resource_id=route_template,
                    outcome=outcome,
                    metadata={
                        "request_id": request_id,
                        "status_code": status_code,
                        "duration_ms": elapsed_ms,
                    },
                )
            except Exception:
                LOGGER.exception(
                    "Unable to persist HTTP audit event request_id=%s", request_id
                )


def _require_active_subscription_for_context(
    context: Optional[AccessContext],
) -> Optional[dict]:
    """Fail closed for professional features when commercial access is enforced."""
    if not FROID_SUBSCRIPTIONS_REQUIRED:
        return None
    if not TENANT_STORE.enabled:
        raise HTTPException(
            status_code=503,
            detail="validação de assinatura temporariamente indisponível",
        )
    if context is None or context.status != "active":
        raise HTTPException(status_code=402, detail="plano FROID ativo obrigatório")
    try:
        subscription = TENANT_STORE.subscription_status(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
    except Exception:
        LOGGER.exception("Unable to validate required FROID subscription")
        raise HTTPException(
            status_code=503,
            detail="validação de assinatura temporariamente indisponível",
        )
    if (
        not subscription
        or subscription.get("status") not in ACTIVE_SUBSCRIPTION_STATUSES
    ):
        raise HTTPException(status_code=402, detail="plano FROID ativo obrigatório")
    return subscription


def _require_professional_feature_access(request: Request) -> Optional[AccessContext]:
    """Authenticate and apply the subscription gate to a professional feature."""
    user = _require_current_user(request)
    approval = _professional_access_status(user.get("email") or "")
    if not approval.get("manual_approval_ready"):
        detail = (
            "acesso profissional suspenso pelo FROID"
            if approval.get("manual_approval_status") == "suspended"
            else "acesso profissional aguardando aprovação FROID"
        )
        raise HTTPException(status_code=403, detail=detail)
    context = _tenant_context_from_request(request)
    _require_active_subscription_for_context(context)
    return context


def _require_professional_websocket_access(user: dict) -> Optional[AccessContext]:
    """Apply the same fail-closed gate before accepting professional sockets."""
    approval = _professional_access_status(user.get("email") or "")
    if not approval.get("manual_approval_ready"):
        raise HTTPException(
            status_code=403,
            detail="acesso profissional aguardando aprovação FROID",
        )
    contexts = _tenant_contexts_for_email(user.get("email") or "")
    active_id = str(user.get("active_organization_id") or "")
    selected = next(
        (
            item
            for item in contexts
            if isinstance(item, dict)
            and str(item.get("organization_id") or "") == active_id
        ),
        contexts[0] if len(contexts) == 1 else None,
    )
    context = (
        AccessContext.create(
            organization_id=selected.get("organization_id") or "",
            membership_id=selected.get("membership_id") or "",
            user_id=selected.get("user_id") or "",
            roles=selected.get("roles") or [],
            status=selected.get("status") or "",
            organization_type=selected.get("organization_type") or "clinic",
        )
        if isinstance(selected, dict)
        else None
    )
    _require_active_subscription_for_context(context)
    return context


def _session_matches_context(session_id: str, context: Optional[AccessContext]) -> bool:
    organization_id = str(SESSION_ORGANIZATIONS.get(session_id) or "")
    return not organization_id or bool(
        context and organization_id == context.organization_id
    )


async def _record_websocket_audit(
    *,
    action: str,
    session_id: str,
    role: str,
    outcome: str,
    context: Optional[AccessContext] = None,
    organization_id: str = "",
) -> None:
    safe_session_reference = hashlib.sha256(
        str(session_id or "").encode("utf-8")
    ).hexdigest()[:16]
    request_id = uuid.uuid4().hex
    tenant_id = context.organization_id if context else str(organization_id or "")
    safe_role = str(role or "unknown")[:32]
    event = {
        "event": "froid.websocket_audit",
        "request_id": request_id,
        "action": action,
        "session_reference": safe_session_reference,
        "role": safe_role,
        "outcome": outcome,
        "organization_id": tenant_id,
        "actor_user_id": context.user_id if context else "",
    }
    AUDIT_LOGGER.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
    if tenant_id and TENANT_STORE.enabled:
        try:
            await asyncio.to_thread(
                TENANT_STORE.record_access_audit,
                organization_id=tenant_id,
                actor_user_id=context.user_id if context else "",
                action=f"websocket.{action}",
                resource_type="clinical_session",
                resource_id=session_id,
                outcome=outcome,
                metadata={"request_id": request_id, "role": safe_role},
            )
        except Exception:
            LOGGER.exception(
                "Unable to persist WebSocket audit event request_id=%s", request_id
            )


def _authorize_tenant_request(
    request: Request,
    permission: str,
    *,
    resource_type: str,
    resource_id: str = "",
    resource_organization_id: str = "",
    assigned: bool = False,
    owns_resource: bool = False,
    context_override: Optional[AccessContext] = None,
) -> Optional[AccessContext]:
    context = context_override or _tenant_context_from_request(request)
    _require_active_subscription_for_context(context)
    if FROID_TENANT_AUTHORIZATION_MODE == "off":
        return context
    decision = decide(
        context,
        permission,
        resource_organization_id=resource_organization_id,
        assigned=assigned,
        owns_resource=owns_resource,
    )
    effective_mode = _tenant_authorization_mode_for(
        context.organization_id if context else resource_organization_id
    )
    if not decision.allowed:
        try:
            TENANT_STORE.record_access_audit(
                organization_id=(context.organization_id if context else resource_organization_id),
                actor_user_id=(context.user_id if context else ""),
                action=permission,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="denied" if should_block(effective_mode, decision) else "observed_denial",
                metadata={"reason": decision.reason},
            )
        except Exception:
            LOGGER.exception("Unable to record tenant authorization audit")
    if should_block(effective_mode, decision):
        raise HTTPException(status_code=403, detail="acesso restrito nesta organização")
    return context


def _require_tenant_management_context(
    request: Request, organization_id: str, permission: str
) -> AccessContext:
    if not TENANT_STORE.enabled:
        raise HTTPException(
            status_code=409,
            detail="gestão multi-organização requer persistência dual",
        )
    context = _tenant_context_from_request(request)
    decision = decide(
        context,
        permission,
        resource_organization_id=str(organization_id or ""),
    )
    if not decision.allowed or context is None:
        # "permissão organizacional insuficiente" é verdade e não ensina nada.
        # Quem recebe essa frase não sabe se está na organização errada, com o
        # papel errado, com a associação suspensa, ou se o produto não existe
        # para aquele tipo de organização — e todas as quatro produzem
        # exatamente o mesmo texto. Um administrador clicando nos links do NR-1
        # recebia isso em todos eles, sem nenhum caminho para descobrir por quê.
        #
        # O que vai abaixo é sobre a PRÓPRIA associação de quem pediu: o papel
        # que ele tem e o tipo da organização em que está. Não é vazamento —
        # ele já é essa pessoa. O que continua fora é qualquer informação sobre
        # organização de terceiro.
        if context is None:
            detalhe = (
                "sua conta não tem associação ativa com esta organização. "
                "Se você trocou de organização há pouco, recarregue a página."
            )
        else:
            papeis = ", ".join(sorted(context.roles)) or "nenhum papel atribuído"
            detalhe = (
                f"esta ação exige a permissão '{permission}', que nenhum dos "
                f"seus papéis nesta organização carrega. Seus papéis aqui: "
                f"{papeis}. Tipo da organização: {context.organization_type}. "
                f"Motivo técnico: {decision.reason}."
            )
        raise HTTPException(
            status_code=403,
            detail=f"permissão organizacional insuficiente — {detalhe}",
        )
    subscription = _require_active_subscription_for_context(context)
    if subscription is None:
        subscription = TENANT_STORE.subscription_status(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
    if permission == "audit.read" and subscription:
        if not bool((subscription.get("entitlements") or {}).get("audit_export")):
            raise HTTPException(status_code=403, detail="plano sem trilha de auditoria avançada")
    return context


def _record_tenant_success(
    context: Optional[AccessContext], action: str, resource_type: str,
    resource_id: str = "", metadata: Optional[dict] = None,
) -> None:
    if context is None:
        return
    try:
        TENANT_STORE.record_access_audit(
            organization_id=context.organization_id,
            actor_user_id=context.user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
        )
    except Exception:
        LOGGER.exception("Unable to record successful tenant audit event")


def _current_patient_from_request(request: Request) -> Optional[dict]:
    auth_header = request.headers.get("authorization", "")
    token = (
        auth_header.replace("Bearer ", "", 1).strip()
        if auth_header.startswith("Bearer ")
        else ""
    )
    if not token:
        return None
    patient_session = PATIENT_PORTAL_SESSIONS.get(token)
    if not isinstance(patient_session, dict):
        return None
    if float(patient_session.get("_session_expires_at") or 0) <= datetime.now(timezone.utc).timestamp():
        PATIENT_PORTAL_SESSIONS.pop(token, None)
        return None
    return patient_session


def _require_current_patient(request: Request) -> dict:
    patient_session = _current_patient_from_request(request)
    if not patient_session:
        raise HTTPException(status_code=401, detail="paciente não autenticado")
    return patient_session


def _protect_data_subject_details(details: str) -> dict:
    clean_details = str(details or "").strip()
    if not clean_details:
        return {}
    if not CLINICAL_TEXT_CIPHER:
        raise HTTPException(
            status_code=503,
            detail="proteção dos detalhes da solicitação temporariamente indisponível",
        )
    return CLINICAL_TEXT_CIPHER.protect(
        {"details": clean_details}, "details", "details_encrypted"
    )


def _reveal_data_subject_request(item: dict) -> dict:
    public_item = dict(item or {})
    payload = public_item.get("request_payload")
    payload = dict(payload) if isinstance(payload, dict) else {}
    if payload.get("details_encrypted") and CLINICAL_TEXT_CIPHER:
        try:
            payload = CLINICAL_TEXT_CIPHER.reveal(
                payload, "details", "details_encrypted"
            )
        except TokenEncryptionError:
            payload = {"details": "", "details_locked": True}
    else:
        payload.pop("details_encrypted", None)
    public_item["request_payload"] = payload
    encrypted_response = str(public_item.get("response_summary") or "")
    if encrypted_response:
        if CLINICAL_TEXT_CIPHER:
            try:
                response = CLINICAL_TEXT_CIPHER.reveal(
                    {"response_encrypted": encrypted_response},
                    "response",
                    "response_encrypted",
                )
                public_item["response_summary"] = response.get("response") or ""
            except TokenEncryptionError:
                public_item["response_summary"] = ""
                public_item["response_locked"] = True
        else:
            public_item["response_summary"] = ""
            public_item["response_locked"] = True
    return public_item


def _protect_data_subject_response(response_summary: str) -> str:
    clean_response = str(response_summary or "").strip()
    if not clean_response:
        return ""
    if not CLINICAL_TEXT_CIPHER:
        raise HTTPException(
            status_code=503,
            detail="proteção da resposta ao titular temporariamente indisponível",
        )
    protected = CLINICAL_TEXT_CIPHER.protect(
        {"response": clean_response}, "response", "response_encrypted"
    )
    return str(protected.get("response_encrypted") or "")


def _is_admin_email(email: str) -> bool:
    return _normalize_email(email) in FROID_ADMIN_EMAILS


def _require_admin_user(request: Request) -> dict:
    user = _require_current_user(request)
    if not _is_admin_email(user.get("email") or ""):
        raise HTTPException(status_code=403, detail="acesso administrativo restrito")
    return user


def _record_admin_audit_event(request: Request, action: str, target: str, detail: Optional[dict] = None) -> None:
    user = _current_user_from_request(request)
    if not user:
        # If no user, we cannot record an audit event due to NOT NULL constraints.
        # In practice, this function should only be called from authenticated endpoints.
        return
    actor_user_id = user.get("id")
    # Determine organization_id: prefer active_organization_id, else first organization.
    organization_id = user.get("active_organization_id")
    if not organization_id:
        orgs = user.get("organizations") or []
        if orgs:
            organization_id = orgs[0].get("organization_id")
    # If still none, we cannot insert due to NOT NULL constraint; skip.
    if not organization_id:
        return
    # Prepare metadata: include the original detail and admin_email for reference.
    metadata = {
        "detail": detail or {},
        "admin_email": _normalize_email(user.get("email") or ""),
    }
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        target=target,
        outcome="success",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
        metadata=metadata,
    )


def _calendar_connection_public(connection: Optional[dict]) -> dict:
    if not connection:
        return {"connected": False}
    return {
        "connected": True,
        "professional_email": connection.get("professional_email") or "",
        "google_email": connection.get("google_email") or "",
        "scope": connection.get("scope") or "",
        "selected_calendar_id": connection.get("selected_calendar_id") or "primary",
        "selected_calendar_summary": connection.get("selected_calendar_summary") or "Agenda principal",
        "connected_at": connection.get("connected_at") or "",
        "updated_at": connection.get("updated_at") or "",
        "expires_at": connection.get("expires_at") or "",
    }


def _calendar_configured() -> bool:
    return bool(GOOGLE_CALENDAR_CLIENT_ID and GOOGLE_CALENDAR_CLIENT_SECRET)


def _calendar_auth_url(email: str, redirect_uri: str) -> str:
    state = secrets.token_urlsafe(32)
    GOOGLE_CALENDAR_OAUTH_STATES[state] = {
        "email": _normalize_email(email),
        "redirect_uri": redirect_uri,
        "created_at": datetime.now(timezone.utc).timestamp(),
    }
    params = {
        "client_id": GOOGLE_CALENDAR_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_CALENDAR_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "false",
        "prompt": "consent",
        "state": state,
        "login_hint": email,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def _exchange_google_calendar_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CALENDAR_CLIENT_ID,
                "client_secret": GOOGLE_CALENDAR_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Falha ao conectar Google Agenda: {response.text[:300]}")
    return response.json()


async def _refresh_google_calendar_token(email: str, connection: dict) -> dict:
    refresh_token = connection.get("refresh_token") or ""
    if not refresh_token:
        raise HTTPException(status_code=409, detail="Reconecte o Google Agenda para renovar o acesso")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CALENDAR_CLIENT_ID,
                "client_secret": GOOGLE_CALENDAR_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=409, detail="Falha ao renovar Google Agenda; reconecte a conta")
    payload = response.json()
    now = datetime.now(timezone.utc).timestamp()
    connection.update(
        {
            "access_token": payload.get("access_token") or connection.get("access_token") or "",
            "expires_at": now + int(payload.get("expires_in") or 0),
            "scope": payload.get("scope") or connection.get("scope") or "",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    GOOGLE_CALENDAR_CONNECTIONS[email] = connection
    _save_identity_state()
    return connection


async def _calendar_access_token(email: str) -> str:
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(_normalize_email(email))
    if not connection:
        raise HTTPException(status_code=404, detail="Google Agenda não conectado")
    expires_at = float(connection.get("expires_at") or 0)
    if expires_at <= datetime.now(timezone.utc).timestamp() + 60:
        connection = await _refresh_google_calendar_token(email, connection)
    token = connection.get("access_token") or ""
    if not token:
        raise HTTPException(status_code=404, detail="Google Agenda sem token ativo")
    return token


def _selected_calendar_id(connection: Optional[dict], fallback: str = "primary") -> str:
    calendar_id = str((connection or {}).get("selected_calendar_id") or fallback or "primary").strip()
    return calendar_id or "primary"


def _is_recommended_froid_calendar(summary: Any) -> bool:
    normalized = " ".join(str(summary or "").strip().casefold().split())
    return normalized == "froid" or normalized.startswith("froid -")


async def _google_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return response.json() if response.status_code < 400 else {}


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


def _effective_professional_access_status(user: dict) -> dict:
    """Combine legacy onboarding evidence with authoritative tenant billing."""
    legacy = _professional_access_status(user.get("email") or "")
    fail_closed = {
        **legacy,
        "payment_status": "subscription_unavailable",
        "remaining_sessions": 0,
        "onboarding_required": True,
    }
    if not TENANT_STORE.enabled:
        return fail_closed if FROID_SUBSCRIPTIONS_REQUIRED else legacy
    contexts = user.get("organizations") if isinstance(user, dict) else []
    contexts = contexts if isinstance(contexts, list) else []
    active_id = str(user.get("active_organization_id") or "")
    context = next(
        (
            item for item in contexts
            if isinstance(item, dict)
            and str(item.get("organization_id") or "") == active_id
        ),
        contexts[0] if len(contexts) == 1 and isinstance(contexts[0], dict) else None,
    )
    if not context:
        return fail_closed if FROID_SUBSCRIPTIONS_REQUIRED else legacy
    try:
        subscription = TENANT_STORE.subscription_status(
            organization_id=str(context.get("organization_id") or ""),
            membership_id=str(context.get("membership_id") or ""),
        )
        if not subscription:
            return fail_closed if FROID_SUBSCRIPTIONS_REQUIRED else legacy
        wallet = TENANT_STORE.wallet_status(
            organization_id=str(context.get("organization_id") or ""),
            membership_id=str(context.get("membership_id") or ""),
        )
    except Exception:
        LOGGER.exception("Unable to derive authoritative subscription access")
        return fail_closed if FROID_SUBSCRIPTIONS_REQUIRED else legacy
    balance = max(0, _local_int(wallet.get("balance")))
    billing_active = (
        subscription.get("status") in ACTIVE_SUBSCRIPTION_STATUSES
        and wallet.get("authority") == "shared"
        and balance > 0
    )
    profile_ready = (
        bool(legacy.get("has_profile"))
        and bool(legacy.get("lgpd_acknowledged"))
        and not bool(legacy.get("cpf_required"))
        and bool(legacy.get("manual_approval_ready"))
    )
    return {
        **legacy,
        "selected_plan": subscription.get("package_code") or subscription.get("plan_code"),
        "payment_status": subscription.get("status") or "not_started",
        "remaining_sessions": balance,
        "total_sessions": max(
            balance,
            _local_int(legacy.get("total_sessions")),
        ),
        "onboarding_required": not (profile_ready and billing_active),
        "subscription": subscription,
        "shared_wallet": wallet,
    }


async def _transcribe_with_openai(
    audio_bytes: bytes,
    fallback_text: str = "",
    filename: str = "froid-session.webm",
    prompt: str = "",
    spoken_locale: str = "pt-BR",
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
            spoken_locale,
        )
        if transcript:
            return transcript, ""
    except Exception as exc:
        return fallback_text, str(exc)
    return fallback_text, ""


def _password_policy_error(password: str) -> str:
    """Devolve a queixa a mostrar, ou string vazia se a senha serve."""
    senha = str(password or "")
    if len(senha) < FROID_PASSWORD_MIN_LENGTH:
        return (
            f"A senha precisa ter no mínimo {FROID_PASSWORD_MIN_LENGTH} caracteres"
        )
    if len(senha) > 256:
        return "A senha excede o limite de 256 caracteres"
    if not any(ch.isalpha() for ch in senha) or not any(ch.isdigit() for ch in senha):
        return "A senha precisa combinar letras e números"
    return ""


def _set_professional_password(credential: dict, password: str) -> None:
    salt = secrets.token_hex(16)
    credential["password_salt"] = salt
    credential["password_hash"] = _password_hash(password, salt)
    credential["password_set_at"] = _utc_now_iso()


def _verify_professional_password(credential: dict, password: str) -> bool:
    if not isinstance(credential, dict):
        return False
    salt = str(credential.get("password_salt") or "")
    expected = str(credential.get("password_hash") or "")
    if not salt or not expected or not password:
        return False
    return secrets.compare_digest(_password_hash(password, salt), expected)


def _credential_token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _issue_credential_token(credential: dict, kind: str, ttl_seconds: int) -> str:
    """Emite token de uso único e guarda apenas o hash.

    O estado de identidade é persistido em disco e espelhado no Postgres. Um
    token de verificação em claro nesse arquivo valeria tanto quanto a senha:
    quem lesse o backup entraria como a pessoa.
    """
    token = secrets.token_urlsafe(32)
    credential[f"{kind}_token_hash"] = _credential_token_hash(token)
    credential[f"{kind}_expires_ts"] = (
        datetime.now(timezone.utc).timestamp() + ttl_seconds
    )
    credential[f"{kind}_sent_at"] = _utc_now_iso()
    return token


def _consume_credential_token(kind: str, token: str) -> Optional[dict]:
    """Localiza a credencial dona do token e o queima na mesma passagem.

    Queima antes de checar a validade: um token expirado não sobrevive à
    tentativa de uso, e não há como ficar tentando o mesmo valor até a virada
    de algum relógio.
    """
    if not token:
        return None
    token_hash = _credential_token_hash(token)
    agora = datetime.now(timezone.utc).timestamp()
    for credential in PROFESSIONAL_CREDENTIALS.values():
        armazenado = str(credential.get(f"{kind}_token_hash") or "")
        if not armazenado or not secrets.compare_digest(armazenado, token_hash):
            continue
        expira = credential.get(f"{kind}_expires_ts")
        credential.pop(f"{kind}_token_hash", None)
        credential.pop(f"{kind}_expires_ts", None)
        try:
            valido = float(expira) >= agora
        except (TypeError, ValueError):
            valido = False
        return credential if valido else None
    return None


def _revoke_professional_sessions(email: str) -> None:
    """Derruba toda sessão viva daquele e-mail (troca ou reset de senha)."""
    alvo = _normalize_email(email)
    if not alvo:
        return
    for token, session_user in list(SESSION_USERS.items()):
        if _normalize_email((session_user or {}).get("email") or "") == alvo:
            SESSION_USERS.pop(token, None)


def _public_app_link(hash_path: str) -> str:
    base = os.getenv("FROID_PUBLIC_URL", "http://localhost:5173").rstrip("/")
    if not base.endswith("/app"):
        base = f"{base}/app"
    return f"{base}/#{hash_path}"


async def _deliver_credential_email(
    to_address: str, subject: str, text_body: str, html_body: str
) -> None:
    try:
        await asyncio.to_thread(
            froid_mailer.send_email, to_address, subject, text_body, html_body
        )
    except froid_mailer.MailerError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível enviar o e-mail agora. "
                "Tente novamente em alguns minutos."
            ),
        )


def _credential_email_bodies(titulo: str, chamada: str, link: str, validade: str):
    """Corpo texto e HTML das mensagens de credencial.

    Sempre em duas partes: cliente que bloqueia HTML precisa conseguir ler o
    link, senão a verificação vira um beco sem saída para quem usa leitor de
    tela ou webmail corporativo restrito.
    """
    texto = f"""{titulo}

{chamada}

{link}

O link vale por {validade} e só pode ser usado uma vez.
Se não foi você quem pediu, ignore esta mensagem: nada acontece enquanto o
link não for aberto.

FROID"""
    html = (
        "<div style='font-family:system-ui,sans-serif;line-height:1.6;color:#0f172a'>"
        "<p style='letter-spacing:.3em;font-weight:900;color:#0e7490'>FROID</p>"
        f"<h1 style='font-size:20px'>{titulo}</h1>"
        f"<p>{chamada}</p>"
        f"<p><a href='{link}' style='display:inline-block;background:#0891b2;"
        "color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;"
        "font-weight:700'>Abrir link seguro</a></p>"
        f"<p style='font-size:13px;color:#475569'>O link vale por {validade} e "
        "só pode ser usado uma vez. Se não foi você quem pediu, ignore esta "
        "mensagem.</p>"
        f"<p style='font-size:12px;color:#64748b;word-break:break-all'>{link}</p>"
        "</div>"
    )
    return texto, html


def _expirar_sessoes_de(email: str) -> int:
    """Derruba as sessoes em memoria de um e-mail.

    Sem isto, quem ja estava logado continuaria com o token valido ate o TTL.
    O dado ja estaria protegido -- `_tenant_context_from_request` reconsulta o
    Postgres a cada requisicao -- mas a pessoa veria telas vazias em vez da
    mensagem, que e exatamente o que se quis evitar.
    """
    alvo = _normalize_email(email)
    if not alvo:
        return 0
    tokens = [
        token
        for token, sessao in SESSION_USERS.items()
        if isinstance(sessao, dict) and _normalize_email(sessao.get("email") or "") == alvo
    ]
    for token in tokens:
        SESSION_USERS.pop(token, None)
    return len(tokens)


def _expirar_sessoes_da_organizacao(organization_id: str) -> int:
    """Derruba as sessoes de quem tem vinculo com a organizacao."""
    alvo = str(organization_id or "").strip()
    if not alvo:
        return 0
    tokens = []
    for token, sessao in SESSION_USERS.items():
        if not isinstance(sessao, dict):
            continue
        for contexto in sessao.get("organizations") or []:
            if isinstance(contexto, dict) and str(contexto.get("organization_id") or "") == alvo:
                tokens.append(token)
                break
    for token in tokens:
        SESSION_USERS.pop(token, None)
    return len(tokens)


ACESSO_REVOGADO = (
    "Acesso restrito, entre em contato com froid@froid.com.br "
    "para maiores detalhes"
)


def _guard_acesso_revogado(session_user: dict) -> None:
    """Recusa a sessão de quem teve acesso e perdeu.

    A checagem é deliberadamente estreita. Lista de organizações vazia NÃO
    basta: o profissional autônomo entra pelo cadastro próprio e nunca teve
    vínculo, e recusá-lo trancaria a maior parte do produto clínico para fora.

    Só se recusa quem tem vínculo registrado e nenhum ativo — revogado,
    suspenso, conta desabilitada ou organização suspensa. Sem isto, essa pessoa
    autenticava normalmente e caía numa tela sem organização alguma, que ela
    leria como defeito do sistema e não como decisão de quem opera.
    """
    if session_user.get("organizations"):
        return
    if not TENANT_STORE.enabled:
        return
    try:
        revogado = TENANT_STORE.access_was_revoked(session_user.get("email") or "")
    except Exception:
        # Banco indisponível não pode virar bloqueio de quem tem acesso
        # legítimo. Falha aberta aqui, porque o dado continua protegido pelas
        # políticas de leitura — a sessão sozinha não abre nada.
        return
    if revogado:
        raise HTTPException(status_code=403, detail=ACESSO_REVOGADO)


def _issue_session(user: dict):
    token = secrets.token_urlsafe(32)
    session_user = dict(user or {})
    session_user["email"] = _normalize_email(session_user.get("email") or "")
    session_user = _attach_tenant_contexts(session_user)
    _guard_acesso_revogado(session_user)
    session_user["access_status"] = _effective_professional_access_status(session_user)
    session_user["_session_expires_at"] = (
        datetime.now(timezone.utc).timestamp() + FROID_SESSION_TOKEN_TTL_SECONDS
    )
    SESSION_USERS[token] = session_user
    public_user = {
        key: value for key, value in session_user.items() if not key.startswith("_")
    }
    return {
        "token": token,
        "expires_in": FROID_SESSION_TOKEN_TTL_SECONDS,
        "user": public_user,
    }


def _verify_local_login(body: dict) -> dict:
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email:
        raise HTTPException(status_code=400, detail="email obrigatório")

    # Conta real com senha vem primeiro: o formulário de e-mail e senha da tela
    # de login continua apontando para cá, e quem se cadastrou sem Google
    # precisa entrar por ele. A lista local de desenvolvimento segue existindo
    # como fallback, nunca como atalho por cima de uma credencial real.
    credencial = PROFESSIONAL_CREDENTIALS.get(email)
    if isinstance(credencial, dict) and credencial.get("password_hash"):
        if not _verify_professional_password(credencial, password):
            raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
        if not credencial.get("email_verified"):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Confirme seu e-mail antes de entrar. "
                    "Verifique a caixa de entrada ou peça um novo link."
                ),
            )
        credencial["last_auth_at"] = _utc_now_iso()
        _save_identity_state()
        return {
            "email": email,
            "provider": "password",
            "name": str(credencial.get("name") or "") or email.split("@", 1)[0],
        }

    if FROID_LOCAL_AUTH_PASSWORD and FROID_LOCAL_AUTH_EMAILS:
        if not secrets.compare_digest(password, FROID_LOCAL_AUTH_PASSWORD):
            raise HTTPException(status_code=401, detail="senha inválida")
        if FROID_LOCAL_AUTH_EMAILS and email not in FROID_LOCAL_AUTH_EMAILS:
            raise HTTPException(status_code=403, detail="email não autorizado")
    else:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    return {
        "email": email,
        "provider": "local-dev",
        "name": body.get("name") or email.split("@", 1)[0],
    }


async def _verify_google_credential(credential: str) -> dict:
    if not GOOGLE_AUTH_CLIENT_ID:
        raise HTTPException(
            status_code=503, detail="GOOGLE_AUTH_CLIENT_ID não configurado"
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Credencial Google inválida")

    profile = response.json()
    if profile.get("aud") != GOOGLE_AUTH_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Credencial Google de outro aplicativo")
    if str(profile.get("email_verified", "")).lower() != "true":
        raise HTTPException(status_code=401, detail="E-mail Google não verificado")

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
    """Laço de tick da sessão (1/s): calcula o payload multimodal e o envia ao
    profissional. Uma exceção num único tick (ex.: dado de borda inesperado de
    um marcador real) NÃO PODE encerrar o laço para o resto da sessão — sem
    isolamento, o IPM e os biomarcadores ficam congelados em silêncio até o
    fim do encontro, sem sinal algum para o profissional. Cada tick é isolado:
    uma falha é registrada e o laço segue para o próximo segundo."""
    entry = manager.active_sessions.get(session_id)
    if not entry: return
    state: SessionState = entry["state"]
    while manager.is_current(session_id, connection_id):
        try:
            voice_12 = MockBiometricStream.generate_voice_spectral()
            facs_flags, facs_details = MockBiometricStream.generate_facs_dissonance()
            payload = state.process_tick(voice_12, facs_flags, facs_details)
            await manager.broadcast_payload(session_id, payload)
        except Exception:
            STREAM_LOGGER.exception(
                "froid_stream_loop: tick falhou (session_id=%s) — seguindo para o próximo tick",
                session_id,
            )
        await asyncio.sleep(1.0)


@app.post("/api/froid/{session_id}/acoustic-f0")
async def submit_acoustic_f0(session_id: str, request: Request):
    """Recebe uma janela de PCM cru (int16 mono) do navegador e mede a F0 real
    da voz do paciente por YIN, atualizando o estado da sessão ativa. Aceita
    autenticação do paciente (convite aceito) ou do profissional (dono da
    sessão)."""
    body = await request.json()
    invite = str(body.get("invite") or request.query_params.get("invite") or "")
    professional = _current_user_from_request(request)
    invite_record = SESSION_INVITES.get(invite) if invite else None
    patient_authorized = bool(
        invite_record
        and invite_record.get("status") == "accepted"
        and str(invite_record.get("session_id") or "") == session_id
    )
    professional_authorized = bool(
        professional
        and session_id
        and _normalize_email(SESSION_OWNERS.get(session_id) or "")
        == _normalize_email(professional.get("email") or "")
    )
    if not patient_authorized and not professional_authorized:
        raise HTTPException(status_code=401, detail="acesso acústico não autorizado")

    # Guarda de enxurrada: uso legítimo envia ~1 janela/s; teto bem acima disso
    # (240/min) apenas bloqueia flood sem afetar a captura normal.
    _rate_limit_guard(
        "acoustic", session_id or _client_ip(request), 240, 60.0,
        "Taxa de envio acústico excedida.",
    )

    entry = manager.active_sessions.get(session_id)
    if not entry:
        # A sessão de análise do profissional ainda não está ativa; o cliente
        # continua enviando e a F0 passa a valer quando ela abrir.
        return {"status": "session_inactive", "f0_mean": 0.0}

    try:
        sample_rate = int(body.get("sample_rate") or 16000)
    except (TypeError, ValueError):
        sample_rate = 16000
    if sample_rate < 4000 or sample_rate > 96000:
        raise HTTPException(status_code=400, detail="sample_rate inválido")
    pcm_b64 = body.get("pcm_base64") or ""
    if not isinstance(pcm_b64, str) or not pcm_b64:
        raise HTTPException(status_code=400, detail="pcm_base64 ausente")
    try:
        pcm_bytes = base64.b64decode(pcm_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="pcm_base64 inválido")
    # Teto de tamanho: ~5 s a 48 kHz int16 mono.
    if len(pcm_bytes) > 500_000:
        raise HTTPException(status_code=413, detail="quadro de áudio grande demais")

    state: SessionState = entry["state"]
    signal = froid_f0.pcm16_bytes_to_float(pcm_bytes)
    # Buffer rolante (~3s) dá resolução às bandas de modulação lentas; todos os
    # biomarcadores vocais reais são extraídos dele e injetados na sessão.
    buffer = state.ingest_pcm(signal, sample_rate)
    # A DSP (YIN + FFT + Hilbert + MFCC) é pesada; roda em thread pool para NÃO
    # bloquear o event loop — mantendo o laço de tick fluido com várias sessões
    # simultâneas. numpy libera o GIL nas operações vetoriais, então paraleliza
    # de fato entre núcleos.
    features = await asyncio.to_thread(
        froid_voice.extract_voice_features, buffer, sample_rate
    )
    state.update_voice_features(features)
    return {
        "f0_mean": features.get("f0_mean", 0.0),
        "f0_voiced_ratio": features.get("f0_voiced_ratio", 0.0),
        "markers_computed": len(features),
        "source": "real_pcm",
        "sample_rate": sample_rate,
    }


@app.post("/api/froid/{session_id}/facial-aus")
async def submit_facial_aus(session_id: str, request: Request):
    """Recebe os coeficientes de blendshape faciais (MediaPipe FaceLandmarker /
    ARKit) medidos pelo navegador e deriva, no servidor, as Unidades de Ação
    (FACS) reais e as dissonâncias faciais — substituindo as marcações
    simuladas. Mesma autenticação do endpoint acústico (paciente por convite
    aceito ou profissional dono da sessão)."""
    body = await request.json()
    invite = str(body.get("invite") or request.query_params.get("invite") or "")
    professional = _current_user_from_request(request)
    invite_record = SESSION_INVITES.get(invite) if invite else None
    patient_authorized = bool(
        invite_record
        and invite_record.get("status") == "accepted"
        and str(invite_record.get("session_id") or "") == session_id
    )
    professional_authorized = bool(
        professional
        and session_id
        and _normalize_email(SESSION_OWNERS.get(session_id) or "")
        == _normalize_email(professional.get("email") or "")
    )
    if not patient_authorized and not professional_authorized:
        raise HTTPException(status_code=401, detail="acesso facial não autorizado")

    # Uso legítimo envia ~3 quadros/s; teto de 600/min bloqueia apenas flood.
    _rate_limit_guard(
        "facial", session_id or _client_ip(request), 600, 60.0,
        "Taxa de envio facial excedida.",
    )

    entry = manager.active_sessions.get(session_id)
    if not entry:
        return {"status": "session_inactive", "facs_source": "none"}

    blendshapes = body.get("blendshapes")
    if not isinstance(blendshapes, dict) or not blendshapes:
        raise HTTPException(status_code=400, detail="blendshapes ausentes")
    # Teto defensivo: o padrão ARKit expõe 52 formas; aceitamos folga.
    if len(blendshapes) > 128:
        raise HTTPException(status_code=413, detail="blendshapes em excesso")
    sanitized: dict = {}
    for name, value in blendshapes.items():
        try:
            sanitized[str(name)[:48]] = float(value)
        except (TypeError, ValueError):
            continue

    state: SessionState = entry["state"]
    state.update_facial_features(sanitized)
    return {
        "facs_source": "real_facs" if state.latest_facial_aus else "none",
        "action_units": state.latest_facial_aus or {},
        "active_zones": [z for z, f in (state.latest_facs_flags or {}).items() if f],
    }


@app.websocket("/ws/fusion/{session_id}")
async def websocket_fusion(websocket: WebSocket, session_id: str):
    token = str(websocket.query_params.get("token") or "")
    user = _session_user_for_token(token)
    if not user or SESSION_OWNERS.get(session_id) != _normalize_email(user.get("email") or ""):
        await _record_websocket_audit(
            action="connect", session_id=session_id, role="professional",
            outcome="denied",
        )
        await websocket.close(code=4401)
        return
    try:
        context = _require_professional_websocket_access(user)
    except HTTPException as exc:
        await _record_websocket_audit(
            action="connect", session_id=session_id, role="professional",
            outcome="denied",
        )
        await websocket.close(code=4402 if exc.status_code == 402 else 1013)
        return
    if not _session_matches_context(session_id, context):
        await _record_websocket_audit(
            action="connect", session_id=session_id, role="professional",
            outcome="denied", context=context,
        )
        await websocket.close(code=4403)
        return
    connection_id = await manager.connect(websocket, session_id)
    await _record_websocket_audit(
        action="connect", session_id=session_id, role="professional",
        outcome="success", context=context,
    )
    task = asyncio.create_task(froid_stream_loop(session_id, connection_id))
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping": await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(session_id, connection_id); task.cancel()
        await _record_websocket_audit(
            action="disconnect", session_id=session_id, role="professional",
            outcome="success", context=context,
        )
    except Exception:
        manager.disconnect(session_id, connection_id); task.cancel()
        await _record_websocket_audit(
            action="disconnect", session_id=session_id, role="professional",
            outcome="error", context=context,
        )


@app.websocket("/ws/rtc/{session_id}/{role}")
async def websocket_rtc_signaling(websocket: WebSocket, session_id: str, role: str):
    if role not in {"professional", "patient"}:
        await _record_websocket_audit(
            action="connect", session_id=session_id, role=role,
            outcome="denied",
        )
        await websocket.accept()
        await websocket.send_json({"type": "error", "detail": "role invalido"})
        await websocket.close(code=1008)
        return

    if role == "professional":
        token = str(websocket.query_params.get("token") or "")
        user = _session_user_for_token(token)
        if not user or SESSION_OWNERS.get(session_id) != _normalize_email(user.get("email") or ""):
            await _record_websocket_audit(
                action="connect", session_id=session_id, role=role,
                outcome="denied",
            )
            await websocket.close(code=4401)
            return
        try:
            context = _require_professional_websocket_access(user)
        except HTTPException as exc:
            await _record_websocket_audit(
                action="connect", session_id=session_id, role=role,
                outcome="denied",
            )
            await websocket.close(code=4402 if exc.status_code == 402 else 1013)
            return
        if not _session_matches_context(session_id, context):
            await _record_websocket_audit(
                action="connect", session_id=session_id, role=role,
                outcome="denied", context=context,
            )
            await websocket.close(code=4403)
            return
    else:
        invite_token = str(websocket.query_params.get("invite") or "")
        invite = SESSION_INVITES.get(invite_token)
        if (
            not isinstance(invite, dict)
            or str(invite.get("session_id") or "") != session_id
            or invite.get("status") != "accepted"
            or (
                SESSION_ORGANIZATIONS.get(session_id)
                and _invite_organization_id(invite)
                != SESSION_ORGANIZATIONS.get(session_id)
            )
        ):
            await _record_websocket_audit(
                action="connect", session_id=session_id, role=role,
                outcome="denied",
            )
            await websocket.close(code=4403)
            return

    await rtc_signals.connect(websocket, session_id, role)
    websocket_organization_id = (
        context.organization_id
        if role == "professional"
        else _invite_organization_id(invite)
    )
    await _record_websocket_audit(
        action="connect", session_id=session_id, role=role,
        outcome="success", context=context if role == "professional" else None,
        organization_id=websocket_organization_id,
    )
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            await rtc_signals.relay(session_id, role, message)
    except WebSocketDisconnect:
        peer_socket = rtc_signals.disconnect(session_id, role, websocket)
        if peer_socket:
            await rtc_signals._safe_send(
                peer_socket,
                {"type": "peer-left", "role": role},
            )
        await _record_websocket_audit(
            action="disconnect", session_id=session_id, role=role,
            outcome="success", context=context if role == "professional" else None,
            organization_id=websocket_organization_id,
        )
    except Exception:
        peer_socket = rtc_signals.disconnect(session_id, role, websocket)
        if peer_socket:
            await rtc_signals._safe_send(
                peer_socket,
                {"type": "peer-left", "role": role},
            )
        await _record_websocket_audit(
            action="disconnect", session_id=session_id, role=role,
            outcome="error", context=context if role == "professional" else None,
            organization_id=websocket_organization_id,
        )


@app.get("/api/legal/documents")
def legal_documents(jurisdiction: str = "BR"):
    """Public, versioned copy used by every acceptance surface."""
    normalized_jurisdiction = _normalize_legal_jurisdiction(jurisdiction)
    return {
        **public_legal_catalog(),
        "jurisdiction": normalized_jurisdiction,
        "acceptance_required": _legal_acceptance_required(normalized_jurisdiction),
    }


def _midia_turn() -> tuple[bool, str]:
    """A sonda, blindada: /health nunca pode cair por causa dela.

    Health que quebra quando a checagem quebra e pior que health incompleto —
    quem o consulta perde a informacao toda, inclusive a que estava boa.
    """
    try:
        return turn_reachable()
    except Exception:
        LOGGER.exception("Unable to probe TURN")
        return False, "falha ao sondar o TURN"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "active_sessions": len(manager.active_sessions),
        "persistence": TENANT_STORE.status(),
        "tenant_authorization_mode": FROID_TENANT_AUTHORIZATION_MODE,
        "tenant_enforcement_organizations": len(
            FROID_TENANT_ENFORCEMENT_ORGANIZATIONS
        ),
        "media": {
            # `turn_configured` responde "as variaveis estao preenchidas".
            # `turn_reachable` responde "alguem atende naquela porta". Sao
            # perguntas diferentes, e por muito tempo so a primeira era feita:
            # numa consulta real as variaveis estavam certas, o contêiner do
            # relay nunca havia subido, e nada no sistema ligava as duas
            # coisas. Quem le /health precisa das duas respostas.
            "turn_configured": bool(FROID_TURN_URLS and FROID_TURN_SECRET),
            "turn_reachable": _midia_turn()[0],
            "turn_detail": _midia_turn()[1],
            "ice_transport_policy": FROID_ICE_TRANSPORT_POLICY,
        },
    }


@app.get("/ready")
def readiness():
    result = TENANT_STORE.readiness()
    legal_catalog = public_legal_catalog()
    any_legal_acceptance_required = any(
        FROID_LEGAL_ACCEPTANCE_REQUIRED_BY_JURISDICTION.values()
    )
    security_checks = {
        "clinical_record_encryption_configured": bool(CLINICAL_TEXT_CIPHER),
        # Era `bool(...)`: qualquer string nao-vazia passava. E esta a chave
        # que sustenta o anonimato do trabalhador no NR-1 — o HMAC da
        # matricula. Chave curta se reconstroi por forca bruta a partir da
        # folha de pagamento que o empregador ja tem.
        "datamart_pseudonym_key_configured": FROID_DATAMART_PSEUDONYM_KEY_FORTE,
        "google_token_encryption_configured": (
            bool(TOKEN_CIPHER) if _calendar_configured() else True
        ),
        "rtc_relay_configured": (
            bool(FROID_TURN_URLS and FROID_TURN_SECRET)
            if FROID_REQUIRE_TURN
            else True
        ),
        # A checagem que muda o veredito. Com FROID_REQUIRE_TURN ligado, o
        # servidor declara que a chamada DEPENDE do relay — e entao "as
        # variaveis estao preenchidas" nao e resposta: o que decide se a
        # sessao conecta e o relay atender.
        "rtc_relay_reachable": (
            _midia_turn()[0] if FROID_REQUIRE_TURN else True
        ),
    }
    billing_checks = {
        "stripe_secret_configured": bool(STRIPE_SECRET_KEY),
        "stripe_webhook_secret_configured": bool(STRIPE_WEBHOOK_SECRET),
        "subscription_prices_configured": all(STRIPE_SUBSCRIPTION_PRICE_IDS.values()),
        "subscription_persistence_enabled": TENANT_STORE.enabled,
    }
    result["checks"]["subscriptions_required"] = FROID_SUBSCRIPTIONS_REQUIRED
    result["professional_approval_required"] = FROID_PROFESSIONAL_APPROVAL_REQUIRED
    result["checks"].update(security_checks)
    result["checks"].update(billing_checks)
    result["checks"]["legal_supplier_configured"] = (
        bool(legal_catalog["supplier"].get("configured"))
        if any_legal_acceptance_required else True
    )
    result["checks"]["legal_audit_hmac_configured"] = (
        _legal_audit_key_configured()
        if any_legal_acceptance_required else True
    )
    result["checks"]["legal_ledger_persistence_enabled"] = (
        TENANT_STORE.enabled if any_legal_acceptance_required else True
    )
    if not all(security_checks.values()):
        result["ready"] = False
    if FROID_SUBSCRIPTIONS_REQUIRED and not all(billing_checks.values()):
        result["ready"] = False
    if any_legal_acceptance_required and not (
        legal_catalog["supplier"].get("configured")
        and _legal_audit_key_configured()
        and TENANT_STORE.enabled
    ):
        result["ready"] = False
    return JSONResponse(status_code=200 if result["ready"] else 503, content=result)

@app.post("/session/create")
def create_session(request: Request):
    user = _require_current_user(request)
    context = _require_professional_feature_access(request)
    # O outro ponto de inicio: aqui a sessao passa a existir e ganha dono.
    # Bloquear nos dois — aqui e em /api/session-invites — cobre a sessao
    # presencial e a remota sem alcancar reconexao de socket (que reaproveita um
    # session_id ja criado) nem o salvamento do relatorio.
    if _trial_blocks_new_session(user.get("email") or ""):
        raise HTTPException(status_code=402, detail=_trial_block_detail())
    session_id = str(uuid.uuid4())
    SESSION_OWNERS[session_id] = _normalize_email(user.get("email") or "")
    if context:
        SESSION_ORGANIZATIONS[session_id] = context.organization_id
    _save_identity_state()
    return {"session_id": session_id, "organization_id": context.organization_id if context else ""}

@app.post("/api/session-invites")
async def create_session_invite(request: Request):
    current_user = _require_current_user(request)
    context = _require_professional_feature_access(request)
    # Ponto de inicio explicito de uma sessao. O bloqueio da cortesia vive aqui,
    # e nao dentro de _require_professional_feature_access, porque aquele portao
    # e compartilhado por dezoito endpoints — entre eles /api/session-summary,
    # que roda no FIM do atendimento. Bloquear la derrubaria sessao em
    # andamento, que e exatamente o que este item nao pode fazer.
    if _trial_blocks_new_session(current_user.get("email") or ""):
        raise HTTPException(status_code=402, detail=_trial_block_detail())
    body = await request.json()
    professional_email = _normalize_email(current_user.get("email") or "")
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
    session_mode = str(body.get("session_mode") or "remote").strip().lower()
    spoken_language = normalize_session_locale(body.get("spoken_language"))
    analysis_language = normalize_session_locale(
        body.get("analysis_language"), spoken_language
    )
    report_locale = normalize_session_locale(
        body.get("report_locale"), analysis_language
    )
    patient_ui_locale = normalize_session_locale(
        body.get("patient_ui_locale"), spoken_language
    )
    if session_mode not in {"remote", "presential_mobile"}:
        raise HTTPException(status_code=400, detail="modalidade de sessão inválida")
    if not _session_matches_context(session_id, context):
        raise HTTPException(status_code=409, detail="sessão pertence a outra organização")
    existing_owner = _normalize_email(SESSION_OWNERS.get(session_id) or "")
    if existing_owner and existing_owner != professional_email:
        raise HTTPException(status_code=409, detail="sessão pertence a outro profissional")

    if not patient_name:
        raise HTTPException(status_code=400, detail="Nome do paciente obrigatório")
    if not patient_email and not patient_phone:
        raise HTTPException(status_code=400, detail="Informe email ou WhatsApp do paciente")
    if payment_mode not in {"package", "single"}:
        raise HTTPException(status_code=400, detail="payment_mode deve ser package ou single")
    if session_value_cents <= 0:
        raise HTTPException(status_code=400, detail="Informe o valor da sessão")
    if payment_mode == "package" and package_sessions <= 0:
        raise HTTPException(status_code=400, detail="Informe o número de sessões do pacote")
    if payment_mode == "single" and not pix_code:
        raise HTTPException(status_code=400, detail="Código PIX obrigatório para sessão avulsa")

    contact_key = _patient_contact_key(patient_email, patient_phone)
    known_patient_id = PATIENTS_BY_CONTACT.get(contact_key)
    token = secrets.token_urlsafe(24)
    base_url = body.get("base_url") or ""
    invite_url = _public_invite_url(base_url, token)
    patient_session_url = _public_patient_session_url(base_url, session_id, token)
    now = _utc_now_iso()
    package_total_cents = (
        session_value_cents * package_sessions if payment_mode == "package" else session_value_cents
    )
    # Decisão do profissional, tomada no convite: este paciente poderá ver as
    # próprias sessões e relatórios na área dele? O padrão de um convite NOVO é
    # negativo — liberar dado clínico ao paciente é ato do profissional, e ato
    # não se pratica por omissão. Cadastros anteriores a este controle seguem
    # como estão; quem trata disso é _patient_results_enabled.
    patient_results_enabled = bool(body.get("patient_results_enabled"))

    invite = {
        "id": str(uuid.uuid4()),
        "token": token,
        "session_id": session_id,
        "session_mode": session_mode,
        "patient_results_enabled": patient_results_enabled,
        "spoken_language": spoken_language,
        "analysis_language": analysis_language,
        "report_locale": report_locale,
        "patient_ui_locale": patient_ui_locale,
        "status": "pending",
        "patient_id": known_patient_id,
        "patient_known": bool(known_patient_id),
        "patient_name": patient_name,
        "patient_email": patient_email,
        "patient_phone": patient_phone,
        "professional_email": professional_email,
        "organization_id": context.organization_id if context else "",
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
        "patient_session_url": patient_session_url,
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
    SESSION_OWNERS[session_id] = professional_email
    if context:
        SESSION_ORGANIZATIONS[session_id] = context.organization_id
    _record_session_event("invite_created", invite)
    _save_identity_state()
    return invite


@app.get("/api/sessions/{session_id}/configuration")
async def get_professional_session_configuration(session_id: str, request: Request):
    """Return server-authoritative session language and modality."""
    current_user = _require_current_user(request)
    context = _require_professional_feature_access(request)
    professional_email = _normalize_email(current_user.get("email") or "")
    invite = next(
        (
            item
            for item in SESSION_INVITES.values()
            if str(item.get("session_id") or "") == session_id
            and _normalize_email(item.get("professional_email") or "") == professional_email
            and _session_matches_context(session_id, context)
        ),
        None,
    )
    if not invite:
        raise HTTPException(status_code=404, detail="configuração da sessão não encontrada")
    spoken_language = normalize_session_locale(invite.get("spoken_language"))
    analysis_language = normalize_session_locale(invite.get("analysis_language"), spoken_language)
    report_locale = normalize_session_locale(invite.get("report_locale"), analysis_language)
    patient_ui_locale = normalize_session_locale(invite.get("patient_ui_locale"), spoken_language)
    return {
        "session_id": session_id,
        "session_mode": invite.get("session_mode") or "remote",
        "spoken_language": spoken_language,
        "analysis_language": analysis_language,
        "report_locale": report_locale,
        "patient_ui_locale": patient_ui_locale,
        "patient": {
            "id": invite.get("patient_id") or "",
            "name": invite.get("patient_name") or "",
            "email": invite.get("patient_email") or "",
            "phone": invite.get("patient_phone") or "",
        },
    }


@app.get("/api/professional/receivables")
async def professional_receivables(request: Request):
    user = _require_current_user(request)
    context = _tenant_context_from_request(request)
    if context is None:
        raise HTTPException(status_code=403, detail="contexto organizacional indisponível")
    owner_email = _normalize_email(user.get("email") or "")
    grouped: Dict[str, dict] = {}

    for invite in SESSION_INVITES.values():
        if not isinstance(invite, dict) or not _can_access_invite_finance(
            invite, owner_email, context.organization_id if context else ""
        ):
            continue
        key = _invite_patient_key(invite)
        patient = _invite_patient_identity(invite)
        payment = invite.get("payment") if isinstance(invite.get("payment"), dict) else {}
        due_cents = _receivable_due_cents(invite)
        received_cents = min(_receivable_received_cents(invite), due_cents)
        row = grouped.setdefault(
            key,
            {
                "patient_key": key,
                "patient": patient,
                "total_due_cents": 0,
                "total_received_cents": 0,
                "total_pending_cents": 0,
                "session_count": 0,
                "package_count": 0,
                "single_count": 0,
                "last_invite_at": "",
                "items": [],
            },
        )
        row["total_due_cents"] += due_cents
        row["total_received_cents"] += received_cents
        row["session_count"] += max(1, _local_int(payment.get("package_sessions") or 1))
        if payment.get("mode") == "package":
            row["package_count"] += 1
        else:
            row["single_count"] += 1
        created_at = str(invite.get("created_at") or "")
        if created_at > str(row.get("last_invite_at") or ""):
            row["last_invite_at"] = created_at
        row["items"].append(_receivable_item(invite))

    rows = []
    for row in grouped.values():
        row["total_pending_cents"] = max(0, row["total_due_cents"] - row["total_received_cents"])
        row["status"] = _receivable_status(row["total_due_cents"], row["total_received_cents"])
        row["total_due_brl"] = _format_brl(row["total_due_cents"])
        row["total_received_brl"] = _format_brl(row["total_received_cents"])
        row["total_pending_brl"] = _format_brl(row["total_pending_cents"])
        rows.append(row)

    status_rank = {"pendente": 0, "parcial": 1, "sem_valor": 2, "recebido": 3}
    rows.sort(
        key=lambda item: (
            status_rank.get(str(item.get("status") or ""), 9),
            item.get("patient", {}).get("name") or "",
        )
    )
    totals_due = sum(_local_int(row["total_due_cents"]) for row in rows)
    totals_received = sum(_local_int(row["total_received_cents"]) for row in rows)
    return {
        "rows": rows,
        "summary": {
            "patients": len(rows),
            "total_due_cents": totals_due,
            "total_received_cents": totals_received,
            "total_pending_cents": max(0, totals_due - totals_received),
            "total_due_brl": _format_brl(totals_due),
            "total_received_brl": _format_brl(totals_received),
            "total_pending_brl": _format_brl(max(0, totals_due - totals_received)),
        },
    }


@app.post("/api/professional/receivables/update")
async def update_professional_receivable(request: Request):
    user = _require_current_user(request)
    context = _tenant_context_from_request(request)
    if context is None:
        raise HTTPException(status_code=403, detail="contexto organizacional indisponível")
    owner_email = _normalize_email(user.get("email") or "")
    body = await request.json()
    patient_key = str(body.get("patient_key") or "").strip()
    action = str(body.get("action") or "").strip().lower()
    received_cents = body.get("received_cents")
    if not patient_key:
        raise HTTPException(status_code=400, detail="patient_key obrigatório")
    if action not in {"paid", "pending", "partial"}:
        raise HTTPException(status_code=400, detail="action deve ser paid, pending ou partial")

    matching = [
        invite
        for invite in SESSION_INVITES.values()
        if isinstance(invite, dict)
        and _invite_patient_key(invite) == patient_key
        and _can_access_invite_finance(
            invite, owner_email, context.organization_id if context else ""
        )
    ]
    if not matching:
        raise HTTPException(status_code=404, detail="Recebimento não encontrado")

    remaining_partial = max(0, _local_int(received_cents)) if action == "partial" else 0
    now = _utc_now_iso()
    for invite in matching:
        payment = invite.setdefault("payment", {})
        due_cents = _receivable_due_cents(invite)
        if action == "paid":
            payment["received_cents"] = due_cents
            payment["payment_status"] = "paid"
            payment["received_at"] = now
        elif action == "pending":
            payment["received_cents"] = 0
            payment["payment_status"] = "pending_pix" if payment.get("mode") == "single" else "prearranged"
            payment["received_at"] = ""
        else:
            applied = min(due_cents, remaining_partial)
            payment["received_cents"] = applied
            payment["payment_status"] = "partial" if applied < due_cents else "paid"
            payment["received_at"] = now if applied else ""
            remaining_partial = max(0, remaining_partial - applied)
    _save_identity_state()
    return {"updated": True, "patient_key": patient_key}


@app.get("/api/admin/overview")
async def admin_overview(request: Request):
    _require_admin_user(request)
    reports = [
        report
        for report in _load_session_reports().values()
        if isinstance(report, dict)
    ]
    professional_rows = []
    for email, profile in PROFESSIONAL_PROFILES.items():
        if not isinstance(profile, dict):
            continue
        access = _professional_access_status(email)
        professional_reports = [
            report for report in reports if _report_owner_email(report) == _normalize_email(email)
        ]
        professional_invites = [
            invite
            for invite in SESSION_INVITES.values()
            if isinstance(invite, dict)
            and _normalize_email(invite.get("professional_email") or "") == _normalize_email(email)
        ]
        due_cents = sum(_receivable_due_cents(invite) for invite in professional_invites)
        received_cents = sum(
            min(_receivable_received_cents(invite), _receivable_due_cents(invite))
            for invite in professional_invites
        )
        professional_rows.append(
            {
                "email": email,
                "name": profile.get("owner_name") or profile.get("organization_name") or email,
                "account_type": profile.get("account_type") or "",
                "payment_status": profile.get("payment_status") or "",
                "selected_plan": profile.get("selected_plan") or "",
                "total_sessions": access.get("total_sessions", 0),
                "used_sessions": access.get("used_sessions", 0),
                "remaining_sessions": access.get("remaining_sessions", 0),
                "manual_approval_status": access.get("manual_approval_status", "pending"),
                "manual_approval_pending": access.get("manual_approval_pending", False),
                "reports_count": len(professional_reports),
                "patients_count": len({
                    str((report.get("patient") or {}).get("id") or report.get("patientId") or report.get("patientName") or "")
                    for report in professional_reports
                    if isinstance(report, dict)
                }),
                "invites_count": len(professional_invites),
                "due_cents": due_cents,
                "received_cents": received_cents,
                "pending_cents": max(0, due_cents - received_cents),
                "due_brl": _format_brl(due_cents),
                "received_brl": _format_brl(received_cents),
                "pending_brl": _format_brl(max(0, due_cents - received_cents)),
                "updated_at": profile.get("updated_at") or "",
            }
        )

    patient_rows = []
    for patient_id, patient in PATIENTS.items():
        if not isinstance(patient, dict):
            continue
        patient_reports = [
            report
            for report in reports
            if str((report.get("patient") or {}).get("id") or report.get("patientId") or "") == str(patient_id)
        ]
        patient_rows.append(
            {
                "id": patient_id,
                "name": patient.get("name") or "Paciente sem nome",
                "email": patient.get("email") or "",
                "phone": patient.get("phone") or "",
                "sessions_count": len(patient_reports),
                "created_at": patient.get("created_at") or "",
                "updated_at": patient.get("updated_at") or "",
            }
        )

    total_due = sum(_local_int(row.get("due_cents")) for row in professional_rows)
    total_received = sum(_local_int(row.get("received_cents")) for row in professional_rows)
    professional_rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    patient_rows.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    return {
        "summary": {
            "professionals": len(professional_rows),
            "pending_professional_approvals": sum(
                1 for row in professional_rows
                if row.get("manual_approval_status") == "pending"
            ),
            "patients": len(patient_rows),
            "session_reports": len(reports),
            "invites": len(SESSION_INVITES),
            "total_due_cents": total_due,
            "total_received_cents": total_received,
            "total_pending_cents": max(0, total_due - total_received),
            "total_due_brl": _format_brl(total_due),
            "total_received_brl": _format_brl(total_received),
            "total_pending_brl": _format_brl(max(0, total_due - total_received)),
        },
        "professionals": professional_rows,
        "patients": patient_rows[:300],
    }


@app.get("/api/admin/professionals/{professional_email}")
async def admin_professional_detail(professional_email: str, request: Request):
    _require_admin_user(request)
    email = _normalize_email(unquote(professional_email))
    profile = PROFESSIONAL_PROFILES.get(email)
    if not isinstance(profile, dict):
        raise HTTPException(status_code=404, detail="profissional não encontrado")
    _record_admin_audit_event(
        request,
        action="admin_open_professional",
        target=email,
        detail={"profile_id": profile.get("id") or ""},
    )

    reports = [
        _report_for_api(_enrich_report_patient(report))
        for report in _load_session_reports().values()
        if isinstance(report, dict) and _report_owner_email(report) == email
    ]
    reports.sort(
        key=lambda report: str(report.get("createdAt") or report.get("created_at") or ""),
        reverse=True,
    )
    invites = [
        invite
        for invite in SESSION_INVITES.values()
        if isinstance(invite, dict)
        and _normalize_email(invite.get("professional_email") or "") == email
    ]
    invites.sort(key=lambda invite: str(invite.get("created_at") or ""), reverse=True)

    patient_map: Dict[str, dict] = {}
    for invite in invites:
        patient = _invite_patient_identity(invite)
        key = str(patient.get("id") or patient.get("email") or patient.get("phone") or patient.get("name") or "")
        if key:
            patient_map[key] = patient
    for report in reports:
        patient = report.get("patient") if isinstance(report.get("patient"), dict) else {}
        key = str(patient.get("id") or report.get("patientId") or report.get("patientName") or "")
        if key:
            patient_map[key] = {
                "id": patient.get("id") or report.get("patientId") or "",
                "name": patient.get("name") or report.get("patientName") or "Paciente sem nome",
                "email": patient.get("email") or "",
                "phone": patient.get("phone") or "",
                "document": patient.get("document") or report.get("patientDocument") or "",
            }

    receivable_items = []
    due_cents = 0
    received_cents = 0
    for invite in invites:
        item = _receivable_item(invite)
        due_cents += _local_int(item.get("due_cents"))
        received_cents += _local_int(item.get("received_cents"))
        receivable_items.append(
            {
                **item,
                "patient": _invite_patient_identity(invite),
                "status": invite.get("status") or "",
            }
        )

    report_rows = []
    for report in reports[:120]:
        session_average = report.get("sessionAverage") if isinstance(report.get("sessionAverage"), dict) else {}
        report_rows.append(
            {
                "session_id": report.get("sessionId") or report.get("session_id") or "",
                "created_at": report.get("createdAt") or report.get("created_at") or "",
                "patient": report.get("patient") or {},
                "ipm": session_average.get("ipmAvg"),
                "idm": session_average.get("idmAvg"),
                "dominant_zone": session_average.get("dominantZone"),
                "theme": session_average.get("theme") or session_average.get("dominantTheme") or "",
                "summary": ((report.get("sessionSummary") or {}) if isinstance(report.get("sessionSummary"), dict) else {}).get("summary") or "",
            }
        )

    return {
        "profile": profile,
        "access_status": _professional_access_status(email),
        "summary": {
            "patients": len(patient_map),
            "reports": len(reports),
            "invites": len(invites),
            "total_due_cents": due_cents,
            "total_received_cents": received_cents,
            "total_pending_cents": max(0, due_cents - received_cents),
            "total_due_brl": _format_brl(due_cents),
            "total_received_brl": _format_brl(received_cents),
            "total_pending_brl": _format_brl(max(0, due_cents - received_cents)),
        },
        "patients": list(patient_map.values())[:300],
        "receivables": receivable_items[:300],
        "reports": report_rows,
    }


@app.get("/api/admin/patients/{patient_id}")
async def admin_patient_detail(patient_id: str, request: Request):
    """Perfil TRANSVERSAL do paciente para o administrador: reúne os relatórios
    do paciente de TODOS os profissionais (a página do profissional é escopada
    ao dono; esta não). Somente leitura."""
    _require_admin_user(request)
    pid = unquote(patient_id)
    patient = PATIENTS.get(pid) if isinstance(PATIENTS.get(pid), dict) else None

    reports = []
    for report in _load_session_reports().values():
        if not isinstance(report, dict):
            continue
        rp = report.get("patient") if isinstance(report.get("patient"), dict) else {}
        rid = str(rp.get("id") or report.get("patientId") or "")
        if rid != str(pid):
            continue
        reports.append(_report_for_api(_enrich_report_patient(report)))
    reports.sort(
        key=lambda report: str(report.get("createdAt") or report.get("created_at") or ""),
        reverse=True,
    )

    if patient is None and not reports:
        raise HTTPException(status_code=404, detail="paciente não encontrado")

    _record_admin_audit_event(
        request,
        action="admin_open_patient",
        target=str(pid),
        detail={"reports": len(reports)},
    )

    # Identidade consolidada (preferindo o cadastro; caindo no relatório).
    latest_rp = (reports[0].get("patient") if reports else {}) or {}
    identity = {
        "id": str(pid),
        "name": (patient or {}).get("name") or latest_rp.get("name") or "Paciente sem nome",
        "email": (patient or {}).get("email") or latest_rp.get("email") or "",
        "phone": (patient or {}).get("phone") or latest_rp.get("phone") or "",
        "created_at": (patient or {}).get("created_at") or "",
        "updated_at": (patient or {}).get("updated_at") or "",
    }

    professionals: Dict[str, dict] = {}
    report_rows = []
    for report in reports[:200]:
        owner = _report_owner_email(report)
        owner_profile = PROFESSIONAL_PROFILES.get(owner) if isinstance(PROFESSIONAL_PROFILES.get(owner), dict) else {}
        owner_name = (owner_profile or {}).get("owner_name") or (owner_profile or {}).get("organization_name") or owner
        if owner:
            professionals[owner] = {"email": owner, "name": owner_name}
        session_average = report.get("sessionAverage") if isinstance(report.get("sessionAverage"), dict) else {}
        report_rows.append(
            {
                "session_id": report.get("sessionId") or report.get("session_id") or "",
                "created_at": report.get("createdAt") or report.get("created_at") or "",
                "professional_email": owner,
                "professional_name": owner_name,
                "ipm": session_average.get("ipmAvg"),
                "idm": session_average.get("idmAvg"),
                "dominant_zone": session_average.get("dominantZone"),
                "coherence": session_average.get("coherenceStatus") or "",
                "theme": session_average.get("theme") or session_average.get("dominantTheme") or "",
                "summary": ((report.get("sessionSummary") or {}) if isinstance(report.get("sessionSummary"), dict) else {}).get("summary") or "",
            }
        )

    return {
        "patient": identity,
        "summary": {
            "reports": len(reports),
            "professionals": len(professionals),
        },
        "professionals": list(professionals.values()),
        "reports": report_rows,
    }


@app.post("/api/admin/professionals/{professional_email}/access-approval")
async def admin_professional_access_approval(professional_email: str, request: Request):
    admin = _require_admin_user(request)
    email = _normalize_email(unquote(professional_email))
    profile = PROFESSIONAL_PROFILES.get(email)
    if not isinstance(profile, dict):
        raise HTTPException(status_code=404, detail="profissional não encontrado")

    body = await request.json()
    next_status = str(body.get("status") or "").strip().lower()
    if next_status not in {"pending", "approved", "rejected", "suspended"}:
        raise HTTPException(status_code=400, detail="status de aprovação inválido")
    note = str(body.get("note") or "").strip()[:1000]
    previous_status = str(
        profile.get("access_approval_status") or "approved"
    ).strip().lower()
    now = _utc_now_iso()
    profile["access_approval_status"] = next_status
    profile["access_approval_updated_at"] = now
    profile["access_approval_updated_by"] = _normalize_email(admin.get("email") or "")
    profile["access_approval_note"] = note
    if next_status == "approved":
        profile["access_approved_at"] = now
        profile["access_approved_by"] = _normalize_email(admin.get("email") or "")
    PROFESSIONAL_PROFILES[email] = profile
    # Sem isto a aprovacao vivia SO em memoria.
    #
    # Este era o unico endpoint administrativo que muta perfil, e o unico que
    # nao persistia. O efeito e cruel de diagnosticar: aprovar funciona, a tela
    # muda, o cliente entra — e no proximo `docker compose up` do backend a
    # aprovacao desaparece e ele volta para "aguardando liberacao" sem que nada
    # tenha sido desfeito por ninguem. Num dia de deploy, aprovar e reconstruir
    # o container produz exatamente o sintoma de "o botao nao fez nada".
    #
    # E como o espelho do PostgreSQL roda dentro de _save_identity_state, a
    # aprovacao tambem nunca chegava ao banco onde o modulo NR-1 vive.
    _save_identity_state()
    _record_admin_audit_event(
        request,
        action="admin_professional_access_approval",
        target=email,
        detail={
            "previous_status": previous_status,
            "new_status": next_status,
            "note": note,
        },
    )
    return {
        "status": "ok",
        "professional_email": email,
        "access_status": _professional_access_status(email),
    }


# ---------------------------------------------------------------------------
# Controle administrativo de acesso.
#
# Tres alavancas separadas de proposito, porque a escolha errada causa dano
# colateral: desabilitar a PESSOA quando se queria tirar o acesso dela a UM
# cliente derruba o acesso dela a todos os outros. O endpoint nao adivinha qual
# alavanca o operador quis; ele exige que a alavanca seja nomeada na URL.
#
# Toda operacao devolve `atingidos`, e o store recusa qualquer coisa acima de
# um. E toda operacao entra na trilha de auditoria com quem fez e o que mudou.
# ---------------------------------------------------------------------------


def _exigir_store_ativo() -> None:
    if not TENANT_STORE.enabled:
        raise HTTPException(
            status_code=503,
            detail="controle de acesso indisponivel: armazenamento multi-tenant desligado",
        )


@app.get("/api/admin/access")
async def admin_access_snapshot(request: Request):
    """Estado atual de um e-mail ou de uma organizacao. Consulte ANTES de mexer."""
    _require_admin_user(request)
    _exigir_store_ativo()
    email = _normalize_email(request.query_params.get("email") or "")
    organization_id = str(request.query_params.get("organization_id") or "").strip()
    if not email and not organization_id:
        raise HTTPException(
            status_code=400, detail="informe email ou organization_id"
        )
    return TENANT_STORE.access_snapshot(email=email, organization_id=organization_id)


@app.post("/api/admin/access/user")
async def admin_set_user_access(request: Request):
    """Desabilita ou reabilita UMA pessoa, em todas as organizacoes dela."""
    admin = _require_admin_user(request)
    _exigir_store_ativo()
    body = await request.json()
    email = _normalize_email(body.get("email") or "")
    status = str(body.get("status") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email obrigatorio")
    if status not in TENANT_STORE.ESTADOS_USUARIO:
        raise HTTPException(status_code=400, detail="estado invalido para usuario")
    ator = _normalize_email(admin.get("email") or "")
    if email == ator and status != "active":
        # Sem isto o administrador se tranca para fora e nao ha como voltar
        # pela interface -- so por SQL no servidor.
        raise HTTPException(
            status_code=400, detail="um administrador nao pode desabilitar a propria conta"
        )
    try:
        resultado = TENANT_STORE.set_user_status(email, status, ator=ator)
    except (ValueError, RuntimeError) as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    if not resultado.get("encontrado"):
        raise HTTPException(status_code=404, detail="usuario nao encontrado")
    _expirar_sessoes_de(email)
    _record_admin_audit_event(
        request,
        action="admin_set_user_access",
        target=email,
        detail={"anterior": resultado.get("anterior"), "atual": status},
    )
    return resultado


@app.post("/api/admin/access/organization")
async def admin_set_organization_access(request: Request):
    """Suspende ou reativa UMA organizacao, com todos os usuarios dela."""
    admin = _require_admin_user(request)
    _exigir_store_ativo()
    body = await request.json()
    organization_id = str(body.get("organization_id") or "").strip()
    status = str(body.get("status") or "").strip().lower()
    if not organization_id:
        raise HTTPException(status_code=400, detail="organization_id obrigatorio")
    if status not in TENANT_STORE.ESTADOS_ORGANIZACAO:
        raise HTTPException(status_code=400, detail="estado invalido para organizacao")
    try:
        resultado = TENANT_STORE.set_organization_status(
            organization_id, status, ator=_normalize_email(admin.get("email") or "")
        )
    except (ValueError, RuntimeError) as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    if not resultado.get("encontrado"):
        raise HTTPException(status_code=404, detail="organizacao nao encontrada")
    _expirar_sessoes_da_organizacao(organization_id)
    _record_admin_audit_event(
        request,
        action="admin_set_organization_access",
        target=organization_id,
        detail={
            "nome": resultado.get("nome"),
            "anterior": resultado.get("anterior"),
            "atual": status,
            "usuarios_afetados": resultado.get("usuarios_afetados"),
        },
    )
    return resultado


@app.post("/api/admin/access/membership")
async def admin_set_membership_access(request: Request):
    """Revoga ou restaura o vinculo de UMA pessoa com UMA organizacao.

    E a alavanca cirurgica: as demais organizacoes da mesma pessoa ficam
    intactas. E a certa para retirar um acesso de teste.
    """
    admin = _require_admin_user(request)
    _exigir_store_ativo()
    body = await request.json()
    email = _normalize_email(body.get("email") or "")
    organization_id = str(body.get("organization_id") or "").strip()
    status = str(body.get("status") or "").strip().lower()
    if not email or not organization_id:
        raise HTTPException(
            status_code=400, detail="email e organization_id obrigatorios"
        )
    if status not in TENANT_STORE.ESTADOS_VINCULO:
        raise HTTPException(status_code=400, detail="estado invalido para vinculo")
    try:
        resultado = TENANT_STORE.set_membership_status(
            email, organization_id, status,
            ator=_normalize_email(admin.get("email") or ""),
        )
    except (ValueError, RuntimeError) as erro:
        raise HTTPException(status_code=400, detail=str(erro))
    if not resultado.get("encontrado"):
        raise HTTPException(status_code=404, detail="vinculo nao encontrado")
    _expirar_sessoes_de(email)
    _record_admin_audit_event(
        request,
        action="admin_set_membership_access",
        target="%s@%s" % (email, organization_id),
        detail={
            "organizacao": resultado.get("nome"),
            "anterior": resultado.get("anterior"),
            "atual": status,
        },
    )
    return resultado

@app.get("/api/session-invites/{token}")
async def get_session_invite(token: str):
    invite = SESSION_INVITES.get(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    _record_session_event("invite_opened", invite)
    patient = PATIENTS.get(str(invite.get("patient_id") or ""))
    return {
        **invite,
        "password_only": bool(
            isinstance(patient, dict) and patient.get("password_hash")
        ),
    }


@app.post("/api/session-invites/{token}/accept")
async def accept_session_invite(token: str, request: Request):
    # Limita tentativas por IP para conter varredura de tokens de convite.
    _rate_limit_guard(
        "invite_accept", _client_ip(request), 30, 900.0,
        "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
    )
    invite = SESSION_INVITES.get(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    if invite.get("status") == "accepted":
        return invite

    body = await request.json()
    password = str(body.get("password") or "")
    required_consents = [
        "terms_of_use",
        "privacy_policy",
        "sensitive_data_processing",
        "audio_video_processing",
    ]
    legal_jurisdiction = _normalize_legal_jurisdiction(
        invite.get("patient_ui_locale") or invite.get("spoken_language")
    )
    legal_acceptance_required = _legal_acceptance_required(legal_jurisdiction)
    if legal_acceptance_required:
        required_consents.append("patient_tcle")
    now = _utc_now_iso()
    known_patient_id = str(invite.get("patient_id") or "")
    known_patient = PATIENTS.get(known_patient_id) if known_patient_id else None
    returning_patient = bool(
        isinstance(known_patient, dict) and known_patient.get("password_hash")
    )

    if returning_patient:
        patient = known_patient
        if not _verify_patient_password(patient, password):
            raise HTTPException(status_code=401, detail="Senha do paciente inválida")
        consent = _patient_consent_preferences(patient)
        if consent and not patient.get("consent_preferences"):
            patient["consent_preferences"] = consent
            patient["consent_updated_at"] = patient.get("lgpd_consent_at") or now
        missing = [key for key in required_consents if consent.get(key) is not True]
        legal_version_outdated = (
            legal_acceptance_required
            and patient.get("lgpd_consent_version") != LEGAL_DOCUMENT_VERSION
        )
        if missing or legal_version_outdated:
            raise HTTPException(
                status_code=403,
                detail="Autorização do paciente inativa ou desatualizada. Atualize-a no Portal do Paciente.",
            )
        patient_id = known_patient_id
        patient_name = str(patient.get("name") or invite.get("patient_name") or "").strip()
        patient_email = _normalize_email(patient.get("email") or "")
        patient_phone = _digits_only(patient.get("phone") or "")
        consent_source = "persisted_patient_authorization"
    else:
        patient_name = str(body.get("name") or invite.get("patient_name") or "").strip()
        patient_email = _normalize_email(body.get("email") or invite.get("patient_email") or "")
        patient_phone = _digits_only(body.get("phone") or invite.get("patient_phone") or "")
        document = _digits_only(body.get("document") or "")
        sex = str(body.get("sex") or "").strip()[:20]
        birth_date = str(body.get("birth_date") or "").strip()
        consent = body.get("consent") or {}
        missing = [key for key in required_consents if consent.get(key) is not True]
        if missing:
            raise HTTPException(status_code=400, detail=f"Consentimentos obrigatorios ausentes: {', '.join(missing)}")
        if not patient_name:
            raise HTTPException(status_code=400, detail="Nome do paciente obrigatório")
        if not patient_email:
            raise HTTPException(status_code=400, detail="E-mail do paciente obrigatório")
        # Fase de testes: CPF e confirmação de e-mail nao sao mais exigidos; a
        # senha continua obrigatoria.
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Senha do paciente obrigatória com no minimo 8 caracteres")

        contact_key = _patient_contact_key(patient_email, patient_phone)
        patient_id = (
            known_patient_id
            or PATIENTS_BY_CONTACT.get(contact_key)
            or PATIENTS_BY_CONTACT.get(f"document:{document}")
            or str(uuid.uuid4())
        )
        patient = {
            "id": patient_id,
            "name": patient_name,
            "email": patient_email,
            "phone": patient_phone,
            "document": document,
            "sex": sex,
            "birth_date": birth_date,
            "created_at": PATIENTS.get(patient_id, {}).get("created_at") or now,
            "updated_at": now,
            "lgpd_consent_version": LEGAL_DOCUMENT_VERSION,
            "legal_jurisdiction": legal_jurisdiction,
            "lgpd_consent_at": now,
            "consent_preferences": consent,
            "consent_updated_at": now,
            # Escolha feita pelo profissional ao criar o convite. Num cadastro
            # que já existe, a escolha anterior prevalece: um convite novo para
            # um paciente conhecido não deve reabrir nem fechar o acesso dele
            # sem que alguém decida isso explicitamente na ficha.
            "portal_results_enabled": (
                PATIENTS.get(patient_id, {}).get("portal_results_enabled")
                if patient_id in PATIENTS
                else bool(invite.get("patient_results_enabled"))
            ),
        }
        _set_patient_password(patient, password)
        PATIENTS[patient_id] = patient
        for patient_contact_key in _patient_contact_keys(patient):
            PATIENTS_BY_CONTACT[patient_contact_key] = patient_id
        consent_source = "initial_registration"

    patient_portal_session = _issue_patient_portal_session(patient)

    ledger_payload = {
        "patient_id": patient_id,
        "invite_id": invite.get("id"),
        "session_id": invite.get("session_id"),
        "consent": consent,
        "source": consent_source,
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

    if consent.get("patient_tcle") is True:
        legal_catalog = public_legal_catalog()["documents"]
        patient_legal_acceptances = {
            key: {
                "version": legal_catalog[key]["version"],
                "sha256": legal_catalog[key]["sha256"],
                "accepted_at": now,
            }
            for key in ("patient_tcle", "terms", "privacy")
        }
        _record_legal_documents(
            request=request,
            subject_reference=patient_id,
            subject_kind="patient",
            organization_id=_invite_organization_id(invite),
            acceptances=patient_legal_acceptances,
            context="patient_invite_acceptance",
        )

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
            "session_url": invite.get("patient_session_url")
            or _public_patient_session_url("", str(invite.get("session_id") or ""), token),
        }
    )
    _record_session_event("invite_accepted", invite)
    return {
        **invite,
        "patient": patient_portal_session["patient"],
        "patient_portal_token": patient_portal_session["token"],
        "consent": ledger_entry,
    }


@app.post("/api/patient-sessions/{session_id}/join")
async def join_patient_session(session_id: str, request: Request):
    body = await request.json()
    invite_token = str(body.get("invite_token") or "").strip()
    invite = SESSION_INVITES.get(invite_token)
    if not invite or str(invite.get("session_id") or "") != session_id:
        raise HTTPException(status_code=404, detail="Sessão do paciente não encontrada")
    if (
        SESSION_ORGANIZATIONS.get(session_id)
        and _invite_organization_id(invite) != SESSION_ORGANIZATIONS.get(session_id)
    ):
        raise HTTPException(status_code=403, detail="sessão pertence a outra organização")
    if invite.get("status") != "accepted":
        raise HTTPException(
            status_code=403,
            detail="Confirme o cadastro e os consentimentos antes de entrar na sessão",
        )

    now = _utc_now_iso()
    entry = {
        "session_id": session_id,
        "invite_id": invite.get("id"),
        "patient_id": invite.get("patient_id"),
        "patient_name": invite.get("patient_name"),
        "joined_at": now,
        "remote_addr": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", ""),
    }
    PATIENT_SESSION_ENTRIES.setdefault(session_id, []).append(entry)
    event = _record_session_event("patient_joined", invite, {"joined_at": now})
    return {
        "status": "joined",
        "session_id": session_id,
        "patient_name": invite.get("patient_name"),
        "session_mode": invite.get("session_mode") or "remote",
        "spoken_language": normalize_session_locale(invite.get("spoken_language")),
        "analysis_language": normalize_session_locale(
            invite.get("analysis_language"),
            normalize_session_locale(invite.get("spoken_language")),
        ),
        "report_locale": normalize_session_locale(
            invite.get("report_locale"),
            normalize_session_locale(invite.get("spoken_language")),
        ),
        "patient_ui_locale": normalize_session_locale(
            invite.get("patient_ui_locale"),
            normalize_session_locale(invite.get("spoken_language")),
        ),
        "joined_at": now,
        "join_count": len(PATIENT_SESSION_ENTRIES.get(session_id, [])),
        "event_id": event.get("id"),
    }


@app.post("/api/patient-auth/login")
async def patient_portal_login(payload: PatientPortalLoginRequest, request: Request):
    # CPF ou e-mail no mesmo campo. A presença do "@" decide como interpretar:
    # aplicar _digits_only num e-mail extrairia digitos avulsos do texto e
    # consultaria um documento que ninguem digitou.
    identificador = str(payload.document or payload.email or "").strip()
    password = str(payload.password or "")
    if "@" in identificador:
        document = ""
        email = _normalize_email(identificador)
    else:
        document = _digits_only(identificador)
        email = ""
    if (not document and not email) or not password:
        raise HTTPException(
            status_code=400,
            detail="Informe CPF ou e-mail e a senha para acessar o portal do paciente",
        )
    now = datetime.now(timezone.utc).timestamp()
    remote_reference = request.client.host if request.client else "unknown"
    attempt_key = hashlib.sha256(
        f"{remote_reference}:{document or email}".encode("utf-8")
    ).hexdigest()
    recent_attempts = [
        attempt for attempt in PATIENT_LOGIN_ATTEMPTS.get(attempt_key, [])
        if attempt >= now - 900
    ]
    if len(recent_attempts) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde 15 minutos antes de tentar novamente.",
        )
    recent_attempts.append(now)
    PATIENT_LOGIN_ATTEMPTS[attempt_key] = recent_attempts
    patient = (
        _find_registered_patient_by_document(document)
        if document
        else _find_registered_patient_by_email(email)
    )
    # Recusa uniforme: identificador inexistente e senha errada respondem igual.
    # Duas mensagens distintas transformavam a rota em consulta de quem e
    # paciente no FROID — e "este CPF esta em tratamento" e justamente o tipo de
    # informacao que nao pode ser confirmada a um estranho.
    if not patient or not _verify_patient_password(patient, password):
        raise HTTPException(
            status_code=401, detail="CPF/e-mail ou senha inválido"
        )
    PATIENT_LOGIN_ATTEMPTS.pop(attempt_key, None)
    patient["last_auth_at"] = _utc_now_iso()
    patient["last_auth_provider"] = "password"
    _save_identity_state()
    return _issue_patient_portal_session(patient, "password")


@app.post("/api/patient-auth/google")
async def patient_portal_google_login(
    payload: PatientGoogleLoginRequest, request: Request
):
    google_identity = await _verify_google_credential(payload.credential)
    patient = _find_registered_patient_by_email(
        google_identity.get("email") or ""
    )
    if not patient:
        raise HTTPException(
            status_code=403,
            detail=(
                "Esta conta Google não corresponde ao e-mail de um paciente "
                "já cadastrado no FROID"
            ),
        )
    google_sub = str(google_identity.get("google_sub") or "").strip()
    bound_google_sub = str(patient.get("google_sub") or "").strip()
    if not google_sub or (bound_google_sub and bound_google_sub != google_sub):
        raise HTTPException(
            status_code=403,
            detail="Conta Google diferente da vinculada a este paciente",
        )
    patient["google_sub"] = google_sub
    patient["google_linked_at"] = patient.get("google_linked_at") or _utc_now_iso()
    patient["last_auth_at"] = _utc_now_iso()
    patient["last_auth_provider"] = "google"
    patient["updated_at"] = _utc_now_iso()
    _save_identity_state()
    LOGGER.info(
        json.dumps(
            {
                "event": "froid.patient_google_auth",
                "outcome": "success",
                "patient_id": str(patient.get("id") or ""),
                "remote_addr": request.client.host if request.client else "",
            },
            ensure_ascii=False,
        )
    )
    return _issue_patient_portal_session(patient, "google")


@app.get("/api/patient-auth/me")
async def patient_portal_me(request: Request):
    patient_session = _require_current_patient(request)
    return {"patient": _patient_public_identity(patient_session)}


@app.post("/api/patient-auth/logout")
async def patient_portal_logout(request: Request):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    if token:
        PATIENT_PORTAL_SESSIONS.pop(token, None)
    return {"status": "ok"}


@app.put("/api/patient-portal/password")
async def patient_portal_update_password(
    payload: PatientPasswordUpdate, request: Request
):
    patient_session = _require_current_patient(request)
    patient_id = str(patient_session.get("id") or "")
    patient = PATIENTS.get(patient_id)
    if not isinstance(patient, dict):
        raise HTTPException(status_code=404, detail="Paciente não localizado")
    if payload.new_password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Confirmação da nova senha não confere")
    authenticated_with_google = (
        str(patient_session.get("_auth_provider") or "") == "google"
    )
    if not authenticated_with_google and not _verify_patient_password(
        patient, payload.current_password
    ):
        raise HTTPException(status_code=401, detail="Senha atual inválida")
    _set_patient_password(patient, payload.new_password)
    patient["updated_at"] = _utc_now_iso()
    patient["password_updated_via"] = (
        "google_recovery" if authenticated_with_google else "authenticated_change"
    )
    for session_token, active_session in list(PATIENT_PORTAL_SESSIONS.items()):
        if (
            active_session is not patient_session
            and str(active_session.get("id") or "") == patient_id
        ):
            PATIENT_PORTAL_SESSIONS.pop(session_token, None)
    patient_session.update(_patient_public_identity(patient))
    _save_identity_state()
    LOGGER.info(
        json.dumps(
            {
                "event": "froid.patient_password_updated",
                "patient_id": patient_id,
                "method": patient["password_updated_via"],
                "remote_addr": request.client.host if request.client else "",
            },
            ensure_ascii=False,
        )
    )
    return {"status": "ok"}


@app.get("/api/patient-portal/reports")
async def patient_portal_reports(request: Request):
    patient_session = _require_current_patient(request)
    reports = _reports_for_patient_session(patient_session)
    # A lista vazia tem duas causas muito diferentes — ainda não há sessão, ou o
    # profissional não habilitou o acesso — e sem este campo a área diria
    # "nenhum resultado localizado" nos dois casos. Para quem teve sessão e não
    # vê nada, essa frase é simplesmente falsa.
    patient_id = str(patient_session.get("id") or "")
    results_enabled = _patient_results_enabled(PATIENTS.get(patient_id) if patient_id else None)
    return {
        "patient": _patient_public_identity(patient_session),
        "reports": reports,
        "total": len(reports),
        "resultsEnabled": results_enabled,
    }


@app.put("/api/patient-portal/profile")
async def patient_portal_update_profile(payload: PatientPortalProfileUpdate, request: Request):
    patient_session = _require_current_patient(request)
    patient_id = str(patient_session.get("id") or "")
    patient = PATIENTS.get(patient_id) if patient_id else None
    if not isinstance(patient, dict):
        patient = None
        for candidate_id, candidate in PATIENTS.items():
            if _patient_identity_matches(
                candidate,
                _normalize_email(patient_session.get("email") or ""),
                _digits_only(patient_session.get("document") or ""),
                _digits_only(patient_session.get("phone") or ""),
            ):
                patient_id = str(candidate_id)
                patient = candidate
                break
    if not isinstance(patient, dict):
        raise HTTPException(status_code=404, detail="Cadastro do paciente não encontrado para atualização")

    now = _utc_now_iso()
    requested_document = _digits_only(payload.document or patient.get("document") or "")
    existing_document_owner = PATIENTS_BY_CONTACT.get(f"document:{requested_document}")
    if requested_document and existing_document_owner and str(existing_document_owner) != patient_id:
        raise HTTPException(status_code=409, detail="documento já vinculado a outro cadastro")
    patient.update(
        {
            "name": str(payload.name or patient.get("name") or "").strip(),
            "phone": _digits_only(payload.phone or patient.get("phone") or ""),
            "document": requested_document,
            "birth_date": str(payload.birth_date or patient.get("birth_date") or "").strip(),
            "updated_at": now,
        }
    )
    PATIENTS[patient_id] = patient
    rebuilt = _rebuild_patient_contact_index(PATIENTS, PATIENTS_BY_CONTACT)
    PATIENTS_BY_CONTACT.clear()
    PATIENTS_BY_CONTACT.update(rebuilt)
    patient_session.update(_patient_public_identity(patient))
    _save_identity_state()
    return {"patient": _patient_public_identity(patient)}


@app.get("/api/patient-portal/consent")
async def patient_portal_consent(request: Request):
    patient_session = _require_current_patient(request)
    patient_id = str(patient_session.get("id") or "")
    patient = PATIENTS.get(patient_id)
    if not isinstance(patient, dict):
        raise HTTPException(status_code=404, detail="Cadastro do paciente não encontrado")
    preferences = _patient_consent_preferences(patient)
    legal_acceptance_required = _legal_acceptance_required(
        patient.get("legal_jurisdiction") or "BR"
    )
    return {
        "consent": preferences,
        "version": patient.get("lgpd_consent_version") or LEGAL_DOCUMENT_VERSION,
        "updated_at": patient.get("consent_updated_at") or patient.get("lgpd_consent_at"),
        "session_authorization_active": (
            (
                not legal_acceptance_required
                or patient.get("lgpd_consent_version") == LEGAL_DOCUMENT_VERSION
            )
            and all(
                preferences.get(key) is True
                for key in (
                    *(("patient_tcle",) if legal_acceptance_required else ()),
                    "terms_of_use",
                    "privacy_policy",
                    "sensitive_data_processing",
                    "audio_video_processing",
                )
            )
        ),
    }


@app.put("/api/patient-portal/consent")
async def patient_portal_update_consent(
    payload: PatientConsentPreferences, request: Request
):
    patient_session = _require_current_patient(request)
    patient_id = str(patient_session.get("id") or "")
    patient = PATIENTS.get(patient_id)
    if not isinstance(patient, dict):
        raise HTTPException(status_code=404, detail="Cadastro do paciente não encontrado")
    now = _utc_now_iso()
    preferences = payload.model_dump()
    patient["consent_preferences"] = preferences
    patient["consent_updated_at"] = now
    patient["lgpd_consent_version"] = LEGAL_DOCUMENT_VERSION
    ledger_payload = {
        "patient_id": patient_id,
        "invite_id": "",
        "session_id": "",
        "consent": preferences,
        "version": LEGAL_DOCUMENT_VERSION,
        "accepted_at": now,
        "source": "patient_portal_update",
        "remote_addr": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", ""),
    }
    CONSENT_LEDGER.append(
        {**ledger_payload, "hash": _consent_hash(ledger_payload)}
    )
    if preferences.get("patient_tcle") is True:
        legal_catalog = public_legal_catalog()["documents"]
        _record_legal_documents(
            request=request,
            subject_reference=patient_id,
            subject_kind="patient",
            organization_id="",
            acceptances={
                key: {
                    "version": legal_catalog[key]["version"],
                    "sha256": legal_catalog[key]["sha256"],
                    "accepted_at": now,
                }
                for key in ("patient_tcle", "terms", "privacy")
            },
            context="patient_portal_consent_update",
        )
    _save_identity_state()
    return await patient_portal_consent(request)


@app.get("/api/patient-portal/privacy")
async def patient_portal_privacy_overview(request: Request):
    patient_session = _require_current_patient(request)
    patient_id = str(patient_session.get("id") or "")
    identity_document = _digits_only(patient_session.get("document") or "")
    if not TENANT_STORE.enabled:
        raise HTTPException(
            status_code=503,
            detail="portal de direitos requer persistência protegida disponível",
        )
    scopes = TENANT_STORE.patient_privacy_scopes(patient_id, identity_document)
    requests = [
        _reveal_data_subject_request(item)
        for item in TENANT_STORE.list_patient_data_subject_requests(
            patient_id, identity_document
        )
    ]
    return {
        "patient": _patient_public_identity(patient_session),
        "organizations": scopes,
        "requests": requests,
        "rights": sorted(DATA_SUBJECT_REQUEST_TYPES),
        "processing": {
            "categories": [
                "cadastro e autenticação",
                "áudio e transcrição clínica, quando aplicável",
                "métricas vocais e multimodais",
                "relatórios, cortes semânticos e resumos",
                "segurança, auditoria e prevenção de fraude",
                "faturamento e gestão de sessões",
                "Data-FROID após anonimização",
            ],
            "automated_decision": False,
            "clinical_decision_owner": "profissional habilitado",
            "datamart_rule": "somente dados aprovados pelo gate de anonimização",
        },
    }


@app.post("/api/patient-portal/privacy/requests", status_code=201)
async def patient_portal_create_privacy_request(
    payload: DataSubjectRequestCreate, request: Request
):
    patient_session = _require_current_patient(request)
    request_type = str(payload.request_type or "").strip().lower()
    if request_type not in DATA_SUBJECT_REQUEST_TYPES:
        raise HTTPException(status_code=400, detail="direito solicitado não reconhecido")
    if not TENANT_STORE.enabled:
        raise HTTPException(
            status_code=503,
            detail="portal de direitos requer persistência protegida disponível",
        )
    patient_id = str(patient_session.get("id") or "")
    identity_document = _digits_only(patient_session.get("document") or "")
    try:
        created = TENANT_STORE.create_data_subject_requests(
            legacy_patient_id=patient_id,
            identity_document=identity_document,
            request_type=request_type,
            request_payload=_protect_data_subject_details(payload.details),
            organization_id=str(payload.organization_id or "").strip(),
        )
    except ValueError as exc:
        status_code = 409 if "transition" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {
        "status": "submitted",
        "requests": [_reveal_data_subject_request(item) for item in created],
        "total": len(created),
    }


@app.get("/api/patient-portal/privacy/export")
async def patient_portal_privacy_export(request: Request):
    patient_session = _require_current_patient(request)
    patient_id = str(patient_session.get("id") or "")
    identity_document = _digits_only(patient_session.get("document") or "")
    # Exportação de titular: caminho próprio, sem os portões da área do paciente.
    reports = _reports_for_patient_privacy_export(patient_session)
    consents = [
        {
            "version": item.get("version"),
            "accepted_at": item.get("accepted_at"),
            "consent": item.get("consent") or {},
            "hash": item.get("hash"),
        }
        for item in CONSENT_LEDGER
        if str(item.get("patient_id") or "") == patient_id
    ]
    requests = (
        [
            _reveal_data_subject_request(item)
            for item in TENANT_STORE.list_patient_data_subject_requests(
                patient_id, identity_document
            )
        ]
        if TENANT_STORE.enabled
        else []
    )
    return {
        "export_version": "FROID-LGPD-export-v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "patient": _patient_public_identity(patient_session),
        "organizations": (
            TENANT_STORE.patient_privacy_scopes(patient_id, identity_document)
            if TENANT_STORE.enabled else []
        ),
        "consents": consents,
        "available_session_records": [
            _privacy_export_report(report) for report in reports
        ],
        "privacy_requests": requests,
        "limitations": [
            "Transcrições integrais e registros que possam conter dados de terceiros são fornecidos após revisão do pedido de acesso ou portabilidade.",
            "Registros cuja conservação seja obrigatória podem ser bloqueados em vez de eliminados.",
        ],
    }


@app.get("/api/organizations/{organization_id}/privacy-requests")
async def organization_privacy_requests(
    organization_id: str, request: Request, limit: int = 200
):
    context = _require_tenant_management_context(
        request, organization_id, "privacy.read"
    )
    items = TENANT_STORE.list_organization_data_subject_requests(
        organization_id=organization_id,
        membership_id=context.membership_id,
        limit=limit,
    )
    _record_tenant_success(
        context, "privacy.request.list", "data_subject_request"
    )
    return {
        "requests": [_reveal_data_subject_request(item) for item in items],
        "total": len(items),
    }


@app.patch("/api/organizations/{organization_id}/privacy-requests/{request_id}")
async def organization_update_privacy_request(
    organization_id: str,
    request_id: str,
    payload: DataSubjectRequestUpdate,
    request: Request,
):
    context = _require_tenant_management_context(
        request, organization_id, "privacy.manage"
    )
    status = str(payload.status or "").strip().lower()
    if status not in DATA_SUBJECT_REQUEST_STATUSES:
        raise HTTPException(status_code=400, detail="status de solicitação inválido")
    if status in {"completed", "denied", "partially_approved"} and not payload.response_summary.strip():
        raise HTTPException(
            status_code=400,
            detail="conclusão ou decisão restritiva exige resposta ao titular",
        )
    if status in {"denied", "partially_approved"} and not (
        payload.legal_basis.strip() or payload.retention_exception.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="decisão restritiva exige fundamento ou exceção de retenção",
        )
    try:
        updated = TENANT_STORE.update_data_subject_request(
            organization_id=organization_id,
            membership_id=context.membership_id,
            actor_user_id=context.user_id,
            request_id=request_id,
            status=status,
            response_summary=_protect_data_subject_response(payload.response_summary),
            legal_basis=str(payload.legal_basis or "").strip(),
            retention_exception=str(payload.retention_exception or "").strip(),
        )
    except ValueError as exc:
        status_code = 409 if "transition" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    _record_tenant_success(
        context,
        "privacy.request.update",
        "data_subject_request",
        request_id,
        {"status": status},
    )
    return {"request": _reveal_data_subject_request(updated)}


@app.get("/api/session-events/latest")
async def get_latest_session_event(request: Request):
    user = _require_current_user(request)
    context = _require_professional_feature_access(request)
    owner_email = _normalize_email(user.get("email") or "")
    visible = [
        event for event in SESSION_EVENTS
        if _normalize_email(event.get("professional_email") or "") == owner_email
        and _invite_organization_id(event) == (context.organization_id if context else "")
    ]
    latest_id = visible[-1]["id"] if visible else 0
    return {"latest_id": latest_id}


@app.get("/api/session-events")
async def get_session_events(request: Request, after: int = 0):
    user = _require_current_user(request)
    context = _require_professional_feature_access(request)
    owner_email = _normalize_email(user.get("email") or "")
    events = [
        event for event in SESSION_EVENTS
        if int(event.get("id") or 0) > after
        and _normalize_email(event.get("professional_email") or "") == owner_email
        and _invite_organization_id(event) == (context.organization_id if context else "")
    ]
    return {
        "latest_id": events[-1]["id"] if events else after,
        "events": events[-50:],
    }


@app.get("/api/session-waiting")
async def get_waiting_patient_sessions(request: Request):
    user = _require_current_user(request)
    context = _require_professional_feature_access(request)
    owner_email = _normalize_email(user.get("email") or "")
    organization_id = context.organization_id if context else ""
    completed_session_ids = set(_load_session_reports(reveal_transcripts=False))
    waiting = []

    for invite in SESSION_INVITES.values():
        session_id = str(invite.get("session_id") or "").strip()
        if (
            not session_id
            or session_id in completed_session_ids
            or invite.get("status") != "accepted"
            or _normalize_email(invite.get("professional_email") or "") != owner_email
            or _invite_organization_id(invite) != organization_id
            or not rtc_signals.role_connected(session_id, "patient")
        ):
            continue

        entries = PATIENT_SESSION_ENTRIES.get(session_id) or []
        latest_entry = entries[-1] if entries else {}
        waiting.append(
            {
                "session_id": session_id,
                "patient_id": invite.get("patient_id"),
                "patient_name": invite.get("patient_name") or "Paciente",
                "patient_email": invite.get("patient_email") or "",
                "patient_phone": invite.get("patient_phone") or "",
                "session_mode": invite.get("session_mode") or "remote",
                "joined_at": latest_entry.get("joined_at")
                or invite.get("accepted_at")
                or invite.get("created_at"),
                "patient_connected": True,
            }
        )

    waiting.sort(key=lambda item: str(item.get("joined_at") or ""), reverse=True)
    return {"waiting": waiting}

@app.get("/api/auth/config")
def auth_config():
    return {
        "google_client_id": GOOGLE_AUTH_CLIENT_ID,
        "google_auth_configured": bool(GOOGLE_AUTH_CLIENT_ID),
        "dev_fallback_enabled": GOOGLE_AUTH_DEV_FALLBACK,
        "local_login_enabled": bool(
            (FROID_LOCAL_AUTH_PASSWORD and FROID_LOCAL_AUTH_EMAILS)
            or GOOGLE_AUTH_DEV_FALLBACK
        ),
        # A tela de login precisa saber se pode oferecer "criar conta". Sem
        # entrega de e-mail configurada o cadastro não se completa, então o
        # botão não deve aparecer prometendo o que o servidor não cumpre.
        "registration_enabled": bool(
            FROID_REGISTRATION_ENABLED
            and (froid_mailer.mailer_enabled() or froid_mailer.dev_echo_enabled())
        ),
        "password_login_enabled": True,
        "password_min_length": FROID_PASSWORD_MIN_LENGTH,
        "email_delivery_configured": froid_mailer.mailer_enabled(),
    }

@app.post("/api/auth/google")
async def auth_google(request: Request):
    # Mitigação de força bruta/credential stuffing na autenticação profissional.
    _rate_limit_guard(
        "auth_pro", _client_ip(request), 15, 900.0,
        "Muitas tentativas de login. Aguarde alguns minutos e tente novamente.",
    )
    body = await request.json()
    credential = body.get("credential") or body.get("id_token") or body.get("token")
    if credential:
        user = await _verify_google_credential(credential)
        return _issue_session(user)

    return _issue_session(_verify_local_login(body))

@app.post("/api/auth/google-dev")
async def auth_google_dev(request: Request):
    if not GOOGLE_AUTH_DEV_FALLBACK:
        raise HTTPException(status_code=404, detail="rota de desenvolvimento desabilitada")
    body = await request.json()
    return _issue_session(_verify_local_login(body))

def _valid_email_shape(email: str) -> bool:
    """Checagem de forma, não de existência. Quem prova o endereço é o e-mail
    de verificação — validar demais aqui só rejeitaria endereço legítimo."""
    valor = _normalize_email(email)
    if not valor or len(valor) > 320 or valor.count("@") != 1:
        return False
    local, _, dominio = valor.partition("@")
    if not local or not dominio or "." not in dominio:
        return False
    return " " not in valor and ".." not in valor


async def _send_verification_email(credential: dict) -> str:
    """Envia o convite de verificação. Devolve o link apenas no modo de
    desenvolvimento sem SMTP; em produção devolve string vazia."""
    token = _issue_credential_token(
        credential, "verification", FROID_EMAIL_VERIFICATION_TTL_SECONDS
    )
    link = _public_app_link("/verificar-email?token=" + quote(token, safe=""))
    horas = max(1, FROID_EMAIL_VERIFICATION_TTL_SECONDS // 3600)
    assunto = "Confirme seu e-mail no FROID"
    texto, html = _credential_email_bodies(
        assunto,
        (
            "Você criou um acesso profissional no FROID. Confirme este endereço "
            "para continuar o cadastro e escolher o produto."
        ),
        link,
        "{} hora(s)".format(horas),
    )
    if froid_mailer.dev_echo_enabled():
        LOGGER.warning("FROID_SMTP_DEV_ECHO ativo: link de verificação não enviado")
        return link
    await _deliver_credential_email(
        str(credential.get("email") or ""), assunto, texto, html
    )
    return ""


async def _send_password_reset_email(credential: dict) -> str:
    token = _issue_credential_token(
        credential, "reset", FROID_PASSWORD_RESET_TTL_SECONDS
    )
    link = _public_app_link("/recuperar-senha?token=" + quote(token, safe=""))
    minutos = max(5, FROID_PASSWORD_RESET_TTL_SECONDS // 60)
    assunto = "Definir nova senha no FROID"
    texto, html = _credential_email_bodies(
        assunto,
        "Recebemos um pedido para redefinir a senha do seu acesso profissional.",
        link,
        "{} minuto(s)".format(minutos),
    )
    if froid_mailer.dev_echo_enabled():
        LOGGER.warning("FROID_SMTP_DEV_ECHO ativo: link de recuperação não enviado")
        return link
    await _deliver_credential_email(
        str(credential.get("email") or ""), assunto, texto, html
    )
    return ""


@app.post("/api/auth/register")
async def auth_register(request: Request):
    """Cadastro de profissional ou empresa sem conta Google.

    A resposta é sempre a mesma, exista ou não a conta. Um cadastro que
    respondesse "e-mail já usado" viraria consulta pública de quem atende pelo
    FROID — e a clientela de um psicólogo não é informação de domínio público.
    Quem já tem conta verificada recebe, no lugar do convite, o caminho de
    recuperação de senha.
    """
    if not FROID_REGISTRATION_ENABLED:
        raise HTTPException(status_code=404, detail="cadastro próprio desabilitado")
    _rate_limit_guard(
        "auth_register", _client_ip(request), 10, 3600.0,
        "Muitas tentativas de cadastro. Tente novamente em uma hora.",
    )
    body = await request.json()
    email = _normalize_email(body.get("email") or "")
    if not _valid_email_shape(email):
        raise HTTPException(status_code=400, detail="Informe um e-mail válido")
    password = str(body.get("password") or "")
    confirm = str(body.get("password_confirm") or password)
    if password != confirm:
        raise HTTPException(status_code=400, detail="A confirmação da senha não confere")
    queixa = _password_policy_error(password)
    if queixa:
        raise HTTPException(status_code=400, detail=queixa)
    nome = str(body.get("name") or "").strip()[:300] or email.split("@", 1)[0]

    _rate_limit_guard(
        "auth_register_email", email, 5, 3600.0,
        "Muitas tentativas de cadastro para este e-mail. Tente novamente em uma hora.",
    )

    agora = _utc_now_iso()
    existente = PROFESSIONAL_CREDENTIALS.get(email)
    resposta = {"status": "verification_sent"}

    if isinstance(existente, dict) and existente.get("email_verified"):
        # Conta existe e o endereço já foi provado. Trocar a senha aqui seria
        # sequestro de conta por formulário público: o caminho legítimo é a
        # recuperação, que também passa pela caixa de entrada.
        link = await _send_password_reset_email(existente)
        _save_identity_state()
        LOGGER.info(
            json.dumps(
                {
                    "event": "froid.professional_register",
                    "outcome": "already_registered",
                    "remote_addr": _client_ip(request),
                },
                ensure_ascii=False,
            )
        )
        if link:
            resposta["dev_link"] = link
        return resposta

    credencial = existente if isinstance(existente, dict) else {
        "email": email,
        "created_at": agora,
        "email_verified": False,
    }
    credencial["email"] = email
    credencial["name"] = nome
    credencial["provider"] = "password"
    credencial["updated_at"] = agora
    _set_professional_password(credencial, password)
    PROFESSIONAL_CREDENTIALS[email] = credencial
    link = await _send_verification_email(credencial)
    _save_identity_state()
    LOGGER.info(
        json.dumps(
            {
                "event": "froid.professional_register",
                "outcome": "verification_sent",
                "remote_addr": _client_ip(request),
            },
            ensure_ascii=False,
        )
    )
    if link:
        resposta["dev_link"] = link
    return resposta


@app.post("/api/auth/resend-verification")
async def auth_resend_verification(request: Request):
    """Reenvia a verificação. Resposta uniforme, pelo mesmo motivo do cadastro."""
    _rate_limit_guard(
        "auth_resend", _client_ip(request), 10, 3600.0,
        "Muitos reenvios. Tente novamente em uma hora.",
    )
    body = await request.json()
    email = _normalize_email(body.get("email") or "")
    resposta = {"status": "verification_sent"}
    if not _valid_email_shape(email):
        return resposta
    _rate_limit_guard(
        "auth_resend_email", email, 5, 3600.0,
        "Muitos reenvios para este e-mail. Tente novamente em uma hora.",
    )
    credencial = PROFESSIONAL_CREDENTIALS.get(email)
    if not isinstance(credencial, dict) or credencial.get("email_verified"):
        return resposta
    link = await _send_verification_email(credencial)
    _save_identity_state()
    if link:
        resposta["dev_link"] = link
    return resposta


@app.post("/api/auth/verify-email")
async def auth_verify_email(request: Request):
    """Queima o token e já devolve a sessão.

    Abrir o link prova o controle da caixa de entrada, que é exatamente o que o
    Google provava antes. Pedir a senha de novo aqui não acrescentaria
    segurança nenhuma e só perderia gente no meio do caminho.
    """
    _rate_limit_guard(
        "auth_verify", _client_ip(request), 30, 900.0,
        "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
    )
    body = await request.json()
    token = str(body.get("token") or "").strip()
    credencial = _consume_credential_token("verification", token)
    if not isinstance(credencial, dict):
        _save_identity_state()
        raise HTTPException(
            status_code=400,
            detail="Link de verificação inválido ou expirado. Peça um novo e-mail.",
        )
    credencial["email_verified"] = True
    credencial["email_verified_at"] = _utc_now_iso()
    credencial["updated_at"] = _utc_now_iso()
    _save_identity_state()
    LOGGER.info(
        json.dumps(
            {
                "event": "froid.professional_email_verified",
                "remote_addr": _client_ip(request),
            },
            ensure_ascii=False,
        )
    )
    return _issue_session(
        {
            "email": str(credencial.get("email") or ""),
            "name": str(credencial.get("name") or ""),
            "provider": "password",
        }
    )


@app.post("/api/auth/login")
async def auth_password_login(request: Request):
    """Login por senha de quem se cadastrou sem Google."""
    _rate_limit_guard(
        "auth_pro", _client_ip(request), 15, 900.0,
        "Muitas tentativas de login. Aguarde alguns minutos e tente novamente.",
    )
    body = await request.json()
    email = _normalize_email(body.get("email") or "")
    password = str(body.get("password") or "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Informe e-mail e senha")
    _rate_limit_guard(
        "auth_pro_email", email, 10, 900.0,
        "Muitas tentativas para este e-mail. Aguarde alguns minutos.",
    )
    credencial = PROFESSIONAL_CREDENTIALS.get(email)
    if not isinstance(credencial, dict) or not _verify_professional_password(
        credencial, password
    ):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if not credencial.get("email_verified"):
        # Só chega aqui quem já acertou a senha, então não há vazamento: é a
        # dona da conta e precisa saber por que não entra.
        raise HTTPException(
            status_code=403,
            detail=(
                "Confirme seu e-mail antes de entrar. "
                "Verifique a caixa de entrada ou peça um novo link."
            ),
        )
    credencial["last_auth_at"] = _utc_now_iso()
    _save_identity_state()
    return _issue_session(
        {
            "email": email,
            "name": str(credencial.get("name") or ""),
            "provider": "password",
        }
    )


@app.post("/api/auth/password-reset")
async def auth_password_reset_request(request: Request):
    """Pede o link de nova senha. Resposta uniforme."""
    _rate_limit_guard(
        "auth_reset", _client_ip(request), 10, 3600.0,
        "Muitos pedidos de recuperação. Tente novamente em uma hora.",
    )
    body = await request.json()
    email = _normalize_email(body.get("email") or "")
    resposta = {"status": "reset_sent"}
    if not _valid_email_shape(email):
        return resposta
    _rate_limit_guard(
        "auth_reset_email", email, 5, 3600.0,
        "Muitos pedidos para este e-mail. Tente novamente em uma hora.",
    )
    credencial = PROFESSIONAL_CREDENTIALS.get(email)
    if not isinstance(credencial, dict):
        return resposta
    link = await _send_password_reset_email(credencial)
    _save_identity_state()
    if link:
        resposta["dev_link"] = link
    return resposta


@app.post("/api/auth/password-reset/confirm")
async def auth_password_reset_confirm(request: Request):
    """Consome o token e grava a nova senha.

    Derruba todas as sessões vivas daquele e-mail: se a recuperação foi pedida
    porque alguém entrou na conta, deixar a sessão do invasor de pé anularia o
    efeito de trocar a senha.
    """
    _rate_limit_guard(
        "auth_reset_confirm", _client_ip(request), 30, 900.0,
        "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
    )
    body = await request.json()
    token = str(body.get("token") or "").strip()
    password = str(body.get("password") or "")
    confirm = str(body.get("password_confirm") or password)
    if password != confirm:
        raise HTTPException(status_code=400, detail="A confirmação da senha não confere")
    queixa = _password_policy_error(password)
    if queixa:
        raise HTTPException(status_code=400, detail=queixa)
    credencial = _consume_credential_token("reset", token)
    if not isinstance(credencial, dict):
        _save_identity_state()
        raise HTTPException(
            status_code=400,
            detail="Link de recuperação inválido ou expirado. Peça um novo e-mail.",
        )
    email = _normalize_email(credencial.get("email") or "")
    _set_professional_password(credencial, password)
    # Abrir o link de recuperação prova a caixa de entrada tanto quanto o de
    # verificação: quem redefiniu a senha por e-mail está verificado.
    credencial["email_verified"] = True
    credencial["email_verified_at"] = (
        credencial.get("email_verified_at") or _utc_now_iso()
    )
    credencial["updated_at"] = _utc_now_iso()
    _revoke_professional_sessions(email)
    _save_identity_state()
    LOGGER.info(
        json.dumps(
            {
                "event": "froid.professional_password_reset",
                "remote_addr": _client_ip(request),
            },
            ensure_ascii=False,
        )
    )
    return _issue_session(
        {
            "email": email,
            "name": str(credencial.get("name") or ""),
            "provider": "password",
        }
    )


@app.get("/api/auth/me")
async def auth_me(request: Request):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    user = _session_user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    user = dict(user)
    user = _attach_tenant_contexts(user)
    # A guarda vive aqui e no login, e nao em cada rota: esta e a chamada que o
    # front faz a cada carregamento de pagina, entao a revogacao aparece como
    # mensagem no proximo carregamento em vez de virar tela vazia. O dado em si
    # ja esta protegido antes disto — `_tenant_context_from_request` reconsulta
    # o Postgres a cada requisicao e os chamadores recusam sem contexto.
    _guard_acesso_revogado(user)
    user["access_status"] = _effective_professional_access_status(user)
    SESSION_USERS[token] = user
    return {key: value for key, value in user.items() if not key.startswith("_")}


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    if token:
        SESSION_USERS.pop(token, None)
    return {"status": "ok"}


@app.post("/api/auth/active-organization")
async def set_active_organization(request: Request):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    user = _session_user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    body = await request.json()
    organization_id = str(body.get("organization_id") or "").strip()
    enriched = _attach_tenant_contexts(user)
    if not any(
        str(item.get("organization_id") or "") == organization_id
        for item in enriched.get("organizations") or []
        if isinstance(item, dict)
    ):
        raise HTTPException(status_code=403, detail="organização não pertence ao usuário")
    _guard_acesso_revogado(enriched)
    enriched["active_organization_id"] = organization_id
    SESSION_USERS[token] = enriched
    return {"status": "ok", "active_organization_id": organization_id}


@app.get("/api/organizations")
async def list_current_user_organizations(request: Request):
    user = _require_current_user(request)
    enriched = _attach_tenant_contexts(user)
    user.update(enriched)
    return {
        "organizations": enriched.get("organizations") or [],
        "active_organization_id": enriched.get("active_organization_id") or "",
        "authorization_mode": FROID_TENANT_AUTHORIZATION_MODE,
    }


@app.get("/api/organizations/{organization_id}/members")
async def list_organization_members(organization_id: str, request: Request):
    context = _require_tenant_management_context(request, organization_id, "members.manage")
    members = TENANT_STORE.list_members(organization_id)
    _record_tenant_success(
        context, "member.list", "organization_membership",
        metadata={"result_count": len(members)},
    )
    return {"members": members}


@app.post("/api/organizations/{organization_id}/members/invitations")
async def invite_organization_member(organization_id: str, request: Request):
    context = _require_tenant_management_context(
        request, organization_id, "members.manage"
    )
    body = await request.json()
    invited_email = _normalize_email(body.get("email") or "")
    roles = {
        str(role).strip().lower()
        for role in (body.get("roles") if isinstance(body.get("roles"), list) else ["professional"])
        if str(role).strip()
    }
    if not invited_email:
        raise HTTPException(status_code=400, detail="email do profissional obrigatório")
    if not roles or roles - TENANT_ROLES:
        raise HTTPException(status_code=400, detail="papéis organizacionais inválidos")
    if "owner" in roles and "owner" not in context.roles:
        raise HTTPException(status_code=403, detail="somente proprietário pode convidar outro proprietário")
    expires_hours = min(168, max(1, _local_int(body.get("expires_hours") or 72)))
    invitation_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(invitation_token.encode("utf-8")).hexdigest()
    invitation_id = TENANT_STORE.create_member_invitation(
        organization_id=organization_id,
        invited_by_membership_id=context.membership_id,
        invited_email=invited_email,
        token_hash=token_hash,
        roles=roles,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    )
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=context.user_id,
        action="member.invite",
        resource_type="membership_invitation",
        resource_id=invitation_id,
        metadata={"roles": sorted(roles), "expires_hours": expires_hours},
    )
    return {
        "invitation_id": invitation_id,
        "invitation_token": invitation_token,
        "expires_in_hours": expires_hours,
        "note": "o token é exibido uma única vez e deve ser enviado ao destinatário por canal seguro",
    }


@app.post("/api/organization-invitations/accept")
async def accept_organization_invitation(request: Request):
    user = _require_current_user(request)
    if not TENANT_STORE.enabled:
        raise HTTPException(status_code=409, detail="persistência dual obrigatória")
    body = await request.json()
    invitation_token = str(body.get("invitation_token") or "").strip()
    if not invitation_token:
        raise HTTPException(status_code=400, detail="token de convite obrigatório")
    token_hash = hashlib.sha256(invitation_token.encode("utf-8")).hexdigest()
    try:
        context = TENANT_STORE.accept_member_invitation(
            token_hash=token_hash,
            email=user.get("email") or "",
            display_name=user.get("name") or "",
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="convite destinado a outro email")
    except ValueError as exc:
        if str(exc) == "organization_member_limit_reached":
            raise HTTPException(status_code=409, detail="limite de profissionais do plano atingido")
        if str(exc) == "organization_subscription_inactive":
            raise HTTPException(status_code=402, detail="plano FROID inativo")
        raise HTTPException(status_code=404, detail="convite inválido ou expirado")
    TENANT_STORE.record_access_audit(
        organization_id=context["organization_id"],
        actor_user_id=context["user_id"],
        action="member.join",
        resource_type="organization_membership",
        resource_id=context["membership_id"],
    )
    refreshed = _attach_tenant_contexts(user)
    user.update(refreshed)
    return {"status": "accepted", "membership": context}


@app.delete("/api/organizations/{organization_id}/members/{membership_id}")
async def revoke_organization_member(
    organization_id: str, membership_id: str, request: Request
):
    context = _require_tenant_management_context(
        request, organization_id, "members.manage"
    )
    if membership_id == context.membership_id:
        raise HTTPException(
            status_code=409,
            detail="use o fluxo de transferência de propriedade para remover a própria conta",
        )
    try:
        TENANT_STORE.revoke_membership(
            organization_id=organization_id,
            membership_id=membership_id,
            allow_owner_revoke="owner" in context.roles,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="somente proprietário pode remover proprietário")
    except ValueError as exc:
        reason = str(exc)
        if reason == "cannot_revoke_last_owner":
            raise HTTPException(status_code=409, detail="não é permitido remover o último proprietário")
        raise HTTPException(status_code=404, detail="vínculo profissional não encontrado")
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=context.user_id,
        action="member.revoke",
        resource_type="organization_membership",
        resource_id=membership_id,
    )
    return {"status": "revoked", "membership_id": membership_id}


@app.get(
    "/api/organizations/{organization_id}/patients/{patient_id}/assignments"
)
async def list_patient_assignments(
    organization_id: str, patient_id: str, request: Request
):
    context = _require_tenant_management_context(
        request, organization_id, "assignments.manage"
    )
    assignments = TENANT_STORE.list_patient_assignments(
        organization_id=organization_id, patient_id=patient_id
    )
    _record_tenant_success(
        context, "patient.assignment.list", "patient", patient_id,
        {"result_count": len(assignments)},
    )
    return {"assignments": assignments}


@app.post(
    "/api/organizations/{organization_id}/patients/{patient_id}/assignments"
)
async def create_patient_assignment(
    organization_id: str, patient_id: str, request: Request
):
    context = _require_tenant_management_context(
        request, organization_id, "assignments.manage"
    )
    body = await request.json()
    membership_id = str(body.get("membership_id") or "").strip()
    assignment_type = str(body.get("assignment_type") or "care_team").strip()
    if assignment_type not in {"primary", "care_team", "supervisor", "read_only"}:
        raise HTTPException(status_code=400, detail="tipo de atribuição inválido")
    if assignment_type == "supervisor":
        subscription = TENANT_STORE.subscription_status(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
        if not subscription or not bool(
            (subscription.get("entitlements") or {}).get("supervision")
        ):
            raise HTTPException(status_code=403, detail="supervisão não incluída no plano")
    if not membership_id:
        raise HTTPException(status_code=400, detail="vínculo profissional obrigatório")
    try:
        assignment_id = TENANT_STORE.assign_patient(
            organization_id=organization_id,
            patient_id=patient_id,
            membership_id=membership_id,
            assignment_type=assignment_type,
        )
    except ValueError as exc:
        reason = str(exc)
        if reason == "patient_not_found":
            raise HTTPException(status_code=404, detail="paciente não encontrado na organização")
        if reason == "assignment_role_mismatch":
            raise HTTPException(
                status_code=409,
                detail="papel incompatível com a atribuição clínica",
            )
        if reason == "primary_assignment_exists":
            raise HTTPException(
                status_code=409,
                detail="paciente já possui profissional primário ativo",
            )
        raise HTTPException(status_code=404, detail="profissional ativo não encontrado na organização")
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=context.user_id,
        action="patient.assign",
        resource_type="patient_assignment",
        resource_id=assignment_id,
        metadata={
            "patient_id": patient_id,
            "membership_id": membership_id,
            "assignment_type": assignment_type,
        },
    )
    return {"status": "assigned", "assignment_id": assignment_id}


@app.delete(
    "/api/organizations/{organization_id}/patients/{patient_id}/assignments/{assignment_id}"
)
async def delete_patient_assignment(
    organization_id: str,
    patient_id: str,
    assignment_id: str,
    request: Request,
):
    context = _require_tenant_management_context(
        request, organization_id, "assignments.manage"
    )
    try:
        TENANT_STORE.revoke_patient_assignment(
            organization_id=organization_id,
            patient_id=patient_id,
            assignment_id=assignment_id,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="atribuição ativa não encontrada")
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=context.user_id,
        action="patient.unassign",
        resource_type="patient_assignment",
        resource_id=assignment_id,
        metadata={"patient_id": patient_id},
    )
    return {"status": "revoked", "assignment_id": assignment_id}


# ---------------------------------------------------------------------------
# NR-1 psychosocial compliance (Portaria MTE 1.419/2024)
#
# The employer-facing surface. None of these routes can reach an individual
# answer: the aggregate comes out of a k-clamped SQL function and the runtime
# database role holds no SELECT on the raw answer tables.
# ---------------------------------------------------------------------------
def _require_enterprise_context(
    request: Request, organization_id: str, permission: str
) -> AccessContext:
    context = _require_tenant_management_context(request, organization_id, permission)
    if not context.is_enterprise:
        raise HTTPException(
            status_code=409,
            detail="módulo NR-1 disponível apenas para organizações do tipo enterprise",
        )
    return context


def _nr1_representativeness(progress: dict) -> nr1_compliance.Representativeness:
    """O Portão A tal como o banco o aplicou, para poder explicá-lo.

    Os parâmetros vêm dos critérios vinculados à campanha. Quando ela não tem
    critérios, o progresso devolve nulo e vale o padrão da plataforma — a mesma
    resolução que froid_nr1_required_sample faz por coalesce, e é de propósito
    que os dois lados decidam igual: quem lê a tela e quem lê o SQL precisam
    chegar ao mesmo número.
    """
    overrides = {
        "margin_of_error": progress.get("sampling_margin_of_error"),
        "confidence_z": progress.get("sampling_confidence_z"),
        "census_threshold": progress.get("census_threshold_ratio"),
    }
    return nr1_compliance.representativeness(
        int(progress.get("target_headcount") or 0),
        int(progress.get("substantive_responses") or 0),
        **{name: float(value) for name, value in overrides.items() if value is not None},
    )


def _nr1_representativeness_payload(
    verdict: nr1_compliance.Representativeness,
) -> dict:
    """O veredito em forma serializável, para a tela dizer quanto falta."""
    return {
        "population": verdict.population,
        "achieved": verdict.achieved,
        "required": verdict.required,
        "mode": verdict.mode,
        "met": verdict.met,
        "confidence": round(verdict.confidence, 4),
        "margin_of_error": verdict.margin_of_error,
    }


def _nr1_criteria_for(context: AccessContext) -> nr1_compliance.GradationCriteria:
    """The organization's documented criteria, or the seeded default.

    Subitem 1.5.4.4.2.2 makes the gradations the organization's own, and the
    Manual requires the same ones across every risk type in the PGR — so a
    client already running a 3x3 matrix keeps it, and FROID grades on that.
    """
    try:
        document = TENANT_STORE.nr1_active_criteria(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
    except Exception:
        LOGGER.exception("Unable to read NR-1 criteria; falling back to default")
        return nr1_compliance.DEFAULT_CRITERIA
    if not document:
        return nr1_compliance.DEFAULT_CRITERIA
    try:
        return nr1_compliance.GradationCriteria.from_document(document)
    except ValueError:
        LOGGER.exception("Stored NR-1 criteria are invalid; falling back to default")
        return nr1_compliance.DEFAULT_CRITERIA


def _nr1_review_interval_months(context: AccessContext) -> int:
    """O teto de revisão que 1.5.4.4.6 impõe a esta organização.

    Dois anos, ou até três quando ela tem sistema de gestão de SST certificado
    (1.5.4.4.6.1) — o Manual do GRO cita a ISO 45001:2018 como exemplo. O banco
    já impede esticar sem a certificação, por CHECK em gro_risk_criteria; aqui
    só se lê o que ficou publicado.
    """
    try:
        document = TENANT_STORE.nr1_active_criteria(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
    except Exception:
        LOGGER.exception("Unable to read NR-1 review interval; falling back to 24")
        return 24
    if not document:
        return 24
    return max(1, min(36, int(document.get("review_interval_months") or 24)))


@app.post("/api/leads/nr1")
async def register_nr1_lead(request: Request):
    """Contato deixado no diagnóstico de prontidão do site.

    Endpoint público, sem autenticação — e por isso com três cuidados.

    Limite de taxa por IP, porque formulário aberto na internet é alvo de
    robô antes de ser alvo de cliente.

    Nada de dado sensível: aqui entram nome, e-mail corporativo, empresa,
    cargo e o resultado da calculadora. O contexto vale mais do que parece
    para o comercial — saber, antes de ligar, que aquele lead tem 40 pessoas
    e portanto o caminho dele é a AEP evita uma conversa que terminaria em
    frustração dos dois lados.

    E o e-mail é chave única: quem volta ao site e recalcula atualiza a
    própria visita em vez de virar duas pessoas na base.
    """
    _rate_limit_guard(
        "leads", _client_ip(request), 5, 3600.0,
        "Muitos envios deste endereço. Tente novamente mais tarde.",
    )
    body = await request.json()

    def _texto(chave: str, limite: int) -> str:
        return str(body.get(chave) or "").strip()[:limite]

    nome = _texto("nome", 120)
    email = _texto("email", 180)
    empresa = _texto("empresa", 180)
    if len(nome) < 2 or "@" not in email or not empresa:
        raise HTTPException(
            status_code=400, detail="nome, e-mail e empresa são obrigatórios"
        )
    if not TENANT_STORE.enabled:
        # Sem persistência dual não há onde gravar. Devolver 200 fingindo que
        # gravou perderia o lead em silêncio, que é pior que a falha visível.
        raise HTTPException(status_code=503, detail="cadastro indisponível no momento")
    try:
        TENANT_STORE.register_marketing_lead(
            nome=nome,
            email=email,
            empresa=empresa,
            cargo=_texto("cargo", 120),
            contexto=_texto("contexto", 300),
            origem=_texto("origem", 60) or "diagnostico-nr1",
        )
    except Exception:
        LOGGER.exception("Falha ao registrar lead do diagnóstico NR-1")
        raise HTTPException(status_code=503, detail="cadastro indisponível no momento")
    return {
        "status": "ok",
        "mensagem": "Recebemos seu contato. O material chega no seu e-mail.",
    }


# ----------------------------------------------------------------------
# Validade convergente.
#
# O profissional aplica o instrumento e registra o escore; nenhum endpoint
# aqui aplica ou pontua questionário. Essa ausência é o que mantém o FROID
# como instrumentação e fora da definição de instrumento de avaliação
# psicológica.
# ----------------------------------------------------------------------


@app.get("/api/organizations/{organization_id}/validation/consent/{patient_id}")
async def read_research_consent(organization_id: str, patient_id: str, request: Request):
    """Estado do consentimento de pesquisa deste paciente."""
    context = _require_tenant_management_context(
        request, organization_id, "patients.read_assigned"
    )
    return TENANT_STORE.validation_consent_state(
        organization_id=context.organization_id,
        membership_id=context.membership_id,
        patient_id=patient_id,
    )


@app.post("/api/organizations/{organization_id}/validation/consent/{patient_id}")
async def set_research_consent(organization_id: str, patient_id: str, request: Request):
    """Registra ou revoga a participação.

    Revogar não marca uma coluna: apaga os pares deste paciente da base do
    estudo, que é o que o TCLE promete.
    """
    context = _require_tenant_management_context(
        request, organization_id, "patients.manage"
    )
    body = await request.json()
    granted = bool(body.get("granted"))
    # Retirar sempre pode. Consentir, só depois do parecer do CEP: colher
    # aceite antes da aprovação é colher aceite para um estudo que ainda não
    # existe no formato aprovado.
    if granted and not froid_validation.collection_allowed():
        raise HTTPException(
            status_code=409,
            detail="coleta bloqueada: parecer do CEP ainda não registrado "
                   "(FROID_RESEARCH_CAAE)",
        )
    resultado = TENANT_STORE.validation_set_consent(
        organization_id=context.organization_id,
        membership_id=context.membership_id,
        patient_id=patient_id,
        registered_by=context.user_id,
        granted=granted,
        consent_version=LEGAL_DOCUMENT_VERSION,
    )
    return resultado


@app.post("/api/organizations/{organization_id}/validation/administrations")
async def record_validation_administration(organization_id: str, request: Request):
    """Escore do instrumento aplicado pelo profissional, e os padrões da janela."""
    context = _require_tenant_management_context(
        request, organization_id, "reports.write"
    )
    if not froid_validation.collection_allowed():
        raise HTTPException(
            status_code=409,
            detail="coleta bloqueada: parecer do CEP ainda não registrado "
                   "(FROID_RESEARCH_CAAE)",
        )
    body = await request.json()
    patient_id = str(body.get("patient_id") or "")
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id é obrigatório")
    try:
        score = float(body.get("total_score"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="total_score inválido")
    try:
        return TENANT_STORE.validation_record_administration(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            patient_id=patient_id,
            instrument_code=str(body.get("instrument") or "PHQ-9"),
            total_score=score,
            administered_by=context.user_id,
            administered_at=str(body.get("administered_at") or "")
            or datetime.now(timezone.utc).isoformat(),
            session_id=body.get("session_id"),
            observations=list(body.get("observations") or []),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/organizations/{organization_id}/validation/patients/{patient_id}")
async def read_validation_history(organization_id: str, patient_id: str, request: Request):
    context = _require_tenant_management_context(
        request, organization_id, "patients.read_assigned"
    )
    return {
        "consent": TENANT_STORE.validation_consent_state(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            patient_id=patient_id,
        ),
        "administrations": TENANT_STORE.validation_patient_history(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            patient_id=patient_id,
        ),
    }


@app.get("/api/organizations/{organization_id}/validation/progress")
async def read_validation_progress(organization_id: str, request: Request):
    """Progresso da coleta. Sem coeficiente, deliberadamente.

    Correlação parcial numa tela de uso diário vira número que a pessoa
    lembra e repete fora de contexto. Progresso não tem esse risco.
    """
    context = _require_tenant_management_context(
        request, organization_id, "reports.read_assigned"
    )
    coletados = {
        f"{item['pattern_key']}:{item['instrument']}": item["pairs"]
        for item in TENANT_STORE.validation_progress(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
    }
    return {
        "target": froid_validation.TARGET_PAIRS,
        "pilot": froid_validation.PILOT_PAIRS,
        "floor": froid_validation.MIN_PAIRS,
        # Sem parecer do CEP a tela some, em vez de oferecer o que o backend
        # vai recusar.
        "collection_allowed": froid_validation.collection_allowed(),
        "ethics_approval": froid_validation.ethics_approval(),
        "hypotheses": [
            {
                "pattern_key": p.pattern_key,
                "instrument": p.instrument,
                "expected_direction": p.expected_direction,
                "pairs": coletados.get(f"{p.pattern_key}:{p.instrument}", 0),
            }
            for p in froid_validation.DECLARED_PAIRINGS
        ],
    }


@app.get("/api/organizations/{organization_id}/validation/report")
async def read_validation_report(organization_id: str, request: Request):
    """As três hipóteses avaliadas contra os pares coletados."""
    context = _require_tenant_management_context(
        request, organization_id, "reports.read_all"
    )
    saida = []
    for pairing in froid_validation.DECLARED_PAIRINGS:
        xs, ys = TENANT_STORE.validation_pairs(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            pattern_key=pairing.pattern_key,
            instrument_code=pairing.instrument,
        )
        resultado = froid_validation.evaluate(pairing, xs, ys)
        saida.append({
            "pattern_key": resultado.pattern_key,
            "instrument": resultado.instrument,
            "expected_direction": pairing.expected_direction,
            "n": resultado.n,
            "progress": resultado.progress,
            "is_final": resultado.is_final,
            "r": resultado.r,
            "interval": resultado.interval,
            "verdict": resultado.verdict,
            "detail": resultado.detail,
            "statement": froid_validation.evidence_statement(resultado),
        })
    return {"target": froid_validation.TARGET_PAIRS, "results": saida}


@app.get("/api/organizations/{organization_id}/nr1/criteria")
async def read_nr1_criteria(organization_id: str, request: Request):
    """Documento de critérios do GRO — the third mandatory PGR document."""
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    criteria = _nr1_criteria_for(context)
    return {
        "published": criteria.source != "froid-default",
        "version": criteria.version,
        "source": criteria.source,
        "document": criteria.as_document(),
    }


@app.post("/api/organizations/{organization_id}/nr1/criteria")
async def publish_nr1_criteria(organization_id: str, request: Request):
    """Publish an immutable version of the criteria.

    Accepts a full document, or a matrix shape to rescale the FROID default onto
    the gradations the organization already uses for its other risks.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.inventory.manage"
    )
    body = await request.json()
    document = body.get("document")
    if not isinstance(document, dict):
        severity_max = _local_int(body.get("severity_levels")) or 5
        probability_max = _local_int(body.get("probability_levels")) or 5
        try:
            document = nr1_compliance.criteria_for_scale(
                severity_max, probability_max
            ).as_document()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        try:
            nr1_compliance.GradationCriteria.from_document(document)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"critérios inválidos: {exc}")

    document.setdefault("classification_rules", {
        "basis": "NR-1 1.5.4.4.3",
        "note": (
            "Riscos classificados para determinar a necessidade de adoção ou "
            "manutenção de medidas e a elaboração do plano de ação."
        ),
    })
    document.setdefault("decision_rules", {
        "priority": (
            "Nível de risco, seguido do número de trabalhadores possivelmente "
            "atingidos (NR-1 1.5.5.2.1.1)."
        ),
        "measure_hierarchy": list(nr1_compliance.MEASURE_HIERARCHY),
        "effectiveness": (
            "Eficácia aferida por comparação da unidade contra a própria linha "
            "de base; medida sem eficácia demonstrada deve ser corrigida "
            "(NR-1 1.5.5.3.2.1)."
        ),
    })

    try:
        published = TENANT_STORE.nr1_publish_criteria(
            organization_id=organization_id,
            membership_id=context.membership_id,
            document=document,
            review_interval_months=_local_int(body.get("review_interval_months")) or 24,
            has_certified_sst_system=bool(body.get("has_certified_sst_system")),
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to publish NR-1 criteria")
        raise HTTPException(status_code=400, detail="não foi possível publicar os critérios")

    _record_tenant_success(
        context, "nr1.criteria.publish", "gro_risk_criteria",
        published["criteria_id"], {"version": published["version"]},
    )
    return published


@app.post("/api/organizations/{organization_id}/nr1/aep")
async def create_nr1_aep(organization_id: str, request: Request):
    """Open an Avaliação Ergonômica Preliminar for one evaluation unit."""
    context = _require_enterprise_context(
        request, organization_id, "nr1.inventory.manage"
    )
    body = await request.json()
    unit_id = str(body.get("unit_id") or "").strip()
    if not unit_id:
        raise HTTPException(status_code=400, detail="unidade de avaliação obrigatória")
    try:
        created = TENANT_STORE.nr1_create_aep(
            organization_id=organization_id,
            membership_id=context.membership_id,
            unit_id=unit_id,
            reference_period=str(body.get("reference_period") or "").strip(),
            criteria_id=str(body.get("criteria_id") or "").strip() or None,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to open AEP")
        raise HTTPException(status_code=400, detail="não foi possível abrir a AEP")
    _record_tenant_success(
        context, "nr1.aep.create", "aep_assessment", created["aep_id"]
    )
    return created


@app.post("/api/organizations/{organization_id}/nr1/aep/{aep_id}/evidence")
async def add_nr1_aep_evidence(organization_id: str, aep_id: str, request: Request):
    """Attach one piece of evidence, naming the method it came from.

    A questionnaire never stands alone: the MTE is explicit that its results do
    not by themselves prove risk management, so every AEP records which methods
    grounded it.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.inventory.manage"
    )
    body = await request.json()
    method = str(body.get("method") or "").strip()
    allowed_methods = {
        "activity_observation", "worker_dialogue", "questionnaire",
        "workshop", "focus_group", "document_analysis", "cipa_manifestation",
    }
    if method not in allowed_methods:
        raise HTTPException(status_code=400, detail="método de evidência inválido")
    summary = str(body.get("summary") or "").strip()
    collected_on = body.get("collected_on")
    if not summary or not collected_on:
        raise HTTPException(status_code=400, detail="data e descrição são obrigatórias")
    try:
        evidence_id = TENANT_STORE.nr1_add_aep_evidence(
            organization_id=organization_id,
            membership_id=context.membership_id,
            aep_id=aep_id,
            method=method,
            collected_on=collected_on,
            summary=summary,
            collected_by=str(body.get("collected_by") or "").strip(),
            campaign_id=str(body.get("campaign_id") or "").strip() or None,
            evidence_reference=str(body.get("evidence_reference") or "").strip(),
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to record AEP evidence")
        raise HTTPException(status_code=400, detail="não foi possível registrar a evidência")
    _record_tenant_success(
        context, "nr1.aep.evidence", "aep_assessment", aep_id, {"method": method}
    )
    return {"evidence_id": evidence_id, "aep_id": aep_id, "method": method}


@app.get("/api/organizations/{organization_id}/nr1/aep")
async def list_nr1_aep(organization_id: str, request: Request):
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    try:
        items = TENANT_STORE.nr1_list_aep(
            organization_id=organization_id,
            membership_id=context.membership_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    _record_tenant_success(
        context, "nr1.aep.list", "aep_assessment", organization_id,
        {"result_count": len(items)},
    )
    return {"assessments": items}


@app.patch("/api/organizations/{organization_id}/nr1/aep/{aep_id}")
async def update_nr1_aep(organization_id: str, aep_id: str, request: Request):
    """Fill in the AEP while it is being conducted.

    The body can only reach the descriptive fields. Status and the conclusion
    date are not editable here: dating and signing the document is a separate,
    audited act.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.inventory.manage"
    )
    body = await request.json()
    fields = {
        name: body[name]
        for name in TENANT_STORE.NR1_AEP_EDITABLE_FIELDS
        if name in body
    }
    aet_required = body.get("aet_required")
    if aet_required is not None:
        aet_required = bool(aet_required)
    if not fields and aet_required is None:
        raise HTTPException(status_code=400, detail="nenhum campo editável informado")
    try:
        updated = TENANT_STORE.nr1_update_aep(
            organization_id=organization_id,
            membership_id=context.membership_id,
            aep_id=aep_id,
            fields=fields,
            aet_required=aet_required,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError as exc:
        if str(exc) == "no_editable_field":
            raise HTTPException(status_code=400, detail="nenhum campo editável informado")
        raise HTTPException(
            status_code=409,
            detail="AEP não encontrada ou já concluída — conclua uma nova revisão",
        )
    _record_tenant_success(
        context, "nr1.aep.update", "aep_assessment", aep_id,
        {"fields": sorted(fields)},
    )
    return updated


@app.post("/api/organizations/{organization_id}/nr1/aep/{aep_id}/conclude")
async def conclude_nr1_aep(organization_id: str, aep_id: str, request: Request):
    """Date and sign the AEP.

    Refused unless the real work is described, a responsible is named and at
    least one piece of evidence was recorded. An undated, unsigned or unfounded
    document is not evidence of diligence — it is the absence of it.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.inventory.manage"
    )
    try:
        concluded = TENANT_STORE.nr1_conclude_aep(
            organization_id=organization_id,
            membership_id=context.membership_id,
            aep_id=aep_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=(
                "para concluir, a AEP precisa da descrição do trabalho real, "
                "de um responsável nomeado e de ao menos uma evidência"
            ),
        )
    _record_tenant_success(
        context, "nr1.aep.conclude", "aep_assessment", aep_id
    )
    return concluded


@app.get("/api/organizations/{organization_id}/nr1/aep/{aep_id}")
async def read_nr1_aep(organization_id: str, aep_id: str, request: Request):
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    try:
        aep = TENANT_STORE.nr1_get_aep(
            organization_id=organization_id,
            membership_id=context.membership_id,
            aep_id=aep_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    if aep is None:
        raise HTTPException(status_code=404, detail="AEP não encontrada")
    methods = {item["method"] for item in aep["evidence"]}
    aep["method_count"] = len(methods)
    # Surfaced rather than blocked: the norm does not forbid a single method,
    # but an AEP resting only on a questionnaire is the exact shape the FAQ
    # says does not prove risk management on its own.
    aep["single_method_warning"] = (
        methods == {"questionnaire"}
        or (len(methods) == 1 and aep["status"] == "concluded")
    )
    _record_tenant_success(context, "nr1.aep.read", "aep_assessment", aep_id)
    return aep


@app.post("/api/organizations/{organization_id}/nr1/effectiveness")
async def review_nr1_effectiveness(organization_id: str, request: Request):
    """Did the prevention measures work? Measured, not asserted.

    Compares a follow-up campaign against an earlier baseline for the same unit
    and dimension. Feeds the eficácia term that 1.5.4.4.5.3 puts inside the
    probability, and flags measures that 1.5.5.3.2.1 obliges correcting.

    A POST because it records the review: the verdict becomes the efficacy the
    next cycle grades against, so it is an act, not a lookup.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    body = await request.json()
    baseline_id = str(body.get("baseline_campaign_id") or "").strip()
    followup_id = str(body.get("followup_campaign_id") or "").strip()
    if not baseline_id or not followup_id:
        raise HTTPException(
            status_code=400,
            detail="baseline_campaign_id e followup_campaign_id são obrigatórios",
        )
    if baseline_id == followup_id:
        raise HTTPException(
            status_code=400, detail="a comparação exige duas campanhas distintas"
        )
    try:
        baseline_rows = TENANT_STORE.nr1_dimension_scores(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=baseline_id,
        )
        followup_rows = TENANT_STORE.nr1_dimension_scores(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=followup_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to compare NR-1 campaigns")
        raise HTTPException(status_code=503, detail="comparação indisponível")

    if not baseline_rows or not followup_rows:
        return {
            "baseline_campaign_id": baseline_id,
            "followup_campaign_id": followup_id,
            "comparable": False,
            "reviews": [],
            "notice": (
                "Comparação indisponível: as duas campanhas precisam estar "
                "encerradas e ter atingido o piso de coorte."
            ),
        }

    # Os mesmos criterios que graduam o inventario decidem em que escala a
    # exigencia da atividade e lida aqui. Sem passa-los, a comparacao usava a
    # escala padrao do FROID mesmo para quem publicou uma matriz propria.
    verdicts = nr1_effectiveness.compare_campaigns(
        (nr1_compliance.DimensionScore(**row) for row in baseline_rows),
        (nr1_compliance.DimensionScore(**row) for row in followup_rows),
        _nr1_criteria_for(context),
    )
    payload = [
        {
            "unit_id": verdict.unit_id,
            "dimension_id": verdict.dimension_id,
            "baseline_cohort": verdict.baseline_cohort,
            "followup_cohort": verdict.followup_cohort,
            "baseline_mean": verdict.baseline_mean,
            "followup_mean": verdict.followup_mean,
            "effect_size": verdict.effect_size,
            # A margem viaja junto com o efeito de propósito: sem ela, quem lê
            # não distingue um resultado de um ruído.
            "effect_margin": verdict.effect_margin,
            "significant": verdict.significant,
            "verdict": verdict.verdict,
            "measure_efficacy": verdict.measure_efficacy,
            "requires_correction": verdict.requires_correction,
            "rationale": verdict.rationale,
        }
        for verdict in verdicts
    ]

    if payload and "nr1.inventory.manage" in context.permissions:
        try:
            TENANT_STORE.nr1_store_effectiveness(
                organization_id=organization_id,
                membership_id=context.membership_id,
                baseline_campaign_id=baseline_id,
                followup_campaign_id=followup_id,
                verdicts=payload,
            )
        except Exception:
            LOGGER.exception("Unable to persist NR-1 effectiveness review")

    _record_tenant_success(
        context, "nr1.effectiveness.review", "assessment_campaign", followup_id,
        {"result_count": len(payload)},
    )
    return {
        "baseline_campaign_id": baseline_id,
        "followup_campaign_id": followup_id,
        "comparable": True,
        "notice": "",
        "requires_correction": sum(
            1 for item in payload if item["requires_correction"]
        ),
        "reviews": payload,
    }


@app.get("/api/organizations/{organization_id}/nr1/campaigns")
async def list_nr1_campaigns(organization_id: str, request: Request):
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    try:
        campaigns = TENANT_STORE.nr1_list_campaigns(
            organization_id=organization_id,
            membership_id=context.membership_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    _record_tenant_success(
        context, "nr1.campaign.list", "assessment_campaign", organization_id,
        {"result_count": len(campaigns)},
    )
    return {"campaigns": campaigns}


@app.post("/api/organizations/{organization_id}/nr1/campaigns")
async def create_nr1_campaign(organization_id: str, request: Request):
    context = _require_enterprise_context(
        request, organization_id, "nr1.campaigns.manage"
    )
    body = await request.json()
    instrument_id = str(body.get("instrument_id") or "").strip()
    title = str(body.get("title") or "").strip()
    opens_at = body.get("opens_at")
    closes_at = body.get("closes_at")
    if not instrument_id or not title or not opens_at or not closes_at:
        raise HTTPException(
            status_code=400,
            detail="instrumento, título e janela de coleta são obrigatórios",
        )
    try:
        created = TENANT_STORE.nr1_create_campaign(
            organization_id=organization_id,
            membership_id=context.membership_id,
            instrument_id=instrument_id,
            title=title,
            opens_at=opens_at,
            closes_at=closes_at,
            unit_id=str(body.get("unit_id") or "").strip() or None,
            reference_period=str(body.get("reference_period") or "").strip(),
            target_headcount=_local_int(body.get("target_headcount")),
            # A base legal entra na estrutura, nao no texto livre: o campo e
            # preenchido por campanha, por gente diferente, sob pressa.
            purpose_notice=lgpd_registry.compose_purpose_notice(
                str(body.get("purpose_notice") or "")
            ),
            support_channel_label=str(body.get("support_channel_label") or "").strip(),
            support_channel_detail=str(body.get("support_channel_detail") or "").strip(),
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to create NR-1 campaign")
        raise HTTPException(status_code=400, detail="não foi possível criar a campanha")
    _record_tenant_success(
        context, "nr1.campaign.create", "assessment_campaign",
        created["campaign_id"],
    )
    return created


@app.post("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/open")
async def open_nr1_campaign(organization_id: str, campaign_id: str, request: Request):
    """Start collection.

    The database refuses to open a campaign without a support channel and a
    purpose notice, so this cannot be shipped by accident.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.campaigns.manage"
    )
    try:
        opened = TENANT_STORE.nr1_open_campaign(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError:
        raise HTTPException(status_code=409, detail="campanha não está em rascunho")
    except Exception as exc:
        LOGGER.exception("Unable to open NR-1 campaign")
        detail = str(exc)
        if "efetivo de trabalhadores" in detail:
            raise HTTPException(
                status_code=400,
                detail=(
                    "informe o efetivo de trabalhadores do período de "
                    "referência antes de abrir a coleta: é ele que define "
                    "quantas respostas tornam o resultado representativo"
                ),
            )
        if "canal de apoio" in detail or "aviso de finalidade" in detail:
            raise HTTPException(
                status_code=400,
                detail=(
                    "informe o aviso de finalidade e o canal de apoio ao "
                    "colaborador antes de abrir a coleta"
                ),
            )
        raise HTTPException(status_code=400, detail="não foi possível abrir a campanha")
    _record_tenant_success(
        context, "nr1.campaign.open", "assessment_campaign", campaign_id
    )
    return opened


@app.post("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/close")
async def close_nr1_campaign(organization_id: str, campaign_id: str, request: Request):
    """End collection, which is what makes the aggregate readable.

    Results are withheld while a campaign is open on purpose: a cohort that is
    still growing can be differenced one respondent at a time, and no cohort
    floor protects against that.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.campaigns.manage"
    )
    try:
        closed = TENANT_STORE.nr1_close_campaign(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError:
        raise HTTPException(status_code=409, detail="campanha não está aberta")
    _record_tenant_success(
        context, "nr1.campaign.close", "assessment_campaign", campaign_id
    )
    return closed


def _nr1_subject_pseudonym(organization_id: str, payroll_number: str) -> str:
    """Salted pseudonym for one worker, scoped to the organization.

    Keyed HMAC rather than a plain digest: without the server key nobody can
    rebuild the table by hashing a payroll list they already hold.
    """
    if not FROID_DATAMART_PSEUDONYM_KEY:
        raise RuntimeError("FROID_DATAMART_PSEUDONYM_KEY is required")
    raw = f"nr1:{organization_id}:{str(payroll_number).strip().lower()}"
    return hmac.new(
        FROID_DATAMART_PSEUDONYM_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _nr1_token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


@app.post("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/invitations")
async def create_nr1_invitations(
    organization_id: str, campaign_id: str, request: Request
):
    """Turn a payroll list into single-use anonymous invitation links.

    The response carries the raw tokens once, for distribution. They are not
    recoverable afterwards: only their digest is stored.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.campaigns.manage"
    )
    body = await request.json()
    subjects = body.get("subjects")
    if not isinstance(subjects, list) or not subjects:
        raise HTTPException(status_code=400, detail="lista de colaboradores obrigatória")
    if len(subjects) > 5000:
        raise HTTPException(status_code=400, detail="limite de 5000 convites por chamada")

    prepared: list[dict] = []
    links: list[dict] = []
    try:
        for subject in subjects:
            payroll_number = str((subject or {}).get("payroll_number") or "").strip()
            if not payroll_number:
                raise HTTPException(status_code=400, detail="matrícula obrigatória")
            token = secrets.token_urlsafe(32)
            pseudonym = _nr1_subject_pseudonym(organization_id, payroll_number)
            prepared.append(
                {
                    "pseudonym": pseudonym,
                    "token_hash": _nr1_token_hash(token),
                    "unit_id": str((subject or {}).get("unit_id") or "").strip() or None,
                }
            )
            # Echoed back so the employer can dispatch the link, paired with the
            # payroll number it already holds. FROID never stores the pairing.
            links.append(
                {
                    "payroll_number": payroll_number,
                    "token": token,
                    "pseudonym": pseudonym,
                }
            )
    except RuntimeError:
        raise HTTPException(status_code=503, detail="chave de pseudonimização não configurada")

    try:
        criados = TENANT_STORE.nr1_create_invitations(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
            subjects=prepared,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to create NR-1 invitations")
        raise HTTPException(status_code=400, detail="não foi possível registrar os convites")

    # Só devolve o link do convite que existe.
    #
    # Quem já tinha convite nesta campanha é ignorado pelo ON CONFLICT, e o
    # token recém-gerado para ele nunca chegou ao banco. Devolvê-lo junto dos
    # demais entregava ao RH uma planilha com links mortos indistinguíveis dos
    # vivos — e o trabalhador que recebesse um deles leria "convite
    # indisponível" sem que ninguém soubesse por quê.
    gravados = set(criados)
    emitidos = [
        {"payroll_number": link["payroll_number"], "token": link["token"]}
        for link in links
        if link["pseudonym"] in gravados
    ]
    ja_convidados = [
        link["payroll_number"] for link in links if link["pseudonym"] not in gravados
    ]

    _record_tenant_success(
        context, "nr1.invitation.create", "assessment_campaign", campaign_id,
        {"result_count": len(emitidos)},
    )
    return {
        "campaign_id": campaign_id,
        "created": len(emitidos),
        "links": emitidos,
        # A matrícula volta porque foi o empregador quem a enviou: ele precisa
        # saber quem já tinha convite para não ficar esperando resposta de quem
        # nunca recebeu link novo.
        "already_invited": ja_convidados,
    }


@app.post(
    "/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/invitations/reissue"
)
async def reissue_nr1_invitations(
    organization_id: str, campaign_id: str, request: Request
):
    """Emite um link novo para quem perdeu o dele, e só para quem não respondeu.

    Rota separada da emissão, e não uma opção dela, porque o efeito é
    destrutivo: o link anterior para de funcionar no instante em que o novo é
    gravado. Isso precisa ser um ato deliberado, com nome próprio na trilha de
    auditoria, e não uma caixa marcada por engano no meio do fluxo normal.

    Quem já respondeu não recebe link novo, e a recusa é do banco, não daqui.

    **O que esta rota revela, dito de propósito.** Quem opera o RH já tem o
    pareamento matrícula-link no CSV que baixou, e já podia descobrir quem
    respondeu abrindo cada link e vendo qual recusa. Esta rota não cria esse
    conhecimento — mas torna barato obtê-lo em lote, e isso é diferença real.
    As contenções são três: o lote é limitado, toda reemissão vira evento de
    auditoria com autor e contagem, e a resposta não diz POR QUE alguém não foi
    reemitido. "Sem convite pendente" cobre tanto quem já respondeu quanto quem
    nunca foi convidado — o servidor não afirma qual dos dois.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.campaigns.manage"
    )
    body = await request.json()
    matriculas = body.get("payroll_numbers")
    if not isinstance(matriculas, list) or not matriculas:
        raise HTTPException(status_code=400, detail="lista de matrículas obrigatória")
    if len(matriculas) > 50:
        raise HTTPException(
            status_code=400,
            detail=(
                "limite de 50 matrículas por reemissão: reemitir em massa é "
                "redistribuir a campanha inteira, e isso é campanha nova"
            ),
        )

    prepared: list[dict] = []
    links: list[dict] = []
    try:
        for entrada in matriculas:
            payroll_number = str(entrada or "").strip()
            if not payroll_number:
                raise HTTPException(status_code=400, detail="matrícula obrigatória")
            token = secrets.token_urlsafe(32)
            pseudonym = _nr1_subject_pseudonym(organization_id, payroll_number)
            prepared.append(
                {"pseudonym": pseudonym, "token_hash": _nr1_token_hash(token)}
            )
            links.append(
                {
                    "payroll_number": payroll_number,
                    "token": token,
                    "pseudonym": pseudonym,
                }
            )
    except RuntimeError:
        raise HTTPException(status_code=503, detail="chave de pseudonimização não configurada")

    try:
        reemitidos = TENANT_STORE.nr1_reissue_invitations(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
            subjects=prepared,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to reissue NR-1 invitations")
        raise HTTPException(status_code=400, detail="não foi possível reemitir os convites")

    trocados = set(reemitidos)
    emitidos = [
        {"payroll_number": link["payroll_number"], "token": link["token"]}
        for link in links
        if link["pseudonym"] in trocados
    ]
    sem_convite = [
        link["payroll_number"] for link in links if link["pseudonym"] not in trocados
    ]

    _record_tenant_success(
        context, "nr1.invitation.reissue", "assessment_campaign", campaign_id,
        {"result_count": len(emitidos)},
    )
    return {
        "campaign_id": campaign_id,
        "reissued": len(emitidos),
        "links": emitidos,
        "sem_convite_pendente": sem_convite,
    }


@app.post("/api/organizations/{organization_id}/nr1/explica")
async def nr1_explica_query(organization_id: str, request: Request):
    """Pergunta aberta sobre a NR-1, respondida a partir do acervo corporativo.

    Rota SEPARADA de `/api/froid-explica/query`, e a separacao e a fronteira do
    produto, nao arrumacao de codigo. Aquela rota exige aprovacao profissional
    e assinatura, e injeta resumo da carteira de pacientes quando a pergunta e
    comparativa. Reaproveita-la para o empregador levaria dado clinico para o
    lado errado da fronteira por um caminho que ninguem estaria olhando.

    Aqui a autorizacao e a mesma do painel agregado — quem pode ler o resultado
    da propria organizacao pode perguntar sobre a norma que o produziu — e o
    acervo consultado e uma collection propria, sem material clinico dentro.

    Quando nao ha acervo indexado ou o modelo nao responde, devolve
    `disponivel: false` em vez de erro: a tela tem conteudo curado proprio e
    continua respondendo sem esta rota. Uma tela de duvida que quebra na frente
    do cliente e pior do que uma tela que responde menos.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    body = await request.json()
    pergunta = str(body.get("pergunta") or body.get("query_text") or "").strip()
    if not pergunta:
        raise HTTPException(status_code=400, detail="pergunta obrigatória")
    if len(pergunta) > 800:
        raise HTTPException(
            status_code=400,
            detail="pergunta muito longa: resuma em uma ou duas frases",
        )

    trechos, prompt = nr1_explica.preparar(pergunta)
    if not trechos:
        # Acervo ausente nao e falha do usuario nem do servidor: e estado
        # conhecido, e a tela sabe o que fazer com ele.
        return {
            "disponivel": False,
            "motivo": "acervo_nao_indexado",
            "resposta": "",
            "citacoes": [],
        }

    texto, motor = await _generate_froid_explain_text(
        nr1_explica.INSTRUCAO, prompt, temperature=0.1, max_tokens=800
    )
    if not texto:
        return {
            "disponivel": False,
            "motivo": "gerador_indisponivel",
            "resposta": "",
            "citacoes": nr1_explica.citacoes(trechos),
        }

    _record_tenant_success(
        context, "nr1.explica.query", "assessment_campaign", organization_id,
        {"result_count": len(trechos)},
    )
    return {
        "disponivel": True,
        "resposta": texto,
        "citacoes": nr1_explica.citacoes(trechos),
        "motor": motor,
    }


@app.get("/api/nr1/questionnaire")
async def read_nr1_questionnaire(request: Request):
    """Fetch the form for one invitation token. No login, no tenant header.

    Fails uniformly: an unknown token, a used one and a closed campaign all
    return the same 404, so the endpoint cannot be used to probe who was
    invited or who already answered.
    """
    token = str(request.query_params.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token obrigatório")
    try:
        payload = TENANT_STORE.nr1_questionnaire_for_token(
            token_hash=_nr1_token_hash(token)
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to load NR-1 questionnaire")
        raise HTTPException(status_code=503, detail="questionário indisponível")
    if not payload:
        raise HTTPException(
            status_code=404, detail="convite indisponível ou fora da janela de coleta"
        )
    return payload


@app.post("/api/nr1/responses")
async def submit_nr1_response(request: Request):
    """Anonymous questionnaire submission. No login, no tenant header.

    Intentionally uniform in its failure mode: an expired token, a closed
    campaign and an already-used token all return the same 409, so the endpoint
    cannot be used to probe who was invited or who already answered.
    """
    body = await request.json()
    token = str(body.get("token") or "").strip()
    answers = body.get("answers")
    if not token or not isinstance(answers, dict) or not answers:
        raise HTTPException(status_code=400, detail="token e respostas são obrigatórios")
    normalized: dict[str, int] = {}
    for item_id, value in answers.items():
        try:
            normalized[str(item_id)] = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="resposta inválida")
    try:
        accepted = TENANT_STORE.nr1_submit_response(
            token_hash=_nr1_token_hash(token), answers=normalized
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError:
        raise HTTPException(status_code=400, detail="respostas inválidas")
    except Exception:
        LOGGER.exception("Unable to record NR-1 response")
        raise HTTPException(status_code=503, detail="coleta indisponível")
    if not accepted:
        raise HTTPException(
            status_code=409, detail="convite indisponível ou fora da janela de coleta"
        )
    return {"status": "recorded"}


def _require_nr1_persistence() -> None:
    """Falha com uma frase util quando o modulo NR-1 nao esta ligado.

    O tenant_store levanta RuntimeError quando FROID_PERSISTENCE_MODE nao e
    'dual' ou quando falta o papel de runtime. Sem esta traducao, quem esta
    cadastrando a empresa recebe um 500 mudo no meio do formulario e nao tem
    como saber que o problema e de configuracao do servidor, e nao do que
    digitou.
    """
    if not TENANT_STORE.enabled or not TENANT_STORE.runtime_database_url:
        raise HTTPException(
            status_code=503,
            detail=(
                "modulo NR-1 indisponivel: requer FROID_PERSISTENCE_MODE=dual, "
                "FROID_DATABASE_URL e FROID_RUNTIME_DATABASE_URL configurados "
                "no servidor."
            ),
        )


@app.get("/api/organizations/{organization_id}/nr1/instruments")
async def list_nr1_instruments(organization_id: str, request: Request):
    """Os instrumentos publicados que uma campanha pode usar.

    A criacao de campanha sempre exigiu `instrument_id` e nenhuma rota o
    devolvia — na pratica, so era possivel criar campanha com o UUID em maos.
    A tela ficava impossivel de construir sem fixar o id no front, que e a
    quinta copia espelhada de um parametro que so o banco decide.

    Escopo de organizacao na URL apesar de o catalogo ser global: quem pergunta
    precisa ser membro de uma organizacao enterprise, e e o mesmo contexto que
    a tela ja tem em maos. Nao ha dado de terceiro aqui — o instrumento e o
    mesmo para todas as empresas.
    """
    _require_enterprise_context(request, organization_id, "nr1.unit.list")
    _require_nr1_persistence()
    try:
        instrumentos = TENANT_STORE.nr1_list_instruments()
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to list NR-1 instruments")
        raise HTTPException(status_code=503, detail="catálogo de instrumentos indisponível")
    return {"instruments": instrumentos}


@app.get("/api/organizations/{organization_id}/legal-acceptances")
async def list_organization_legal_acceptances(organization_id: str, request: Request):
    """O que ESTA pessoa aceitou, com versao, impressao digital e data.

    A materia-prima do comprovante de aceite, que e um documento diferente do
    contrato: o contrato prova o texto, o comprovante prova a contratacao
    daquele texto por aquela pessoa naquela data.

    Devolve as aceitacoes do proprio solicitante, nao as da organizacao
    inteira. Nao e limitacao: o comprovante e a prova de um ato, e o ato tem um
    autor. Listar as de terceiros exporia quem mais da empresa se cadastrou —
    dado que nenhuma tela precisa e que ninguem pediu.
    """
    user = _require_current_user(request)
    context = _require_tenant_management_context(
        request, organization_id, "organization.read"
    )
    email = _normalize_email(user.get("email") or "")
    assinatura = _legal_hmac(email)
    # O catalogo nao e parametrizado por jurisdicao: `public_legal_catalog()`
    # devolve os textos, e so `acceptance_required` varia por pais. Passar
    # jurisdicao aqui seria inventar uma assinatura que a funcao nao tem.
    catalogo = public_legal_catalog()
    if not assinatura:
        # Sem chave nao ha o que procurar, e dizer "nenhum aceite" seria mentir
        # por omissao: a diferenca entre "nunca aceitou" e "nao consigo
        # verificar" e a diferenca inteira num documento de prova.
        return {
            "ledger_configured": False,
            "acceptances": [],
            "organization_id": context.organization_id,
            "subject_email": email,
            "documents": catalogo.get("documents", {}),
            "supplier": catalogo.get("supplier", {}),
        }
    try:
        registros = TENANT_STORE.list_legal_acceptances(
            subject_reference_hash=assinatura
        )
    except Exception:
        LOGGER.exception("Unable to list legal acceptances")
        raise HTTPException(status_code=503, detail="registro de aceites indisponível")
    return {
        "ledger_configured": True,
        "acceptances": registros,
        "organization_id": context.organization_id,
        "subject_email": email,
        # O catalogo vigente viaja junto para que o comprovante possa imprimir
        # a INTEGRA do que foi aceito, e nao so a referencia. Cabe a tela
        # comparar o sha256 registrado com o do catalogo: divergiu, o texto
        # vigente nao e o texto aceito, e o comprovante precisa dizer isso em
        # vez de imprimir o texto de hoje sob a data de ontem.
        "documents": catalogo.get("documents", {}),
        "supplier": catalogo.get("supplier", {}),
    }


@app.get("/api/organizations/{organization_id}/nr1/units")
async def list_nr1_units(organization_id: str, request: Request):
    """Estrutura da empresa: estabelecimentos e os setores de cada um.

    Precede tudo no modulo NR-1. Sem estabelecimento nao ha unidade de
    resultado, e sem setor nao ha recorte publicavel — a campanha nem chega a
    ser desenhavel.
    """
    context = _require_enterprise_context(request, organization_id, "nr1.unit.list")
    _require_nr1_persistence()
    unidades = TENANT_STORE.nr1_list_units(
        organization_id=organization_id,
        membership_id=context.membership_id,
        include_archived=str(request.query_params.get("include_archived") or "")
        .strip()
        .lower()
        in {"1", "true", "yes"},
    )
    estabelecimentos = [u for u in unidades if u["unit_type"] == "site"]
    return {
        "units": unidades,
        "site_count": len(estabelecimentos),
        "sector_count": len([u for u in unidades if u["unit_type"] == "sector"]),
        # O piso de anonimato e propriedade da UNIDADE, nao da empresa: uma
        # matriz grande nao salva a filial pequena. Devolver o efetivo por
        # estabelecimento deixa a tela avisar antes de a campanha ser montada.
        "headcount_by_site": {
            site["unit_id"]: site["headcount"] for site in estabelecimentos
        },
    }


@app.post("/api/organizations/{organization_id}/nr1/units", status_code=201)
async def create_nr1_unit(organization_id: str, request: Request):
    context = _require_enterprise_context(request, organization_id, "nr1.unit.manage")
    _require_nr1_persistence()
    body = await request.json()
    try:
        criada = TENANT_STORE.nr1_create_unit(
            organization_id=organization_id,
            membership_id=context.membership_id,
            name=str(body.get("name") or ""),
            unit_type=str(body.get("unit_type") or "sector"),
            parent_unit_id=(str(body.get("parent_unit_id")).strip() or None)
            if body.get("parent_unit_id")
            else None,
            external_code=str(body.get("external_code") or ""),
            headcount=_local_int(body.get("headcount")),
        )
    except ValueError as exc:
        # Regra de estrutura violada e erro do cliente, nao falha do servidor:
        # setor sem estabelecimento, pai de outra organizacao, nome vazio.
        raise HTTPException(status_code=400, detail=str(exc))
    return criada


@app.patch("/api/organizations/{organization_id}/nr1/units/{unit_id}")
async def update_nr1_unit(organization_id: str, unit_id: str, request: Request):
    """Renomeia, recontabiliza ou arquiva. Nao existe exclusao.

    O inventario de riscos aponta para a unidade e precisa sobreviver vinte anos
    (1.5.7.3.3.1). Apagar a linha deixaria o registro antigo sem referencia.
    """
    context = _require_enterprise_context(request, organization_id, "nr1.unit.manage")
    _require_nr1_persistence()
    body = await request.json()
    campos = {
        chave: body[chave]
        for chave in ("name", "external_code", "headcount", "status")
        if chave in body
    }
    if not campos:
        raise HTTPException(status_code=400, detail="nada a atualizar")
    if "headcount" in campos:
        campos["headcount"] = _local_int(campos["headcount"])
    try:
        return TENANT_STORE.nr1_update_unit(
            organization_id=organization_id,
            membership_id=context.membership_id,
            unit_id=unit_id,
            **campos,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _nr1_declared_findings(
    context: AccessContext,
    campaign_id: str,
    criteria,
    progress: dict,
    total: int,
) -> list[dict]:
    """Recortes que os portões reprovaram, prontos para o painel e o inventário.

    Suprimir é ocultar; declarar insuficiente é documentar. A diferença não é
    de redação: painel vazio é lido pelo cliente como "não há risco aqui", que é
    exatamente a conclusão que a ausência de dado não autoriza — e o contrato
    revisado em 25/08/2026 passou a proibi-la expressamente.

    Devolve lista vazia enquanto a coleta está aberta: ali nada foi reprovado
    ainda, e declarar insuficiência de uma campanha em andamento seria afirmar
    sobre um resultado que ainda não existe.
    """
    if progress.get("status") != "closed":
        return []
    try:
        rows = TENANT_STORE.nr1_unclassifiable_cohorts(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
    except Exception:
        # Falhar aqui não pode derrubar o painel de quem TEM resultado: a
        # declaração é acréscimo, e o agregado é o serviço.
        LOGGER.exception("Unable to read unclassifiable NR-1 cohorts")
        return []
    achados = nr1_compliance.unclassifiable_findings(rows, criteria)
    return [
        {
            "unit_id": achado.unit_id,
            "dimension_id": achado.dimension_id,
            "nr1_factor": achado.nr1_factor,
            "risk_level": achado.risk_level,
            "gate": achado.gate,
            # A amostra exigida sai do efetivo que a própria contratante
            # declarou. O que NÃO sai daqui é quantas respostas o recorte
            # reunido tem: esse número está abaixo do piso por definição.
            "required_responses": achado.required_responses,
            "declared_headcount": achado.declared_headcount,
            "escalation": achado.escalation,
        }
        for achado in achados
    ]


def _nr1_campaign_header(context: AccessContext, campaign_id: str) -> dict:
    """Título, período e janela da campanha, para o cabeçalho do documento.

    Vem da lista de campanhas porque o progresso só conta adesão. Falha aqui
    devolve dicionário vazio em vez de derrubar a leitura do inventário: o
    documento vale sem o cabeçalho completo, e não vale sem as linhas.
    """
    try:
        campanhas = TENANT_STORE.nr1_list_campaigns(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
    except Exception:
        LOGGER.exception("Unable to read campaign header for inventory")
        return {}
    for campanha in campanhas:
        if str(campanha.get("campaign_id")) == str(campaign_id):
            return {
                "title": campanha.get("title"),
                "reference_period": campanha.get("reference_period"),
                "opens_at": campanha.get("opens_at"),
                "closes_at": campanha.get("closes_at"),
                "unit_name": campanha.get("unit_name"),
            }
    return {}


def _nr1_campaign_level_declaration(progress: dict) -> list[dict]:
    """A insuficiência do conjunto, quando não há quebra por recorte a mostrar.

    Abaixo do piso da campanha o SQL não devolve verdito por unidade — numa
    campanha minúscula, dizer quais unidades apareceram revelaria quais tiveram
    ao menos uma resposta. A declaração existe mesmo assim, porque o que não
    pode acontecer é a tela não dizer nada.
    """
    if progress.get("status") != "closed":
        return []
    return [
        {
            "unit_id": None,
            "dimension_id": None,
            "nr1_factor": None,
            "risk_level": nr1_compliance.UNCLASSIFIABLE_LEVEL,
            "gate": "campanha_abaixo_do_piso",
            "required_responses": None,
            "declared_headcount": None,
            "escalation": nr1_compliance.escalation_note("campanha_abaixo_do_piso"),
        }
    ]


@app.get("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/panel")
async def read_nr1_panel(organization_id: str, campaign_id: str, request: Request):
    """Aggregated psychosocial panel, or an explicit suppression notice."""
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    try:
        progress = TENANT_STORE.nr1_campaign_progress(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
        rows = TENANT_STORE.nr1_dimension_scores(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError:
        raise HTTPException(status_code=404, detail="campanha não encontrada")
    except Exception:
        LOGGER.exception("Unable to aggregate NR-1 campaign")
        raise HTTPException(status_code=503, detail="painel NR-1 indisponível")

    # O piso que o banco aplica conta respostas substantivas, não convites
    # respondidos. Explicar a supressão pelo número errado manda o gestor
    # perseguir uma meta que já foi atingida.
    total = int(
        progress.get("substantive_responses", progress.get("responses") or 0) or 0
    )
    verdict = _nr1_representativeness(progress)
    criteria = _nr1_criteria_for(context)
    # Os recortes que os portões reprovaram. Vêm ANTES da bifurcação porque
    # existem nos dois casos: quando nada passou e quando parte passou. Um
    # painel que mostra três setores e cala sobre o quarto afirma, pelo
    # silêncio, que o quarto está bem.
    declarados = _nr1_declared_findings(
        context, campaign_id, criteria, progress, total
    )
    if not rows:
        # Distinguish the reasons, otherwise an open campaign that already
        # cleared the floor would report an empty notice and look broken.
        if progress.get("status") != "closed":
            notice = (
                "A coleta ainda está aberta. Nenhum resultado é liberado "
                "enquanto a coorte continua crescendo, porque quem observasse o "
                "painel a cada nova resposta poderia deduzir a resposta "
                "individual por diferença. Encerre a campanha para ver a "
                "gradação."
            )
        else:
            # Ordem deliberada: o piso de anonimato vem primeiro porque não se
            # negocia — enquanto ele não cair, discutir tamanho de amostra é
            # conversa sobre o portão errado.
            notice = (
                nr1_compliance.suppression_notice(total)
                or nr1_compliance.representativeness_notice(verdict)
                or "Nenhum recorte atingiu o piso mínimo de coorte."
            )
        _record_tenant_success(
            context, "nr1.panel.suppressed", "assessment_campaign", campaign_id,
            {"status": progress.get("status")},
        )
        return {
            "campaign_id": campaign_id,
            "reportable": False,
            "risks": [],
            # Nada classificado não é o mesmo que nada a dizer. Quando nem a
            # campanha atinge o piso, froid_nr1_unclassifiable_cohorts não
            # devolve quebra por unidade — de propósito, porque numa campanha
            # minúscula isso revelaria quais unidades tiveram ao menos uma
            # resposta — e a insuficiência declarada é a do conjunto.
            "declared": declarados or _nr1_campaign_level_declaration(progress),
            "progress": progress,
            "representativeness": _nr1_representativeness_payload(verdict),
            "notice": notice,
        }

    graded = nr1_compliance.grade_all(
        (nr1_compliance.DimensionScore(**row) for row in rows), criteria
    )
    _record_tenant_success(
        context, "nr1.panel.read", "assessment_campaign", campaign_id,
        {"result_count": len(graded)},
    )
    return {
        "campaign_id": campaign_id,
        "reportable": True,
        "notice": "",
        "progress": progress,
        "representativeness": _nr1_representativeness_payload(verdict),
        # Campanha que publica parte dos recortes precisa dizer o que aconteceu
        # com o resto. Sem isto o painel mostra os setores que foram bem e cala
        # sobre os que não formaram coorte — e um setor ausente da tela é lido
        # como setor sem problema.
        "declared": declarados,
        "risks": [
            {
                "dimension_id": risk.dimension_id,
                "nr1_factor": risk.nr1_factor,
                "unit_id": risk.unit_id,
                "cohort_size": risk.cohort_size,
                # Uma casa decimal numa escala de 1 a 5. As três que vinham do
                # SQL eram precisão falsa e ampliavam a superfície de
                # diferenciação entre ciclos sem informar nada a mais.
                "mean_score": round(risk.mean_score, 1),
                # A proporção sai em FAIXA, e a exata não sai.
                #
                # O tamanho da coorte é publicado exato — e tem de ser, porque é
                # o que sustenta a leitura do resultado. Publicando junto a
                # proporção com três casas, uma multiplicação devolvia a
                # contagem de pessoas na faixa crítica. Numa coorte de 15, 0,067
                # é exatamente uma pessoa.
                "critical_ratio_band": nr1_compliance.critical_ratio_band(
                    risk.critical_ratio
                ),
                "exposure_level": risk.exposure_level,
                "severity": risk.severity,
                "probability": risk.probability,
                "risk_level": risk.risk_level,
                "consequence": risk.consequence,
                "measure_efficacy": risk.measure_efficacy,
                "exposed_workers": risk.exposed_workers,
                "rationale": risk.rationale,
            }
            for risk in graded
        ],
    }


@app.post("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/inventory")
async def generate_nr1_inventory(
    organization_id: str, campaign_id: str, request: Request
):
    """Grade the campaign and persist the risk inventory that feeds the PGR."""
    context = _require_enterprise_context(
        request, organization_id, "nr1.inventory.manage"
    )
    try:
        progress = TENANT_STORE.nr1_campaign_progress(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
        rows = TENANT_STORE.nr1_dimension_scores(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError:
        raise HTTPException(status_code=404, detail="campanha não encontrada")

    total = int(
        progress.get("substantive_responses", progress.get("responses") or 0) or 0
    )
    # Coleta aberta continua sendo 409, e por outro motivo: não é insuficiência
    # de evidência, é resultado que ainda não existe. Gerar inventário de
    # campanha em andamento congelaria uma foto que a próxima resposta muda.
    if progress.get("status") != "closed":
        raise HTTPException(
            status_code=409,
            detail="encerre a coleta antes de gerar o inventário",
        )

    criteria = _nr1_criteria_for(context)
    # Campanha encerrada SEMPRE gera documento, mesmo sem nada classificado.
    #
    # Até 25/08/2026 esta função devolvia 409 quando nenhum recorte passava nos
    # portões: a empresa pagava o ciclo e não recebia documento nenhum, e ficava
    # sem nada para mostrar a uma fiscalização que continua cobrando dela. Pior,
    # a ausência de documento era lida como ausência de risco.
    #
    # 1.5.7.3.1 manda consolidar no inventário os dados da identificação de
    # perigos e das avaliações — não apenas os riscos que couberam numa
    # classificação. E 1.5.4.2.1.3 é explícito ao mandar registrar no inventário
    # o risco cuja medida não pôde ser adotada de imediato.
    declarados = _nr1_declared_findings(
        context, campaign_id, criteria, progress, total
    )
    if not rows and not declarados:
        declarados = _nr1_campaign_level_declaration(progress)
        # A declaração de campanha não tem dimensão nem unidade, e o inventário
        # exige as duas. Ela vive na resposta e no aviso, não como linha.
        declarados_para_gravar: list[dict] = []
    else:
        declarados_para_gravar = [
            {
                "unit_id": achado["unit_id"],
                "dimension_id": achado["dimension_id"],
                "nr1_factor": achado["nr1_factor"],
                "cohort_size": None,
                "mean_score": None,
                "severity": None,
                "probability": None,
                "risk_level": nr1_compliance.UNCLASSIFIABLE_LEVEL,
                "risk_classification": nr1_compliance.UNCLASSIFIABLE_LEVEL,
                "rationale": achado["escalation"],
                "suppression_gate": achado["gate"],
                "escalation_note": achado["escalation"],
                "exposed_workers": achado["declared_headcount"] or 0,
            }
            for achado in declarados
        ]

    graded = nr1_compliance.grade_all(
        (nr1_compliance.DimensionScore(**row) for row in rows), criteria
    )
    stored = TENANT_STORE.nr1_store_inventory(
        organization_id=organization_id,
        membership_id=context.membership_id,
        campaign_id=campaign_id,
        graded_rows=[
            {
                "unit_id": risk.unit_id,
                "dimension_id": risk.dimension_id,
                "nr1_factor": risk.nr1_factor,
                "cohort_size": risk.cohort_size,
                "mean_score": risk.mean_score,
                "severity": risk.severity,
                "probability": risk.probability,
                "risk_level": risk.risk_level,
                "rationale": risk.rationale,
                # 1.5.7.3.2 "d", "e", "f" and "g"
                "selected_consequence": risk.consequence,
                "possible_harms": list(risk.consequences_considered),
                "exposed_workers": risk.exposed_workers,
                "measure_efficacy": risk.measure_efficacy,
                "exposure_level": risk.exposure_level,
                "risk_classification": risk.risk_level,
            }
            for risk in graded
        ]
        # As linhas declaradas entram no MESMO documento, e não num anexo.
        # Separá-las produziria um inventário que parece completo e uma folha à
        # parte que ninguém abre — que é exatamente como se perde a informação
        # de que um setor não foi avaliado.
        + declarados_para_gravar,
        review_interval_months=_nr1_review_interval_months(context),
    )

    # Os dois documentos obrigatórios do PGR (1.5.7.1) nascem juntos. Gerar o
    # inventário e deixar o plano para depois é o estado em que a empresa fica
    # com metade do exigido — que foi exatamente o estado do produto até aqui,
    # porque o rascunho voltava na resposta e não era gravado em lugar nenhum.
    seed = nr1_compliance.action_plan_seed(graded)
    try:
        plan_rows = TENANT_STORE.nr1_generate_action_plan(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
            seed_rows=seed,
        )
    except Exception:
        # O inventário já foi gravado e vale por si. Falhar a resposta inteira
        # aqui faria a empresa perder o documento que deu certo por causa do que
        # ainda pode ser refeito pelo endpoint de plano.
        LOGGER.exception("Inventory stored but action plan seeding failed")
        plan_rows = 0

    _record_tenant_success(
        context, "nr1.inventory.generate", "assessment_campaign", campaign_id,
        {"result_count": stored, "action_plan_rows": plan_rows},
    )
    return {
        "campaign_id": campaign_id,
        "inventory_rows": stored,
        # Quantas linhas do inventário são declaração de insuficiência, e não
        # classificação. Separadas na RESPOSTA — nunca no documento — para que a
        # tela possa dizer "12 riscos classificados, 3 recortes sem coorte" em
        # vez de anunciar 15 riscos avaliados, que seria falso.
        "declared_rows": len(declarados_para_gravar),
        "declared": declarados,
        "action_plan_rows": plan_rows,
        "action_plan_seed": seed,
    }


@app.get("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/inventory")
async def list_nr1_inventory(organization_id: str, campaign_id: str, request: Request):
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    try:
        inventory = TENANT_STORE.nr1_list_inventory(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
        progress = TENANT_STORE.nr1_campaign_progress(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except ValueError:
        raise HTTPException(status_code=404, detail="campanha não encontrada")

    # A declaração da campanha inteira não é linha do inventário, e não pode
    # ser: `dimension_id` é NOT NULL, e insuficiência do conjunto não tem
    # dimensão. Mas ela precisa chegar a quem lê o documento — senão a campanha
    # que não fechou produz uma folha em branco, que é exatamente a leitura
    # ("não há risco aqui") que este módulo inteiro existe para impedir.
    #
    # Vai ao lado das linhas, e não no lugar delas: quando há classificação, as
    # duas coisas convivem.
    declaracao_da_campanha = (
        _nr1_campaign_level_declaration(progress) if not inventory else []
    )

    criteria = _nr1_criteria_for(context)
    _record_tenant_success(
        context, "nr1.inventory.read", "assessment_campaign", campaign_id,
        {"result_count": len(inventory)},
    )
    return {
        "campaign_id": campaign_id,
        "inventory": inventory,
        "declared_campaign": declaracao_da_campanha,
        # O cabeçalho que um documento de conformidade precisa ter para ser
        # lido fora da tela: quem, quando, sobre quantos, e sob qual régua.
        "campaign": {
            "status": progress.get("status"),
            "target_headcount": progress.get("target_headcount"),
            "responses": progress.get("responses"),
            "substantive_responses": progress.get("substantive_responses"),
            "invited": progress.get("invited"),
            # Título, período e janela vivem na campanha, não no progresso —
            # que só conta adesão. Sem eles o documento sai sem saber a que
            # período de referência se refere, que é a primeira coisa que um
            # auditor procura.
            **_nr1_campaign_header(context, campaign_id),
        },
        "criteria": {
            "version": criteria.version,
            "source": criteria.source,
            "published": criteria.source != "froid-default",
        },
    }


# ---------------------------------------------------------------------------
# Plano de ação — o segundo documento obrigatório do PGR (1.5.7.1 "b").
#
# Até aqui o FROID entregava um dos dois. action_plan_seed() devolvia um
# rascunho no corpo da resposta de geração do inventário e ele evaporava: não
# havia rota que escrevesse psychosocial_action_plan, embora a tabela, as
# políticas de RLS, os grants ao froid_runtime e a permissão
# nr1.action_plan.manage existissem desde a migration 010.
# ---------------------------------------------------------------------------

_ACTION_PLAN_STATUSES = frozenset({"planned", "in_progress", "done", "cancelled"})

# As CHECK da migration 026 foram escritas para o gestor ler, mas o psycopg
# entrega a mensagem do Postgres embrulhada em ruído. O mapa traduz o nome da
# restrição violada na frase que explica QUAL exigência da norma foi tocada —
# porque "violates check constraint" não ensina ninguém a preencher o documento.
_ACTION_PLAN_CONSTRAINT_MESSAGES = {
    "psychosocial_action_plan_done_needs_implementation": (
        "medida não pode ser concluída sem a data em que foi implementada "
        "(NR-1 1.5.5.3.1)"
    ),
    "psychosocial_action_plan_done_needs_schedule": (
        "medida não pode ser concluída sem responsável e sem prazo "
        "(NR-1 1.5.5.2.2)"
    ),
    "psychosocial_action_plan_done_needs_monitoring": (
        "medida não pode ser concluída sem forma de acompanhamento e de "
        "aferição de resultados (NR-1 1.5.5.2.2)"
    ),
    "psychosocial_action_plan_measure_not_blank": (
        "descreva a medida antes de tirá-la do rascunho"
    ),
    "psychosocial_action_plan_cancel_needs_reason": (
        "cancelar uma medida planejada para um risco identificado exige "
        "justificativa escrita; sem ela o cancelamento é indistinguível de "
        "esquecimento"
    ),
    "psychosocial_action_plan_efficacy_after_implementation": (
        "não se julga a eficácia de medida que ainda não foi implementada — a "
        "eficácia entra no cálculo da probabilidade do risco (NR-1 1.5.4.4.5.3)"
    ),
    "psychosocial_action_plan_review_pairs_with_verdict": (
        "o veredito de eficácia e a data da revisão andam juntos"
    ),
    "psychosocial_action_plan_plan_action_check": (
        "a medida é introduzida, aprimorada ou mantida (NR-1 1.5.5.2.1)"
    ),
}


def _nr1_constraint_message(exc: Exception) -> str:
    texto = str(exc)
    for nome, mensagem in _ACTION_PLAN_CONSTRAINT_MESSAGES.items():
        if nome in texto:
            return mensagem
    if "nao pode ser apagada" in texto:
        return (
            "a data de implementação registrada não pode ser apagada "
            "(NR-1 1.5.5.3.1)"
        )
    if "nao muda de risco" in texto:
        return "uma medida não muda de risco; cancele esta e abra outra no risco correto"
    return "não foi possível atualizar a medida"


def _nr1_parse_date(valor: Any, rotulo: str):
    if valor in (None, ""):
        return None
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"{rotulo} em formato inválido; use AAAA-MM-DD"
        )


def _nr1_parse_datetime(valor: Any, rotulo: str):
    """Aceita data ou data-hora, e assume UTC quando o fuso não vem.

    Um cronograma preenchido por gestor chega com 'AAAA-MM-DD' na maior parte
    das vezes; recusar isso seria fazer o documento depender do formato em vez do
    fato.
    """
    if valor in (None, ""):
        return None
    texto = str(valor).strip().replace("Z", "+00:00")
    try:
        quando = datetime.fromisoformat(texto)
    except ValueError:
        try:
            quando = datetime.combine(
                date.fromisoformat(texto[:10]), datetime.min.time()
            )
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{rotulo} em formato inválido")
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    return quando


def _nr1_action_plan_summary(itens: List[dict]) -> dict:
    """O que um gestor precisa ver antes de abrir o documento inteiro.

    `overdue` conta medida com prazo vencido que ainda não foi implementada — é
    a métrica que a fiscalização transforma em pergunta, porque o prazo foi a
    própria organização que escreveu (1.5.5.2.2).

    `awaiting_residual_review` conta medida implementada cuja reavaliação de
    risco residual ainda não foi feita. É a alínea "a" de 1.5.4.4.6 em aberto: a
    obrigação nasceu no dia da implementação e segue pendente.
    """
    hoje = datetime.now(timezone.utc).date()
    por_status: Dict[str, int] = {status: 0 for status in sorted(_ACTION_PLAN_STATUSES)}
    vencidas = 0
    aguardando_residual = 0
    for item in itens:
        status = str(item.get("status") or "planned")
        por_status[status] = por_status.get(status, 0) + 1
        prazo = item.get("due_date")
        if (
            prazo is not None
            and item.get("implemented_at") is None
            and status not in ("done", "cancelled")
            and prazo < hoje
        ):
            vencidas += 1
        if item.get("implemented_at") is not None and item.get("effectiveness") is None:
            aguardando_residual += 1
    return {
        "total": len(itens),
        "by_status": por_status,
        "overdue": vencidas,
        "awaiting_residual_review": aguardando_residual,
    }


def _nr1_seed_rows_for_campaign(
    context, organization_id: str, campaign_id: str
) -> List[dict]:
    """Rascunhos de medida derivados do inventário desta campanha.

    Reaproveita a mesma agregação que o painel usa, e portanto os mesmos dois
    portões: se a coorte não libera resultado, não há inventário e não há plano.
    """
    rows = TENANT_STORE.nr1_dimension_scores(
        organization_id=organization_id,
        membership_id=context.membership_id,
        campaign_id=campaign_id,
    )
    if not rows:
        return []
    criteria = _nr1_criteria_for(context)
    graded = nr1_compliance.grade_all(
        (nr1_compliance.DimensionScore(**row) for row in rows), criteria
    )
    return nr1_compliance.action_plan_seed(graded)


@app.get("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/action-plan")
async def list_nr1_action_plan(organization_id: str, campaign_id: str, request: Request):
    """O plano de ação como documento, na ordem de prioridade de 1.5.5.2.1.1."""
    context = _require_enterprise_context(
        request, organization_id, "nr1.aggregate.read"
    )
    try:
        itens = TENANT_STORE.nr1_list_action_plan(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
        )
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    _record_tenant_success(
        context, "nr1.action_plan.read", "assessment_campaign", campaign_id,
        {"result_count": len(itens)},
    )
    return {
        "campaign_id": campaign_id,
        "action_plan": itens,
        "summary": _nr1_action_plan_summary(itens),
    }


@app.post("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/action-plan")
async def generate_nr1_action_plan(
    organization_id: str, campaign_id: str, request: Request
):
    """Abre as linhas de plano que faltam para os riscos já inventariados.

    Idempotente: só cria medida para risco que ainda não tem nenhuma viva, então
    chamar de novo depois de a empresa ter preenchido o plano não sobrescreve
    trabalho feito.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.action_plan.manage"
    )
    try:
        seed = _nr1_seed_rows_for_campaign(context, organization_id, campaign_id)
        if not seed:
            raise HTTPException(
                status_code=409,
                detail=(
                    "não há inventário liberado para esta campanha; gere o "
                    "inventário antes do plano de ação"
                ),
            )
        criadas = TENANT_STORE.nr1_generate_action_plan(
            organization_id=organization_id,
            membership_id=context.membership_id,
            campaign_id=campaign_id,
            seed_rows=seed,
        )
    except HTTPException:
        raise
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to generate NR-1 action plan")
        raise HTTPException(status_code=400, detail="não foi possível gerar o plano de ação")
    _record_tenant_success(
        context, "nr1.action_plan.generate", "assessment_campaign", campaign_id,
        {"result_count": criadas},
    )
    return {"campaign_id": campaign_id, "created": criadas, "seeded_risks": len(seed)}


@app.get("/api/organizations/{organization_id}/nr1/responsibles")
async def list_nr1_responsibles(organization_id: str, request: Request):
    """Quem pode ser nomeado responsável por uma medida (NR-1 1.5.5.2.2).

    Rota própria porque quem preenche o plano é o `compliance_manager`, que não
    tem `members.manage` e portanto não alcança a listagem administrativa de
    membros. Devolve o mínimo — identificação da associação e nome de exibição —
    e nada mais: é a lista de quem pode assinar uma medida, não um diretório.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.action_plan.manage"
    )
    try:
        pessoas = TENANT_STORE.nr1_list_responsibles(organization_id)
    except Exception:
        LOGGER.exception("Unable to list NR-1 responsibles")
        raise HTTPException(status_code=400, detail="não foi possível listar os responsáveis")
    _record_tenant_success(
        context, "nr1.action_plan.responsibles", "organization", organization_id,
        {"result_count": len(pessoas)},
    )
    return {"responsibles": pessoas}


@app.post("/api/organizations/{organization_id}/nr1/action-plan/items", status_code=201)
async def add_nr1_action_plan_item(organization_id: str, request: Request):
    """Segunda medida para o mesmo risco.

    A hierarquia de 1.5.5.1.2 frequentemente exige combinar: uma medida coletiva
    e, enquanto ela não fica de pé, uma administrativa em caráter complementar. A
    norma não limita o plano a uma medida por risco.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.action_plan.manage"
    )
    body = await request.json()
    inventory_id = str(body.get("inventory_id") or "").strip()
    measure = str(body.get("measure") or "").strip()
    measure_type = str(body.get("measure_type") or "").strip()
    plan_action = str(body.get("plan_action") or "introduce").strip()
    if not inventory_id or not measure:
        raise HTTPException(status_code=400, detail="risco e descrição da medida são obrigatórios")
    if measure_type not in nr1_compliance.MEASURE_HIERARCHY:
        raise HTTPException(status_code=400, detail="tipo de medida fora da hierarquia da NR-1")
    if plan_action not in nr1_compliance.PLAN_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail="a medida é introduzida, aprimorada ou mantida (NR-1 1.5.5.2.1)",
        )
    try:
        item_id = TENANT_STORE.nr1_add_action_plan_item(
            organization_id=organization_id,
            membership_id=context.membership_id,
            inventory_id=inventory_id,
            measure=measure[:4000],
            measure_type=measure_type,
            plan_action=plan_action,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="risco não encontrado no inventário")
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception:
        LOGGER.exception("Unable to add NR-1 action plan item")
        raise HTTPException(status_code=400, detail="não foi possível acrescentar a medida")
    _record_tenant_success(
        context, "nr1.action_plan.item.create", "psychosocial_action_plan", item_id,
        {"measure_type": measure_type, "plan_action": plan_action},
    )
    return {"item_id": item_id, "inventory_id": inventory_id}


@app.patch("/api/organizations/{organization_id}/nr1/action-plan/items/{item_id}")
async def update_nr1_action_plan_item(
    organization_id: str, item_id: str, request: Request
):
    """Preenche o cronograma, registra a implementação e o veredito de eficácia.

    As garantias que importam não estão aqui: estão em CHECK e trigger na
    migration 026, onde nenhum caminho de código as contorna — concluir sem data
    de implementação, sem responsável, sem prazo ou sem forma de aferição é
    recusado pelo banco, e a data de implementação registrada não pode ser
    apagada. O que se faz aqui é recusar cedo, com mensagem melhor.
    """
    context = _require_enterprise_context(
        request, organization_id, "nr1.action_plan.manage"
    )
    body = await request.json()
    campos: Dict[str, Any] = {}

    if "measure" in body:
        campos["measure"] = str(body.get("measure") or "")[:4000]
    if "measure_type" in body:
        valor = str(body.get("measure_type") or "").strip()
        if valor not in nr1_compliance.MEASURE_HIERARCHY:
            raise HTTPException(status_code=400, detail="tipo de medida fora da hierarquia da NR-1")
        campos["measure_type"] = valor
    if "plan_action" in body:
        valor = str(body.get("plan_action") or "").strip()
        if valor not in nr1_compliance.PLAN_ACTIONS:
            raise HTTPException(
                status_code=400,
                detail="a medida é introduzida, aprimorada ou mantida (NR-1 1.5.5.2.1)",
            )
        campos["plan_action"] = valor
    if "status" in body:
        valor = str(body.get("status") or "").strip()
        if valor not in _ACTION_PLAN_STATUSES:
            raise HTTPException(status_code=400, detail="situação da medida inválida")
        campos["status"] = valor
    if "responsible_membership_id" in body:
        valor = body.get("responsible_membership_id")
        campos["responsible_membership_id"] = str(valor).strip() or None if valor else None
    for texto in ("evidence", "monitoring_method", "result_measurement"):
        if texto in body:
            campos[texto] = str(body.get(texto) or "")[:4000]
    if "due_date" in body:
        campos["due_date"] = _nr1_parse_date(body.get("due_date"), "prazo")
    if "implemented_at" in body:
        quando = _nr1_parse_datetime(body.get("implemented_at"), "data de implementação")
        if quando is not None and quando > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="não se registra implementação no futuro; o registro é de fato ocorrido (NR-1 1.5.5.3.1)",
            )
        campos["implemented_at"] = quando
    if "effectiveness" in body:
        valor = body.get("effectiveness")
        if valor is not None:
            valor = str(valor).strip()
            if valor not in nr1_compliance.VALID_EFFICACY:
                raise HTTPException(status_code=400, detail="veredito de eficácia inválido")
        campos["effectiveness"] = valor
        # Veredito e data andam juntos: o banco recusa um sem o outro, e deixar
        # o cliente descobrir isso por erro de constraint seria pior.
        if "effectiveness_reviewed_at" not in body:
            campos["effectiveness_reviewed_at"] = (
                datetime.now(timezone.utc) if valor else None
            )
    if "effectiveness_reviewed_at" in body:
        campos["effectiveness_reviewed_at"] = _nr1_parse_datetime(
            body.get("effectiveness_reviewed_at"), "data da revisão de eficácia"
        )

    if not campos:
        raise HTTPException(status_code=400, detail="nada a atualizar")
    try:
        resultado = TENANT_STORE.nr1_update_action_plan_item(
            organization_id=organization_id,
            membership_id=context.membership_id,
            item_id=item_id,
            fields=campos,
        )
    except ValueError as exc:
        if str(exc) == "action_plan_item_not_found":
            raise HTTPException(status_code=404, detail="medida não encontrada")
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError:
        raise HTTPException(status_code=409, detail="módulo NR-1 requer persistência dual")
    except Exception as exc:
        # As mensagens das CHECK da 026 são escritas para o gestor ler; repassar
        # a do banco ajuda mais que "não foi possível atualizar".
        LOGGER.exception("Unable to update NR-1 action plan item")
        raise HTTPException(status_code=400, detail=_nr1_constraint_message(exc))
    _record_tenant_success(
        context, "nr1.action_plan.item.update", "psychosocial_action_plan", item_id,
        {"fields": resultado.get("updated_fields")},
    )
    return resultado


@app.get("/api/organizations/{organization_id}/wallet")
async def get_organization_wallet(organization_id: str, request: Request):
    context = _require_tenant_management_context(
        request, organization_id, "credits.read"
    )
    try:
        wallet = TENANT_STORE.wallet_status(
            organization_id=organization_id,
            membership_id=context.membership_id,
        )
        _record_tenant_success(context, "wallet.read", "organization_wallet", organization_id)
        return wallet
    except ValueError:
        raise HTTPException(status_code=404, detail="carteira organizacional não encontrada")
    except Exception:
        LOGGER.exception("Unable to read organization wallet")
        raise HTTPException(status_code=503, detail="carteira organizacional indisponível")


@app.post("/api/organizations/{organization_id}/wallet/activate")
async def activate_organization_wallet(organization_id: str, request: Request):
    context = _require_tenant_management_context(
        request, organization_id, "credits.manage"
    )
    body = await request.json()
    if "expected_legacy_balance" not in body:
        raise HTTPException(status_code=400, detail="saldo legado esperado obrigatório")
    expected_balance = _local_int(body.get("expected_legacy_balance"))
    if expected_balance < 0:
        raise HTTPException(status_code=400, detail="saldo legado esperado inválido")
    try:
        result = TENANT_STORE.activate_shared_wallet(
            organization_id=organization_id,
            membership_id=context.membership_id,
            actor_user_id=context.user_id,
            expected_legacy_balance=expected_balance,
        )
    except Exception as exc:
        message = str(exc).lower()
        if "reconciliation" in message:
            raise HTTPException(
                status_code=409,
                detail="saldo legado diverge da carteira; reconciliação obrigatória",
            )
        LOGGER.exception("Unable to activate organization wallet")
        raise HTTPException(status_code=503, detail="falha ao ativar carteira organizacional")
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=context.user_id,
        action="wallet.activate",
        resource_type="organization_wallet",
        resource_id=organization_id,
        metadata={"expected_legacy_balance": expected_balance, **result},
    )
    return {"status": "ok", **result}


@app.get("/api/organizations/{organization_id}/usage")
async def get_organization_usage(organization_id: str, request: Request):
    """Relatório consolidado da clínica para o gestor.

    Exige ``reports.read_all`` (owner/administrator/supervisor): o relatório
    expõe o consumo e a carteira de pacientes de TODA a equipe, então um
    profissional comum não pode lê-lo.
    """
    context = _require_tenant_management_context(
        request, organization_id, "reports.read_all"
    )
    try:
        report = TENANT_STORE.organization_usage_report(
            organization_id=organization_id,
            membership_id=context.membership_id,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="carteira organizacional não encontrada")
    except Exception:
        LOGGER.exception("Unable to build organization usage report")
        raise HTTPException(status_code=503, detail="relatório organizacional indisponível")
    _record_tenant_success(context, "usage.read", "organization", organization_id)
    return report


@app.put("/api/organizations/{organization_id}/members/{target_membership_id}/quota")
async def set_organization_member_quota(
    organization_id: str, target_membership_id: str, request: Request
):
    """Define ou remove a cota individual de um profissional.

    Corpo: ``{"quota_sessions": 20}`` para definir; ``{"quota_sessions": null}``
    para remover e devolver o profissional ao pool livre.
    """
    context = _require_tenant_management_context(
        request, organization_id, "credits.manage"
    )
    body = await request.json()
    if "quota_sessions" not in body:
        raise HTTPException(status_code=400, detail="quota_sessions obrigatório")
    raw_quota = body.get("quota_sessions")
    quota = None
    if raw_quota is not None:
        quota = _local_int(raw_quota)
        if quota < 0:
            raise HTTPException(status_code=400, detail="cota não pode ser negativa")
    try:
        result = TENANT_STORE.set_member_quota(
            organization_id=organization_id,
            membership_id=context.membership_id,
            actor_user_id=context.user_id,
            target_membership_id=target_membership_id,
            quota_sessions=quota,
        )
    except Exception as exc:
        message = str(exc).lower()
        if "target membership not in organization" in message:
            raise HTTPException(status_code=404, detail="profissional não pertence à organização")
        if "role cannot manage member quotas" in message:
            raise HTTPException(status_code=403, detail="perfil não pode gerenciar cotas")
        LOGGER.exception("Unable to set member quota")
        raise HTTPException(status_code=503, detail="falha ao definir cota do profissional")
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=context.user_id,
        action="member_quota.remove" if result["removed"] else "member_quota.set",
        resource_type="organization_member_quota",
        resource_id=target_membership_id,
        metadata=result,
    )
    return {"status": "ok", **result}


@app.put("/api/organizations/{organization_id}/report-visibility")
async def set_organization_report_visibility(organization_id: str, request: Request):
    """Define quem, dentro da clínica, enxerga os relatórios dos pacientes.

    ``restricted`` (padrão): supervisor/gestor veem a clínica inteira; o
    profissional vê apenas o paciente atribuído a ele.
    ``clinic_wide``: todos os profissionais da clínica veem os relatórios da
    clínica, para análise conjunta de conduta.

    Prerrogativa do gestor (``credits.manage`` = owner/administrator). Amplia o
    acesso a dado sensível de saúde, então fica registrado em auditoria.
    """
    context = _require_tenant_management_context(
        request, organization_id, "credits.manage"
    )
    body = await request.json()
    visibility = str(body.get("report_visibility") or "").strip().lower()
    if visibility not in {"restricted", "clinic_wide"}:
        raise HTTPException(
            status_code=400,
            detail="report_visibility deve ser 'restricted' ou 'clinic_wide'",
        )
    try:
        result = TENANT_STORE.set_report_visibility(
            organization_id=organization_id,
            membership_id=context.membership_id,
            actor_user_id=context.user_id,
            visibility=visibility,
        )
    except Exception as exc:
        if "role cannot manage report visibility" in str(exc).lower():
            raise HTTPException(status_code=403, detail="perfil não pode alterar a visibilidade")
        LOGGER.exception("Unable to set report visibility")
        raise HTTPException(status_code=503, detail="falha ao definir a visibilidade")
    TENANT_STORE.record_access_audit(
        organization_id=organization_id,
        actor_user_id=context.user_id,
        action="report_visibility.set",
        resource_type="organization",
        resource_id=organization_id,
        metadata=result,
    )
    return {"status": "ok", **result}


@app.get("/api/organizations/{organization_id}/audit-events")
async def list_organization_audit_events(
    organization_id: str, request: Request, limit: int = 100
):
    context = _require_tenant_management_context(
        request, organization_id, "audit.read"
    )
    try:
        events = TENANT_STORE.list_audit_events(
            organization_id=organization_id,
            membership_id=context.membership_id,
            limit=limit,
        )
    except Exception:
        LOGGER.exception("Unable to list organization audit events")
        raise HTTPException(status_code=503, detail="trilha de auditoria indisponível")
    _record_tenant_success(
        context, "audit.read", "audit_event",
        metadata={"result_count": len(events)},
    )
    return {"events": events}


@app.post("/api/audit/client-event")
async def record_client_audit_event(request: Request):
    context = _tenant_context_from_request(request)
    _require_active_subscription_for_context(context)
    if context is None:
        raise HTTPException(status_code=409, detail="contexto organizacional ausente")
    body = await request.json()
    action = str(body.get("action") or "").strip().lower()
    allowed_actions = {"receipt.export", "report.export", "report.share"}
    if action not in allowed_actions:
        raise HTTPException(status_code=400, detail="evento de auditoria inválido")
    permitted_roles = (
        {"owner", "administrator", "professional"}
        if action == "receipt.export"
        else {"owner", "administrator", "supervisor", "professional"}
    )
    if not (set(context.roles) & permitted_roles):
        raise HTTPException(status_code=403, detail="papel sem permissão para exportar")
    resource_id = str(body.get("resource_id") or "").strip()[:200]
    if not resource_id:
        raise HTTPException(status_code=400, detail="recurso auditado obrigatório")
    TENANT_STORE.record_access_audit(
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        action=action,
        resource_type=action.split(".", 1)[0],
        resource_id=resource_id,
        metadata={"source": "web", "surface": str(body.get("surface") or "")[:80]},
    )
    return {"status": "recorded"}


@app.get("/api/google-calendar/status")
async def google_calendar_status(request: Request):
    user = _require_current_user(request)
    email = _normalize_email(user.get("email") or "")
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email)
    return {
        "configured": _calendar_configured(),
        **_calendar_connection_public(connection),
        "redirect_uri": _public_google_calendar_redirect_uri(str(request.base_url).rstrip("/")),
    }


@app.post("/api/google-calendar/connect")
async def google_calendar_connect(request: Request):
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    if not _calendar_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Configure GOOGLE_CALENDAR_CLIENT_ID e "
                "GOOGLE_CALENDAR_CLIENT_SECRET no servidor"
            ),
        )
    if not TOKEN_CIPHER:
        raise HTTPException(
            status_code=503,
            detail="Configure FROID_TOKEN_ENCRYPTION_KEYS antes de conectar o Google",
        )
    body = await request.json()
    email = _normalize_email(user.get("email") or "")
    redirect_uri = _public_google_calendar_redirect_uri(body.get("base_url") or "")
    return {
        "auth_url": _calendar_auth_url(email, redirect_uri),
        "redirect_uri": redirect_uri,
    }


@app.get("/api/google-calendar/callback")
async def google_calendar_callback(code: str = "", state: str = "", error: str = ""):
    app_base = _public_app_base_url("")
    if error:
        return RedirectResponse(f"{app_base}/#/settings?calendar=error")
    oauth_state = GOOGLE_CALENDAR_OAUTH_STATES.pop(state, None)
    if not code or not oauth_state:
        return RedirectResponse(f"{app_base}/#/settings?calendar=invalid_state")
    email = _normalize_email(oauth_state.get("email") or "")
    redirect_uri = str(oauth_state.get("redirect_uri") or _public_google_calendar_redirect_uri(""))
    token_payload = await _exchange_google_calendar_code(code, redirect_uri)
    now = datetime.now(timezone.utc)
    previous = GOOGLE_CALENDAR_CONNECTIONS.get(email) or {}
    access_token = token_payload.get("access_token") or ""
    userinfo = await _google_userinfo(access_token) if access_token else {}
    connection = {
        **previous,
        "professional_email": email,
        "google_email": userinfo.get("email") or previous.get("google_email") or email,
        "access_token": access_token,
        "refresh_token": token_payload.get("refresh_token") or previous.get("refresh_token") or "",
        "scope": token_payload.get("scope") or "",
        "token_type": token_payload.get("token_type") or "Bearer",
        "expires_at": now.timestamp() + int(token_payload.get("expires_in") or 0),
        "connected_at": previous.get("connected_at") or now.isoformat(),
        "updated_at": now.isoformat(),
    }
    GOOGLE_CALENDAR_CONNECTIONS[email] = connection
    _save_identity_state()
    return RedirectResponse(f"{app_base}/#/settings?calendar=connected")


@app.post("/api/google-calendar/disconnect")
async def google_calendar_disconnect(request: Request):
    user = _require_current_user(request)
    email = _normalize_email(user.get("email") or "")
    GOOGLE_CALENDAR_CONNECTIONS.pop(email, None)
    _save_identity_state()
    return {"connected": False}


@app.get("/api/google-calendar/calendars")
async def google_calendar_calendars(request: Request):
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    email = _normalize_email(user.get("email") or "")
    token = await _calendar_access_token(email)
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email) or {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            params={"minAccessRole": "owner", "maxResults": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Falha ao listar agendas Google: {response.text[:300]}")
    payload = response.json()
    selected_id = _selected_calendar_id(connection)
    calendars = []
    for item in payload.get("items", []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        summary = item.get("summary") or item.get("id") or "Agenda"
        calendars.append(
            {
                "id": item.get("id"),
                "summary": summary,
                "primary": bool(item.get("primary")),
                "accessRole": item.get("accessRole") or "",
                "backgroundColor": item.get("backgroundColor") or "",
                "selected": str(item.get("id") or "") == selected_id,
                "recommended": _is_recommended_froid_calendar(summary),
            }
        )
    recommended = next(
        (calendar["id"] for calendar in calendars if calendar["recommended"]),
        "",
    )
    return {
        "selected_calendar_id": selected_id,
        "recommended_calendar_id": recommended,
        "items": calendars,
    }


@app.post("/api/google-calendar/select-calendar")
async def google_calendar_select_calendar(request: Request):
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    email = _normalize_email(user.get("email") or "")
    body = await request.json()
    calendar_id = str(body.get("calendar_id") or "").strip()
    if not calendar_id:
        raise HTTPException(status_code=400, detail="calendar_id obrigatório")
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email)
    if not connection:
        raise HTTPException(status_code=404, detail="Google Agenda não conectado")
    token = await _calendar_access_token(email)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList/"
            f"{quote(calendar_id, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
        )
    calendar = response.json() if response.status_code < 400 else {}
    if (
        response.status_code >= 400
        or not isinstance(calendar, dict)
        or calendar.get("accessRole") != "owner"
    ):
        raise HTTPException(
            status_code=403,
            detail="Selecione uma agenda Google própria autorizada para o FROID",
        )
    verified_summary = str(
        calendar.get("summary") or calendar.get("id") or calendar_id
    ).strip()
    connection.update(
        {
            "selected_calendar_id": calendar_id,
            "selected_calendar_summary": verified_summary,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    GOOGLE_CALENDAR_CONNECTIONS[email] = connection
    _save_identity_state()
    return _calendar_connection_public(connection)


@app.get("/api/google-calendar/events")
async def google_calendar_events(
    request: Request,
    max_results: int = 30,
    time_min: str = "",
    time_max: str = "",
    calendar_id: str = "",
):
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    email = _normalize_email(user.get("email") or "")
    token = await _calendar_access_token(email)
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email) or {}
    selected_calendar = _selected_calendar_id(connection, calendar_id or "primary")
    params = {
        "timeMin": time_min or datetime.now(timezone.utc).isoformat(),
        "maxResults": max(1, min(max_results, 100)),
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    if time_max:
        params["timeMax"] = time_max
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(selected_calendar, safe='')}/events",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Falha ao ler Google Agenda: {response.text[:300]}")
    payload = response.json()
    return {
        "items": [
            {
                "id": item.get("id"),
                "summary": item.get("summary") or "(sem titulo)",
                "start": item.get("start") or {},
                "end": item.get("end") or {},
                "htmlLink": item.get("htmlLink") or "",
            }
            for item in payload.get("items", [])
            if isinstance(item, dict)
        ]
    }


@app.post("/api/google-calendar/events")
async def google_calendar_create_event(request: Request):
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    email = _normalize_email(user.get("email") or "")
    token = await _calendar_access_token(email)
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email) or {}
    body = await request.json()
    summary = str(body.get("summary") or "Sessao FROID").strip()
    start = str(body.get("start") or "").strip()
    end = str(body.get("end") or "").strip()
    if not start or not end:
        raise HTTPException(status_code=400, detail="Informe start e end em ISO 8601")
    event = {
        "summary": summary,
        "description": str(body.get("description") or "").strip(),
        "start": {"dateTime": start, "timeZone": body.get("timeZone") or "America/Sao_Paulo"},
        "end": {"dateTime": end, "timeZone": body.get("timeZone") or "America/Sao_Paulo"},
    }
    attendees = body.get("attendees")
    if isinstance(attendees, list):
        event["attendees"] = [
            {"email": _normalize_email(item.get("email") if isinstance(item, dict) else item)}
            for item in attendees
            if _normalize_email(item.get("email") if isinstance(item, dict) else item)
        ]
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(_selected_calendar_id(connection, body.get('calendar_id') or 'primary'), safe='')}/events",
            params={"sendUpdates": "all" if event.get("attendees") else "none"},
            headers={"Authorization": f"Bearer {token}"},
            json=event,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Falha ao criar evento Google Agenda: {response.text[:300]}")
    return response.json()


@app.patch("/api/google-calendar/events/{event_id}")
async def google_calendar_update_event(event_id: str, request: Request):
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    email = _normalize_email(user.get("email") or "")
    token = await _calendar_access_token(email)
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email) or {}
    body = await request.json()
    calendar_id = _selected_calendar_id(connection, body.get("calendar_id") or "primary")
    allowed = {key: body[key] for key in ["summary", "description", "start", "end", "attendees"] if key in body}
    if not allowed:
        raise HTTPException(status_code=400, detail="Informe campos para atualizar")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.patch(
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
            params={"sendUpdates": "all" if allowed.get("attendees") else "none"},
            headers={"Authorization": f"Bearer {token}"},
            json=allowed,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Falha ao alterar evento Google Agenda: {response.text[:300]}")
    return response.json()


@app.delete("/api/google-calendar/events/{event_id}")
async def google_calendar_delete_event(event_id: str, request: Request, calendar_id: str = ""):
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    email = _normalize_email(user.get("email") or "")
    token = await _calendar_access_token(email)
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email) or {}
    selected_calendar = _selected_calendar_id(connection, calendar_id or "primary")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.delete(
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(selected_calendar, safe='')}/events/{quote(event_id, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code not in {200, 204}:
        raise HTTPException(status_code=400, detail=f"Falha ao excluir evento Google Agenda: {response.text[:300]}")
    return {"deleted": True, "event_id": event_id}


@app.get("/api/access/plans")
async def access_plans(currency: str = ""):
    selected_currency = _normalize_stripe_currency(currency) or _normalize_stripe_currency(STRIPE_CURRENCY) or "usd"
    return {
        "currency": selected_currency,
        "plans": [
            _plan_public(plan, selected_currency)
            for plan in FROID_ACCESS_PLANS.values()
        ],
    }


@app.get("/api/professional/profile")
async def get_professional_profile(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")

    email = _normalize_email(user.get("email") or "")
    profile = PROFESSIONAL_PROFILES.get(email)
    return {
        "has_profile": bool(profile),
        "profile": profile,
        "access_status": _professional_access_status(email),
    }


@app.post("/api/professional/legal-acceptances")
async def renew_professional_legal_acceptances(request: Request):
    """Record the current legal documents without rewriting the professional profile."""
    user = _require_current_user(request)
    context = _tenant_context_from_request(request)
    if context is None:
        raise HTTPException(status_code=409, detail="contexto organizacional ausente")
    if not ({"owner", "administrator"} & set(context.roles)):
        raise HTTPException(status_code=403, detail="papel sem permissão para aceitar contratação")
    email = _normalize_email(user.get("email") or "")
    profile = PROFESSIONAL_PROFILES.get(email)
    if not isinstance(profile, dict):
        raise HTTPException(status_code=409, detail="cadastro profissional ausente")
    body = await request.json()
    account_type = str(profile.get("account_type") or "individual")
    legal_acceptances = _validated_legal_acceptances(
        body.get("legal_acceptances"),
        account_type,
        required=True,
    )
    _record_legal_documents(
        request=request,
        subject_reference=email,
        subject_kind=("organization" if account_type == "organization" else "professional"),
        organization_id=context.organization_id,
        acceptances=legal_acceptances,
        context="professional_legal_renewal",
    )
    profile["legal_acceptances"] = legal_acceptances
    profile["updated_at"] = _utc_now_iso()
    PROFESSIONAL_PROFILES[email] = profile
    _save_identity_state()
    return {"status": "accepted", "legal_acceptances": legal_acceptances}


def _assert_account_type_transition(
    owner_email: str, account_type: str, organization_document: str
) -> None:
    """Impede que uma organizacao atravesse a fronteira do 'enterprise'.

    Empresa NR-1 e clinica com o MESMO CNPJ resolvem para o MESMO
    organization_id, e o upsert de organizacoes faz ON CONFLICT DO UPDATE do
    organization_type. Sem esta trava, reenviar o perfil com account_type
    trocado rebaixa a organizacao de 'enterprise' para 'clinic' — e o dono do
    lado do empregador recupera patients.read_all e reports.read_all sobre a
    empresa inteira. O painel nao oferece esse caminho, mas a rota e uma API
    publica autenticada: a barreira nao pode ser o roteador do navegador.

    Subir de clinica para empresa e igualmente recusado. Nao e simetrico por
    elegancia: uma clinica que virasse 'enterprise' perderia o acesso clinico
    dos proprios profissionais, quebrando o atendimento em vez de vazar dado.
    Os dois sentidos exigem decisao administrativa, nao um POST de formulario.
    """
    alvo = tenant_organization_type_for_account(account_type)

    # Verdade local, sempre disponivel: o proprio perfil ja gravado. Vale
    # inclusive com o Postgres desligado, que e o caso de instalacao pequena.
    perfil = PROFESSIONAL_PROFILES.get(_normalize_email(owner_email))
    if isinstance(perfil, dict) and perfil.get("account_type"):
        anterior = tenant_organization_type_for_account(perfil.get("account_type"))
        if (anterior == "enterprise") != (alvo == "enterprise"):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Este cadastro já existe como "
                    + ("empresa contratante do NR-1" if anterior == "enterprise"
                       else "cadastro clínico")
                    + ". A troca entre empresa e clínica muda quem pode ler "
                    "prontuário e exige atendimento do suporte FROID."
                ),
            )

    # Verdade compartilhada: a organizacao do CNPJ pode ter sido criada por
    # OUTRA pessoa. Sem esta segunda pergunta, um cadastro novo com o CNPJ de
    # uma empresa NR-1 existente a rebaixaria para clinica.
    if not TENANT_STORE.enabled:
        return
    organizacao = tenant_organization_id_for_profile(
        owner_email, account_type, organization_document
    )
    try:
        atual = TENANT_STORE.organization_type(organizacao)
    except Exception:
        LOGGER.exception("Unable to read organization type for transition guard")
        # Falha fechada: sem conseguir conferir o tipo vigente, nao se grava um
        # cadastro que pode atravessar a fronteira.
        raise HTTPException(
            status_code=503,
            detail="Não foi possível validar o tipo da organização agora.",
        )
    if not atual or atual == "legacy":
        return
    if (atual == "enterprise") != (alvo == "enterprise"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Já existe uma organização com este CNPJ cadastrada como "
                + ("empresa contratante do NR-1" if atual == "enterprise"
                   else "cadastro clínico")
                + ". A troca entre empresa e clínica muda quem pode ler "
                "prontuário e exige atendimento do suporte FROID."
            ),
        )


@app.post("/api/professional/profile")
async def save_professional_profile(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")

    body = await request.json()
    owner_email = _normalize_email(user.get("email") or body.get("email") or "")
    if not owner_email:
        raise HTTPException(status_code=400, detail="email profissional obrigatório")

    account_type = str(body.get("account_type") or "individual").strip().lower()
    # "nr1_company" e a empresa CONTRATANTE da avaliacao NR-1, e nao uma
    # variacao de clinica. A diferenca nao e de rotulo: ela decide o
    # organization_type, e so 'enterprise' aciona o estreitamento que retira do
    # empregador as permissoes clinicas identificadas. Cadastrada como
    # "organization", a empresa viraria clinica e o dono dela guardaria
    # patients.read_all e reports.read_all — a fronteira que o produto inteiro
    # existe para sustentar.
    if account_type not in {"individual", "organization", "nr1_company"}:
        raise HTTPException(status_code=400, detail="tipo de cadastro inválido")
    _assert_account_type_transition(
        owner_email, account_type, body.get("organization_document")
    )

    professionals = [
        {
            "name": str(item.get("name") or "")[:300],
            "email": _normalize_email(item.get("email") or "")[:320],
            "phone": str(item.get("phone") or "")[:80],
        }
        for item in (
            body.get("professionals")
            if isinstance(body.get("professionals"), list) else []
        )[:100]
        if isinstance(item, dict)
    ]
    raw_patient_base_access = (
        body.get("patient_base_access")
        if isinstance(body.get("patient_base_access"), list)
        else []
    )
    patient_base_access = [
        str(item)[:500] for item in raw_patient_base_access[:500]
        if isinstance(item, (str, int))
    ]
    raw_profile_fields = (
        body.get("profile_fields") if isinstance(body.get("profile_fields"), dict) else {}
    )
    profile_fields = {
        str(key)[:100]: str(value or "")[:4000]
        for key, value in list(raw_profile_fields.items())[:150]
        if isinstance(value, (str, int, float, bool)) or value is None
    }
    legal_jurisdiction = _normalize_legal_jurisdiction(
        body.get("legal_jurisdiction") or profile_fields.get("country") or "BR"
    )
    referrals = [
        {
            "name": str(item.get("name") or "")[:300],
            "email": _normalize_email(item.get("email") or "")[:320],
            "phone": str(item.get("phone") or "")[:80],
        }
        for item in (
            body.get("referrals") if isinstance(body.get("referrals"), list) else []
        )[:100]
        if isinstance(item, dict)
    ]
    # A chave de conferência depende de QUEM se cadastra, e confundir as duas
    # travava o cadastro da empresa no primeiro passo.
    #
    # Profissional autônomo e clínica são identificados por uma pessoa: o CPF do
    # profissional ou o do representante legal. A empresa contratante do NR-1
    # não é — ela responde por um CNPJ, e é o CNPJ que amarra o cadastro à
    # organização que a fiscalização vai auditar. Pedir o CPF de quem preenche o
    # formulário seria coletar dado pessoal sem finalidade: o responsável pelo
    # programa é registrado pelo nome e pelo cargo, como 1.5.7.2 pede, e não por
    # documento de identidade.
    if account_type == "nr1_company":
        company_document = _digits_only(body.get("organization_document") or "")
        if len(company_document) != 14:
            raise HTTPException(
                status_code=400,
                detail="CNPJ da empresa contratante é obrigatório e deve ter 14 dígitos",
            )
        professional_cpf = ""
    else:
        professional_cpf = _digits_only(
            profile_fields.get("legalRepresentativeCpf")
            if account_type == "organization"
            else profile_fields.get("cpf") or body.get("document") or ""
        )
        if not professional_cpf:
            raise HTTPException(status_code=400, detail="CPF obrigatório como chave de conferência do profissional")

    legal_acceptances = _validated_legal_acceptances(
        body.get("legal_acceptances"),
        account_type,
        required=_legal_acceptance_required(legal_jurisdiction),
    )

    now = datetime.now(timezone.utc).isoformat()
    existing = PROFESSIONAL_PROFILES.get(owner_email) or {}
    approval_status = str(existing.get("access_approval_status") or "").strip().lower()
    if not approval_status:
        approval_status = (
            "approved"
            if existing or not FROID_PROFESSIONAL_APPROVAL_REQUIRED
            else "pending"
        )
    existing_used_sessions = max(0, _local_int(existing.get("used_sessions")))
    existing_consumed_sessions = (
        existing.get("consumed_session_ids")
        if isinstance(existing.get("consumed_session_ids"), list)
        else []
    )
    total_sessions = max(0, _local_int(existing.get("total_sessions")))
    # Cortesia so na criacao. `existing` vazio significa cadastro novo — e e por
    # isso que quem ja esta cadastrado em producao nao ganha credito retroativo.
    trial_granted_at = str(existing.get("trial_granted_at") or "")
    trial_sessions = max(0, _local_int(existing.get("trial_sessions")))
    conceder_cortesia = not existing and FROID_TRIAL_SESSIONS > 0
    if conceder_cortesia:
        trial_sessions = FROID_TRIAL_SESSIONS
        trial_granted_at = now
        total_sessions = FROID_TRIAL_SESSIONS
    profile = {
        "id": existing.get("id") or f"prof-{uuid.uuid4().hex[:12]}",
        "owner_email": owner_email,
        "owner_name": str(body.get("owner_name") or user.get("name") or "").strip(),
        "account_type": account_type,
        "legal_jurisdiction": legal_jurisdiction,
        "document": str(body.get("document") or "").strip(),
        "phone": str(body.get("phone") or "").strip(),
        "organization_name": str(body.get("organization_name") or "").strip(),
        "organization_document": str(body.get("organization_document") or "").strip(),
        "professionals": professionals,
        "patient_base_access": patient_base_access,
        "profile_fields": profile_fields,
        "referrals": referrals,
        "lgpd_acknowledged": bool(body.get("lgpd_acknowledged")),
        "lgpd_acknowledged_at": body.get("lgpd_acknowledged_at") or existing.get("lgpd_acknowledged_at"),
        "legal_acceptances": legal_acceptances or existing.get("legal_acceptances") or {},
        "monthly_consultations": max(
            0, min(100_000, _local_int(body.get("monthly_consultations")))
        ),
        "selected_plan": (
            FROID_TRIAL_PLAN_ID
            if conceder_cortesia
            else str(existing.get("selected_plan") or "").strip()
        ),
        "contracted_sessions": max(0, _local_int(existing.get("contracted_sessions"))),
        "bonus_sessions": max(0, _local_int(existing.get("bonus_sessions"))),
        # Cortesia fica em campo proprio, separada de contratadas e de bonus:
        # é o que permite distinguir "nunca comprou" de "comprou e acabou", e
        # essa distincao decide se o excedente vira pendencia ou bloqueio.
        "trial_sessions": trial_sessions,
        "trial_granted_at": trial_granted_at,
        "total_sessions": total_sessions,
        "used_sessions": existing_used_sessions,
        "remaining_sessions": max(0, total_sessions - existing_used_sessions),
        "consumed_session_ids": existing_consumed_sessions[-500:],
        "session_unit_amount_cents": max(0, _local_int(existing.get("session_unit_amount_cents"))),
        "package_total_cents": max(0, _local_int(existing.get("package_total_cents"))),
        "payment_status": (
            # "trialing" ja e aceito por access_ready e por
            # ACTIVE_SUBSCRIPTION_STATUSES: a cortesia entra pela porta que ja
            # existia, sem afrouxar nenhum portao.
            "trialing"
            if conceder_cortesia
            else existing.get("payment_status") or "not_started"
        ),
        "access_approval_status": approval_status,
        "access_approval_requested_at": (
            existing.get("access_approval_requested_at") or now
        ),
        "access_approval_updated_at": existing.get("access_approval_updated_at") or "",
        "access_approval_updated_by": existing.get("access_approval_updated_by") or "",
        "access_approval_note": existing.get("access_approval_note") or "",
        "access_approved_at": existing.get("access_approved_at") or "",
        "access_approved_by": existing.get("access_approved_by") or "",
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
    }
    if legal_acceptances:
        # A organizacao gravada aqui precisa ser a MESMA em que o cadastro vai
        # viver, e nao era.
        #
        # `stable_uuid("organization", owner_email)` deriva do e-mail, que e a
        # regra do profissional autonomo. Clinica e empresa NR-1 derivam do
        # CNPJ (organization_id_for_profile), porque varias pessoas do mesmo
        # CNPJ compartilham a organizacao. O efeito era que o aceite da empresa
        # ficava arquivado sob um id que nao corresponde a nenhuma organizacao
        # dela: qualquer leitura por organizacao devolvia vazio, e o contrato
        # aceito parecia nao ter sido aceito.
        #
        # Nao ha correcao retroativa possivel — legal_acceptance_events e
        # append-only por trigger, e assim deve continuar. Por isso o
        # comprovante procura pelo SUJEITO, que sempre esteve certo.
        _record_legal_documents(
            request=request,
            subject_reference=owner_email,
            subject_kind=("organization" if account_type == "organization" else "professional"),
            organization_id=tenant_organization_id_for_profile(
                owner_email, account_type, body.get("organization_document")
            ),
            acceptances=legal_acceptances,
            context="professional_onboarding",
        )
    PROFESSIONAL_PROFILES[owner_email] = profile
    _save_identity_state()
    # A organizacao acaba de ser provisionada a partir deste perfil, e quem
    # chamou ainda nao sabe o id dela. Sem devolve-lo aqui, o cadastro guiado da
    # empresa monta a proxima chamada como /api/organizations//nr1/units e
    # quebra no passo seguinte — o usuario recem-criado nao tem
    # active_organization_id em lugar nenhum.
    contextos = _tenant_contexts_for_email(owner_email)
    return {
        "status": "ok",
        "profile": profile,
        "access_status": _professional_access_status(owner_email),
        "organizations": contextos,
        "organization_id": (
            str(contextos[0].get("organization_id") or "") if contextos else ""
        ),
    }


@app.get("/api/subscriptions/plans")
async def subscription_plans(request: Request, currency: str = "brl"):
    _require_current_user(request)
    selected_currency = _normalize_stripe_currency(currency) or "brl"
    return {
        "plans": [
            {
                **plan,
                "available": any(
                    package["plan_code"] == plan["code"]
                    and bool(STRIPE_SUBSCRIPTION_PRICE_IDS.get(package["code"]))
                    for package in SESSION_PACKAGES.values()
                ),
            }
            for plan in public_plan_catalog()
        ],
        "currency": selected_currency,
        "supported_currencies": list(SUPPORTED_BILLING_CURRENCIES),
        "packages": [{
            **package,
            "selected_price": package_price(package, selected_currency),
            "available": bool(STRIPE_SUBSCRIPTION_PRICE_IDS.get(package["code"])),
        } for package in public_package_catalog()],
    }


@app.get("/api/subscriptions/current")
async def current_subscription(request: Request):
    context = _tenant_context_from_request(request)
    if context is None:
        raise HTTPException(status_code=409, detail="contexto organizacional ausente")
    subscription = TENANT_STORE.subscription_status(
        organization_id=context.organization_id,
        membership_id=context.membership_id,
    )
    return {
        "subscription": subscription,
        "access_active": bool(
            subscription and subscription.get("status") in ACTIVE_SUBSCRIPTION_STATUSES
        ),
    }


async def _verify_stripe_checkout_line_item(
    checkout_session_id: str,
    package_code: str,
    currency: str,
    expected_amount: int,
) -> None:
    """Fail closed unless Stripe confirms the exact server-owned package price."""
    expected_price_id = STRIPE_SUBSCRIPTION_PRICE_IDS.get(package_code) or ""
    if not expected_price_id:
        raise HTTPException(status_code=503, detail="preço Stripe não configurado")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://api.stripe.com/v1/checkout/sessions/"
            f"{quote(checkout_session_id, safe='')}/line_items",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            params={"limit": 10},
        )
    payload = response.json()
    items = payload.get("data") if isinstance(payload, dict) else None
    if response.status_code >= 400 or not isinstance(items, list) or len(items) != 1:
        raise HTTPException(status_code=409, detail="itens do pagamento não confirmados")
    item = items[0] if isinstance(items[0], dict) else {}
    price = item.get("price") if isinstance(item.get("price"), dict) else {}
    if (
        str(price.get("id") or "") != expected_price_id
        or int(item.get("quantity") or 0) != 1
        or str(item.get("currency") or "").lower() != currency
        or int(item.get("amount_total") or 0) != int(expected_amount)
    ):
        raise HTTPException(status_code=409, detail="item Stripe diverge do pacote FROID")


@app.post("/api/subscriptions/checkout")
async def create_subscription_checkout(request: Request):
    user = _require_current_user(request)
    context = _tenant_context_from_request(request)
    if context is None:
        raise HTTPException(status_code=409, detail="contexto organizacional ausente")
    if not ({"owner", "administrator"} & set(context.roles)):
        raise HTTPException(status_code=403, detail="papel sem permissão para contratar plano")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe não configurado")
    body = await request.json()
    auto_replenish = body.get("auto_replenish_consent") is True
    package_code = str(body.get("package_code") or "").strip().lower()
    package = SESSION_PACKAGES.get(package_code)
    if not package:
        raise HTTPException(status_code=400, detail="pacote de assinatura inválido")
    plan_code = str(package["plan_code"])
    currency = _normalize_stripe_currency(body.get("currency"))
    commercial_price = package_price(package, currency)
    if not currency or not commercial_price:
        raise HTTPException(status_code=400, detail="moeda de cobrança inválida")
    order_summary_accepted = body.get("order_summary_accepted") is True
    email = _normalize_email(user.get("email") or "")
    profile = PROFESSIONAL_PROFILES.get(email) or {}
    legal_jurisdiction = _normalize_legal_jurisdiction(
        profile.get("legal_jurisdiction")
        or (profile.get("profile_fields") or {}).get("country")
        or "BR"
    )
    legal_acceptance_required = _legal_acceptance_required(legal_jurisdiction)
    if legal_acceptance_required:
        if not order_summary_accepted:
            raise HTTPException(status_code=428, detail="confirme o resumo da contratação")
        current_documents = public_legal_catalog()["documents"]
        current_acceptances = profile.get("legal_acceptances") or {}
        account_type = str(profile.get("account_type") or "individual")
        for key in required_document_keys(account_type):
            accepted = current_acceptances.get(key) or {}
            if (
                accepted.get("version") != current_documents[key]["version"]
                or accepted.get("sha256") != current_documents[key]["sha256"]
            ):
                raise HTTPException(status_code=428, detail=f"renove o aceite jurídico: {key}")
    order_snapshot = _commercial_order_snapshot(
        package_code, package, currency, commercial_price, auto_replenish
    )
    order_sha256 = _commercial_order_sha256(order_snapshot)
    price_id = STRIPE_SUBSCRIPTION_PRICE_IDS.get(package_code) or ""
    if not price_id:
        raise HTTPException(status_code=503, detail="preço Stripe do plano não configurado")
    async with httpx.AsyncClient(timeout=20.0) as client:
        price_response = await client.get(
            f"https://api.stripe.com/v1/prices/{quote(price_id, safe='')}",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            params={"expand[]": "currency_options"},
        )
    price_data = price_response.json()
    recurring = price_data.get("recurring") if isinstance(price_data, dict) else None
    currency_options = (
        price_data.get("currency_options")
        if isinstance(price_data.get("currency_options"), dict) else {}
    )
    stripe_amount = (
        price_data.get("unit_amount")
        if price_data.get("currency") == currency
        else (currency_options.get(currency) or {}).get("unit_amount")
    )
    if (
        price_response.status_code >= 400
        or not price_data.get("active")
        or int(stripe_amount or 0) != int(commercial_price["total_amount_minor"])
        or recurring is not None
    ):
        raise HTTPException(status_code=409, detail="preço Stripe diverge do catálogo FROID")
    base_url = _public_app_base_url(body.get("base_url") or "")
    checkout_context = str(body.get("checkout_context") or "settings").strip().lower()
    return_path = "access/register" if checkout_context == "onboarding" else "settings"
    form = {
        "mode": "payment",
        "success_url": f"{base_url}/#/{return_path}?subscription=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base_url}/#/{return_path}?subscription=cancelled",
        "client_reference_id": context.organization_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "currency": currency,
        "metadata[organization_id]": context.organization_id,
        "metadata[plan_code]": plan_code,
        "metadata[package_code]": package_code,
        "metadata[currency]": currency,
        "metadata[auto_replenish]": "true" if auto_replenish else "false",
        "metadata[legal_terms_version]": LEGAL_DOCUMENT_VERSION,
        "metadata[legal_jurisdiction]": legal_jurisdiction,
        "metadata[legal_acceptance_required]": (
            "true" if legal_acceptance_required else "false"
        ),
        "metadata[order_sha256]": order_sha256,
        "payment_intent_data[metadata][organization_id]": context.organization_id,
        "payment_intent_data[metadata][plan_code]": plan_code,
        "payment_intent_data[metadata][package_code]": package_code,
        "payment_intent_data[metadata][currency]": currency,
        "payment_intent_data[metadata][auto_replenish]": (
            "true" if auto_replenish else "false"
        ),
        "payment_intent_data[metadata][legal_terms_version]": LEGAL_DOCUMENT_VERSION,
        "payment_intent_data[metadata][legal_jurisdiction]": legal_jurisdiction,
        "payment_intent_data[metadata][legal_acceptance_required]": (
            "true" if legal_acceptance_required else "false"
        ),
        "payment_intent_data[metadata][order_sha256]": order_sha256,
    }
    if auto_replenish:
        form["metadata[auto_replenish_terms_version]"] = AUTO_REPLENISH_TERMS_VERSION
        form["customer_creation"] = "always"
        form["payment_intent_data[setup_future_usage]"] = "off_session"
        form["payment_intent_data[metadata][auto_replenish_terms_version]"] = (
            AUTO_REPLENISH_TERMS_VERSION
        )
        form["custom_text[submit][message]"] = (
            "Ao concluir, você autoriza o FROID a salvar o método de pagamento "
            "e recomprar este pacote, na mesma moeda e pelo valor informado, "
            "quando o saldo de sessões chegar a zero."
        )
    if email:
        form["customer_email"] = email
    if order_summary_accepted:
        _record_legal_documents(
            request=request,
            subject_reference=email,
            subject_kind=(
                "organization"
                if profile.get("account_type") == "organization"
                else "professional"
            ),
            organization_id=context.organization_id,
            acceptances={
                "order_summary": {
                    "version": LEGAL_DOCUMENT_VERSION,
                    "sha256": order_sha256,
                    "accepted_at": _utc_now_iso(),
                }
            },
            context="stripe_checkout_requested",
            commercial_snapshot=order_snapshot,
        )
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            data=form,
        )
    data = response.json()
    if response.status_code >= 400:
        detail = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise HTTPException(status_code=502, detail=detail or "Falha ao criar assinatura Stripe")
    return {
        "status": "ok", "checkout_session_id": data.get("id"),
        "checkout_url": data.get("url"), "plan": SUBSCRIPTION_PLANS[plan_code],
        "package": package,
    }


@app.post("/api/subscriptions/confirm-checkout")
async def confirm_subscription_checkout(request: Request):
    """Reconcile a paid Stripe return without depending on webhook timing."""
    user = _require_current_user(request)
    context = _tenant_context_from_request(request)
    if context is None:
        raise HTTPException(status_code=409, detail="contexto organizacional ausente")
    if not ({"owner", "administrator"} & set(context.roles)):
        raise HTTPException(status_code=403, detail="papel sem permissão para confirmar plano")
    if not STRIPE_SECRET_KEY or not TENANT_STORE.enabled:
        raise HTTPException(status_code=503, detail="confirmação de pagamento indisponível")
    body = await request.json()
    checkout_session_id = str(body.get("checkout_session_id") or "").strip()
    if not checkout_session_id.startswith("cs_"):
        raise HTTPException(status_code=400, detail="sessão de pagamento inválida")

    async with httpx.AsyncClient(timeout=20.0) as client:
        session_response = await client.get(
            f"https://api.stripe.com/v1/checkout/sessions/{quote(checkout_session_id, safe='')}",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
        )
    stripe_session = session_response.json()
    if session_response.status_code >= 400 or not isinstance(stripe_session, dict):
        detail = (
            stripe_session.get("error", {}).get("message")
            if isinstance(stripe_session, dict) else None
        )
        raise HTTPException(status_code=502, detail=detail or "Falha ao consultar pagamento")

    metadata = (
        stripe_session.get("metadata")
        if isinstance(stripe_session.get("metadata"), dict) else {}
    )
    organization_id = str(metadata.get("organization_id") or "").strip()
    if (
        organization_id != context.organization_id
        or str(stripe_session.get("client_reference_id") or "") != context.organization_id
    ):
        raise HTTPException(status_code=403, detail="pagamento não pertence à organização ativa")
    if stripe_session.get("payment_status") != "paid":
        raise HTTPException(status_code=409, detail="pagamento ainda não confirmado pelo Stripe")

    package_code = str(metadata.get("package_code") or "").strip().lower()
    package = SESSION_PACKAGES.get(package_code)
    currency = _normalize_stripe_currency(metadata.get("currency"))
    commercial_price = package_price(package or {}, currency)
    auto_replenish = metadata.get("auto_replenish") == "true"
    if (
        not package or not commercial_price
        or metadata.get("plan_code") != package["plan_code"]
        or (
            auto_replenish
            and metadata.get("auto_replenish_terms_version")
            != AUTO_REPLENISH_TERMS_VERSION
        )
    ):
        raise HTTPException(status_code=422, detail="pacote Stripe não reconhecido")
    _validate_checkout_legal_metadata(
        metadata,
        package_code=package_code,
        package=package,
        currency=currency,
        commercial_price=commercial_price,
        auto_replenish=auto_replenish,
    )
    if (
        stripe_session.get("mode") != "payment"
        or stripe_session.get("status") != "complete"
        or str(stripe_session.get("currency") or "").lower() != currency
        or int(stripe_session.get("amount_total") or 0)
        != int(commercial_price["total_amount_minor"])
    ):
        raise HTTPException(status_code=409, detail="total do checkout não confirmado")
    await _verify_stripe_checkout_line_item(
        checkout_session_id,
        package_code,
        currency,
        int(commercial_price["total_amount_minor"]),
    )

    payment_intent_id = str(stripe_session.get("payment_intent") or "")
    if not payment_intent_id:
        raise HTTPException(status_code=409, detail="pagamento sem identificação financeira")
    async with httpx.AsyncClient(timeout=20.0) as client:
        pi_response = await client.get(
            f"https://api.stripe.com/v1/payment_intents/{quote(payment_intent_id, safe='')}",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
        )
    payment_intent = pi_response.json()
    payment_metadata = (
        payment_intent.get("metadata")
        if isinstance(payment_intent.get("metadata"), dict) else {}
    )
    paid_amount = int(
        payment_intent.get("amount_received")
        or payment_intent.get("amount") or 0
    )
    if (
        pi_response.status_code >= 400
        or payment_intent.get("status") != "succeeded"
        or payment_intent.get("currency") != currency
        or paid_amount != int(commercial_price["total_amount_minor"])
        or bool(payment_intent.get("livemode")) != bool(stripe_session.get("livemode"))
        or payment_metadata.get("organization_id") != organization_id
        or payment_metadata.get("plan_code") != package["plan_code"]
        or payment_metadata.get("package_code") != package_code
        or payment_metadata.get("currency") != currency
        or payment_metadata.get("legal_jurisdiction")
        != metadata.get("legal_jurisdiction")
        or payment_metadata.get("legal_acceptance_required")
        != metadata.get("legal_acceptance_required")
    ):
        raise HTTPException(status_code=409, detail="pagamento inicial não confirmado")
    _validate_checkout_legal_metadata(
        payment_metadata,
        package_code=package_code,
        package=package,
        currency=currency,
        commercial_price=commercial_price,
        auto_replenish=auto_replenish,
    )
    stripe_customer_id = str(
        stripe_session.get("customer") or payment_intent.get("customer") or ""
    )
    stripe_payment_method_id = str(payment_intent.get("payment_method") or "")
    if auto_replenish and (not stripe_customer_id or not stripe_payment_method_id):
        raise HTTPException(status_code=409, detail="método sem suporte a recarga")

    result = TENANT_STORE.apply_checkout_purchase(
        event_id=f"checkout:{checkout_session_id}",
        event_type="checkout.session.confirmed",
        payload_sha256=hashlib.sha256(
            json.dumps(stripe_session, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        organization_id=organization_id,
        plan_code=str(package["plan_code"]),
        package_code=package_code,
        session_credits=int(package["sessions"]),
        amount_cents=int(commercial_price["total_amount_minor"]),
        currency=currency,
        stripe_customer_id=stripe_customer_id,
        stripe_payment_method_id=stripe_payment_method_id,
        terms_version=str(metadata.get("auto_replenish_terms_version") or ""),
        auto_replenish=auto_replenish,
    )
    refreshed_user = _attach_tenant_contexts(dict(user))
    return {
        "status": "active",
        **result,
        "access_status": _effective_professional_access_status(refreshed_user),
    }


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = verify_stripe_event(
            payload,
            request.headers.get("stripe-signature", ""),
            STRIPE_WEBHOOK_SECRET,
        )
    except StripeSignatureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    event_type = str(event.get("type") or "")
    if event_type not in {
        "checkout.session.completed", "payment_intent.succeeded",
        "payment_intent.payment_failed",
    }:
        return {"received": True, "handled": False}
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    stripe_object = data.get("object") if isinstance(data.get("object"), dict) else {}
    metadata = stripe_object.get("metadata") if isinstance(stripe_object.get("metadata"), dict) else {}
    if not TENANT_STORE.enabled:
        raise HTTPException(status_code=503, detail="persistência de assinaturas indisponível")

    if event_type == "checkout.session.completed":
        if stripe_object.get("payment_status") != "paid":
            return {"received": True, "handled": True, "applied": False}
        organization_id = str(metadata.get("organization_id") or "").strip()
        package_code = str(metadata.get("package_code") or "").strip().lower()
        package = SESSION_PACKAGES.get(package_code)
        currency = _normalize_stripe_currency(metadata.get("currency"))
        commercial_price = package_price(package or {}, currency)
        auto_replenish = metadata.get("auto_replenish") == "true"
        try:
            uuid.UUID(organization_id)
        except (ValueError, AttributeError) as exc:
            raise HTTPException(status_code=422, detail="checkout sem organização válida") from exc
        if (
            not package or not commercial_price
            or metadata.get("plan_code") != package["plan_code"]
            or (
                auto_replenish
                and metadata.get("auto_replenish_terms_version")
                != AUTO_REPLENISH_TERMS_VERSION
            )
        ):
            raise HTTPException(status_code=422, detail="pacote Stripe não reconhecido")
        _validate_checkout_legal_metadata(
            metadata,
            package_code=package_code,
            package=package,
            currency=currency,
            commercial_price=commercial_price,
            auto_replenish=auto_replenish,
        )
        if (
            stripe_object.get("mode") != "payment"
            or stripe_object.get("status") != "complete"
            or str(stripe_object.get("currency") or "").lower() != currency
            or int(stripe_object.get("amount_total") or 0)
            != int(commercial_price["total_amount_minor"])
        ):
            raise HTTPException(status_code=409, detail="total do checkout não confirmado")
        checkout_session_id = str(stripe_object.get("id") or "")
        await _verify_stripe_checkout_line_item(
            checkout_session_id,
            package_code,
            currency,
            int(commercial_price["total_amount_minor"]),
        )
        payment_intent_id = str(stripe_object.get("payment_intent") or "")
        async with httpx.AsyncClient(timeout=20.0) as client:
            pi_response = await client.get(
                f"https://api.stripe.com/v1/payment_intents/{quote(payment_intent_id, safe='')}",
                headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            )
        payment_intent = pi_response.json()
        payment_metadata = (
            payment_intent.get("metadata")
            if isinstance(payment_intent.get("metadata"), dict) else {}
        )
        paid_amount = int(
            payment_intent.get("amount_received")
            or payment_intent.get("amount") or 0
        )
        if (
            pi_response.status_code >= 400
            or payment_intent.get("status") != "succeeded"
            or payment_intent.get("currency") != currency
            or paid_amount != int(commercial_price["total_amount_minor"])
            or bool(payment_intent.get("livemode")) != bool(stripe_object.get("livemode"))
            or payment_metadata.get("organization_id") != organization_id
            or payment_metadata.get("plan_code") != package["plan_code"]
            or payment_metadata.get("package_code") != package_code
            or payment_metadata.get("currency") != currency
            or payment_metadata.get("legal_jurisdiction")
            != metadata.get("legal_jurisdiction")
            or payment_metadata.get("legal_acceptance_required")
            != metadata.get("legal_acceptance_required")
        ):
            raise HTTPException(status_code=409, detail="pagamento inicial não confirmado")
        _validate_checkout_legal_metadata(
            payment_metadata,
            package_code=package_code,
            package=package,
            currency=currency,
            commercial_price=commercial_price,
            auto_replenish=auto_replenish,
        )
        stripe_customer_id = str(
            stripe_object.get("customer") or payment_intent.get("customer") or ""
        )
        stripe_payment_method_id = str(payment_intent.get("payment_method") or "")
        if auto_replenish and (not stripe_customer_id or not stripe_payment_method_id):
            raise HTTPException(status_code=409, detail="método sem suporte a recarga")
        result = TENANT_STORE.apply_checkout_purchase(
            event_id=f"checkout:{checkout_session_id}", event_type=event_type,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            organization_id=organization_id, plan_code=str(package["plan_code"]),
            package_code=package_code, session_credits=int(package["sessions"]),
            amount_cents=int(commercial_price["total_amount_minor"]),
            currency=currency, stripe_customer_id=stripe_customer_id,
            stripe_payment_method_id=stripe_payment_method_id,
            terms_version=str(metadata.get("auto_replenish_terms_version") or ""),
            auto_replenish=auto_replenish,
        )
        return {"received": True, "handled": True, **result}

    recharge_id = str(metadata.get("recharge_id") or "")
    if metadata.get("froid_auto_recharge") != "true" or not recharge_id:
        return {"received": True, "handled": False}
    if event_type == "payment_intent.succeeded":
        result = TENANT_STORE.complete_auto_recharge(
            recharge_id=recharge_id,
            stripe_payment_intent_id=str(stripe_object.get("id") or ""),
            event_id=str(event.get("id") or ""), event_type=event_type,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            paid_amount_cents=int(
                stripe_object.get("amount_received")
                or stripe_object.get("amount") or 0
            ),
            paid_currency=str(stripe_object.get("currency") or "").lower(),
        )
        return {"received": True, "handled": True, **result}
    error = stripe_object.get("last_payment_error") if isinstance(stripe_object.get("last_payment_error"), dict) else {}
    TENANT_STORE.fail_auto_recharge(
        recharge_id=recharge_id, status="failed",
        failure_code=str(error.get("code") or "payment_failed"),
        stripe_payment_intent_id=str(stripe_object.get("id") or ""),
        event_id=str(event.get("id") or ""), event_type=event_type,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )
    return {"received": True, "handled": True, "applied": False}


async def _run_automatic_recharge(organization_id: str) -> None:
    recharge = None
    try:
        recharge = await asyncio.to_thread(
            TENANT_STORE.prepare_auto_recharge, organization_id=organization_id
        )
        if not recharge:
            return
        form = {
            "amount": str(recharge["amount_cents"]),
            "currency": recharge["currency"],
            "customer": recharge["stripe_customer_id"],
            "payment_method": recharge["stripe_payment_method_id"],
            "off_session": "true", "confirm": "true",
            "metadata[froid_auto_recharge]": "true",
            "metadata[recharge_id]": recharge["recharge_id"],
            "metadata[organization_id]": organization_id,
            "metadata[package_code]": recharge["package_code"],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.stripe.com/v1/payment_intents",
                headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}",
                         "Idempotency-Key": recharge["idempotency_key"]},
                data=form,
            )
        payment_intent = response.json()
        payment_intent_id = str(payment_intent.get("id") or "")
        if response.status_code < 400 and payment_intent.get("status") == "succeeded":
            await asyncio.to_thread(
                TENANT_STORE.complete_auto_recharge,
                recharge_id=recharge["recharge_id"],
                stripe_payment_intent_id=payment_intent_id,
                event_id=f"direct:{payment_intent_id}",
                event_type="payment_intent.succeeded.direct",
                payload_sha256=hashlib.sha256(response.content).hexdigest(),
                paid_amount_cents=int(
                    payment_intent.get("amount_received")
                    or payment_intent.get("amount") or 0
                ),
                paid_currency=str(payment_intent.get("currency") or "").lower(),
            )
            return
        error = payment_intent.get("error") if isinstance(payment_intent.get("error"), dict) else {}
        intent = error.get("payment_intent") if isinstance(error.get("payment_intent"), dict) else payment_intent
        requires_action = intent.get("status") in {"requires_action", "requires_confirmation"}
        await asyncio.to_thread(
            TENANT_STORE.fail_auto_recharge,
            recharge_id=recharge["recharge_id"],
            status="action_required" if requires_action else "failed",
            failure_code=str(error.get("code") or intent.get("status") or "payment_failed"),
            stripe_payment_intent_id=str(intent.get("id") or payment_intent_id),
        )
    except Exception as exc:
        LOGGER.exception("Automatic package recharge failed")
        if recharge:
            try:
                await asyncio.to_thread(
                    TENANT_STORE.fail_auto_recharge,
                    recharge_id=recharge["recharge_id"],
                    status="failed",
                    failure_code=f"transport_error:{type(exc).__name__}",
                )
            except Exception:
                LOGGER.exception("Unable to release failed automatic recharge")


@app.post("/api/subscriptions/recharge/retry")
async def retry_automatic_recharge(request: Request):
    context = _tenant_context_from_request(request)
    if context is None:
        raise HTTPException(status_code=409, detail="contexto organizacional ausente")
    if not ({"owner", "administrator"} & set(context.roles)):
        raise HTTPException(status_code=403, detail="papel sem permissão para recarga")
    await _run_automatic_recharge(context.organization_id)
    return {"status": "processed"}


@app.post("/api/billing/checkout")
async def create_billing_checkout(request: Request):
    if FROID_SUBSCRIPTIONS_REQUIRED:
        raise HTTPException(status_code=410, detail="checkout legado desativado")
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")

    body = await request.json()
    plan_id = str(body.get("plan_id") or "").strip()
    plan = FROID_ACCESS_PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="plano FROID inválido")

    base_url = _public_app_base_url(body.get("base_url") or "")
    purchase_type = str(body.get("purchase_type") or "onboarding").strip().lower()
    return_path = "/settings" if purchase_type == "add_sessions" else "/dashboard"
    cancel_path = "/settings" if purchase_type == "add_sessions" else "/access/register"
    success_url = f"{base_url}/#{return_path}?checkout=success&plan={quote(plan_id)}&stripe_session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/#{cancel_path}?checkout=cancelled&plan={quote(plan_id)}"
    email = _normalize_email(user.get("email") or body.get("email") or "")
    contracted_sessions = max(
        1,
        min(10000, _local_int(body.get("contracted_sessions") or plan.get("session_credits") or 1)),
    )
    bonus_sessions = (contracted_sessions // 100) * 10
    total_sessions = contracted_sessions + bonus_sessions
    plan_currency = (
        _normalize_stripe_currency(body.get("currency"))
        or _normalize_stripe_currency(plan.get("currency"))
        or _normalize_stripe_currency(STRIPE_CURRENCY)
        or "usd"
    )
    unit_amount_cents = _plan_amount_for_currency(plan, plan_currency)
    package_total_cents = max(0, unit_amount_cents * contracted_sessions)
    checkout_description = (
        f"{plan['description']} "
        f"Sessoes contratadas: {contracted_sessions}. "
        f"Bonus: {bonus_sessions}. "
        f"Total liberado: {total_sessions}. "
        f"Valor por sessao: {_format_brl(unit_amount_cents, plan_currency)}."
    )

    def apply_local_credits() -> None:
        _apply_session_credit_purchase(
            email=email,
            plan_id=plan_id,
            purchase_type=purchase_type,
            contracted_sessions=contracted_sessions,
            bonus_sessions=bonus_sessions,
            total_sessions=total_sessions,
            unit_amount_cents=unit_amount_cents,
            package_total_cents=package_total_cents,
            status="paid_local" if package_total_cents <= 0 else "local_applied",
        )

    if not STRIPE_SECRET_KEY:
        if not FROID_ALLOW_LOCAL_BILLING_FALLBACK:
            raise HTTPException(
                status_code=503,
                detail="checkout indisponível: Stripe não configurado",
            )
        apply_local_credits()
        return {
            "status": "stripe_not_configured",
            "mode": "local_fallback",
            "checkout_url": success_url,
            "message": "STRIPE_SECRET_KEY nao configurada; usando redirecionamento local para testes.",
            "plan": {
                **plan,
                "amount_brl": _format_brl(package_total_cents, plan_currency),
                "contracted_sessions": contracted_sessions,
                "bonus_sessions": bonus_sessions,
                "total_sessions": total_sessions,
                "session_unit_amount_brl": _format_brl(unit_amount_cents, plan_currency),
            },
        }

    if package_total_cents <= 0:
        if not FROID_ALLOW_LOCAL_BILLING_FALLBACK:
            raise HTTPException(
                status_code=409,
                detail="plano sem cobrança disponível apenas em ambiente autorizado",
            )
        apply_local_credits()
        return {
            "status": "free_access",
            "mode": "local_success",
            "checkout_url": success_url,
            "message": "Plano gratuito liberado sem checkout Stripe.",
            "plan": {
                **plan,
                "amount_brl": _format_brl(package_total_cents, plan_currency),
                "contracted_sessions": contracted_sessions,
                "bonus_sessions": bonus_sessions,
                "total_sessions": total_sessions,
                "session_unit_amount_brl": _format_brl(unit_amount_cents, plan_currency),
            },
        }

    stripe_currency = plan_currency

    form = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": email or uuid.uuid4().hex,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": stripe_currency,
        "line_items[0][price_data][unit_amount]": str(package_total_cents),
        "line_items[0][price_data][product_data][name]": f"{plan['name']} - {total_sessions} sessoes",
        "line_items[0][price_data][product_data][description]": checkout_description,
        "metadata[plan_id]": plan_id,
        "metadata[purchase_type]": purchase_type,
        "metadata[session_credits]": str(total_sessions),
        "metadata[contracted_sessions]": str(contracted_sessions),
        "metadata[bonus_sessions]": str(bonus_sessions),
        "metadata[unit_amount_cents]": str(unit_amount_cents),
        "metadata[package_total_cents]": str(package_total_cents),
        "metadata[currency]": plan_currency,
        "metadata[professional_email]": email,
    }
    if email:
        form["customer_email"] = email

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
                data=form,
            )
        data = response.json()
        if response.status_code >= 400:
            detail = data.get("error", {}).get("message") if isinstance(data, dict) else None
            raise HTTPException(
                status_code=502,
                detail=detail or "Falha ao criar checkout Stripe",
            )
        return {
            "status": "ok",
            "checkout_session_id": data.get("id"),
            "checkout_url": data.get("url"),
            "plan": {
                **plan,
                "amount_brl": _format_brl(package_total_cents, plan_currency),
                "contracted_sessions": contracted_sessions,
                "bonus_sessions": bonus_sessions,
                "total_sessions": total_sessions,
                "session_unit_amount_brl": _format_brl(unit_amount_cents, plan_currency),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro Stripe: {exc}")


@app.post("/api/billing/confirm-checkout")
async def confirm_billing_checkout(request: Request):
    if FROID_SUBSCRIPTIONS_REQUIRED or not FROID_ALLOW_LOCAL_BILLING_FALLBACK:
        raise HTTPException(status_code=410, detail="confirmação legada desativada")
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=409, detail="Stripe não configurado")

    body = await request.json()
    checkout_session_id = str(body.get("checkout_session_id") or "").strip()
    if not checkout_session_id:
        raise HTTPException(status_code=400, detail="checkout_session_id obrigatório")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://api.stripe.com/v1/checkout/sessions/{quote(checkout_session_id, safe='')}",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
        )
    data = response.json()
    if response.status_code >= 400:
        detail = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise HTTPException(status_code=502, detail=detail or "Falha ao confirmar checkout Stripe")

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    email = _normalize_email(metadata.get("professional_email") or data.get("customer_email") or "")
    current_email = _normalize_email(user.get("email") or "")
    if email != current_email:
        raise HTTPException(status_code=403, detail="checkout não pertence ao profissional autenticado")
    if data.get("payment_status") != "paid":
        raise HTTPException(status_code=409, detail="pagamento Stripe ainda não confirmado")

    plan_id = str(metadata.get("plan_id") or "")
    if plan_id not in FROID_ACCESS_PLANS:
        raise HTTPException(status_code=409, detail="plano Stripe não reconhecido")
    if max(0, _local_int(metadata.get("session_credits"))) <= 0:
        raise HTTPException(status_code=409, detail="checkout Stripe sem créditos válidos")

    credit_total = max(0, _local_int(metadata.get("session_credits")))
    context = _tenant_context_from_request(request)
    wallet_result = None
    if _shared_credit_mode_for(context.organization_id if context else "") == "enforce":
        if context is None:
            raise HTTPException(status_code=403, detail="contexto organizacional ausente")
        try:
            wallet_result = TENANT_STORE.apply_credit_event(
                organization_id=context.organization_id,
                membership_id=context.membership_id,
                actor_user_id=context.user_id,
                delta=credit_total,
                event_type="purchase",
                idempotency_key=f"stripe:{checkout_session_id}",
                metadata={"source": "stripe_checkout", "plan_id": metadata.get("plan_id")},
            )
        except Exception:
            LOGGER.exception("Shared wallet purchase failed")
            raise HTTPException(status_code=503, detail="falha ao creditar carteira organizacional")

    profile = _apply_session_credit_purchase(
        email=email,
        plan_id=str(metadata.get("plan_id") or ""),
        purchase_type=str(metadata.get("purchase_type") or body.get("purchase_type") or "add_sessions"),
        contracted_sessions=_local_int(metadata.get("contracted_sessions")),
        bonus_sessions=_local_int(metadata.get("bonus_sessions")),
        total_sessions=_local_int(metadata.get("session_credits")),
        unit_amount_cents=_local_int(metadata.get("unit_amount_cents")),
        package_total_cents=_local_int(metadata.get("package_total_cents")),
        status="paid",
        checkout_session_id=checkout_session_id,
    )
    if wallet_result and isinstance(profile, dict):
        profile["remaining_sessions"] = max(0, _local_int(wallet_result.get("balance")))
        PROFESSIONAL_PROFILES[email] = profile
        _save_identity_state()
    return {
        "status": "ok",
        "profile": profile,
        "access_status": _professional_access_status(email),
        "shared_wallet": wallet_result,
    }


@app.post("/api/froid-explica/query", response_model=FroidExplicaResponse)
async def froid_explica_query(payload: FroidExplicaQuery, request: Request):
    _require_professional_feature_access(request)
    # Comparacao com a carteira: injeta resumos autorizados (RLS aplicado) so
    # quando a pergunta e comparativa, minimizando exposicao de dados.
    if _is_comparative_question(payload.query_text):
        current_patient_id = str(
            payload.patient_id
            or (payload.context or {}).get("patient_id")
            or ""
        )
        portfolio = _build_portfolio_summary(request, current_patient_id)
        if portfolio:
            payload.context = {**(payload.context or {}), "portfolio_summary": portfolio}
    intent = _classify_froid_explica_intent(payload.query_text)
    if intent == "analytics":
        result = await _query_froid_analytics(payload)
    else:
        result = await _query_froid_knowledge(payload)
    result.result_text = _sanitize_reference_sections(result.result_text)
    result.citations = _scientific_citations(result.citations)
    return result


@app.post("/api/copilot/query", response_model=FroidExplicaResponse)
async def copilot_query_alias(payload: FroidExplicaQuery, request: Request):
    return await froid_explica_query(payload, request)


def _accessible_session_reports(
    request: Request, *, reveal_transcripts: bool = False
) -> tuple[list[dict], Any]:
    """Fonte unica de verdade para o RLS de relatorios: devolve os relatorios
    brutos que o solicitante pode ver e o contexto tenant, aplicando exatamente
    a mesma autorizacao (posse, organizacao e, em planos multiprofissionais, a
    decisao tenant que respeita os acessos definidos pelo administrador)."""
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    owner_email = _normalize_email(user.get("email") or "")
    context = _authorize_tenant_request(
        request, "organization.read", resource_type="session_report"
    )
    effective_mode = _tenant_authorization_mode_for(
        context.organization_id if context else ""
    )
    assigned_report_ids = (
        TENANT_STORE.accessible_legacy_report_ids(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
        if effective_mode == "enforce" and context
        else set()
    )
    # Politica definida pelo gestor da clinica. Falha de leitura devolve
    # 'restricted', entao um problema de infraestrutura nunca amplia acesso.
    clinic_wide_reports = bool(
        effective_mode == "enforce"
        and context
        and TENANT_STORE.report_visibility(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
        )
        == "clinic_wide"
    )
    reports = [
        report
        for report in _load_session_reports(
            reveal_transcripts=reveal_transcripts
        ).values()
        if isinstance(report, dict)
        and (
            context is None
            or _report_organization_id(report) == context.organization_id
        )
        and (
            (
                effective_mode != "enforce"
                and _can_access_report(report, owner_email)
            )
            or (
                effective_mode == "enforce"
                and decide(
                    context,
                    "reports.read",
                    resource_organization_id=_report_organization_id(report),
                    assigned=str(
                        report.get("sessionId") or report.get("session_id") or ""
                    ) in assigned_report_ids,
                    owns_resource=_can_access_report(report, owner_email),
                    clinic_wide_reports=clinic_wide_reports,
                ).allowed
            )
        )
    ]
    return reports, context


@app.get("/api/session-reports")
async def list_session_reports(request: Request):
    # Preserva o comportamento original: a lista decripta transcricoes (True).
    accessible, context = _accessible_session_reports(request, reveal_transcripts=True)
    reports = [
        _report_for_api(_enrich_report_patient(report))
        for report in accessible
    ]
    reports.sort(
        key=lambda report: str(report.get("createdAt") or report.get("created_at") or ""),
        reverse=True,
    )
    _record_tenant_success(
        context,
        "report.list",
        "session_report",
        metadata={"result_count": len(reports)},
    )
    return {"reports": reports}


@app.post("/api/session-reports")
async def save_session_report(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    owner_email = _normalize_email(user.get("email") or "")
    report = await request.json()
    report.pop("transcript_encrypted", None)
    report.pop("transcript_storage_locked", None)
    report.pop("transcript_storage_error", None)
    session_id = str(report.get("sessionId") or report.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId obrigatório")
    transcript = str(report.get("transcript") or "")
    if not transcript.strip():
        raise HTTPException(
            status_code=422,
            detail="transcrição integral obrigatória para arquivar a sessão",
        )
    if len(transcript) > 2_000_000:
        raise HTTPException(status_code=413, detail="transcrição excede o limite seguro")
    context = _authorize_tenant_request(
        request,
        "reports.write",
        resource_type="session_report",
        resource_id=session_id,
    )
    if not _session_matches_context(session_id, context):
        raise HTTPException(status_code=409, detail="sessão pertence a outra organização")
    report["professionalEmail"] = owner_email
    if context:
        report["organizationId"] = context.organization_id
    report["professional"] = {
        **(report.get("professional") if isinstance(report.get("professional"), dict) else {}),
        "email": owner_email,
        "name": user.get("name") or owner_email,
    }
    report = _enrich_report_patient(report)
    report = _attach_metrics_analysis(report)
    reports = _load_session_reports()
    is_new_report = session_id not in reports
    if not is_new_report:
        existing_report = reports[session_id]
        if (
            context
            and _report_organization_id(existing_report) != context.organization_id
        ):
            raise HTTPException(status_code=403, detail="relatório pertence a outra organização")
        _authorize_tenant_request(
            request,
            "reports.update",
            resource_type="session_report",
            resource_id=session_id,
            resource_organization_id=_report_organization_id(existing_report),
            owns_resource=_can_access_report(existing_report, owner_email),
        )
    if context and not SESSION_ORGANIZATIONS.get(session_id):
        SESSION_ORGANIZATIONS[session_id] = context.organization_id
        _save_identity_state()
    reports[session_id] = report
    _save_session_reports(reports)
    try:
        access_status = (
            _consume_session_credit(context, owner_email, session_id)
            if is_new_report
            else _professional_access_status(owner_email)
        )
    except HTTPException:
        # O registro clinico NUNCA e descartado por falha de cobranca ou de
        # infraestrutura. Antes, um 402/503 aqui apagava o relatorio de uma
        # sessao ja realizada; agora ele permanece salvo e a falha e sinalizada
        # para acerto posterior. A idempotencia por session_id garante que uma
        # nova tentativa do cliente nao cobre a sessao duas vezes.
        LOGGER.exception(
            "Falha ao consumir crédito da sessão %s; relatório clínico preservado.",
            session_id,
        )
        raise
    _record_tenant_success(
        context,
        "report.create" if is_new_report else "report.update",
        "session_report",
        session_id,
    )
    _append_anonymous_datamart_row(report)
    return {
        "status": "ok",
        "session_id": session_id,
        "metrics_analysis": report.get("metricsAnalysis"),
        "metrics_analysis_error": report.get("metricsAnalysisError"),
        "access_status": access_status,
    }


@app.post("/api/session-reports/{session_id}/clinical-notes", status_code=201)
async def add_session_clinical_note(
    session_id: str, payload: ClinicalNoteCreate, request: Request
):
    user = _require_current_user(request)
    owner_email = _normalize_email(user.get("email") or "")
    reports = _load_session_reports()
    report = reports.get(session_id)
    if not isinstance(report, dict):
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    context = _authorize_tenant_request(
        request,
        "reports.update",
        resource_type="session_report",
        resource_id=session_id,
        resource_organization_id=_report_organization_id(report),
        owns_resource=_can_access_report(report, owner_email),
    )
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Observação vazia")
    note = {
        "id": str(uuid.uuid4()),
        "text": text,
        "timestamp": int(time.time() * 1000),
        "professional_email": owner_email,
    }
    notes = list(report.get("clinicalNotes") or [])
    notes.append(note)
    report["clinicalNotes"] = notes[-500:]
    reports[session_id] = report
    _save_session_reports(reports)
    _record_tenant_success(
        context,
        "report.clinical_note.create",
        "session_report",
        session_id,
        metadata={"clinical_note_id": note["id"]},
    )
    return {"status": "created", "note": note}


@app.put("/api/session-reports/{session_id}/patient-release")
async def set_session_report_patient_release(session_id: str, request: Request):
    """Libera ou retém, para o paciente, o relatório de UMA sessão.

    Nada chega ao paciente sem este ato. O profissional compõe o documento
    marcando os blocos que entram e libera; enquanto não liberar, a sessão não
    aparece na área dele. Revogar é o mesmo endpoint com released=false — e o
    relatório some da área na hora, porque o portão é lido a cada requisição e
    não gravado numa cópia.

    O documento do PROFISSIONAL não passa por aqui: ele sai sempre completo.
    Este endpoint só descreve o que o paciente recebe.
    """
    user = _require_current_user(request)
    owner_email = _normalize_email(user.get("email") or "")
    reports = _load_session_reports()
    report = reports.get(session_id)
    if not isinstance(report, dict):
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    context = _authorize_tenant_request(
        request,
        "reports.update",
        resource_type="session_report",
        resource_id=session_id,
        resource_organization_id=_report_organization_id(report),
        owns_resource=_can_access_report(report, owner_email),
    )

    body = await request.json()
    released = bool(body.get("released"))
    items = _normalize_patient_report_items(body.get("items"))
    if released and not items:
        raise HTTPException(
            status_code=400,
            detail="Selecione ao menos um item para compor o relatório do paciente",
        )

    now = datetime.now(timezone.utc).isoformat()
    # O texto redigido vive no estado da tela do profissional e não era gravado
    # em lugar nenhum. Sem congelá-lo aqui, a cópia que o paciente baixa no
    # portal sairia com a seção "Anotações do seu profissional" em branco — o
    # portal não tem, e não deve ter, acesso à área de trabalho do profissional.
    # Congelado no ato da liberação, e não lido depois: o paciente recebe o
    # texto que foi liberado, não uma versão que mudou desde então.
    report["patientRelease"] = {
        "released": released,
        "items": items,
        "releasedAt": now if released else "",
        "releasedBy": owner_email if released else "",
        "notes": _safe_str(body.get("descriptiveText"), 20000) if released else "",
    }
    reports[session_id] = report
    _save_session_reports(reports)
    _record_tenant_success(
        context,
        "report.patient_release.update" if released else "report.patient_release.revoke",
        "session_report",
        session_id,
        metadata={"released": released, "items": items},
    )
    return {"status": "ok", "patientRelease": report["patientRelease"]}


@app.get("/api/patients/{patient_id}/results-access")
async def get_patient_results_access(patient_id: str, request: Request):
    """Estado atual da permissão, para a ficha do paciente desenhar a chave.

    Existe separado do PUT porque a ficha precisa saber o estado ANTES de o
    profissional mexer em nada — uma chave que nasce sempre no mesmo lugar,
    independente do que está gravado, mente sobre o que está valendo.
    """
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    owner_email = _normalize_email(user.get("email") or "")
    patient = PATIENTS.get(patient_id)
    if not isinstance(patient, dict):
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    if not _professional_linked_to_patient(owner_email, patient_id):
        raise HTTPException(status_code=403, detail="Paciente não vinculado a este profissional")
    return {
        "patient_id": patient_id,
        "portal_results_enabled": _patient_results_enabled(patient),
        # Quem nunca teve o campo definido conta como habilitado, por
        # compatibilidade. A ficha diz isso em vez de deixar parecer escolha.
        "explicit": patient.get("portal_results_enabled") is not None,
    }


@app.put("/api/patients/{patient_id}/results-access")
async def set_patient_results_access(patient_id: str, request: Request):
    """Liga ou desliga o acesso do paciente aos próprios resultados.

    Mesma decisão tomada no convite, disponível depois na ficha — porque a
    escolha muda com o caso clínico, e obrigar o profissional a acertar no ato
    do convite transformaria uma decisão reversível em definitiva.

    DESLIGAR NÃO FECHA O PORTAL. O paciente continua entrando, vendo os próprios
    dados cadastrais e exercendo os direitos de titular; o que ele deixa de ver
    são sessões e relatórios. Fechar o portal inteiro removeria o canal pelo qual
    a LGPD é atendida, e isso não é escolha de produto.
    """
    user = _require_current_user(request)
    _require_professional_feature_access(request)
    owner_email = _normalize_email(user.get("email") or "")

    patient = PATIENTS.get(patient_id)
    if not isinstance(patient, dict):
        raise HTTPException(status_code=404, detail="Paciente não encontrado")

    if not _professional_linked_to_patient(owner_email, patient_id):
        raise HTTPException(status_code=403, detail="Paciente não vinculado a este profissional")

    body = await request.json()
    enabled = bool(body.get("enabled"))
    patient["portal_results_enabled"] = enabled
    patient["updated_at"] = datetime.now(timezone.utc).isoformat()
    PATIENTS[patient_id] = patient
    # _persist_state() nao existe e nunca existiu: a chamada entrou assim e o
    # endpoint respondia 500 depois de ja ter mudado PATIENTS em memoria. O
    # profissional via erro, a liberacao valia ate o proximo restart, e o
    # paciente do outro lado nao entendia por que o acesso ia e voltava.
    _save_identity_state()
    return {"status": "ok", "patient_id": patient_id, "portal_results_enabled": enabled}


@app.get("/api/session-reports/{session_id}/patient-release")
async def get_session_report_patient_release(session_id: str, request: Request):
    """Estado de liberação da sessão, e o catálogo de itens que a tela desenha.

    O catálogo vem do servidor de propósito: é a mesma tupla que filtra o
    documento, então a tela não pode oferecer um item que o filtro desconhece.
    """
    user = _require_current_user(request)
    owner_email = _normalize_email(user.get("email") or "")
    reports = _load_session_reports()
    report = reports.get(session_id)
    if not isinstance(report, dict):
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    _authorize_tenant_request(
        request,
        "reports.read",
        resource_type="session_report",
        resource_id=session_id,
        resource_organization_id=_report_organization_id(report),
        owns_resource=_can_access_report(report, owner_email),
    )
    patient = _patient_record_for_report(report)
    return {
        "patientRelease": _report_patient_release(report),
        "catalog": [{"key": key, "label": label} for key, label in PATIENT_REPORT_ITEMS],
        "patientResultsEnabled": _patient_results_enabled(patient),
        "patientId": str((patient or {}).get("id") or ""),
    }


@app.get("/api/session-reports/{session_id}/metrics")
async def get_session_report_metrics(session_id: str, request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    report = _load_session_reports().get(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    request_context = _tenant_context_from_request(request)
    if (
        request_context
        and _report_organization_id(report) != request_context.organization_id
    ):
        raise HTTPException(status_code=403, detail="relatório pertence a outra organização")
    assigned_report_ids = (
        TENANT_STORE.accessible_legacy_report_ids(
            organization_id=request_context.organization_id,
            membership_id=request_context.membership_id,
        )
        if request_context else set()
    )
    context = _authorize_tenant_request(
        request,
        "reports.read",
        resource_type="session_report",
        resource_id=session_id,
        resource_organization_id=_report_organization_id(report),
        assigned=session_id in assigned_report_ids,
        owns_resource=_can_access_report(report, user.get("email") or ""),
        context_override=request_context,
    )
    if not _can_access_report(report, user.get("email") or ""):
        if _tenant_authorization_mode_for(_report_organization_id(report)) != "enforce":
            raise HTTPException(status_code=403, detail="Relatório pertence a outro profissional")
    report = _enrich_report_patient(report)
    if not report.get("metricsAnalysis"):
        report = _attach_metrics_analysis(report)
    if report.get("metricsAnalysisError") and not report.get("metricsAnalysis"):
        raise HTTPException(status_code=500, detail=report["metricsAnalysisError"])
    _record_tenant_success(context, "report.metrics.read", "session_report", session_id)
    return report.get("metricsAnalysis")


@app.get("/api/session-reports/{session_id}")
async def get_session_report(session_id: str, request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    report = _load_session_reports().get(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    request_context = _tenant_context_from_request(request)
    if (
        request_context
        and _report_organization_id(report) != request_context.organization_id
    ):
        raise HTTPException(status_code=403, detail="relatório pertence a outra organização")
    assigned_report_ids = (
        TENANT_STORE.accessible_legacy_report_ids(
            organization_id=request_context.organization_id,
            membership_id=request_context.membership_id,
        )
        if request_context else set()
    )
    context = _authorize_tenant_request(
        request,
        "reports.read",
        resource_type="session_report",
        resource_id=session_id,
        resource_organization_id=_report_organization_id(report),
        assigned=session_id in assigned_report_ids,
        owns_resource=_can_access_report(report, user.get("email") or ""),
        context_override=request_context,
    )
    if not _can_access_report(report, user.get("email") or ""):
        if _tenant_authorization_mode_for(_report_organization_id(report)) != "enforce":
            raise HTTPException(status_code=403, detail="Relatório pertence a outro profissional")
    report = _enrich_report_patient(report)
    if not report.get("metricsAnalysis"):
        report = _attach_metrics_analysis(report)
    _record_tenant_success(context, "report.read", "session_report", session_id)
    return _report_for_api(report)


@app.delete("/api/session-reports/{session_id}")
async def delete_session_report(session_id: str, request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="não autenticado")
    reports = _load_session_reports()
    if session_id not in reports:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    request_context = _tenant_context_from_request(request)
    if (
        request_context
        and _report_organization_id(reports[session_id])
        != request_context.organization_id
    ):
        raise HTTPException(status_code=403, detail="relatório pertence a outra organização")
    context = _authorize_tenant_request(
        request,
        "reports.delete",
        resource_type="session_report",
        resource_id=session_id,
        resource_organization_id=_report_organization_id(reports[session_id]),
        owns_resource=_can_access_report(reports[session_id], user.get("email") or ""),
        context_override=request_context,
    )
    if not _can_access_report(reports[session_id], user.get("email") or ""):
        if _tenant_authorization_mode_for(
            _report_organization_id(reports[session_id])
        ) != "enforce":
            raise HTTPException(status_code=403, detail="Relatório pertence a outro profissional")
    del reports[session_id]
    _save_session_reports(reports)
    if context:
        try:
            TENANT_STORE.mark_mirrored_report_deleted(
                organization_id=context.organization_id,
                session_id=session_id,
            )
        except Exception:
            LOGGER.exception("Unable to delete mirrored session report")
    _record_tenant_success(context, "report.delete", "session_report", session_id)
    return {
        "status": "deleted",
        "session_id": session_id,
        "note": "Relatorio identificado removido. Registros anonimizados agregados nao contem PII.",
    }


@app.post("/api/insights")
async def insights_proxy(request: Request):
    _require_professional_feature_access(request)
    try:
        body = await request.json()
        raw_messages = body.get("messages") if isinstance(body, dict) else []
        if not isinstance(raw_messages, list):
            raise HTTPException(status_code=400, detail="mensagens inválidas")
        messages = []
        total_chars = 0
        for item in raw_messages[-20:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "user").strip().lower()
            if role not in {"system", "user", "assistant"}:
                continue
            content = str(item.get("content") or "")[:12_000]
            total_chars += len(content)
            if total_chars > 50_000:
                raise HTTPException(status_code=413, detail="contexto de insights muito extenso")
            messages.append({"role": role, "content": content})
        if not OPENAI_API_KEY:
            fallback = messages[-1]["content"] if messages else "Sem resposta."
            return {"choices": [{"message": {"content": f"[FROID-IA local] {fallback}"}}]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": OPENAI_MODEL, "messages": messages, "temperature": 0.4, "max_tokens": 700}
            )
            if r.status_code >= 400:
                raise RuntimeError(f"OpenAI insights status {r.status_code}")
            return r.json()
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("FROID insights request failed")
        raise HTTPException(status_code=502, detail="Falha ao processar insights")

@app.get("/api/knowledge")
async def knowledge_base(request: Request, q: str = ""):
    _require_professional_feature_access(request)
    results = []
    qlower = q.lower()
    for k, v in KNOWLEDGE_BASE.items():
        if qlower in k or qlower in v.lower() or not q:
            results.append({"source": k, "content": v})
    return {"query": q, "results": results}

@app.post("/api/transcribe")
async def transcribe_audio(request: Request):
    """Endpoint de transcrição vocal com fallback local para uso clínico e testes."""
    _require_professional_feature_access(request)
    body = await request.json()
    fallback_text = body.get("fallback_text") or body.get("text") or ""
    audio_bytes = _decode_audio_bytes(body)
    if audio_bytes and len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="segmento de áudio excede 25 MB")
    filename = _audio_filename(body)
    spoken_language = normalize_session_locale(body.get("spoken_language"))
    prompt = transcription_prompt(
        spoken_language,
        body.get("previous_context"),
    )
    started_at = time.perf_counter()
    try:
        transcript, error = await _transcribe_with_openai(
            audio_bytes,
            fallback_text,
            filename,
            prompt,
            spoken_language,
        )
    except Exception:
        LOGGER.exception("FROID transcription provider failure")
        transcript, error = fallback_text, "serviço de transcrição indisponível"
    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    provider = (
        f"openai-{OPENAI_TRANSCRIBE_MODEL}"
        if OPENAI_API_KEY and audio_bytes and not error
        else "local-fallback"
    )
    status = "ok" if transcript and not error else "empty" if not error else "error"
    AUDIT_LOGGER.info(
        json.dumps(
            {
                "event": "froid.transcription",
                "session_id": str(body.get("session_id") or ""),
                "status": status,
                "provider": provider,
                "spoken_language": spoken_language,
                "audio_bytes": len(audio_bytes or b""),
                "latency_ms": latency_ms,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return {
        "status": status,
        "text": transcript or fallback_text,
        "provider": provider,
        "model": OPENAI_TRANSCRIBE_MODEL,
        "spoken_language": spoken_language,
        "filename": filename,
        "latency_ms": latency_ms,
        "audio_bytes": len(audio_bytes or b""),
        "error": error,
    }

@app.post("/api/session-summary")
async def session_summary(request: Request):
    _require_professional_feature_access(request)
    body = await request.json()
    transcript = str(body.get("transcript") or "").strip()
    start_minute = int(body.get("start_minute") or 0)
    end_minute = int(body.get("end_minute") or start_minute + 10)
    spoken_language = normalize_session_locale(body.get("spoken_language"))
    analysis_language = normalize_session_locale(
        body.get("analysis_language"), spoken_language
    )
    output_locale = normalize_session_locale(
        body.get("report_locale"), analysis_language
    )
    output_language = session_language(output_locale)

    if not transcript:
        return {
            "status": "empty",
            "theme": output_language.no_speech_theme,
            "summary": output_language.no_speech_summary,
            "start_minute": start_minute,
            "end_minute": end_minute,
            "model": OPENAI_MODEL,
            "spoken_language": spoken_language,
            "analysis_language": analysis_language,
            "report_locale": output_locale,
            "summary_locale": output_locale,
        }

    fallback = {
        "status": "fallback",
        "theme": output_language.pending_theme,
        "summary": _limit_words(transcript, 80),
        "start_minute": start_minute,
        "end_minute": end_minute,
        "model": OPENAI_MODEL,
        "spoken_language": spoken_language,
        "analysis_language": analysis_language,
        "report_locale": output_locale,
        "summary_locale": spoken_language,
    }

    if not OPENAI_API_KEY:
        return fallback

    prompt = summary_prompt(transcript, start_minute, end_minute, output_locale)

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
                            "content": summary_system_prompt(output_locale),
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
        theme = _limit_words(str(parsed.get("theme") or fallback["theme"]).strip(), 6)
        summary_text = str(parsed.get("summary") or fallback["summary"]).strip()
        return {
            "status": "ok",
            "theme": theme,
            "summary": _limit_words(summary_text, 80),
            "start_minute": start_minute,
            "end_minute": end_minute,
            "model": OPENAI_MODEL,
            "spoken_language": spoken_language,
            "analysis_language": analysis_language,
            "report_locale": output_locale,
            "summary_locale": output_locale,
        }
    except Exception:
        return fallback
