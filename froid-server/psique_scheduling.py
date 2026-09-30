"""Phase 4: organizational scheduling for Psique V2.

The internal Appointment is the authority; the Google mirror is fed by an
outbox after commit, so a mirror failure never loses a booking, and no
external token is ever persisted by this domain. Scheduling requires RBAC V2:
SECRETARY/ORG_ADMIN book, reschedule and cancel without any clinical content;
a CLINICIAN acts on their own agenda only, and only the appointment's own
clinician can link an analysis source to it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from psique_billing import BillingError, PsiqueBilling
from psique_rbac import PHASE3_SCHEMA
from tenant_access import AccessContext

PHASE4_SCHEMA = PHASE3_SCHEMA | {"044_psique_org_scheduling",
                                 "045_psique_scheduling_serialization"}

# Mirrors of the migration 044 CHECK domains; drift is guarded by tests.
APPOINTMENT_STATUSES = ("SCHEDULED", "CONFIRMED", "IN_PROGRESS",
                        "COMPLETED", "CANCELLED", "NO_SHOW")
APPOINTMENT_EVENT_KINDS = ("CREATED", "RESCHEDULED", "STATUS_CHANGED",
                           "CANCELLED", "SESSION_LINKED")
OUTBOX_STATUSES = ("PENDING", "DELIVERED", "FAILED")
OUTBOX_OPERATIONS = ("UPSERT", "CANCEL")


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise BillingError("TIMEZONE_REQUIRED")
    return value.isoformat()


class PsiqueScheduling:
    def __init__(self, connection_factory: Callable[[], Any]):
        self._commands = PsiqueBilling(
            connection_factory, stripe_client=None, webhook_secret="unused",
            account_id="acct_unused", pricing_version="unused",
            success_url="https://unused.invalid", cancel_url="https://unused.invalid")

    def _call(self, sql: str, params: tuple, context: AccessContext) -> dict[str, Any]:
        return self._commands._call(sql, params, context, schema=PHASE4_SCHEMA)

    def upsert_unit(self, context: AccessContext, name: str) -> dict[str, Any]:
        return self._call("SELECT psique_v2_unit_upsert(%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id,
                           context.user_id, name), context)

    def set_availability(self, context: AccessContext, *, clinician_membership_id: str,
                         weekday: int, start_minute: int, end_minute: int,
                         timezone_name: str, active: bool = True) -> dict[str, Any]:
        payload = {"clinician_membership_id": clinician_membership_id, "weekday": weekday,
                   "start_minute": start_minute, "end_minute": end_minute,
                   "timezone": timezone_name, "active": active}
        return self._call("SELECT psique_v2_availability_set(%s,%s,%s,%s::jsonb)",
                          (context.organization_id, context.membership_id, context.user_id,
                           json.dumps(payload, allow_nan=False)), context)

    def create_appointment(self, context: AccessContext, *, patient_id: str,
                           clinician_membership_id: str, start_at: datetime,
                           end_at: datetime, timezone_name: str, idempotency_key: str,
                           unit_id: str | None = None) -> dict[str, Any]:
        payload = {"patient_id": patient_id,
                   "clinician_membership_id": clinician_membership_id,
                   "unit_id": unit_id, "start_at": _iso(start_at), "end_at": _iso(end_at),
                   "timezone": timezone_name, "idempotency_key": idempotency_key}
        return self._call("SELECT psique_v2_appointment_create(%s,%s,%s,%s::jsonb)",
                          (context.organization_id, context.membership_id, context.user_id,
                           json.dumps(payload, allow_nan=False)), context)

    def change_appointment(self, context: AccessContext, *, appointment_id: str,
                           expected_version: int, start_at: datetime | None = None,
                           end_at: datetime | None = None,
                           appointment_status: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"appointment_id": appointment_id,
                                   "expected_version": expected_version}
        if start_at is not None:
            payload["start_at"] = _iso(start_at)
        if end_at is not None:
            payload["end_at"] = _iso(end_at)
        if appointment_status is not None:
            payload["appointment_status"] = appointment_status
        return self._call("SELECT psique_v2_appointment_change(%s,%s,%s,%s::jsonb)",
                          (context.organization_id, context.membership_id, context.user_id,
                           json.dumps(payload, allow_nan=False)), context)

    def cancel_appointment(self, context: AccessContext, *, appointment_id: str,
                           expected_version: int, reason: str) -> dict[str, Any]:
        return self._call("SELECT psique_v2_appointment_cancel(%s,%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           appointment_id, expected_version, reason), context)

    def list_appointments(self, context: AccessContext, *, from_at: datetime,
                          to_at: datetime) -> dict[str, Any]:
        return self._call("SELECT psique_v2_appointments_list(%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           _iso(from_at), _iso(to_at)), context)

    def appointment_history(self, context: AccessContext, appointment_id: str) -> dict[str, Any]:
        return self._call("SELECT psique_v2_appointment_history(%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           appointment_id), context)

    def link_source(self, context: AccessContext, *, appointment_id: str,
                    analysis_source_id: str) -> dict[str, Any]:
        return self._call("SELECT psique_v2_appointment_link_source(%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           appointment_id, analysis_source_id), context)

    # -- Mirror worker boundary (operator context; tokens live elsewhere) ----
    def outbox_take(self, context: AccessContext, how_many: int = 10) -> dict[str, Any]:
        return self._call("SELECT psique_v2_outbox_take(%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           how_many), context)

    def outbox_settle(self, context: AccessContext, *, outbox_id: str, delivered: bool,
                      external_event_id: str = "", error_note: str = "") -> dict[str, Any]:
        return self._call("SELECT psique_v2_outbox_settle(%s,%s,%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           outbox_id, delivered, external_event_id, error_note), context)

    def calendar_sync_status(self, context: AccessContext) -> dict[str, Any]:
        return self._call("SELECT psique_v2_calendar_sync_status(%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id),
                          context)
