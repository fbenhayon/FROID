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

_DENIED_CODES = {
    "PSIQUE_CONTEXT_MISMATCH", "PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED",
    "PSIQUE_BILLING_ADMIN_REQUIRED", "PURCHASE_ACCESS_DENIED",
}
_BAD_REQUEST_CODES = {
    "CHECKOUT_BODY_MUST_BE_PRODUCT_CODE_ONLY", "PRODUCT_CODE_REQUIRED",
    "PRODUCT_CODE_NOT_PURCHASABLE", "IDEMPOTENCY_MISMATCH",
    "IDEMPOTENCY_KEY_REQUIRED",
}


def _http_error(error: BillingError) -> HTTPException:
    if error.code in _DENIED_CODES:
        return HTTPException(status_code=403, detail=error.code)
    if error.code in _BAD_REQUEST_CODES:
        return HTTPException(status_code=422, detail=error.code)
    if error.code == "PSIQUE_WALLET_REQUIRED":
        return HTTPException(status_code=409, detail=error.code)
    return HTTPException(status_code=503, detail=error.code)


def build_psique_v2_billing_router(
    billing_provider: Callable[[], PsiqueBilling],
    context_dependency: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(prefix="/api/psique/v2", tags=["psique-v2-billing"])

    @router.post("/checkout")
    async def create_checkout(request: Request, context: Any = Depends(context_dependency)):  # noqa: B008 -- padrao FastAPI de dependencia
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 -- fronteira HTTP: corpo ilegivel vira 422 nomeado
            raise HTTPException(status_code=422, detail="CHECKOUT_BODY_MUST_BE_PRODUCT_CODE_ONLY")
        idempotency_key = request.headers.get("x-idempotency-key") or uuid.uuid4().hex
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
