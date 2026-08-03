from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_store import TenantStore  # noqa: E402


class SharedCreditWalletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial_sql = (
            SERVER_DIR / "migrations" / "004_shared_credit_wallet.sql"
        ).read_text(encoding="utf-8")
        cls.safety_sql = (
            SERVER_DIR / "migrations" / "005_wallet_activation_safety.sql"
        ).read_text(encoding="utf-8")
        cls.store_source = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        cls.main_source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

    def test_wallet_update_locks_row_and_is_idempotent(self):
        self.assertIn("FOR UPDATE", self.safety_sql)
        self.assertGreaterEqual(self.safety_sql.count("idempotency_key=idem"), 2)
        self.assertIn("resulting_balance", self.safety_sql)

    def test_wallet_rejects_negative_balance_and_cross_context(self):
        self.assertIn("insufficient organization credits", self.safety_sql)
        self.assertIn("wallet event context mismatch", self.safety_sql)

    def test_consumption_is_exactly_one_credit(self):
        self.assertIn("kind='consumption' AND delta<>-1", self.safety_sql)

    def test_shared_wallet_requires_explicit_reconciled_activation(self):
        self.assertIn("authority IN ('legacy','shared')", self.safety_sql)
        self.assertIn("legacy balance reconciliation failed", self.safety_sql)
        self.assertIn("wallet.authority<>'shared'", self.safety_sql)

    def test_legacy_backfill_cannot_overwrite_shared_balance(self):
        # A guarda deixou de ser um CASE WHEN inline no ON CONFLICT e passou a
        # ser explicita em _contribute_legacy_balance, que le a autoridade sob
        # FOR UPDATE e desiste se a carteira ja foi ativada. O comportamento e
        # exercitado de verdade em test_legacy_balance_consolidation.
        self.assertIn("def _contribute_legacy_balance(", self.store_source)
        self.assertIn('authority != "legacy"', self.store_source)
        self.assertIn("FOR UPDATE", self.store_source)

    def test_legacy_backfill_sums_balances_instead_of_overwriting(self):
        """Numa clinica, cada profissional soma seu saldo ao pool compartilhado."""
        self.assertIn("current_balance + contribution", self.store_source)
        self.assertIn('f"legacy-opening-v1:{user_id}"', self.store_source)
        self.assertNotIn(
            "balance=CASE WHEN organization_wallets.authority='legacy'",
            self.store_source,
        )

    def test_billing_fallback_is_opt_in_and_bonus_is_server_calculated(self):
        self.assertIn('"FROID_ALLOW_LOCAL_BILLING_FALLBACK", "false"', self.main_source)
        self.assertIn("bonus_sessions = (contracted_sessions // 100) * 10", self.main_source)

    def test_legacy_mode_cannot_mutate_shared_wallet(self):
        store = TenantStore("legacy", "", SERVER_DIR / "missing.sql")
        with self.assertRaises(RuntimeError):
            store.apply_credit_event(
                organization_id="org", membership_id="member",
                actor_user_id="user", delta=-1, event_type="consumption",
                idempotency_key="session:1",
            )

    def test_runtime_role_is_mandatory(self):
        store = TenantStore(
            "dual", "postgresql://owner", SERVER_DIR / "missing.sql"
        )
        with self.assertRaises(RuntimeError):
            store.apply_credit_event(
                organization_id="org", membership_id="member",
                actor_user_id="user", delta=-1, event_type="consumption",
                idempotency_key="session:1",
            )


if __name__ == "__main__":
    unittest.main()
