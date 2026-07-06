import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
import secrets
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from froid_core import SessionState, MockBiometricStream
from froid_metrics_engine import calculate_report_metrics
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FROID_EXPLICA_MODEL = os.getenv("FROID_EXPLICA_MODEL", "gemini-1.5-pro")
FROID_CHROMA_PATH = os.getenv("FROID_CHROMA_PATH", "/data/chroma_db")
FROID_CHROMA_COLLECTION = os.getenv(
    "FROID_CHROMA_COLLECTION",
    "froid_clinical_knowledge",
)
FROID_DUCKDB_PATH = os.getenv(
    "FROID_DUCKDB_PATH",
    "/data/datamart_anonymous.duckdb",
)
FROID_ALGORITHM_VERSION = os.getenv("FROID_ALGORITHM_VERSION", app.version)
FROID_ANALYTICS_MIN_K = int(os.getenv("FROID_ANALYTICS_MIN_K", "50") or "50")
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
GOOGLE_AUTH_DEV_FALLBACK = os.getenv("GOOGLE_AUTH_DEV_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}
GOOGLE_CALENDAR_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
FROID_LOCAL_AUTH_PASSWORD = os.getenv("FROID_LOCAL_AUTH_PASSWORD", "")
FROID_LOCAL_AUTH_EMAILS = {
    email.strip().lower()
    for email in os.getenv("FROID_LOCAL_AUTH_EMAILS", "").split(",")
    if email.strip()
}
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "brl")

SESSION_USERS = {}
PROFESSIONAL_PROFILES: Dict[str, dict] = {}
PATIENTS: Dict[str, dict] = {}
PATIENTS_BY_CONTACT: Dict[str, str] = {}
SESSION_INVITES: Dict[str, dict] = {}
CONSENT_LEDGER: list[dict] = []
PATIENT_SESSION_ENTRIES: Dict[str, list[dict]] = {}
SESSION_EVENTS: list[dict] = []
SESSION_EVENT_COUNTER = 0
GOOGLE_CALENDAR_CONNECTIONS: Dict[str, dict] = {}
GOOGLE_CALENDAR_OAUTH_STATES: Dict[str, dict] = {}
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
    if email:
        keys.append(f"email:{email}")
    if phone:
        keys.append(f"phone:{phone}")
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
    global PATIENTS
    global PATIENTS_BY_CONTACT
    global SESSION_INVITES
    global CONSENT_LEDGER
    global PATIENT_SESSION_ENTRIES
    global SESSION_EVENTS
    global SESSION_EVENT_COUNTER
    global GOOGLE_CALENDAR_CONNECTIONS

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
    if isinstance(raw_invites, dict):
        SESSION_INVITES = {
            str(token): invite
            for token, invite in raw_invites.items()
            if token and isinstance(invite, dict)
        }

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

    max_event_id = max(
        [_local_int(event.get("id")) for event in SESSION_EVENTS if isinstance(event, dict)]
        or [0]
    )
    SESSION_EVENT_COUNTER = max(_local_int(state.get("session_event_counter")), max_event_id)

    raw_calendar_connections = state.get("google_calendar_connections")
    if isinstance(raw_calendar_connections, dict):
        GOOGLE_CALENDAR_CONNECTIONS = {
            _local_normalize_email(email): connection
            for email, connection in raw_calendar_connections.items()
            if _local_normalize_email(email) and isinstance(connection, dict)
        }


