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
                          actor: str, lookup_key: str | None = None,
                          live: bool = False) -> str:
    """Validate already retrieved Stripe objects; this function makes no Stripe calls.

    Caller is an explicit operator/test, not an HTTP/frontend input. A later
    Stripe integration must retrieve these objects authenticated to account_id.
    O padrao continua TEST; live=True e a decisao explicita da Fase 6 e exige
    objetos cujo livemode confere (migration 046 destrava o banco).
    """
    verify_schema(connection, {"035_psique_v2_pricing", "036_psique_v2_purchases"})
    if lookup_key is not None:
        # Phase 2B checkout resolves mappings by offer+account and audits the
        # lookup_key; registering one requires the 039 columns and the exact
        # key Stripe returned, never a locally invented value.
        verify_schema(connection, {"039_psique_stripe_test_checkout"})
        if price.get("lookup_key") != lookup_key:
            raise PricingError("stripe_lookup_key_does_not_match")
    config = read_catalog(connection, version=version, include_draft=True)
    offer = offer_for(config, product_code)
    if not actor.strip() or not account_id.startswith("acct_"):
        raise PricingError("mapping_actor_and_account_required")
    expected = {
        "froid_product": "psique", "family": "psique_credits",
        "product_code": product_code, "credits": str(offer["credits"]),
        "pricing_version": version, "pricing_hash": pricing_hash(config),
    }
    if product.get("livemode") is not live or price.get("livemode") is not live:
        raise PricingError("stripe_object_mode_mismatch" if live else "phase1_test_only")
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
        if lookup_key is None:
            connection.execute(
                """INSERT INTO psique_stripe_price_mappings
                   (offer_id,pricing_table_id,stripe_account_id,livemode,stripe_product_id,
                    stripe_price_id,verified_at,verified_by)
                   VALUES(%s,%s,%s,%s,%s,%s,now(),%s)
                   ON CONFLICT(offer_id,stripe_account_id,livemode) DO NOTHING""",
                (row[0], row[1], account_id, live, product["id"], price["id"], actor),
            )
        else:
            connection.execute(
                """INSERT INTO psique_stripe_price_mappings
                   (offer_id,pricing_table_id,stripe_account_id,livemode,stripe_product_id,
                    stripe_price_id,verified_at,verified_by,lookup_key,active)
                   VALUES(%s,%s,%s,%s,%s,%s,now(),%s,%s,true)
                   ON CONFLICT(offer_id,stripe_account_id,livemode) DO NOTHING""",
                (row[0], row[1], account_id, live, product["id"], price["id"], actor, lookup_key),
            )
        columns = "id,stripe_product_id,stripe_price_id"
        if lookup_key is not None:
            # The lookup_key column only exists from migration 039 on; the
            # legacy Phase 1 call keeps working against a through-036 schema.
            columns += ",lookup_key"
        mapping = connection.execute(
            f"""SELECT {columns} FROM psique_stripe_price_mappings
               WHERE offer_id=%s AND stripe_account_id=%s AND livemode=%s""",
            (row[0], account_id, live),
        ).fetchone()
        if mapping is None or mapping[1:3] != (product["id"], price["id"]):
            raise PricingError("existing_mapping_is_immutable")
        if lookup_key is not None and mapping[3] != lookup_key:
            raise PricingError("existing_mapping_is_immutable")
    return str(mapping[0])


