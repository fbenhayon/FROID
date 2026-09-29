"""Create/verify the TEST license Price, homologate tiers, register mapping.

--create-objects: creates the FROID_ORG_LICENSE Product and the monthly BRL
graduated Price in the TEST account, idempotently (an existing Price with the
lookup_key is reused, never duplicated).
--homolog: previews the first invoice for every checklist boundary quantity
and compares the Stripe total with the backend formula; divergence fails.
--register: registers the immutable mapping in the confirmed disposable DB.

Never touches LIVE, never prints a secret, never deletes or archives objects.
"""

import argparse
import json
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import psique_pricing
from psique_billing import StripeTestClient
from psique_catalog_store import license_expected_tiers, register_license_test_mapping

LOOKUP_KEY = "froid_psique_org_license_v2_1"
BOUNDARIES = (1, 2, 3, 5, 6, 10, 11, 20, 25, 26, 30, 50, 51, 100, 101, 200)


def find_price(client):
    listing = client._request(
        "GET", f"/v1/prices?lookup_keys[]={LOOKUP_KEY}&expand[]=data.tiers")
    data = listing.get("data") or []
    return data[0] if data else None


def create_objects(client, config):
    price = find_price(client)
    metadata = {
        "froid_product": "psique", "family": "psique_license",
        "product_code": "FROID_ORG_LICENSE",
        "pricing_version": config["version"],
        "pricing_hash": psique_pricing.pricing_hash(config),
    }
    if price is not None:
        return price, False
    fields = [("name", "FROID Psique - Licenca Organizacional")]
    fields += [(f"metadata[{k}]", v) for k, v in metadata.items()]
    product = client._request("POST", "/v1/products", fields)
    fields = [
        ("product", product["id"]), ("currency", config["currency"]),
        ("recurring[interval]", "month"), ("billing_scheme", "tiered"),
        ("tiers_mode", "graduated"), ("lookup_key", LOOKUP_KEY),
        ("expand[]", "tiers"),
    ]
    fields += [(f"metadata[{k}]", v) for k, v in metadata.items()]
    for index, tier in enumerate(license_expected_tiers(config)):
        fields.append((f"tiers[{index}][up_to]",
                       "inf" if tier["up_to"] is None else str(tier["up_to"])))
        fields.append((f"tiers[{index}][unit_amount]", str(tier["unit_amount"])))
        if tier["flat_amount"]:
            fields.append((f"tiers[{index}][flat_amount]", str(tier["flat_amount"])))
    price = client._request("POST", "/v1/prices", fields)
    return price, True


def homolog(client, config, price_id):
    customer = client._request("POST", "/v1/customers",
                               [("description", "FROID Psique V2 QA homolog licenca")])
    failures = []
    rows = []
    for quantity in BOUNDARIES:
        expected = psique_pricing.organization_quote(config, quantity)["monthly_cents"]
        preview = client.preview_license_invoice(
            customer_id=customer["id"], price_id=price_id, quantity=quantity)
        got = preview.get("total")
        rows.append((quantity, expected, got))
        if got != expected:
            failures.append((quantity, expected, got))
    return rows, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-objects", action="store_true")
    parser.add_argument("--homolog", action="store_true")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--confirm-database", default="")
    parser.add_argument("--actor", default="")
    args = parser.parse_args()
    try:
        secret = os.environ.get("FROID_PSIQUE_STRIPE_TEST_SECRET_KEY", "")
        if not secret:
            parser.error("FROID_PSIQUE_STRIPE_TEST_SECRET_KEY is required")
        client = StripeTestClient(secret)
        account = client.account()["id"]
        config = psique_pricing.load_config()
        result = {"account": account, "version": config["version"], "lookup_key": LOOKUP_KEY}

        price = None
        if args.create_objects:
            price, created = create_objects(client, config)
            result["price_id"] = price["id"]
            result["price_created"] = created
        if price is None and (args.homolog or args.register):
            price = find_price(client)
            result["price_id"] = price["id"] if price else None
        if (args.homolog or args.register) and price is None:
            raise ValueError("license_price_not_found_run_create_objects")
        assert price is not None or not (args.homolog or args.register)

        if args.homolog:
            assert price is not None
            rows, failures = homolog(client, config, price["id"])
            result["homolog"] = [{"quantity": q, "expected_cents": e, "stripe_cents": g}
                                 for q, e, g in rows]
            result["homolog_failures"] = len(failures)
            if failures:
                raise ValueError(f"tiered_preview_divergent:{failures[:3]}")

        if args.register:
            if not args.confirm_database.startswith("psique_v2_test_") or not args.actor.strip():
                parser.error("--register requires --confirm-database psique_v2_test_* and --actor")
            dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
            if not dsn:
                parser.error("FROID_PSIQUE_TEST_DATABASE_URL is required")
            assert price is not None
            product = client._request("GET", f"/v1/products/{price['product']}")
            import psycopg
            with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
                row = conn.execute("SELECT current_database()").fetchone()
                if row is None or row[0] != args.confirm_database:
                    raise ValueError("database_confirmation_mismatch")
                result["mapping_id"] = register_license_test_mapping(
                    conn, version=config["version"], account_id=account,
                    product=product, price=price, actor=args.actor,
                    lookup_key=LOOKUP_KEY)
        print(json.dumps(result))
        return 0
    except Exception as exc:  # noqa: BLE001 -- sanitize the CLI boundary; never print credentials
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__,
                          "detail": str(exc)[:200]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
