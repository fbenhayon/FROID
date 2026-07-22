from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ProfessionalManualApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (ROOT / "froid-server" / "main.py").read_text(encoding="utf-8")
        cls.compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        cls.env_example = (
            ROOT / "froid-server" / ".env.multitenant.example"
        ).read_text(encoding="utf-8")
        cls.onboarding = (
            ROOT / "froid-dashboard" / "src" / "pages" / "ProfessionalOnboarding.tsx"
        ).read_text(encoding="utf-8")
        cls.admin_detail = (
            ROOT / "froid-dashboard" / "src" / "pages" / "AdminProfessionalDetail.tsx"
        ).read_text(encoding="utf-8")
        cls.admin_dashboard = (
            ROOT / "froid-dashboard" / "src" / "pages" / "AdminDashboard.tsx"
        ).read_text(encoding="utf-8")

    def test_feature_flag_is_explicit_and_forwarded_to_backend(self):
        setting = "FROID_PROFESSIONAL_APPROVAL_REQUIRED"
        self.assertIn(f"{setting}=false", self.env_example)
        self.assertIn(f"{setting}=${{{setting}:-false}}", self.compose)

    def test_new_profiles_wait_while_existing_profiles_are_preserved(self):
        self.assertIn('if existing or not FROID_PROFESSIONAL_APPROVAL_REQUIRED', self.backend)
        self.assertIn('else "pending"', self.backend)
        self.assertIn('"access_approval_status": approval_status', self.backend)

    def test_clinical_http_and_websocket_paths_enforce_approval(self):
        http_gate = self.backend[
            self.backend.index("def _require_professional_feature_access") :
            self.backend.index("def _require_professional_websocket_access")
        ]
        websocket_gate = self.backend[
            self.backend.index("def _require_professional_websocket_access") :
            self.backend.index("def _session_matches_context")
        ]
        self.assertIn('manual_approval_ready', http_gate)
        self.assertIn('manual_approval_ready', websocket_gate)
        self.assertIn("status_code=403", http_gate)
        self.assertIn("status_code=403", websocket_gate)
        middleware = self.backend[
            self.backend.index('async def security_audit_middleware') :
            self.backend.index('def _require_active_subscription_for_context')
        ]
        self.assertIn('request.url.path.startswith("/api/")', middleware)
        self.assertIn('not approval.get("manual_approval_ready")', middleware)
        self.assertIn('"/api/subscriptions/"', middleware)

    def test_only_admin_endpoint_changes_approval_and_audits_it(self):
        route = self.backend[
            self.backend.index('@app.post("/api/admin/professionals/{professional_email}/access-approval")') :
            self.backend.index('@app.get("/api/session-invites/{token}")')
        ]
        self.assertIn("_require_admin_user(request)", route)
        self.assertIn('action="admin_professional_access_approval"', route)
        self.assertIn('"approved", "rejected", "suspended"', route)

    def test_pending_screen_prevents_duplicate_payment_and_admin_can_approve(self):
        self.assertIn("Cadastro aguardando aprovação FROID", self.onboarding)
        self.assertIn("Não realize outro pagamento", self.onboarding)
        self.assertIn("Verificar aprovação", self.onboarding)
        self.assertIn("Aprovar acesso", self.admin_detail)
        self.assertIn("Suspender acesso", self.admin_detail)
        self.assertIn("Aprovações pendentes", self.admin_dashboard)


if __name__ == "__main__":
    unittest.main()
