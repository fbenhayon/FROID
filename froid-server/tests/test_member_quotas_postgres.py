"""Cotas individuais por profissional dentro do pool da clinica.

Executa contra PostgreSQL real. A cota e um teto de consumo aplicado DENTRO da
mesma transacao do debito do pool - por isso o teste de concorrencia abaixo e o
mais importante do arquivo: validar a cota fora da transacao deixaria uma janela
para dois consumos simultaneos ultrapassarem o limite.

Pulado automaticamente sem ``FROID_TEST_DATABASE_URL``.
"""

import os
import threading
import unittest

DATABASE_URL = os.getenv("FROID_TEST_DATABASE_URL", "")

try:  # pragma: no cover - import guard
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ORG = "44444444-4444-4444-8444-444444444444"
ADMIN = {
    "user": "55555555-5555-4555-8555-555555555555",
    "membership": "66666666-6666-4666-8666-666666666666",
    "email": "gestor@clinica.example",
    "role": "owner",
}
MEMBER = {
    "user": "77777777-7777-4777-8777-777777777777",
    "membership": "88888888-8888-4888-8888-888888888888",
    "email": "profissional.cota@clinica.example",
    "role": "professional",
}
FREE = {
    "user": "99999999-9999-4999-8999-999999999999",
    "membership": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "email": "profissional.livre@clinica.example",
    "role": "professional",
}
EVERYONE = [ADMIN, MEMBER, FREE]


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class MemberQuotaTests(unittest.TestCase):
    @classmethod
    def connect(cls):
        return psycopg.connect(DATABASE_URL, autocommit=True)

    @classmethod
    def bind(cls, cursor, person):
        cursor.execute("SELECT set_config('app.organization_id', %s, false)", (ORG,))
        cursor.execute(
            "SELECT set_config('app.membership_id', %s, false)", (person["membership"],)
        )

    @classmethod
    def setUpClass(cls):
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO organizations
                    (id, organization_type, legal_name, display_name, document)
                VALUES (%s,'clinic','Clinica Cotas','Clinica Cotas','99.999.999/0001-99')
                ON CONFLICT (id) DO NOTHING
                """,
                (ORG,),
            )
            for person in EVERYONE:
                cursor.execute(
                    "INSERT INTO users (id,email) VALUES (%s,%s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (person["user"], person["email"]),
                )
                cursor.execute(
                    "INSERT INTO organization_memberships "
                    "(id,organization_id,user_id,status) VALUES (%s,%s,%s,'active') "
                    "ON CONFLICT (id) DO NOTHING",
                    (person["membership"], ORG, person["user"]),
                )
                cursor.execute(
                    "INSERT INTO membership_roles (membership_id,role) VALUES (%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (person["membership"], person["role"]),
                )

    def setUp(self):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM credit_ledger WHERE organization_id=%s", (ORG,))
            cursor.execute(
                "DELETE FROM organization_member_quotas WHERE organization_id=%s", (ORG,)
            )
            cursor.execute(
                """
                INSERT INTO organization_wallets (organization_id, balance, authority)
                VALUES (%s,1000,'shared')
                ON CONFLICT (organization_id) DO UPDATE
                SET balance=1000, authority='shared'
                """,
                (ORG,),
            )

    def set_quota(self, target, quota, actor=ADMIN):
        with self.connect() as connection, connection.cursor() as cursor:
            self.bind(cursor, actor)
            cursor.execute(
                "SELECT * FROM froid_set_member_quota(%s,%s,%s,%s,%s)",
                (ORG, actor["membership"], actor["user"], target["membership"], quota),
            )
            return cursor.fetchone()

    def consume(self, person, session_id, connection=None):
        owns = connection is None
        connection = connection or self.connect()
        try:
            with connection.cursor() as cursor:
                self.bind(cursor, person)
                cursor.execute(
                    """
                    SELECT resulting_balance, applied FROM froid_apply_credit_event(
                        %s,%s,%s,-1,'consumption',%s,%s,'{}'::jsonb)
                    """,
                    (
                        ORG,
                        person["membership"],
                        person["user"],
                        f"session:{session_id}",
                        session_id,
                    ),
                )
                return cursor.fetchone()
        finally:
            if owns:
                connection.close()

    def quota_row(self, person):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT quota_sessions, consumed_sessions FROM organization_member_quotas "
                "WHERE organization_id=%s AND membership_id=%s",
                (ORG, person["membership"]),
            )
            return cursor.fetchone()

    def wallet(self):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT balance FROM organization_wallets WHERE organization_id=%s",
                (ORG,),
            )
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------

    def test_without_quota_professional_draws_freely_from_the_pool(self):
        """Padrao do produto: pool livre para todos."""
        for index in range(5):
            self.consume(FREE, f"livre-{index}")
        self.assertIsNone(self.quota_row(FREE))
        self.assertEqual(self.wallet(), 995)

    def test_quota_caps_how_much_of_the_pool_a_member_may_use(self):
        self.set_quota(MEMBER, 3)
        for index in range(3):
            self.consume(MEMBER, f"cota-{index}")
        self.assertEqual(self.quota_row(MEMBER), (3, 3))
        with self.assertRaises(psycopg.errors.RaiseException) as raised:
            self.consume(MEMBER, "cota-estourada")
        self.assertIn("member quota exhausted", str(raised.exception))
        # O pool ainda tem saldo: quem barrou foi a cota, nao o saldo.
        self.assertEqual(self.wallet(), 997)

    def test_quota_of_one_member_does_not_limit_another(self):
        self.set_quota(MEMBER, 1)
        self.consume(MEMBER, "limitado-1")
        with self.assertRaises(psycopg.errors.RaiseException):
            self.consume(MEMBER, "limitado-2")
        for index in range(4):
            self.consume(FREE, f"sem-limite-{index}")
        self.assertEqual(self.wallet(), 995)

    def test_concurrent_consumption_cannot_exceed_the_quota(self):
        """O teste central: 8 consumos simultaneos com cota de 3."""
        self.set_quota(MEMBER, 3)
        attempts = 8
        barrier = threading.Barrier(attempts)
        applied = []
        lock = threading.Lock()

        def worker(index):
            connection = None
            try:
                connection = self.connect()
                barrier.wait(timeout=30)
                self.consume(MEMBER, f"corrida-cota-{index}", connection)
                with lock:
                    applied.append(True)
            except Exception:
                with lock:
                    applied.append(False)
            finally:
                if connection:
                    connection.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(attempts)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(
            applied.count(True), 3, "a cota nao pode ser ultrapassada por concorrencia"
        )
        self.assertEqual(self.quota_row(MEMBER), (3, 3))
        self.assertEqual(self.wallet(), 997)

    def test_admin_can_raise_lower_and_remove_a_quota(self):
        self.set_quota(MEMBER, 2)
        self.consume(MEMBER, "ajuste-1")
        self.assertEqual(self.quota_row(MEMBER), (2, 1))
        # Aumentar libera mais sessoes, preservando o ja consumido.
        self.set_quota(MEMBER, 5)
        self.assertEqual(self.quota_row(MEMBER), (5, 1))
        # Remover devolve o profissional ao pool livre.
        removed = self.set_quota(MEMBER, None)
        self.assertTrue(removed[2])
        self.assertIsNone(self.quota_row(MEMBER))
        for index in range(3):
            self.consume(MEMBER, f"pos-remocao-{index}")
        self.assertEqual(self.wallet(), 996)

    def test_lowering_quota_below_usage_blocks_further_consumption(self):
        self.set_quota(MEMBER, 5)
        for index in range(4):
            self.consume(MEMBER, f"antes-corte-{index}")
        self.set_quota(MEMBER, 2)  # abaixo do ja consumido
        self.assertEqual(self.quota_row(MEMBER), (2, 4))
        with self.assertRaises(psycopg.errors.RaiseException):
            self.consume(MEMBER, "depois-corte")

    def test_professional_cannot_set_quotas(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as raised:
            self.set_quota(FREE, 10, actor=MEMBER)
        self.assertIn("role cannot manage member quotas", str(raised.exception))

    def test_quota_cannot_target_someone_outside_the_organization(self):
        outsider = {"membership": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as raised:
            self.set_quota(outsider, 5)
        self.assertIn("target membership not in organization", str(raised.exception))

    def test_negative_quota_is_rejected(self):
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            self.set_quota(MEMBER, -1)

    def test_quota_does_not_break_idempotency(self):
        self.set_quota(MEMBER, 5)
        first = self.consume(MEMBER, "idem-cota")
        second = self.consume(MEMBER, "idem-cota")
        self.assertTrue(first[1])
        self.assertFalse(second[1], "reenvio nao pode consumir cota de novo")
        self.assertEqual(self.quota_row(MEMBER), (5, 1))


if __name__ == "__main__":
    unittest.main()
