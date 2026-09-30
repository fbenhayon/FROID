"""Phase 2B routes for Psique V2 Stripe TEST billing.

The router is only mounted when the operator enables the V2 billing flag, so
deploying this code changes nothing for V1 until that explicit decision.
Authorization and price resolution live in the SQL command boundary; this
layer transports requests and never interprets amounts or credits.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from psique_billing import BillingError, PsiqueBilling
from psique_license import PsiqueLicense
from psique_rbac import PsiqueRbac
from psique_scheduling import PsiqueScheduling

_DENIED_CODES = {
    "PSIQUE_CONTEXT_MISMATCH", "PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED",
    "PSIQUE_BILLING_ADMIN_REQUIRED", "PURCHASE_ACCESS_DENIED",
    "PREVIEW_ACCESS_DENIED", "CLINICAL_TARGET_MEMBERSHIP_REQUIRED",
    "PSIQUE_ORG_ADMIN_REQUIRED", "PSIQUE_CLINICIAN_REQUIRED",
    "RBAC_ENABLE_OWNER_REQUIRED", "RBAC_TARGET_MEMBERSHIP_REQUIRED",
    "PSIQUE_SCHEDULING_ROLE_DENIED", "OWN_AGENDA_ONLY", "OWN_AVAILABILITY_ONLY",
    "APPOINTMENT_ACCESS_DENIED", "SOURCE_ACCESS_DENIED",
}
_BAD_REQUEST_CODES = {
    "CHECKOUT_BODY_MUST_BE_PRODUCT_CODE_ONLY", "PRODUCT_CODE_REQUIRED",
    "PRODUCT_CODE_NOT_PURCHASABLE", "IDEMPOTENCY_MISMATCH",
    "IDEMPOTENCY_KEY_REQUIRED", "RBAC_ROLE_UNKNOWN",
}


def _http_error(error: BillingError) -> HTTPException:
    if error.code in _DENIED_CODES:
        return HTTPException(status_code=403, detail=error.code)
    if error.code in _BAD_REQUEST_CODES:
        return HTTPException(status_code=422, detail=error.code)
    if error.code in {"PSIQUE_WALLET_REQUIRED", "ENTERPRISE_REQUIRED_NO_SELF_SERVICE",
                      "SEAT_COUNT_UNSTABLE_RETRY_LATER", "RBAC_V2_NOT_ENABLED",
                      "LAST_ORG_ADMIN_PROTECTED", "SUPERVISOR_ROLE_REQUIRED",
                      "SUPERVISED_CLINICIAN_REQUIRED", "APPOINTMENT_CONFLICT",
                      "OUTSIDE_AVAILABILITY"}:
        return HTTPException(status_code=409, detail=error.code)
    return HTTPException(status_code=503, detail=error.code)


def build_psique_v2_billing_router(
    billing_provider: Callable[[], PsiqueBilling],
    context_dependency: Callable[..., Any],
    license_provider: Callable[[], PsiqueLicense] | None = None,
    rbac_provider: Callable[[], PsiqueRbac] | None = None,
    scheduling_provider: Callable[[], PsiqueScheduling] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/psique/v2", tags=["psique-v2-billing"])

    @router.post("/checkout")
    async def create_checkout(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 -- fronteira HTTP: corpo ilegivel vira 422 nomeado
            raise HTTPException(status_code=422, detail="CHECKOUT_BODY_MUST_BE_PRODUCT_CODE_ONLY")
        idempotency_key = (request.headers.get("x-idempotency-key") or "").strip()
        if not idempotency_key:
            # Um retry de rede sem chave viraria uma segunda compra com uma
            # chave inventada aqui; o cliente e quem define a intencao.
            raise HTTPException(status_code=422, detail="IDEMPOTENCY_KEY_REQUIRED")
        try:
            return billing_provider().checkout(context, body, idempotency_key=idempotency_key)
        except BillingError as error:
            raise _http_error(error) from None

    @router.get("/purchases/{purchase_id}")
    async def purchase_state(purchase_id: uuid.UUID, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
        try:
            return billing_provider().purchase_state(context, str(purchase_id))
        except BillingError as error:
            raise _http_error(error) from None

    if license_provider is not None:
        @router.get("/organization-license/quote")
        async def license_quote(clinical_seat_count: int):
            try:
                return license_provider().quote(clinical_seat_count)
            except BillingError as error:
                raise _http_error(error) from None

        @router.get("/organization-license")
        async def license_state(context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                return license_provider().state(context)
            except BillingError as error:
                raise _http_error(error) from None

        @router.post("/organization-license/preview")
        async def license_preview(context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                return license_provider().preview(context)
            except BillingError as error:
                raise _http_error(error) from None

        @router.post("/organization-license/changes")
        async def license_change(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001 -- fronteira HTTP: corpo ilegivel vira 422 nomeado
                raise HTTPException(status_code=422, detail="CHANGE_BODY_INVALID")
            if not isinstance(body, dict) or set(body) != {"preview_id", "expected_version"}:
                raise HTTPException(status_code=422, detail="CHANGE_BODY_INVALID")
            try:
                result = license_provider().confirm(
                    context, preview_id=str(body["preview_id"]),
                    expected_version=body["expected_version"])
            except BillingError as error:
                raise _http_error(error) from None
            if not result.get("applied"):
                return JSONResponse(status_code=409, content=result)
            return result

        @router.patch("/clinical-memberships/{membership_id}")
        async def clinical_set(membership_id: uuid.UUID, request: Request,
                               context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001 -- fronteira HTTP: corpo ilegivel vira 422 nomeado
                raise HTTPException(status_code=422, detail="CLINICAL_BODY_INVALID")
            if not isinstance(body, dict) or set(body) != {"active"} or not isinstance(body["active"], bool):
                raise HTTPException(status_code=422, detail="CLINICAL_BODY_INVALID")
            try:
                return license_provider().set_clinical(
                    context, str(membership_id), active=body["active"])
            except BillingError as error:
                raise _http_error(error) from None

    if rbac_provider is not None:
        @router.get("/capabilities")
        async def rbac_capabilities(context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                return rbac_provider().capabilities(context)
            except BillingError as error:
                raise _http_error(error) from None

        @router.post("/rbac/enable")
        async def rbac_enable(context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                return rbac_provider().enable(context)
            except BillingError as error:
                raise _http_error(error) from None

        async def _rbac_role_body(request: Request) -> tuple[str, str]:
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001 -- fronteira HTTP: corpo ilegivel vira 422 nomeado
                raise HTTPException(status_code=422, detail="RBAC_BODY_INVALID")
            if not isinstance(body, dict) or set(body) != {"membership_id", "role"}:
                raise HTTPException(status_code=422, detail="RBAC_BODY_INVALID")
            return str(body["membership_id"]), str(body["role"])

        @router.post("/rbac/role-grants")
        async def rbac_grant(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            membership_id, role = await _rbac_role_body(request)
            try:
                return rbac_provider().grant_role(context, membership_id, role)
            except BillingError as error:
                raise _http_error(error) from None

        @router.post("/rbac/role-revocations")
        async def rbac_revoke(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            membership_id, role = await _rbac_role_body(request)
            try:
                return rbac_provider().revoke_role(context, membership_id, role)
            except BillingError as error:
                raise _http_error(error) from None

        @router.post("/rbac/supervisions")
        async def rbac_supervision(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001 -- fronteira HTTP: corpo ilegivel vira 422 nomeado
                raise HTTPException(status_code=422, detail="RBAC_BODY_INVALID")
            expected = {"supervisor_membership_id", "supervised_membership_id", "active"}
            if not isinstance(body, dict) or set(body) != expected or not isinstance(body["active"], bool):
                raise HTTPException(status_code=422, detail="RBAC_BODY_INVALID")
            try:
                return rbac_provider().set_supervision(
                    context, supervisor_membership_id=str(body["supervisor_membership_id"]),
                    supervised_membership_id=str(body["supervised_membership_id"]),
                    active=body["active"])
            except BillingError as error:
                raise _http_error(error) from None

    if scheduling_provider is not None:
        from datetime import datetime

        def _dt(value: Any, field: str) -> datetime:
            try:
                parsed = datetime.fromisoformat(str(value))
            except ValueError:
                raise HTTPException(status_code=422, detail=f"SCHEDULING_{field}_INVALID")
            if parsed.tzinfo is None:
                raise HTTPException(status_code=422, detail=f"SCHEDULING_{field}_INVALID")
            return parsed

        async def _json_body(request: Request, expected: set[str],
                             optional: set[str] | frozenset[str] = frozenset()):
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001 -- fronteira HTTP: corpo ilegivel vira 422 nomeado
                raise HTTPException(status_code=422, detail="SCHEDULING_BODY_INVALID")
            if not isinstance(body, dict) or not expected <= set(body) or not set(body) <= (expected | optional):
                raise HTTPException(status_code=422, detail="SCHEDULING_BODY_INVALID")
            return body

        @router.post("/scheduling/units")
        async def scheduling_unit(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            body = await _json_body(request, {"unit_name"})
            try:
                return scheduling_provider().upsert_unit(context, str(body["unit_name"]))
            except BillingError as error:
                raise _http_error(error) from None

        @router.put("/scheduling/availability")
        async def scheduling_availability(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            body = await _json_body(request, {"clinician_membership_id", "weekday",
                                              "start_minute", "end_minute", "timezone"},
                                    {"active"})
            try:
                return scheduling_provider().set_availability(
                    context, clinician_membership_id=str(body["clinician_membership_id"]),
                    weekday=int(body["weekday"]), start_minute=int(body["start_minute"]),
                    end_minute=int(body["end_minute"]), timezone_name=str(body["timezone"]),
                    active=bool(body.get("active", True)))
            except BillingError as error:
                raise _http_error(error) from None

        @router.get("/scheduling/appointments")
        async def scheduling_list(from_at: str, to_at: str,
                                  context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                return scheduling_provider().list_appointments(
                    context, from_at=_dt(from_at, "FROM"), to_at=_dt(to_at, "TO"))
            except BillingError as error:
                raise _http_error(error) from None

        @router.post("/scheduling/appointments")
        async def scheduling_create(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            body = await _json_body(request, {"patient_id", "clinician_membership_id",
                                              "start_at", "end_at", "timezone"}, {"unit_id"})
            idempotency_key = (request.headers.get("x-idempotency-key") or "").strip()
            if not idempotency_key:
                raise HTTPException(status_code=422, detail="IDEMPOTENCY_KEY_REQUIRED")
            try:
                return scheduling_provider().create_appointment(
                    context, patient_id=str(body["patient_id"]),
                    clinician_membership_id=str(body["clinician_membership_id"]),
                    start_at=_dt(body["start_at"], "START"), end_at=_dt(body["end_at"], "END"),
                    timezone_name=str(body["timezone"]),
                    idempotency_key=idempotency_key,
                    unit_id=str(body["unit_id"]) if body.get("unit_id") else None)
            except BillingError as error:
                raise _http_error(error) from None

        @router.patch("/scheduling/appointments/{appointment_id}")
        async def scheduling_change(appointment_id: uuid.UUID, request: Request,
                                    context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            body = await _json_body(request, {"expected_version"},
                                    {"start_at", "end_at", "appointment_status"})
            try:
                result = scheduling_provider().change_appointment(
                    context, appointment_id=str(appointment_id),
                    expected_version=int(body["expected_version"]),
                    start_at=_dt(body["start_at"], "START") if body.get("start_at") else None,
                    end_at=_dt(body["end_at"], "END") if body.get("end_at") else None,
                    appointment_status=body.get("appointment_status"))
            except BillingError as error:
                raise _http_error(error) from None
            if not result.get("applied"):
                return JSONResponse(status_code=409, content=result)
            return result

        @router.post("/scheduling/appointments/{appointment_id}/cancel")
        async def scheduling_cancel(appointment_id: uuid.UUID, request: Request,
                                    context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            body = await _json_body(request, {"expected_version"}, {"reason"})
            try:
                result = scheduling_provider().cancel_appointment(
                    context, appointment_id=str(appointment_id),
                    expected_version=int(body["expected_version"]),
                    reason=str(body.get("reason", "")))
            except BillingError as error:
                raise _http_error(error) from None
            if not result.get("applied"):
                return JSONResponse(status_code=409, content=result)
            return result

        @router.get("/scheduling/appointments/{appointment_id}/history")
        async def scheduling_history(appointment_id: uuid.UUID,
                                     context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                return scheduling_provider().appointment_history(context, str(appointment_id))
            except BillingError as error:
                raise _http_error(error) from None

        @router.post("/scheduling/appointments/{appointment_id}/session-link")
        async def scheduling_link(appointment_id: uuid.UUID, request: Request,
                                  context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            body = await _json_body(request, {"analysis_source_id"})
            try:
                return scheduling_provider().link_source(
                    context, appointment_id=str(appointment_id),
                    analysis_source_id=str(body["analysis_source_id"]))
            except BillingError as error:
                raise _http_error(error) from None

        @router.get("/scheduling/calendar-sync/status")
        async def scheduling_sync_status(context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
            try:
                return scheduling_provider().calendar_sync_status(context)
            except BillingError as error:
                raise _http_error(error) from None

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        payload = await request.body()
        signature = request.headers.get("stripe-signature") or ""
        try:
            status_code, body = billing_provider().webhook(payload, signature)
        except BillingError as error:
            # Recorded-but-unprocessable events return 503 so Stripe retries;
            # the durable inbox row keeps reprocessing idempotent.
            return JSONResponse(status_code=503, content={"received": False, "code": error.code})
        return JSONResponse(status_code=status_code, content=body)

    return router
