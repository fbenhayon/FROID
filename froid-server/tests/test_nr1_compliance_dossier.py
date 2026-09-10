from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_store import canonical_json, sha256_json


MIGRATION = (SERVER_DIR / "migrations" / "031_nr1_compliance_dossier.sql").read_text(encoding="utf-8")
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
DASHBOARD = (SERVER_DIR.parent / "froid-dashboard" / "src" / "pages" / "Nr1Dossier.tsx").read_text(encoding="utf-8")


class DossierIntegrityTests(unittest.TestCase):
    def test_canonical_hash_is_independent_of_dictionary_order(self):
        first = {"b": [2, 1], "a": {"z": True, "x": None}}
        second = {"a": {"x": None, "z": True}, "b": [2, 1]}
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(sha256_json(first), sha256_json(second))
        self.assertEqual(len(sha256_json(first)), 64)

    def test_versions_are_append_only_chained_and_runtime_cannot_mutate(self):
        self.assertIn("previous_sha256", MIGRATION)
        self.assertIn("psychosocial_compliance_dossiers is append-only", MIGRATION)
        self.assertIn("REVOKE UPDATE, DELETE ON psychosocial_compliance_dossiers", MIGRATION)
        self.assertIn("UNIQUE (organization_id, version)", MIGRATION)
        self.assertIn("UNIQUE (organization_id, content_sha256)", MIGRATION)

    def test_sealing_is_serialized_and_audited(self):
        seal = STORE[STORE.index("def nr1_seal_compliance_dossier"):]
        seal = seal[:seal.index("def nr1_get_compliance_dossier")]
        self.assertIn("pg_advisory_xact_lock", seal)
        # FOR SHARE também exige UPDATE no PostgreSQL. A tabela é append-only e
        # o runtime deliberadamente não tem esse privilégio; o advisory lock já
        # serializa a numeração sem enfraquecer a imutabilidade.
        self.assertNotIn("FOR SHARE", seal)
        self.assertIn("nr1.dossier.seal", seal)
        self.assertIn("sha256_json(payload)", seal)


class DossierPrivacyAndFlowTests(unittest.TestCase):
    def test_payload_does_not_query_individual_answers(self):
        payload = STORE[STORE.index("def _nr1_dossier_payload"):]
        payload = payload[:payload.index("def nr1_compliance_dossier_preview")]
        self.assertNotIn("FROM assessment_responses", payload)
        self.assertNotIn("JOIN assessment_responses", payload)
        self.assertNotIn("assessment_response_items", payload)
        self.assertIn("froid_nr1_campaign_response_counts", payload)

    def test_read_and_seal_have_distinct_permissions(self):
        self.assertIn('request, organization_id, "nr1.aggregate.read"', MAIN)
        self.assertIn('request, organization_id, "nr1.action_plan.manage"', MAIN)
        self.assertIn('@app.post("/api/organizations/{organization_id}/nr1/dossiers"', MAIN)

    def test_interface_states_hash_limit_and_exports(self):
        self.assertIn("não substitui a assinatura eletrônica", DASHBOARD)
        self.assertIn("Baixar JSON", DASHBOARD)
        self.assertIn("Imprimir / salvar PDF", DASHBOARD)
        self.assertIn("Roteiro para fiscalização", DASHBOARD)
        self.assertIn("Nenhuma resposta individual", DASHBOARD)


if __name__ == "__main__":
    unittest.main()
