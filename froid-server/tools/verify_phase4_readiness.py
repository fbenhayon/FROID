"""Fail-closed PostgreSQL readiness gate for FROID Phase 4.

The command prints only boolean infrastructure checks and never clinical data.
It does not run migrations or mutate the database.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_store import TenantStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("FROID_DATABASE_URL", ""),
        help="Owner/migration DSN; prefer FROID_DATABASE_URL",
    )
    parser.add_argument(
        "--runtime-database-url",
        default=os.getenv("FROID_RUNTIME_DATABASE_URL", ""),
        help="Restricted runtime DSN; prefer FROID_RUNTIME_DATABASE_URL",
    )
    args = parser.parse_args()
    if not args.database_url or not args.runtime_database_url:
        parser.error("owner and runtime PostgreSQL URLs are required")

    store = TenantStore(
        mode="dual",
        database_url=args.database_url,
        runtime_database_url=args.runtime_database_url,
        migration_path=SERVER_DIR / "migrations" / "001_multitenant_foundation.sql",
    )
    result = store.readiness()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
