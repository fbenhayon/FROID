"""Phase 2B: Stripe TEST checkout and webhook for Psique V2 credit packs.

The browser only ever sends a product_code. Price, credits, currency and the
Stripe Price ID are resolved server side from the installed catalog and the
verified TEST mapping. Credits are granted exactly once per Purchase, by the
SQL command boundary, only after a signed paid event is durably recorded.

No secret is ever logged, returned or persisted by this module.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from froid_schema import verify_schema
from tenant_access import AccessContext

PHASE2B_SCHEMA = {
    "035_psique_v2_pricing", "036_psique_v2_purchases",
    "037_psique_trial_credit_state", "038_psique_credit_commands",
    "039_psique_stripe_test_checkout",
}
PHASE2C_SCHEMA = PHASE2B_SCHEMA | {"040_psique_org_license_test"}

# Mirrors the CHECK constraints of migration 039; test_enum_drift compares.
PURCHASE_STATUSES = (
    "prepared", "canceled", "CREATED", "CHECKOUT_CREATED", "PENDING_PAYMENT",
    "PAID", "APPLIED", "CANCELED", "EXPIRED", "FAILED", "REVIEW_REQUIRED",
)
EVENT_PROCESSING_STATUSES = ("received", "credited", "resolved", "review", "rejected")

CREDIT_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
REVIEW_EVENTS = (
    "charge.dispute.created", "charge.dispute.closed", "charge.refunded",
    "refund.created", "refund.updated", "refund.failed",
)
_SECRET_PATTERN = re.compile(r"(?:[sr]k_(?:test|live)|whsec)_[A-Za-z0-9]+")


def _sanitize(text: str) -> str:
    return _SECRET_PATTERN.sub("<segredo omitido>", text or "")[:200]


class BillingError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def verify_stripe_signature(payload: bytes, header: str, secret: str, *,
                            tolerance_seconds: int = 300, now: float | None = None) -> None:
    """Constant-time verification of the Stripe-Signature header (v1 scheme)."""
    if not secret:
        raise BillingError("WEBHOOK_SECRET_REQUIRED")
    timestamp = None
    candidates: list[str] = []
    for part in (header or "").split(","):
        name, _, value = part.strip().partition("=")
        if name == "t" and value.isdigit():
            timestamp = int(value)
        elif name == "v1" and re.fullmatch(r"[0-9a-f]{64}", value):
            candidates.append(value)
    if timestamp is None or not candidates:
        raise BillingError("SIGNATURE_HEADER_INVALID")
    current = now if now is not None else time.time()
    if abs(current - timestamp) > tolerance_seconds:
        raise BillingError("SIGNATURE_TIMESTAMP_OUT_OF_TOLERANCE")
    signed = str(timestamp).encode("ascii") + b"." + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise BillingError("SIGNATURE_INVALID")


class StripeTestClient:
    """Raw HTTPS client bound to one TEST key. Refuses LIVE at construction."""

    def __init__(self, secret_key: str, *, timeout: int = 30):
        if not secret_key.startswith(("sk_test_", "rk_test_")):
            raise BillingError("STRIPE_TEST_KEY_REQUIRED")
        self._key = secret_key
        self._timeout = timeout

    def _request(self, method: str, path: str, fields: list[tuple[str, str]] | None = None) -> dict[str, Any]:
        body = urllib.parse.urlencode(fields).encode("ascii") if fields else None
        request = urllib.request.Request(
            "https://api.stripe.com" + path, data=body, method=method,
            headers={"Authorization": "Bearer " + self._key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            try:
                message = json.load(error).get("error", {}).get("message", "")
            except Exception:  # noqa: BLE001 -- resposta de erro ilegivel nao pode derrubar a sanitizacao
                message = ""
            raise BillingError(f"STRIPE_HTTP_{error.code} {_sanitize(message)}") from None
        except urllib.error.URLError:
            raise BillingError("STRIPE_UNREACHABLE") from None

    def account(self) -> dict[str, Any]:
        return self._request("GET", "/v1/account")

    def create_checkout_session(self, *, price_id: str, purchase_id: str,
                                success_url: str, cancel_url: str) -> dict[str, Any]:
        return self._request("POST", "/v1/checkout/sessions", [
            ("mode", "payment"),
            ("line_items[0][price]", price_id),
            ("line_items[0][quantity]", "1"),
            ("success_url", success_url),
            ("cancel_url", cancel_url),
            ("client_reference_id", purchase_id),
            ("metadata[purchase_id]", purchase_id),
            ("metadata[froid_product]", "psique"),
        ])

    def get_checkout_session(self, session_id: str) -> dict[str, Any]:
        query = urllib.parse.urlencode([("expand[]", "line_items")])
        return self._request(
            "GET", f"/v1/checkout/sessions/{urllib.parse.quote(session_id)}?{query}",
        )

    # -- Organizational license (Phase 2C, TEST homologation) ---------------
    def create_customer(self, *, description: str, email: str) -> dict[str, Any]:
        # send_invoice collection requires a deliverable billing e-mail.
        return self._request("POST", "/v1/customers",
                             [("description", description), ("email", email)])

    def create_license_subscription(self, *, customer_id: str, price_id: str,
                                    quantity: int) -> dict[str, Any]:
        # TEST homologation collects by invoice so no synthetic card is needed;
        # a LIVE collection decision belongs to a later authorized phase.
        return self._request("POST", "/v1/subscriptions", [
            ("customer", customer_id),
            ("items[0][price]", price_id),
            ("items[0][quantity]", str(quantity)),
            ("collection_method", "send_invoice"),
            ("days_until_due", "30"),
        ])

    def update_subscription_quantity(self, *, subscription_item_id: str,
                                     quantity: int) -> dict[str, Any]:
        # Accrues the proration to the next invoice; never always_invoice.
        return self._request("POST", f"/v1/subscription_items/{subscription_item_id}", [
            ("quantity", str(quantity)),
            ("proration_behavior", "create_prorations"),
        ])

    def set_cancel_at_period_end(self, *, subscription_id: str, cancel: bool) -> dict[str, Any]:
        return self._request("POST", f"/v1/subscriptions/{subscription_id}", [
            ("cancel_at_period_end", "true" if cancel else "false"),
        ])

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/subscriptions/{urllib.parse.quote(subscription_id)}")

    def preview_license_invoice(self, *, customer_id: str, price_id: str,
                                quantity: int) -> dict[str, Any]:
        return self._request("POST", "/v1/invoices/create_preview", [
            ("customer", customer_id),
            ("subscription_details[items][0][price]", price_id),
            ("subscription_details[items][0][quantity]", str(quantity)),
        ])


def flatten_session(session: dict[str, Any]) -> dict[str, Any]:
    """Project the fields the SQL validator checks; absent keys stay absent."""
    flat: dict[str, Any] = {key: session.get(key) for key in (
        "id", "livemode", "payment_status", "amount_total", "currency",
        "client_reference_id", "payment_intent")}
    if isinstance(session.get("metadata"), dict):
        flat["metadata"] = {"purchase_id": session["metadata"].get("purchase_id")}
    items = (session.get("line_items") or {}).get("data") or []
    if items:
        price = items[0].get("price") or {}
        flat["price_id"] = price.get("id")
        product = price.get("product")
        flat["product_id"] = product.get("id") if isinstance(product, dict) else product
        flat["quantity"] = items[0].get("quantity")
    return flat


class PsiqueBilling:
    def __init__(self, connection_factory: Callable[[], Any], *,
                 stripe_client: Any, webhook_secret: str, account_id: str,
                 pricing_version: str, success_url: str, cancel_url: str):
        if not account_id.startswith("acct_"):
            raise BillingError("STRIPE_ACCOUNT_REQUIRED")
        self._connect = connection_factory
        self._stripe = stripe_client
        self._webhook_secret = webhook_secret
        self._account_id = account_id
        self._pricing_version = pricing_version
        self._success_url = success_url
        self._cancel_url = cancel_url

    def _call(self, sql: str, params: tuple, context: AccessContext | None = None,
              schema: set[str] | None = None) -> dict[str, Any]:
        import psycopg

        try:
            with self._connect() as conn, conn.transaction():
                verify_schema(conn, schema or PHASE2B_SCHEMA)
                if context is not None:
                    conn.execute("SELECT set_config('app.organization_id',%s,true)",
                                 (context.organization_id,))
                    conn.execute("SELECT set_config('app.membership_id',%s,true)",
                                 (context.membership_id,))
                row = conn.execute(sql, params).fetchone()
                if row is None:
                    raise BillingError("PSIQUE_COMMAND_RESULT_MISSING")
                result: dict[str, Any] = row[0]
                return result
        except psycopg.Error as exc:
            reason = exc.diag.message_primary or ""
            if reason and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in reason):
                raise BillingError(reason) from exc
            raise BillingError("PSIQUE_STORAGE_ERROR") from exc

    # -- Checkout -----------------------------------------------------------
    def checkout(self, context: AccessContext, body: dict[str, Any], *,
                 idempotency_key: str) -> dict[str, Any]:
        if not isinstance(body, dict) or set(body) != {"product_code"}:
            # amount/credits/currency/price ids from the browser are refused,
            # not ignored: a silent drop would hide a tampering attempt.
            raise BillingError("CHECKOUT_BODY_MUST_BE_PRODUCT_CODE_ONLY")
        product_code = body["product_code"]
        if not isinstance(product_code, str) or not product_code.strip():
            raise BillingError("PRODUCT_CODE_REQUIRED")
        prepared = self._call(
            "SELECT psique_v2_checkout_prepare(%s,%s,%s,%s,%s,%s,%s)",
            (context.organization_id, context.membership_id, context.user_id,
             product_code.strip(), self._pricing_version, self._account_id,
             idempotency_key), context)
        session_id = prepared.get("stripe_checkout_session_id")
        if session_id:
            session = self._stripe.get_checkout_session(session_id)
            return {"purchase_id": prepared["purchase_id"], "status": prepared["status"],
                    "checkout_url": session.get("url")}
        session = self._stripe.create_checkout_session(
            price_id=prepared["stripe_price_id"], purchase_id=str(prepared["purchase_id"]),
            success_url=self._success_url, cancel_url=self._cancel_url)
        if session.get("livemode") is not False:
            raise BillingError("LIVE_SESSION_REFUSED")
        attached = self._call(
            "SELECT psique_v2_checkout_attach(%s,%s,%s,%s,%s)",
            (context.organization_id, context.membership_id, context.user_id,
             prepared["purchase_id"], session["id"]), context)
        return {"purchase_id": attached["purchase_id"], "status": attached["status"],
                "checkout_url": session.get("url")}

    def purchase_state(self, context: AccessContext, purchase_id: str) -> dict[str, Any]:
        return self._call(
            "SELECT psique_v2_purchase_state(%s,%s,%s,%s)",
            (context.organization_id, context.membership_id, context.user_id,
             purchase_id), context)

    # -- Webhook ------------------------------------------------------------
    def webhook(self, payload: bytes, signature_header: str) -> tuple[int, dict[str, Any]]:
        try:
            verify_stripe_signature(payload, signature_header, self._webhook_secret)
        except BillingError as error:
            return 400, {"received": False, "code": error.code}
        try:
            event = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"received": False, "code": "EVENT_PAYLOAD_INVALID"}
        event_id = event.get("id")
        event_type = event.get("type")
        target = (event.get("data") or {}).get("object") or {}
        if (not isinstance(event_id, str) or not re.fullmatch(r"evt_[A-Za-z0-9]+", event_id)
                or not isinstance(event_type, str) or not event_type):
            return 400, {"received": False, "code": "EVENT_PAYLOAD_INVALID"}
        if event.get("livemode") is not False or target.get("livemode") is True:
            # A LIVE event on the TEST endpoint is a configuration failure and
            # must fail loudly instead of entering the TEST inbox.
            return 400, {"received": False, "code": "LIVE_EVENT_REFUSED"}
        session_id = target.get("id") if event_type.startswith("checkout.session.") else None
        if session_id is not None and not re.fullmatch(r"cs_test_[A-Za-z0-9]+", session_id):
            return 400, {"received": False, "code": "EVENT_PAYLOAD_INVALID"}
        payload_hash = hashlib.sha256(payload).hexdigest()

        recorded = self._call(
            "SELECT psique_v2_stripe_event(%s,%s,%s,%s,%s,%s)",
            (self._account_id, False, event_id, event_type, session_id, payload_hash))
        if recorded["duplicate"] and recorded["processing_status"] != "received":
            return 200, {"received": True, "duplicate": True,
                         "processing_status": recorded["processing_status"]}

        if event_type in CREDIT_EVENTS:
            outcome = self._apply(event_id, session_id, target)
        elif event_type == "checkout.session.expired":
            outcome = self._outcome(event_id, "EXPIRED", "CHECKOUT_SESSION_EXPIRED")
        elif event_type == "checkout.session.async_payment_failed":
            outcome = self._outcome(event_id, "FAILED", "ASYNC_PAYMENT_FAILED")
        elif event_type in REVIEW_EVENTS:
            outcome = self._outcome(event_id, "REVIEW", event_type)
        elif event_type.startswith("customer.subscription."):
            outcome = self._license_sync(event_id, target)
        elif event_type.startswith("invoice."):
            # License state follows the subscription object; invoices are
            # auditable and never move credits or clinical status.
            outcome = self._outcome(event_id, "RESOLVED", "LICENSE_INVOICE_AUDIT_ONLY")
        elif event_type == "payment_intent.succeeded":
            # Audited, never grants: the grant belongs to the paid Checkout.
            outcome = self._outcome(event_id, "RESOLVED", "AUDIT_ONLY_PAYMENT_INTENT")
        elif event_type == "payment_intent.payment_failed":
            outcome = self._outcome(event_id, "RESOLVED", "PAYMENT_FAILED_NO_GRANT")
        else:
            outcome = self._outcome(event_id, "RESOLVED", "UNHANDLED_EVENT_TYPE")
        return 200, {"received": True, "duplicate": bool(recorded["duplicate"]), **outcome}

    def _apply(self, event_id: str, session_id: str | None, payload_object: dict[str, Any]) -> dict[str, Any]:
        if session_id is None:
            return self._outcome(event_id, "RESOLVED", "SESSION_ID_MISSING")
        source = payload_object
        if self._stripe is not None:
            try:
                # The applied truth is the session Stripe returns to OUR key,
                # not the delivered payload: a session from another account or
                # mode does not resolve here and is rejected downstream.
                source = self._stripe.get_checkout_session(session_id)
            except BillingError as error:
                if error.code.startswith("STRIPE_HTTP_404"):
                    return self._outcome(event_id, "RESOLVED", "SESSION_NOT_IN_ACCOUNT")
                raise
        flat = flatten_session(source)
        result = self._call("SELECT psique_v2_apply_purchase(%s,%s::jsonb)",
                            (event_id, json.dumps(flat, allow_nan=False)))
        return result

    def _outcome(self, event_id: str, outcome: str, note: str) -> dict[str, Any]:
        return self._call("SELECT psique_v2_purchase_outcome(%s,%s,%s)",
                          (event_id, outcome, _sanitize(note)))

    def _license_sync(self, event_id: str, subscription: dict[str, Any]) -> dict[str, Any]:
        from datetime import datetime, timezone

        period_end = subscription.get("current_period_end")
        items = (subscription.get("items") or {}).get("data") or []
        synced = self._call(
            "SELECT psique_v2_license_sync(%s::jsonb)",
            (json.dumps({
                "subscription_id": subscription.get("id"),
                "stripe_status": subscription.get("status"),
                "cancel_at_period_end": subscription.get("cancel_at_period_end"),
                "current_period_end": datetime.fromtimestamp(
                    period_end, tz=timezone.utc).isoformat() if isinstance(period_end, int) else None,
                "quantity": items[0].get("quantity") if items else None,
            }, allow_nan=False),), schema=PHASE2C_SCHEMA)
        note = "LICENSE_SYNC_" + ("OK" if synced.get("synced") else str(synced.get("code")))
        closure = self._outcome(event_id, "RESOLVED", note)
        return {**closure, "license_sync": synced}
