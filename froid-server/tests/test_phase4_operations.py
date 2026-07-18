from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Phase4OperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backup = (ROOT / "ops" / "backup_postgres.sh").read_text(encoding="utf-8")
        cls.restore = (ROOT / "ops" / "verify_postgres_restore.sh").read_text(
            encoding="utf-8"
        )

    def test_backup_is_atomic_and_validated_before_publish(self):
        self.assertIn(".partial", self.backup)
        self.assertIn("pg_restore --list", self.backup)
        self.assertLess(self.backup.index("pg_restore --list"), self.backup.index('mv "$temporary"'))
        self.assertIn("sha256sum", self.backup)
        self.assertIn(
            '(cd backups/postgres && sha256sum "$backup_name"',
            self.backup,
        )
        self.assertIn('test -s "backups/postgres/$backup_name"\n', self.backup)
        self.assertIn('test -s "backups/postgres/$backup_name.sha256"', self.backup)

    def test_restore_never_targets_production_database(self):
        self.assertIn("froid_restore_verify_", self.restore)
        self.assertIn("trap cleanup EXIT INT TERM", self.restore)
        self.assertNotIn('-d "$POSTGRES_DB"', self.restore)

    def test_restore_checks_migrations_rls_and_stops_on_error(self):
        self.assertIn("--exit-on-error", self.restore)
        self.assertIn("migration_count <> 7", self.restore)
        self.assertIn("007_multitenant_security_hardening", self.restore)
        self.assertIn("rls_count <> 9", self.restore)
        self.assertIn("sha256sum -c", self.restore)


if __name__ == "__main__":
    unittest.main()
