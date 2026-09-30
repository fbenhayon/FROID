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

_DENIED_CODES = {
    "PSIQUE_CONTEXT_MISMATCH", "PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED",
    "PSIQUE_BILLING_ADMIN_REQUIRED", "PURCHASE_ACCESS_DENIED",
    "PREVIEW_ACCESS_DENIED", "CLINICAL_TARGET_MEMBERSHIP_REQUIRED",
    "PSIQUE_ORG_ADMIN_REQUIRED", "PSIQUE_CLINICIAN_REQUIRED",
    "RBAC_ENABLE_OWNER_REQUIRED", "RBAC_TARGET_MEMBERSHIP_REQUIRED",
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
                      "SUPERVISED_CLINICIAN_REQUIRED"}:
        return HTTPException(status_code=409, detail=error.code)
    return HTTPException(status_code=503, detail=error.code)


def build_psique_v2_billing_router(
    billing_provider: Callable[[], PsiqueBilling],
    context_dependency: Callable[..., Any],
    license_provider: Callable[[], PsiqueLicense] | None = None,
    rbac_provider: Callable[[], PsiqueRbac] | None = None,
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
