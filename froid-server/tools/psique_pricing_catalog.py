"""Inspect the blueprint or explicitly install a DRAFT pricing table.

Default target is a disposable test DB (psique_v2_test_*). The production
path exists since the multicurrency window (07/10/2026) and is opt-in by two
explicit signals: --producao plus --confirm-database said out loud, reading
FROID_PSIQUE_OPERACAO_DATABASE_URL (the same contract as the live Stripe
tool's --register). Until then the BRL table was installed by hand with
install_draft inside the container, which left no command in the repository.

No public activation, Checkout, credit grant or Stripe operation is available.
"""

import argparse
import json
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from psique_catalog_store import install_draft
from psique_pricing import CURRENCIES, load_config, pricing_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-draft", action="store_true")
    parser.add_argument("--confirm-database", default="")
    parser.add_argument("--actor", default="")
    parser.add_argument("--moeda", choices=CURRENCIES, default="brl",
                        help="tabela derivada da BRL (mesmos numeros): usd -> versao 2.1-usd")
    parser.add_argument("--producao", action="store_true",
                        help="instala no banco de operacao (FROID_PSIQUE_OPERACAO_DATABASE_URL), "
                             "com --confirm-database e --actor; sem isto, so psique_v2_test_*")
    args = parser.parse_args()
    try:
        config = load_config(currency=args.moeda)
        result = {"code": config["code"], "version": config["version"],
                  "currency": config["currency"],
                  "pricing_hash": pricing_hash(config), "status": "blueprint", "public": False}
        if args.install_draft:
            if args.producao:
                if not args.confirm_database.strip() or not args.actor.strip():
                    parser.error("--producao requires --confirm-database and --actor")
                dsn = os.environ.get("FROID_PSIQUE_OPERACAO_DATABASE_URL", "")
                if not dsn:
                    parser.error("FROID_PSIQUE_OPERACAO_DATABASE_URL is required")
            else:
                if not args.confirm_database.startswith("psique_v2_test_") or not args.actor.strip():
                    parser.error("Phase 1 requires --confirm-database psique_v2_test_* and --actor")
                dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
                if not dsn:
                    parser.error("FROID_PSIQUE_TEST_DATABASE_URL is required")
            import psycopg
            with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
                database_row = conn.execute("SELECT current_database()").fetchone()
                if database_row is None:
                    raise ValueError("database_identity_unavailable")
                actual = database_row[0]
                if actual != args.confirm_database:
                    raise ValueError("database_confirmation_mismatch")
                result["table_id"] = install_draft(conn, config, actor=args.actor)
                result["status"] = "draft"
        print(json.dumps(result))
        return 0
    except Exception as exc:  # noqa: BLE001 -- sanitize the CLI boundary; never print credentials
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
