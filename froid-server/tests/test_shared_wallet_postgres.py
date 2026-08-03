"""Executable integration tests for the shared credit wallet.

Unlike the textual assertions in ``test_phase3_wallet.py`` (which only grep the
migration files as strings), these tests run the real SQL against a real
PostgreSQL instance. They cover the money-critical properties: idempotency
under concurrency, absence of lost updates, the non-negative balance floor,
role enforcement, and activation reconciliation.

Skipped automatically when ``FROID_TEST_DATABASE_URL`` is not set, so ordinary
test runs and CI without a database stay green.

To run locally:
    createdb froid_test && psql -d froid_test -f migrations/001_...sql  (etc.)
    FROID_TEST_DATABASE_URL=postgresql://... python3 -m unittest \\
        froid-server.tests.test_shared_wallet_postgres
"""

import os
import threading
import unittest
import uuid

DATABASE_URL = os.getenv("FROID_TEST_DATABASE_URL", "")

try:  # pragma: no cover - import guard
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ORG = "11111111-1111-4111-8111-111111111111"
# Quatro profissionais na mesma clinica, exatamente o cenario auditado.
PROFESSIONALS = [
    {
        "user": f"2222222{index}-2222-4222-8222-222222222222",
        "membership": f"3333333{index}-3333-4333-8333-333333333333",
        "email": f"profissional{index}@clinica.example",
        "role": "owner" if index == 0 else "professional",
    }
    for index in range(4)
]
OWNER = PROFESSIONALS[0]


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class SharedWalletPostgresTests(unittest.TestCase):
    @classmethod
    def connect(cls):
        return psycopg.connect(DATABASE_URL, autocommit=True)

    @classmethod
    def bind(cls, cursor, professional):
        """Aplica o contexto de sessao que as funcoes SECURITY DEFINER exigem."""
        cursor.execute("SELECT set_config('app.organization_id', %s, false)", (ORG,))
        cursor.execute(
            "SELECT set_config('app.membership_id', %s, false)",
            (professional["membership"],),
        )

    def reset_wallet(self, balance, authority="shared"):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM credit_ledger WHERE organization_id=%s", (ORG,))
            cursor.execute(
                """
                INSERT INTO organization_wallets (organization_id, balance, authority)
                VALUES (%s,%s,%s)
                ON CONFLICT (organization_id) DO UPDATE
                SET balance=EXCLUDED.balance, authority=EXCLUDED.authority
                """,
                (ORG, balance, authority),
            )

    @classmethod
    def setUpClass(cls):
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO organizations
                    (id, organization_type, legal_name, display_name, document)
                VALUES (%s,'clinic','Clinica Auditoria','Clinica Auditoria','00.000.000/0001-00')
                ON CONFLICT (id) DO NOTHING
                """,
                (ORG,),
            )
            for professional in PROFESSIONALS:
                cursor.execute(
                    "INSERT INTO users (id,email) VALUES (%s,%s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (professional["user"], professional["email"]),
                )
                cursor.execute(
                    """
                    INSERT INTO organization_memberships
                        (id, organization_id, user_id, status)
                    VALUES (%s,%s,%s,'active') ON CONFLICT (id) DO NOTHING
                    """,
                    (professional["membership"], ORG, professional["user"]),
                )
                cursor.execute(
                    "INSERT INTO membership_roles (membership_id, role) VALUES (%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (professional["membership"], professional["role"]),
                )

    def consume(self, professional, session_id, connection=None):
        """Debita um credito; devolve (balance, applied) ou levanta a excecao."""
        owns_connection = connection is None
        connection = connection or self.connect()
        try:
            with connection.cursor() as cursor:
                self.bind(cursor, professional)
                cursor.execute(
                    """
                    SELECT resulting_balance, applied FROM froid_apply_credit_event(
                        %s,%s,%s,-1,'consumption',%s,%s,'{}'::jsonb)
                    """,
                    (
                        ORG,
                        professional["membership"],
                        professional["user"],
                        f"session:{session_id}",
                        session_id,
                    ),
                )
                return cursor.fetchone()
        finally:
            if owns_connection:
                connection.close()

    def wallet_balance(self):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT balance FROM organization_wallets WHERE organization_id=%s",
                (ORG,),
            )
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Propriedades criticas de dinheiro
    # ------------------------------------------------------------------

    def test_same_session_debits_exactly_once(self):
        """Reenviar o mesmo relatorio nao pode cobrar duas vezes."""
        self.reset_wallet(500)
        first = self.consume(OWNER, "sessao-repetida")
        second = self.consume(OWNER, "sessao-repetida")
        self.assertEqual(first, (499, True))
        self.assertEqual(second, (499, False), "segunda chamada deveria ser inerte")
        self.assertEqual(self.wallet_balance(), 499)

    def test_concurrent_debits_never_lose_updates(self):
        """4 profissionais debitando ao mesmo tempo: 40 sessoes = 40 creditos."""
        self.reset_wallet(500)
        per_professional = 10
        barrier = threading.Barrier(len(PROFESSIONALS))
        errors = []

        def worker(professional, index):
            try:
                connection = self.connect()
                barrier.wait(timeout=30)  # maximiza a contencao real
                for attempt in range(per_professional):
                    self.consume(professional, f"conc-{index}-{attempt}", connection)
                connection.close()
            except Exception as error:  # pragma: no cover - falha do teste
                errors.append(error)

        threads = [
            threading.Thread(target=worker, args=(professional, index))
            for index, professional in enumerate(PROFESSIONALS)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(errors, [], "nenhum debito concorrente deveria falhar")
        expected = 500 - len(PROFESSIONALS) * per_professional
        self.assertEqual(self.wallet_balance(), expected)
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM credit_ledger "
                "WHERE organization_id=%s AND event_type='consumption'",
                (ORG,),
            )
            self.assertEqual(cursor.fetchone()[0], len(PROFESSIONALS) * per_professional)

    def test_concurrent_duplicate_key_debits_only_once(self):
        """A corrida que a migracao 004 nao cobria: mesma chave em paralelo."""
        self.reset_wallet(500)
        barrier = threading.Barrier(len(PROFESSIONALS))
        applied_flags = []
        lock = threading.Lock()

        def worker(professional):
            connection = None
            try:
                connection = self.connect()
                barrier.wait(timeout=30)
                _, applied = self.consume(professional, "corrida-mesma-chave", connection)
                with lock:
                    applied_flags.append(applied)
            except Exception:
                # Violacao de unicidade tambem e um desfecho seguro: aborta a
                # transacao inteira, entao o debito nao persiste.
                with lock:
                    applied_flags.append(False)
            finally:
                if connection:
                    connection.close()

        threads = [
            threading.Thread(target=worker, args=(professional,))
            for professional in PROFESSIONALS
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(
            applied_flags.count(True), 1, "exatamente um debito deveria ser aplicado"
        )
        self.assertEqual(self.wallet_balance(), 499)

    def test_balance_never_goes_negative(self):
        self.reset_wallet(1)
        self.consume(OWNER, "ultima-sessao")
        self.assertEqual(self.wallet_balance(), 0)
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.consume(OWNER, "sessao-sem-saldo")
        self.assertIn("insufficient organization credits", str(raised.exception))
        self.assertEqual(self.wallet_balance(), 0)

    def test_professional_role_cannot_purchase_credits(self):
        self.reset_wallet(10)
        professional = PROFESSIONALS[1]
        with self.connect() as connection, connection.cursor() as cursor:
            self.bind(cursor, professional)
            with self.assertRaises(psycopg.errors.InsufficientPrivilege) as raised:
                cursor.execute(
                    """
                    SELECT * FROM froid_apply_credit_event(
                        %s,%s,%s,100,'purchase',%s,NULL,'{}'::jsonb)
                    """,
                    (
                        ORG,
                        professional["membership"],
                        professional["user"],
                        f"compra-{uuid.uuid4()}",
                    ),
                )
            self.assertIn("role cannot manage credits", str(raised.exception))
        self.assertEqual(self.wallet_balance(), 10)

    def test_consumption_must_debit_exactly_one(self):
        self.reset_wallet(100)
        with self.connect() as connection, connection.cursor() as cursor:
            self.bind(cursor, OWNER)
            with self.assertRaises(psycopg.errors.InvalidParameterValue):
                cursor.execute(
                    """
                    SELECT * FROM froid_apply_credit_event(
                        %s,%s,%s,-25,'consumption',%s,NULL,'{}'::jsonb)
                    """,
                    (ORG, OWNER["membership"], OWNER["user"], f"lote-{uuid.uuid4()}"),
                )
        self.assertEqual(self.wallet_balance(), 100)

    def test_wallet_refuses_events_until_activated(self):
        """Portao de autoridade: nada e debitado antes da ativacao explicita."""
        self.reset_wallet(500, authority="legacy")
        with self.assertRaises(psycopg.errors.ObjectNotInPrerequisiteState) as raised:
            self.consume(OWNER, "antes-da-ativacao")
        self.assertIn("shared wallet is not active", str(raised.exception))
        self.assertEqual(self.wallet_balance(), 500)

    def test_activation_requires_exact_reconciliation(self):
        self.reset_wallet(500, authority="legacy")
        with self.connect() as connection, connection.cursor() as cursor:
            self.bind(cursor, OWNER)
            with self.assertRaises(psycopg.errors.RaiseException) as raised:
                cursor.execute(
                    "SELECT * FROM froid_activate_shared_wallet(%s,%s,%s,%s)",
                    (ORG, OWNER["membership"], OWNER["user"], 499),
                )
            self.assertIn("legacy balance reconciliation failed", str(raised.exception))

        with self.connect() as connection, connection.cursor() as cursor:
            self.bind(cursor, OWNER)
            cursor.execute(
                "SELECT * FROM froid_activate_shared_wallet(%s,%s,%s,%s)",
                (ORG, OWNER["membership"], OWNER["user"], 500),
            )
            self.assertEqual(cursor.fetchone(), (500, True))
            # Reativar e inerte, nao duplica saldo.
            cursor.execute(
                "SELECT * FROM froid_activate_shared_wallet(%s,%s,%s,%s)",
                (ORG, OWNER["membership"], OWNER["user"], 500),
            )
            self.assertEqual(cursor.fetchone(), (500, False))
        self.assertEqual(self.wallet_balance(), 500)

    def test_ledger_attributes_each_consumption_to_its_actor(self):
        """A atribuicao por profissional existe no ledger (base do relatorio)."""
        self.reset_wallet(500)
        for index, professional in enumerate(PROFESSIONALS):
            for attempt in range(index + 1):  # 1, 2, 3 e 4 sessoes
                self.consume(professional, f"atrib-{index}-{attempt}")
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT actor_user_id, count(*) FROM credit_ledger
                WHERE organization_id=%s AND event_type='consumption'
                GROUP BY actor_user_id
                """,
                (ORG,),
            )
            usage = {str(row[0]): row[1] for row in cursor.fetchall()}
        for index, professional in enumerate(PROFESSIONALS):
            self.assertEqual(usage.get(professional["user"]), index + 1)
        self.assertEqual(self.wallet_balance(), 500 - 10)


if __name__ == "__main__":
    unittest.main()
