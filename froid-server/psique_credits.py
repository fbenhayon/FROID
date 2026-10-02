"""Scoped backend service for Phase 2A; no public routes or Stripe operations.

Each call commits one PostgreSQL transaction. All financial state transitions
are serialized by the existing organization's wallet row, including expiry.
The connection factory must use a restricted runtime role; it never migrates.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from froid_schema import verify_schema
from psique_identity import (
    AuthorizedMaterial,
    EvidenceError,
    TrialIdentity,
    TrialKeyring,
    normalize_trial_email,
    source_sha256,
)
from tenant_access import AccessContext

PHASE2_SCHEMA = {"037_psique_trial_credit_state", "038_psique_credit_commands"}
# A cobranca de sessao (Fase 7.2) vive numa funcao propria de 047, separada do
# comando grande; so precisa da base de estado (037) mais a sua migration.
SESSION_SCHEMA = {"037_psique_trial_credit_state", "047_psique_session_consumption"}


class CreditError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _credit_error(exc: Any) -> CreditError:
    """Promote a PostgreSQL error to a stable, non-leaking CreditError code."""
    reason = exc.diag.message_primary or ""
    if reason and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in reason):
        return CreditError(reason)
    return CreditError("PSIQUE_STORAGE_ERROR")


class PsiqueCredits:
    def __init__(self, connection_factory: Callable[[], Any], *,
                 identity_loader: Callable[[str], TrialIdentity],
                 material_loader: Callable[[str, str], AuthorizedMaterial],
                 keyring: TrialKeyring):
        self._connect = connection_factory
        self._identity_loader = identity_loader
        self._material_loader = material_loader
        self._keyring = keyring

    def _command(self, context: AccessContext, command: str, **args: Any) -> dict[str, Any]:
        import psycopg

        try:
            with self._connect() as conn, conn.transaction():
                # schema_migrations has no clinical content. Verification never writes.
                verify_schema(conn, PHASE2_SCHEMA)
                conn.execute("SELECT set_config('app.organization_id',%s,true)", (context.organization_id,))
                conn.execute("SELECT set_config('app.membership_id',%s,true)", (context.membership_id,))
                row = conn.execute("SELECT psique_v2_credit_command(%s,%s,%s,%s,%s::jsonb)",
                                   (context.organization_id, context.membership_id, context.user_id,
                                    command, json.dumps(args, allow_nan=False))).fetchone()
                if row is None:
                    raise CreditError("PSIQUE_COMMAND_RESULT_MISSING")
                result: dict[str, Any] = row[0]
                return result
        except psycopg.Error as exc:
            raise _credit_error(exc) from exc

    def charge_session(self, context: AccessContext, session_id: str, *, note: str = "") -> dict[str, Any]:
        """Debita 1 credito da carteira V2 por sessao atendida (Fase 7.2).

        Politica A (entregar e acertar depois): sem saldo nao levanta erro —
        marca a sessao como pendencia e devolve pending=true. A idempotencia e
        por session_id: atender a mesma sessao de novo nunca cobra duas vezes.
        Liquida pendencias antigas em ordem (FIFO) quando houver saldo.
        """
        import psycopg

        if not session_id.strip():
            raise CreditError("SESSION_ID_REQUIRED")
        try:
            with self._connect() as conn, conn.transaction():
                verify_schema(conn, SESSION_SCHEMA)
                conn.execute("SELECT set_config('app.organization_id',%s,true)", (context.organization_id,))
                conn.execute("SELECT set_config('app.membership_id',%s,true)", (context.membership_id,))
                row = conn.execute("SELECT psique_v2_session_charge(%s,%s,%s,%s,%s)",
                                   (context.organization_id, context.membership_id, context.user_id,
                                    session_id, note)).fetchone()
                if row is None:
                    raise CreditError("PSIQUE_COMMAND_RESULT_MISSING")
                result: dict[str, Any] = row[0]
                return result
        except psycopg.Error as exc:
            raise _credit_error(exc) from exc

    def enroll_empty_wallet(self, context: AccessContext) -> dict[str, Any]:
        return self._command(context, "ENROLL")

    def grant_trial(self, context: AccessContext) -> dict[str, Any]:
        identity = self._identity_loader(context.user_id)
        if identity.legacy_history_checked is not True:
            raise EvidenceError("LEGACY_HISTORY_CHECK_REQUIRED")
        if (identity.verified_at is None or identity.verified_at.tzinfo is None
            or identity.verified_at > datetime.now(timezone.utc)
            or not identity.verification_ref.strip()):
            raise EvidenceError("VERIFIED_IDENTITY_REQUIRED")
        registered = self._command(context, "IDENTITY")
        if normalize_trial_email(identity.email) != normalize_trial_email(registered["email"]):
            raise EvidenceError("VERIFIED_IDENTITY_MISMATCH")
        history = self._command(context, "KEY_VERSIONS")["versions"]
        tokens = self._keyring.tokens(identity.email, history)
        if identity.legacy_benefit_ref is not None and not identity.legacy_benefit_ref.strip():
            raise EvidenceError("LEGACY_BENEFIT_EVIDENCE_REQUIRED")
        return self._command(context, "GRANT_TRIAL", tokens=tokens,
                             verified_at=identity.verified_at.isoformat(),
                             evidence_ref=identity.legacy_benefit_ref or identity.verification_ref,
                             legacy_benefit=identity.legacy_benefit_ref is not None)

    def register_source(self, context: AccessContext, material_reference: str) -> dict[str, Any]:
        material = self._material_loader(context.user_id, material_reference)
        if (material.organization_id != context.organization_id
            or material.owner_user_id != context.user_id or not material.session_id.strip()):
            raise EvidenceError("MATERIAL_ACCESS_DENIED")
        UUID(material.material_key)
        if material.source_kind == "file":
            if material.original_chunks is None:
                raise EvidenceError("ORIGINAL_BYTES_REQUIRED")
            digest = source_sha256(material.original_chunks)
        elif material.source_kind == "stream":
            digest = None
        else:
            raise EvidenceError("SOURCE_KIND_INVALID")
        return self._command(context, "REGISTER_SOURCE", material_key=material.material_key,
                             session_id=material.session_id, source_kind=material.source_kind,
                             source_sha256=digest)

    def balance(self, context: AccessContext) -> dict[str, Any]:
        return self._command(context, "BALANCE")

    def expire_trial(self, context: AccessContext) -> dict[str, Any]:
        return self._command(context, "EXPIRE")

    def begin(self, context: AccessContext, source_id: str, execution_key: str,
              lease_until: datetime) -> dict[str, Any]:
        UUID(source_id)
        if lease_until.tzinfo is None:
            raise CreditError("TIMEZONE_REQUIRED")
        if not execution_key.strip():
            raise CreditError("EXECUTION_KEY_REQUIRED")
        return self._command(context, "BEGIN", source_id=source_id, execution_key=execution_key,
                             lease_until=lease_until.isoformat())

    def heartbeat(self, context: AccessContext, attempt_id: str,
                  lease_until: datetime) -> dict[str, Any]:
        if lease_until.tzinfo is None:
            raise CreditError("TIMEZONE_REQUIRED")
        return self._command(context, "HEARTBEAT", attempt_id=attempt_id, lease_until=lease_until.isoformat())

    def deliver(self, context: AccessContext, attempt_id: str, *, protected_report: dict[str, Any],
                technical_complete: bool, minimum_result_verified: bool) -> dict[str, Any]:
        if technical_complete is not True or minimum_result_verified is not True:
            raise CreditError("DELIVERY_CONTRACT_NOT_MET")
        return self._command(context, "DELIVER", attempt_id=attempt_id, protected_report=protected_report,
                             technical_complete=True, minimum_result_verified=True)

    def read_delivery(self, context: AccessContext, attempt_id: str) -> dict[str, Any]:
        return self._command(context, "READ_DELIVERY", attempt_id=attempt_id)

    def consume(self, context: AccessContext, attempt_id: str) -> dict[str, Any]:
        return self._command(context, "CONSUME", attempt_id=attempt_id)

    def release(self, context: AccessContext, attempt_id: str, reason: str) -> dict[str, Any]:
        return self._command(context, "RELEASE", attempt_id=attempt_id, reason=reason)

    def restore(self, context: AccessContext, consumption_id: str, *, reason: str,
                evidence_ref: str) -> dict[str, Any]:
        return self._command(context, "RESTORE", consumption_id=consumption_id,
                             reason=reason, evidence_ref=evidence_ref)

    def manual_adjustment(self, context: AccessContext, delta: int, *, reason: str,
                          idempotency_key: str) -> dict[str, Any]:
        if type(delta) is not int:
            raise CreditError("INTEGER_CREDITS_REQUIRED")
        return self._command(context, "ADJUST", delta=delta, reason=reason, idempotency_key=idempotency_key)

    def reconcile(self, context: AccessContext, attempt_id: str) -> dict[str, Any]:
        return self._command(context, "RECONCILE", attempt_id=attempt_id)

    def reconcile_pending(self, context: AccessContext) -> list[dict[str, Any]]:
        pending = self._command(context, "PENDING_ATTEMPTS")["attempt_ids"]
        return [{"attempt_id": attempt_id, **self.reconcile(context, attempt_id)}
                for attempt_id in pending]