def _identity_state_snapshot() -> dict:
    return {
        "schema_version": "froid-identity-state-v1",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "professional_profiles": PROFESSIONAL_PROFILES,
        "patients": PATIENTS,
        "patients_by_contact": PATIENTS_BY_CONTACT,
        "session_invites": SESSION_INVITES,
        "consent_ledger": CONSENT_LEDGER[-2000:],
        "patient_session_entries": PATIENT_SESSION_ENTRIES,
        "session_events": SESSION_EVENTS[-500:],
        "session_event_counter": SESSION_EVENT_COUNTER,
        "google_calendar_connections": GOOGLE_CALENDAR_CONNECTIONS,
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


_load_identity_state()

KNOWLEDGE_BASE = {
    "froid_zonas": "As 12 Zonas de Percepcao FROID organizam padroes de desequilibrio facial-vocal e orientam a leitura clinica por temas, tensoes e dissonancias.",
    "ipm_velocimetro": "O IPM indica a intensidade ou energia global da sessao. Ele funciona como velocimetro emocional e nao define sozinho a direcao do desequilibrio.",
    "idm_direcao": "O IDM aponta a direcao do desequilibrio entre marcadores negativos e positivos, enquanto o IPM mede a energia global empregada.",
    "mfcc7_depressao": "MFCC7 elevado durante conteudos semanticamente negativos, associado a pausas, menor variacao de F0 e retardo psicomotor, contribui para risco depressivo.",
    "mfcc9_ansiedade": "MFCC9 em discurso neutro pode ter relacao inversa com ansiedade somatica; quedas acusticas podem indicar tensao autonoma latente.",
    "shimmer_bioacustico": "Shimmer mede perturbacao ciclo-a-ciclo da amplitude vocal. No FROID, deve ser interpretado contra baseline individual, cortes temporais, Jitter, F0, ZCR, energia, pausas, tema semantico e dissonancias; isoladamente nao define estado emocional.",
    "jitter_bioacustico": "Jitter mede perturbacao ciclo-a-ciclo da frequencia fundamental. Quando sustentado junto a Shimmer, alteracoes de F0, pausas e tensao vocal, pode apoiar hipotese de instabilidade laringea ou carga autonomica.",
    "f0_bioacustico": "F0 e a frequencia fundamental da voz. Elevacoes, quedas ou reducao de variabilidade devem ser comparadas ao baseline de 60 segundos e ao contexto semantico da fala.",
    "zcr_bioacustico": "ZCR, taxa de cruzamento por zero, apoia leitura de aspereza, ruido, energia de alta frequencia e alteracoes acusticas quando combinado a MFCCs, F0, Jitter e Shimmer.",
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


class FroidExplicaResponse(BaseModel):
    result_text: str
    engine_used: str
    citations: List[str] = Field(default_factory=list)
    safety_check_passed: bool
    intent: str = "knowledge"


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


def _query_local_froid_knowledge(query_text: str, limit: int = 4) -> Tuple[List[str], List[str]]:
    query = _normalize_search_text(query_text)
    tokens = {token for token in re.split(r"\W+", query) if len(token) >= 4}
    ranked: List[Tuple[int, str, str]] = []
    for source, content in KNOWLEDGE_BASE.items():
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
        collection = chroma_client.get_or_create_collection(
            name=FROID_CHROMA_COLLECTION
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
        return [], []


def _format_session_context(context: Dict[str, Any]) -> str:
    if not context:
        return "Sem contexto de sessao enviado pelo painel."
    safe_context = {
        key: value
        for key, value in context.items()
        if key not in {"patient_name", "email", "phone", "document"}
    }
    return json.dumps(safe_context, ensure_ascii=False, indent=2)[:5000]


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
            "Shimmer mede perturbacao ciclo-a-ciclo da amplitude vocal, isto e, a instabilidade da intensidade da voz entre ciclos sucessivos de fonacao.",
            "No FROID, o Shimmer deve ser comparado ao baseline individual e aos cortes posteriores. Ele se torna mais informativo quando aparece junto de Jitter, alteracoes de F0, energia, pausas, ZCR, tensao vocal ou dissonancias faciais-vocais.",
            "Use o Shimmer para observar esforco vocal, instabilidade autonomica possivel, tensao afetiva ou controle emocional excessivo. Em atendimento, ele pode orientar perguntas mais finas sobre carga emocional no trecho em que a amplitude vocal se tornou instavel.",
            "Base local FROID: shimmer_bioacustico; Referencia cientifica: Boersma e Weenink/Praat para analise acustica vocal.",
        )

    if "jitter" in query:
        return _metric_response(
            "Jitter",
            {"jitter", "jitter_avg", "average_jitter", "jittermean"},
            "Jitter mede perturbacao ciclo-a-ciclo da frequencia fundamental, refletindo instabilidade fina da fonacao.",
            "No FROID, Jitter ganha relevancia quando aparece sustentado com Shimmer, alteracoes de F0, pausas, tensao vocal, queda de fluidez ou mudanca de tom emocional.",
            "Use o Jitter como apoio para investigar instabilidade laringea, carga autonomica ou esforco de controle emocional, sempre relacionando com o conteudo verbal e com o baseline.",
            "Base local FROID: jitter_bioacustico; Referencia cientifica: Boersma e Weenink/Praat para analise acustica vocal.",
        )

    if "zcr" in query or "cruzamento por zero" in query:
        return _metric_response(
            "ZCR",
            {"zcr", "zcr_avg", "average_zcr", "zcrmean"},
            "ZCR e a taxa de cruzamento por zero do sinal acustico, usada para observar caracteristicas de ruido, aspereza e energia de alta frequencia.",
            "No FROID, ZCR deve ser lido junto de MFCCs, F0, Jitter, Shimmer, pausas e intensidade. Alteracoes isoladas podem refletir artefato, microfone, fricativas ou mudanca real de qualidade vocal.",
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
    operational_result = _operational_fallback_result(
        payload.query_text,
        payload.context,
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
    context_chunks = chroma_docs or local_docs
    context_labels = chroma_citations or local_citations
    citations = _scientific_citations(context_labels)
    context_str = "\n\n".join(
        f"[Fonte: {source}]\n{doc}"
        for source, doc in zip(context_labels, context_chunks)
    )
    session_context = _format_session_context(payload.context)
    conversation_history = _format_conversation_history(payload.conversation_history)
    system_instruction = (
        "Voce e o FROID Explica, uma inteligencia clinica de apoio ao profissional. "
        "Responda em portugues do Brasil, de modo objetivo, sem diagnosticar e sem inventar. "
        "Use estritamente o contexto cientifico disponivel, o contexto da sessao e o historico "
        "conversacional. Se a pergunta for de seguimento, como 'quais fontes?', responda sobre "
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
        f"CONTEXTO DA SESSAO ATUAL:\n{session_context}\n\n"
        f"HISTORICO RECENTE DO FROID EXPLICA:\n{conversation_history}\n\n"
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
        raise HTTPException(status_code=400, detail="SQL bloqueado: apenas SELECT e WITH sao permitidos")
    if ";" in sql:
        raise HTTPException(status_code=400, detail="SQL bloqueado: multiplas instrucoes nao sao permitidas")
    if SQL_FORBIDDEN_RE.search(sql):
        raise HTTPException(status_code=400, detail="SQL bloqueado por conter comando nao permitido")
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
        "session_kind VARCHAR, treatment_phase VARCHAR, session_ordinal INTEGER, "
        "interval_since_previous_days DOUBLE, baseline_ipm DOUBLE, baseline_idm DOUBLE, "
        "baseline_zone INTEGER, baseline_tone VARCHAR, baseline_words_per_minute DOUBLE, "
        "average_idm DOUBLE, average_words_per_minute DOUBLE, dissonance_count INTEGER, "
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
        "f0_mean DOUBLE, zcr DOUBLE, jitter DOUBLE, shimmer DOUBLE, subharmonic_5_12 DOUBLE, "
        "subharmonic_12_20 DOUBLE, cut_trigger VARCHAR, cut_summary_anon VARCHAR, "
        "patient_summary_anon VARCHAR, professional_summary_anon VARCHAR, patient_word_count INTEGER, "
        "professional_word_count INTEGER, intervention_category VARCHAR, patient_response VARCHAR, "
        "ipm_delta_from_baseline DOUBLE, idm_delta_from_baseline DOUBLE, "
        "dissonance_delta_from_baseline DOUBLE, ipm_delta_previous_cut DOUBLE, "
        "idm_delta_previous_cut DOUBLE, dissonance_delta_previous_cut DOUBLE, risk_score DOUBLE, "
        "quality_confidence DOUBLE, stt_model VARCHAR, llm_model VARCHAR, algorithm_version VARCHAR, "
        "audio_quality VARCHAR, theme_predominant VARCHAR, relevant_dissonances VARCHAR, "
        "aggregated_clinical_risk DOUBLE, ipm_delta_after_intervention DOUBLE, "
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

    if cohort_size < FROID_ANALYTICS_MIN_K:
        try:
            conn.close()
        except Exception:
            pass
        return FroidExplicaResponse(
            result_text=(
                "Acesso bloqueado por governanca de dados e LGPD. "
                f"A coorte resultante contem {cohort_size} registros, abaixo do minimo "
                f"k >= {FROID_ANALYTICS_MIN_K}. Refine para uma coorte maior ou use apenas leitura qualitativa da sessao atual."
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


def _load_session_reports() -> Dict[str, dict]:
    try:
        if not os.path.exists(FROID_SESSION_REPORTS_PATH):
            return {}
        with open(FROID_SESSION_REPORTS_PATH, "r", encoding="utf-8") as report_file:
            data = json.load(report_file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_session_reports(reports: Dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(FROID_SESSION_REPORTS_PATH), exist_ok=True)
    with open(FROID_SESSION_REPORTS_PATH, "w", encoding="utf-8") as report_file:
        json.dump(reports, report_file, ensure_ascii=False, indent=2)


def _professional_access_status(email: str) -> dict:
    owner_email = _normalize_email(email)
    profile = PROFESSIONAL_PROFILES.get(owner_email) if owner_email else None
    selected_plan = str((profile or {}).get("selected_plan") or "").strip()
    lgpd_acknowledged = bool((profile or {}).get("lgpd_acknowledged"))
    has_profile = bool(profile)
    access_ready = has_profile and lgpd_acknowledged and bool(selected_plan)
    total_sessions = max(0, _local_int((profile or {}).get("total_sessions")))
    used_sessions = max(0, _local_int((profile or {}).get("used_sessions")))
    remaining_sessions = max(
        0,
        _local_int((profile or {}).get("remaining_sessions") if profile else 0)
        if (profile or {}).get("remaining_sessions") is not None
        else total_sessions - used_sessions,
    )
    return {
        "has_profile": has_profile,
        "lgpd_acknowledged": lgpd_acknowledged,
        "selected_plan": selected_plan,
        "payment_status": str((profile or {}).get("payment_status") or ("pending_checkout" if access_ready else "not_started")),
        "onboarding_required": not access_ready,
        "total_sessions": total_sessions,
        "used_sessions": used_sessions,
        "remaining_sessions": remaining_sessions,
        "admin": _is_admin_email(owner_email),
    }


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

    total_sessions = max(0, _local_int(profile.get("total_sessions")))
    used_sessions = max(0, _local_int(profile.get("used_sessions"))) + 1
    profile["used_sessions"] = used_sessions
    profile["remaining_sessions"] = max(0, total_sessions - used_sessions)
    profile["last_session_consumed_at"] = _utc_now_iso()
    profile["consumed_session_ids"] = [*consumed, session_id][-500:]
    PROFESSIONAL_PROFILES[email] = profile
    _save_identity_state()
    return _professional_access_status(email)


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


def _can_access_invite_finance(invite: dict, owner_email: str) -> bool:
    invite_owner = _normalize_email(invite.get("professional_email") or "")
    if invite_owner:
        return invite_owner == _normalize_email(owner_email)
    return _normalize_email(owner_email) == _normalize_email(FROID_LEGACY_REPORT_OWNER)


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
    raw = f"{report.get('sessionId') or report.get('session_id') or ''}:{report.get('createdAt') or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _anonymous_cut_hash(session_hash: str, cut_index: int, start_second: int, end_second: int) -> str:
    raw = f"{session_hash}:{cut_index}:{start_second}:{end_second}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    try:
        import duckdb

        os.makedirs(os.path.dirname(FROID_DUCKDB_PATH), exist_ok=True)
        conn = duckdb.connect(database=FROID_DUCKDB_PATH, read_only=False)
        session_hash = _anonymous_session_hash(report)
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
                media_loss_events INTEGER
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
                subharmonic_5_12 DOUBLE,
                subharmonic_12_20 DOUBLE,
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
                risk_score DOUBLE,
                quality_confidence DOUBLE,
                stt_model VARCHAR,
                llm_model VARCHAR,
                algorithm_version VARCHAR,
                audio_quality VARCHAR,
                theme_predominant VARCHAR,
                relevant_dissonances VARCHAR,
                aggregated_clinical_risk DOUBLE,
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
                "risk_score": "DOUBLE",
                "quality_confidence": "DOUBLE",
                "stt_model": "VARCHAR",
                "llm_model": "VARCHAR",
                "algorithm_version": "VARCHAR",
                "audio_quality": "VARCHAR",
                "theme_predominant": "VARCHAR",
                "relevant_dissonances": "VARCHAR",
                "aggregated_clinical_risk": "DOUBLE",
                "ipm_delta_after_intervention": "DOUBLE",
                "idm_delta_after_intervention": "DOUBLE",
                "dissonance_delta_after_intervention": "DOUBLE",
                "dominant_zone_shift": "VARCHAR",
                "emotional_tone_shift": "VARCHAR",
                "cadence_shift": "VARCHAR",
                "semantic_coherence_shift": "VARCHAR",
                "biomarker_snapshot_json": "VARCHAR",
                "subharmonic_snapshot_json": "VARCHAR",
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
        average = report.get("sessionAverage") or {}
        baseline = report.get("baseline") or {}
        context = _session_context(report)
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
        audio_quality = str(context.get("audio_quality") or context.get("audioQuality") or "nao_informada")
        consent_research = _safe_bool(
            context.get("consent_anonymous_research")
            or context.get("consentAnonymousResearch")
            or report.get("consentAnonymousResearch"),
            True,
        )
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
                session_modality, session_kind, treatment_phase, session_ordinal,
                interval_since_previous_days, baseline_ipm, baseline_idm, baseline_zone,
                baseline_tone, baseline_words_per_minute, average_idm,
                average_words_per_minute, dissonance_count, cuts_count,
                clinical_notes_count, summary_theme, summary_text_anon, stt_model,
                llm_model, algorithm_version, audio_quality, media_interruptions,
                confidence_score, consent_anonymous_research
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session_hash,
                _safe_str(context.get("age_bucket") or context.get("ageBucket") or "unknown", 64),
                _safe_str(context.get("gender") or "unknown", 64),
                _safe_float(average.get("ipmAvg")),
                _safe_int(dominant_zone),
                _safe_float(vocal_tension),
                _safe_bool(context.get("ssri_medication") or context.get("ssriMedication"), False),
                _safe_int(report.get("durationSeconds")),
                "anonymous_datamart_v2",
                _safe_str(report.get("createdAt") or datetime.now(timezone.utc).isoformat(), 80),
                _safe_str(context.get("session_modality") or context.get("sessionModality") or "unknown", 80),
                _safe_str(context.get("session_kind") or context.get("sessionKind") or "seguimento", 80),
                _safe_str(context.get("treatment_phase") or context.get("treatmentPhase") or "nao_informada", 80),
                _safe_int(context.get("session_ordinal") or context.get("sessionOrdinal")),
                _safe_float(context.get("interval_since_previous_days") or context.get("intervalSincePreviousDays")),
                _safe_float(baseline.get("ipmAvg")),
                _safe_float(baseline.get("idmAvg")),
                _safe_int(baseline.get("dominantZone")),
                _safe_str(baseline.get("emotionalTone") or "", 80),
                _safe_float(baseline.get("wordsPerMinute")),
                _safe_float(average.get("idmAvg")),
                _safe_float(average.get("wordsPerMinute")),
                _safe_int(average.get("dissonanceCount")),
                len(ten_minute_cuts),
                len(report.get("clinicalNotes") or []),
                _safe_str(session_summary.get("theme") or average.get("theme") or "", 180),
                _limit_words(_safe_str(session_summary.get("summary") or "", 3000), 150),
                _safe_str(context.get("stt_model") or context.get("sttModel") or OPENAI_TRANSCRIBE_MODEL, 120),
                _safe_str(context.get("llm_model") or context.get("llmModel") or FROID_EXPLICA_MODEL, 120),
                _safe_str(context.get("algorithm_version") or context.get("algorithmVersion") or FROID_ALGORITHM_VERSION, 80),
                _safe_str(audio_quality, 80),
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
                media_loss_events = ?
            WHERE session_hash = ?
            """,
            [
                _safe_str(context.get("session_type") or context.get("sessionType") or context.get("session_kind") or context.get("sessionKind"), 80),
                _safe_int(context.get("previous_sessions_count") or context.get("previousSessionsCount")),
                _safe_float(context.get("delta_ipm_from_session_baseline") or context.get("deltaIpmFromSessionBaseline")),
                _safe_float(context.get("delta_idm_from_session_baseline") or context.get("deltaIdmFromSessionBaseline")),
                _safe_float(context.get("delta_ipm_vs_last3") or context.get("deltaIpmVsLast3")),
                _safe_float(context.get("delta_idm_vs_last3") or context.get("deltaIdmVsLast3")),
                _safe_float(context.get("delta_ipm_vs_historical") or context.get("deltaIpmVsHistorical")),
                _safe_float(context.get("delta_idm_vs_historical") or context.get("deltaIdmVsHistorical")),
                _safe_str(context.get("longitudinal_trend") or context.get("longitudinalTrend") or "nao_apurado", 80),
                _safe_str(context.get("emotional_stability") or context.get("emotionalStability") or "nao_apurada", 80),
                _safe_str(json.dumps(context.get("recurring_themes") or context.get("recurringThemes") or [], ensure_ascii=False), 1200),
                _safe_str(json.dumps(context.get("recurring_zones") or context.get("recurringZones") or [], ensure_ascii=False), 1200),
                _safe_str(json.dumps(context.get("recurring_risks") or context.get("recurringRisks") or [], ensure_ascii=False), 1200),
                _safe_str(context.get("metrics_version") or context.get("metricsVersion") or "froid-metrics-v3", 80),
                _safe_str(context.get("weights_version") or context.get("weightsVersion") or "froid-weights-v1", 80),
                _safe_str(context.get("privacy_tier") or context.get("privacyTier") or "anonymous_research_datamart", 120),
                _safe_bool(context.get("pii_excluded") or context.get("piiExcluded"), True),
                _safe_bool(context.get("raw_audio_retained") or context.get("rawAudioRetained"), False),
                _safe_bool(context.get("literal_transcript_retained") or context.get("literalTranscriptRetained"), False),
                _safe_int(context.get("media_loss_events") or context.get("mediaLossEvents") or context.get("media_interruptions") or context.get("mediaInterruptions")),
                session_hash,
            ],
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
            intervention_category = _safe_str(
                cut_context.get("intervention_category")
                or cut_context.get("interventionCategory")
                or _infer_intervention_category(professional_text),
                120,
            )
            patient_response = _safe_str(
                cut_context.get("patient_response")
                or cut_context.get("patientResponse")
                or _infer_patient_response(cut, previous_cut, baseline),
                120,
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
                    subharmonic_5_12, subharmonic_12_20, cut_trigger,
                    cut_summary_anon, patient_summary_anon, professional_summary_anon,
                    patient_word_count, professional_word_count, intervention_category,
                    patient_response, ipm_delta_from_baseline, idm_delta_from_baseline,
                    dissonance_delta_from_baseline, ipm_delta_previous_cut,
                    idm_delta_previous_cut, dissonance_delta_previous_cut, risk_score,
                    quality_confidence, stt_model, llm_model, algorithm_version, audio_quality
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    session_hash,
                    index,
                    str(cut.get("label") or ""),
                    start_second,
                    end_second,
                    _safe_int(cut.get("sampleCount")),
                    _safe_float(cut.get("ipmAvg")),
                    _safe_float(cut.get("idmAvg")),
                    _safe_int(cut.get("dominantZone")),
                    str(cut.get("dominantTheme") or ""),
                    str(cut.get("coherenceStatus") or ""),
                    str(cut.get("emotionalTone") or ""),
                    _safe_float(cut.get("wordsPerMinute")),
                    str(cut.get("theme") or ""),
                    _safe_int(cut.get("dissonanceCount")),
                    _safe_float(cut.get("mfcc7")),
                    _safe_float(cut.get("mfcc9")),
                    _safe_float(cut.get("f0Mean")),
                    _safe_float(cut.get("zcr")),
                    _safe_float(cut.get("jitter")),
                    _safe_float(cut.get("shimmer")),
                    _safe_float(cut.get("subharmonic5_12")),
                    _safe_float(cut.get("subharmonic12_20")),
                    _safe_str(cut_context.get("cut_trigger") or cut_context.get("cutTrigger") or "automatico_10min", 80),
                    _limit_words(_safe_str(summary.get("summary") or cut.get("theme") or "", 3000), 120),
                    _limit_words(_safe_str(cut_context.get("patient_summary_anon") or cut_context.get("patientSummaryAnon") or patient_text, 3000), 120),
                    _limit_words(_safe_str(cut_context.get("professional_summary_anon") or cut_context.get("professionalSummaryAnon") or professional_text, 3000), 120),
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
                    _safe_float((report.get("metricsAnalysis") or {}).get("dashboard", {}).get("max_risk")),
                    _cut_confidence(cut),
                    _safe_str(cut_context.get("stt_model") or cut_context.get("sttModel") or OPENAI_TRANSCRIBE_MODEL, 120),
                    _safe_str(cut_context.get("llm_model") or cut_context.get("llmModel") or FROID_EXPLICA_MODEL, 120),
                    _safe_str(cut_context.get("algorithm_version") or cut_context.get("algorithmVersion") or FROID_ALGORITHM_VERSION, 80),
                    _safe_str(cut_context.get("audio_quality") or cut_context.get("audioQuality") or audio_quality, 80),
                ],
            )
            biomarker_snapshot = {
                "mfcc7": cut.get("mfcc7"),
                "mfcc9": cut.get("mfcc9"),
                "f0_mean": cut.get("f0Mean"),
                "zcr": cut.get("zcr"),
                "jitter": cut.get("jitter"),
                "shimmer": cut.get("shimmer"),
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
            previous_context_label = (
                f"cut_{index - 1}:{previous_cut.get('theme') or previous_cut.get('dominantTheme') or 'sem_tema'}"
                if previous_cut
                else "baseline"
            )
            next_cut = ten_minute_cuts[index + 1] if index + 1 < len(ten_minute_cuts) else None
            next_context_label = (
                f"cut_{index + 1}:{next_cut.get('theme') or next_cut.get('dominantTheme') or 'sem_tema'}"
                if isinstance(next_cut, dict)
                else "fim_sessao"
            )
            cut_context_vector = {
                "schema": "anonymous_cut_context_v1",
                "cut_hash": cut_hash,
                "cut_index": index,
                "cut_label": str(cut.get("label") or ""),
                "time": {
                    "start_second": start_second,
                    "end_second": end_second,
                    "duration_seconds": duration_seconds,
                    "relative_position": relative_position,
                    "trigger": _safe_str(cut_context.get("cut_trigger") or cut_context.get("cutTrigger") or "automatico_10min", 80),
                },
                "semantic": {
                    "theme": cut.get("theme") or "",
                    "theme_predominant": cut_context.get("theme_predominant") or cut_context.get("themePredominant") or cut.get("theme") or "",
                    "coherence_status": cut.get("coherenceStatus") or "",
                    "patient_word_count": patient_word_count,
                    "professional_word_count": professional_word_count,
                    "speech_density": speech_density,
                    "patient_professional_word_ratio": patient_professional_word_ratio,
                },
                "intervention": {
                    "category": intervention_category,
                    "patient_response": patient_response,
                    "response_ipm_direction": cut_context.get("response_ipm_direction") or cut_context.get("responseIpmDirection") or "nao_apurado",
                    "response_idm_direction": cut_context.get("response_idm_direction") or cut_context.get("responseIdmDirection") or "nao_apurado",
                    "response_dissonance_direction": cut_context.get("response_dissonance_direction") or cut_context.get("responseDissonanceDirection") or "nao_apurado",
                },
                "metrics": {
                    "ipm_avg": cut.get("ipmAvg"),
                    "idm_avg": cut.get("idmAvg"),
                    "dominant_zone": cut.get("dominantZone"),
                    "dominant_theme": cut.get("dominantTheme"),
                    "emotional_tone": cut.get("emotionalTone"),
                    "words_per_minute": cut.get("wordsPerMinute"),
                    "dissonance_count": cut.get("dissonanceCount"),
                    "risk_score": _safe_float((report.get("metricsAnalysis") or {}).get("dashboard", {}).get("max_risk")),
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
                    "audio_quality": _safe_str(cut_context.get("audio_quality") or cut_context.get("audioQuality") or audio_quality, 80),
                    "media_loss_events": _safe_int(cut_context.get("media_loss_events") or cut_context.get("mediaLossEvents") or context.get("media_loss_events") or context.get("mediaLossEvents")),
                    "stt_model": _safe_str(cut_context.get("stt_model") or cut_context.get("sttModel") or OPENAI_TRANSCRIBE_MODEL, 120),
                    "llm_model": _safe_str(cut_context.get("llm_model") or cut_context.get("llmModel") or FROID_EXPLICA_MODEL, 120),
                    "algorithm_version": _safe_str(cut_context.get("algorithm_version") or cut_context.get("algorithmVersion") or FROID_ALGORITHM_VERSION, 80),
                },
            }
            conn.execute(
                """
                UPDATE anonymous_session_cuts SET
                    cut_hash = ?, duration_seconds = ?, relative_position = ?,
                    speech_density = ?, patient_professional_word_ratio = ?,
                    theme_predominant = ?, relevant_dissonances = ?,
                    aggregated_clinical_risk = ?, ipm_delta_after_intervention = ?,
                    idm_delta_after_intervention = ?, dissonance_delta_after_intervention = ?,
                    dominant_zone_shift = ?, emotional_tone_shift = ?, cadence_shift = ?,
                    semantic_coherence_shift = ?, biomarker_snapshot_json = ?,
                    subharmonic_snapshot_json = ?, cut_context_json = ?,
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
                    _safe_str(cut_context.get("theme_predominant") or cut_context.get("themePredominant") or cut.get("theme") or "", 180),
                    _safe_str(cut_context.get("relevant_dissonances") or cut_context.get("relevantDissonances") or "", 500),
                    _safe_float(cut_context.get("aggregated_clinical_risk") or cut_context.get("aggregatedClinicalRisk") or (report.get("metricsAnalysis") or {}).get("dashboard", {}).get("max_risk")),
                    _safe_float(cut_context.get("ipm_delta_after_intervention") or cut_context.get("ipmDeltaAfterIntervention")),
                    _safe_float(cut_context.get("idm_delta_after_intervention") or cut_context.get("idmDeltaAfterIntervention")),
                    _safe_float(cut_context.get("dissonance_delta_after_intervention") or cut_context.get("dissonanceDeltaAfterIntervention")),
                    _safe_str(cut_context.get("dominant_zone_shift") or cut_context.get("dominantZoneShift") or "nao_apurado", 80),
                    _safe_str(cut_context.get("emotional_tone_shift") or cut_context.get("emotionalToneShift") or "nao_apurado", 80),
                    _safe_str(cut_context.get("cadence_shift") or cut_context.get("cadenceShift") or "nao_apurado", 80),
                    _safe_str(cut_context.get("semantic_coherence_shift") or cut_context.get("semanticCoherenceShift") or "nao_apurado", 80),
                    _safe_str(json.dumps(biomarker_snapshot, ensure_ascii=False, sort_keys=True), 1200),
                    _safe_str(json.dumps(subharmonic_snapshot, ensure_ascii=False, sort_keys=True), 1200),
                    _safe_str(json.dumps(cut_context_vector, ensure_ascii=False, sort_keys=True), 6000),
                    _safe_str(previous_context_label, 240),
                    _safe_str(next_context_label, 240),
                    _safe_str(cut_context.get("response_ipm_direction") or cut_context.get("responseIpmDirection") or "nao_apurado", 80),
                    _safe_str(cut_context.get("response_idm_direction") or cut_context.get("responseIdmDirection") or "nao_apurado", 80),
                    _safe_str(cut_context.get("response_dissonance_direction") or cut_context.get("responseDissonanceDirection") or "nao_apurado", 80),
                    _safe_str(cut_context.get("metrics_version") or cut_context.get("metricsVersion") or context.get("metrics_version") or context.get("metricsVersion") or "froid-metrics-v3", 80),
                    _safe_str(cut_context.get("weights_version") or cut_context.get("weightsVersion") or context.get("weights_version") or context.get("weightsVersion") or "froid-weights-v1", 80),
                    _safe_int(cut_context.get("media_loss_events") or cut_context.get("mediaLossEvents") or context.get("media_loss_events") or context.get("mediaLossEvents")),
                    session_hash,
                    index,
                ],
            )
            previous_cut = cut
        conn.close()
    except Exception:
        pass


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
        await self._safe_send(peer_socket, payload)

    async def _safe_send(self, websocket: WebSocket, payload: dict):
        try:
            await websocket.send_json(payload)
        except Exception:
            pass


rtc_signals = RtcSignalManager()


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


def _public_patient_session_url(base_url: str, session_id: str, token: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        base = os.getenv("FROID_PUBLIC_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/#/paciente/sessao/{session_id}?invite={token}"


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


def _format_brl(cents: int, currency: str = "brl") -> str:
    cents = max(0, int(cents or 0))
    reais = cents // 100
    centavos = cents % 100
    if str(currency or "").lower() == "usd":
        return f"US$ {reais}.{centavos:02d}"
    return f"R$ {reais},{centavos:02d}"


FROID_ACCESS_PLANS = {
    "single_session": {
        "id": "single_session",
        "name": "Sessao avulsa FROID",
        "description": "Credito individual para uma sessao FROID.",
        "session_credits": 1,
        "amount_cents": 0,
        "currency": "usd",
    },
    "professional_pack_25": {
        "id": "professional_pack_25",
        "name": "Pacote profissional 25 sessoes",
        "description": "Pacote mensal com 25 sessoes FROID.",
        "session_credits": 25,
        "amount_cents": 150,
        "currency": "usd",
    },
    "developer_pack_25": {
        "id": "developer_pack_25",
        "name": "Pacote desenvolvedor 25 sessoes",
        "description": "Pacote tecnico de desenvolvimento e testes com 25 sessoes.",
        "session_credits": 25,
        "amount_cents": 250,
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
    else:
        profile["contracted_sessions"] = contracted_sessions
        profile["bonus_sessions"] = bonus_sessions
        profile["total_sessions"] = total_sessions
        profile["remaining_sessions"] = max(
            0,
            total_sessions - max(0, _local_int(profile.get("used_sessions"))),
        )
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
    return SESSION_USERS.get(token)


def _require_current_user(request: Request) -> dict:
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")
    return user


def _is_admin_email(email: str) -> bool:
    return _normalize_email(email) in FROID_ADMIN_EMAILS


def _require_admin_user(request: Request) -> dict:
    user = _require_current_user(request)
    if not _is_admin_email(user.get("email") or ""):
        raise HTTPException(status_code=403, detail="acesso administrativo restrito")
    return user


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
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def _calendar_auth_url(email: str, redirect_uri: str) -> str:
    state = secrets.token_urlsafe(32)
    GOOGLE_CALENDAR_OAUTH_STATES[state] = {
        "email": _normalize_email(email),
        "redirect_uri": redirect_uri,
        "created_at": datetime.now(timezone.utc).timestamp(),
    }
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_CALENDAR_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
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
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
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
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
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
        raise HTTPException(status_code=404, detail="Google Agenda nao conectado")
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
    session_user = dict(user or {})
    session_user["email"] = _normalize_email(session_user.get("email") or "")
    session_user["access_status"] = _professional_access_status(session_user.get("email") or "")
    SESSION_USERS[token] = session_user
    return {"token": token, "user": session_user}


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


@app.websocket("/ws/rtc/{session_id}/{role}")
async def websocket_rtc_signaling(websocket: WebSocket, session_id: str, role: str):
    if role not in {"professional", "patient"}:
        await websocket.accept()
        await websocket.send_json({"type": "error", "detail": "role invalido"})
        await websocket.close(code=1008)
        return

    await rtc_signals.connect(websocket, session_id, role)
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
    except Exception:
        peer_socket = rtc_signals.disconnect(session_id, role, websocket)
        if peer_socket:
            await rtc_signals._safe_send(
                peer_socket,
                {"type": "peer-left", "role": role},
            )


@app.get("/health")
def health(): return {"status": "ok", "active_sessions": len(manager.active_sessions)}

@app.post("/session/create")
def create_session(): return {"session_id": str(uuid.uuid4())}

@app.post("/api/session-invites")
async def create_session_invite(request: Request):
    current_user = _require_current_user(request)
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
    base_url = body.get("base_url") or ""
    invite_url = _public_invite_url(base_url, token)
    patient_session_url = _public_patient_session_url(base_url, session_id, token)
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
        "professional_email": professional_email,
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
    _record_session_event("invite_created", invite)
    _save_identity_state()
    return invite


@app.get("/api/professional/receivables")
async def professional_receivables(request: Request):
    user = _require_current_user(request)
    owner_email = _normalize_email(user.get("email") or "")
    grouped: Dict[str, dict] = {}

    for invite in SESSION_INVITES.values():
        if not isinstance(invite, dict) or not _can_access_invite_finance(invite, owner_email):
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
    owner_email = _normalize_email(user.get("email") or "")
    body = await request.json()
    patient_key = str(body.get("patient_key") or "").strip()
    action = str(body.get("action") or "").strip().lower()
    received_cents = body.get("received_cents")
    if not patient_key:
        raise HTTPException(status_code=400, detail="patient_key obrigatorio")
    if action not in {"paid", "pending", "partial"}:
        raise HTTPException(status_code=400, detail="action deve ser paid, pending ou partial")

    matching = [
        invite
        for invite in SESSION_INVITES.values()
        if isinstance(invite, dict)
        and _invite_patient_key(invite) == patient_key
        and _can_access_invite_finance(invite, owner_email)
    ]
    if not matching:
        raise HTTPException(status_code=404, detail="Recebimento nao encontrado")

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


@app.get("/api/session-invites/{token}")
async def get_session_invite(token: str):
    invite = SESSION_INVITES.get(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Convite nao encontrado")
    _record_session_event("invite_opened", invite)
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
            "session_url": invite.get("patient_session_url")
            or _public_patient_session_url("", str(invite.get("session_id") or ""), token),
        }
    )
    _record_session_event("invite_accepted", invite)
    return {
        **invite,
        "patient": patient,
        "consent": ledger_entry,
    }


@app.post("/api/patient-sessions/{session_id}/join")
async def join_patient_session(session_id: str, request: Request):
    body = await request.json()
    invite_token = str(body.get("invite_token") or "").strip()
    invite = SESSION_INVITES.get(invite_token)
    if not invite or str(invite.get("session_id") or "") != session_id:
        raise HTTPException(status_code=404, detail="Sessao do paciente nao encontrada")
    if invite.get("status") != "accepted":
        raise HTTPException(
            status_code=403,
            detail="Confirme o cadastro e os consentimentos antes de entrar na sessao",
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
        "joined_at": now,
        "join_count": len(PATIENT_SESSION_ENTRIES.get(session_id, [])),
        "event_id": event.get("id"),
    }


@app.get("/api/session-events/latest")
async def get_latest_session_event():
    latest_id = SESSION_EVENTS[-1]["id"] if SESSION_EVENTS else 0
    return {"latest_id": latest_id}


@app.get("/api/session-events")
async def get_session_events(after: int = 0):
    events = [event for event in SESSION_EVENTS if int(event.get("id") or 0) > after]
    return {
        "latest_id": SESSION_EVENTS[-1]["id"] if SESSION_EVENTS else after,
        "events": events[-50:],
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
    user = dict(user)
    user["access_status"] = _professional_access_status(user.get("email") or "")
    SESSION_USERS[token] = user
    return user


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
    if not _calendar_configured():
        raise HTTPException(
            status_code=503,
            detail="Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no servidor",
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
    email = _normalize_email(user.get("email") or "")
    token = await _calendar_access_token(email)
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email) or {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            params={"minAccessRole": "writer", "maxResults": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Falha ao listar agendas Google: {response.text[:300]}")
    payload = response.json()
    selected_id = _selected_calendar_id(connection)
    calendars = [
        {
            "id": item.get("id"),
            "summary": item.get("summary") or item.get("id") or "Agenda",
            "primary": bool(item.get("primary")),
            "accessRole": item.get("accessRole") or "",
            "backgroundColor": item.get("backgroundColor") or "",
            "selected": str(item.get("id") or "") == selected_id,
        }
        for item in payload.get("items", [])
        if isinstance(item, dict) and item.get("id")
    ]
    return {"selected_calendar_id": selected_id, "items": calendars}


@app.post("/api/google-calendar/select-calendar")
async def google_calendar_select_calendar(request: Request):
    user = _require_current_user(request)
    email = _normalize_email(user.get("email") or "")
    body = await request.json()
    calendar_id = str(body.get("calendar_id") or "").strip()
    calendar_summary = str(body.get("calendar_summary") or "").strip()
    if not calendar_id:
        raise HTTPException(status_code=400, detail="calendar_id obrigatorio")
    connection = GOOGLE_CALENDAR_CONNECTIONS.get(email)
    if not connection:
        raise HTTPException(status_code=404, detail="Google Agenda nao conectado")
    connection.update(
        {
            "selected_calendar_id": calendar_id,
            "selected_calendar_summary": calendar_summary or calendar_id,
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
async def access_plans():
    return {
        "currency": "usd",
        "plans": [
            {
                **plan,
                "amount_brl": _format_brl(plan["amount_cents"], plan.get("currency", "usd")),
            }
            for plan in FROID_ACCESS_PLANS.values()
        ],
    }


@app.get("/api/professional/profile")
async def get_professional_profile(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")

    email = _normalize_email(user.get("email") or "")
    profile = PROFESSIONAL_PROFILES.get(email)
    return {
        "has_profile": bool(profile),
        "profile": profile,
        "access_status": _professional_access_status(email),
    }


@app.post("/api/professional/profile")
async def save_professional_profile(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")

    body = await request.json()
    owner_email = _normalize_email(user.get("email") or body.get("email") or "")
    if not owner_email:
        raise HTTPException(status_code=400, detail="email profissional obrigatorio")

    account_type = str(body.get("account_type") or "individual").strip().lower()
    if account_type not in {"individual", "organization"}:
        raise HTTPException(status_code=400, detail="tipo de cadastro invalido")

    professionals = body.get("professionals") if isinstance(body.get("professionals"), list) else []
    patient_base_access = (
        body.get("patient_base_access")
        if isinstance(body.get("patient_base_access"), list)
        else []
    )
    profile_fields = body.get("profile_fields") if isinstance(body.get("profile_fields"), dict) else {}
    referrals = body.get("referrals") if isinstance(body.get("referrals"), list) else []

    now = datetime.now(timezone.utc).isoformat()
    existing = PROFESSIONAL_PROFILES.get(owner_email) or {}
    existing_used_sessions = max(0, _local_int(existing.get("used_sessions")))
    existing_consumed_sessions = (
        existing.get("consumed_session_ids")
        if isinstance(existing.get("consumed_session_ids"), list)
        else []
    )
    total_sessions = max(0, int(body.get("total_sessions") or 0))
    profile = {
        "id": existing.get("id") or f"prof-{uuid.uuid4().hex[:12]}",
        "owner_email": owner_email,
        "owner_name": str(body.get("owner_name") or user.get("name") or "").strip(),
        "account_type": account_type,
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
        "monthly_consultations": int(body.get("monthly_consultations") or 0),
        "selected_plan": str(body.get("selected_plan") or "").strip(),
        "contracted_sessions": max(0, int(body.get("contracted_sessions") or 0)),
        "bonus_sessions": max(0, int(body.get("bonus_sessions") or 0)),
        "total_sessions": total_sessions,
        "used_sessions": existing_used_sessions,
        "remaining_sessions": max(0, total_sessions - existing_used_sessions),
        "consumed_session_ids": existing_consumed_sessions[-500:],
        "session_unit_amount_cents": max(0, int(body.get("session_unit_amount_cents") or 0)),
        "package_total_cents": max(0, int(body.get("package_total_cents") or 0)),
        "payment_status": existing.get("payment_status")
        or ("pending_checkout" if str(body.get("selected_plan") or "").strip() else "not_started"),
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
    }
    PROFESSIONAL_PROFILES[owner_email] = profile
    _save_identity_state()
    return {"status": "ok", "profile": profile, "access_status": _professional_access_status(owner_email)}


@app.post("/api/billing/checkout")
async def create_billing_checkout(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")

    body = await request.json()
    plan_id = str(body.get("plan_id") or "").strip()
    plan = FROID_ACCESS_PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="plano FROID invalido")

    base_url = _public_app_base_url(body.get("base_url") or "")
    purchase_type = str(body.get("purchase_type") or "onboarding").strip().lower()
    return_path = "/settings" if purchase_type == "add_sessions" else "/dashboard"
    cancel_path = "/settings" if purchase_type == "add_sessions" else "/access/register"
    success_url = f"{base_url}/#{return_path}?checkout=success&plan={quote(plan_id)}&stripe_session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/#{cancel_path}?checkout=cancelled&plan={quote(plan_id)}"
    email = _normalize_email(user.get("email") or body.get("email") or "")
    contracted_sessions = max(0, int(body.get("contracted_sessions") or plan.get("session_credits") or 0))
    bonus_sessions = max(0, int(body.get("bonus_sessions") or ((contracted_sessions // 100) * 10)))
    total_sessions = max(0, int(body.get("total_sessions") or (contracted_sessions + bonus_sessions)))
    unit_amount_cents = max(0, int(body.get("session_unit_amount_cents") or plan.get("amount_cents") or 0))
    package_total_cents = max(0, int(body.get("package_total_cents") or (unit_amount_cents * contracted_sessions)))
    plan_currency = str(plan.get("currency") or STRIPE_CURRENCY or "usd").lower()
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
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=409, detail="Stripe nao configurado")

    body = await request.json()
    checkout_session_id = str(body.get("checkout_session_id") or "").strip()
    if not checkout_session_id:
        raise HTTPException(status_code=400, detail="checkout_session_id obrigatorio")

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
        raise HTTPException(status_code=403, detail="checkout nao pertence ao profissional autenticado")
    if data.get("payment_status") != "paid" and data.get("status") != "complete":
        raise HTTPException(status_code=409, detail="pagamento Stripe ainda nao confirmado")

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
    return {
        "status": "ok",
        "profile": profile,
        "access_status": _professional_access_status(email),
    }


@app.post("/api/froid-explica/query", response_model=FroidExplicaResponse)
async def froid_explica_query(payload: FroidExplicaQuery):
    intent = _classify_froid_explica_intent(payload.query_text)
    if intent == "analytics":
        result = await _query_froid_analytics(payload)
    else:
        result = await _query_froid_knowledge(payload)
    result.result_text = _sanitize_reference_sections(result.result_text)
    result.citations = _scientific_citations(result.citations)
    return result


@app.post("/api/copilot/query", response_model=FroidExplicaResponse)
async def copilot_query_alias(payload: FroidExplicaQuery):
    return await froid_explica_query(payload)


@app.get("/api/session-reports")
async def list_session_reports(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")
    owner_email = _normalize_email(user.get("email") or "")
    reports = [
        _enrich_report_patient(report)
        for report in _load_session_reports().values()
        if isinstance(report, dict) and _can_access_report(report, owner_email)
    ]
    reports.sort(
        key=lambda report: str(report.get("createdAt") or report.get("created_at") or ""),
        reverse=True,
    )
    return {"reports": reports}


@app.post("/api/session-reports")
async def save_session_report(request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")
    owner_email = _normalize_email(user.get("email") or "")
    report = await request.json()
    session_id = str(report.get("sessionId") or report.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId obrigatorio")
    report["professionalEmail"] = owner_email
    report["professional"] = {
        **(report.get("professional") if isinstance(report.get("professional"), dict) else {}),
        "email": owner_email,
        "name": user.get("name") or owner_email,
    }
    report = _enrich_report_patient(report)
    report = _attach_metrics_analysis(report)
    reports = _load_session_reports()
    is_new_report = session_id not in reports
    reports[session_id] = report
    _save_session_reports(reports)
    access_status = _consume_professional_session_credit(owner_email, session_id) if is_new_report else _professional_access_status(owner_email)
    _append_anonymous_datamart_row(report)
    return {
        "status": "ok",
        "session_id": session_id,
        "metrics_analysis": report.get("metricsAnalysis"),
        "metrics_analysis_error": report.get("metricsAnalysisError"),
        "access_status": access_status,
    }


@app.get("/api/session-reports/{session_id}/metrics")
async def get_session_report_metrics(session_id: str, request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")
    report = _load_session_reports().get(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    if not _can_access_report(report, user.get("email") or ""):
        raise HTTPException(status_code=403, detail="Relatorio pertence a outro profissional")
    report = _enrich_report_patient(report)
    if not report.get("metricsAnalysis"):
        report = _attach_metrics_analysis(report)
    if report.get("metricsAnalysisError") and not report.get("metricsAnalysis"):
        raise HTTPException(status_code=500, detail=report["metricsAnalysisError"])
    return report.get("metricsAnalysis")


@app.get("/api/session-reports/{session_id}")
async def get_session_report(session_id: str, request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")
    report = _load_session_reports().get(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    if not _can_access_report(report, user.get("email") or ""):
        raise HTTPException(status_code=403, detail="Relatorio pertence a outro profissional")
    report = _enrich_report_patient(report)
    if not report.get("metricsAnalysis"):
        report = _attach_metrics_analysis(report)
    return report


@app.delete("/api/session-reports/{session_id}")
async def delete_session_report(session_id: str, request: Request):
    user = _current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="nao autenticado")
    reports = _load_session_reports()
    if session_id not in reports:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    if not _can_access_report(reports[session_id], user.get("email") or ""):
        raise HTTPException(status_code=403, detail="Relatorio pertence a outro profissional")
    del reports[session_id]
    _save_session_reports(reports)
    return {
        "status": "deleted",
        "session_id": session_id,
        "note": "Relatorio identificado removido. Registros anonimizados agregados nao contem PII.",
    }


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
        "summary": _limit_words(transcript, 60),
        "start_minute": start_minute,
        "end_minute": end_minute,
        "model": OPENAI_MODEL,
    }

    if not OPENAI_API_KEY:
        return fallback

    prompt = (
        "Analise a transcricao clinica abaixo e responda somente em JSON valido "
        "com as chaves theme e summary. theme deve ser resultado direto do assunto tratado, "
        "nao pode vir de lista predefinida e deve ter no maximo 6 palavras. "
        "summary deve ter no maximo 60 palavras, em portugues do Brasil, sem diagnostico, "
        "sem inventar fatos e preservando apenas o que foi falado no intervalo. "
        "Se a transcricao tiver pouco conteudo, resuma apenas o material real disponivel. "
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
        theme = _limit_words(str(parsed.get("theme") or fallback["theme"]).strip(), 6)
        summary_text = str(parsed.get("summary") or fallback["summary"]).strip()
        return {
            "status": "ok",
            "theme": theme,
            "summary": _limit_words(summary_text, 60),
            "start_minute": start_minute,
            "end_minute": end_minute,
            "model": OPENAI_MODEL,
        }
    except Exception:
        return fallback
