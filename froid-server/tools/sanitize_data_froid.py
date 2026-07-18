#!/usr/bin/env python3
"""Remove pre-v3 Data-FROID rows; identified clinical sources remain untouched."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=os.getenv("FROID_DUCKDB_PATH", "/data/datamart_anonymous.duckdb"))
    parser.add_argument("--backup-dir", default="/data/data-froid-backups")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    database = Path(args.database)
    if not database.is_file():
        print(json.dumps({"status": "empty", "database": str(database)}))
        return 0

    import duckdb

    connection = duckdb.connect(str(database), read_only=True)
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    legacy_count = 0
    if "anonymous_sessions" in tables:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('anonymous_sessions')").fetchall()}
        legacy_count = (
            connection.execute(
                "SELECT count(*) FROM anonymous_sessions WHERE coalesce(ingestion_basis, '') <> 'post_anonymization'"
            ).fetchone()[0]
            if "ingestion_basis" in columns
            else connection.execute("SELECT count(*) FROM anonymous_sessions").fetchone()[0]
        )
    connection.close()
    preview = {"legacy_rows": int(legacy_count), "apply": bool(args.apply)}
    if not args.apply or not legacy_count:
        print(json.dumps({"status": "preview", **preview}))
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"data-froid-before-privacy-v3-{stamp}.duckdb"
    shutil.copy2(database, backup_path)

    connection = duckdb.connect(str(database), read_only=False)
    connection.execute("BEGIN")
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('anonymous_sessions')").fetchall()}
        if "anonymous_session_cuts" in tables:
            if "ingestion_basis" in columns:
                connection.execute(
                    """DELETE FROM anonymous_session_cuts
                       WHERE session_hash IN (
                           SELECT session_hash FROM anonymous_sessions
                           WHERE coalesce(ingestion_basis, '') <> 'post_anonymization'
                       )"""
                )
            else:
                connection.execute("DELETE FROM anonymous_session_cuts")
        if "ingestion_basis" in columns:
            connection.execute("DELETE FROM anonymous_sessions WHERE coalesce(ingestion_basis, '') <> 'post_anonymization'")
        else:
            connection.execute("DELETE FROM anonymous_sessions")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
    print(json.dumps({"status": "sanitized", **preview, "backup": str(backup_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
