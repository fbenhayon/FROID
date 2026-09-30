"""Schema verification has no write path; migrations require an explicit command.

Psique V2.1, 29/09/2026: ensure_schema used to run SQL during ordinary reads.
Shipping a migration could change production on a login. Verification must
remain independent from the operational migration runner.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

PSIQUE_V2_VERSIONS = frozenset({
    "035_psique_v2_pricing",
    "036_psique_v2_purchases",
    "037_psique_trial_credit_state",
    "038_psique_credit_commands",
    "039_psique_stripe_test_checkout",
    "040_psique_org_license_test",
    "041_psique_financial_lookup_indexes",
    "042_psique_rbac_v2",
    "043_psique_rbac_v2_complement",
    "044_psique_org_scheduling",
})


class SchemaNotReady(RuntimeError):
    def __init__(self, missing: Iterable[str]):
        self.missing = tuple(sorted(missing))
        super().__init__(
            "schema_migration_required: " + ", ".join(self.missing)
            + "; run the explicit migration command before enabling this feature"
        )


def migration_paths(directory: Path) -> list[Path]:
    paths = sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))
    if not paths:
        raise RuntimeError("migration_catalog_missing")
    return paths


def runtime_migration_paths(directory: Path) -> list[Path]:
    # V2 stays opt-in. Unknown migrations are not silently ignored.
    return [p for p in migration_paths(directory) if p.stem not in PSIQUE_V2_VERSIONS]


def recorded_versions(connection: Any) -> set[str]:
    exists = connection.execute(
        "SELECT to_regclass('public.schema_migrations') IS NOT NULL"
    ).fetchone()
    if not exists or not exists[0]:
        return set()
    return {row[0] for row in connection.execute(
        "SELECT version FROM schema_migrations"
    ).fetchall()}


def verify_schema(connection: Any, required: Iterable[str]) -> None:
    missing = set(required) - recorded_versions(connection)
    if missing:
        raise SchemaNotReady(missing)
