"""Consolidacao dos saldos individuais num unico pool da clinica.

Executa contra PostgreSQL real. Cobre a etapa que ate entao nao existia em
lugar nenhum do codigo: somar o saldo remanescente de N profissionais que
partilham a mesma organizacao (clinica com CNPJ) num unico pool compartilhado.

A implementacao anterior escrevia ``balance=EXCLUDED.balance`` por profissional,
o que SOBRESCREVIA o pool. Enquanto cada profissional tinha uma organizacao
propria isso era inofensivo; assim que a clinica passa a existir, essa
sobrescrita destruiria os creditos de todos menos o ultimo da iteracao. Estes
testes travam a soma correta e a idempotencia.

Pulado automaticamente sem ``FROID_TEST_DATABASE_URL``.
"""

import os
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

DATABASE_URL = os.getenv("FROID_TEST_DATABASE_URL", "")

try:  # pragma: no cover - import guard
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

from tenant_store import TenantStore, stable_uuid  # noqa: E402


CNPJ = "12.345.678/0001-99"
# Clinica com 4 profissionais e saldos individuais diferentes.
CLINIC = [
    {"email": "ana@clinica.example", "balance": 200},
    {"email": "bruno@clinica.example", "balance": 150},
    {"email": "carla@clinica.example", "balance": 100},
    {"email": "diego@clinica.example", "balance": 50},
]
EXPECTED_POOL = 500


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class LegacyBalanceConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.store = TenantStore.__new__(TenantStore)  # sem tocar no __init__
        self.connection = psycopg.connect(DATABASE_URL, autocommit=True)
        self.organization_id = stable_uuid("organization", "cnpj", "12345678000199")
        with self.connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM credit_ledger WHERE organization_id=%s",
                (self.organization_id,),
            )
            cursor.execute(
                "DELETE FROM organization_wallets WHERE organization_id=%s",
                (self.organization_id,),
            )
            cursor.execute(
                """
                INSERT INTO organizations
                    (id, organization_type, legal_name, display_name, document)
                VALUES (%s,'clinic','Clinica CNPJ','Clinica CNPJ',%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (self.organization_id, CNPJ),
            )
            for professional in CLINIC:
                user_id = stable_uuid("user", professional["email"])
                cursor.execute(
                    "INSERT INTO users (id,email) VALUES (%s,%s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (user_id, professional["email"]),
                )

    def tearDown(self):
        self.connection.close()

    def contribute_all(self):
        with self.connection.cursor() as cursor:
            for professional in CLINIC:
                self.store._contribute_legacy_balance(
                    cursor,
                    organization_id=self.organization_id,
                    user_id=stable_uuid("user", professional["email"]),
                    balance=professional["balance"],
                    metadata={"owner_email": professional["email"]},
                )

    def pool_balance(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT balance FROM organization_wallets WHERE organization_id=%s",
                (self.organization_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def test_four_professionals_consolidate_into_one_pool(self):
        """200 + 150 + 100 + 50 = 500, nao o saldo do ultimo da iteracao."""
        self.contribute_all()
        self.assertEqual(self.pool_balance(), EXPECTED_POOL)

    def test_consolidation_is_idempotent(self):
        """Reexecutar o backfill nao pode dobrar o pool."""
        self.contribute_all()
        self.contribute_all()
        self.contribute_all()
        self.assertEqual(self.pool_balance(), EXPECTED_POOL)

    def test_each_professional_contribution_is_auditable(self):
        self.contribute_all()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT actor_user_id, delta FROM credit_ledger
                WHERE organization_id=%s AND event_type='migration_opening'
                """,
                (self.organization_id,),
            )
            contributions = {str(row[0]): row[1] for row in cursor.fetchall()}
        self.assertEqual(len(contributions), len(CLINIC))
        for professional in CLINIC:
            user_id = str(stable_uuid("user", professional["email"]))
            self.assertEqual(contributions[user_id], professional["balance"])
        self.assertEqual(sum(contributions.values()), EXPECTED_POOL)

    def test_consolidation_stops_once_the_wallet_is_activated(self):
        """Depois de ativada, a carteira compartilhada e a autoridade."""
        self.contribute_all()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE organization_wallets SET authority='shared' "
                "WHERE organization_id=%s",
                (self.organization_id,),
            )
            # Um profissional novo, ainda sem contribuicao registrada.
            novo = "erica@clinica.example"
            cursor.execute(
                "INSERT INTO users (id,email) VALUES (%s,%s) "
                "ON CONFLICT (id) DO NOTHING",
                (stable_uuid("user", novo), novo),
            )
            self.store._contribute_legacy_balance(
                cursor,
                organization_id=self.organization_id,
                user_id=stable_uuid("user", novo),
                balance=999,
                metadata={"owner_email": novo},
            )
        self.assertEqual(
            self.pool_balance(),
            EXPECTED_POOL,
            "migracao nao pode alterar uma carteira ja ativada",
        )

    def test_partial_reruns_still_reach_the_correct_total(self):
        """Backfill interrompido no meio e retomado converge para a soma."""
        with self.connection.cursor() as cursor:
            for professional in CLINIC[:2]:
                self.store._contribute_legacy_balance(
                    cursor,
                    organization_id=self.organization_id,
                    user_id=stable_uuid("user", professional["email"]),
                    balance=professional["balance"],
                    metadata={},
                )
        self.assertEqual(self.pool_balance(), 350)
        self.contribute_all()  # retomada completa
        self.assertEqual(self.pool_balance(), EXPECTED_POOL)


@unittest.skipUnless(psycopg is not None, "psycopg indisponivel")
class ClinicOrganizationIdentityTests(unittest.TestCase):
    """A organizacao da clinica deriva do CNPJ, nao do e-mail."""

    def test_same_cnpj_yields_the_same_organization_for_every_professional(self):
        ids = {
            stable_uuid("organization", "cnpj", "12345678000199")
            for _ in CLINIC
        }
        self.assertEqual(len(ids), 1)

    def test_cnpj_formatting_does_not_change_the_organization(self):
        self.assertEqual(
            stable_uuid("organization", "cnpj", "12345678000199"),
            stable_uuid("organization", "cnpj", "12345678000199"),
        )

    def test_solo_professional_still_derives_from_email(self):
        solo = stable_uuid("organization", "autonomo@example.com")
        clinic = stable_uuid("organization", "cnpj", "12345678000199")
        self.assertNotEqual(solo, clinic)


if __name__ == "__main__":
    unittest.main()
