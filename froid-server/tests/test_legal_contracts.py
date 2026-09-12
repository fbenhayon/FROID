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
        cls.settings = (
            ROOT / "froid-dashboard" / "src" / "pages" / "Settings.tsx"
        ).read_text(encoding="utf-8")
        cls.patient_portal = (
            ROOT / "froid-dashboard" / "src" / "pages" / "PatientPortalPage.tsx"
        ).read_text(encoding="utf-8")

    def test_supplier_pii_is_not_committed(self):
        self.assertIn('os.getenv("FROID_LEGAL_SUPPLIER_NAME", "")', self.documents)
        self.assertIn('os.getenv("FROID_LEGAL_SUPPLIER_TAX_ID", "")', self.documents)
        self.assertIn('os.getenv("FROID_LEGAL_SUPPLIER_ADDRESS", "")', self.documents)

    def _catalog_for(self, tax_id: str):
        """O catálogo renderizado para um documento de fornecedor."""
        spec = importlib.util.spec_from_file_location(
            "legal_documents_under_test", SERVER / "legal_documents.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        deployment = {
            "FROID_LEGAL_SUPPLIER_NAME": "Fornecedor de Teste",
            "FROID_LEGAL_SUPPLIER_TAX_ID": tax_id,
            "FROID_LEGAL_SUPPLIER_ADDRESS": "endereço-de-teste",
            "FROID_LEGAL_CONTACT_EMAIL": "contato@example.invalid",
            "FROID_LEGAL_PRIVACY_EMAIL": "privacidade@example.invalid",
        }
        with patch.dict(os.environ, deployment):
            return module.public_legal_catalog()

    def test_rendered_supplier_is_versioned_without_source_defaults(self):
        catalog = self._catalog_for("11.222.333/0001-81")
        self.assertTrue(catalog["supplier"]["configured"])
        self.assertEqual(len(catalog["documents"]["terms"]["sha256"]), 64)
        self.assertIn("Fornecedor de Teste", catalog["documents"]["terms"]["sections"][0]["body"])

    def test_supplier_document_label_follows_the_document(self):
        """"CPF" estava ESCRITO NO CÓDIGO, e o fornecedor virou pessoa jurídica.

        Em 11/09/2026 o FORNECEDOR passou a ser uma Ltda. Com o rótulo literal,
        os sete documentos do catálogo passariam a qualificar a parte como
        "Fulano Ltda, CPF 05.215.763/0001-73" — afirmação falsa sobre uma das
        partes, em todo documento assinado, e invisível para quem não conferir
        dígito a dígito.
        """
        pj = self._catalog_for("11.222.333/0001-81")
        self.assertEqual(pj["supplier"]["tax_id_label"], "CNPJ")
        identidade = pj["documents"]["nr1_company_contract"]["sections"][0]["body"]
        self.assertIn("CNPJ 11.222.333/0001-81", identidade)
        self.assertNotIn("CPF 11.222.333/0001-81", identidade)

        pf = self._catalog_for("050.983.408-61")
        self.assertEqual(pf["supplier"]["tax_id_label"], "CPF")
        self.assertIn(
            "CPF 050.983.408-61",
            pf["documents"]["nr1_company_contract"]["sections"][0]["body"],
        )

    def test_unknown_document_leaves_the_supplier_unconfigured(self):
        """Documento que não é CPF nem CNPJ recusa, em vez de rotular no chute.

        `configured=False` já bloqueia a contratação e já mostra "Configuração
        jurídica do fornecedor pendente" na página do contrato. Um fornecedor
        estrangeiro (NIF, SIREN, EIN) cai aqui de propósito: os textos deste
        catálogo são de direito brasileiro, e inventar um rótulo para o
        documento dele seria pior do que recusar.
        """
        for documento in ("ES-B12345678", "documento-de-teste", "", "123"):
            with self.subTest(documento=documento):
                catalog = self._catalog_for(documento)
                self.assertFalse(catalog["supplier"]["configured"])
                self.assertIn(
                    "configuração jurídica pendente",
                    catalog["documents"]["nr1_company_contract"]["sections"][0]["body"],
                )

    def test_no_document_label_is_written_into_the_texts(self):
        """A regra varre o ARQUIVO, e não a ocorrência que eu vi."""
        self.assertNotIn("CPF {supplier", self.documents)
        self.assertNotIn("CNPJ {supplier", self.documents)
        self.assertIn("{supplier['tax_id_label']}", self.documents)

    def test_documents_describe_actual_remote_processing(self):
        self.assertIn("servidor TURN", self.documents)
        self.assertIn("provedor de transcrição", self.documents)
        self.assertIn("hospedagem na Estônia", self.documents)
        self.assertNotIn("100% local", self.documents)
        self.assertNotIn("jamais são transmitidos", self.documents)

    def test_documents_do_not_freeze_prices_or_false_sla(self):
        """Preco e SLA moram no documento comercial, nunca no contrato.

        A assercao final afirmava a expressao literal "ordem eletronica", que
        era o vocabulario dos dois contratos clinicos antigos. Quando eles
        viraram um, em 12/09/2026, o texto novo passou a dizer "Proposta
        Comercial, Ordem de Contratacao ou aceite eletronico" — e o teste
        reprovou sem que nada da garantia tivesse mudado. Ele agora aceita
        qualquer um dos nomes do mesmo instrumento: o que precisa continuar
        verdadeiro e que o contrato REMETA o preco a outro documento, e nao que
        o remeta com uma palavra especifica.
        """
        self.assertNotIn("R$ 297", self.documents)
        self.assertNotIn("200ms", self.documents)
        self.assertNotIn("15 FPS", self.documents)
        self.assertTrue(
            any(
                nome in self.documents
                for nome in ("Proposta Comercial", "Ordem de Contratação", "ordem eletrônica")
            ),
            "nenhum documento remete as condicoes comerciais ao instrumento proprio",
        )

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

    def test_existing_professional_can_renew_acceptances_before_checkout(self):
        self.assertIn('@app.post("/api/professional/legal-acceptances")', self.main)
        self.assertIn('apiUrl("/api/professional/legal-acceptances")', self.settings)
        self.assertIn("order_summary_accepted: orderSummaryAccepted", self.settings)

    def test_patient_deletion_has_irreversible_double_confirmation(self):
        self.assertIn('privacyForm.request_type === "deletion"', self.patient_portal)
        self.assertIn("irreversível para todos, inclusive para você", self.patient_portal)
        self.assertIn('typedConfirmation?.trim().toUpperCase() !== "EXCLUIR"', self.patient_portal)

    def test_patient_authorization_tracks_current_legal_version(self):
        self.assertIn('"lgpd_consent_version": LEGAL_DOCUMENT_VERSION', self.main)
        self.assertIn('patient.get("lgpd_consent_version") != LEGAL_DOCUMENT_VERSION', self.main)
        self.assertIn('patient.get("lgpd_consent_version") == LEGAL_DOCUMENT_VERSION', self.main)

    def test_automatic_recharge_checkbox_is_optional_in_onboarding(self):
        marker = 'name="auto_replenish_consent"'
        start = self.onboarding.index(marker)
        checkbox = self.onboarding[start : start + 350]
        self.assertNotIn("required", checkbox)

    def test_observation_mode_presents_documents_without_blocking_onboarding(self):
        self.assertIn(
            "legalCatalog?.acceptance_required && !lgpdAccepted",
            self.onboarding,
        )
        self.assertIn(
            "o não aceite não impede o cadastro, o pagamento nem o início da operação",
            self.onboarding,
        )
        self.assertIn(
            "required={Boolean(legalCatalog?.acceptance_required)}",
            self.onboarding,
        )

    def test_legal_enforcement_is_independent_by_jurisdiction(self):
        """As quatro chaves precisam existir nas TRES camadas.

        Ate 11/09/2026 este teste conferia o `.env.multitenant.example` e o
        `main.py`, e nunca o `docker-compose.yml` — que e exatamente onde elas
        se perdiam. O servico recebe lista explicita e nao `env_file`, entao
        ligar a chave no `.env` nao mudava nada, sem erro e sem log.

        Guarda que olha a camada errada e pior que guarda nenhum: a suite verde
        fazia crer que a ativacao gradual por pais funcionava.
        """
        exemplo = (SERVER / ".env.multitenant.example").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        for jurisdiction in ("BR", "ES", "FR", "US"):
            chave = f"FROID_LEGAL_ACCEPTANCE_REQUIRED_{jurisdiction}"
            with self.subTest(jurisdiction=jurisdiction):
                self.assertIn(chave, exemplo)
                # `assertTrue` e nao `assertIn`: o assertIn imprime o
                # haystack, e aqui o haystack e o compose inteiro.
                self.assertTrue(
                    f"- {chave}=${{{chave}:-false}}" in compose,
                    f"{chave} nao chega ao contentor: o servico recebe lista "
                    "explicita, e sem esta linha a chave do .env e ignorada",
                )
        self.assertIn("FROID_LEGAL_ACCEPTANCE_REQUIRED_BY_JURISDICTION", self.main)
        self.assertIn("_legal_acceptance_required(legal_jurisdiction)", self.main)
        self.assertIn('"metadata[legal_jurisdiction]"', self.main)


if __name__ == "__main__":
    unittest.main()