def license_expected_tiers(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Stripe graduated tiers that reproduce the backend formula exactly."""
    rule = config["organization_license"]
    tiers: list[dict[str, Any]] = [{
        "up_to": rule["included_clinicians"],
        "flat_amount": rule["base_cents"], "unit_amount": 0,
    }]
    for tier in rule["tiers"]:
        tiers.append({"up_to": tier["through"], "flat_amount": None,
                      "unit_amount": tier["unit_cents"]})
    # Stripe requires an open last tier; the application refuses quantities
    # above self_service_max before any Stripe call (201+ is Enterprise).
    tiers[-1]["up_to"] = None
    return tiers


def register_license_test_mapping(connection: Any, *, version: str, account_id: str,
                                  product: dict[str, Any], price: dict[str, Any],
                                  actor: str, lookup_key: str,
                                  live: bool = False) -> str:
    """Validate the retrieved license objects and register the mapping.

    The price must be monthly, BRL, tiered/graduated, with tiers identical to
    the catalog rule (fetch it with expand[]=tiers). Divergence stops here.
    O padrao continua TEST; live=True exige objetos cujo livemode confere.
    """
    verify_schema(connection, {"035_psique_v2_pricing", "036_psique_v2_purchases",
                               "039_psique_stripe_test_checkout"})
    config = read_catalog(connection, version=version, include_draft=True)
    if not actor.strip() or not account_id.startswith("acct_"):
        raise PricingError("mapping_actor_and_account_required")
    if product.get("livemode") is not live or price.get("livemode") is not live:
        raise PricingError("stripe_object_mode_mismatch" if live
                           else "license_mapping_is_test_only")
    recurring = price.get("recurring") or {}
    if (product.get("active") is not True or price.get("active") is not True
        or price.get("product") not in (product.get("id"),)
        or price.get("currency") != config["currency"]
        or recurring.get("interval") != "month" or recurring.get("interval_count") != 1
        or price.get("billing_scheme") != "tiered" or price.get("tiers_mode") != "graduated"
        or price.get("lookup_key") != lookup_key):
        raise PricingError("stripe_license_price_shape_mismatch")
    expected = license_expected_tiers(config)
    actual = [{"up_to": tier.get("up_to"),
               "flat_amount": tier.get("flat_amount") or None,
               "unit_amount": tier.get("unit_amount") or 0}
              for tier in (price.get("tiers") or [])]
    normalized = [{"up_to": tier["up_to"],
                   "flat_amount": tier["flat_amount"] or None,
                   "unit_amount": tier["unit_amount"] or 0} for tier in expected]
    if actual != normalized:
        raise PricingError("stripe_license_tiers_do_not_match_backend")
    expected_meta = {"froid_product": "psique", "family": "psique_license",
                     "product_code": "FROID_ORG_LICENSE",
                     "pricing_version": version, "pricing_hash": pricing_hash(config)}
    for obj in (product, price):
        if any((obj.get("metadata") or {}).get(k) != v for k, v in expected_meta.items()):
            raise PricingError("stripe_license_metadata_mismatch")
    with connection.transaction():
        row = connection.execute(
            """SELECT offers.id,offers.pricing_table_id FROM psique_pricing_offers offers
               JOIN psique_pricing_tables parent ON parent.id=offers.pricing_table_id
               WHERE parent.code=%s AND parent.version=%s AND offers.product_code='FROID_ORG_LICENSE'""",
            (config["code"], version),
        ).fetchone()
        if row is None:
            raise PricingError("license_offer_missing_from_catalog")
        connection.execute(
            """INSERT INTO psique_stripe_price_mappings
               (offer_id,pricing_table_id,stripe_account_id,livemode,stripe_product_id,
                stripe_price_id,verified_at,verified_by,lookup_key,active)
               VALUES(%s,%s,%s,%s,%s,%s,now(),%s,%s,true)
               ON CONFLICT(offer_id,stripe_account_id,livemode) DO NOTHING""",
            (row[0], row[1], account_id, live, product["id"], price["id"], actor, lookup_key),
        )
        mapping = connection.execute(
            """SELECT id,stripe_product_id,stripe_price_id,lookup_key
               FROM psique_stripe_price_mappings
               WHERE offer_id=%s AND stripe_account_id=%s AND livemode=%s""",
            (row[0], account_id, live),
        ).fetchone()
        if mapping is None or mapping[1:] != (product["id"], price["id"], lookup_key):
            raise PricingError("existing_mapping_is_immutable")
    return str(mapping[0])
