"""Idempotent Phase 1 backfill from FROID JSON files to PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_store import TenantStore, read_json_object  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--identity",
        default=os.getenv("FROID_IDENTITY_STATE_PATH", "/data/identity_state.json"),
        help="Path to identity_state.json",
    )
    parser.add_argument(
        "--reports",
        default=os.getenv("FROID_SESSION_REPORTS_PATH", "/data/session_reports.json"),
        help="Path to session_reports.json",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("FROID_DATABASE_URL", ""),
        help="PostgreSQL DSN (prefer FROID_DATABASE_URL to avoid shell history)",
    )
    args = parser.parse_args()

    if not args.database_url:
        parser.error("FROID_DATABASE_URL or --database-url is required")

    store = TenantStore(
        mode="dual",
        database_url=args.database_url,
        migration_path=SERVER_DIR / "migrations" / "001_multitenant_foundation.sql",
    )
    counters = store.sync_all(
        read_json_object(args.identity),
        read_json_object(args.reports),
    )
    print(json.dumps({"status": "completed", "counters": counters}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
