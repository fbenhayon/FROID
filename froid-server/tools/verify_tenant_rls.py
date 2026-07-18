"""Verify FROID tenant isolation using a non-owner PostgreSQL role.

This command does not print patient, professional or clinical data. It expects
IDs from a controlled homologation fixture and exits non-zero on any RLS leak.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("FROID_RUNTIME_DATABASE_URL", ""),
        help="Runtime PostgreSQL DSN; prefer FROID_RUNTIME_DATABASE_URL",
    )
    parser.add_argument("--organization", required=True)
    parser.add_argument("--membership", required=True)
    parser.add_argument("--other-organization", required=True)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("FROID_RUNTIME_DATABASE_URL or --database-url is required")

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required for the RLS verification") from exc

    checks = {}
    with psycopg.connect(args.database_url, connect_timeout=10) as connection:
        with connection.transaction():
            connection.execute(
                "SELECT set_config('app.organization_id', %s, true)",
                (args.organization,),
            )
            connection.execute(
                "SELECT set_config('app.membership_id', %s, true)",
                (args.membership,),
            )
            owner_count = connection.execute(
                """
                SELECT count(*) FROM pg_class table_entry
                WHERE table_entry.relname IN (
                    'organizations', 'patients', 'session_reports',
                    'audit_events', 'organization_memberships',
                    'data_subject_requests', 'data_subject_request_events'
                )
                  AND pg_has_role(current_user, table_entry.relowner, 'MEMBER')
                """
            ).fetchone()[0]
            checks["runtime_is_not_table_owner"] = owner_count == 0

            own_visible = connection.execute(
                "SELECT count(*) FROM organizations WHERE id=%s",
                (args.organization,),
            ).fetchone()[0]
            checks["own_organization_visible"] = own_visible == 1

            other_visible = connection.execute(
                "SELECT count(*) FROM organizations WHERE id=%s",
                (args.other_organization,),
            ).fetchone()[0]
            checks["other_organization_hidden"] = other_visible == 0

            cross_patients = connection.execute(
                "SELECT count(*) FROM patients WHERE organization_id=%s",
                (args.other_organization,),
            ).fetchone()[0]
            checks["cross_organization_patients_hidden"] = cross_patients == 0

            cross_reports = connection.execute(
                "SELECT count(*) FROM session_reports WHERE organization_id=%s",
                (args.other_organization,),
            ).fetchone()[0]
            checks["cross_organization_reports_hidden"] = cross_reports == 0

            cross_privacy_requests = connection.execute(
                "SELECT count(*) FROM data_subject_requests WHERE organization_id=%s",
                (args.other_organization,),
            ).fetchone()[0]
            checks["cross_organization_privacy_requests_hidden"] = cross_privacy_requests == 0

            connection.execute(
                "SELECT froid_has_role(ARRAY['owner','administrator','supervisor','professional','auditor']::text[])"
            ).fetchone()
            checks["role_function_executable"] = True

    passed = all(checks.values())
    print(json.dumps({"status": "passed" if passed else "failed", "checks": checks}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
