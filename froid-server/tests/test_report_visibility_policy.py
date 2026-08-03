"""Politica de visibilidade de relatorios dentro da clinica.

Cobre as duas metades da funcionalidade:

* A REGRA DE DECISAO (``tenant_access.decide``), testada diretamente: com a
  politica desligada um profissional so alcanca o paciente atribuido a ele; com
  a politica ligada alcanca a clinica inteira - e NUNCA outra organizacao.
* O ARMAZENAMENTO da politica, exercitado contra PostgreSQL real: padrao
  seguro, alteracao pelo gestor, recusa de valor invalido e de perfil sem
  poder.

Dado sensivel de saude: o padrao e sempre 'restricted', e qualquer falha de
leitura precisa degradar para 'restricted', nunca para o acesso mais amplo.
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

from tenant_access import AccessContext, decide  # noqa: E402
from tenant_store import TenantStore  # noqa: E402

MAIN_SOURCE = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

ORG = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
OTHER_ORG = "0f0f0f0f-0f0f-4f0f-8f0f-0f0f0f0f0f0f"
GESTOR_MEMBERSHIP = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
GESTOR_USER = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


def professional_context(organization_id=ORG):
    return AccessContext.create(
        organization_id=organization_id,
        membership_id="f2222222-2222-4222-8222-222222222222",
        user_id="f1111111-1111-4111-8111-111111111111",
        roles=["professional"],
    )


class ClinicWideDecisionTests(unittest.TestCase):
    """A regra em si, sem banco."""

    def test_restricted_keeps_a_professional_on_their_own_patients(self):
        decision = decide(
            professional_context(),
            "reports.read",
            resource_organization_id=ORG,
            assigned=False,
            owns_resource=False,
            clinic_wide_reports=False,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "permission_denied")

    def test_clinic_wide_opens_colleagues_reports_in_the_same_clinic(self):
        decision = decide(
            professional_context(),
            "reports.read",
            resource_organization_id=ORG,
            assigned=False,
            owns_resource=False,
            clinic_wide_reports=True,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "clinic_wide_policy")

    def test_clinic_wide_also_opens_the_patient_record(self):
        """Analise conjunta sem o paciente seria inutil."""
        decision = decide(
            professional_context(),
            "patients.read",
            resource_organization_id=ORG,
            assigned=False,
            clinic_wide_reports=True,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "clinic_wide_policy")

    def test_clinic_wide_never_crosses_into_another_organization(self):
        """O ponto mais importante: a politica amplia DENTRO da clinica."""
        decision = decide(
            professional_context(),
            "reports.read",
            resource_organization_id=OTHER_ORG,
            assigned=False,
            owns_resource=False,
            clinic_wide_reports=True,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "cross_organization")

    def test_assigned_access_still_works_and_is_labelled_normally(self):
        decision = decide(
            professional_context(),
            "reports.read",
            resource_organization_id=ORG,
            assigned=True,
            clinic_wide_reports=False,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "report_scope")

    def test_inactive_membership_is_denied_regardless_of_the_policy(self):
        context = AccessContext.create(
            organization_id=ORG,
            membership_id=GESTOR_MEMBERSHIP,
            user_id=GESTOR_USER,
            roles=["professional"],
            status="revoked",
        )
        decision = decide(
            context, "reports.read", resource_organization_id=ORG,
            clinic_wide_reports=True,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "inactive_membership")


class VisibilityWiringTests(unittest.TestCase):
    """A politica precisa chegar ate a listagem, senao nao tem efeito."""

    def test_report_listing_passes_the_policy_into_the_decision(self):
        self.assertIn("clinic_wide_reports=clinic_wide_reports", MAIN_SOURCE)
        self.assertIn("TENANT_STORE.report_visibility(", MAIN_SOURCE)

    def test_endpoint_exists_and_is_restricted_to_managers(self):
        self.assertIn(
            '@app.put("/api/organizations/{organization_id}/report-visibility")',
            MAIN_SOURCE,
        )
        anchor = MAIN_SOURCE.index('"/api/organizations/{organization_id}/report-visibility"')
        block = MAIN_SOURCE[anchor : anchor + 1800]
        self.assertIn('"credits.manage"', block)
        self.assertIn("report_visibility.set", block)


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class ReportVisibilityStoreTests(unittest.TestCase):
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
                "UPDATE organizations SET report_visibility='restricted' WHERE id=%s",
                (ORG,),
            )

    def current(self):
        return self.store.report_visibility(
            organization_id=ORG, membership_id=GESTOR_MEMBERSHIP
        )

    def apply(self, visibility):
        return self.store.set_report_visibility(
            organization_id=ORG,
            membership_id=GESTOR_MEMBERSHIP,
            actor_user_id=GESTOR_USER,
            visibility=visibility,
        )

    def test_default_is_restricted(self):
        self.assertEqual(self.current(), "restricted")

    def test_manager_can_open_and_close_visibility(self):
        opened = self.apply("clinic_wide")
        self.assertTrue(opened["changed"])
        self.assertEqual(self.current(), "clinic_wide")
        closed = self.apply("restricted")
        self.assertTrue(closed["changed"])
        self.assertEqual(self.current(), "restricted")

    def test_setting_the_same_value_is_inert(self):
        self.apply("clinic_wide")
        again = self.apply("clinic_wide")
        self.assertFalse(again["changed"])

    def test_invalid_visibility_is_rejected(self):
        with self.assertRaises(Exception) as raised:
            self.apply("everyone")
        self.assertIn("invalid report visibility", str(raised.exception))
        self.assertEqual(self.current(), "restricted")

    def test_professional_cannot_change_the_policy(self):
        with self.assertRaises(Exception) as raised:
            self.store.set_report_visibility(
                organization_id=ORG,
                membership_id="f2222222-2222-4222-8222-222222222222",
                actor_user_id="f1111111-1111-4111-8111-111111111111",
                visibility="clinic_wide",
            )
        self.assertIn("role cannot manage report visibility", str(raised.exception))
        self.assertEqual(self.current(), "restricted")


if __name__ == "__main__":
    unittest.main()
