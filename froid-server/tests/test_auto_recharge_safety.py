"""Propriedades de seguranca da recarga automatica.

A recarga automatica cobra o cartao do cliente sem interacao humana
(``off_session``), entao as travas abaixo protegem dinheiro real. Validar isso
ponta a ponta exige chaves Stripe de teste, que nao estao configuradas neste
ambiente - o que ESTE arquivo garante e que as travas nao sumam do codigo por
uma refatoracao. A validacao ponta a ponta continua pendente e depende das
chaves ``sk_test_...``.
"""

from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]


class AutoRechargeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        anchor = cls.main_source.index("async def _run_automatic_recharge(")
        cls.block = cls.main_source[anchor : anchor + 4000]

    def test_charge_carries_an_idempotency_key(self):
        """Sem isso, um retry de rede cobraria o cliente duas vezes."""
        self.assertIn('"Idempotency-Key": recharge["idempotency_key"]', self.block)

    def test_charge_is_explicitly_off_session_and_confirmed(self):
        self.assertIn('"off_session": "true"', self.block)
        self.assertIn('"confirm": "true"', self.block)

    def test_recharge_only_runs_when_the_organization_opted_in(self):
        """prepare_auto_recharge devolve None para quem nao habilitou."""
        self.assertIn("TENANT_STORE.prepare_auto_recharge", self.block)
        self.assertIn("if not recharge:", self.block)
        self.assertIn("return", self.block)

    def test_recharge_is_only_triggered_at_zero_balance(self):
        anchor = self.main_source.index("def _consume_session_credit(")
        consume = self.main_source[anchor : anchor + 3600]
        self.assertIn('int(result.get("balance") or 0) == 0', consume)
        self.assertIn("_run_automatic_recharge(context.organization_id)", consume)

    def test_credits_are_only_granted_after_stripe_confirms(self):
        """O credito so entra com status 'succeeded' vindo do Stripe."""
        self.assertIn('payment_intent.get("status") == "succeeded"', self.block)
        self.assertIn("TENANT_STORE.complete_auto_recharge", self.block)

    def test_the_stripe_response_is_fingerprinted_for_audit(self):
        self.assertIn("payload_sha256=hashlib.sha256(response.content).hexdigest()", self.block)

    def test_recharge_failure_never_raises_into_the_session_flow(self):
        """Uma falha de cobranca nao pode derrubar a sessao clinica em curso."""
        self.assertIn("try:", self.block)
        anchor = self.main_source.index("def _consume_session_credit(")
        consume = self.main_source[anchor : anchor + 3600]
        # A recarga e agendada como task; a sessao segue independentemente.
        self.assertIn("create_task(", consume)


if __name__ == "__main__":
    unittest.main()
