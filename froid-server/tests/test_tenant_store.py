from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_store import (  # noqa: E402
    TenantStore,
    _migration_is_applied,
    normalize_email,
    stable_uuid,
)


class _Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return (self.value,)


class _MigrationConnection:
    def __init__(self, *, table_exists: bool, recorded: bool):
        self.table_exists = table_exists
        self.recorded = recorded
        self.calls = []

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        if "to_regclass" in sql:
            return _Result(self.table_exists)
        return _Result(self.recorded)


class TenantStoreUnitTests(unittest.TestCase):
    def test_stable_uuid_is_deterministic_and_scoped_by_kind(self):
        first = stable_uuid("patient", "org-1", "Patient-1")
        self.assertEqual(first, stable_uuid("patient", "ORG-1", "patient-1"))
        self.assertNotEqual(first, stable_uuid("report", "org-1", "patient-1"))

    def test_normalize_email(self):
        self.assertEqual(normalize_email("  Pro@FROID.COM "), "pro@froid.com")

    def test_legacy_mode_never_requires_database(self):
        store = TenantStore("legacy", "", SERVER_DIR / "missing.sql")
        self.assertFalse(store.enabled)
        self.assertEqual(store.sync_all({}, {}), {})

    def test_dual_mode_requires_database_url(self):
        with self.assertRaises(ValueError):
            TenantStore("dual", "", SERVER_DIR / "missing.sql")

    def test_phase_one_rejects_unsafe_cutover_mode(self):
        with self.assertRaises(ValueError):
            TenantStore("postgres", "postgresql://unused", SERVER_DIR / "missing.sql")

    def test_migration_lookup_handles_a_clean_database(self):
        connection = _MigrationConnection(table_exists=False, recorded=False)
        self.assertFalse(_migration_is_applied(connection, "001_foundation"))
        self.assertEqual(len(connection.calls), 1)

    def test_recorded_migration_is_not_reapplied(self):
        connection = _MigrationConnection(table_exists=True, recorded=True)
        self.assertTrue(_migration_is_applied(connection, "004_wallet"))
        self.assertEqual(connection.calls[1][1], ("004_wallet",))


if __name__ == "__main__":
    unittest.main()
