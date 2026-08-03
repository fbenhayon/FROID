"""Testes funcionais da aritmetica de quitacao de sessoes em aberto.

main.py nao e importavel no ambiente de teste (depende de FastAPI, openai,
duckdb...), mas a matematica de credito e dinheiro do cliente e precisa ser
executada, nao apenas conferida por string. Estes testes extraem o codigo-fonte
real das funcoes com ``ast`` e o executam com as dependencias minimas
substituidas - portanto exercitam a implementacao de verdade, nao uma copia.

Regra de produto coberta aqui:
- Sessao entregue sem credito vira pendencia (nunca e recusada).
- O teto de sessoes em aberto bloqueia o INICIO de novas sessoes.
- Na renovacao do plano, as pendentes sao creditadas ao FROID automaticamente,
  exatamente uma vez - sem cobrar duas vezes nem perder a cobranca.
"""

import ast
import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

# main.py usa uma f-string com barra invertida, valida a partir do Python 3.12
# (a imagem de producao e python:3.12-slim). Em interpretadores anteriores o
# ast.parse falha, entao os testes que executam o codigo real sao pulados -
# rode-os com python3.12 para exercitar a aritmetica de credito.
try:
    ast.parse(MAIN_SOURCE)
    MAIN_PARSEABLE = True
except SyntaxError:
    MAIN_PARSEABLE = False


def load_functions(*names):
    """Executa as funcoes reais de main.py num namespace isolado."""
    tree = ast.parse(MAIN_SOURCE)
    wanted = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }
    missing = set(names) - set(wanted)
    if missing:
        raise AssertionError(f"funcoes nao encontradas em main.py: {sorted(missing)}")

    def local_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    namespace = {
        "_local_int": local_int,
        "_utc_now_iso": lambda: "2026-01-01T00:00:00+00:00",
    }
    module = ast.Module(body=[wanted[name] for name in names], type_ignores=[])
    exec(compile(module, "<main-extract>", "exec"), namespace)  # noqa: S102
    return namespace


@unittest.skipUnless(
    MAIN_PARSEABLE, f"main.py exige Python >= 3.12 (atual: {sys.version_info[:2]})"
)
class PendingSettlementMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.namespace = load_functions("_settle_pending_sessions")
        # staticmethod evita que o acesso via self vincule a instancia como
        # primeiro argumento da funcao extraida.
        cls.settle = staticmethod(cls.namespace["_settle_pending_sessions"])

    # -- compra avulsa: a divida sai dos creditos novos --------------------

    def test_add_sessions_charges_pending_against_new_credits(self):
        """3 pendentes + compra de 50 => 47 disponiveis, divida zerada."""
        profile = {
            "remaining_sessions": 50,  # ja somado pelo ramo add_sessions
            "pending_settlement_session_ids": ["s1", "s2", "s3"],
            "pending_settlement_count": 3,
        }
        settled = self.settle(profile, already_deducted=False)
        self.assertEqual(settled, 3)
        self.assertEqual(profile["remaining_sessions"], 47)
        self.assertEqual(profile["pending_settlement_count"], 0)
        self.assertEqual(profile["pending_settlement_session_ids"], [])

    def test_partial_settlement_when_new_credits_are_insufficient(self):
        """5 pendentes mas so 2 creditos: quita 2 e mantem 3 em aberto."""
        profile = {
            "remaining_sessions": 2,
            "pending_settlement_session_ids": ["a", "b", "c", "d", "e"],
            "pending_settlement_count": 5,
        }
        settled = self.settle(profile, already_deducted=False)
        self.assertEqual(settled, 2)
        self.assertEqual(profile["remaining_sessions"], 0)
        self.assertEqual(profile["pending_settlement_count"], 3)
        self.assertEqual(profile["pending_settlement_session_ids"], ["c", "d", "e"])

    def test_no_credits_settles_nothing_and_keeps_the_debt(self):
        profile = {
            "remaining_sessions": 0,
            "pending_settlement_session_ids": ["x"],
            "pending_settlement_count": 1,
        }
        self.assertEqual(self.settle(profile, already_deducted=False), 0)
        self.assertEqual(profile["remaining_sessions"], 0)
        self.assertEqual(profile["pending_settlement_count"], 1)
        self.assertEqual(profile["pending_settlement_session_ids"], ["x"])

    # -- troca de plano: (total - usadas) ja descontou ---------------------

    def test_plan_replacement_does_not_charge_twice(self):
        """A conta (total - usadas) ja abateu as pendentes; nao descontar de novo."""
        # total=150, usadas=101 (100 pagas + 1 entregue sem credito) => 49.
        profile = {
            "remaining_sessions": 49,
            "used_sessions": 101,
            "total_sessions": 150,
            "pending_settlement_session_ids": ["pendente-1"],
            "pending_settlement_count": 1,
        }
        settled = self.settle(profile, already_deducted=True)
        self.assertEqual(settled, 1)
        self.assertEqual(
            profile["remaining_sessions"], 49, "saldo nao pode ser debitado de novo"
        )
        self.assertEqual(profile["pending_settlement_count"], 0)

    def test_settlement_is_recorded_for_audit(self):
        profile = {
            "remaining_sessions": 10,
            "pending_settlement_session_ids": ["s9"],
            "pending_settlement_count": 1,
        }
        self.settle(profile, already_deducted=False)
        history = profile["settlement_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["settled_sessions"], 1)
        self.assertEqual(history[0]["settled_session_ids"], ["s9"])
        self.assertTrue(history[0]["charged_against_new_credits"])

    # -- idempotencia / ausencia de divida --------------------------------

    def test_settling_twice_does_not_double_charge(self):
        profile = {
            "remaining_sessions": 20,
            "pending_settlement_session_ids": ["s1", "s2"],
            "pending_settlement_count": 2,
        }
        self.assertEqual(self.settle(profile, already_deducted=False), 2)
        self.assertEqual(profile["remaining_sessions"], 18)
        # Uma segunda renovacao nao pode cobrar as mesmas sessoes de novo.
        self.assertEqual(self.settle(profile, already_deducted=False), 0)
        self.assertEqual(profile["remaining_sessions"], 18)

    def test_profile_without_debt_is_untouched(self):
        profile = {"remaining_sessions": 30}
        self.assertEqual(self.settle(profile, already_deducted=False), 0)
        self.assertEqual(profile["remaining_sessions"], 30)
        self.assertEqual(profile["pending_settlement_count"], 0)


class PendingSettlementPolicyTests(unittest.TestCase):
    """Politica declarada em main.py: teto de 10 e bloqueio de novas sessoes."""

    def test_default_limit_is_ten_and_configurable(self):
        self.assertIn('os.getenv("FROID_MAX_PENDING_SETTLEMENTS", "10")', MAIN_SOURCE)

    def test_reaching_the_limit_blocks_starting_new_sessions(self):
        self.assertIn(
            "settlement_blocked = pending_settlement >= FROID_MAX_PENDING_SETTLEMENTS",
            MAIN_SOURCE,
        )
        self.assertIn('"settlement_blocked": settlement_blocked,', MAIN_SOURCE)

    def test_purchase_records_how_many_pending_sessions_it_settled(self):
        self.assertIn('"settled_pending_sessions": settled_sessions,', MAIN_SOURCE)


if __name__ == "__main__":
    unittest.main()
