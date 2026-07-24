import hashlib
import hmac
import json
from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from subscriptions import StripeSignatureError, verify_stripe_event
from secure_tokens import TextCipher, TokenCipher
from cryptography.fernet import Fernet


class Phase4SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.store_source = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        cls.compose_source = (PROJECT_ROOT / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        cls.frontend_dockerfile = (
            PROJECT_ROOT / "froid-dashboard" / "Dockerfile"
        ).read_text(encoding="utf-8")
        cls.migration = (
            SERVER_DIR / "migrations" / "006_subscription_entitlements.sql"
        ).read_text(encoding="utf-8")
        cls.hardening = (
            SERVER_DIR / "migrations" / "007_multitenant_security_hardening.sql"
        ).read_text(encoding="utf-8")

    def test_development_auth_is_fail_closed(self):
        self.assertIn('os.getenv("GOOGLE_AUTH_DEV_FALLBACK", "false")', self.main_source)
        self.assertIn("if FROID_LOCAL_AUTH_PASSWORD and FROID_LOCAL_AUTH_EMAILS", self.main_source)
        self.assertIn("raise HTTPException(status_code=403, detail=\"login local desabilitado\")", self.main_source)

    def test_clinical_routes_require_commercial_access_gate(self):
        for route in (
            "/session/create", "/api/session-invites", "/api/session-events/latest",
            "/api/session-events", "/api/session-waiting", "/api/froid-explica/query",
            "/api/insights", "/api/knowledge", "/api/transcribe",
            "/api/session-summary",
        ):
            route_index = self.main_source.index(f'"{route}"')
            next_block = self.main_source[route_index:route_index + 500]
            self.assertIn("_require_professional_feature_access(request)", next_block, route)

    def test_subscription_enforcement_is_central_and_fail_closed(self):
        authorization_index = self.main_source.index("def _authorize_tenant_request")
        authorization_block = self.main_source[authorization_index:authorization_index + 900]
        self.assertIn("_require_active_subscription_for_context(context)", authorization_block)
        gate_index = self.main_source.index("def _require_active_subscription_for_context")
        gate_block = self.main_source[gate_index:gate_index + 1800]
        self.assertIn("if not TENANT_STORE.enabled:", gate_block)
        self.assertIn("status_code=503", gate_block)
        self.assertIn("status_code=402", gate_block)

    def test_professional_websockets_use_the_subscription_gate(self):
        self.assertGreaterEqual(
            self.main_source.count("_require_professional_websocket_access(user)"),
            2,
        )

    def test_sessions_and_reports_are_bound_to_one_organization(self):
        self.assertIn("SESSION_ORGANIZATIONS", self.main_source)
        self.assertGreaterEqual(self.main_source.count("_session_matches_context("), 4)
        self.assertGreaterEqual(
            self.main_source.count("relatório pertence a outra organização"),
            4,
        )
        self.assertIn("def scoped_ref(owner:", self.store_source)

    def test_every_http_action_has_content_safe_audit_correlation(self):
        self.assertIn('@app.middleware("http")', self.main_source)
        self.assertIn('"event": "froid.http_audit"', self.main_source)
        self.assertIn('AUDIT_LOGGER = logging.getLogger("uvicorn.error")', self.main_source)
        self.assertNotIn('AUDIT_LOGGER = logging.getLogger("uvicorn.access")', self.main_source)
        self.assertIn('resource_type="api_route"', self.main_source)
        middleware_start = self.main_source.index("async def security_audit_middleware")
        middleware_end = self.main_source.index(
            "def _require_active_subscription_for_context", middleware_start
        )
        middleware = self.main_source[middleware_start:middleware_end]
        for sensitive_name in ("transcript", "authorization", "access_token", "password"):
            self.assertNotIn(sensitive_name, middleware.lower())

    def test_realtime_clinical_connections_are_audited(self):
        self.assertIn('"event": "froid.websocket_audit"', self.main_source)
        self.assertGreaterEqual(
            self.main_source.count("await _record_websocket_audit("),
            13,
        )
        self.assertIn('outcome="denied"', self.main_source)

    def test_anonymous_datamart_requires_anonymization_and_excludes_literal_speech(self):
        self.assertIn("FROID_DATAMART_PSEUDONYM_KEY", self.main_source)
        self.assertIn("ingestion_basis='post_anonymization'", self.main_source)
        self.assertNotIn("patientSummaryAnon\") or patient_text", self.main_source)
        self.assertNotIn("professionalSummaryAnon\") or professional_text", self.main_source)
        self.assertIn('"",\n                    "",\n                    "",', self.main_source)

    def test_subscription_tables_have_rls_and_idempotency(self):
        self.assertIn("ALTER TABLE organization_subscriptions ENABLE ROW LEVEL SECURITY", self.migration)
        self.assertIn("ALTER TABLE organization_subscriptions NO FORCE ROW LEVEL SECURITY", self.migration)
        self.assertIn("froid_membership_is_active()", self.migration)
        self.assertIn("event_id text PRIMARY KEY", self.migration)
        self.assertIn("CHECK (code IN ('pro', 'plus', 'master'))", self.migration)

    def test_stripe_signature_verification_and_replay_tolerance(self):
        payload = json.dumps({"id": "evt_test", "type": "checkout.session.completed"}).encode()
        timestamp = 1_700_000_000
        secret = "whsec_unit_test"
        digest = hmac.new(
            secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        event = verify_stripe_event(
            payload, f"t={timestamp},v1={digest}", secret, now=timestamp
        )
        self.assertEqual(event["id"], "evt_test")
        with self.assertRaises(StripeSignatureError):
            verify_stripe_event(
                payload, f"t={timestamp},v1={digest}", secret, now=timestamp + 301
            )
        with self.assertRaises(StripeSignatureError):
            verify_stripe_event(
                payload, f"t={timestamp},v1=invalid", secret, now=timestamp
            )

    def test_google_oauth_tokens_are_encrypted_at_rest(self):
        cipher = TokenCipher([Fernet.generate_key().decode("ascii")])
        protected = cipher.protect({
            "google_email": "professional@example.com",
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
        })
        serialized = json.dumps(protected)
        self.assertNotIn("access-secret", serialized)
        self.assertNotIn("refresh-secret", serialized)
        revealed = cipher.reveal(protected)
        self.assertEqual(revealed["access_token"], "access-secret")
        self.assertEqual(revealed["refresh_token"], "refresh-secret")

    def test_google_sign_in_and_calendar_use_separate_oauth_clients(self):
        self.assertIn("GOOGLE_AUTH_CLIENT_ID", self.main_source)
        self.assertIn("GOOGLE_CALENDAR_CLIENT_ID", self.main_source)
        self.assertIn("GOOGLE_CALENDAR_CLIENT_SECRET", self.main_source)
        self.assertIn(
            "VITE_GOOGLE_CLIENT_ID=${GOOGLE_AUTH_CLIENT_ID:-",
            self.compose_source,
        )
        self.assertIn("ARG VITE_GOOGLE_CLIENT_ID", self.frontend_dockerfile)
        verify_start = self.main_source.index("async def _verify_google_credential")
        verify_end = self.main_source.index(
            "\n\nasync def froid_stream_loop", verify_start
        )
        verify_source = self.main_source[verify_start:verify_end]
        self.assertIn("GOOGLE_AUTH_CLIENT_ID", verify_source)
        self.assertNotIn("GOOGLE_CALENDAR_CLIENT_ID", verify_source)
        calendar_start = self.main_source.index("def _calendar_auth_url")
        calendar_end = self.main_source.index(
            "\n\nasync def _refresh_google_calendar_token", calendar_start
        )
        calendar_source = self.main_source[calendar_start:calendar_end]
        self.assertIn("GOOGLE_CALENDAR_CLIENT_ID", calendar_source)
        self.assertIn("GOOGLE_CALENDAR_CLIENT_SECRET", calendar_source)

    def test_calendar_selection_is_user_controlled_and_server_verified(self):
        route_start = self.main_source.index(
            '@app.post("/api/google-calendar/select-calendar")'
        )
        route_end = self.main_source.index(
            '@app.get("/api/google-calendar/events")', route_start
        )
        route_source = self.main_source[route_start:route_end]
        self.assertIn("calendarList/", route_source)
        self.assertIn('calendar.get("accessRole") != "owner"', route_source)
        self.assertIn('"selected_calendar_id": calendar_id', route_source)
        self.assertIn("verified_summary", route_source)
        self.assertIn('"recommended_calendar_id": recommended', self.main_source)

    def test_encrypted_token_survives_a_locked_state_save(self):
        cipher = TokenCipher([Fernet.generate_key().decode("ascii")])
        protected = cipher.protect({"access_token": "access-secret"})
        locked = {
            **protected,
            "token_storage_locked": True,
            "token_storage_error": True,
        }
        self.assertEqual(
            cipher.protect(locked)["oauth_tokens_encrypted"],
            protected["oauth_tokens_encrypted"],
        )

    def test_google_token_rotation_detects_an_old_key(self):
        old_key = Fernet.generate_key().decode("ascii")
        new_key = Fernet.generate_key().decode("ascii")
        old_cipher = TokenCipher([old_key])
        protected = old_cipher.protect({"access_token": "access-secret"})
        rotating_cipher = TokenCipher([new_key, old_key])
        self.assertTrue(rotating_cipher.needs_rotation(protected))
        self.assertEqual(
            rotating_cipher.reveal(protected)["access_token"],
            "access-secret",
        )

    def test_runtime_clinical_policies_require_active_membership_and_role(self):
        self.assertGreaterEqual(self.hardening.count("froid_membership_is_active()"), 24)
        self.assertIn("froid_has_role(ARRAY['professional']", self.hardening)
        self.assertIn("DROP POLICY IF EXISTS consents_read", self.hardening)
        self.assertIn("REVOKE DELETE ON membership_roles", self.hardening)
        self.assertIn("patient_assignments_one_active_primary", self.hardening)

    def test_token_migration_runs_after_mirror_helper_definition(self):
        mirror_index = self.main_source.index("def _mirror_legacy_state_to_postgres")
        migration_index = self.main_source.index("if CALENDAR_TOKEN_MIGRATION_REQUIRED:")
        self.assertLess(mirror_index, migration_index)

    def test_clinical_transcript_is_encrypted_at_rest(self):
        cipher = TextCipher([Fernet.generate_key().decode("ascii")])
        protected = cipher.protect(
            {"session_id": "session-1", "transcript": "DR. - contexto clínico"},
            "transcript", "transcript_encrypted",
        )
        self.assertNotIn("contexto clínico", json.dumps(protected))
        revealed = cipher.reveal(protected, "transcript", "transcript_encrypted")
        self.assertEqual(revealed["transcript"], "DR. - contexto clínico")

    def test_postgres_mirror_reads_the_protected_transcript(self):
        self.assertIn(
            "_load_session_reports(reveal_transcripts=False)",
            self.main_source,
        )

    def test_session_archive_requires_the_complete_transcript(self):
        self.assertIn("transcrição integral obrigatória", self.main_source)
        self.assertIn('report.pop("transcript_encrypted", None)', self.main_source)

    def test_insights_model_and_context_limits_are_server_owned(self):
        self.assertIn('"model": OPENAI_MODEL', self.main_source)
        self.assertNotIn('body.get("model", OPENAI_MODEL)', self.main_source)
        self.assertIn("total_chars > 50_000", self.main_source)


if __name__ == "__main__":
    unittest.main()
