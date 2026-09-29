"""A login/read must never apply an unapproved migration (Psique V2.1)."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from froid_schema import SchemaNotReady, runtime_migration_paths, verify_schema
from tenant_store import TenantStore

ROOT = Path(__file__).resolve().parents[1]


class ReadOnlyConnection:
    def __init__(self, versions):
        self.versions = versions
        self.statements = []

    def execute(self, sql, parameters=None):
        self.statements.append(sql)
        if not sql.lstrip().startswith("SELECT "):
            raise AssertionError("schema verification attempted a write")
        self.last = sql
        return self

    def fetchone(self):
        return (self.versions is not None,)

    def fetchall(self):
        return [(v,) for v in self.versions]


class SchemaReadOnlyTests(unittest.TestCase):
    def store(self):
        return TenantStore("dual", "postgresql://unused", ROOT / "migrations/001_multitenant_foundation.sql")

    def test_empty_database_is_reported_without_bootstrapping(self):
        connection = ReadOnlyConnection(None)
        with self.assertRaises(SchemaNotReady) as caught:
            self.store().ensure_schema(connection)
        self.assertIn("001_multitenant_foundation", caught.exception.missing)
        self.assertEqual(len(connection.statements), 1)

    def test_missing_legacy_migration_is_visible_without_writes(self):
        versions = {p.stem for p in runtime_migration_paths(ROOT / "migrations")}
        versions.remove("005_wallet_activation_safety")
        with self.assertRaises(SchemaNotReady) as caught:
            self.store().ensure_schema(ReadOnlyConnection(versions))
        self.assertEqual(caught.exception.missing, ("005_wallet_activation_safety",))

    def test_v1_and_nr1_do_not_require_unactivated_v2(self):
        versions = {p.stem for p in runtime_migration_paths(ROOT / "migrations")}
        connection = ReadOnlyConnection(versions)
        self.store().ensure_schema(connection)
        self.assertNotIn("035_psique_v2_pricing", versions)
        self.assertIn("034_anonimato_apos_o_fechamento", versions)

    def test_v2_reader_must_require_its_own_schema(self):
        with self.assertRaises(SchemaNotReady):
            verify_schema(ReadOnlyConnection(set()), {"035_psique_v2_pricing"})

    def test_environment_cannot_reenable_implicit_migrations(self):
        with (
            patch.dict(os.environ, {"FROID_AUTO_APPLY_MIGRATIONS": "true"}),
            self.assertRaisesRegex(ValueError, "must be false"),
        ):
            TenantStore.from_env()

    def test_absent_flag_does_not_enable_implicit_migrations(self):
        with patch.dict(os.environ, {"FROID_PERSISTENCE_MODE": "legacy"}, clear=True):
            self.assertFalse(TenantStore.from_env().enabled)

    def test_compose_cannot_expand_an_environment_override_to_true(self):
        compose = (ROOT.parent / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("- FROID_AUTO_APPLY_MIGRATIONS=false", compose)
        self.assertNotIn("${FROID_AUTO_APPLY_MIGRATIONS", compose)


if __name__ == "__main__":
    unittest.main()
