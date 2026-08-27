"""Phase 1 PostgreSQL bridge for FROID multi-tenant persistence.

Legacy JSON remains the source of truth in ``legacy`` and ``dual`` modes.  The
dual writer is deliberately idempotent so a deployment can be rolled back to
legacy mode without data loss while the PostgreSQL copy is validated.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Dict, Iterable, Optional, Sequence
import uuid


NAMESPACE = uuid.UUID("c173f252-e04f-4ca4-a337-39767764c79c")
VALID_MODES = {"legacy", "dual"}
VALID_MEMBERSHIP_ROLES = {
    "owner", "administrator", "supervisor", "professional", "auditor"
}


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def stable_uuid(kind: str, *parts: Any) -> uuid.UUID:
    normalized = "|".join(str(part or "").strip().lower() for part in parts)
    return uuid.uuid5(NAMESPACE, f"{kind}|{normalized}")


def organization_id_for_profile(
    owner_email: str, account_type: str, organization_document=None
) -> str:
    """Organizacao a que este perfil pertence.

    Clinica: derivada do CNPJ, para que todos os profissionais do mesmo CNPJ
    caiam na MESMA organizacao e partilhem um unico pool de creditos. A empresa
    contratante do NR-1 tambem deriva do CNPJ, porque varias pessoas do mesmo
    empregador precisam enxergar a mesma estrutura e as mesmas campanhas.
    Profissional autonomo continua derivando do e-mail (organizacao propria),
    preservando quem ja opera hoje.

    Publica e fora da transacao de gravacao de proposito: quem valida a
    transicao de tipo precisa saber QUAL organizacao seria tocada antes de
    tocar nela, e recalcular isso por fora seria duas verdades sobre a mesma
    coisa — exatamente como uma delas fica velha sem ninguem notar.
    """
    normalizado = normalize_email(owner_email) or "legacy-unassigned@froid.local"
    documento = re.sub(r"\D", "", str(organization_document or ""))
    if organization_derives_from_cnpj(account_type, organization_document):
        return stable_uuid("organization", "cnpj", documento)
    return stable_uuid("organization", normalizado)


def organization_derives_from_cnpj(account_type: str, organization_document=None) -> bool:
    """A organizacao deste perfil vem do CNPJ, e portanto e compartilhada.

    Clinica: varios profissionais do mesmo CNPJ. Empresa NR-1: varias pessoas
    do mesmo empregador. Nos dois casos a organizacao nao tem "dono legado"
    unico, e reivindicar o e-mail do titular em legacy_owner_email colide com o
    indice organizations_legacy_owner_unique assim que a mesma pessoa tiver
    tambem organizacao propria — o autonomo que depois se formaliza como
    clinica, ou o profissional que tambem cadastra a empresa dele no NR-1.

    Existe para que a condicao nao seja escrita em dois lugares.
    organization_id_for_profile decide DE ONDE vem o id; quem grava a linha
    precisa da mesma resposta para decidir se reivindica o e-mail. Ja houve uma
    copia dessa regra, ela foi removida de um lado so, e o que sobrou foi um
    NameError vivo em producao (ver o teste que veio junto com esta funcao).
    """
    documento = re.sub(r"\D", "", str(organization_document or ""))
    tipo = str(account_type or "individual").lower()
    return bool(documento) and tipo in {"organization", "nr1_company"}


def _ou_nulo(valor, conversor):
    """Converte, ou preserva o nulo — nunca inventa zero.

    O inventario passou a aceitar linha declarada insuficiente, em que coorte,
    media, severidade e probabilidade sao NULL por exigencia de restricao. Um
    int(None) aqui estouraria; um int(valor or 0) seria pior, porque gravaria
    zero e um auditor leria "coorte de zero pessoa" ou "severidade zero" como se
    fossem medidas, e nao ausencia de medida.
    """
    return None if valor is None else conversor(valor)


def organization_type_for_account(account_type: str) -> str:
    """Mapa account_type -> organization_type.

    'enterprise' nao e cosmetico: e o unico valor que faz
    effective_role_permissions retirar as permissoes clinicas identificadas dos
    papeis do lado do empregador. Trocar este mapeamento devolve ao empregador
    o acesso ao prontuario.
    """
    tipo = str(account_type or "individual").lower()
    if tipo == "nr1_company":
        return "enterprise"
    if tipo == "organization":
        return "clinic"
    return "solo"


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _migration_is_applied(connection, version: str) -> bool:
    """Return whether a version is recorded without assuming the table exists."""
    table_exists = connection.execute(
        "SELECT to_regclass('public.schema_migrations') IS NOT NULL"
    ).fetchone()
    if not table_exists or not bool(table_exists[0]):
        return False
    recorded = connection.execute(
        "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version=%s)",
        (version,),
    ).fetchone()
    return bool(recorded and recorded[0])


class TenantStore:
    """Optional, rollback-safe mirror of legacy FROID state in PostgreSQL."""

    def __init__(
        self,
        mode: str,
        database_url: str,
        migration_path: Path,
        runtime_database_url: str = "",
    ):
        requested_mode = (mode or "legacy").strip().lower()
        if requested_mode not in VALID_MODES:
            raise ValueError(
                "FROID_PERSISTENCE_MODE must be 'legacy' or 'dual' during Phase 1"
            )
        if requested_mode == "dual" and not database_url:
            raise ValueError("FROID_DATABASE_URL is required in dual mode")
        self.mode = requested_mode
        self.database_url = database_url
        self.runtime_database_url = str(runtime_database_url or "").strip()
        self.migration_path = migration_path
        self._lock = threading.Lock()
        self._schema_lock = threading.Lock()
        self._schema_ready = False
        self._last_sync_at: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_counters: Dict[str, int] = {}

    @classmethod
    def from_env(cls) -> "TenantStore":
        return cls(
            mode=os.getenv("FROID_PERSISTENCE_MODE", "legacy"),
            database_url=os.getenv("FROID_DATABASE_URL", "").strip(),
            migration_path=Path(__file__).parent
            / "migrations"
            / "001_multitenant_foundation.sql",
            runtime_database_url=os.getenv(
                "FROID_RUNTIME_DATABASE_URL", ""
            ).strip(),
        )

    @property
    def enabled(self) -> bool:
        return self.mode == "dual"

    def status(self) -> dict:
        return {
            "mode": self.mode,
            "postgres_mirror_enabled": self.enabled,
            "runtime_role_configured": bool(self.runtime_database_url),
            "schema_ready": self._schema_ready,
            "last_sync_at": self._last_sync_at,
            "last_error": self._last_error,
            "last_counters": self._last_counters,
        }

    def readiness(self) -> dict:
        """Read-only cutover checks that never apply migrations or expose PII."""
        checks = {
            "persistence_mode_supported": self.mode in VALID_MODES,
        }
        if not self.enabled:
            checks["legacy_source_available"] = True
            return {"ready": True, "mode": self.mode, "checks": checks}

        expected_migrations = {
            path.stem for path in self.migration_path.parent.glob("*.sql")
        }
        try:
            with self._connect() as owner_connection:
                owner_database = owner_connection.execute(
                    "SELECT current_database()"
                ).fetchone()[0]
                applied_migrations = {
                    row[0]
                    for row in owner_connection.execute(
                        "SELECT version FROM schema_migrations"
                    ).fetchall()
                }
                rls_count = owner_connection.execute(
                    """
                    SELECT count(*) FROM pg_class
                    WHERE relnamespace='public'::regnamespace
                      AND relname = ANY(%s) AND relrowsecurity
                    """,
                    ([
                        "organization_memberships", "patients",
                        "patient_assignments", "session_reports", "consents",
                        "organization_wallets", "credit_ledger", "audit_events",
                        "organization_subscriptions", "data_subject_requests",
                        "data_subject_request_events", "legal_acceptance_events",
                    ],),
                ).fetchone()[0]
            checks["owner_database_reachable"] = True
            checks["all_migrations_applied"] = expected_migrations.issubset(
                applied_migrations
            )
            checks["rls_enabled_on_tenant_tables"] = int(rls_count) == 12
        except Exception as exc:
            checks["owner_database_reachable"] = False
            checks["all_migrations_applied"] = False
            checks["rls_enabled_on_tenant_tables"] = False
            return {
                "ready": False,
                "mode": self.mode,
                "checks": checks,
                "error": type(exc).__name__,
            }

        if not self.runtime_database_url:
            checks["runtime_database_configured"] = False
        else:
            checks["runtime_database_configured"] = True
            try:
                with self._connect(runtime=True) as runtime_connection:
                    runtime_database = runtime_connection.execute(
                        "SELECT current_database()"
                    ).fetchone()[0]
                    owner_count = runtime_connection.execute(
                        """
                        SELECT count(*) FROM pg_class table_entry
                        WHERE table_entry.relnamespace='public'::regnamespace
                          AND table_entry.relname = ANY(%s)
                          AND pg_has_role(
                              current_user, table_entry.relowner, 'MEMBER'
                          )
                        """,
                        ([
                            "organizations", "patients", "session_reports",
                            "organization_wallets", "credit_ledger",
                            "audit_events", "organization_subscriptions",
                        ],),
                    ).fetchone()[0]
                    function_access = runtime_connection.execute(
                        """
                        SELECT has_function_privilege(
                            current_user, 'froid_has_role(text[])', 'EXECUTE'
                        )
                        """
                    ).fetchone()[0]
                checks["runtime_database_reachable"] = True
                checks["runtime_targets_owner_database"] = (
                    runtime_database == owner_database
                )
                checks["runtime_is_not_table_owner"] = int(owner_count) == 0
                checks["runtime_role_function_available"] = bool(function_access)
            except Exception as exc:
                checks["runtime_database_reachable"] = False
                checks["runtime_targets_owner_database"] = False
                checks["runtime_is_not_table_owner"] = False
                checks["runtime_role_function_available"] = False
                return {
                    "ready": False,
                    "mode": self.mode,
                    "checks": checks,
                    "error": type(exc).__name__,
                }

        return {
            "ready": all(checks.values()),
            "mode": self.mode,
            "checks": checks,
        }

    def _connect(self, *, runtime: bool = False):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required when FROID_PERSISTENCE_MODE=dual"
            ) from exc
        database_url = (
            self.runtime_database_url
            if runtime and self.runtime_database_url
            else self.database_url
        )
        return psycopg.connect(database_url, connect_timeout=10)

    def ensure_schema(self, connection=None) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            migration_paths = sorted(self.migration_path.parent.glob("*.sql"))
            if self.migration_path not in migration_paths:
                migration_paths.insert(0, self.migration_path)

            def apply_migrations(conn) -> None:
                # Serializes schema startup across workers on the same database.
                lock_id = 7_346_643_004
                conn.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
                try:
                    for migration_path in migration_paths:
                        if _migration_is_applied(conn, migration_path.stem):
                            continue
                        conn.execute(migration_path.read_text(encoding="utf-8"))
                except Exception:
                    conn.rollback()
                    conn.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
                    conn.commit()
                    raise
                conn.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
                conn.commit()

            if connection is None:
                with self._connect() as conn:
                    apply_migrations(conn)
            else:
                apply_migrations(connection)
            self._schema_ready = True

    def organization_type(self, organization_id) -> str:
        """Tipo ja gravado desta organizacao, ou string vazia se ela nao existe.

        Existe para uma pergunta so: a organizacao que este cadastro vai tocar
        ja e 'enterprise'? Um cadastro que a rebaixasse para 'clinic' devolveria
        ao empregador as permissoes clinicas identificadas que
        effective_role_permissions retira — e o upsert de organizacoes faz
        ON CONFLICT DO UPDATE do organization_type, entao sem esta pergunta a
        troca passa despercebida.
        """
        if not self.enabled or not organization_id:
            return ""
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT organization_type FROM organizations WHERE id = %s",
                    (str(organization_id),),
                )
                row = cursor.fetchone()
        return str((row or [""])[0] or "")

    def access_contexts(self, email: str) -> list[dict]:
        """Return active organization memberships for an authenticated email."""
        if not self.enabled:
            return []
        normalized_email = normalize_email(email)
        if not normalized_email:
            return []
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT organization.id, organization.display_name,
                           membership.id, user_account.id, membership.status,
                           coalesce(array_agg(role.role) FILTER (
                               WHERE role.role IS NOT NULL
                           ), ARRAY[]::text[]),
                           organization.organization_type
                    FROM users user_account
                    JOIN organization_memberships membership
                      ON membership.user_id = user_account.id
                    JOIN organizations organization
                      ON organization.id = membership.organization_id
                    LEFT JOIN membership_roles role
                      ON role.membership_id = membership.id
                    WHERE lower(user_account.email) = %s
                      AND user_account.status = 'active'
                      AND membership.status = 'active'
                      AND organization.status = 'active'
                    GROUP BY organization.id, organization.display_name,
                             membership.id, user_account.id, membership.status,
                             organization.organization_type
                    ORDER BY organization.display_name, organization.id
                    """,
                    (normalized_email,),
                )
                return [
                    {
                        "organization_id": str(row[0]),
                        "organization_name": row[1],
                        "membership_id": str(row[2]),
                        "user_id": str(row[3]),
                        "status": row[4],
                        "roles": sorted(row[5] or []),
                        "organization_type": row[6] or "clinic",
                    }
                    for row in cursor.fetchall()
                ]

    def record_access_audit(
        self,
        *,
        organization_id: str,
        actor_user_id: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        outcome: str = "success",
        metadata: Optional[dict] = None,
    ) -> None:
        if not self.enabled or not organization_id:
            return
        with self._connect() as connection:
            self.ensure_schema(connection)
            connection.execute(
                """
                INSERT INTO audit_events
                    (id, organization_id, actor_user_id, action, resource_type,
                     resource_id, outcome, metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                """,
                (
                    uuid.uuid4(), organization_id, actor_user_id or None, action,
                    resource_type, resource_id or None, outcome,
                    _json(metadata or {}),
                ),
            )
            connection.commit()

    def record_legal_acceptance(
        self,
        *,
        organization_id: str = "",
        subject_kind: str,
        subject_reference_hash: str,
        document_key: str,
        document_version: str,
        document_sha256: str,
        acceptance_context: str,
        commercial_snapshot: Optional[dict] = None,
        request_fingerprint_hash: str = "",
        accepted_at: str = "",
    ) -> None:
        """Persist immutable legal evidence without copying identity PII."""
        if not self.enabled:
            return
        if subject_kind not in {"professional", "organization", "patient"}:
            raise ValueError("invalid legal acceptance subject")
        with self._connect() as connection:
            self.ensure_schema(connection)
            connection.execute(
                """
                INSERT INTO legal_acceptance_events
                    (id, organization_id, subject_kind, subject_reference_hash,
                     document_key, document_version, document_sha256,
                     acceptance_context, commercial_snapshot,
                     request_fingerprint_hash, accepted_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                """,
                (
                    uuid.uuid4(), organization_id or None, subject_kind,
                    subject_reference_hash, document_key, document_version,
                    document_sha256, acceptance_context,
                    _json(commercial_snapshot or {}),
                    request_fingerprint_hash or None,
                    parse_timestamp(accepted_at),
                ),
            )
            connection.commit()

    def list_audit_events(
        self, *, organization_id: str, membership_id: str, limit: int = 100
    ) -> list[dict]:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        safe_limit = max(1, min(500, int(limit)))
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                rows = connection.execute(
                    """
                    SELECT event.id, event.actor_user_id, account.email,
                           event.action, event.resource_type, event.resource_id,
                           event.outcome, event.metadata, event.occurred_at
                    FROM audit_events event
                    LEFT JOIN users account ON account.id=event.actor_user_id
                    WHERE event.organization_id=%s
                    ORDER BY event.occurred_at DESC, event.id DESC
                    LIMIT %s
                    """,
                    (organization_id, safe_limit),
                ).fetchall()
        return [
            {
                "id": str(row[0]),
                "actor_user_id": str(row[1]) if row[1] else None,
                "actor_email": row[2],
                "action": row[3],
                "resource_type": row[4],
                "resource_id": row[5],
                "outcome": row[6],
                "metadata": row[7] or {},
                "occurred_at": row[8],
            }
            for row in rows
        ]

    @staticmethod
    def _data_subject_request(row) -> dict:
        return {
            "id": str(row[0]),
            "request_batch_id": str(row[1]),
            "organization_id": str(row[2]),
            "organization_name": row[3],
            "patient_id": str(row[4]),
            "request_type": row[5],
            "status": row[6],
            "channel": row[7],
            "request_payload": row[8] or {},
            "response_summary": row[9] or "",
            "legal_basis": row[10] or "",
            "retention_exception": row[11] or "",
            "submitted_at": row[12],
            "service_due_at": row[13],
            "identity_verified_at": row[14],
            "resolved_at": row[15],
            "updated_at": row[16],
        }

    def patient_privacy_scopes(
        self, legacy_patient_id: str, identity_document: str
    ) -> list[dict]:
        """Resolve organizations holding data for an authenticated legacy patient."""
        if not self.enabled or not legacy_patient_id or not identity_document:
            return []
        with self._connect() as connection:
            self.ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT patient.organization_id, organization.display_name, patient.id
                FROM patients patient
                JOIN organizations organization ON organization.id=patient.organization_id
                WHERE patient.legacy_patient_id=%s
                  AND regexp_replace(coalesce(patient.document, ''), '\\D', '', 'g')=%s
                  AND patient.status <> 'deleted'
                ORDER BY organization.display_name, organization.id
                """,
                (str(legacy_patient_id), str(identity_document)),
            ).fetchall()
        return [
            {
                "organization_id": str(row[0]),
                "organization_name": row[1],
                "patient_id": str(row[2]),
            }
            for row in rows
        ]

    def create_data_subject_requests(
        self,
        *,
        legacy_patient_id: str,
        identity_document: str,
        request_type: str,
        request_payload: dict,
        organization_id: str = "",
    ) -> list[dict]:
        if not self.enabled:
            raise RuntimeError("dual persistence is required")
        batch_id = uuid.uuid4()
        with self._connect() as connection:
            self.ensure_schema(connection)
            scopes = connection.execute(
                """
                SELECT patient.organization_id, organization.display_name, patient.id
                FROM patients patient
                JOIN organizations organization ON organization.id=patient.organization_id
                WHERE patient.legacy_patient_id=%s
                  AND regexp_replace(coalesce(patient.document, ''), '\\D', '', 'g')=%s
                  AND patient.status <> 'deleted'
                  AND (%s='' OR patient.organization_id::text=%s)
                ORDER BY organization.display_name, organization.id
                """,
                (
                    str(legacy_patient_id), str(identity_document),
                    str(organization_id or ""), str(organization_id or ""),
                ),
            ).fetchall()
            if not scopes:
                raise ValueError("patient has no matching organization scope")
            created_ids = []
            for scoped_organization_id, _name, patient_id in scopes:
                request_id = uuid.uuid4()
                connection.execute(
                    """
                    INSERT INTO data_subject_requests
                        (id, request_batch_id, organization_id, patient_id,
                         request_type, status, channel, request_payload,
                         identity_verified_at)
                    VALUES (%s,%s,%s,%s,%s,'identity_verified','patient_portal',
                            %s::jsonb,now())
                    """,
                    (
                        request_id, batch_id, scoped_organization_id, patient_id,
                        request_type, _json(request_payload or {}),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO data_subject_request_events
                        (id, organization_id, request_id, actor_kind, action,
                         from_status, to_status, metadata)
                    VALUES (%s,%s,%s,'patient','request.submitted',NULL,
                            'identity_verified','{}'::jsonb)
                    """,
                    (uuid.uuid4(), scoped_organization_id, request_id),
                )
                connection.execute(
                    """INSERT INTO audit_events
                        (id, organization_id, action, resource_type, resource_id,
                         outcome, metadata)
                    VALUES (%s,%s,'privacy.request.submitted','data_subject_request',
                            %s,'success','{"actor_kind":"patient"}'::jsonb)""",
                    (uuid.uuid4(), scoped_organization_id, str(request_id)),
                )
                created_ids.append(request_id)
            connection.commit()
            rows = connection.execute(
                """
                SELECT request.id, request.request_batch_id, request.organization_id,
                       organization.display_name, request.patient_id,
                       request.request_type, request.status, request.channel,
                       request.request_payload, request.response_summary,
                       request.legal_basis, request.retention_exception,
                       request.submitted_at, request.service_due_at,
                       request.identity_verified_at, request.resolved_at,
                       request.updated_at
                FROM data_subject_requests request
                JOIN organizations organization ON organization.id=request.organization_id
                WHERE request.id=ANY(%s)
                ORDER BY organization.display_name
                """,
                (created_ids,),
            ).fetchall()
        return [self._data_subject_request(row) for row in rows]

    def list_patient_data_subject_requests(
        self, legacy_patient_id: str, identity_document: str
    ) -> list[dict]:
        if not self.enabled or not legacy_patient_id or not identity_document:
            return []
        with self._connect() as connection:
            self.ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT request.id, request.request_batch_id, request.organization_id,
                       organization.display_name, request.patient_id,
                       request.request_type, request.status, request.channel,
                       request.request_payload, request.response_summary,
                       request.legal_basis, request.retention_exception,
                       request.submitted_at, request.service_due_at,
                       request.identity_verified_at, request.resolved_at,
                       request.updated_at
                FROM data_subject_requests request
                JOIN patients patient
                  ON patient.organization_id=request.organization_id
                 AND patient.id=request.patient_id
                JOIN organizations organization ON organization.id=request.organization_id
                WHERE patient.legacy_patient_id=%s
                  AND regexp_replace(coalesce(patient.document, ''), '\\D', '', 'g')=%s
                ORDER BY request.submitted_at DESC, request.id DESC
                """,
                (str(legacy_patient_id), str(identity_document)),
            ).fetchall()
        return [self._data_subject_request(row) for row in rows]

    def list_organization_data_subject_requests(
        self, *, organization_id: str, membership_id: str, limit: int = 200
    ) -> list[dict]:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        safe_limit = max(1, min(500, int(limit)))
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute("SELECT set_config('app.organization_id', %s, true)", (organization_id,))
                connection.execute("SELECT set_config('app.membership_id', %s, true)", (membership_id,))
                rows = connection.execute(
                    """
                    SELECT request.id, request.request_batch_id, request.organization_id,
                           organization.display_name, request.patient_id,
                           request.request_type, request.status, request.channel,
                           request.request_payload, request.response_summary,
                           request.legal_basis, request.retention_exception,
                           request.submitted_at, request.service_due_at,
                           request.identity_verified_at, request.resolved_at,
                           request.updated_at
                    FROM data_subject_requests request
                    JOIN organizations organization ON organization.id=request.organization_id
                    WHERE request.organization_id=%s
                    ORDER BY request.service_due_at, request.submitted_at
                    LIMIT %s
                    """,
                    (organization_id, safe_limit),
                ).fetchall()
        return [self._data_subject_request(row) for row in rows]

    def update_data_subject_request(
        self,
        *,
        organization_id: str,
        membership_id: str,
        actor_user_id: str,
        request_id: str,
        status: str,
        response_summary: str = "",
        legal_basis: str = "",
        retention_exception: str = "",
    ) -> dict:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        final_statuses = {"completed", "cancelled", "denied", "partially_approved"}
        allowed_transitions = {
            "submitted": {"identity_verified", "cancelled"},
            "identity_verified": {"in_review", "awaiting_information", "cancelled"},
            "in_review": {"awaiting_information", "approved", "partially_approved", "denied", "cancelled"},
            "awaiting_information": {"in_review", "cancelled"},
            "approved": {"in_review", "completed"},
            "partially_approved": {"in_review", "completed"},
            "denied": {"in_review"},
            "completed": set(),
            "cancelled": set(),
        }
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute("SELECT set_config('app.organization_id', %s, true)", (organization_id,))
                connection.execute("SELECT set_config('app.membership_id', %s, true)", (membership_id,))
                current = connection.execute(
                    "SELECT status FROM data_subject_requests WHERE organization_id=%s AND id=%s FOR UPDATE",
                    (organization_id, request_id),
                ).fetchone()
                if not current:
                    raise ValueError("data subject request not found")
                previous_status = str(current[0])
                if status != previous_status and status not in allowed_transitions.get(previous_status, set()):
                    raise ValueError(
                        f"invalid data subject request transition: {previous_status} -> {status}"
                    )
                connection.execute(
                    """
                    UPDATE data_subject_requests SET status=%s, response_summary=%s,
                        legal_basis=%s, retention_exception=%s,
                        resolved_by_user_id=%s,
                        resolved_at=CASE WHEN %s=ANY(%s) THEN now() ELSE NULL END,
                        updated_at=now()
                    WHERE organization_id=%s AND id=%s
                    """,
                    (
                        status, response_summary or None, legal_basis or None,
                        retention_exception or None, actor_user_id or None,
                        status, list(final_statuses), organization_id, request_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO data_subject_request_events
                        (id, organization_id, request_id, actor_kind, actor_user_id,
                         action, from_status, to_status, metadata)
                    VALUES (%s,%s,%s,'professional',%s,'request.status_changed',
                            %s,%s,'{}'::jsonb)
                    """,
                    (uuid.uuid4(), organization_id, request_id, actor_user_id, previous_status, status),
                )
                row = connection.execute(
                    """
                    SELECT request.id, request.request_batch_id, request.organization_id,
                           organization.display_name, request.patient_id,
                           request.request_type, request.status, request.channel,
                           request.request_payload, request.response_summary,
                           request.legal_basis, request.retention_exception,
                           request.submitted_at, request.service_due_at,
                           request.identity_verified_at, request.resolved_at,
                           request.updated_at
                    FROM data_subject_requests request
                    JOIN organizations organization ON organization.id=request.organization_id
                    WHERE request.organization_id=%s AND request.id=%s
                    """,
                    (organization_id, request_id),
                ).fetchone()
        return self._data_subject_request(row)

    def accessible_legacy_report_ids(
        self, *, organization_id: str, membership_id: str
    ) -> set[str]:
        """Return report IDs visible through assignment-aware PostgreSQL RLS."""
        if not self.enabled or not self.runtime_database_url:
            return set()
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                rows = connection.execute(
                    """SELECT legacy_session_id FROM session_reports
                    WHERE organization_id=%s AND deleted_at IS NULL""",
                    (organization_id,),
                ).fetchall()
        return {str(row[0]) for row in rows if row and row[0]}

    def list_members(self, organization_id: str) -> list[dict]:
        if not self.enabled:
            return []
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT membership.id, user_account.id, user_account.email,
                           user_account.display_name, membership.status,
                           membership.joined_at, membership.revoked_at,
                           coalesce(array_agg(role.role) FILTER (
                               WHERE role.role IS NOT NULL
                           ), ARRAY[]::text[])
                    FROM organization_memberships membership
                    JOIN users user_account ON user_account.id = membership.user_id
                    LEFT JOIN membership_roles role
                      ON role.membership_id = membership.id
                    WHERE membership.organization_id = %s
                    GROUP BY membership.id, user_account.id, user_account.email,
                             user_account.display_name, membership.status,
                             membership.joined_at, membership.revoked_at
                    ORDER BY user_account.display_name, user_account.email
                    """,
                    (organization_id,),
                )
                return [
                    {
                        "membership_id": str(row[0]), "user_id": str(row[1]),
                        "email": row[2], "display_name": row[3],
                        "status": row[4], "joined_at": row[5],
                        "revoked_at": row[6], "roles": sorted(row[7] or []),
                    }
                    for row in cursor.fetchall()
                ]

    def nr1_list_responsibles(self, organization_id: str) -> list[dict]:
        """Quem pode ser nomeado responsável por uma medida do plano de ação.

        1.5.5.2.2 exige responsável para cada medida, e quem preenche o plano é o
        `compliance_manager` — que não tem `members.manage` e portanto não
        consegue listar membros pela rota administrativa. Sem esta consulta o
        campo de responsável seria um UUID digitado à mão, e o resultado
        previsível é plano com responsável em branco.

        Devolve o mínimo: identificação da associação e o nome de exibição.
        Nenhum e-mail, nenhum papel, nenhum dado clínico — é a lista de quem
        pode assinar uma medida, não um diretório de pessoal.
        """
        if not self.enabled:
            return []
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT membership.id, user_account.display_name
                    FROM organization_memberships membership
                    JOIN users user_account ON user_account.id = membership.user_id
                    WHERE membership.organization_id = %s
                      AND membership.status = 'active'
                    ORDER BY user_account.display_name
                    """,
                    (organization_id,),
                )
                return [
                    {"membership_id": str(row[0]), "display_name": row[1] or ""}
                    for row in cursor.fetchall()
                ]

    def create_member_invitation(
        self,
        *,
        organization_id: str,
        invited_by_membership_id: str,
        invited_email: str,
        token_hash: str,
        roles: Iterable[str],
        expires_at: datetime,
    ) -> str:
        invitation_id = uuid.uuid4()
        with self._connect() as connection:
            self.ensure_schema(connection)
            organization = connection.execute(
                "SELECT id FROM organizations WHERE id=%s FOR UPDATE",
                (organization_id,),
            ).fetchone()
            if not organization:
                raise ValueError("organization_not_found")
            normalized_email = normalize_email(invited_email)
            connection.execute(
                """UPDATE membership_invitations
                SET status='revoked',revoked_at=now()
                WHERE organization_id=%s AND lower(invited_email)=%s
                  AND status='pending'""",
                (organization_id, normalized_email),
            )
            entitlement = connection.execute(
                """SELECT coalesce((p.entitlements->>'organization_members')::integer,1)
                FROM organization_subscriptions s JOIN subscription_plans p
                ON p.code=s.plan_code WHERE s.organization_id=%s
                AND s.status IN ('active','trialing')
                FOR UPDATE OF s""",
                (organization_id,),
            ).fetchone()
            if entitlement:
                occupied = connection.execute(
                    """SELECT
                    (SELECT count(*) FROM organization_memberships WHERE organization_id=%s AND status IN ('active','invited')) +
                    (SELECT count(*) FROM membership_invitations WHERE organization_id=%s AND status='pending' AND expires_at>now())""",
                    (organization_id, organization_id),
                ).fetchone()[0]
                if int(occupied) >= int(entitlement[0]):
                    raise ValueError("organization_member_limit_reached")
            connection.execute(
                """
                INSERT INTO membership_invitations
                    (id, organization_id, invited_email,
                     invited_by_membership_id, token_hash, requested_roles,
                     expires_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
                """,
                (
                    invitation_id, organization_id, normalized_email,
                    invited_by_membership_id, token_hash,
                    _json(sorted(set(roles))), expires_at,
                ),
            )
            connection.commit()
        return str(invitation_id)

    def accept_member_invitation(
        self, *, token_hash: str, email: str, display_name: str
    ) -> dict:
        normalized_email = normalize_email(email)
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, organization_id, invited_email, requested_roles
                    FROM membership_invitations
                    WHERE token_hash=%s AND status='pending' AND expires_at > now()
                    FOR UPDATE
                    """,
                    (token_hash,),
                )
                invitation = cursor.fetchone()
                if not invitation:
                    raise ValueError("invalid_or_expired_invitation")
                if normalize_email(invitation[2]) != normalized_email:
                    raise PermissionError("invitation_email_mismatch")
                organization_id = invitation[1]
                roles = invitation[3]
                if isinstance(roles, str):
                    roles = json.loads(roles)
                roles = {
                    str(role).strip().lower() for role in (roles or [])
                    if str(role).strip()
                }
                if not roles or roles - VALID_MEMBERSHIP_ROLES:
                    raise ValueError("invalid_invitation_roles")
                user_id = stable_uuid("user", normalized_email)
                membership_id = stable_uuid("membership", organization_id, user_id)
                entitlement = cursor.execute(
                    """SELECT s.status,
                    coalesce((p.entitlements->>'organization_members')::integer,1)
                    FROM organization_subscriptions s JOIN subscription_plans p
                    ON p.code=s.plan_code WHERE s.organization_id=%s
                    FOR UPDATE OF s""",
                    (organization_id,),
                ).fetchone()
                if entitlement:
                    if entitlement[0] not in {"active", "trialing"}:
                        raise ValueError("organization_subscription_inactive")
                    current = cursor.execute(
                        """SELECT status FROM organization_memberships
                        WHERE organization_id=%s AND user_id=%s""",
                        (organization_id, user_id),
                    ).fetchone()
                    active_count = cursor.execute(
                        """SELECT count(*) FROM organization_memberships
                        WHERE organization_id=%s AND status='active'""",
                        (organization_id,),
                    ).fetchone()[0]
                    if (
                        (not current or current[0] != "active")
                        and int(active_count) >= int(entitlement[1])
                    ):
                        raise ValueError("organization_member_limit_reached")
                now = datetime.now(timezone.utc)
                cursor.execute(
                    """
                    INSERT INTO users (id, email, display_name, status)
                    VALUES (%s,%s,%s,'active')
                    ON CONFLICT (id) DO UPDATE SET
                        display_name=EXCLUDED.display_name, status='active',
                        updated_at=now()
                    """,
                    (user_id, normalized_email, display_name or normalized_email),
                )
                cursor.execute(
                    """
                    INSERT INTO organization_memberships
                        (id, organization_id, user_id, status, joined_at)
                    VALUES (%s,%s,%s,'active',%s)
                    ON CONFLICT (organization_id, user_id) DO UPDATE SET
                        status='active', joined_at=EXCLUDED.joined_at,
                        revoked_at=NULL, updated_at=now()
                    """,
                    (membership_id, organization_id, user_id, now),
                )
                cursor.execute(
                    "DELETE FROM membership_roles WHERE membership_id=%s",
                    (membership_id,),
                )
                for role in roles or []:
                    cursor.execute(
                        "INSERT INTO membership_roles (membership_id, role) VALUES (%s,%s)",
                        (membership_id, role),
                    )
                cursor.execute(
                    """
                    UPDATE membership_invitations
                    SET status='accepted', accepted_at=%s WHERE id=%s
                    """,
                    (now, invitation[0]),
                )
            connection.commit()
        return {
            "organization_id": str(organization_id),
            "membership_id": str(membership_id),
            "user_id": str(user_id),
            "roles": sorted(roles),
            "status": "active",
        }

    def revoke_membership(
        self, *, organization_id: str, membership_id: str,
        allow_owner_revoke: bool = False,
    ) -> None:
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM membership_roles
                        WHERE membership_id=%s AND role='owner'
                    )
                    """,
                    (membership_id,),
                )
                target_is_owner = bool(cursor.fetchone()[0])
                if target_is_owner:
                    if not allow_owner_revoke:
                        raise PermissionError("only_owner_can_revoke_owner")
                    cursor.execute(
                        """
                        SELECT count(*)
                        FROM organization_memberships membership
                        JOIN membership_roles role ON role.membership_id=membership.id
                        WHERE membership.organization_id=%s
                          AND membership.status='active' AND role.role='owner'
                        """,
                        (organization_id,),
                    )
                    if int(cursor.fetchone()[0]) <= 1:
                        raise ValueError("cannot_revoke_last_owner")
                cursor.execute(
                    """
                    UPDATE organization_memberships
                    SET status='revoked', revoked_at=now(), updated_at=now()
                    WHERE id=%s AND organization_id=%s AND status <> 'revoked'
                    """,
                    (membership_id, organization_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError("membership_not_found")
                cursor.execute(
                    """
                    UPDATE patient_assignments
                    SET status='revoked', revoked_at=now()
                    WHERE organization_id=%s AND membership_id=%s AND status='active'
                    """,
                    (organization_id, membership_id),
                )
                cursor.execute(
                    """
                    UPDATE membership_invitations
                    SET status='revoked', revoked_at=now()
                    WHERE organization_id=%s AND invited_by_membership_id=%s
                      AND status='pending'
                    """,
                    (organization_id, membership_id),
                )
            connection.commit()

    def list_patient_assignments(
        self, *, organization_id: str, patient_id: str
    ) -> list[dict]:
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT assignment.id, assignment.membership_id,
                           assignment.assignment_type, assignment.status,
                           assignment.assigned_at, assignment.revoked_at,
                           user_account.email, user_account.display_name
                    FROM patient_assignments assignment
                    JOIN organization_memberships membership
                      ON membership.id=assignment.membership_id
                     AND membership.organization_id=assignment.organization_id
                    JOIN users user_account ON user_account.id=membership.user_id
                    WHERE assignment.organization_id=%s
                      AND assignment.patient_id=%s
                    ORDER BY assignment.status, user_account.display_name,
                             assignment.assigned_at
                    """,
                    (organization_id, patient_id),
                )
                return [
                    {
                        "assignment_id": str(row[0]),
                        "membership_id": str(row[1]),
                        "assignment_type": row[2], "status": row[3],
                        "assigned_at": row[4], "revoked_at": row[5],
                        "professional_email": row[6],
                        "professional_name": row[7],
                    }
                    for row in cursor.fetchall()
                ]

    def assign_patient(
        self,
        *,
        organization_id: str,
        patient_id: str,
        membership_id: str,
        assignment_type: str,
    ) -> str:
        assignment_id = stable_uuid(
            "assignment", patient_id, membership_id, assignment_type
        )
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status FROM patients
                    WHERE id=%s AND organization_id=%s
                    FOR UPDATE
                    """,
                    (patient_id, organization_id),
                )
                patient = cursor.fetchone()
                if not patient or patient[0] in {"deleted", "restricted"}:
                    raise ValueError("patient_not_found")
                cursor.execute(
                    """SELECT coalesce(array_agg(role.role) FILTER (
                    WHERE role.role IS NOT NULL), ARRAY[]::text[])
                    FROM organization_memberships membership
                    LEFT JOIN membership_roles role ON role.membership_id=membership.id
                    WHERE membership.id=%s AND membership.organization_id=%s
                      AND membership.status='active'
                    GROUP BY membership.id""",
                    (membership_id, organization_id),
                )
                membership = cursor.fetchone()
                if not membership:
                    raise ValueError("membership_not_found")
                target_roles = set(membership[0] or [])
                required_roles = {
                    "primary": {"professional"},
                    "care_team": {"professional"},
                    "supervisor": {"supervisor"},
                    "read_only": {"professional", "supervisor"},
                }.get(assignment_type, set())
                if not (target_roles & required_roles):
                    raise ValueError("assignment_role_mismatch")
                if assignment_type == "primary":
                    cursor.execute(
                        """SELECT id FROM patient_assignments
                        WHERE organization_id=%s AND patient_id=%s
                          AND assignment_type='primary' AND status='active'
                          AND membership_id<>%s""",
                        (organization_id, patient_id, membership_id),
                    )
                    if cursor.fetchone():
                        raise ValueError("primary_assignment_exists")
                cursor.execute(
                    """
                    INSERT INTO patient_assignments
                        (id, organization_id, patient_id, membership_id,
                         assignment_type, status, assigned_at)
                    VALUES (%s,%s,%s,%s,%s,'active',now())
                    ON CONFLICT (patient_id, membership_id, assignment_type)
                    DO UPDATE SET status='active', assigned_at=now(),
                                  revoked_at=NULL
                    """,
                    (
                        assignment_id, organization_id, patient_id,
                        membership_id, assignment_type,
                    ),
                )
            connection.commit()
        return str(assignment_id)

    def revoke_patient_assignment(
        self, *, organization_id: str, patient_id: str, assignment_id: str
    ) -> None:
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE patient_assignments
                    SET status='revoked', revoked_at=now()
                    WHERE id=%s AND organization_id=%s AND patient_id=%s
                      AND status='active'
                    """,
                    (assignment_id, organization_id, patient_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError("assignment_not_found")
            connection.commit()

    def activate_shared_wallet(
        self,
        *,
        organization_id: str,
        membership_id: str,
        actor_user_id: str,
        expected_legacy_balance: int,
    ) -> dict:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                row = connection.execute(
                    """
                    SELECT resulting_balance, activated
                    FROM froid_activate_shared_wallet(%s,%s,%s,%s)
                    """,
                    (
                        organization_id, membership_id, actor_user_id,
                        max(0, int(expected_legacy_balance)),
                    ),
                ).fetchone()
        return {"balance": int(row[0]), "activated": bool(row[1])}

    def report_visibility(self, *, organization_id: str, membership_id: str) -> str:
        """Politica vigente de visibilidade de relatorios da organizacao.

        Devolve 'restricted' (padrao seguro) sempre que a informacao nao puder
        ser lida - nunca 'clinic_wide' por omissao, para que uma falha de
        leitura jamais amplie o acesso a dado sensivel de saude.
        """
        if not self.enabled or not self.runtime_database_url:
            return "restricted"
        try:
            with self._connect(runtime=True) as connection:
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('app.organization_id', %s, true)",
                        (organization_id,),
                    )
                    connection.execute(
                        "SELECT set_config('app.membership_id', %s, true)",
                        (membership_id,),
                    )
                    row = connection.execute(
                        "SELECT report_visibility FROM organizations WHERE id=%s",
                        (organization_id,),
                    ).fetchone()
        except Exception:
            return "restricted"
        if not row or str(row[0]) != "clinic_wide":
            return "restricted"
        return "clinic_wide"

    def set_report_visibility(
        self,
        *,
        organization_id: str,
        membership_id: str,
        actor_user_id: str,
        visibility: str,
    ) -> dict:
        """Define a politica de visibilidade (owner/administrator da clinica)."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                row = connection.execute(
                    """
                    SELECT report_visibility, changed
                    FROM froid_set_report_visibility(%s,%s,%s,%s)
                    """,
                    (organization_id, membership_id, actor_user_id, visibility),
                ).fetchone()
        return {"report_visibility": str(row[0]), "changed": bool(row[1])}

    def set_member_quota(
        self,
        *,
        organization_id: str,
        membership_id: str,
        actor_user_id: str,
        target_membership_id: str,
        quota_sessions: Optional[int],
    ) -> dict:
        """Define, ajusta ou remove a cota individual de um profissional.

        ``quota_sessions=None`` remove a cota e devolve o profissional ao pool
        livre. A autorizacao (owner/administrator) e conferida dentro da funcao
        SECURITY DEFINER, junto do contexto de organizacao/membership.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        quota = None if quota_sessions is None else max(0, int(quota_sessions))
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                row = connection.execute(
                    """
                    SELECT quota_sessions, consumed_sessions, removed
                    FROM froid_set_member_quota(%s,%s,%s,%s,%s)
                    """,
                    (
                        organization_id,
                        membership_id,
                        actor_user_id,
                        target_membership_id,
                        quota,
                    ),
                ).fetchone()
        removed = bool(row[2])
        return {
            "membership_id": target_membership_id,
            "removed": removed,
            "quota_sessions": None if removed else int(row[0]),
            "consumed_sessions": None if removed else int(row[1]),
            "quota_remaining": (
                None if removed else max(0, int(row[0]) - int(row[1]))
            ),
        }

    def wallet_status(self, *, organization_id: str, membership_id: str) -> dict:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                row = connection.execute(
                    """
                    SELECT balance, version, authority, updated_at
                    FROM organization_wallets WHERE organization_id=%s
                    """,
                    (organization_id,),
                ).fetchone()
        if not row:
            raise ValueError("wallet_not_found")
        return {
            "balance": int(row[0]), "version": int(row[1]),
            "authority": row[2], "updated_at": row[3],
        }

    def organization_usage_report(
        self, *, organization_id: str, membership_id: str
    ) -> dict:
        """Relatorio consolidado da clinica: saldo, uso e pacientes por profissional.

        Responde as tres perguntas do gestor num unico lugar: quanto sobrou para
        a clinica, quanto cada profissional consumiu, e quantos pacientes cada um
        atende. O consumo por profissional vem do ``credit_ledger``, que atribui
        cada debito ao seu ator - e a unica fonte fiel, porque os contadores
        legados por profissional viram mera projecao do saldo compartilhado.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                wallet = connection.execute(
                    "SELECT balance, authority, updated_at FROM organization_wallets "
                    "WHERE organization_id=%s",
                    (organization_id,),
                ).fetchone()
                visibility_row = connection.execute(
                    "SELECT report_visibility FROM organizations WHERE id=%s",
                    (organization_id,),
                ).fetchone()
                members = connection.execute(
                    """
                    SELECT
                        membership.id,
                        user_account.email,
                        coalesce(
                            string_agg(DISTINCT membership_role.role, ',' ORDER BY membership_role.role),
                            ''
                        ) AS roles,
                        (SELECT count(*) FROM credit_ledger ledger
                          WHERE ledger.organization_id = membership.organization_id
                            AND ledger.event_type = 'consumption'
                            AND ledger.actor_user_id = membership.user_id) AS sessions_used,
                        (SELECT count(DISTINCT assignment.patient_id)
                           FROM patient_assignments assignment
                          WHERE assignment.organization_id = membership.organization_id
                            AND assignment.membership_id = membership.id) AS patients,
                        quota.quota_sessions,
                        quota.consumed_sessions
                    FROM organization_memberships membership
                    JOIN users user_account ON user_account.id = membership.user_id
                    LEFT JOIN membership_roles membership_role
                           ON membership_role.membership_id = membership.id
                    LEFT JOIN organization_member_quotas quota
                           ON quota.organization_id = membership.organization_id
                          AND quota.membership_id = membership.id
                    WHERE membership.organization_id = %s
                      AND membership.status = 'active'
                    GROUP BY membership.id, membership.organization_id, membership.user_id,
                             user_account.email, quota.quota_sessions, quota.consumed_sessions
                    ORDER BY user_account.email
                    """,
                    (organization_id,),
                ).fetchall()
                consumed_total = connection.execute(
                    "SELECT count(*) FROM credit_ledger WHERE organization_id=%s "
                    "AND event_type='consumption'",
                    (organization_id,),
                ).fetchone()
        if not wallet:
            raise ValueError("wallet_not_found")
        professionals = [
            {
                "membership_id": str(row[0]),
                "email": row[1],
                "roles": [role for role in str(row[2] or "").split(",") if role],
                "sessions_used": int(row[3] or 0),
                "patients": int(row[4] or 0),
                "quota_sessions": None if row[5] is None else int(row[5]),
                "quota_consumed": None if row[6] is None else int(row[6]),
                "quota_remaining": (
                    None if row[5] is None else max(0, int(row[5]) - int(row[6] or 0))
                ),
            }
            for row in members
        ]
        return {
            "organization_id": organization_id,
            "pool_balance": int(wallet[0]),
            "pool_authority": wallet[1],
            "pool_updated_at": wallet[2],
            "report_visibility": (
                "clinic_wide"
                if visibility_row and str(visibility_row[0]) == "clinic_wide"
                else "restricted"
            ),
            "sessions_used_total": int(consumed_total[0] if consumed_total else 0),
            "professionals": professionals,
        }

    def subscription_status(
        self, *, organization_id: str, membership_id: str
    ) -> Optional[dict]:
        """Read the current subscription through the restricted runtime role."""
        if not self.enabled or not self.runtime_database_url:
            return None
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                row = connection.execute(
                    """
                    SELECT s.plan_code, s.status, s.current_period_start,
                           s.current_period_end, s.cancel_at_period_end,
                           p.display_name, p.entitlements, s.package_code,
                           s.sessions_per_recharge, s.auto_replenish,
                           s.last_recharge_status, s.currency,
                           s.recharge_amount_cents,
                           s.auto_replenish_consent_at,
                           s.auto_replenish_terms_version
                    FROM organization_subscriptions s
                    JOIN subscription_plans p ON p.code=s.plan_code
                    WHERE s.organization_id=%s
                    """,
                    (organization_id,),
                ).fetchone()
        if not row:
            return None
        return {
            "plan_code": row[0], "status": row[1],
            "current_period_start": row[2], "current_period_end": row[3],
            "cancel_at_period_end": bool(row[4]), "display_name": row[5],
            "entitlements": row[6] if isinstance(row[6], dict) else {},
            "package_code": row[7], "sessions_per_recharge": int(row[8]),
            "auto_replenish": bool(row[9]), "last_recharge_status": row[10],
            "currency": row[11], "recharge_amount_minor": int(row[12]),
            "auto_replenish_consent_at": row[13],
            "auto_replenish_terms_version": row[14],
        }

    def _reconcile_legacy_wallet_for_purchase(
        self, connection, *, organization_id: str, balance: int, checkout_event_id: str,
    ) -> None:
        """Activate a legacy wallet only when its opening ledger proves the balance."""
        opening = connection.execute(
            """SELECT delta,balance_after FROM credit_ledger
            WHERE organization_id=%s AND idempotency_key='legacy-opening-v1'
            FOR UPDATE""",
            (organization_id,),
        ).fetchone()
        if (
            not opening
            or int(opening[0]) != int(balance)
            or int(opening[1]) != int(balance)
        ):
            raise RuntimeError("legacy wallet opening balance reconciliation failed")
        connection.execute(
            """UPDATE organization_wallets
            SET authority='shared',version=version+1,updated_at=now()
            WHERE organization_id=%s AND authority='legacy' AND balance=%s""",
            (organization_id, int(balance)),
        )
        connection.execute(
            """INSERT INTO audit_events(
            id,organization_id,action,resource_type,resource_id,outcome,metadata)
            VALUES(%s,%s,'wallet.legacy_reconciled_for_purchase','organization_wallet',
            %s,'success',%s::jsonb)""",
            (
                uuid.uuid4(), organization_id, organization_id,
                _json({
                    "legacy_balance_preserved": int(balance),
                    "checkout_event_id": checkout_event_id,
                }),
            ),
        )

    def apply_checkout_purchase(
        self, *, event_id: str, event_type: str, payload_sha256: str,
        organization_id: str, plan_code: str, package_code: str,
        session_credits: int, amount_cents: int, stripe_customer_id: str,
        stripe_payment_method_id: str, currency: str, terms_version: str,
        auto_replenish: bool,
    ) -> dict:
        """Activate access and credit a paid package exactly once."""
        if not self.enabled:
            raise RuntimeError("package persistence requires dual mode")
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.transaction():
                inserted = connection.execute(
                    """INSERT INTO stripe_webhook_events(event_id,event_type,payload_sha256)
                    VALUES(%s,%s,%s) ON CONFLICT(event_id) DO NOTHING RETURNING event_id""",
                    (event_id, event_type, payload_sha256),
                ).fetchone()
                if not inserted:
                    return {"applied": False}
                wallet = connection.execute(
                    "SELECT balance,authority FROM organization_wallets WHERE organization_id=%s FOR UPDATE",
                    (organization_id,),
                ).fetchone()
                if not wallet:
                    connection.execute(
                        "INSERT INTO organization_wallets(organization_id,balance,authority) VALUES(%s,0,'shared')",
                        (organization_id,),
                    )
                    balance = 0
                else:
                    balance = int(wallet[0])
                    if wallet[1] != "shared":
                        self._reconcile_legacy_wallet_for_purchase(
                            connection,
                            organization_id=organization_id,
                            balance=balance,
                            checkout_event_id=event_id,
                        )
                new_balance = balance + int(session_credits)
                connection.execute(
                    "UPDATE organization_wallets SET balance=%s,version=version+1,updated_at=now() WHERE organization_id=%s",
                    (new_balance, organization_id),
                )
                connection.execute(
                    """UPDATE automatic_recharges
                    SET status='failed',failure_code='superseded_by_checkout',updated_at=now()
                    WHERE organization_id=%s
                      AND status IN ('pending','processing','action_required')""",
                    (organization_id,),
                )
                connection.execute(
                    """INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,
                    idempotency_key,metadata) VALUES(%s,%s,%s,%s,'purchase',%s,%s::jsonb)""",
                    (uuid.uuid4(), organization_id, int(session_credits), new_balance,
                     f"stripe:{event_id}", _json({
                         "package_code": package_code, "currency": currency,
                         "amount_minor": int(amount_cents),
                     })),
                )
                connection.execute(
                    """INSERT INTO organization_subscriptions(
                    organization_id,plan_code,package_code,sessions_per_recharge,recharge_amount_cents,
                    currency,status,stripe_customer_id,stripe_payment_method_id,auto_replenish,
                    auto_replenish_consent_at,auto_replenish_terms_version,last_recharge_status)
                    VALUES(%s,%s,%s,%s,%s,%s,'active',%s,%s,%s,
                    CASE WHEN %s THEN now() ELSE NULL END,%s,
                    CASE WHEN %s THEN 'succeeded' ELSE 'not_started' END)
                    ON CONFLICT(organization_id) DO UPDATE SET plan_code=excluded.plan_code,
                    package_code=excluded.package_code,sessions_per_recharge=excluded.sessions_per_recharge,
                    recharge_amount_cents=excluded.recharge_amount_cents,currency=excluded.currency,status='active',
                    stripe_customer_id=excluded.stripe_customer_id,
                    stripe_payment_method_id=excluded.stripe_payment_method_id,
                    auto_replenish=excluded.auto_replenish,
                    auto_replenish_consent_at=excluded.auto_replenish_consent_at,
                    auto_replenish_terms_version=excluded.auto_replenish_terms_version,
                    last_recharge_status=excluded.last_recharge_status,updated_at=now()""",
                    (organization_id, plan_code, package_code, int(session_credits),
                     int(amount_cents), currency, stripe_customer_id,
                     stripe_payment_method_id, bool(auto_replenish),
                     bool(auto_replenish), terms_version or None,
                     bool(auto_replenish)),
                )
        return {"applied": True, "balance": new_balance}

    def prepare_auto_recharge(self, *, organization_id: str) -> Optional[dict]:
        """Reserve one recharge when an active shared wallet reaches zero."""
        if not self.enabled:
            return None
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.transaction():
                row = connection.execute(
                    """SELECT s.package_code,s.sessions_per_recharge,s.recharge_amount_cents,
                    s.stripe_customer_id,s.stripe_payment_method_id,w.balance,s.currency
                    FROM organization_subscriptions s JOIN organization_wallets w
                    ON w.organization_id=s.organization_id
                    WHERE s.organization_id=%s AND s.status='active' AND s.auto_replenish
                    AND w.authority='shared' FOR UPDATE OF s,w""",
                    (organization_id,),
                ).fetchone()
                if not row or int(row[5]) != 0 or not row[3] or not row[4]:
                    return None
                open_recharge = connection.execute(
                    "SELECT id FROM automatic_recharges WHERE organization_id=%s AND status IN ('pending','processing','action_required')",
                    (organization_id,),
                ).fetchone()
                if open_recharge:
                    return None
                recharge_id = uuid.uuid4()
                idempotency_key = f"froid-recharge:{organization_id}:{recharge_id}"
                connection.execute(
                    """INSERT INTO automatic_recharges(id,organization_id,package_code,
                    session_credits,amount_cents,currency,status,idempotency_key)
                    VALUES(%s,%s,%s,%s,%s,%s,'processing',%s)""",
                    (recharge_id, organization_id, row[0], int(row[1]),
                     int(row[2]), row[6], idempotency_key),
                )
                connection.execute(
                    "UPDATE organization_subscriptions SET last_recharge_status='pending',updated_at=now() WHERE organization_id=%s",
                    (organization_id,),
                )
        return {"recharge_id": str(recharge_id), "package_code": row[0],
                "session_credits": int(row[1]), "amount_cents": int(row[2]),
                "stripe_customer_id": row[3], "stripe_payment_method_id": row[4],
                "currency": row[6], "idempotency_key": idempotency_key}

    def complete_auto_recharge(
        self, *, recharge_id: str, stripe_payment_intent_id: str,
        event_id: str, event_type: str, payload_sha256: str,
        paid_amount_cents: int, paid_currency: str,
    ) -> dict:
        """Credit a successful automatic recharge once, regardless of retries."""
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.transaction():
                connection.execute(
                    """INSERT INTO stripe_webhook_events(event_id,event_type,payload_sha256)
                    VALUES(%s,%s,%s) ON CONFLICT(event_id) DO NOTHING""",
                    (event_id, event_type, payload_sha256),
                )
                recharge = connection.execute(
                    """SELECT organization_id,session_credits,status,amount_cents,currency
                    FROM automatic_recharges
                    WHERE id=%s FOR UPDATE""", (recharge_id,),
                ).fetchone()
                if not recharge or recharge[2] == "succeeded":
                    return {"applied": False}
                if (
                    int(recharge[3]) != int(paid_amount_cents)
                    or recharge[4] != str(paid_currency or "").lower()
                ):
                    raise RuntimeError("automatic recharge amount or currency mismatch")
                wallet = connection.execute(
                    "SELECT balance FROM organization_wallets WHERE organization_id=%s FOR UPDATE",
                    (recharge[0],),
                ).fetchone()
                if not wallet:
                    raise RuntimeError("organization wallet not found")
                new_balance = int(wallet[0]) + int(recharge[1])
                connection.execute(
                    "UPDATE organization_wallets SET balance=%s,version=version+1,updated_at=now() WHERE organization_id=%s",
                    (new_balance, recharge[0]),
                )
                connection.execute(
                    """INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,
                    idempotency_key,metadata) VALUES(%s,%s,%s,%s,'purchase',%s,%s::jsonb)""",
                    (uuid.uuid4(), recharge[0], int(recharge[1]), new_balance,
                     f"recharge:{recharge_id}", _json({"stripe_payment_intent_id": stripe_payment_intent_id})),
                )
                connection.execute(
                    "UPDATE automatic_recharges SET status='succeeded',stripe_payment_intent_id=%s,updated_at=now() WHERE id=%s",
                    (stripe_payment_intent_id, recharge_id),
                )
                connection.execute(
                    "UPDATE organization_subscriptions SET last_recharge_status='succeeded',updated_at=now() WHERE organization_id=%s",
                    (recharge[0],),
                )
        return {"applied": True, "balance": new_balance}

    def fail_auto_recharge(
        self, *, recharge_id: str, status: str, failure_code: str = "",
        stripe_payment_intent_id: str = "",
        event_id: str = "", event_type: str = "", payload_sha256: str = "",
    ) -> None:
        if status not in {"failed", "action_required"}:
            raise ValueError("invalid recharge failure status")
        with self._connect() as connection:
            self.ensure_schema(connection)
            with connection.transaction():
                if event_id:
                    connection.execute(
                        """INSERT INTO stripe_webhook_events(event_id,event_type,payload_sha256)
                        VALUES(%s,%s,%s) ON CONFLICT(event_id) DO NOTHING""",
                        (event_id, event_type, payload_sha256),
                    )
                row = connection.execute(
                    """UPDATE automatic_recharges
                    SET status=%s,failure_code=%s,stripe_payment_intent_id=%s,updated_at=now()
                    WHERE id=%s
                      AND status IN ('pending','processing','action_required')
                    RETURNING organization_id""",
                    (status, failure_code or None, stripe_payment_intent_id or None, recharge_id),
                ).fetchone()
                if row:
                    connection.execute(
                        "UPDATE organization_subscriptions SET last_recharge_status=%s,updated_at=now() WHERE organization_id=%s",
                        (status, row[0]),
                    )

    # ------------------------------------------------------------------
    # NR-1 psychosocial compliance (Portaria MTE 1.419/2024)
    #
    # Every method here runs through the restricted runtime role. That is not a
    # style choice: the runtime role has no SELECT on assessment_responses, so
    # even a mistake in this file cannot read an individual answer back.
    # ------------------------------------------------------------------
    def _nr1_session(self, connection, organization_id: str, membership_id: str) -> None:
        connection.execute(
            "SELECT set_config('app.organization_id', %s, true)", (organization_id,)
        )
        connection.execute(
            "SELECT set_config('app.membership_id', %s, true)", (membership_id,)
        )

    # -- Estrutura da empresa -------------------------------------------------
    #
    # organization_units existia desde a migration 010 e so era LIDO: quatro
    # LEFT JOIN e nenhuma insercao. Na pratica a estrutura de cada cliente
    # entrava no banco a mao, e era por isso que o cadastro da empresa precisava
    # ser "conduzido pela equipe".
    #
    # A hierarquia e de dois niveis por decisao da NR-1, nao por simplificacao:
    # 'site' e o ESTABELECIMENTO, que define a unidade de resultado e a base da
    # cobranca; 'sector' e o recorte dentro dele, que define quais coortes podem
    # ser publicadas. Confundir os dois foi o mal-entendido comercial que a
    # pagina de precos precisou desfazer por escrito.

    UNIT_TYPES = ("site", "sector", "exposure_group")

    def nr1_create_unit(
        self,
        *,
        organization_id: str,
        membership_id: str,
        name: str,
        unit_type: str = "sector",
        parent_unit_id: Optional[str] = None,
        external_code: str = "",
        headcount: int = 0,
    ) -> dict:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        nome = str(name or "").strip()
        if not nome:
            raise ValueError("unidade sem nome")
        if unit_type not in self.UNIT_TYPES:
            raise ValueError(f"unit_type invalido: {unit_type!r}")
        # Setor solto nao existe: ele so significa alguma coisa dentro de um
        # estabelecimento, que e o que a norma chama de unidade.
        if unit_type == "sector" and not parent_unit_id:
            raise ValueError("setor exige o estabelecimento ao qual pertence")
        if unit_type == "site" and parent_unit_id:
            raise ValueError("estabelecimento nao pode ter unidade pai")
        unit_id = str(uuid.uuid4())
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                if parent_unit_id:
                    # O pai precisa ser da MESMA organizacao. A RLS ja filtra a
                    # leitura, mas a checagem explicita transforma um vinculo
                    # cruzado em erro aqui, e nao em linha orfa depois.
                    pai = connection.execute(
                        """
                        SELECT unit_type FROM organization_units
                        WHERE id = %s AND organization_id = %s
                        """,
                        (parent_unit_id, organization_id),
                    ).fetchone()
                    if not pai:
                        raise ValueError("unidade pai inexistente nesta organizacao")
                    if pai[0] != "site":
                        raise ValueError("o pai de um setor precisa ser um estabelecimento")
                connection.execute(
                    """
                    INSERT INTO organization_units
                        (id, organization_id, parent_unit_id, unit_type, name,
                         external_code, headcount)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        unit_id, organization_id, parent_unit_id, unit_type,
                        nome, str(external_code or "").strip() or None,
                        max(0, int(headcount)),
                    ),
                )
        return {
            "unit_id": unit_id,
            "unit_type": unit_type,
            "name": nome,
            "parent_unit_id": parent_unit_id,
            "headcount": max(0, int(headcount)),
        }

    def nr1_list_units(
        self, *, organization_id: str, membership_id: str,
        include_archived: bool = False,
    ) -> list[dict]:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                rows = connection.execute(
                    """
                    SELECT unit.id, unit.parent_unit_id, unit.unit_type,
                           unit.name, unit.external_code, unit.headcount,
                           unit.status,
                           (SELECT count(*) FROM organization_units filho
                             WHERE filho.parent_unit_id = unit.id
                               AND filho.status = 'active') AS filhos
                    FROM organization_units unit
                    WHERE unit.organization_id = %s
                      AND (%s OR unit.status = 'active')
                    ORDER BY unit.unit_type DESC, unit.name
                    """,
                    (organization_id, include_archived),
                ).fetchall()
        return [
            {
                "unit_id": str(row[0]),
                "parent_unit_id": str(row[1]) if row[1] else None,
                "unit_type": row[2],
                "name": row[3],
                "external_code": row[4] or "",
                "headcount": int(row[5]),
                "status": row[6],
                "child_count": int(row[7]),
            }
            for row in rows
        ]

    def nr1_update_unit(
        self,
        *,
        organization_id: str,
        membership_id: str,
        unit_id: str,
        name: Optional[str] = None,
        external_code: Optional[str] = None,
        headcount: Optional[int] = None,
        status: Optional[str] = None,
    ) -> dict:
        """Renomeia, recontabiliza ou arquiva. Nunca apaga.

        A NR-1 exige guardar o historico do inventario por vinte anos, e o
        inventario aponta para a unidade. Apagar a linha deixaria o registro
        antigo sem referencia — por isso 'archived' e a unica remocao possivel,
        e por isso a propria migration usa ON DELETE RESTRICT.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        if status is not None and status not in ("active", "archived"):
            raise ValueError(f"status invalido: {status!r}")
        campos: list[str] = []
        valores: list = []
        if name is not None:
            nome = str(name).strip()
            if not nome:
                raise ValueError("unidade sem nome")
            campos.append("name = %s")
            valores.append(nome)
        if external_code is not None:
            campos.append("external_code = %s")
            valores.append(str(external_code).strip() or None)
        if headcount is not None:
            campos.append("headcount = %s")
            valores.append(max(0, int(headcount)))
        if status is not None:
            campos.append("status = %s")
            valores.append(status)
        if not campos:
            raise ValueError("nada a atualizar")
        campos.append("updated_at = now()")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                if status == "archived":
                    # Arquivar um estabelecimento com setores ativos deixaria os
                    # setores pendurados num pai invisivel.
                    ativos = connection.execute(
                        """
                        SELECT count(*) FROM organization_units
                        WHERE parent_unit_id = %s AND status = 'active'
                        """,
                        (unit_id,),
                    ).fetchone()
                    if ativos and int(ativos[0]) > 0:
                        raise ValueError(
                            "arquive ou mova os setores antes do estabelecimento"
                        )
                linha = connection.execute(
                    f"""
                    UPDATE organization_units
                       SET {", ".join(campos)}
                     WHERE id = %s AND organization_id = %s
                     RETURNING id, unit_type, name, headcount, status
                    """,
                    (*valores, unit_id, organization_id),
                ).fetchone()
        if not linha:
            raise ValueError("unidade inexistente nesta organizacao")
        return {
            "unit_id": str(linha[0]),
            "unit_type": linha[1],
            "name": linha[2],
            "headcount": int(linha[3]),
            "status": linha[4],
        }

    def nr1_list_instruments(self) -> list[dict]:
        """Os instrumentos publicados, para a tela de campanha escolher um.

        Existe porque o `instrument_id` era a unica coisa que a criacao de
        campanha exigia e nenhuma rota devolvia. A alternativa era fixar o UUID
        no front — e o modulo ja tem quatro copias espelhadas de parametros que
        so o banco decide, com o historico de uma delas sobreviver a uma
        migration em silencio. Publicada a versao 1.1, uma copia fixa
        continuaria abrindo campanha na 1.0 sem ninguem notar.

        Catalogo global de proposito: `assessment_instruments` nao tem
        organization_id nem RLS, e o GRANT SELECT ao froid_runtime e da
        migration 010. Nao ha o que vazar entre organizacoes aqui — o
        instrumento e o mesmo para todas.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            linhas = connection.execute(
                """
                SELECT id, code, version, title, language,
                       scale_min, scale_max, scale_labels, source_reference,
                       published_at
                  FROM assessment_instruments
                 WHERE status = 'published'
                 ORDER BY code, version DESC
                """
            ).fetchall()
        return [
            {
                "instrument_id": str(linha[0]),
                "code": linha[1],
                "version": linha[2],
                "title": linha[3],
                "language": linha[4],
                "scale_min": int(linha[5]),
                "scale_max": int(linha[6]),
                "scale_labels": linha[7] or [],
                "source_reference": linha[8] or "",
                "published_at": linha[9].isoformat() if linha[9] else "",
            }
            for linha in linhas
        ]

    def list_legal_acceptances(
        self, *, subject_reference_hash: str, organization_id: str = ""
    ) -> list[dict]:
        """As aceitacoes registradas para UM sujeito, para o comprovante.

        Le pela conexao do dono, e nao pela de runtime, porque a migration 009
        REVOKE ALL de `legal_acceptance_events` para froid_runtime: prova
        juridica nao passa pelo papel que atende requisicao.

        **Filtra pelo sujeito, nao pela organizacao.** Duas razoes. A primeira e
        que o comprovante responde "quem aceitou o que", e o sujeito e a
        identidade do ato — a organizacao e contexto. A segunda e concreta: ate
        agora o cadastro gravava aqui a organizacao derivada do E-MAIL, enquanto
        a empresa NR-1 vive na organizacao derivada do CNPJ. Filtrar por
        organizacao devolveria vazio justamente para o caso que motivou esta
        funcao. A gravacao foi corrigida; a tabela e append-only, entao as
        linhas antigas continuam com o id velho e precisam ser encontradas.

        `organization_id` fica como filtro OPCIONAL, para quando se quiser
        exatamente o que foi aceito sob uma organizacao.
        """
        if not self.enabled:
            return []
        alvo = str(subject_reference_hash or "").strip()
        if not alvo:
            return []
        clausulas = ["subject_reference_hash = %s"]
        valores: list = [alvo]
        if organization_id:
            clausulas.append("organization_id = %s")
            valores.append(organization_id)
        with self._connect() as connection:
            self.ensure_schema(connection)
            linhas = connection.execute(
                f"""
                SELECT document_key, document_version, document_sha256,
                       acceptance_context, accepted_at, organization_id,
                       subject_kind
                  FROM legal_acceptance_events
                 WHERE {" AND ".join(clausulas)}
                 ORDER BY accepted_at ASC
                """,
                tuple(valores),
            ).fetchall()
        return [
            {
                "document_key": linha[0],
                "document_version": linha[1],
                "document_sha256": linha[2],
                "acceptance_context": linha[3],
                "accepted_at": linha[4].isoformat() if linha[4] else "",
                "organization_id": str(linha[5]) if linha[5] else "",
                "subject_kind": linha[6],
            }
            for linha in linhas
        ]

    def nr1_create_campaign(
        self,
        *,
        organization_id: str,
        membership_id: str,
        instrument_id: str,
        title: str,
        opens_at,
        closes_at,
        unit_id: Optional[str] = None,
        reference_period: str = "",
        target_headcount: int = 0,
        purpose_notice: str = "",
        support_channel_label: str = "",
        support_channel_detail: str = "",
    ) -> dict:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        campaign_id = str(uuid.uuid4())
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                connection.execute(
                    """
                    INSERT INTO assessment_campaigns
                        (id, organization_id, instrument_id, unit_id, title,
                         reference_period, target_headcount, opens_at, closes_at,
                         status, created_by_membership_id, purpose_notice,
                         support_channel_label, support_channel_detail)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s,%s)
                    """,
                    (
                        campaign_id, organization_id, instrument_id, unit_id,
                        title, reference_period, max(0, int(target_headcount)),
                        opens_at, closes_at, membership_id, purpose_notice,
                        support_channel_label, support_channel_detail,
                    ),
                )
        return {"campaign_id": campaign_id, "status": "draft"}

    def nr1_open_campaign(
        self, *, organization_id: str, membership_id: str, campaign_id: str
    ) -> dict:
        """Open collection. The database refuses without a support channel."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    """
                    UPDATE assessment_campaigns
                    SET status='open', updated_at=now()
                    WHERE id=%s AND organization_id=%s AND status='draft'
                    RETURNING id
                    """,
                    (campaign_id, organization_id),
                ).fetchone()
        if not row:
            raise ValueError("campaign_not_draft")
        return {"campaign_id": campaign_id, "status": "open"}

    def nr1_close_campaign(
        self, *, organization_id: str, membership_id: str, campaign_id: str
    ) -> dict:
        """Close collection. Only a closed campaign yields an aggregate.

        The cohort has to stop moving before any result is served, otherwise it
        can be differenced one respondent at a time.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    """
                    UPDATE assessment_campaigns
                    SET status='closed', closed_at=now(),
                        closed_by_membership_id=%s, updated_at=now()
                    WHERE id=%s AND organization_id=%s AND status='open'
                    RETURNING id
                    """,
                    (membership_id, campaign_id, organization_id),
                ).fetchone()
        if not row:
            raise ValueError("campaign_not_open")
        return {"campaign_id": campaign_id, "status": "closed"}

    def nr1_list_campaigns(
        self, *, organization_id: str, membership_id: str
    ) -> list[dict]:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                rows = connection.execute(
                    """
                    SELECT campaign.id, campaign.title, campaign.status,
                           campaign.opens_at, campaign.closes_at,
                           campaign.unit_id, unit.name, campaign.target_headcount,
                           campaign.reference_period
                    FROM assessment_campaigns campaign
                    LEFT JOIN organization_units unit ON unit.id = campaign.unit_id
                    WHERE campaign.organization_id = %s
                    ORDER BY campaign.opens_at DESC
                    """,
                    (organization_id,),
                ).fetchall()
        return [
            {
                "campaign_id": str(row[0]), "title": row[1], "status": row[2],
                "opens_at": row[3], "closes_at": row[4],
                "unit_id": str(row[5]) if row[5] else None,
                "unit_name": row[6], "target_headcount": int(row[7]),
                "reference_period": row[8],
            }
            for row in rows
        ]

    def nr1_submit_response(
        self, *, token_hash: str, answers: Dict[str, int]
    ) -> bool:
        """Record one questionnaire submission against an invitation token.

        Takes no organization or membership: the respondent is an employee with
        no FROID login, and the single-use token is the authorization. All the
        validation lives in froid_nr1_submit_response so the rules cannot drift
        between callers. Returns only whether it was accepted — never anything
        about what was answered.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        if not answers:
            raise ValueError("empty_submission")
        payload = json.dumps({str(k): int(v) for k, v in answers.items()})
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                row = connection.execute(
                    "SELECT froid_nr1_submit_response(%s, %s::jsonb)",
                    (token_hash, payload),
                ).fetchone()
        return bool(row[0]) if row else False

    def nr1_create_invitations(
        self,
        *,
        organization_id: str,
        membership_id: str,
        campaign_id: str,
        subjects: Sequence[dict],
    ) -> list[str]:
        """Register invitations from a list of {pseudonym, token_hash, unit_id}.

        The caller hashes both values before they get here: neither the payroll
        number nor the raw token is ever written to the database.

        Devolve os pseudonimos EFETIVAMENTE gravados, e nao uma contagem.

        A diferenca importa porque `ON CONFLICT DO NOTHING` nao levanta erro:
        quem ja tinha convite nesta campanha e simplesmente ignorado. A versao
        anterior contava `created += 1` a cada iteracao, entao devolvia o
        tamanho da lista enviada — e a tela exibia um link para cada linha,
        inclusive para as ignoradas. Esse link nunca existiu no banco: a pessoa
        que o recebesse leria "convite indisponivel", e nao havia como saber
        quais dos links da planilha estavam mortos.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        if not subjects:
            return []
        criados: list[str] = []
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                for subject in subjects:
                    linha = connection.execute(
                        """
                        INSERT INTO assessment_invitations
                            (id, organization_id, campaign_id, unit_id,
                             subject_pseudonym, token_hash)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (campaign_id, subject_pseudonym) DO NOTHING
                        RETURNING subject_pseudonym
                        """,
                        (
                            str(uuid.uuid4()), organization_id, campaign_id,
                            subject.get("unit_id"), subject["pseudonym"],
                            subject["token_hash"],
                        ),
                    ).fetchone()
                    # Sem RETURNING nao ha como distinguir gravado de ignorado:
                    # o ON CONFLICT devolve sucesso nos dois casos.
                    if linha:
                        criados.append(str(linha[0]))
        return criados

    def nr1_reissue_invitations(
        self,
        *,
        organization_id: str,
        membership_id: str,
        campaign_id: str,
        subjects: Sequence[dict],
    ) -> list[str]:
        """Troca o token de um convite que ainda nao foi respondido.

        Existe porque numa campanha de centenas de pessoas alguem apaga a
        mensagem antes de responder, e ate aqui nao havia saida: o servidor
        guarda so o digest do link, e uma segunda emissao para a mesma
        matricula esbarra no UNIQUE (campaign_id, subject_pseudonym). A unica
        alternativa era recriar a campanha inteira.

        Atualiza a linha EXISTENTE em vez de revogar e inserir outra. Nao e
        economia de codigo:

        - a chave unica e por (campanha, pseudonimo), entao uma segunda linha
          para a mesma pessoa nao caberia sem migration;
        - `invited` conta linhas de convite. Duas linhas por pessoa inflariam o
          denominador da adesao — a campanha pareceria ter mais convidados do
          que gente, e a taxa cairia sozinha a cada reemissao.

        O token antigo morre no instante em que o digest e substituido, e isso
        e o comportamento pretendido: quem reemite esta declarando que o link
        anterior se perdeu.

        `status = 'pending'` no WHERE e a trava que importa. Quem ja respondeu
        nao recebe link novo — senao a mesma pessoa responderia duas vezes e a
        coorte contaria dois. Nao ha excecao a isso, nem para administrador.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        if not subjects:
            return []
        reemitidos: list[str] = []
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                for subject in subjects:
                    linha = connection.execute(
                        """
                        UPDATE assessment_invitations
                           SET token_hash = %s, invited_at = now()
                         WHERE campaign_id = %s
                           AND organization_id = %s
                           AND subject_pseudonym = %s
                           AND status = 'pending'
                        RETURNING subject_pseudonym
                        """,
                        (
                            subject["token_hash"], campaign_id, organization_id,
                            subject["pseudonym"],
                        ),
                    ).fetchone()
                    if linha:
                        reemitidos.append(str(linha[0]))
        return reemitidos

    def nr1_questionnaire_for_token(self, *, token_hash: str) -> Optional[dict]:
        """Render payload for one invitation. No tenant session: the token is it."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                row = connection.execute(
                    "SELECT froid_nr1_questionnaire(%s)", (token_hash,)
                ).fetchone()
        payload = row[0] if row else None
        return payload if isinstance(payload, dict) else None

    def nr1_campaign_progress(
        self, *, organization_id: str, membership_id: str, campaign_id: str
    ) -> dict:
        """Adhesion and status, without touching what anyone answered.

        Deliberately readable while the campaign is open: the organization needs
        to chase participation, and a count leaks nothing. The results do not
        follow until the campaign closes.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    """
                    SELECT campaign.status, campaign.target_headcount,
                           (SELECT count(*) FROM assessment_invitations invitation
                             WHERE invitation.campaign_id = campaign.id
                               AND invitation.status = 'responded'),
                           -- Convite revogado nao e convidado: contá-lo
                           -- infla o denominador da adesao e faz a taxa cair
                           -- sozinha a cada correcao de distribuicao.
                           (SELECT count(*) FROM assessment_invitations invitation
                             WHERE invitation.campaign_id = campaign.id
                               AND invitation.status <> 'revoked'),
                           -- Respostas gravadas e respostas substantivas.
                           --
                           -- A submissao aceita o envio quando ao menos UM
                           -- item e valido, o que e a decisao certa na hora de
                           -- gravar: descartar o que a pessoa respondeu seria
                           -- pior. Mas uma resposta de um item conta igual a
                           -- uma de trinta e nove para o piso da campanha.
                           --
                           -- Por dimensao o dado ja esta protegido — quem nao
                           -- respondeu nada de uma dimensao nao entra na
                           -- coorte dela. O que faltava era enxergar a
                           -- diferenca, para que uma campanha cheia de
                           -- respostas parciais deixe de passar por uma
                           -- campanha cheia.
                           --
                           -- As duas contagens saem de funcao SECURITY
                           -- DEFINER, e nao de subselect: o papel de runtime
                           -- nao tem — e nao deve ter — SELECT em
                           -- assessment_responses. Contar aqui direto derrubou
                           -- todo painel NR-1 em producao com
                           -- InsufficientPrivilege, sem que a suite acusasse,
                           -- porque ela roda como owner. Ver migration 029.
                           contagem.recorded,
                           contagem.substantive,
                           -- Tolerancia de amostra vigente para esta campanha.
                           -- Nula quando nao ha criterios vinculados, e nesse
                           -- caso quem le aplica o padrao da plataforma.
                           criteria.sampling_margin_of_error,
                           criteria.sampling_confidence_z,
                           criteria.census_threshold_ratio
                    FROM assessment_campaigns campaign
                    LEFT JOIN gro_risk_criteria criteria
                      ON criteria.id = campaign.criteria_id
                    LEFT JOIN LATERAL
                      froid_nr1_campaign_response_counts(campaign.id) contagem
                      ON TRUE
                    WHERE campaign.id=%s AND campaign.organization_id=%s
                    """,
                    (campaign_id, organization_id),
                ).fetchone()
        if not row:
            raise ValueError("campaign_not_found")
        invited = int(row[3] or 0)
        answered = int(row[2] or 0)
        gravadas = int(row[4] or 0)
        substantivas = int(row[5] or 0)
        return {
            "status": row[0],
            "target_headcount": int(row[1] or 0),
            "responses": answered,
            "invited": invited,
            "response_rate": round(answered / invited, 3) if invited else 0.0,
            "recorded_responses": gravadas,
            "substantive_responses": substantivas,
            "partial_responses": max(0, gravadas - substantivas),
            # Parametros do Portao A, para que a camada HTTP possa explicar a
            # supressao com os numeros que o banco de fato aplicou.
            "sampling_margin_of_error": float(row[6]) if row[6] is not None else None,
            "sampling_confidence_z": float(row[7]) if row[7] is not None else None,
            "census_threshold_ratio": float(row[8]) if row[8] is not None else None,
        }

    def nr1_dimension_scores(
        self, *, organization_id: str, membership_id: str, campaign_id: str
    ) -> list[dict]:
        """Aggregate a campaign through the k-clamped SECURITY DEFINER function.

        Returns an empty list when either floor is unmet — the function itself
        decides that, so no caller can talk its way past it.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                rows = connection.execute(
                    """
                    SELECT unit_id, dimension_id, nr1_factor, polarity,
                           cut_favorable, cut_critical, cohort_size, mean_score,
                           critical_ratio, score_stddev, consequences,
                           measure_efficacy, exposed_workers
                    FROM froid_nr1_dimension_scores(%s)
                    """,
                    (campaign_id,),
                ).fetchall()
        return [
            {
                "unit_id": str(row[0]) if row[0] else None,
                "dimension_id": str(row[1]),
                "nr1_factor": row[2],
                "polarity": row[3],
                "cut_favorable": float(row[4]),
                "cut_critical": float(row[5]),
                "cohort_size": int(row[6]),
                "mean_score": float(row[7]),
                "critical_ratio": float(row[8]),
                "score_stddev": float(row[9] or 0.0),
                "consequences": tuple(row[10] or ("transtorno_mental",)),
                "measure_efficacy": row[11] or "none",
                "exposed_workers": int(row[12] or 0),
            }
            for row in rows
        ]

    def nr1_unclassifiable_cohorts(
        self, *, organization_id: str, membership_id: str, campaign_id: str
    ) -> list[dict]:
        """Os recortes que os portoes reprovaram, e QUAL portao reprovou cada um.

        Complemento exato de nr1_dimension_scores: aquele devolve o que passou,
        este devolve o que nao passou. Existe porque suprimir e ocultar e
        declarar insuficiente e documentar, e ate 25/08/2026 o produto so sabia
        fazer a primeira coisa.

        Nao devolve contagem de resposta do recorte reprovado — o numero esta
        abaixo do piso por definicao, e traze-lo para ca seria publicar pela
        porta dos fundos a coorte que o piso recusou mostrar no painel. Devolve
        o portao, porque o remedio depende dele, e a amostra exigida, que sai do
        efetivo que a propria contratante declarou.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                rows = connection.execute(
                    """
                    SELECT unit_id, dimension_id, nr1_factor, gate,
                           required_responses, declared_headcount
                    FROM froid_nr1_unclassifiable_cohorts(%s)
                    """,
                    (campaign_id,),
                ).fetchall()
        return [
            {
                "unit_id": str(row[0]) if row[0] else None,
                "dimension_id": str(row[1]),
                "nr1_factor": row[2],
                "gate": row[3],
                "required_responses": int(row[4]) if row[4] is not None else None,
                "declared_headcount": int(row[5]) if row[5] is not None else None,
            }
            for row in rows
        ]

    def nr1_active_criteria(
        self, *, organization_id: str, membership_id: str
    ) -> Optional[dict]:
        """Latest published critérios do GRO (1.5.4.4.2.2), if any."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    """
                    SELECT id, version, severity_scale, probability_scale,
                           risk_matrix, consequence_magnitudes,
                           review_interval_months, has_certified_sst_system
                    FROM gro_risk_criteria
                    WHERE organization_id=%s AND published_at IS NOT NULL
                    ORDER BY version DESC LIMIT 1
                    """,
                    (organization_id,),
                ).fetchone()
        if not row:
            return None
        return {
            "criteria_id": str(row[0]), "version": int(row[1]),
            "severity_scale": row[2], "probability_scale": row[3],
            "risk_matrix": row[4], "consequence_magnitudes": row[5],
            "review_interval_months": int(row[6]),
            "has_certified_sst_system": bool(row[7]),
            "source": "organization",
        }

    def nr1_publish_criteria(
        self,
        *,
        organization_id: str,
        membership_id: str,
        document: Dict[str, Any],
        review_interval_months: int = 24,
        has_certified_sst_system: bool = False,
    ) -> dict:
        """Publish a new immutable version of the critérios do GRO."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        criteria_id = str(uuid.uuid4())
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    "SELECT coalesce(max(version),0)+1 FROM gro_risk_criteria "
                    "WHERE organization_id=%s",
                    (organization_id,),
                ).fetchone()
                version = int(row[0] if row else 1)
                connection.execute(
                    """
                    INSERT INTO gro_risk_criteria
                        (id, organization_id, version, severity_scale,
                         probability_scale, risk_matrix, classification_rules,
                         decision_rules, consequence_magnitudes,
                         review_interval_months, has_certified_sst_system,
                         published_at, published_by_membership_id)
                    VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                            %s::jsonb,%s::jsonb,%s,%s,now(),%s)
                    """,
                    (
                        criteria_id, organization_id, version,
                        json.dumps(document.get("severity_scale") or {}),
                        json.dumps(document.get("probability_scale") or {}),
                        json.dumps(document.get("risk_matrix") or {}),
                        json.dumps(document.get("classification_rules") or {}),
                        json.dumps(document.get("decision_rules") or {}),
                        json.dumps(document.get("consequence_magnitudes") or {}),
                        max(1, min(36, int(review_interval_months))),
                        bool(has_certified_sst_system),
                        membership_id,
                    ),
                )
        return {"criteria_id": criteria_id, "version": version}

    def nr1_create_aep(
        self,
        *,
        organization_id: str,
        membership_id: str,
        unit_id: str,
        reference_period: str = "",
        criteria_id: Optional[str] = None,
    ) -> dict:
        """Open an Avaliação Ergonômica Preliminar for one evaluation unit."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        aep_id = str(uuid.uuid4())
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                connection.execute(
                    """
                    INSERT INTO aep_assessments
                        (id, organization_id, unit_id, criteria_id,
                         reference_period, status, responsible_membership_id)
                    VALUES (%s,%s,%s,%s,%s,'draft',%s)
                    """,
                    (
                        aep_id, organization_id, unit_id, criteria_id,
                        reference_period, membership_id,
                    ),
                )
        return {"aep_id": aep_id, "status": "draft"}

    def nr1_add_aep_evidence(
        self,
        *,
        organization_id: str,
        membership_id: str,
        aep_id: str,
        method: str,
        collected_on,
        summary: str,
        collected_by: str = "",
        campaign_id: Optional[str] = None,
        evidence_reference: str = "",
    ) -> str:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        evidence_id = str(uuid.uuid4())
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                connection.execute(
                    """
                    INSERT INTO aep_evidence
                        (id, organization_id, aep_id, method, campaign_id,
                         collected_on, collected_by, summary, evidence_reference)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        evidence_id, organization_id, aep_id, method, campaign_id,
                        collected_on, collected_by, summary, evidence_reference,
                    ),
                )
        return evidence_id

    # Fields the organization fills in while the AEP is being conducted. Kept
    # as an explicit allow-list so a request body can never reach status,
    # concluded_at or the organization: concluding is a separate act.
    NR1_AEP_EDITABLE_FIELDS = (
        "reference_period",
        "real_work_description",
        "exposure_duration",
        "exposure_frequency",
        "exposure_intensity",
        "exposure_cofactors",
        "health_indicators",
        "absenteeism_notes",
        "previous_assessments",
        "responsible_name",
        "responsible_qualification",
        "aet_justification",
    )

    def nr1_update_aep(
        self,
        *,
        organization_id: str,
        membership_id: str,
        aep_id: str,
        fields: Dict[str, Any],
        aet_required: Optional[bool] = None,
    ) -> dict:
        """Fill in the AEP. Refuses once concluded."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        assignments = []
        values: list = []
        for name in self.NR1_AEP_EDITABLE_FIELDS:
            if name in fields:
                assignments.append(f"{name}=%s")
                values.append(str(fields.get(name) or ""))
        if aet_required is not None:
            assignments.append("aet_required=%s")
            values.append(bool(aet_required))
        if not assignments:
            raise ValueError("no_editable_field")
        assignments.append("status=CASE WHEN status='draft' THEN 'in_progress' ELSE status END")
        assignments.append("updated_at=now()")
        values.extend([aep_id, organization_id])
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    f"""
                    UPDATE aep_assessments SET {", ".join(assignments)}
                    WHERE id=%s AND organization_id=%s
                      AND status IN ('draft','in_progress')
                    RETURNING id, status
                    """,
                    tuple(values),
                ).fetchone()
        if not row:
            raise ValueError("aep_not_editable")
        return {"aep_id": str(row[0]), "status": row[1]}

    def nr1_conclude_aep(
        self, *, organization_id: str, membership_id: str, aep_id: str
    ) -> dict:
        """Date and sign the AEP (NR-1 1.5.7.2).

        The database refuses to conclude without a named responsible, so an
        unsigned document cannot be presented as evidence of diligence.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    """
                    UPDATE aep_assessments
                    SET status='concluded', concluded_at=now(), updated_at=now()
                    WHERE id=%s AND organization_id=%s
                      AND status IN ('draft','in_progress')
                      AND btrim(real_work_description) <> ''
                      AND btrim(responsible_name) <> ''
                      AND EXISTS (
                          SELECT 1 FROM aep_evidence evidence
                          WHERE evidence.aep_id = aep_assessments.id
                      )
                    RETURNING id, concluded_at
                    """,
                    (aep_id, organization_id),
                ).fetchone()
        if not row:
            raise ValueError("aep_not_concludable")
        return {
            "aep_id": str(row[0]),
            "status": "concluded",
            "concluded_at": row[1],
        }

    def nr1_list_aep(
        self, *, organization_id: str, membership_id: str
    ) -> list[dict]:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                rows = connection.execute(
                    """
                    SELECT aep.id, aep.unit_id, unit.name, aep.status,
                           aep.reference_period, aep.opened_at, aep.concluded_at,
                           (SELECT count(DISTINCT evidence.method)
                              FROM aep_evidence evidence
                             WHERE evidence.aep_id = aep.id)
                    FROM aep_assessments aep
                    LEFT JOIN organization_units unit ON unit.id = aep.unit_id
                    WHERE aep.organization_id=%s
                    ORDER BY aep.opened_at DESC
                    """,
                    (organization_id,),
                ).fetchall()
        return [
            {
                "aep_id": str(row[0]),
                "unit_id": str(row[1]) if row[1] else None,
                "unit_name": row[2], "status": row[3],
                "reference_period": row[4],
                "opened_at": row[5], "concluded_at": row[6],
                "method_count": int(row[7] or 0),
            }
            for row in rows
        ]

    def nr1_get_aep(
        self, *, organization_id: str, membership_id: str, aep_id: str
    ) -> Optional[dict]:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                head = connection.execute(
                    """
                    SELECT aep.id, aep.unit_id, unit.name, aep.status,
                           aep.reference_period, aep.real_work_description,
                           aep.exposure_duration, aep.exposure_frequency,
                           aep.exposure_intensity, aep.exposure_cofactors,
                           aep.responsible_name, aep.responsible_qualification,
                           aep.aet_required, aep.opened_at, aep.concluded_at,
                           aep.health_indicators, aep.absenteeism_notes,
                           aep.previous_assessments, aep.aet_justification
                    FROM aep_assessments aep
                    LEFT JOIN organization_units unit ON unit.id = aep.unit_id
                    WHERE aep.organization_id=%s AND aep.id=%s
                    """,
                    (organization_id, aep_id),
                ).fetchone()
                if not head:
                    return None
                evidence = connection.execute(
                    """
                    SELECT id, method, collected_on, collected_by, summary,
                           evidence_reference, campaign_id
                    FROM aep_evidence
                    WHERE aep_id=%s ORDER BY collected_on
                    """,
                    (aep_id,),
                ).fetchall()
        return {
            "aep_id": str(head[0]),
            "unit_id": str(head[1]), "unit_name": head[2],
            "status": head[3], "reference_period": head[4],
            "real_work_description": head[5],
            "exposure": {
                "duration": head[6], "frequency": head[7],
                "intensity": head[8], "cofactors": head[9],
            },
            "responsible_name": head[10],
            "responsible_qualification": head[11],
            "aet_required": bool(head[12]),
            "opened_at": head[13], "concluded_at": head[14],
            "preparation": {
                "health_indicators": head[15],
                "absenteeism_notes": head[16],
                "previous_assessments": head[17],
            },
            "aet_justification": head[18],
            "evidence": [
                {
                    "evidence_id": str(item[0]), "method": item[1],
                    "collected_on": item[2], "collected_by": item[3],
                    "summary": item[4], "evidence_reference": item[5],
                    "campaign_id": str(item[6]) if item[6] else None,
                }
                for item in evidence
            ],
        }

    def nr1_store_effectiveness(
        self,
        *,
        organization_id: str,
        membership_id: str,
        baseline_campaign_id: str,
        followup_campaign_id: str,
        verdicts: Sequence[dict],
    ) -> int:
        """Persist measured effectiveness, so the next cycle reads a fact."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        if not verdicts:
            return 0
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                for verdict in verdicts:
                    connection.execute(
                        """
                        INSERT INTO measure_effectiveness_reviews
                            (id, organization_id, unit_id, dimension_id,
                             baseline_campaign_id, followup_campaign_id,
                             baseline_cohort, followup_cohort, baseline_mean,
                             followup_mean, effect_size, verdict,
                             measure_efficacy, requires_correction, rationale)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (followup_campaign_id, unit_id, dimension_id)
                        DO UPDATE SET
                            effect_size=EXCLUDED.effect_size,
                            verdict=EXCLUDED.verdict,
                            measure_efficacy=EXCLUDED.measure_efficacy,
                            requires_correction=EXCLUDED.requires_correction,
                            rationale=EXCLUDED.rationale,
                            reviewed_at=now()
                        """,
                        (
                            str(uuid.uuid4()), organization_id,
                            verdict.get("unit_id"), verdict["dimension_id"],
                            baseline_campaign_id, followup_campaign_id,
                            int(verdict["baseline_cohort"]),
                            int(verdict["followup_cohort"]),
                            float(verdict["baseline_mean"]),
                            float(verdict["followup_mean"]),
                            float(verdict["effect_size"]),
                            verdict["verdict"], verdict["measure_efficacy"],
                            bool(verdict["requires_correction"]),
                            verdict.get("rationale", ""),
                        ),
                    )
        return len(verdicts)

    def nr1_store_inventory(
        self,
        *,
        organization_id: str,
        membership_id: str,
        campaign_id: str,
        graded_rows: Sequence[dict],
        review_interval_months: int = 24,
    ) -> int:
        """Persist the graded risk inventory that feeds the PGR.

        Seis campos de 1.5.7.3.2 vinham calculados do endpoint e eram
        descartados aqui: o INSERT nao os listava. O inventario era gravado com
        as alineas "d", "e", "f" e "g" vazias — justamente as que descrevem o
        agravo possivel, quem esta exposto, que medida ja existe e como e a
        exposicao. Um auditor lendo aquilo via um inventario pela metade.

        `review_due_at` recebe o teto de 1.5.4.4.6: dois anos, ou tres quando a
        organizacao tem sistema de gestao de SST certificado (1.5.4.4.6.1). E
        teto, nao cadencia — a alinea "a" antecipa esta data assim que uma medida
        do plano for implementada, e quem faz isso e o gatilho da migration 026.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        if not graded_rows:
            return 0
        meses = max(1, min(36, int(review_interval_months or 24)))
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                for row in graded_rows:
                    connection.execute(
                        """
                        INSERT INTO psychosocial_risk_inventory
                            (id, organization_id, campaign_id, unit_id, dimension_id,
                             nr1_factor, cohort_size, mean_score, severity,
                             probability, risk_level, rationale,
                             possible_harms, selected_consequence, exposed_workers,
                             measure_efficacy, exposure_level, risk_classification,
                             suppression_gate, escalation_note,
                             review_due_at, review_trigger, criteria_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,%s,
                                now() + make_interval(months => %s), 'scheduled',
                                -- Os critérios em vigor quando a campanha rodou,
                                -- e não os de hoje: gro_risk_criteria é imutável
                                -- depois de publicado justamente para que um
                                -- inventário continue explicável pela régua que
                                -- o produziu.
                                (SELECT campanha.criteria_id
                                   FROM assessment_campaigns campanha
                                  WHERE campanha.id = %s))
                        ON CONFLICT (campaign_id, unit_id, dimension_id)
                        DO UPDATE SET
                            cohort_size=EXCLUDED.cohort_size,
                            mean_score=EXCLUDED.mean_score,
                            severity=EXCLUDED.severity,
                            probability=EXCLUDED.probability,
                            risk_level=EXCLUDED.risk_level,
                            rationale=EXCLUDED.rationale,
                            possible_harms=EXCLUDED.possible_harms,
                            selected_consequence=EXCLUDED.selected_consequence,
                            exposed_workers=EXCLUDED.exposed_workers,
                            measure_efficacy=EXCLUDED.measure_efficacy,
                            exposure_level=EXCLUDED.exposure_level,
                            risk_classification=EXCLUDED.risk_classification,
                            suppression_gate=EXCLUDED.suppression_gate,
                            escalation_note=EXCLUDED.escalation_note,
                            -- Regerar o inventario NAO apaga uma revisao ja
                            -- devida por risco residual: a obrigacao da alinea
                            -- "a" nasceu de um evento que aconteceu, e o teto
                            -- programado nunca a adia.
                            review_due_at=LEAST(
                                psychosocial_risk_inventory.review_due_at,
                                EXCLUDED.review_due_at
                            ),
                            review_trigger=CASE
                                WHEN psychosocial_risk_inventory.review_trigger
                                     = 'residual_risk' THEN 'residual_risk'
                                ELSE EXCLUDED.review_trigger
                            END,
                            generated_at=now()
                        """,
                        (
                            str(uuid.uuid4()), organization_id, campaign_id,
                            row.get("unit_id"), row["dimension_id"],
                            row["nr1_factor"],
                            # Os quatro numeros sao None na linha declarada
                            # insuficiente, e a restricao de banco exige que
                            # sejam. Converter com int() um None estouraria aqui
                            # — e estourar e melhor que gravar zero, que um
                            # auditor leria como coorte de zero pessoa avaliada.
                            _ou_nulo(row.get("cohort_size"), int),
                            _ou_nulo(row.get("mean_score"), float),
                            _ou_nulo(row.get("severity"), int),
                            _ou_nulo(row.get("probability"), int),
                            row["risk_level"],
                            row.get("rationale", ""),
                            list(row.get("possible_harms") or []),
                            row.get("selected_consequence", ""),
                            max(0, int(row.get("exposed_workers") or 0)),
                            row.get("measure_efficacy", "none"),
                            row.get("exposure_level"),
                            row.get("risk_classification", row["risk_level"]),
                            row.get("suppression_gate"),
                            row.get("escalation_note", ""),
                            meses, campaign_id,
                        ),
                    )
        return len(graded_rows)

    def nr1_list_inventory(
        self, *, organization_id: str, membership_id: str, campaign_id: str
    ) -> list[dict]:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                rows = connection.execute(
                    """
                    SELECT inventory.id, inventory.unit_id, unit.name,
                           inventory.dimension_id, dimension.title,
                           inventory.nr1_factor, inventory.cohort_size,
                           inventory.mean_score, inventory.severity,
                           inventory.probability, inventory.risk_level,
                           inventory.rationale, inventory.generated_at,
                           inventory.suppression_gate, inventory.escalation_note,
                           -- O ESTABELECIMENTO do setor, e nao so o setor.
                           --
                           -- "Assedio · Auditoria" nao diz nada a uma empresa
                           -- com onze enderecos, e varias delas repetem o nome
                           -- do setor em cada filial. O documento que a
                           -- fiscalizacao le precisa dizer ONDE, senao a medida
                           -- corretiva nao tem destino.
                           estabelecimento.name
                    FROM psychosocial_risk_inventory inventory
                    JOIN assessment_dimensions dimension
                      ON dimension.id = inventory.dimension_id
                    LEFT JOIN organization_units unit ON unit.id = inventory.unit_id
                    LEFT JOIN organization_units estabelecimento
                      ON estabelecimento.id = unit.parent_unit_id
                    WHERE inventory.organization_id = %s
                      AND inventory.campaign_id = %s
                    -- NULLS LAST porque a linha declarada insuficiente tem
                    -- severidade e probabilidade nulas, e em DESC o Postgres
                    -- poe NULL primeiro: sem isto os recortes que NAO foram
                    -- avaliados apareceriam acima dos riscos criticos.
                    ORDER BY inventory.severity * inventory.probability DESC
                             NULLS LAST,
                             inventory.nr1_factor
                    """,
                    (organization_id, campaign_id),
                ).fetchall()
        return [
            {
                "inventory_id": str(row[0]),
                "unit_id": str(row[1]) if row[1] else None,
                "unit_name": row[2],
                "dimension_id": str(row[3]), "dimension_title": row[4],
                "nr1_factor": row[5],
                # Nulo preservado, nunca convertido em zero: a linha declarada
                # insuficiente NAO tem coorte, media, severidade nem
                # probabilidade, e zero seria lido como medida que deu zero.
                "cohort_size": _ou_nulo(row[6], int),
                "mean_score": _ou_nulo(row[7], float),
                "severity": _ou_nulo(row[8], int),
                "probability": _ou_nulo(row[9], int),
                "risk_level": row[10],
                "rationale": row[11], "generated_at": row[12],
                "suppression_gate": row[13],
                "escalation_note": row[14] or "",
                "site_name": row[15],
            }
            for row in rows
        ]

    # -- Plano de ação (1.5.7.1 "b") ------------------------------------------
    #
    # O segundo documento obrigatório do PGR. A tabela existia desde a migration
    # 010, com RLS, com grants e com permissão própria em tenant_access.py — e
    # nunca recebeu um INSERT: action_plan_seed() devolvia um rascunho na
    # resposta da API e ele evaporava. Estes três métodos são a camada que
    # faltava.
    #
    # Nenhuma consulta aqui faz JOIN com `users` de propósito. Não há
    # `GRANT SELECT ... users TO froid_runtime` em nenhuma migration, e as
    # consultas que resolvem nome de pessoa neste arquivo correm pela conexão
    # administrativa. Um JOIN aqui aplicaria limpo em desenvolvimento e falharia
    # por permissão no primeiro uso em produção, longe do deploy que o causou —
    # que é exatamente como este projeto já se queimou antes. O responsável sai
    # daqui como membership_id; quem precisa do nome o resolve por fora.

    ACTION_PLAN_UPDATABLE = {
        "measure", "measure_type", "plan_action", "responsible_membership_id",
        "due_date", "status", "evidence", "monitoring_method",
        "result_measurement", "implemented_at", "effectiveness",
        "effectiveness_reviewed_at",
    }

    def nr1_generate_action_plan(
        self,
        *,
        organization_id: str,
        membership_id: str,
        campaign_id: str,
        seed_rows: Sequence[dict],
        criteria_id: Optional[str] = None,
    ) -> int:
        """Abre as linhas de plano que faltam para os riscos deste inventário.

        Idempotente por construção: só cria linha para risco que ainda não tem
        nenhuma medida viva. Regerar depois de a empresa ter preenchido o plano
        não sobrescreve nada — e regerar depois de todas as medidas de um risco
        terem sido canceladas cria um rascunho novo, porque risco cuja única
        medida foi cancelada é risco sem medida, e a norma não aceita isso.

        A NR-1 permite mais de uma medida por risco; esta função só garante a
        primeira. As demais entram por nr1_add_action_plan_item().
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        if not seed_rows:
            return 0
        criadas = 0
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                for row in seed_rows:
                    cursor = connection.execute(
                        """
                        INSERT INTO psychosocial_action_plan
                            (id, organization_id, inventory_id, campaign_id,
                             criteria_id, measure, measure_type, plan_action,
                             status, exposed_workers, priority_rank)
                        SELECT %s, %s, inventory.id, %s, %s, '', %s, %s,
                               'planned', %s, %s
                        FROM psychosocial_risk_inventory inventory
                        WHERE inventory.organization_id = %s
                          AND inventory.campaign_id = %s
                          AND inventory.dimension_id = %s
                          AND inventory.unit_id IS NOT DISTINCT FROM %s
                          AND NOT EXISTS (
                              SELECT 1 FROM psychosocial_action_plan viva
                              WHERE viva.inventory_id = inventory.id
                                AND viva.status <> 'cancelled'
                          )
                        """,
                        (
                            str(uuid.uuid4()), organization_id, campaign_id,
                            criteria_id, row["measure_type"], row["plan_action"],
                            max(0, int(row.get("exposed_workers") or 0)),
                            row.get("priority_rank"),
                            organization_id, campaign_id, row["dimension_id"],
                            row.get("unit_id"),
                        ),
                    )
                    criadas += int(getattr(cursor, "rowcount", 0) or 0)
        return criadas

    def nr1_add_action_plan_item(
        self,
        *,
        organization_id: str,
        membership_id: str,
        inventory_id: str,
        measure: str,
        measure_type: str,
        plan_action: str = "introduce",
    ) -> str:
        """Acrescenta uma segunda (ou terceira) medida ao mesmo risco.

        1.5.5.2.1 não limita o plano a uma medida por risco, e a hierarquia de
        1.5.5.1.2 frequentemente exige combinar: uma coletiva mais uma
        administrativa enquanto a primeira não fica de pé.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        item_id = str(uuid.uuid4())
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                cursor = connection.execute(
                    """
                    INSERT INTO psychosocial_action_plan
                        (id, organization_id, inventory_id, campaign_id,
                         criteria_id, measure, measure_type, plan_action,
                         status, exposed_workers, priority_rank)
                    SELECT %s, %s, inventory.id, inventory.campaign_id,
                           inventory.criteria_id, %s, %s, %s, 'planned',
                           inventory.exposed_workers, NULL
                    FROM psychosocial_risk_inventory inventory
                    WHERE inventory.id = %s
                      AND inventory.organization_id = %s
                    """,
                    (
                        item_id, organization_id, measure, measure_type,
                        plan_action, inventory_id, organization_id,
                    ),
                )
                if int(getattr(cursor, "rowcount", 0) or 0) == 0:
                    raise ValueError("inventory_not_found")
        return item_id

    def nr1_list_action_plan(
        self, *, organization_id: str, membership_id: str, campaign_id: str
    ) -> list[dict]:
        """O plano de ação como documento: por risco, na ordem de prioridade."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                rows = connection.execute(
                    """
                    SELECT plano.id, plano.inventory_id, plano.plan_action,
                           plano.measure, plano.measure_type,
                           plano.responsible_membership_id, plano.due_date,
                           plano.status, plano.evidence, plano.monitoring_method,
                           plano.result_measurement, plano.implemented_at,
                           plano.effectiveness_reviewed_at, plano.effectiveness,
                           plano.exposed_workers, plano.priority_rank,
                           plano.created_at, plano.updated_at,
                           inventory.unit_id, unit.name, inventory.dimension_id,
                           dimension.title, inventory.nr1_factor,
                           inventory.risk_level, inventory.severity,
                           inventory.probability, inventory.review_due_at,
                           inventory.review_trigger,
                           -- O estabelecimento do setor. Sem ele a medida
                           -- corretiva nao tem destino numa empresa com varios
                           -- enderecos que repetem o nome do setor.
                           estabelecimento.name
                    FROM psychosocial_action_plan plano
                    JOIN psychosocial_risk_inventory inventory
                      ON inventory.id = plano.inventory_id
                    JOIN assessment_dimensions dimension
                      ON dimension.id = inventory.dimension_id
                    LEFT JOIN organization_units unit ON unit.id = inventory.unit_id
                    LEFT JOIN organization_units estabelecimento
                      ON estabelecimento.id = unit.parent_unit_id
                    WHERE plano.organization_id = %s
                      AND inventory.campaign_id = %s
                    ORDER BY coalesce(plano.priority_rank, 2147483647),
                             inventory.severity * inventory.probability DESC,
                             plano.created_at
                    """,
                    (organization_id, campaign_id),
                ).fetchall()
        return [
            {
                "item_id": str(row[0]),
                "inventory_id": str(row[1]),
                "plan_action": row[2],
                "measure": row[3],
                "measure_type": row[4],
                "responsible_membership_id": str(row[5]) if row[5] else None,
                "due_date": row[6],
                "status": row[7],
                "evidence": row[8],
                "monitoring_method": row[9],
                "result_measurement": row[10],
                "implemented_at": row[11],
                "effectiveness_reviewed_at": row[12],
                "effectiveness": row[13],
                "exposed_workers": int(row[14] or 0),
                "priority_rank": int(row[15]) if row[15] is not None else None,
                "created_at": row[16],
                "updated_at": row[17],
                "unit_id": str(row[18]) if row[18] else None,
                "unit_name": row[19],
                "dimension_id": str(row[20]),
                "dimension_title": row[21],
                "nr1_factor": row[22],
                "risk_level": row[23],
                "severity": int(row[24]),
                "probability": int(row[25]),
                # 1.5.4.4.6: por que e desde quando a reavaliação está devida.
                "review_due_at": row[26],
                "review_trigger": row[27],
                "site_name": row[28],
            }
            for row in rows
        ]

    def nr1_update_action_plan_item(
        self,
        *,
        organization_id: str,
        membership_id: str,
        item_id: str,
        fields: Dict[str, Any],
    ) -> dict:
        """Atualiza uma medida do plano.

        A lista branca não é higiene genérica: sem ela o nome da coluna viria do
        corpo da requisição. E as regras de integridade que importam não estão
        aqui — estão em CHECK e trigger na migration 026, onde nenhum caminho de
        código as contorna. Aqui só se recusa cedo o que dá para recusar cedo,
        com mensagem melhor que a do banco.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        alteracoes = {
            chave: valor
            for chave, valor in (fields or {}).items()
            if chave in self.ACTION_PLAN_UPDATABLE
        }
        if not alteracoes:
            raise ValueError("no_updatable_fields")
        atribuicoes = ", ".join(f"{chave}=%s" for chave in alteracoes)
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                cursor = connection.execute(
                    f"""
                    UPDATE psychosocial_action_plan
                       SET {atribuicoes}
                     WHERE id=%s AND organization_id=%s
                    """,
                    (*alteracoes.values(), item_id, organization_id),
                )
                if int(getattr(cursor, "rowcount", 0) or 0) == 0:
                    raise ValueError("action_plan_item_not_found")
        return {"item_id": item_id, "updated_fields": sorted(alteracoes)}

    def mark_mirrored_report_deleted(
        self, *, organization_id: str, session_id: str
    ) -> None:
        if not self.enabled:
            return
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE session_reports SET deleted_at=now(), updated_at=now()
                WHERE organization_id=%s AND legacy_session_id=%s
                """,
                (organization_id, session_id),
            )
            connection.commit()

    def apply_credit_event(
        self,
        *,
        organization_id: str,
        membership_id: str,
        actor_user_id: str,
        delta: int,
        event_type: str,
        idempotency_key: str,
        session_id: str = "",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Atomically update an organization wallet through the RLS runtime role."""
        if not self.enabled:
            raise RuntimeError("shared credit wallet requires dual persistence")
        if not self.runtime_database_url:
            raise RuntimeError("FROID_RUNTIME_DATABASE_URL is required for wallet events")
        if event_type not in {"purchase", "consumption", "refund", "adjustment"}:
            raise ValueError("invalid_credit_event_type")
        if not str(idempotency_key or "").strip():
            raise ValueError("idempotency_key_required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)",
                    (organization_id,),
                )
                connection.execute(
                    "SELECT set_config('app.membership_id', %s, true)",
                    (membership_id,),
                )
                row = connection.execute(
                    """
                    SELECT ledger_id, resulting_balance, applied
                    FROM froid_apply_credit_event(
                        %s,%s,%s,%s,%s,%s,%s,%s::jsonb
                    )
                    """,
                    (
                        organization_id, membership_id, actor_user_id, int(delta),
                        event_type, idempotency_key, session_id or None,
                        _json(metadata or {}),
                    ),
                ).fetchone()
        return {
            "ledger_id": str(row[0]),
            "balance": int(row[1]),
            "applied": bool(row[2]),
        }

    def _contribute_legacy_balance(
        self,
        cursor,
        organization_id: str,
        user_id: str,
        balance: int,
        metadata: Optional[dict] = None,
    ) -> int:
        """Soma o saldo individual de um profissional ao pool da organizacao.

        Quando varios profissionais partilham a mesma organizacao (clinica com
        CNPJ), cada um contribui com o proprio saldo remanescente e o pool passa
        a valer a SOMA. A versao anterior escrevia ``balance=EXCLUDED.balance``,
        o que sobrescrevia: numa clinica de 4 profissionais o pool terminaria
        valendo o saldo do ultimo da iteracao, destruindo os demais creditos.

        Idempotente por profissional: a contribuicao e registrada no
        ``credit_ledger`` com a chave ``legacy-opening-v1:<user_id>``, entao
        reexecutar o backfill nao soma duas vezes.

        So atua enquanto a carteira esta em ``authority='legacy'``. Depois da
        ativacao o saldo compartilhado e a autoridade e nao pode ser remexido
        por uma migracao.

        Devolve o saldo do pool apos a contribuicao (ou o atual, se inerte).
        """
        idempotency_key = f"legacy-opening-v1:{user_id}"
        cursor.execute(
            "SELECT 1 FROM credit_ledger WHERE organization_id=%s AND idempotency_key=%s",
            (organization_id, idempotency_key),
        )
        already_contributed = cursor.fetchone() is not None

        cursor.execute(
            "INSERT INTO organization_wallets (organization_id, balance) "
            "VALUES (%s,0) ON CONFLICT (organization_id) DO NOTHING",
            (organization_id,),
        )
        cursor.execute(
            "SELECT balance, authority FROM organization_wallets "
            "WHERE organization_id=%s FOR UPDATE",
            (organization_id,),
        )
        row = cursor.fetchone()
        current_balance = safe_int(row[0]) if row else 0
        authority = str(row[1]) if row else "legacy"
        if already_contributed or authority != "legacy":
            return current_balance

        contribution = max(0, safe_int(balance))
        new_balance = current_balance + contribution
        cursor.execute(
            "UPDATE organization_wallets SET balance=%s, updated_at=now() "
            "WHERE organization_id=%s",
            (new_balance, organization_id),
        )
        cursor.execute(
            """
            INSERT INTO credit_ledger
                (id, organization_id, delta, balance_after, event_type,
                 idempotency_key, actor_user_id, metadata)
            VALUES (%s,%s,%s,%s,'migration_opening',%s,%s,%s::jsonb)
            """,
            (
                stable_uuid("credit", organization_id, idempotency_key),
                organization_id,
                contribution,
                new_balance,
                idempotency_key,
                user_id,
                _json(metadata or {}),
            ),
        )
        return new_balance

    def _organization_for_email(self, cursor, email: str, profile: dict) -> dict:
        owner_email = normalize_email(email) or "legacy-unassigned@froid.local"
        account_type_raw = str(profile.get("account_type") or "individual").lower()
        organization_id = organization_id_for_profile(
            owner_email, account_type_raw, profile.get("organization_document")
        )
        user_id = stable_uuid("user", owner_email)
        membership_id = stable_uuid("membership", organization_id, user_id)
        account_type = str(profile.get("account_type") or "individual").lower()
        # 'enterprise' nao e cosmetico: e o unico valor que faz
        # effective_role_permissions retirar as permissoes clinicas
        # identificadas dos papeis do lado do empregador. Trocar este mapeamento
        # devolve ao empregador o acesso ao prontuario.
        organization_type = organization_type_for_account(account_type)
        owner_name = str(profile.get("owner_name") or owner_email).strip()
        organization_name = str(profile.get("organization_name") or owner_name).strip()
        organization_document = str(profile.get("organization_document") or "").strip() or None
        now = datetime.now(timezone.utc)

        cursor.execute(
            """
            INSERT INTO organizations
                (id, organization_type, legal_name, display_name, document,
                 legacy_owner_email, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                organization_type = EXCLUDED.organization_type,
                legal_name = EXCLUDED.legal_name,
                display_name = EXCLUDED.display_name,
                document = EXCLUDED.document,
                updated_at = EXCLUDED.updated_at
            """,
            (
                organization_id,
                organization_type,
                organization_name,
                organization_name,
                organization_document,
                # Organizacao derivada do CNPJ nao tem "dono legado" unico: a
                # clinica e compartilhada por varios profissionais, a empresa
                # NR-1 por varias pessoas do empregador. Alem de semanticamente
                # errado, gravar o e-mail aqui colide com o indice unico
                # organizations_legacy_owner_unique quando a mesma pessoa tem
                # tambem organizacao propria - o autonomo que depois se
                # formaliza como clinica, ou o profissional que cadastra a
                # empresa dele no NR-1 - e o backfill quebra com UniqueViolation.
                None
                if organization_derives_from_cnpj(
                    account_type_raw, profile.get("organization_document")
                )
                else owner_email,
                parse_timestamp(profile.get("created_at")),
                now,
            ),
        )
        cursor.execute(
            """
            INSERT INTO users (id, email, display_name, status, created_at, updated_at)
            VALUES (%s, %s, %s, 'active', %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                display_name = EXCLUDED.display_name,
                updated_at = EXCLUDED.updated_at
            """,
            (user_id, owner_email, owner_name, parse_timestamp(profile.get("created_at")), now),
        )
        cursor.execute(
            """
            INSERT INTO organization_memberships
                (id, organization_id, user_id, status, joined_at, created_at, updated_at)
            VALUES (%s, %s, %s, 'active', %s, %s, %s)
            ON CONFLICT (organization_id, user_id) DO UPDATE SET
                status = 'active', revoked_at = NULL, updated_at = EXCLUDED.updated_at
            """,
            (membership_id, organization_id, user_id, now, now, now),
        )
        # O segundo papel depende do tipo de organizacao, e a diferenca nao e
        # cosmetica.
        #
        # Numa organizacao clinica o dono e o profissional: 'professional' e o
        # papel que lhe da o proprio consultorio.
        #
        # Numa organizacao 'enterprise' o dono e o EMPREGADOR. Dar-lhe
        # 'professional' devolve pela porta dos fundos exatamente o que o modulo
        # inteiro existe para impedir: 'professional' NAO esta em
        # EMPLOYER_SIDE_ROLES, entao ele conserva patients.read_assigned,
        # reports.read_assigned e reports.write mesmo numa org enterprise. O
        # estreitamento que retira as permissoes clinicas so alcanca os papeis do
        # lado do empregador — e o dono, carregando os dois, escapava por cima
        # dele.
        #
        # 'compliance_manager' e o papel desenhado para isso ("runs the NR-1
        # programme for the employer: campaigns, aggregated panel, risk inventory
        # and action plan. Reads no identified clinical record"). E resolve de
        # quebra um segundo problema: o dono de uma empresa NR-1 so tinha
        # nr1.unit.* e nao conseguia abrir campanha, gerar inventario nem
        # preencher o plano de acao do produto que acabara de contratar.
        #
        # Se a empresa tiver de fato um clinico atendendo colaboradores, ele
        # entra por convite com papel 'professional' — que e o desenho, porque a
        # fronteira depende de serem pessoas distintas.
        papeis = (
            ("owner", "compliance_manager")
            if organization_type == "enterprise"
            else ("owner", "professional")
        )
        for role in papeis:
            cursor.execute(
                """
                INSERT INTO membership_roles (membership_id, role)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                (membership_id, role),
            )
        if organization_type == "enterprise":
            # Corretivo, e nao apenas preventivo: quem se cadastrou como empresa
            # antes desta mudanca ja tem 'professional' gravado, e deixa-lo e
            # manter o buraco aberto para o unico tipo de organizacao onde ele
            # importa.
            cursor.execute(
                """
                DELETE FROM membership_roles
                WHERE membership_id=%s AND role='professional'
                """,
                (membership_id,),
            )
        return {
            "organization_id": organization_id,
            "user_id": user_id,
            "membership_id": membership_id,
        }

    def _build_owners(self, state: dict) -> tuple[dict, dict]:
        profiles = state.get("professional_profiles") or {}
        invites = state.get("session_invites") or {}
        owners: Dict[str, dict] = {
            normalize_email(email): profile
            for email, profile in profiles.items()
            if normalize_email(email) and isinstance(profile, dict)
        }
        for invite in invites.values():
            if not isinstance(invite, dict):
                continue
            email = normalize_email(
                invite.get("professional_email") or invite.get("owner_email")
            )
            if email and email not in owners:
                owners[email] = {"owner_email": email, "account_type": "individual"}
        fallback = normalize_email(os.getenv("FROID_LEGACY_REPORT_OWNER", ""))
        if fallback and fallback not in owners:
            owners[fallback] = {"owner_email": fallback, "account_type": "individual"}
        return owners, invites

    def sync_all(self, state: dict, reports: dict) -> Dict[str, int]:
        """Idempotently mirror a complete legacy snapshot.

        Errors are retained in status and re-raised. Callers serving live legacy
        requests may catch them; the standalone migration command must fail.
        """
        if not self.enabled:
            return {}
        with self._lock:
            run_id = uuid.uuid4()
            try:
                with self._connect() as connection:
                    self.ensure_schema(connection)
                    with connection.cursor() as cursor:
                        fingerprint = hashlib.sha256(
                            (_json(state) + _json(reports)).encode("utf-8")
                        ).hexdigest()
                        cursor.execute(
                            """
                            INSERT INTO migration_runs
                                (id, migration_version, mode, status, source_fingerprint)
                            VALUES (%s, '001_multitenant_foundation', 'dual', 'running', %s)
                            """,
                            (run_id, fingerprint),
                        )
                        counters = self._sync(cursor, state or {}, reports or {})
                        cursor.execute(
                            """
                            UPDATE migration_runs SET status='completed', counters=%s::jsonb,
                                completed_at=now() WHERE id=%s
                            """,
                            (_json(counters), run_id),
                        )
                    connection.commit()
                self._last_sync_at = datetime.now(timezone.utc).isoformat()
                self._last_error = None
                self._last_counters = counters
                return counters
            except Exception as exc:
                self._last_error = type(exc).__name__
                raise

    def _sync(self, cursor, state: dict, reports: dict) -> Dict[str, int]:
        owners, invites = self._build_owners(state)
        for report in reports.values():
            if not isinstance(report, dict):
                continue
            professional = report.get("professional")
            professional = professional if isinstance(professional, dict) else {}
            email = normalize_email(
                report.get("professionalEmail")
                or report.get("professional_email")
                or professional.get("email")
            )
            if email and email not in owners:
                owners[email] = {"owner_email": email, "account_type": "individual"}
        owner_refs = {
            email: self._organization_for_email(cursor, email, profile)
            for email, profile in owners.items()
        }
        fallback_email = normalize_email(os.getenv("FROID_LEGACY_REPORT_OWNER", ""))
        if not fallback_email or fallback_email not in owner_refs:
            fallback_email = next(iter(owner_refs), "legacy-unassigned@froid.local")
        if fallback_email not in owner_refs:
            owner_refs[fallback_email] = self._organization_for_email(
                cursor,
                fallback_email,
                {"owner_name": "FROID Legacy", "account_type": "individual"},
            )

        scoped_refs: Dict[tuple[str, str], dict] = {}

        def scoped_ref(owner: str, explicit_organization_id: Any = "") -> dict:
            """Resolve the professional's real membership for tenant-bound data."""
            normalized_owner = normalize_email(owner) or fallback_email
            organization_id = str(explicit_organization_id or "").strip()
            fallback_ref = owner_refs.get(normalized_owner) or owner_refs[fallback_email]
            if not organization_id:
                return fallback_ref
            cache_key = (normalized_owner, organization_id)
            if cache_key in scoped_refs:
                return scoped_refs[cache_key]
            row = cursor.execute(
                """SELECT membership.organization_id, membership.user_id, membership.id
                FROM organization_memberships membership
                JOIN users user_account ON user_account.id=membership.user_id
                WHERE membership.organization_id=%s AND lower(user_account.email)=%s""",
                (organization_id, normalized_owner),
            ).fetchone()
            if not row:
                raise ValueError(
                    "tenant-bound clinical data has no matching organization membership"
                )
            resolved = {
                "organization_id": row[0],
                "user_id": row[1],
                "membership_id": row[2],
            }
            scoped_refs[cache_key] = resolved
            return resolved

        patient_scopes: Dict[str, set[tuple[str, str]]] = {}
        session_invites: Dict[str, dict] = {}
        invite_ids: Dict[str, dict] = {}
        for token, invite in invites.items():
            if not isinstance(invite, dict):
                continue
            owner = normalize_email(invite.get("professional_email")) or fallback_email
            organization_id = str(invite.get("organization_id") or "").strip()
            patient_id = str(invite.get("patient_id") or "").strip()
            if patient_id:
                patient_scopes.setdefault(patient_id, set()).add(
                    (owner, organization_id)
                )
            session_id = str(invite.get("session_id") or "").strip()
            if session_id:
                session_invites[session_id] = invite
            invite_id = str(invite.get("id") or token).strip()
            if invite_id:
                invite_ids[invite_id] = invite
        for report in reports.values():
            if not isinstance(report, dict):
                continue
            professional = report.get("professional")
            professional = professional if isinstance(professional, dict) else {}
            owner = normalize_email(
                report.get("professionalEmail")
                or report.get("professional_email")
                or professional.get("email")
            ) or fallback_email
            organization_id = str(
                report.get("organizationId") or report.get("organization_id") or ""
            ).strip()
            legacy_patient_id = str(
                report.get("patientId") or report.get("patient_id") or ""
            ).strip()
            if legacy_patient_id:
                patient_scopes.setdefault(legacy_patient_id, set()).add(
                    (owner, organization_id)
                )

        migrated_patients: Dict[tuple[str, str], uuid.UUID] = {}
        patients = state.get("patients") or {}
        for legacy_patient_id, patient in patients.items():
            if not isinstance(patient, dict):
                continue
            legacy_patient_id = str(legacy_patient_id)
            for owner, scoped_organization_id in patient_scopes.get(
                legacy_patient_id, {(fallback_email, "")}
            ):
                ref = scoped_ref(owner, scoped_organization_id)
                organization_id = ref["organization_id"]
                patient_id = stable_uuid("patient", organization_id, legacy_patient_id)
                migrated_patients[(str(organization_id), legacy_patient_id)] = patient_id
                cursor.execute(
                    """
                    INSERT INTO patients
                        (id, organization_id, legacy_patient_id, full_name, email,
                         phone, document, birth_date, legacy_payload, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                    ON CONFLICT (organization_id, legacy_patient_id) DO UPDATE SET
                        full_name=EXCLUDED.full_name, email=EXCLUDED.email,
                        phone=EXCLUDED.phone, document=EXCLUDED.document,
                        birth_date=EXCLUDED.birth_date,
                        legacy_payload=EXCLUDED.legacy_payload,
                        updated_at=EXCLUDED.updated_at
                    """,
                    (
                        patient_id,
                        organization_id,
                        legacy_patient_id,
                        str(patient.get("name") or patient.get("full_name") or "Paciente"),
                        normalize_email(patient.get("email")) or None,
                        str(patient.get("phone") or "") or None,
                        str(patient.get("document") or "") or None,
                        str(patient.get("birth_date") or "") or None,
                        _json(patient),
                        parse_timestamp(patient.get("created_at")),
                        parse_timestamp(patient.get("updated_at")),
                    ),
                )
                assignment_id = stable_uuid("assignment", patient_id, ref["membership_id"], "primary")
                cursor.execute(
                    """
                    INSERT INTO patient_assignments
                        (id, organization_id, patient_id, membership_id, assignment_type)
                    VALUES (%s,%s,%s,%s,'primary') ON CONFLICT DO NOTHING
                    """,
                    (assignment_id, organization_id, patient_id, ref["membership_id"]),
                )

        for email, profile in owners.items():
            ref = owner_refs[email]
            self._contribute_legacy_balance(
                cursor,
                organization_id=ref["organization_id"],
                user_id=ref["user_id"],
                balance=max(0, safe_int(profile.get("remaining_sessions"))),
                metadata={
                    "owner_email": email,
                    "total_sessions": safe_int(profile.get("total_sessions")),
                    "used_sessions": safe_int(profile.get("used_sessions")),
                },
            )

        for consent in state.get("consent_ledger") or []:
            if not isinstance(consent, dict):
                continue
            invite = invite_ids.get(str(consent.get("invite_id") or "")) or session_invites.get(
                str(consent.get("session_id") or "")
            ) or {}
            owner = normalize_email(invite.get("professional_email")) or fallback_email
            ref = scoped_ref(owner, invite.get("organization_id"))
            legacy_patient_id = str(consent.get("patient_id") or invite.get("patient_id") or "")
            patient_id = migrated_patients.get(
                (str(ref["organization_id"]), legacy_patient_id)
            )
            consent_hash = str(consent.get("hash") or stable_uuid("consent-hash", _json(consent)))
            cursor.execute(
                """
                INSERT INTO consents
                    (id, organization_id, patient_id, legacy_invite_id,
                     legacy_session_id, consent_version, consent_hash,
                     accepted_at, evidence)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (organization_id, consent_hash) DO NOTHING
                """,
                (
                    stable_uuid("consent", ref["organization_id"], consent_hash),
                    ref["organization_id"], patient_id,
                    str(consent.get("invite_id") or "") or None,
                    str(consent.get("session_id") or "") or None,
                    str(consent.get("version") or "legacy"), consent_hash,
                    parse_timestamp(consent.get("accepted_at")), _json(consent),
                ),
            )

        for session_id, report in reports.items():
            if not isinstance(report, dict):
                continue
            session_id = str(session_id)
            invite = session_invites.get(session_id) or {}
            report_professional = (
                report.get("professional")
                if isinstance(report.get("professional"), dict)
                else {}
            )
            owner = normalize_email(
                report.get("professionalEmail")
                or report.get("professional_email")
                or report_professional.get("email")
                or invite.get("professional_email")
            ) or fallback_email
            explicit_organization_id = (
                report.get("organizationId")
                or report.get("organization_id")
                or invite.get("organization_id")
                or ""
            )
            ref = scoped_ref(owner, explicit_organization_id)
            legacy_patient_id = str(
                report.get("patientId") or report.get("patient_id") or invite.get("patient_id") or ""
            )
            patient_id = migrated_patients.get(
                (str(ref["organization_id"]), legacy_patient_id)
            )
            cursor.execute(
                """
                INSERT INTO session_reports
                    (id, organization_id, legacy_session_id, patient_id,
                     professional_membership_id, report_payload, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT (organization_id, legacy_session_id) DO UPDATE SET
                    patient_id=EXCLUDED.patient_id,
                    professional_membership_id=EXCLUDED.professional_membership_id,
                    report_payload=EXCLUDED.report_payload,
                    updated_at=EXCLUDED.updated_at, deleted_at=NULL
                """,
                (
                    stable_uuid("report", ref["organization_id"], session_id),
                    ref["organization_id"], session_id, patient_id,
                    ref["membership_id"], _json(report),
                    parse_timestamp(report.get("createdAt") or report.get("created_at")),
                    datetime.now(timezone.utc),
                ),
            )

        for event in state.get("admin_audit_events") or []:
            if not isinstance(event, dict):
                continue
            actor_email = normalize_email(
                event.get("actor_email") or event.get("admin_email") or event.get("email")
            )
            ref = owner_refs.get(actor_email) or owner_refs[fallback_email]
            event_key = str(event.get("id") or event.get("created_at") or _json(event))
            cursor.execute(
                """
                INSERT INTO audit_events
                    (id, organization_id, actor_user_id, action, resource_type,
                     resource_id, metadata, occurred_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    stable_uuid("audit", ref["organization_id"], event_key),
                    ref["organization_id"], ref["user_id"],
                    str(event.get("action") or event.get("event_type") or "legacy_event"),
                    str(event.get("resource_type") or "legacy"),
                    str(event.get("resource_id") or "") or None,
                    _json(event), parse_timestamp(event.get("created_at") or event.get("occurred_at")),
                ),
            )

        return {
            "organizations": len(owner_refs),
            "patients": len(migrated_patients),
            "consents": len([x for x in state.get("consent_ledger") or [] if isinstance(x, dict)]),
            "reports": len([x for x in reports.values() if isinstance(x, dict)]),
            "audit_events": len([x for x in state.get("admin_audit_events") or [] if isinstance(x, dict)]),
        }

    def register_marketing_lead(
        self, *, nome: str, email: str, empresa: str,
        cargo: str = "", contexto: str = "", origem: str = "diagnostico-nr1",
    ) -> None:
        """Grava o contato do diagnóstico de prontidão.

        Sem sessão de tenant: o formulário é público e o lead ainda não
        pertence a organização nenhuma. A tabela vive fora do RLS por isso, e
        por isso mesmo não pode receber dado sensível — o comentário na
        migration 021 é a única barreira contra alguém decidir guardar
        resposta de questionário aqui um dia.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        # As demais operacoes chegam aqui depois de autenticacao, que ja
        # garantiu o esquema. Esta nao: o formulario e publico, e num deploy
        # novo a tabela so existiria quando alguem da equipe logasse. Ate la o
        # endpoint devolveria 503 e os leads se perderiam — em silencio, porque
        # ninguem investiga um formulario que ninguem reclamou.
        self.ensure_schema()
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                connection.execute(
                    "INSERT INTO marketing_leads "
                    "(nome, email, empresa, cargo, contexto, origem) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (lower(btrim(email))) DO UPDATE SET "
                    " nome=EXCLUDED.nome, empresa=EXCLUDED.empresa, "
                    " cargo=EXCLUDED.cargo, contexto=EXCLUDED.contexto, "
                    " origem=EXCLUDED.origem, created_at=now(), opt_out_at=NULL",
                    (nome, email, empresa, cargo, contexto, origem),
                )

    # ------------------------------------------------------------------
    # Validade convergente.
    #
    # O profissional aplica o instrumento e registra o escore; o FROID guarda
    # o par. Nenhum método aqui aplica ou pontua questionário — a fronteira
    # que mantém o produto como instrumentação mora nessa ausência.
    # ------------------------------------------------------------------

    def validation_consent_state(
        self, *, organization_id: str, membership_id: str, patient_id: str
    ) -> dict:
        """Concedido, revogado, ou nunca perguntado."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                row = connection.execute(
                    "SELECT consent_version, granted_at, revoked_at "
                    "FROM patient_research_consent WHERE patient_id=%s",
                    (patient_id,),
                ).fetchone()
        if not row:
            return {"state": "never_asked", "version": None, "at": None}
        version, granted_at, revoked_at = row
        if revoked_at is not None:
            return {"state": "revoked", "version": version, "at": revoked_at.isoformat()}
        return {"state": "granted", "version": version, "at": granted_at.isoformat()}

    def validation_set_consent(
        self, *, organization_id: str, membership_id: str, patient_id: str,
        registered_by: str, granted: bool, consent_version: str,
    ) -> dict:
        """Registra a decisão. Revogar apaga os pares, não apenas os sinaliza."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        removidos = 0
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                if granted:
                    connection.execute(
                        "INSERT INTO patient_research_consent "
                        "(patient_id, organization_id, consent_version, granted_at, "
                        " revoked_at, registered_by) "
                        "VALUES (%s, %s, %s, now(), NULL, %s) "
                        "ON CONFLICT (patient_id) DO UPDATE SET "
                        " consent_version=EXCLUDED.consent_version, granted_at=now(), "
                        " revoked_at=NULL, registered_by=EXCLUDED.registered_by, "
                        " updated_at=now()",
                        (patient_id, organization_id, consent_version, registered_by),
                    )
                else:
                    connection.execute(
                        "INSERT INTO patient_research_consent "
                        "(patient_id, organization_id, consent_version, granted_at, "
                        " revoked_at, registered_by) "
                        "VALUES (%s, %s, %s, NULL, now(), %s) "
                        "ON CONFLICT (patient_id) DO NOTHING",
                        (patient_id, organization_id, consent_version, registered_by),
                    )
                    row = connection.execute(
                        "SELECT froid_revoke_research_consent(%s, %s)",
                        (patient_id, registered_by),
                    ).fetchone()
                    removidos = int(row[0] or 0) if row else 0
        return {"granted": granted, "removed_administrations": removidos}

    def validation_record_administration(
        self, *, organization_id: str, membership_id: str, patient_id: str,
        instrument_code: str, total_score: float, administered_by: str,
        administered_at: str, session_id: Optional[str], observations: list,
    ) -> dict:
        """Grava o escore e os padrões medidos na mesma janela.

        Recusa se o consentimento não estiver ativo. A checagem está aqui, e
        não apenas na tela, porque tela é a camada que se esquece.
        """
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                ativo = connection.execute(
                    "SELECT froid_research_consent_active(%s)", (patient_id,)
                ).fetchone()
                if not ativo or not ativo[0]:
                    raise PermissionError("consentimento de pesquisa não está ativo")
                versao = connection.execute(
                    "SELECT consent_version FROM patient_research_consent "
                    "WHERE patient_id=%s",
                    (patient_id,),
                ).fetchone()
                row = connection.execute(
                    "INSERT INTO validation_administrations "
                    "(organization_id, patient_id, instrument_id, session_id, "
                    " administered_at, total_score, administered_by, "
                    " research_consent, consent_version) "
                    "SELECT %s, %s, i.id, %s, %s, %s, %s, TRUE, %s "
                    "FROM validation_instruments i WHERE i.code=%s RETURNING id",
                    (organization_id, patient_id, session_id, administered_at,
                     total_score, administered_by, versao[0] if versao else "",
                     instrument_code),
                ).fetchone()
                if not row:
                    raise ValueError(f"instrumento desconhecido: {instrument_code}")
                administration_id = row[0]
                for obs in observations or []:
                    connection.execute(
                        "INSERT INTO validation_observations "
                        "(administration_id, pattern_key, pattern_value, coverage, "
                        " confidence, window_seconds) VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (administration_id, pattern_key) DO NOTHING",
                        (administration_id, obs.get("pattern_key"),
                         obs.get("pattern_value"), obs.get("coverage"),
                         obs.get("confidence"), obs.get("window_seconds")),
                    )
        return {"administration_id": str(administration_id)}

    def validation_patient_history(
        self, *, organization_id: str, membership_id: str, patient_id: str
    ) -> list:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                linhas = connection.execute(
                    "SELECT a.administered_at, i.code, a.total_score, i.score_max, "
                    "       a.session_id, "
                    "       (SELECT count(*) FROM validation_observations o "
                    "         WHERE o.administration_id = a.id) "
                    "FROM validation_administrations a "
                    "JOIN validation_instruments i ON i.id = a.instrument_id "
                    "WHERE a.patient_id=%s ORDER BY a.administered_at DESC",
                    (patient_id,),
                ).fetchall()
        return [
            {
                "administered_at": r[0].isoformat(), "instrument": r[1],
                "total_score": float(r[2]), "score_max": float(r[3]),
                "session_id": r[4], "patterns": int(r[5]),
            }
            for r in linhas
        ]

    def validation_progress(
        self, *, organization_id: str, membership_id: str
    ) -> list:
        """Quantos pares por hipótese. Sem coeficiente, de propósito."""
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                linhas = connection.execute(
                    "SELECT pattern_key, instrument_code, pairs "
                    "FROM froid_validation_progress()"
                ).fetchall()
        return [
            {"pattern_key": r[0], "instrument": r[1], "pairs": int(r[2])}
            for r in linhas
        ]

    def validation_pairs(
        self, *, organization_id: str, membership_id: str,
        pattern_key: str, instrument_code: str,
    ) -> tuple:
        if not self.enabled or not self.runtime_database_url:
            raise RuntimeError("dual persistence and runtime role are required")
        with self._connect(runtime=True) as connection:
            with connection.transaction():
                self._nr1_session(connection, organization_id, membership_id)
                linhas = connection.execute(
                    "SELECT pattern_value, instrument_score "
                    "FROM froid_validation_pairs(%s, %s)",
                    (pattern_key, instrument_code),
                ).fetchall()
        return [float(r[0]) for r in linhas], [float(r[1]) for r in linhas]


def read_json_object(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value
