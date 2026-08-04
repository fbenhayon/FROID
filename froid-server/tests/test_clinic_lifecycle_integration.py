"""Ciclo de vida completo de uma clinica, ponta a ponta.

As demais suites provam PECAS isoladas: o SQL da carteira via psycopg, a regra
de decisao pura, as rotas por assercao textual. Falta a CADEIA - e e nela que
moram os defeitos de integracao, tipicamente um wrapper Python passando
parametro na ordem errada, que um teste de SQL direto jamais pegaria.

Este arquivo percorre a jornada real de uma clinica usando exclusivamente os
metodos do ``TenantStore`` que o ``main.py`` chama em producao:

  consolidar saldos -> ativar carteira -> consumir sessoes -> definir cota ->
  cota bloquear -> relatorio refletir tudo -> politica de visibilidade

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


CNPJ_DIGITS = "55555555000155"
ORG = str(stable_uuid("organization", "cnpj", CNPJ_DIGITS))

# Clinica realista: uma gestora e tres profissionais, com saldos individuais
# diferentes que precisam virar um pool unico.
GESTORA = {"email": "gestora@ciclo.example", "role": "owner", "balance": 120}
EQUIPE = [
    {"email": "p1@ciclo.example", "role": "professional", "balance": 200},
    {"email": "p2@ciclo.example", "role": "professional", "balance": 130},
    {"email": "p3@ciclo.example", "role": "professional", "balance": 50},
]
TODOS = [GESTORA, *EQUIPE]
POOL_ESPERADO = sum(pessoa["balance"] for pessoa in TODOS)  # 500


def ids(pessoa):
    user_id = str(stable_uuid("user", pessoa["email"]))
    return {
        "user_id": user_id,
        "membership_id": str(stable_uuid("membership", ORG, user_id)),
    }


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class ClinicLifecycleTests(unittest.TestCase):
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
                for table in (
                    "credit_ledger",
                    "organization_member_quotas",
                    "organization_wallets",
                ):
                    cursor.execute(
                        f"DELETE FROM {table} WHERE organization_id=%s", (ORG,)
                    )
                cursor.execute(
                    """
                    INSERT INTO organizations
                        (id, organization_type, legal_name, display_name, document)
                    VALUES (%s,'clinic','Clinica Ciclo','Clinica Ciclo',%s)
                    ON CONFLICT (id) DO UPDATE SET report_visibility='restricted'
                    """,
                    (ORG, CNPJ_DIGITS),
                )
                for pessoa in TODOS:
                    reference = ids(pessoa)
                    cursor.execute(
                        "INSERT INTO users (id,email) VALUES (%s,%s) "
                        "ON CONFLICT (id) DO NOTHING",
                        (reference["user_id"], pessoa["email"]),
                    )
                    cursor.execute(
                        "INSERT INTO organization_memberships "
                        "(id,organization_id,user_id,status) VALUES (%s,%s,%s,'active') "
                        "ON CONFLICT (id) DO NOTHING",
                        (reference["membership_id"], ORG, reference["user_id"]),
                    )
                    cursor.execute(
                        "INSERT INTO membership_roles (membership_id,role) "
                        "VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (reference["membership_id"], pessoa["role"]),
                    )

    def consume(self, pessoa, session_id):
        reference = ids(pessoa)
        return self.store.apply_credit_event(
            organization_id=ORG,
            membership_id=reference["membership_id"],
            actor_user_id=reference["user_id"],
            delta=-1,
            event_type="consumption",
            idempotency_key=f"session:{session_id}",
            session_id=session_id,
            metadata={"source": "lifecycle-test"},
        )

    def report(self):
        return self.store.organization_usage_report(
            organization_id=ORG, membership_id=ids(GESTORA)["membership_id"]
        )

    def test_full_clinic_lifecycle_through_the_real_wrappers(self):
        gestora = ids(GESTORA)

        # 1. Consolidacao: quatro saldos individuais viram um pool unico.
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            with connection.cursor() as cursor:
                for pessoa in TODOS:
                    self.store._contribute_legacy_balance(
                        cursor,
                        organization_id=ORG,
                        user_id=ids(pessoa)["user_id"],
                        balance=pessoa["balance"],
                        metadata={"owner_email": pessoa["email"]},
                    )
        self.assertEqual(
            self.store.wallet_status(
                organization_id=ORG, membership_id=gestora["membership_id"]
            )["balance"],
            POOL_ESPERADO,
        )

        # 2. Antes da ativacao, a carteira recusa consumo.
        with self.assertRaises(Exception) as raised:
            self.consume(EQUIPE[0], "antes-da-ativacao")
        self.assertIn("shared wallet is not active", str(raised.exception))

        # 3. Ativacao exige o saldo consolidado exato.
        with self.assertRaises(Exception):
            self.store.activate_shared_wallet(
                organization_id=ORG,
                membership_id=gestora["membership_id"],
                actor_user_id=gestora["user_id"],
                expected_legacy_balance=POOL_ESPERADO - 1,
            )
        activation = self.store.activate_shared_wallet(
            organization_id=ORG,
            membership_id=gestora["membership_id"],
            actor_user_id=gestora["user_id"],
            expected_legacy_balance=POOL_ESPERADO,
        )
        self.assertEqual(activation, {"balance": POOL_ESPERADO, "activated": True})

        # 4. Consumo compartilhado: todos sacam do MESMO pool.
        for index, pessoa in enumerate(EQUIPE):
            for attempt in range(index + 1):  # 1, 2 e 3 sessoes
                self.consume(pessoa, f"ciclo-{index}-{attempt}")
        consumidas = 1 + 2 + 3
        self.assertEqual(
            self.store.wallet_status(
                organization_id=ORG, membership_id=gestora["membership_id"]
            )["balance"],
            POOL_ESPERADO - consumidas,
        )

        # 5. Reenvio do mesmo relatorio nao cobra de novo.
        repetido = self.consume(EQUIPE[0], "ciclo-0-0")
        self.assertFalse(repetido["applied"])
        self.assertEqual(
            self.store.wallet_status(
                organization_id=ORG, membership_id=gestora["membership_id"]
            )["balance"],
            POOL_ESPERADO - consumidas,
        )

        # 6. A gestora impoe cota a um profissional; os demais seguem livres.
        #
        # SEMANTICA DELIBERADA: a cota vale DALI PARA FRENTE. Quem ja usou 3
        # sessoes e recebe cota 4 pode fazer mais 4 - o contador da cota nasce
        # em zero. Descontar o historico bloquearia a pessoa no instante em que
        # a cota fosse criada, o que contraria "distribuir N sessoes a alguem"
        # (antes da cota, ela sacava do pool livremente, por desenho). Ajustar
        # uma cota existente, por outro lado, PRESERVA o ja consumido - coberto
        # em test_member_quotas_postgres.
        limitado = EQUIPE[2]
        quota = self.store.set_member_quota(
            organization_id=ORG,
            membership_id=gestora["membership_id"],
            actor_user_id=gestora["user_id"],
            target_membership_id=ids(limitado)["membership_id"],
            quota_sessions=4,
        )
        self.assertEqual(quota["quota_sessions"], 4)
        self.assertEqual(quota["consumed_sessions"], 0)
        self.assertEqual(quota["quota_remaining"], 4)

        for attempt in range(4):
            self.consume(limitado, f"ciclo-cota-{attempt}")
        with self.assertRaises(Exception) as raised:
            self.consume(limitado, "ciclo-cota-estourada")
        self.assertIn("member quota exhausted", str(raised.exception))

        # O pool ainda tem saldo: quem barrou foi a cota, nao o saldo.
        saldo = self.store.wallet_status(
            organization_id=ORG, membership_id=gestora["membership_id"]
        )["balance"]
        self.assertEqual(saldo, POOL_ESPERADO - consumidas - 4)
        # E um colega sem cota continua atendendo normalmente.
        self.consume(EQUIPE[0], "ciclo-livre-apos-cota")

        # 7. Relatorio do gestor reflete a realidade inteira.
        report = self.report()
        self.assertEqual(report["pool_balance"], saldo - 1)
        self.assertEqual(report["sessions_used_total"], consumidas + 5)
        self.assertEqual(
            sum(linha["sessions_used"] for linha in report["professionals"]),
            report["sessions_used_total"],
            "uso por profissional precisa somar o total da clinica",
        )
        por_email = {linha["email"]: linha for linha in report["professionals"]}
        self.assertEqual(por_email[limitado["email"]]["quota_sessions"], 4)
        self.assertEqual(por_email[limitado["email"]]["quota_remaining"], 0)
        self.assertIsNone(por_email[EQUIPE[0]["email"]]["quota_sessions"])
        self.assertIn("owner", por_email[GESTORA["email"]]["roles"])

        # 8. Politica de visibilidade, ida e volta.
        self.assertEqual(report["report_visibility"], "restricted")
        self.store.set_report_visibility(
            organization_id=ORG,
            membership_id=gestora["membership_id"],
            actor_user_id=gestora["user_id"],
            visibility="clinic_wide",
        )
        self.assertEqual(self.report()["report_visibility"], "clinic_wide")
        self.store.set_report_visibility(
            organization_id=ORG,
            membership_id=gestora["membership_id"],
            actor_user_id=gestora["user_id"],
            visibility="restricted",
        )
        self.assertEqual(self.report()["report_visibility"], "restricted")

        # 9. Um profissional comum nao consegue gerir creditos nem cotas.
        with self.assertRaises(Exception):
            self.store.apply_credit_event(
                organization_id=ORG,
                membership_id=ids(EQUIPE[0])["membership_id"],
                actor_user_id=ids(EQUIPE[0])["user_id"],
                delta=100,
                event_type="purchase",
                idempotency_key="ciclo-compra-indevida",
            )
        with self.assertRaises(Exception):
            self.store.set_member_quota(
                organization_id=ORG,
                membership_id=ids(EQUIPE[0])["membership_id"],
                actor_user_id=ids(EQUIPE[0])["user_id"],
                target_membership_id=ids(EQUIPE[1])["membership_id"],
                quota_sessions=99,
            )

        # 10. Nada disso alterou o saldo por vias tortas.
        self.assertEqual(
            self.store.wallet_status(
                organization_id=ORG, membership_id=gestora["membership_id"]
            )["balance"],
            report["pool_balance"],
        )


if __name__ == "__main__":
    unittest.main()
