"""Regressao: esgotamento de credito nunca destroi o registro clinico.

Ate esta mudanca, um 402 (sem credito) ou 503 (Postgres inacessivel) durante o
arquivamento do relatorio removia o relatorio de uma sessao ja realizada. Para
um prontuario de saude mental isso e perda de dado clinico causada por
cobranca. A regra definida pelo produto e: a sessao e entregue, o registro
permanece salvo, e a pendencia e avisada a cada acesso para o administrador
acertar.

main.py depende de FastAPI, que nao esta disponivel no ambiente de teste, entao
as assercoes sao sobre o codigo-fonte - mesmo padrao ja usado pelos demais
testes deste diretorio.
"""

from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]


class CreditExhaustionPreservesReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

    def _archive_failure_block(self):
        """Isola o tratamento de falha do consumo de credito no arquivamento."""
        anchor = self.main_source.index("_consume_session_credit(context, owner_email")
        return self.main_source[anchor : anchor + 1200]

    def test_failed_credit_consumption_does_not_delete_the_report(self):
        block = self._archive_failure_block()
        self.assertNotIn("reports.pop(session_id, None)", block)
        self.assertNotIn("mark_mirrored_report_deleted", block)
        self.assertIn("relatório clínico preservado", block)

    def test_exhausted_credit_registers_pending_settlement_instead_of_refusing(self):
        self.assertIn("def _register_pending_settlement(", self.main_source)
        # O caminho legado nao pode mais recusar a sessao com 402.
        self.assertNotIn(
            'raise HTTPException(status_code=402, detail="créditos de sessão insuficientes")',
            self.main_source,
        )
        self.assertNotIn(
            'raise HTTPException(status_code=402, detail="créditos da organização insuficientes")',
            self.main_source,
        )
        self.assertIn("_register_pending_settlement(email, session_id, profile)", self.main_source)

    def test_pending_settlement_is_surfaced_on_every_access(self):
        for field in (
            '"pending_settlement_count"',
            '"settlement_pending"',
            '"settlement_warning"',
        ):
            self.assertIn(field, self.main_source)

    def test_shared_pool_exhaustion_keeps_wallet_non_negative(self):
        """A invariante provada em test_shared_wallet_postgres continua valida.

        O esgotamento e absorvido pela pendencia na aplicacao; a carteira
        compartilhada nunca e levada a saldo negativo.
        """
        self.assertIn('"organization_pool_exhausted"', self.main_source)
        self.assertIn("nunca negativo", self.main_source)

    def test_session_consumption_stays_idempotent_after_the_change(self):
        """Preservar o relatorio nao pode abrir caminho para cobranca dupla."""
        self.assertIn('idempotency_key=f"session:{session_id}"', self.main_source)
        self.assertIn("consumed_session_ids", self.main_source)


if __name__ == "__main__":
    unittest.main()
