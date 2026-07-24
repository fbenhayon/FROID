from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ReportNavigationRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (
            ROOT / "froid-dashboard" / "src" / "main.tsx"
        ).read_text(encoding="utf-8")
        cls.session_source = (
            ROOT / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
        ).read_text(encoding="utf-8")

    def test_frontend_update_recovers_lazy_module_once(self):
        self.assertIn("vite:preloadError", self.main_source)
        self.assertIn("froid_chunk_recovery", self.main_source)
        self.assertIn("reloadOnceAfterFrontendUpdate", self.main_source)
        self.assertIn("CHUNK_RECOVERY_WINDOW_MS", self.main_source)

    def test_render_failure_has_visible_recovery_actions(self):
        self.assertIn("class AppErrorBoundary", self.main_source)
        self.assertIn("Não foi possível abrir esta tela", self.main_source)
        self.assertIn("Tentar novamente", self.main_source)
        self.assertIn("Voltar ao Dashboard", self.main_source)

    def test_report_navigation_replaces_live_session_history(self):
        self.assertIn(
            'navigate(`/session/${report.sessionId}/report`, { replace: true })',
            self.session_source,
        )


if __name__ == "__main__":
    unittest.main()
