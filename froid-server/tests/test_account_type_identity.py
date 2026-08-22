"""CNPJ e exigido apenas de clinicas/empresas; autonomo entra com CPF.

Invariante de cadastro: profissional pessoa fisica se cadastra com nome,
celular, e-mail e CPF - sem CNPJ - e recebe uma organizacao propria derivada do
e-mail. Somente conta do tipo ``organization`` COM documento deriva a
organizacao do CNPJ, que e o que faz varios profissionais da mesma clinica
caírem no mesmo pool.

Uma refatoracao que passasse a exigir CNPJ de todo mundo, ou que jogasse
autonomos numa organizacao compartilhada, quebraria o cadastro de quem opera
hoje. Estes testes existem para isso falhar alto.
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

from tenant_store import TenantStore, stable_uuid  # noqa: E402

ONBOARDING = (
    SERVER_DIR.parent / "froid-dashboard" / "src" / "pages" / "ProfessionalOnboarding.tsx"
).read_text(encoding="utf-8")
MAIN_SOURCE = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


class OnboardingRequirementsTests(unittest.TestCase):
    """O formulario nao pode pedir CNPJ de pessoa fisica."""

    def test_reduced_onboarding_is_off(self):
        """O cadastro reduzido saiu de circulacao.

        Este teste ja afirmou o contrario: travava a flag em true, porque a
        fase de testes pedia so quatro campos. Um cliente concluiu, vendo a
        tela, que o FROID nao distinguia profissional de empresa — a
        diferenciacao existia e estava escondida por esta constante. Agora o
        invariante e o oposto, e por isso ele mora aqui.
        """
        self.assertIn("const TESTING_MINIMAL_ONBOARDING = false;", ONBOARDING)

    def test_reduced_branch_would_never_ask_cnpj_of_a_natural_person(self):
        """A regra vale mesmo com o ramo reduzido desligado.

        O codigo do ramo continua no arquivo. Se alguem religar a flag, ele
        volta a valer — entao continua sendo verificado.
        """
        anchor = ONBOARDING.index("TESTING_MINIMAL_ONBOARDING\n      ? [")
        # Ate o ramo seguinte do ternario, e nao por N caracteres: cortar por
        # tamanho ja reprovou codigo correto neste repositorio.
        end = ONBOARDING.index("accountType === \"organization\"", anchor)
        block = ONBOARDING[anchor:end]
        for field in ("fullName", "mobile", "email", "professionalRegistry"):
            self.assertIn(field, block)
        self.assertNotIn("cnpj", block.lower())

    def test_full_individual_form_asks_cpf_and_never_cnpj(self):
        """Com a flag desligada, pessoa fisica passa a exigir CPF - nunca CNPJ."""
        anchor = ONBOARDING.index('["CPF", "cpf", fields.cpf]')
        block = ONBOARDING[max(0, anchor - 260) : anchor + 60]
        for field in ("fullName", "mobile", "email"):
            self.assertIn(field, block)
        self.assertNotIn("cnpj", block.lower())

    def test_only_organization_accounts_require_cnpj(self):
        anchor = ONBOARDING.index('["CNPJ", "cnpj", fields.cnpj]')
        preamble = ONBOARDING[max(0, anchor - 400) : anchor]
        self.assertIn('accountType === "organization"', preamble)

    def test_backend_never_demands_cnpj_from_a_clinical_account(self):
        """A trava nasceu de um defeito: o cadastro clinico pedia CNPJ.

        Ela conferia isso por texto — exigia a frase exata
        `"cpf_required": not bool(professional_cpf)`. Guardava o certo pelo
        motivo errado, e reprovou codigo correto quando a empresa contratante do
        NR-1 passou a existir: ELA responde por CNPJ, e nao por pessoa. Pedir
        CPF de quem preenche o formulario da empresa seria coletar dado pessoal
        sem finalidade.

        A invariante real: a exigencia de CNPJ existe apenas para 'nr1_company'.
        Autonomo e clinica continuam identificados por CPF.
        """
        self.assertIn("professional_cpf", MAIN_SOURCE)
        self.assertNotIn("cnpj_required", MAIN_SOURCE)

        # A unica exigencia de documento de empresa esta presa ao tipo NR-1.
        exigencia = MAIN_SOURCE.index("company_document_required")
        contexto = MAIN_SOURCE[exigencia - 400 : exigencia + 200]
        self.assertIn("is_nr1_company", contexto)

        # E o caminho clinico continua exigindo CPF, com a mesma mensagem.
        self.assertIn(
            "CPF obrigatório como chave de conferência do profissional",
            MAIN_SOURCE,
        )
        cpf_exigido = MAIN_SOURCE.index(
            "CPF obrigatório como chave de conferência do profissional"
        )
        # A exigencia de CPF vive no ramo 'else', ou seja, fora do nr1_company.
        ramo = MAIN_SOURCE[cpf_exigido - 700 : cpf_exigido]
        self.assertIn("else:", ramo)
        self.assertIn('account_type == "nr1_company"', ramo)


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class OrganizationDerivationTests(unittest.TestCase):
    """Como a organizacao e derivada em cada tipo de conta."""

    @classmethod
    def setUpClass(cls):
        cls.store = TenantStore.__new__(TenantStore)
        cls.connection = psycopg.connect(DATABASE_URL, autocommit=True)

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def derive(self, email, profile):
        with self.connection.cursor() as cursor:
            return self.store._organization_for_email(cursor, email, profile)

    def test_solo_professional_gets_a_private_organization_from_email(self):
        reference = self.derive(
            "autonomo.cpf@example.com",
            {"account_type": "individual", "owner_name": "Autonomo CPF"},
        )
        self.assertEqual(
            str(reference["organization_id"]),
            str(stable_uuid("organization", "autonomo.cpf@example.com")),
        )

    def test_two_solo_professionals_never_share_an_organization(self):
        primeiro = self.derive("solo.a@example.com", {"account_type": "individual"})
        segundo = self.derive("solo.b@example.com", {"account_type": "individual"})
        self.assertNotEqual(primeiro["organization_id"], segundo["organization_id"])

    def test_clinic_professionals_share_one_organization_via_cnpj(self):
        clinica = {
            "account_type": "organization",
            "organization_name": "Clinica Identidade",
            "organization_document": "11.222.333/0001-44",
        }
        primeiro = self.derive("equipe.a@clinica.example", clinica)
        segundo = self.derive("equipe.b@clinica.example", clinica)
        self.assertEqual(primeiro["organization_id"], segundo["organization_id"])
        # Mas cada pessoa continua sendo um usuario distinto na clinica.
        self.assertNotEqual(primeiro["user_id"], segundo["user_id"])
        self.assertNotEqual(primeiro["membership_id"], segundo["membership_id"])

    def test_cnpj_formatting_does_not_split_the_clinic(self):
        formatado = self.derive(
            "fmt.a@clinica.example",
            {"account_type": "organization", "organization_document": "11.222.333/0001-44"},
        )
        cru = self.derive(
            "fmt.b@clinica.example",
            {"account_type": "organization", "organization_document": "11222333000144"},
        )
        self.assertEqual(formatado["organization_id"], cru["organization_id"])

    def test_organization_account_without_cnpj_falls_back_to_email(self):
        """Sem documento nao ha como agrupar; melhor isolar do que agrupar errado."""
        reference = self.derive(
            "sem.documento@clinica.example",
            {"account_type": "organization", "organization_document": ""},
        )
        self.assertEqual(
            str(reference["organization_id"]),
            str(stable_uuid("organization", "sem.documento@clinica.example")),
        )

    def test_a_solo_professional_can_later_become_a_clinic(self):
        """Regressao: autonomo que se formaliza nao pode quebrar o backfill.

        A organizacao individual dele ja ocupa legacy_owner_email com o seu
        e-mail. Se a organizacao da clinica tambem gravasse esse e-mail, o
        indice unico organizations_legacy_owner_unique estouraria e o backfill
        pararia no meio. Clinica nao tem dono legado unico - o campo fica nulo.
        """
        email = "formalizou@example.com"
        solo = self.derive(email, {"account_type": "individual"})
        clinica = self.derive(
            email,
            {"account_type": "organization", "organization_document": "99.888.777/0001-66"},
        )
        self.assertNotEqual(solo["organization_id"], clinica["organization_id"])
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT legacy_owner_email FROM organizations WHERE id=%s",
                (clinica["organization_id"],),
            )
            self.assertIsNone(cursor.fetchone()[0], "clinica nao tem dono legado")
            cursor.execute(
                "SELECT legacy_owner_email FROM organizations WHERE id=%s",
                (solo["organization_id"],),
            )
            self.assertEqual(cursor.fetchone()[0], email)


if __name__ == "__main__":
    unittest.main()
