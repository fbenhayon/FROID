"""Tela de gestao da clinica: rota, visibilidade do acesso e permissoes.

A tela consome os endpoints de gestao ja provados no backend. O que precisa
ficar travado aqui e o que uma regressao de interface poderia estragar em
silencio: quem enxerga o botao, quem consegue EDITAR (contra apenas ler), e o
tratamento do 409 enquanto o multi-organizacao nao esta ativado no servidor.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "froid-dashboard" / "src"


class ClinicManagementUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (DASHBOARD / "pages" / "ClinicManagement.tsx").read_text(
            encoding="utf-8"
        )
        cls.app = (DASHBOARD / "App.tsx").read_text(encoding="utf-8")
        cls.dashboard = (DASHBOARD / "pages" / "Dashboard.tsx").read_text(
            encoding="utf-8"
        )

    def test_route_is_registered_behind_the_clinical_guard(self):
        self.assertIn('path="/clinica"', self.app)
        self.assertIn("clinicalElement(<ClinicManagement user={user} />)", self.app)

    def test_entry_point_is_hidden_from_solo_professionals(self):
        self.assertIn("isClinicManager", self.dashboard)
        self.assertIn("{isClinicManager && (", self.dashboard)
        for role in ("owner", "administrator", "supervisor"):
            self.assertIn(f'"{role}"', self.dashboard)

    def test_only_managers_can_edit_quota_and_visibility(self):
        """Supervisor le o relatorio, mas nao altera cota nem visibilidade."""
        self.assertIn(
            'const MANAGER_ROLES = new Set(["owner", "administrator"]);', self.page
        )
        self.assertIn("disabled={!isManager", self.page)
        self.assertIn("{isManager && (", self.page)

    def test_multitenant_disabled_is_explained_not_shown_as_an_error(self):
        self.assertIn("response.status === 409", self.page)
        self.assertIn("ainda não está ativada neste servidor", self.page)

    def test_forbidden_is_handled_separately_from_a_crash(self):
        self.assertIn("response.status === 403", self.page)

    def test_page_reads_the_endpoints_that_were_proven_in_the_backend(self):
        self.assertIn("/usage", self.page)
        self.assertIn("/report-visibility", self.page)
        self.assertIn("/quota", self.page)

    def test_empty_quota_field_means_free_pool(self):
        """Cota vazia precisa enviar null, nao zero - zero bloquearia o profissional."""
        self.assertIn('const quota = trimmed === "" ? null : Number(trimmed);', self.page)
        self.assertIn("quota_sessions: quota === null ? null : Math.floor(quota)", self.page)


if __name__ == "__main__":
    unittest.main()
