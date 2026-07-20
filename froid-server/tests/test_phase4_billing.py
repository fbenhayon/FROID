from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from subscriptions import SESSION_PACKAGES, SUPPORTED_BILLING_CURRENCIES


class Phase4BillingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.store = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        cls.migration = (
            SERVER_DIR / "migrations" / "006_subscription_entitlements.sql"
        ).read_text(encoding="utf-8")

    def test_official_package_values_are_server_owned(self):
        expected = {
            "pro_10": ("pro", 10, {"brl": (1984, 19800), "usd": (397, 4000), "eur": (331, 3300), "cny": (1492, 14900)}),
            "pro_25": ("pro", 25, {"brl": (1880, 47000), "usd": (376, 9400), "eur": (313, 7800), "cny": (1414, 35300)}),
            "plus_50": ("plus", 50, {"brl": (2363, 118200), "usd": (473, 23600), "eur": (394, 19700), "cny": (1777, 88900)}),
            "plus_100": ("plus", 100, {"brl": (2202, 220200), "usd": (440, 44000), "eur": (367, 36700), "cny": (1656, 165600)}),
            "master_25": ("master", 25, {"brl": (78, 2000), "usd": (16, 400), "eur": (13, 300), "cny": (59, 1500)}),
        }
        actual = {
            code: (
                item["plan_code"], item["sessions"], {
                    currency: (
                        price["unit_amount_minor"], price["total_amount_minor"]
                    ) for currency, price in item["prices"].items()
                },
            )
            for code, item in SESSION_PACKAGES.items()
        }
        self.assertEqual(actual, expected)
        self.assertEqual(SUPPORTED_BILLING_CURRENCIES, ("brl", "usd", "eur", "cny"))

    def test_currency_is_validated_and_persisted(self):
        self.assertIn('params={"expand[]": "currency_options"}', self.main)
        self.assertIn('"currency": recharge["currency"]', self.main)
        self.assertIn("s.currency", self.store)
        self.assertIn("currency IN ('brl','usd','eur','cny')", self.migration)

    def test_checkout_keeps_automatic_recharge_optional(self):
        self.assertIn('auto_replenish = body.get("auto_replenish_consent") is True', self.main)
        self.assertIn('if auto_replenish:', self.main)
        self.assertIn('form["payment_intent_data[setup_future_usage]"] = "off_session"', self.main)
        self.assertEqual(self.main.count('metadata.get("auto_replenish") == "true"'), 2)
        self.assertIn("AUTO_REPLENISH_TERMS_VERSION", self.main)
        self.assertIn("auto_replenish_consent_at", self.migration)

    def test_checkout_return_has_authenticated_reconciliation(self):
        self.assertIn('@app.post("/api/subscriptions/confirm-checkout")', self.main)
        self.assertIn('event_id=f"checkout:{checkout_session_id}"', self.main)
        self.assertIn("pagamento não pertence à organização ativa", self.main)

    def test_access_requires_authoritative_stripe_payment_evidence(self):
        self.assertIn("async def _verify_stripe_checkout_line_item", self.main)
        self.assertIn('payment_intent.get("status") != "succeeded"', self.main)
        self.assertIn('stripe_session.get("payment_status") != "paid"', self.main)
        self.assertIn('str(price.get("id") or "") != expected_price_id', self.main)
        self.assertIn('payment_metadata.get("organization_id") != organization_id', self.main)
        self.assertIn('paid_amount != int(commercial_price["total_amount_minor"])', self.main)

    def test_webhook_handles_purchase_success_and_failure(self):
        for event_type in (
            "checkout.session.completed", "payment_intent.succeeded",
            "payment_intent.payment_failed",
        ):
            self.assertIn(event_type, self.main)
        self.assertIn("verify_stripe_event", self.main)

    def test_recharge_is_single_open_and_credits_once(self):
        self.assertIn("automatic_recharges_one_open_per_org", self.migration)
        self.assertIn("status IN ('pending','processing','action_required')", self.migration)
        self.assertIn("recharge[2] == \"succeeded\"", self.store)
        self.assertIn("automatic recharge amount or currency mismatch", self.store)
        self.assertIn('f"recharge:{recharge_id}"', self.store)
        self.assertIn("status IN ('pending','processing','action_required')", self.store)
        self.assertIn("transport_error:", self.main)

    def test_failed_webhooks_are_recorded_without_downgrading_success(self):
        self.assertIn("event_id: str = \"\", event_type: str = \"\"", self.store)
        self.assertIn("INSERT INTO stripe_webhook_events", self.store)
        self.assertNotIn("WHERE id=%s AND status <> 'succeeded'", self.store)

    def test_catalog_entitlements_are_upserted_as_authoritative(self):
        self.assertIn("ON CONFLICT (code) DO UPDATE SET", self.migration)
        for entitlement in ("session_layouts", "clinical_metrics", "froid_explica"):
            self.assertIn(entitlement, self.migration)

    def test_required_subscription_access_fails_closed(self):
        self.assertIn('"payment_status": "subscription_unavailable"', self.main)
        self.assertIn("fail_closed if FROID_SUBSCRIPTIONS_REQUIRED", self.main)

    def test_member_limit_is_enforced_from_entitlements(self):
        self.assertIn("organization_member_limit_reached", self.store)
        self.assertIn("organization_members", self.store)


if __name__ == "__main__":
    unittest.main()
