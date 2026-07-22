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
        cls.full_backup = (ROOT / "ops" / "backup_froid_state.sh").read_text(
            encoding="utf-8"
        )
        cls.full_verify = (ROOT / "ops" / "verify_froid_state_backup.sh").read_text(
            encoding="utf-8"
        )
        cls.compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

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
        self.assertIn("migration_count <> 9", self.restore)
        self.assertIn("007_multitenant_security_hardening", self.restore)
        self.assertIn("008_data_subject_rights", self.restore)
        self.assertIn("009_legal_acceptance_ledger", self.restore)
        self.assertIn("rls_count <> 12", self.restore)
        self.assertIn('actual_sha256=$(sha256sum "$backup_path"', self.restore)
        self.assertIn("/root/froid-backups/*", self.restore)
        self.assertIn("froid-homologacao.dump", self.restore)

    def test_full_state_backup_is_encrypted_authenticated_and_self_verified(self):
        self.assertIn("FROID_BACKUP_ENCRYPTION_PASSPHRASE", self.full_backup)
        self.assertIn("FROID_BACKUP_INTEGRITY_KEY", self.full_backup)
        self.assertIn("-aes-256-cbc -pbkdf2", self.full_backup)
        self.assertIn("verify_froid_state_backup.sh", self.full_backup)
        self.assertIn("postgres-legacy.dump", self.full_backup)
        self.assertIn("postgres-tenant.dump", self.full_backup)
        self.assertEqual(self.full_verify.count("pg_restore --list"), 2)
        self.assertIn("application-data.tar.gz", self.full_verify)
        self.assertNotIn("STRIPE_SECRET_KEY", self.full_backup)

    def test_backend_joins_the_external_postgres_network(self):
        self.assertIn("- froid-data", self.compose)
        self.assertIn(
            "name: ${FROID_DATA_NETWORK:-froid_froid-network}", self.compose
        )


if __name__ == "__main__":
    unittest.main()
