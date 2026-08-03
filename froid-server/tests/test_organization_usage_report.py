"""Relatorio consolidado da clinica, executado contra PostgreSQL real.

Responde as tres perguntas do gestor num unico lugar: quanto sobrou de saldo
para a clinica, quanto cada profissional consumiu, e quantos pacientes cada um
atende. O consumo por profissional sai do ``credit_ledger`` (atribuido ao ator
de cada debito), que e a unica fonte fiel - os contadores legados por
profissional viram projecao do saldo compartilhado e nao expressam quem gastou
o que.

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

from tenant_store import TenantStore  # noqa: E402


ORG = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
GESTOR = {
    "user": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "membership": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "email": "gestor@relatorio.example",
    "role": "owner",
    "sessions": 2,
}
ANA = {
    "user": "f1111111-1111-4111-8111-111111111111",
    "membership": "f2222222-2222-4222-8222-222222222222",
    "email": "ana@relatorio.example",
    "role": "professional",
    "sessions": 5,
}
BRUNO = {
    "user": "f3333333-3333-4333-8333-333333333333",
    "membership": "f4444444-4444-4444-8444-444444444444",
    "email": "bruno@relatorio.example",
    "role": "professional",
    "sessions": 3,
}
TEAM = [ANA, BRUNO, GESTOR]


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class OrganizationUsageReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = TenantStore(
            mode="dual",
            database_url=DATABASE_URL,
            migration_path=SERVER_DIR / "migrations",
            runtime_database_url=DATABASE_URL,
        )
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM credit_ledger WHERE organization_id=%s", (ORG,)
                )
                cursor.execute(
                    "DELETE FROM organization_member_quotas WHERE organization_id=%s",
                    (ORG,),
                )
                cursor.execute(
                    """
                    INSERT INTO organizations
                        (id, organization_type, legal_name, display_name, document)
                    VALUES (%s,'clinic','Clinica Relatorio','Clinica Relatorio',
                            '77.777.777/0001-77')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (ORG,),
                )
                cursor.execute(
                    """
                    INSERT INTO organization_wallets (organization_id, balance, authority)
                    VALUES (%s,500,'shared')
                    ON CONFLICT (organization_id) DO UPDATE
                    SET balance=500, authority='shared'
                    """,
                    (ORG,),
                )
                for person in TEAM:
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
                        "INSERT INTO membership_roles (membership_id,role) "
                        "VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (person["membership"], person["role"]),
                    )

                # Consumos reais, atribuidos a cada profissional.
                for person in TEAM:
                    for index in range(person["sessions"]):
                        cursor.execute(
                            "SELECT set_config('app.organization_id', %s, false)", (ORG,)
                        )
                        cursor.execute(
                            "SELECT set_config('app.membership_id', %s, false)",
                            (person["membership"],),
                        )
                        cursor.execute(
                            """
                            SELECT froid_apply_credit_event(
                                %s,%s,%s,-1,'consumption',%s,%s,'{}'::jsonb)
                            """,
                            (
                                ORG,
                                person["membership"],
                                person["user"],
                                f"relatorio:{person['email']}:{index}",
                                f"sess-{index}",
                            ),
                        )

                # Ana tem cota; Bruno nao. Pacientes atribuidos a cada uma.
                cursor.execute(
                    "INSERT INTO organization_member_quotas "
                    "(organization_id,membership_id,quota_sessions,consumed_sessions) "
                    "VALUES (%s,%s,20,%s) ON CONFLICT DO NOTHING",
                    (ORG, ANA["membership"], ANA["sessions"]),
                )
                for slot, owner in enumerate([ANA, ANA, ANA, BRUNO]):
                    patient_id = f"a0000000-0000-4000-8000-00000000000{slot}"
                    cursor.execute(
                        "INSERT INTO patients (id,organization_id,full_name) "
                        "VALUES (%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                        (patient_id, ORG, f"Paciente {slot}"),
                    )
                    cursor.execute(
                        "INSERT INTO patient_assignments "
                        "(id,organization_id,patient_id,membership_id,assignment_type) "
                        "VALUES (%s,%s,%s,%s,'primary') ON CONFLICT DO NOTHING",
                        (
                            f"b0000000-0000-4000-8000-00000000000{slot}",
                            ORG,
                            patient_id,
                            owner["membership"],
                        ),
                    )

    def report(self):
        return self.store.organization_usage_report(
            organization_id=ORG, membership_id=GESTOR["membership"]
        )

    def by_email(self):
        return {row["email"]: row for row in self.report()["professionals"]}

    def test_reports_how_many_sessions_remain_for_the_clinic(self):
        report = self.report()
        total_consumed = sum(person["sessions"] for person in TEAM)
        self.assertEqual(report["pool_balance"], 500 - total_consumed)
        self.assertEqual(report["sessions_used_total"], total_consumed)
        self.assertEqual(report["pool_authority"], "shared")

    def test_identifies_each_professional_and_their_usage(self):
        rows = self.by_email()
        self.assertEqual(len(rows), len(TEAM))
        for person in TEAM:
            self.assertEqual(
                rows[person["email"]]["sessions_used"],
                person["sessions"],
                f"uso incorreto para {person['email']}",
            )

    def test_per_professional_usage_sums_to_the_clinic_total(self):
        report = self.report()
        self.assertEqual(
            sum(row["sessions_used"] for row in report["professionals"]),
            report["sessions_used_total"],
        )

    def test_reports_patients_per_professional(self):
        rows = self.by_email()
        self.assertEqual(rows[ANA["email"]]["patients"], 3)
        self.assertEqual(rows[BRUNO["email"]]["patients"], 1)
        self.assertEqual(rows[GESTOR["email"]]["patients"], 0)

    def test_reports_quota_only_for_whoever_has_one(self):
        rows = self.by_email()
        self.assertEqual(rows[ANA["email"]]["quota_sessions"], 20)
        self.assertEqual(rows[ANA["email"]]["quota_remaining"], 20 - ANA["sessions"])
        self.assertIsNone(
            rows[BRUNO["email"]]["quota_sessions"], "sem cota = pool livre"
        )
        self.assertIsNone(rows[BRUNO["email"]]["quota_remaining"])

    def test_reports_roles_so_the_manager_is_identifiable(self):
        rows = self.by_email()
        self.assertIn("owner", rows[GESTOR["email"]]["roles"])
        self.assertEqual(rows[ANA["email"]]["roles"], ["professional"])


if __name__ == "__main__":
    unittest.main()
