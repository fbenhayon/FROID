"""Controlled Phase 1 catalog storage; no billing, trial, credits or public routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from froid_schema import verify_schema
from psique_pricing import (
    PricingError,
    canonical_json,
    offer_for,
    pricing_hash,
    require_effective,
    validate,
)


def install_draft(connection: Any, config: dict[str, Any], *, actor: str) -> str:
    """Explicitly install one immutable version, idempotently and atomically."""
    verify_schema(connection, {"035_psique_v2_pricing"})
    if not actor.strip():
        raise PricingError("catalog_actor_required")
    payload = canonical_json(config)
    digest = pricing_hash(config)
    with connection.transaction():
        connection.execute(
            """INSERT INTO psique_pricing_tables
               (code,version,currency,canonical_json,config_hash,created_by)
               VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(code,version) DO NOTHING""",
            (config["code"], config["version"], config["currency"], payload, digest, actor),
        )
        row = connection.execute(
            "SELECT id,canonical_json,config_hash FROM psique_pricing_tables "
            "WHERE code=%s AND version=%s FOR UPDATE",
            (config["code"], config["version"]),
        ).fetchone()
        if row is None or row[1] != payload or row[2] != digest:
            raise PricingError("pricing_version_already_has_different_content")
        table_id = row[0]
        for offer in config["offers"]:
            connection.execute(
                """INSERT INTO psique_pricing_offers
                   (pricing_table_id,product_code,name,credits,total_cents,billing_type,active,public)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(pricing_table_id,product_code) DO NOTHING""",
                (table_id, offer["product_code"], offer["name"], offer["credits"],
                 offer["total_cents"], offer["billing_type"], offer["active"], offer["public"]),
            )
        read_catalog(connection, version=config["version"], include_draft=True)
    return str(table_id)


def read_catalog(connection: Any, *, version: str,
                 include_draft: bool = False, at: datetime | None = None) -> dict[str, Any]:
    verify_schema(connection, {"035_psique_v2_pricing"})
    row = connection.execute(
        """SELECT id,canonical_json,config_hash,status,valid_from,valid_to
           FROM psique_pricing_tables WHERE code='FROID_PSIQUE_V2' AND version=%s""",
        (version,),
    ).fetchone()
    if row is None:
        raise PricingError("pricing_version_not_found")
    config = json.loads(row[1])
    validate(config)
    if canonical_json(config) != row[1] or pricing_hash(config) != row[2]:
        raise PricingError("pricing_hash_mismatch")
    offers = connection.execute(
        """SELECT product_code,name,credits,total_cents,billing_type,active,public
           FROM psique_pricing_offers WHERE pricing_table_id=%s ORDER BY product_code""",
        (row[0],),
    ).fetchall()
    keys = ("product_code", "name", "credits", "total_cents", "billing_type", "active", "public")
    stored_offers = [dict(zip(keys, values)) for values in offers]
    if stored_offers != sorted(config["offers"], key=lambda o: o["product_code"]):
        raise PricingError("pricing_offers_mismatch")
    if not (include_draft and row[3] == "draft"):
        require_effective(row[3], row[4], row[5], at or datetime.now(timezone.utc))
    return config


def register_test_mapping(connection: Any, *, version: str, product_code: str,
                          account_id: str, product: dict[str, Any], price: dict[str, Any],
                          actor: str) -> str:
    """Validate already retrieved TEST objects; this function makes no Stripe calls.

    Caller is an explicit operator/test, not an HTTP/frontend input. A later
    Stripe integration must retrieve these objects authenticated to account_id.
    No public permission or live mapping is supplied by this phase.
    """
    verify_schema(connection, {"035_psique_v2_pricing", "036_psique_v2_purchases"})
    config = read_catalog(connection, version=version, include_draft=True)
    offer = offer_for(config, product_code)
    if not actor.strip() or not account_id.startswith("acct_"):
        raise PricingError("mapping_actor_and_account_required")
    expected = {
        "froid_product": "psique", "family": "psique_credits",
        "product_code": product_code, "credits": str(offer["credits"]),
        "pricing_version": version, "pricing_hash": pricing_hash(config),
    }
    if product.get("livemode") is not False or price.get("livemode") is not False:
        raise PricingError("phase1_test_only")
    if (offer["billing_type"] != "one_time" or price.get("type") != "one_time"
        or price.get("recurring") is not None or price.get("billing_scheme") != "per_unit"
        or product.get("active") is not True or price.get("active") is not True
        or price.get("product") != product.get("id")
        or price.get("currency") != config["currency"]
        or type(price.get("unit_amount")) is not int
        or price["unit_amount"] != offer["total_cents"]):
        raise PricingError("stripe_price_does_not_match_offer")
    for obj in (product, price):
        if any((obj.get("metadata") or {}).get(k) != v for k, v in expected.items()):
            raise PricingError("stripe_metadata_does_not_match_offer")
    with connection.transaction():
        row = connection.execute(
            """SELECT offers.id,offers.pricing_table_id FROM psique_pricing_offers offers
               JOIN psique_pricing_tables parent ON parent.id=offers.pricing_table_id
               WHERE parent.code=%s AND parent.version=%s AND offers.product_code=%s""",
            (config["code"], version, product_code),
        ).fetchone()
        connection.execute(
            """INSERT INTO psique_stripe_price_mappings
               (offer_id,pricing_table_id,stripe_account_id,livemode,stripe_product_id,
                stripe_price_id,verified_at,verified_by)
               VALUES(%s,%s,%s,false,%s,%s,now(),%s)
               ON CONFLICT(offer_id,stripe_account_id,livemode) DO NOTHING""",
            (row[0], row[1], account_id, product["id"], price["id"], actor),
        )
        mapping = connection.execute(
            """SELECT id,stripe_product_id,stripe_price_id FROM psique_stripe_price_mappings
               WHERE offer_id=%s AND stripe_account_id=%s AND livemode=false""",
            (row[0], account_id),
        ).fetchone()
        if mapping is None or mapping[1:] != (product["id"], price["id"]):
            raise PricingError("existing_mapping_is_immutable")
    return str(mapping[0])
