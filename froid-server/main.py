import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
import secrets
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
FROID_ANALYTICS_MIN_K = int(os.getenv("FROID_ANALYTICS_MIN_K", "50") or "50")
FROID_SESSION_REPORTS_PATH = os.getenv(
    "FROID_SESSION_REPORTS_PATH",
    "/data/session_reports.json",
)
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
PATIENT_SESSION_ENTRIES: Dict[str, list[dict]] = {}
SESSION_EVENTS: list[dict] = []
SESSION_EVENT_COUNTER = 0

KNOWLEDGE_BASE = {
    "froid_zonas": "As 12 Zonas de Percepcao FROID organizam padroes de desequilibrio facial-vocal e orientam a leitura clinica por temas, tensoes e dissonancias.",
    "ipm_velocimetro": "O IPM indica a intensidade ou energia global da sessao. Ele funciona como velocimetro emocional e nao define sozinho a direcao do desequilibrio.",
    "idm_direcao": "O IDM aponta a direcao do desequilibrio entre marcadores negativos e positivos, enquanto o IPM mede a energia global empregada.",
    "mfcc7_depressao": "MFCC7 elevado durante conteudos semanticamente negativos, associado a pausas, menor variacao de F0 e retardo psicomotor, contribui para risco depressivo.",
    "mfcc9_ansiedade": "MFCC9 em discurso neutro pode ter relacao inversa com ansiedade somatica; quedas acusticas podem indicar tensao autonoma latente.",
    "mania_ativacao": "A ativacao de mania acompanha pitch/F0 elevado, loudness, taxa acelerada de fala e fluxo espectral mais incisivo.",
    "sub_harmonicos": "Sub-harmonicos vocais entre 5 e 12 Hz podem refletir tremores do sistema nervoso autonomo quando cruzados com FACS e tensao vocal basal.",
    "facs_trauma": "A combinacao AU15, AU20, dor facial, angustia e tensao vocal pode sinalizar flooding, sobrecarga autonomica ou retraumatizacao.",
    "governanca_lgpd": "Benchmarks populacionais devem usar dados anonimizados e agregados. O FROID aplica k-anonimato minimo para reduzir risco de reidentificacao.",
}


class FroidExplicaQuery(BaseModel):
    query_text: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


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
    selected = ranked[:limit] or [
        (0, key, value) for key, value in list(KNOWLEDGE_BASE.items())[:limit]
    ]
    return [item[2] for item in selected], [item[1] for item in selected]


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


def _classify_froid_explica_intent(query_text: str) -> str:
    query = _normalize_search_text(query_text)
    analytics_markers = {
        "estatistica",
        "estatisticas",
        "comparar",
        "comparacao",
        "benchmark",
        "populacional",
        "populacao",
        "coorte",
        "media",
        "percentil",
        "demografico",
        "similar",
        "similares",
        "base",
        "casos",
    }
    if any(marker in query for marker in analytics_markers):
        return "analytics"
    return "knowledge"


def _fallback_froid_explica_result(query_text: str, context: Dict[str, Any]) -> str:
    ipm = context.get("ipm_score", "--")
    coherence = context.get("coherence_status", "--")
    dominant = context.get("dominant_zone") or {}
    zone_label = (
        f"Zona {dominant.get('zone')} ({dominant.get('theme')})"
        if isinstance(dominant, dict) and dominant.get("zone")
        else "zona dominante ainda indefinida"
    )
    return (
        "FROID Explica em modo local. "
        f"Pergunta recebida: {query_text}. "
        f"Contexto atual: IPM {ipm}, coerencia {coherence}, {zone_label}. "
        "Para resposta cientifica ancorada em RAG, configure GEMINI_API_KEY e/ou OPENAI_API_KEY "
        "e carregue a base ChromaDB dos manuais FROID."
    )


