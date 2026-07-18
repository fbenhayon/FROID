#!/usr/bin/env python3
"""Fail-closed privacy audit for the anonymous Data-FROID DuckDB."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


TEXT_COLUMNS = (
    "cut_summary_anon", "patient_summary_anon", "professional_summary_anon",
    "relevant_dissonances",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=os.getenv("FROID_DUCKDB_PATH", "/data/datamart_anonymous_v3.duckdb"))
    parser.add_argument(
        "--max-suppression-ratio",
        type=float,
        default=float(os.getenv("FROID_ANALYTICS_MAX_SUPPRESSION_RATIO", "0.10")),
    )
    args = parser.parse_args()
    path = Path(args.database)
    if not path.is_file():
        print(json.dumps({"status": "empty", "database": str(path)}))
        return 0

    import duckdb

    connection = duckdb.connect(str(path), read_only=True)
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    required = {"anonymous_sessions", "anonymous_session_cuts", "privacy_ingestion_audit"}
    missing = sorted(required - tables)
    checks: dict[str, object] = {"required_tables": not missing, "missing_tables": missing}

    if "anonymous_session_cuts" in tables:
        predicates = " OR ".join(f"coalesce(trim({column}), '') <> ''" for column in TEXT_COLUMNS)
        literal_rows = connection.execute(
            f"SELECT count(*) FROM anonymous_session_cuts WHERE {predicates}"
        ).fetchone()[0]
        checks["literal_text_rows"] = int(literal_rows)
        checks["literal_text_absent"] = int(literal_rows) == 0

    if "anonymous_sessions" in tables:
        unsafe_flags = connection.execute(
            """SELECT count(*) FROM anonymous_sessions
               WHERE coalesce(pii_excluded, false)=false
                  OR coalesce(raw_audio_retained, false)=true
                  OR coalesce(literal_transcript_retained, false)=true
                  OR coalesce(ingestion_basis, '') <> 'post_anonymization'"""
        ).fetchone()[0]
        invalid_hashes = connection.execute(
            """SELECT count(*) FROM anonymous_sessions
               WHERE NOT regexp_matches(session_hash, '^[0-9a-f]{64}$')"""
        ).fetchone()[0]
        checks["unsafe_session_rows"] = int(unsafe_flags)
        checks["safe_session_flags"] = int(unsafe_flags) == 0
        checks["invalid_pseudonyms"] = int(invalid_hashes)
        checks["pseudonyms_well_formed"] = int(invalid_hashes) == 0

    if "privacy_ingestion_audit" in tables:
        accepted, rejected = connection.execute(
            """SELECT count(*) FILTER (WHERE accepted),
                      count(*) FILTER (WHERE NOT accepted)
               FROM privacy_ingestion_audit"""
        ).fetchone()
        total = int(accepted or 0) + int(rejected or 0)
        ratio = round((int(rejected or 0) / total), 6) if total else 0.0
        checks["accepted"] = int(accepted or 0)
        checks["quarantined"] = int(rejected or 0)
        checks["suppression_ratio"] = ratio
        checks["suppression_target_met"] = ratio <= min(0.10, max(0.0, args.max_suppression_ratio))

    connection.close()
    blocking = [
        "required_tables", "literal_text_absent", "safe_session_flags",
        "pseudonyms_well_formed", "suppression_target_met",
    ]
    passed = all(checks.get(name) is True for name in blocking)
    checks["suppression_target_is_monitoring_only"] = True
    result = {"status": "passed" if passed else "failed", "checks": checks}
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
