"""Endpoints de gestao da clinica: relatorio de uso e cota por profissional.

Duas camadas:

* A parte funcional exercita ``TenantStore.set_member_quota`` contra PostgreSQL
  real (definir, ajustar, remover, e recusar alvo de fora da organizacao).
* A parte de autorizacao e textual, porque main.py depende de FastAPI e nao e
  importavel aqui - mesmo padrao dos demais testes deste diretorio. O que ela
  trava e o essencial: QUAL permissao cada endpoint exige, e portanto quais
  papeis conseguem chamar cada um.
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

from tenant_access import ROLE_PERMISSIONS  # noqa: E402
from tenant_store import TenantStore  # noqa: E402

MAIN_SOURCE = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

ORG = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"  # mesma clinica do relatorio
GESTOR_MEMBERSHIP = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
GESTOR_USER = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
BRUNO_MEMBERSHIP = "f4444444-4444-4444-8444-444444444444"


class EndpointAuthorizationTests(unittest.TestCase):
    """Quem pode ler o relatorio e quem pode mexer em cota."""

    def test_usage_report_endpoint_requires_read_all(self):
        self.assertIn('@app.get("/api/organizations/{organization_id}/usage")', MAIN_SOURCE)
        anchor = MAIN_SOURCE.index('"/api/organizations/{organization_id}/usage"')
        block = MAIN_SOURCE[anchor : anchor + 700]
        self.assertIn('"reports.read_all"', block)

    def test_quota_endpoint_requires_credits_manage(self):
        self.assertIn(
            '@app.put("/api/organizations/{organization_id}/members/{target_membership_id}/quota")',
            MAIN_SOURCE,
        )
        anchor = MAIN_SOURCE.index(
            '"/api/organizations/{organization_id}/members/{target_membership_id}/quota"'
        )
        block = MAIN_SOURCE[anchor : anchor + 900]
        self.assertIn('"credits.manage"', block)

    def test_a_plain_professional_can_read_neither(self):
        professional = ROLE_PERMISSIONS["professional"]
        self.assertNotIn("reports.read_all", professional)
        self.assertNotIn("credits.manage", professional)

    def test_supervisor_reads_usage_but_cannot_change_quotas(self):
        supervisor = ROLE_PERMISSIONS["supervisor"]
        self.assertIn("reports.read_all", supervisor)
        self.assertNotIn("credits.manage", supervisor)

    def test_manager_roles_can_do_both(self):
        for role in ("owner", "administrator"):
            self.assertIn("reports.read_all", ROLE_PERMISSIONS[role])
            self.assertIn("credits.manage", ROLE_PERMISSIONS[role])

    def test_identity_snapshot_does_not_serialize_legacy_admin_audit_state(self):
        self.assertNotIn('"admin_audit_events": ADMIN_AUDIT_EVENTS[-1000:]', MAIN_SOURCE)

    def test_quota_changes_are_audited(self):
        anchor = MAIN_SOURCE.index(
            '"/api/organizations/{organization_id}/members/{target_membership_id}/quota"'
        )
        block = MAIN_SOURCE[anchor : anchor + 2200]
        self.assertIn("record_access_audit", block)
        self.assertIn("member_quota.set", block)
        self.assertIn("member_quota.remove", block)


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class SetMemberQuotaStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = TenantStore(
            mode="dual",
            database_url=DATABASE_URL,
            migration_path=SERVER_DIR / "migrations",
            runtime_database_url=DATABASE_URL,
        )

    def tearDown(self):
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            connection.execute(
                "DELETE FROM organization_member_quotas "
                "WHERE organization_id=%s AND membership_id=%s",
                (ORG, BRUNO_MEMBERSHIP),
            )

    def set_quota(self, quota):
        return self.store.set_member_quota(
            organization_id=ORG,
            membership_id=GESTOR_MEMBERSHIP,
            actor_user_id=GESTOR_USER,
            target_membership_id=BRUNO_MEMBERSHIP,
            quota_sessions=quota,
        )

    def test_manager_sets_a_quota(self):
        result = self.set_quota(12)
        self.assertFalse(result["removed"])
        self.assertEqual(result["quota_sessions"], 12)
        self.assertEqual(result["quota_remaining"], 12)

    def test_quota_can_be_adjusted_preserving_consumption(self):
        self.set_quota(12)
        adjusted = self.set_quota(30)
        self.assertEqual(adjusted["quota_sessions"], 30)
        self.assertEqual(
            adjusted["consumed_sessions"], 0, "ajustar nao pode zerar historico"
        )

    def test_null_quota_returns_the_professional_to_the_free_pool(self):
        self.set_quota(5)
        removed = self.set_quota(None)
        self.assertTrue(removed["removed"])
        self.assertIsNone(removed["quota_sessions"])
        with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
            row = connection.execute(
                "SELECT 1 FROM organization_member_quotas "
                "WHERE organization_id=%s AND membership_id=%s",
                (ORG, BRUNO_MEMBERSHIP),
            ).fetchone()
        self.assertIsNone(row)

    def test_target_outside_the_organization_is_rejected(self):
        with self.assertRaises(Exception) as raised:
            self.store.set_member_quota(
                organization_id=ORG,
                membership_id=GESTOR_MEMBERSHIP,
                actor_user_id=GESTOR_USER,
                target_membership_id="00000000-0000-4000-8000-000000000000",
                quota_sessions=5,
            )
        self.assertIn("target membership not in organization", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
