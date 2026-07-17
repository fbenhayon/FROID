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
        migration_paths = sorted(self.migration_path.parent.glob("*.sql"))
        if self.migration_path not in migration_paths:
            migration_paths.insert(0, self.migration_path)
        if connection is None:
            with self._connect() as conn:
                for migration_path in migration_paths:
                    conn.execute(migration_path.read_text(encoding="utf-8"))
        else:
            for migration_path in migration_paths:
                connection.execute(migration_path.read_text(encoding="utf-8"))
        self._schema_ready = True

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
                           ), ARRAY[]::text[])
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
                             membership.id, user_account.id, membership.status
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
            connection.execute(
                """
                INSERT INTO membership_invitations
                    (id, organization_id, invited_email,
                     invited_by_membership_id, token_hash, requested_roles,
                     expires_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
                """,
                (
                    invitation_id, organization_id, normalize_email(invited_email),
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
                user_id = stable_uuid("user", normalized_email)
                membership_id = stable_uuid("membership", organization_id, user_id)
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
            "roles": sorted(roles or []),
            "status": "active",
        }

    def revoke_membership(
        self, *, organization_id: str, membership_id: str
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
                    SELECT
                      EXISTS(SELECT 1 FROM patients
                             WHERE id=%s AND organization_id=%s
                               AND status NOT IN ('deleted', 'restricted')),
                      EXISTS(SELECT 1 FROM organization_memberships
                             WHERE id=%s AND organization_id=%s
                               AND status='active')
                    """,
                    (patient_id, organization_id, membership_id, organization_id),
                )
                patient_exists, membership_exists = cursor.fetchone()
                if not patient_exists:
                    raise ValueError("patient_not_found")
                if not membership_exists:
                    raise ValueError("membership_not_found")
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
