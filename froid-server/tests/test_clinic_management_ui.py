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

    def test_invite_is_offered_only_to_managers(self):
        self.assertIn("members/invitations", self.page)
        self.assertIn("{isManager && (", self.page)

    def test_invitation_token_is_presented_as_single_use_and_not_persisted(self):
        """O servidor emite o token uma vez; a tela nao pode dar a entender que da para recuperar."""
        self.assertIn("uma única vez", self.page)
        self.assertIn("canal seguro", self.page)
        self.assertIn("Copiar código", self.page)
        # Nunca gravar o token em armazenamento do navegador.
        self.assertNotIn("localStorage.setItem", self.page)
        self.assertNotIn("sessionStorage", self.page)

    def test_owner_role_is_not_offered_in_the_invite_form(self):
        """Convidar outro proprietario e recusado pelo servidor; nao oferecer."""
        anchor = self.page.index('<select\n                      value={inviteRole}')
        block = self.page[anchor : anchor + 600]
        self.assertIn('value="professional"', block)
        self.assertIn('value="supervisor"', block)
        self.assertIn('value="administrator"', block)
        self.assertNotIn('value="owner"', block)

    def test_empty_quota_field_means_free_pool(self):
        """Cota vazia precisa enviar null, nao zero - zero bloquearia o profissional."""
        self.assertIn('const quota = trimmed === "" ? null : Number(trimmed);', self.page)
        self.assertIn("quota_sessions: quota === null ? null : Math.floor(quota)", self.page)


class LegacyFallbackTests(unittest.TestCase):
    """Autonomo nao pode ver uma area de gestao que nao existe para ele."""

    @classmethod
    def setUpClass(cls):
        cls.dashboard = (DASHBOARD / "pages" / "Dashboard.tsx").read_text(
            encoding="utf-8"
        )
        cls.backend = (
            Path(__file__).resolve().parents[1] / "main.py"
        ).read_text(encoding="utf-8")

    def test_backend_marks_synthesized_solo_organizations(self):
        self.assertIn('"legacy_fallback": True', self.backend)
        # O modo legado atribui owner a todo profissional; sem a marca acima o
        # botao de gestao apareceria para todos.
        self.assertIn('"roles": ["owner", "professional"]', self.backend)

    def test_dashboard_hides_management_for_legacy_fallback(self):
        self.assertIn("legacy_fallback) return false", self.dashboard)


if __name__ == "__main__":
    unittest.main()
