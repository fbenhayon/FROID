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
        cls.sql = (
            SERVER_DIR / "migrations" / "004_shared_credit_wallet.sql"
        ).read_text(encoding="utf-8")

    def test_wallet_update_locks_row_and_is_idempotent(self):
        self.assertIn("FOR UPDATE", self.sql)
        self.assertIn("idempotency_key = target_idempotency_key", self.sql)
        self.assertIn("resulting_balance", self.sql)

    def test_wallet_rejects_negative_balance_and_cross_context(self):
        self.assertIn("insufficient organization credits", self.sql)
        self.assertIn("organization context mismatch", self.sql)
        self.assertIn("membership context mismatch", self.sql)

    def test_consumption_is_exactly_one_credit(self):
        self.assertIn("credit_delta <> -1", self.sql)

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
