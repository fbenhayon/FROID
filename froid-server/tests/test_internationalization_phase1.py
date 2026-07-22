import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from localization import (  # noqa: E402
    SESSION_LANGUAGES,
    normalize_session_locale,
    session_language,
    summary_prompt,
    transcription_prompt,
)


class InternationalizationPhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.dashboard_source = (
            SERVER_DIR.parent / "froid-dashboard" / "src" / "pages" / "Dashboard.tsx"
        ).read_text(encoding="utf-8")

    def test_phase1_locales_have_provider_hints(self):
        self.assertEqual(
            {locale: language.provider_language for locale, language in SESSION_LANGUAGES.items()},
            {"pt-BR": "pt", "en-US": "en", "fr-FR": "fr", "es-ES": "es"},
        )

    def test_locale_normalization_is_allowlisted_and_fail_safe(self):
        self.assertEqual(normalize_session_locale("en"), "en-US")
        self.assertEqual(normalize_session_locale("FR-fr"), "fr-FR")
        self.assertEqual(normalize_session_locale("unsupported"), "pt-BR")
        self.assertEqual(normalize_session_locale("unsupported", "es-ES"), "es-ES")

    def test_transcription_prompt_preserves_original_language(self):
        prompt = transcription_prompt("fr-FR", "DR. - contexte précédent")
        self.assertIn("français de France", prompt)
        self.assertIn("Do not translate", prompt)
        self.assertIn("contexte précédent", prompt)
        self.assertLessEqual(len(prompt.rsplit("\n", 1)[-1]), 900)

    def test_summary_prompt_targets_report_locale_without_changing_transcript(self):
        prompt = summary_prompt("The patient spoke in English.", 0, 10, "es-ES")
        self.assertIn("español de España", prompt)
        self.assertIn("The patient spoke in English.", prompt)
        self.assertIn("Do not diagnose", prompt)

    def test_localized_empty_states_exist(self):
        for locale in ("en-US", "fr-FR", "es-ES"):
            language = session_language(locale)
            self.assertTrue(language.no_speech_theme)
            self.assertTrue(language.no_speech_summary)

    def test_transcription_route_uses_allowlisted_session_language(self):
        route = self.main_source[self.main_source.index('@app.post("/api/transcribe")') :]
        route = route[: route.index('@app.post("/api/session-summary")')]
        self.assertIn('normalize_session_locale(body.get("spoken_language"))', route)
        self.assertIn("transcription_prompt(", route)
        self.assertIn("spoken_language,", route)
        self.assertNotIn('"language": "pt"', route)

    def test_invite_persists_all_independent_locale_fields(self):
        invite_route = self.main_source[self.main_source.index('@app.post("/api/session-invites")') :]
        invite_route = invite_route[: invite_route.index('@app.get("/api/professional/receivables")')]
        for field in (
            "patient_ui_locale",
            "spoken_language",
            "analysis_language",
            "report_locale",
        ):
            self.assertIn(f'"{field}"', invite_route)

    def test_professional_session_configuration_is_server_authoritative(self):
        route = self.main_source[
            self.main_source.index('@app.get("/api/sessions/{session_id}/configuration")') :
        ]
        route = route[: route.index('@app.get("/api/professional/receivables")')]
        self.assertIn("_require_current_user(request)", route)
        self.assertIn("_require_professional_feature_access(request)", route)
        self.assertIn('"spoken_language"', route)
        self.assertNotIn('"token"', route)
        self.assertNotIn('"payment"', route)

    def test_transcription_route_emits_content_free_quality_telemetry(self):
        route = self.main_source[self.main_source.index('@app.post("/api/transcribe")') :]
        route = route[: route.index('@app.post("/api/session-summary")')]
        self.assertIn('"event": "froid.transcription"', route)
        self.assertIn('"latency_ms"', route)
        self.assertIn('"audio_bytes"', route)
        audit_block = route[route.index("AUDIT_LOGGER.info(") : route.index("return {")]
        self.assertNotIn('"text"', audit_block)
        self.assertNotIn("transcript,", audit_block)

    def test_professional_dashboard_uses_accessible_froid_language_control(self):
        self.assertIn('role="radiogroup"', self.dashboard_source)
        self.assertIn('role="radio"', self.dashboard_source)
        self.assertIn('aria-checked={selected}', self.dashboard_source)
        self.assertIn('bg-cyan-700 text-white', self.dashboard_source)
        self.assertNotIn('<select\n              value={defaultSessionLocale}', self.dashboard_source)


if __name__ == "__main__":
    unittest.main()
