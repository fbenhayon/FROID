"""Server-owned Psique V2 pricing, with no checkout or credit side effects.

The bundled configuration is installed explicitly as DRAFT for Phase 1.
It is not a fallback when a database/catalog is unavailable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(__file__).parent / "config" / "psique_pricing_v2.json"
BILLING_TYPES = frozenset({"one_time", "usage", "monthly_graduated"})

# Regra do Trial V2. A fonte executavel vive na migration 037
# (credits_granted=10; expires_at = started_at + 336 horas); estes espelhos
# existem para a comunicacao publica e tem guarda de teste contra a 037.
TRIAL_CREDITS = 10
TRIAL_DAYS = 14


class PricingError(ValueError):
    pass


def integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PricingError("invalid_integer:" + name)
    return value


def _no_float(value: Any) -> None:
    if isinstance(value, float):
        raise PricingError("float_not_allowed")
    if isinstance(value, dict):
        for child in value.values():
            _no_float(child)
    elif isinstance(value, list):
        for child in value:
            _no_float(child)


def validate(config: dict[str, Any]) -> None:
    _no_float(config)
    if set(config) != {"code", "version", "currency", "offers", "organization_license"}:
        raise PricingError("invalid_config_fields")
    if config["code"] != "FROID_PSIQUE_V2" or config["currency"] != "brl":
        raise PricingError("invalid_product_or_currency")
    if not isinstance(config["version"], str) or not config["version"].strip():
        raise PricingError("missing_pricing_version")
    if not isinstance(config["offers"], list) or not config["offers"]:
        raise PricingError("missing_offers")
    codes: set[str] = set()
    for offer in config["offers"]:
        if set(offer) != {"product_code", "name", "credits", "total_cents",
                          "billing_type", "active", "public"}:
            raise PricingError("invalid_offer_fields")
        code = offer["product_code"]
        if not isinstance(code, str) or not code.startswith("FROID_") or code in codes:
            raise PricingError("invalid_or_duplicate_product")
        codes.add(code)
        if not isinstance(offer["name"], str) or not offer["name"].strip():
            raise PricingError("missing_offer_name")
        if type(offer["active"]) is not bool or type(offer["public"]) is not bool:
            raise PricingError("invalid_offer_visibility")
        billing = offer["billing_type"]
        if billing not in BILLING_TYPES:
            raise PricingError("invalid_billing_type")
        if billing == "one_time":
            integer(offer["credits"], "credits", 1)
            integer(offer["total_cents"], "total_cents", 1)
        elif billing in {"usage", "monthly_graduated"}:
            if offer["credits"] is not None:
                raise PricingError("license_or_usage_must_not_grant_credits")
            if billing == "usage":
                integer(offer["total_cents"], "usage_cents", 1)
            elif offer["total_cents"] is not None:
                raise PricingError("graduated_price_is_not_a_flat_total")
    rule = config["organization_license"]
    if set(rule) != {"base_cents", "included_clinicians", "self_service_max", "tiers"}:
        raise PricingError("invalid_license_fields")
    integer(rule["base_cents"], "base_cents", 1)
    included = integer(rule["included_clinicians"], "included_clinicians", 1)
    maximum = integer(rule["self_service_max"], "self_service_max", included)
    next_from = included + 1
    for tier in rule["tiers"]:
        if set(tier) != {"from", "through", "unit_cents"}:
            raise PricingError("invalid_tier_fields")
        if integer(tier["from"], "tier_from", 1) != next_from:
            raise PricingError("license_tier_gap_or_overlap")
        next_from = integer(tier["through"], "tier_through", next_from) + 1
        integer(tier["unit_cents"], "unit_cents", 1)
    if next_from != maximum + 1:
        raise PricingError("license_tiers_do_not_cover_self_service")


def canonical_json(config: dict[str, Any]) -> str:
    validate(config)
    # Offer order does not change the commercial meaning of a catalog.
    normalized = {**config, "offers": sorted(config["offers"], key=lambda o: o["product_code"])}
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def pricing_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate(config)
    return config


def offer_for(config: dict[str, Any], product_code: str) -> dict[str, Any]:
    validate(config)
    for offer in config["offers"]:
        if offer["product_code"] == product_code:
            if not offer["active"]:
                raise PricingError("offer_inactive")
            return dict(offer)
    raise PricingError("unknown_product")


def purchase_snapshot(config: dict[str, Any], product_code: str) -> dict[str, Any]:
    offer = offer_for(config, product_code)
    if offer["billing_type"] != "one_time":
        raise PricingError("not_a_prepaid_offer")
    return {
        "product_code": product_code, "credits": offer["credits"],
        "total_cents": offer["total_cents"], "currency": config["currency"],
        "pricing_version": config["version"], "pricing_hash": pricing_hash(config),
    }


def unit_price_display(config: dict[str, Any], product_code: str) -> str:
    offer = offer_for(config, product_code)
    if offer["billing_type"] != "one_time":
        raise PricingError("unit_price_requires_prepaid_offer")
    value = Decimal(offer["total_cents"]) / Decimal(offer["credits"]) / Decimal(100)
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def organization_quote(config: dict[str, Any], clinicians: int) -> dict[str, Any]:
    validate(config)
    integer(clinicians, "clinicians")
    rule = config["organization_license"]
    enterprise = clinicians > rule["self_service_max"]
    total: int | None = None if enterprise else (rule["base_cents"] if clinicians else 0)
    if total is not None and clinicians:
        for tier in rule["tiers"]:
            count = max(0, min(clinicians, tier["through"]) - tier["from"] + 1)
            total += count * tier["unit_cents"]
    return {"clinical_seat_count": clinicians, "monthly_cents": total,
            "currency": config["currency"], "enterprise_required": enterprise,
            "pricing_version": config["version"], "pricing_hash": pricing_hash(config)}


def require_effective(status: str, valid_from: datetime | None,
                      valid_to: datetime | None, at: datetime) -> None:
    if at.tzinfo is None or (valid_from and valid_from.tzinfo is None) or (
        valid_to and valid_to.tzinfo is None
    ):
        raise PricingError("timezone_required")
    if status != "active" or valid_from is None or at < valid_from or (
        valid_to is not None and at >= valid_to
    ):
        raise PricingError("pricing_not_effective")


def public_catalog(config: dict[str, Any]) -> dict[str, Any]:
    """Payload publico de precos: somente pacotes pre-pagos ativos.

    Nenhum consumidor deve exibir preco antigo ou zero quando isto falhar:
    a falha e do chamador comunicar como indisponibilidade explicita.
    """
    validate(config)
    offers = [
        {
            "product_code": offer["product_code"],
            "name": offer["name"],
            "credits": offer["credits"],
            "total_cents": offer["total_cents"],
            "unit_price_display": unit_price_display(config, offer["product_code"]),
        }
        for offer in sorted(
            (o for o in config["offers"]
             if o["billing_type"] == "one_time" and o["active"]),
            key=lambda o: o["credits"])
    ]
    return {
        "pricing_version": config["version"],
        "pricing_hash": pricing_hash(config),
        "currency": config["currency"],
        "trial": {"credits": TRIAL_CREDITS, "days": TRIAL_DAYS},
        "offers": offers,
        "organization_license": {
            "self_service_max": config["organization_license"]["self_service_max"],
        },
    }
