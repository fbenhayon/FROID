"""Explicit, audited migration command. Default action is a read-only plan.

Uses only FROID_MIGRATION_DATABASE_URL, never application/runtime credentials
implicitly. --apply and --confirm-database are both mandatory for writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from froid_schema import migration_paths, recorded_versions


def plan(connection: Any, directory: Path, through: str) -> list[dict[str, Any]]:
    paths = migration_paths(directory)
    if through not in {p.stem for p in paths}:
        raise ValueError("unknown_target_migration")
    applied = recorded_versions(connection)
    return [{
        "version": p.stem,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "applied": p.stem in applied,
    } for p in paths if p.stem <= through]


def apply(connection: Any, directory: Path, through: str,
          confirm_database: str) -> list[str]:
    if not connection.autocommit:
        raise ValueError("migration_runner_requires_autocommit_connection")
    database = connection.execute("SELECT current_database()").fetchone()[0]
    if not confirm_database or database != confirm_database:
        raise ValueError("database_confirmation_mismatch")
    # Validate the target before even creating the operational audit table.
    plan(connection, directory, through)
    lock_id = 7_346_643_004  # Same lock as the historical migration runner.
    connection.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
    completed: list[str] = []
    try:
        connection.execute("""CREATE TABLE IF NOT EXISTS schema_migration_execution_log (
            id uuid PRIMARY KEY, version text NOT NULL, sha256 char(64) NOT NULL,
            actor text NOT NULL DEFAULT current_user,
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz, status text NOT NULL
                CHECK (status IN ('running','applied','failed')),
            error_class text
        )""")
        connection.execute(
            "REVOKE ALL ON schema_migration_execution_log FROM PUBLIC"
        )
        for item in plan(connection, directory, through):
            if item["applied"]:
                # A checksum is evidence of what was executed, never fabricated
                # for pre-existing V1 migrations without an execution record.
                previous = connection.execute(
                    "SELECT sha256 FROM schema_migration_execution_log "
                    "WHERE version=%s AND status='applied' ORDER BY started_at DESC LIMIT 1",
                    (item["version"],),
                ).fetchone()
                if previous and previous[0].strip() != item["sha256"]:
                    raise RuntimeError("applied_migration_checksum_mismatch")
                continue
            run_id = uuid.uuid4()
            connection.execute(
                "INSERT INTO schema_migration_execution_log(id,version,sha256,status) "
                "VALUES(%s,%s,%s,'running')",
                (run_id, item["version"], item["sha256"]),
            )
            try:
                path = directory / (item["version"] + ".sql")
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != item["sha256"]:
                    raise RuntimeError("migration_changed_after_plan")
                connection.execute(content.decode("utf-8"))
                if item["version"] not in recorded_versions(connection):
                    raise RuntimeError("migration_did_not_register_version")
                connection.execute(
                    "UPDATE schema_migration_execution_log SET status='applied', "
                    "finished_at=now() WHERE id=%s", (run_id,),
                )
                completed.append(item["version"])
            except Exception as exc:
                connection.execute("ROLLBACK")
                connection.execute(
                    "UPDATE schema_migration_execution_log SET status='failed', "
                    "finished_at=now(),error_class=%s WHERE id=%s",
                    (type(exc).__name__, run_id),
                )
                raise
    finally:
        connection.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
    return completed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True, help="Exact last migration stem")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", default="")
    args = parser.parse_args()
    dsn = os.environ.get("FROID_MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        parser.error("FROID_MIGRATION_DATABASE_URL is required; credentials are not CLI arguments")
    if args.apply and not args.confirm_database:
        parser.error("--apply requires --confirm-database")
    try:
        import psycopg
        options = "" if args.apply else "-c default_transaction_read_only=on"
        with psycopg.connect(dsn, autocommit=True, options=options,
                             connect_timeout=10) as conn:
            result = (apply(conn, SERVER_DIR / "migrations", args.through,
                            args.confirm_database) if args.apply else
                      plan(conn, SERVER_DIR / "migrations", args.through))
        print(json.dumps({"action": "apply" if args.apply else "plan", "result": result}))
        return 0
    except Exception as exc:  # noqa: BLE001 -- sanitize the CLI boundary; never print credentials
        # Database/HTTP exception messages can contain credentials or payloads.
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
