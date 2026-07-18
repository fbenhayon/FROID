"""Server-owned subscription catalog and Stripe webhook verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any


ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}
SUPPORTED_BILLING_CURRENCIES = ("brl", "usd", "eur", "cny")
AUTO_REPLENISH_TERMS_VERSION = "2026-07-17.multicurrency-v1"
# Prices are intentionally not stored here. Stripe price IDs are supplied through
# deployment secrets, while capabilities remain versioned and auditable in code.
SUBSCRIPTION_PLANS: dict[str, dict[str, Any]] = {
    "pro": {
        "code": "pro",
        "name": "FROID PRO",
        "entitlements": {
            "session_layouts": ["simplified", "detailed"],
            "clinical_metrics": True,
            "froid_explica": True,
            "organization_members": 1,
            "audit_export": False,
            "supervision": False,
        },
    },
    "plus": {
        "code": "plus",
        "name": "FROID PLUS",
        "entitlements": {
            "session_layouts": ["simplified", "detailed"],
            "clinical_metrics": True,
            "froid_explica": True,
            "organization_members": 10,
            "audit_export": True,
            "supervision": True,
        },
    },
    "master": {
        "code": "master",
        "name": "FROID MASTER",
        "entitlements": {
            "session_layouts": ["simplified", "detailed"],
            "clinical_metrics": True,
            "froid_explica": True,
            "organization_members": 35,
            "audit_export": True,
            "supervision": True,
        },
    },
}

# Commercial values are server-owned and expressed in each currency's minor
# unit. BRL, USD, EUR and CNY all use two decimal places. Package totals are the
# authoritative checkout amounts; unit values are commercial display values.
SESSION_PACKAGES: dict[str, dict[str, Any]] = {
    "pro_10": {
        "code": "pro_10", "plan_code": "pro", "sessions": 10,
        "prices": {
            "brl": {"unit_amount_minor": 1984, "total_amount_minor": 19800},
            "usd": {"unit_amount_minor": 397, "total_amount_minor": 4000},
            "eur": {"unit_amount_minor": 331, "total_amount_minor": 3300},
            "cny": {"unit_amount_minor": 1492, "total_amount_minor": 14900},
        },
    },
    "pro_25": {
        "code": "pro_25", "plan_code": "pro", "sessions": 25,
        "prices": {
            "brl": {"unit_amount_minor": 1880, "total_amount_minor": 47000},
            "usd": {"unit_amount_minor": 376, "total_amount_minor": 9400},
            "eur": {"unit_amount_minor": 313, "total_amount_minor": 7800},
            "cny": {"unit_amount_minor": 1414, "total_amount_minor": 35300},
        },
    },
    "plus_50": {
        "code": "plus_50", "plan_code": "plus", "sessions": 50,
        "prices": {
            "brl": {"unit_amount_minor": 2363, "total_amount_minor": 118200},
            "usd": {"unit_amount_minor": 473, "total_amount_minor": 23600},
            "eur": {"unit_amount_minor": 394, "total_amount_minor": 19700},
            "cny": {"unit_amount_minor": 1777, "total_amount_minor": 88900},
        },
    },
    "plus_100": {
        "code": "plus_100", "plan_code": "plus", "sessions": 100,
        "prices": {
            "brl": {"unit_amount_minor": 2202, "total_amount_minor": 220200},
            "usd": {"unit_amount_minor": 440, "total_amount_minor": 44000},
            "eur": {"unit_amount_minor": 367, "total_amount_minor": 36700},
            "cny": {"unit_amount_minor": 1656, "total_amount_minor": 165600},
        },
    },
    "master_25": {
        "code": "master_25", "plan_code": "master", "sessions": 25,
        "prices": {
            "brl": {"unit_amount_minor": 78, "total_amount_minor": 2000},
            "usd": {"unit_amount_minor": 16, "total_amount_minor": 400},
            "eur": {"unit_amount_minor": 13, "total_amount_minor": 300},
            "cny": {"unit_amount_minor": 59, "total_amount_minor": 1500},
        },
    },
}


def package_price(package: dict[str, Any], currency: str) -> dict[str, int] | None:
    normalized = str(currency or "").strip().lower()
    price = (package.get("prices") or {}).get(normalized)
    return price if isinstance(price, dict) else None


class StripeSignatureError(ValueError):
    pass


def verify_stripe_event(
    payload: bytes,
    signature_header: str,
    endpoint_secret: str,
    *,
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> dict:
    """Verify Stripe's raw-body HMAC and reject replayed deliveries."""
    if not endpoint_secret:
        raise StripeSignatureError("webhook secret is not configured")
    values: dict[str, list[str]] = {}
    for part in str(signature_header or "").split(","):
        key, separator, value = part.strip().partition("=")
        if separator and key and value:
            values.setdefault(key, []).append(value)
    try:
        timestamp = int(values.get("t", [""])[0])
    except (TypeError, ValueError) as exc:
        raise StripeSignatureError("invalid Stripe timestamp") from exc
    signatures = values.get("v1", [])
    if not signatures:
        raise StripeSignatureError("missing Stripe v1 signature")
    current_time = int(time.time() if now is None else now)
    if abs(current_time - timestamp) > max(1, int(tolerance_seconds)):
        raise StripeSignatureError("Stripe signature timestamp outside tolerance")
    signed_payload = str(timestamp).encode("ascii") + b"." + payload
    expected = hmac.new(
        endpoint_secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise StripeSignatureError("invalid Stripe signature")
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StripeSignatureError("invalid Stripe payload") from exc
    if not isinstance(event, dict) or not str(event.get("id") or "").startswith("evt_"):
        raise StripeSignatureError("invalid Stripe event")
    return event


def public_plan_catalog() -> list[dict[str, Any]]:
    return [SUBSCRIPTION_PLANS[key] for key in ("pro", "plus", "master")]


def public_package_catalog() -> list[dict[str, Any]]:
    return [SESSION_PACKAGES[key] for key in SESSION_PACKAGES]