async def _query_froid_knowledge(payload: FroidExplicaQuery) -> FroidExplicaResponse:
    chroma_docs, chroma_citations = _query_chroma_froid_knowledge(payload.query_text)
    local_docs, local_citations = _query_local_froid_knowledge(payload.query_text)
    context_chunks = chroma_docs or local_docs
    citations = chroma_citations or local_citations
    context_str = "\n\n".join(
        f"[Fonte: {source}]\n{doc}"
        for source, doc in zip(citations, context_chunks)
    )
    session_context = _format_session_context(payload.context)
    system_instruction = (
        "Voce e o FROID Explica, uma inteligencia clinica de apoio ao profissional. "
        "Responda em portugues do Brasil, de modo objetivo, sem diagnosticar e sem inventar. "
        "Use estritamente o contexto cientifico e o contexto da sessao. "
        "Se os dados forem insuficientes, diga claramente o que falta."
    )
    prompt = (
        f"CONTEXTO CIENTIFICO FROID:\n{context_str or 'Base cientifica nao carregada.'}\n\n"
        f"CONTEXTO DA SESSAO ATUAL:\n{session_context}\n\n"
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
        citations=sorted(set(citations)),
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
        "session_duration INTEGER. "
        "anonymous_session_cuts contem: session_hash VARCHAR, cut_index INTEGER, cut_label VARCHAR, "
        "start_second INTEGER, end_second INTEGER, sample_count INTEGER, ipm_avg DOUBLE, "
        "idm_avg DOUBLE, dominant_zone INTEGER, coherence_status VARCHAR, emotional_tone VARCHAR, "
        "words_per_minute DOUBLE, theme VARCHAR, dissonance_count INTEGER, mfcc7 DOUBLE, mfcc9 DOUBLE, "
        "f0_mean DOUBLE, zcr DOUBLE, jitter DOUBLE, shimmer DOUBLE, subharmonic_5_12 DOUBLE, "
        "subharmonic_12_20 DOUBLE. "
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


def _anonymous_session_hash(report: dict) -> str:
    raw = f"{report.get('sessionId') or report.get('session_id') or ''}:{report.get('createdAt') or ''}"
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
                session_duration INTEGER
            )
            """
        )
        _ensure_duckdb_column(conn, "anonymous_sessions", "session_hash", "VARCHAR")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS anonymous_session_cuts (
                session_hash VARCHAR,
                cut_index INTEGER,
                cut_label VARCHAR,
                start_second INTEGER,
                end_second INTEGER,
                sample_count INTEGER,
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
                subharmonic_12_20 DOUBLE
            )
            """
        )
        average = report.get("sessionAverage") or {}
        baseline = report.get("baseline") or {}
        dominant_zone = average.get("dominantZone") or baseline.get("dominantZone")
        vocal_tension = (
            average.get("jitter")
            or average.get("shimmer")
            or average.get("subharmonic5_12")
            or 0
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
                ssri_medication, session_duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session_hash,
                "unknown",
                "unknown",
                _safe_float(average.get("ipmAvg")),
                _safe_int(dominant_zone),
                _safe_float(vocal_tension),
                False,
                _safe_int(report.get("durationSeconds")),
            ],
        )
        for index, cut in enumerate(report.get("tenMinuteCuts") or []):
            if not isinstance(cut, dict):
                continue
            conn.execute(
                """
                INSERT INTO anonymous_session_cuts (
                    session_hash, cut_index, cut_label, start_second, end_second,
                    sample_count, ipm_avg, idm_avg, dominant_zone, dominant_theme,
                    coherence_status, emotional_tone, words_per_minute, theme,
                    dissonance_count, mfcc7, mfcc9, f0_mean, zcr, jitter, shimmer,
                    subharmonic_5_12, subharmonic_12_20
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    session_hash,
                    index,
                    str(cut.get("label") or ""),
                    _safe_int(cut.get("startSecond")),
                    _safe_int(cut.get("endSecond")),
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
                ],
            )
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
    return invite


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
    return user

@app.post("/api/froid-explica/query", response_model=FroidExplicaResponse)
async def froid_explica_query(payload: FroidExplicaQuery):
    intent = _classify_froid_explica_intent(payload.query_text)
    if intent == "analytics":
        return await _query_froid_analytics(payload)
    return await _query_froid_knowledge(payload)


@app.post("/api/copilot/query", response_model=FroidExplicaResponse)
async def copilot_query_alias(payload: FroidExplicaQuery):
    return await froid_explica_query(payload)


@app.post("/api/session-reports")
async def save_session_report(request: Request):
    report = await request.json()
    session_id = str(report.get("sessionId") or report.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId obrigatorio")
    report = _attach_metrics_analysis(report)
    reports = _load_session_reports()
    reports[session_id] = report
    _save_session_reports(reports)
    _append_anonymous_datamart_row(report)
    return {
        "status": "ok",
        "session_id": session_id,
        "metrics_analysis": report.get("metricsAnalysis"),
        "metrics_analysis_error": report.get("metricsAnalysisError"),
    }


@app.get("/api/session-reports/{session_id}/metrics")
async def get_session_report_metrics(session_id: str):
    report = _load_session_reports().get(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    if not report.get("metricsAnalysis"):
        report = _attach_metrics_analysis(report)
    if report.get("metricsAnalysisError") and not report.get("metricsAnalysis"):
        raise HTTPException(status_code=500, detail=report["metricsAnalysisError"])
    return report.get("metricsAnalysis")


@app.get("/api/session-reports/{session_id}")
async def get_session_report(session_id: str):
    report = _load_session_reports().get(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    if not report.get("metricsAnalysis"):
        report = _attach_metrics_analysis(report)
    return report


@app.delete("/api/session-reports/{session_id}")
async def delete_session_report(session_id: str):
    reports = _load_session_reports()
    if session_id not in reports:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
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
