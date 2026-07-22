from pathlib import Path
import importlib.util
import os
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "froid-server"


class LegalContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (SERVER / "main.py").read_text(encoding="utf-8")
        cls.documents = (SERVER / "legal_documents.py").read_text(encoding="utf-8")
        cls.migration = (
            SERVER / "migrations" / "009_legal_acceptance_ledger.sql"
        ).read_text(encoding="utf-8")
        cls.onboarding = (
            ROOT / "froid-dashboard" / "src" / "pages" / "ProfessionalOnboarding.tsx"
        ).read_text(encoding="utf-8")

    def test_supplier_pii_is_not_committed(self):
        self.assertIn('os.getenv("FROID_LEGAL_SUPPLIER_NAME", "")', self.documents)
        self.assertIn('os.getenv("FROID_LEGAL_SUPPLIER_TAX_ID", "")', self.documents)
        self.assertIn('os.getenv("FROID_LEGAL_SUPPLIER_ADDRESS", "")', self.documents)

    def test_rendered_supplier_is_versioned_without_source_defaults(self):
        spec = importlib.util.spec_from_file_location(
            "legal_documents_under_test", SERVER / "legal_documents.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        deployment = {
            "FROID_LEGAL_SUPPLIER_NAME": "Fornecedor de Teste",
            "FROID_LEGAL_SUPPLIER_TAX_ID": "documento-de-teste",
            "FROID_LEGAL_SUPPLIER_ADDRESS": "endereço-de-teste",
            "FROID_LEGAL_CONTACT_EMAIL": "contato@example.invalid",
            "FROID_LEGAL_PRIVACY_EMAIL": "privacidade@example.invalid",
        }
        with patch.dict(os.environ, deployment):
            catalog = module.public_legal_catalog()
        self.assertTrue(catalog["supplier"]["configured"])
        self.assertEqual(len(catalog["documents"]["terms"]["sha256"]), 64)
        self.assertIn("Fornecedor de Teste", catalog["documents"]["terms"]["sections"][0]["body"])

    def test_documents_describe_actual_remote_processing(self):
        self.assertIn("servidor TURN", self.documents)
        self.assertIn("provedor de transcrição", self.documents)
        self.assertIn("hospedagem na Estônia", self.documents)
        self.assertNotIn("100% local", self.documents)
        self.assertNotIn("jamais são transmitidos", self.documents)

    def test_documents_do_not_freeze_prices_or_false_sla(self):
        self.assertNotIn("R$ 297", self.documents)
        self.assertNotIn("200ms", self.documents)
        self.assertNotIn("15 FPS", self.documents)
        self.assertIn("ordem eletrônica", self.documents)

    def test_ledger_is_append_only_and_pseudonymous(self):
        self.assertIn("legal_acceptance_events is append-only", self.migration)
        self.assertIn("subject_reference_hash char(64)", self.migration)
        self.assertNotIn(" email ", self.migration.lower())

    def test_checkout_and_onboarding_have_independent_acceptances(self):
        self.assertIn('body.get("order_summary_accepted") is True', self.main)
        self.assertIn("legal_acceptances", self.onboarding)
        self.assertIn("order_summary_accepted", self.onboarding)
        self.assertIn("auto_replenish_consent", self.onboarding)
        self.assertIn("_validate_checkout_legal_metadata", self.main)
        self.assertIn("legal_ledger_persistence_enabled", self.main)


if __name__ == "__main__":
    unittest.main()
