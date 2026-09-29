"""Verify the six Stripe TEST objects against the catalog and register mappings.

Reads Products/Prices from the TEST account with GET only, validates amount,
currency, one_time, metadata and lookup_key against the installed catalog, and
registers the immutable mappings in an explicitly confirmed disposable test
database. It never creates, edits or archives Stripe objects, never touches
LIVE and never prints a secret.
"""

import argparse
import json
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from psique_billing import StripeTestClient
from psique_catalog_store import register_test_mapping
from psique_pricing import load_config

# The authorized Phase 2B objects. Divergence stops the run; it is reported,
# never silently corrected.
AUTHORIZED_OBJECTS = {
    "FROID_PRO_10": ("prod_VLl3bMw1tZJQuA", "price_1UL3XJAg9NSIrvBV3VTX3ybq", "froid_psique_pro_10_v2_1"),
    "FROID_PRO_25": ("prod_VLl4nNVvpxxcxc", "price_1UL3YkAg9NSIrvBV6IRjcdsj", "froid_psique_pro_25_v2_1"),
    "FROID_PRO_50": ("prod_VLl5GzlS0a3GpK", "price_1UL3ZOAg9NSIrvBVPwXMuaDn", "froid_psique_pro_50_v2_1"),
    "FROID_PRO_100": ("prod_VLl6eS8CVPTMvf", "price_1UL3a2Ag9NSIrvBV5s7lNuaW", "froid_psique_pro_100_v2_1"),
    "FROID_PRO_200": ("prod_VLl6H6AGS2lgrl", "price_1UL3alAg9NSIrvBVzKmjHPEc", "froid_psique_pro_200_v2_1"),
    "FROID_PRO_500": ("prod_VLl89PtmMJFb9z", "price_1UL3bwAg9NSIrvBV8b47kl4L", "froid_psique_pro_500_v2_1"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
        config = load_config()
        retrieved = {}
        for code, (product_id, price_id, lookup_key) in AUTHORIZED_OBJECTS.items():
            price = client._request("GET", f"/v1/prices/{price_id}")
            product = client._request("GET", f"/v1/products/{product_id}")
            if price.get("lookup_key") != lookup_key:
                raise ValueError(f"lookup_key_divergent:{code}")
            retrieved[code] = (product, price, lookup_key)
        result = {"account": account, "version": config["version"],
                  "objects_verified": len(retrieved), "registered": 0}
        if args.register:
            if not args.confirm_database.startswith("psique_v2_test_") or not args.actor.strip():
                parser.error("--register requires --confirm-database psique_v2_test_* and --actor")
            dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
            if not dsn:
                parser.error("FROID_PSIQUE_TEST_DATABASE_URL is required")
            import psycopg
            with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
                row = conn.execute("SELECT current_database()").fetchone()
                if row is None or row[0] != args.confirm_database:
                    raise ValueError("database_confirmation_mismatch")
                for code, (product, price, lookup_key) in retrieved.items():
                    register_test_mapping(
                        conn, version=config["version"], product_code=code,
                        account_id=account, product=product, price=price,
                        actor=args.actor, lookup_key=lookup_key)
                    result["registered"] += 1
        print(json.dumps(result))
        return 0
    except Exception as exc:  # noqa: BLE001 -- sanitize the CLI boundary; never print credentials
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
