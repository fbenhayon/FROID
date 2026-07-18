from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_store import TenantStore  # noqa: E402


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, role, migrations):
        self.role = role
        self.migrations = migrations

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=None):
        normalized = " ".join(query.split())
        if "current_database()" in normalized:
            return Result([("froid",)])
        if "SELECT version FROM schema_migrations" in normalized:
            return Result([(migration,) for migration in self.migrations])
        if "relrowsecurity" in normalized:
            return Result([(9,)])
        if "pg_has_role" in normalized:
            return Result([(0,)])
        if "has_function_privilege" in normalized:
            return Result([(True,)])
        raise AssertionError(f"unexpected readiness query: {normalized}")


class ReadyStore(TenantStore):
    def __init__(self, *, runtime_url="postgresql://runtime"):
        super().__init__(
            mode="dual",
            database_url="postgresql://owner",
            runtime_database_url=runtime_url,
            migration_path=SERVER_DIR / "migrations" / "001_multitenant_foundation.sql",
        )
        self.migrations = {
            path.stem for path in (SERVER_DIR / "migrations").glob("*.sql")
        }

    def _connect(self, *, runtime=False):
        return Connection("runtime" if runtime else "owner", self.migrations)


class Phase4ReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

    def test_legacy_mode_remains_ready_without_postgres(self):
        store = TenantStore("legacy", "", SERVER_DIR / "missing.sql")
        result = store.readiness()
        self.assertTrue(result["ready"])
        self.assertTrue(result["checks"]["legacy_source_available"])

    def test_dual_mode_requires_restricted_runtime_connection(self):
        result = ReadyStore(runtime_url="").readiness()
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["runtime_database_configured"])

    def test_dual_mode_passes_complete_non_owner_gate(self):
        result = ReadyStore().readiness()
        self.assertTrue(result["ready"])
        self.assertTrue(result["checks"]["all_migrations_applied"])
        self.assertTrue(result["checks"]["rls_enabled_on_tenant_tables"])
        self.assertTrue(result["checks"]["runtime_is_not_table_owner"])

    def test_missing_migration_fails_closed(self):
        store = ReadyStore()
        store.migrations.remove("005_wallet_activation_safety")
        result = store.readiness()
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["all_migrations_applied"])

    def test_application_readiness_requires_encryption(self):
        self.assertIn("clinical_record_encryption_configured", self.main_source)
        self.assertIn("google_token_encryption_configured", self.main_source)
        self.assertIn("if not all(security_checks.values())", self.main_source)


if __name__ == "__main__":
    unittest.main()
