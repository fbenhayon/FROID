"""Phase 2C: organizational license over Stripe TEST.

V2.1 rules, tested against real PostgreSQL: clinical activation is immediate
and operational; billing is a separate versioned preview/confirm. Increases
bill the new seat from confirmation on, with the proration accrued to the next
invoice (never always_invoice). Reductions are operational now and financial
on the next cycle, without touching Stripe today. Zero clinicians never
create a subscription; going back to zero cancels at period end. The license
never grants credits, and billing state never suspends a professional.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import psique_pricing
from psique_billing import PHASE2C_SCHEMA, BillingError, executar_comando_v2
from tenant_access import AccessContext

# Mirrors of the migration 040 CHECK domains; drift is guarded by tests.
CLINICAL_STATUSES = ("ACTIVE", "INACTIVE")
LICENSE_STATUSES = ("ACTIVE", "PENDING_PAYMENT", "PAST_DUE", "CANCEL_AT_PERIOD_END", "CANCELED")
CHANGE_STATUSES = ("PREVIEWED", "CONFIRMED", "SUPERSEDED", "ABORTED")


class PsiqueLicense:
    def __init__(self, connection_factory: Callable[[], Any], *, stripe_client: Any,
                 account_id: str, catalog: dict[str, Any] | None = None,
                 billing_email_resolver: Callable[[AccessContext], str] | None = None):
        if not account_id.startswith("acct_"):
            raise BillingError("STRIPE_ACCOUNT_REQUIRED")
        self._stripe = stripe_client
        self._account_id = account_id
        self._billing_email_resolver = billing_email_resolver
        self._catalog = catalog or psique_pricing.load_config()
        self._connect = connection_factory

    def _call(self, sql: str, params: tuple, context: AccessContext | None = None) -> dict[str, Any]:
        return executar_comando_v2(self._connect, sql, params,
                                   context=context, schema=PHASE2C_SCHEMA)

    # -- Pure quote ----------------------------------------------------------
    def quote(self, clinical_seat_count: int) -> dict[str, Any]:
        if type(clinical_seat_count) is not int or clinical_seat_count < 0:
            raise BillingError("CLINICAL_SEAT_COUNT_INVALID")
        return psique_pricing.organization_quote(self._catalog, clinical_seat_count)

    # -- Clinical status: operational, immediate ------------------------------
    def set_clinical(self, context: AccessContext, membership_id: str, *,
                     active: bool) -> dict[str, Any]:
        return self._call("SELECT psique_v2_clinical_set(%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           membership_id, active), context)

    def state(self, context: AccessContext) -> dict[str, Any]:
        return self._call("SELECT psique_v2_license_state(%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id),
                          context)

    # -- Billing: versioned preview/confirm ----------------------------------
    def preview(self, context: AccessContext) -> dict[str, Any]:
        for _ in range(3):
            active = self.state(context)["active_clinical_seat_count"]
            quoted = self.quote(active)
            if quoted["enterprise_required"]:
                raise BillingError("ENTERPRISE_REQUIRED_NO_SELF_SERVICE")
            try:
                preview = self._call(
                    "SELECT psique_v2_seat_preview(%s,%s,%s,%s::jsonb)",
                    (context.organization_id, context.membership_id, context.user_id,
                     json.dumps({"expected_active": active,
                                 "quote_monthly_cents": quoted["monthly_cents"],
                                 "pricing_version": quoted["pricing_version"],
                                 "pricing_hash": quoted["pricing_hash"]},
                                allow_nan=False)), context)
            except BillingError as error:
                if error.code == "SEAT_COUNT_CHANGED_RETRY":
                    continue
                raise
            return {**preview, "quote": quoted}
        raise BillingError("SEAT_COUNT_UNSTABLE_RETRY_LATER")

    def confirm(self, context: AccessContext, *, preview_id: str,
                expected_version: int | None) -> dict[str, Any]:
        state = self.state(context)
        active = state["active_clinical_seat_count"]
        billed = state["billed_clinical_seat_count"]
        subscription_id = state["stripe_subscription_id"]
        payload: dict[str, Any] | None = None
        compensate: Callable[[], Any] | None = None

        if subscription_id is None and active > 0:
            quoted = self.quote(active)
            if quoted["enterprise_required"]:
                raise BillingError("ENTERPRISE_REQUIRED_NO_SELF_SERVICE")
            price_id = self._license_price_id(context)
            if self._billing_email_resolver is None:
                # No invented billing e-mail: creating the subscription fails
                # closed until the activation phase wires the real source.
                raise BillingError("BILLING_EMAIL_RESOLVER_REQUIRED")
            billing_email = (self._billing_email_resolver(context) or "").strip()
            if not billing_email:
                raise BillingError("BILLING_EMAIL_REQUIRED")
            customer = self._stripe.create_customer(
                description="FROID Psique V2 org " + context.organization_id,
                email=billing_email)
            subscription = self._stripe.create_license_subscription(
                customer_id=customer["id"], price_id=price_id, quantity=active)
            if subscription.get("livemode") is not False:
                raise BillingError("LIVE_SUBSCRIPTION_REFUSED")
            item = subscription["items"]["data"][0]
            payload = {
                "account_id": self._account_id, "livemode": False,
                "customer_id": customer["id"], "subscription_id": subscription["id"],
                "item_id": item["id"], "price_id": price_id,
                "quantity": item["quantity"],
                "license_status": "ACTIVE" if subscription.get("status") == "active" else "PENDING_PAYMENT",
                "current_period_end": self._period_end_iso(subscription),
            }

            def compensate() -> None:
                self._stripe.set_cancel_at_period_end(
                    subscription_id=subscription["id"], cancel=True)
        elif subscription_id is not None and active == 0:
            self._stripe.set_cancel_at_period_end(subscription_id=subscription_id, cancel=True)
            payload = {"subscription_id": subscription_id, "cancel_at_period_end": True}

            def compensate() -> None:
                self._stripe.set_cancel_at_period_end(
                    subscription_id=subscription_id, cancel=False)
        elif subscription_id is not None and billed is not None and active > billed:
            was_canceling = state["license_status"] == "CANCEL_AT_PERIOD_END"
            if was_canceling:
                self._stripe.set_cancel_at_period_end(
                    subscription_id=subscription_id, cancel=False)
            updated = self._stripe.update_subscription_quantity(
                subscription_item_id=state["stripe_subscription_item_id"], quantity=active)
            payload = {"subscription_id": subscription_id,
                       "quantity": updated.get("quantity", active),
                       "proration_behavior": "create_prorations"}
            if was_canceling:
                payload["cancel_at_period_end"] = False

            def compensate() -> None:
                self._stripe.update_subscription_quantity(
                    subscription_item_id=state["stripe_subscription_item_id"], quantity=billed)
                if was_canceling:
                    self._stripe.set_cancel_at_period_end(
                        subscription_id=subscription_id, cancel=True)
        elif (subscription_id is not None and active > 0
              and state["license_status"] == "CANCEL_AT_PERIOD_END"):
            # Reactivation within the billed quantity: only remove the
            # scheduled cancellation; no new charge today.
            self._stripe.set_cancel_at_period_end(subscription_id=subscription_id, cancel=False)
            payload = {"subscription_id": subscription_id, "cancel_at_period_end": False}

            def compensate() -> None:
                self._stripe.set_cancel_at_period_end(
                    subscription_id=subscription_id, cancel=True)

        try:
            result = self._call(
                "SELECT psique_v2_seat_confirm(%s,%s,%s,%s::jsonb)",
                (context.organization_id, context.membership_id, context.user_id,
                 json.dumps({"preview_id": preview_id, "expected_version": expected_version,
                             "stripe": payload}, allow_nan=False)), context)
        except BillingError:
            # The DB refused after the Stripe side effect: undo the quantity
            # or cancellation (never history) and surface the original error.
            if compensate is not None:
                self._try_compensate(compensate)
            raise
        if not result.get("applied") and compensate is not None:
            if result.get("code") == "PREVIEW_CONFIRMED":
                # A concurrent confirm of the SAME preview already applied the
                # same target quantity; compensating would undo real billing.
                return result
            if not self._try_compensate(compensate):
                raise BillingError("STRIPE_COMPENSATION_FAILED_REVIEW_REQUIRED")
        return result

    @staticmethod
    def _try_compensate(compensate: Callable[[], Any]) -> bool:
        try:
            compensate()
            return True
        except BillingError:
            # The divergence also surfaces via license sync / status_reason;
            # the caller decides whether to escalate.
            return False

    def _license_price_id(self, context: AccessContext) -> str:
        row = self._call(
            "SELECT psique_v2_license_price_mapping(%s,%s,%s,%s,%s)",
            (context.organization_id, context.membership_id, context.user_id,
             self._catalog["version"], self._account_id), context)
        return str(row["price_id"])

    @staticmethod
    def _period_end_iso(subscription: dict[str, Any]) -> str | None:
        from datetime import datetime, timezone

        value = subscription.get("current_period_end")
        if not isinstance(value, int):
            items = (subscription.get("items") or {}).get("data") or []
            value = items[0].get("current_period_end") if items else None
        if isinstance(value, int):
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        return None
