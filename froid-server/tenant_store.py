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
import threading
from typing import Any, Dict, Iterable, Optional
import uuid


NAMESPACE = uuid.UUID("c173f252-e04f-4ca4-a337-39767764c79c")
VALID_MODES = {"legacy", "dual"}


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def stable_uuid(kind: str, *parts: Any) -> uuid.UUID:
    normalized = "|".join(str(part or "").strip().lower() for part in parts)
    return uuid.uuid5(NAMESPACE, f"{kind}|{normalized}")


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


class TenantStore:
    """Optional, rollback-safe mirror of legacy FROID state in PostgreSQL."""

    def __init__(self, mode: str, database_url: str, migration_path: Path):
        requested_mode = (mode or "legacy").strip().lower()
        if requested_mode not in VALID_MODES:
            raise ValueError(
                "FROID_PERSISTENCE_MODE must be 'legacy' or 'dual' during Phase 1"
            )
        if requested_mode == "dual" and not database_url:
            raise ValueError("FROID_DATABASE_URL is required in dual mode")
        self.mode = requested_mode
        self.database_url = database_url
        self.migration_path = migration_path
        self._lock = threading.Lock()
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
        )

    @property
    def enabled(self) -> bool:
        return self.mode == "dual"

    def status(self) -> dict:
        return {
            "mode": self.mode,
            "postgres_mirror_enabled": self.enabled,
            "schema_ready": self._schema_ready,
            "last_sync_at": self._last_sync_at,
            "last_error": self._last_error,
            "last_counters": self._last_counters,
        }

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required when FROID_PERSISTENCE_MODE=dual"
            ) from exc
        return psycopg.connect(self.database_url, connect_timeout=10)

    def ensure_schema(self, connection=None) -> None:
        if self._schema_ready:
            return
        sql = self.migration_path.read_text(encoding="utf-8")
        if connection is None:
            with self._connect() as conn:
                conn.execute(sql)
        else:
            connection.execute(sql)
        self._schema_ready = True

    def _organization_for_email(self, cursor, email: str, profile: dict) -> dict:
        owner_email = normalize_email(email) or "legacy-unassigned@froid.local"
        organization_id = stable_uuid("organization", owner_email)
        user_id = stable_uuid("user", owner_email)
        membership_id = stable_uuid("membership", organization_id, user_id)
        account_type = str(profile.get("account_type") or "individual").lower()
        organization_type = "clinic" if account_type == "organization" else "solo"
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
                owner_email,
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
        for role in ("owner", "professional"):
            cursor.execute(
                """
                INSERT INTO membership_roles (membership_id, role)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                (membership_id, role),
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

        patient_owners: Dict[str, set[str]] = {}
        session_invites: Dict[str, dict] = {}
        invite_ids: Dict[str, dict] = {}
        for token, invite in invites.items():
            if not isinstance(invite, dict):
                continue
            owner = normalize_email(invite.get("professional_email")) or fallback_email
            patient_id = str(invite.get("patient_id") or "").strip()
            if patient_id:
                patient_owners.setdefault(patient_id, set()).add(owner)
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
            legacy_patient_id = str(
                report.get("patientId") or report.get("patient_id") or ""
            ).strip()
            if legacy_patient_id:
                patient_owners.setdefault(legacy_patient_id, set()).add(owner)

        migrated_patients: Dict[tuple[str, str], uuid.UUID] = {}
        patients = state.get("patients") or {}
        for legacy_patient_id, patient in patients.items():
            if not isinstance(patient, dict):
                continue
            legacy_patient_id = str(legacy_patient_id)
            for owner in patient_owners.get(legacy_patient_id, {fallback_email}):
                ref = owner_refs.get(owner) or owner_refs[fallback_email]
                organization_id = ref["organization_id"]
                patient_id = stable_uuid("patient", organization_id, legacy_patient_id)
                migrated_patients[(owner, legacy_patient_id)] = patient_id
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
            balance = max(0, safe_int(profile.get("remaining_sessions")))
            cursor.execute(
                """
                INSERT INTO organization_wallets (organization_id, balance)
                VALUES (%s,%s) ON CONFLICT (organization_id) DO UPDATE SET
                    balance=EXCLUDED.balance, updated_at=now()
                """,
                (ref["organization_id"], balance),
            )
            cursor.execute(
                """
                INSERT INTO credit_ledger
                    (id, organization_id, delta, balance_after, event_type,
                     idempotency_key, actor_user_id, metadata)
                VALUES (%s,%s,%s,%s,'migration_opening','legacy-opening-v1',%s,%s::jsonb)
                ON CONFLICT (organization_id, idempotency_key) DO UPDATE SET
                    delta=EXCLUDED.delta, balance_after=EXCLUDED.balance_after,
                    actor_user_id=EXCLUDED.actor_user_id, metadata=EXCLUDED.metadata
                """,
                (
                    stable_uuid("credit", ref["organization_id"], "legacy-opening-v1"),
                    ref["organization_id"],
                    balance,
                    balance,
                    ref["user_id"],
                    _json({"total_sessions": safe_int(profile.get("total_sessions")),
                           "used_sessions": safe_int(profile.get("used_sessions"))}),
                ),
            )

        for consent in state.get("consent_ledger") or []:
            if not isinstance(consent, dict):
                continue
            invite = invite_ids.get(str(consent.get("invite_id") or "")) or session_invites.get(
                str(consent.get("session_id") or "")
            ) or {}
            owner = normalize_email(invite.get("professional_email")) or fallback_email
            ref = owner_refs.get(owner) or owner_refs[fallback_email]
            legacy_patient_id = str(consent.get("patient_id") or invite.get("patient_id") or "")
            patient_id = migrated_patients.get((owner, legacy_patient_id))
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
            ref = owner_refs.get(owner) or owner_refs[fallback_email]
            legacy_patient_id = str(
                report.get("patientId") or report.get("patient_id") or invite.get("patient_id") or ""
            )
            patient_id = migrated_patients.get((owner, legacy_patient_id))
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


def read_json_object(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value
