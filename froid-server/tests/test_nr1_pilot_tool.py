from pathlib import Path
import re
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

TOOL = SERVER_DIR / "tools" / "nr1_pilot_dryrun.py"
SOURCE = TOOL.read_text(encoding="utf-8")

# Tudo que guarda dado de pessoa real. O piloto escreve num banco de producao:
# encostar em qualquer uma destas seria inaceitavel.
CLINICAL_TABLES = {
    "patients",
    "patient_assignments",
    "session_reports",
    "consents",
    "credit_ledger",
    "organization_wallets",
    "subscription_plans",
    "organization_subscriptions",
    "automatic_recharges",
    "stripe_webhook_events",
    "data_subject_requests",
    "data_subject_request_events",
    "legal_acceptance_events",
    "audit_events",
    "membership_invitations",
}

# Fora do NR-1, o piloto so pode criar o proprio usuario e vinculo — sem eles a
# agregacao nao roda, porque froid_nr1_dimension_scores exige vinculo ativo.
ALLOWED_NON_NR1 = {"organizations", "users", "organization_memberships", "membership_roles"}


def written_tables():
    return set(
        re.findall(r"(?:INSERT INTO|DELETE FROM|UPDATE)\s+([a-z_]+)", SOURCE)
    ) | set(re.findall(r'\("([a-z_]+)", "organization_id=%s"\)', SOURCE))


class PilotSafetyTests(unittest.TestCase):
    def test_never_writes_to_a_clinical_table(self):
        invadidas = written_tables() & CLINICAL_TABLES
        self.assertEqual(
            invadidas, set(),
            f"O piloto escreve em tabela com dado de pessoa real: {sorted(invadidas)}",
        )

    def test_only_touches_nr1_tables_plus_the_declared_exceptions(self):
        fora = {
            table
            for table in written_tables()
            if table not in ALLOWED_NON_NR1
            and not table.startswith(("assessment_", "aep_", "psychosocial_", "gro_", "measure_", "organization_unit", "worker_"))
        }
        self.assertEqual(fora, set(), f"tabelas inesperadas: {sorted(fora)}")

    def test_everything_it_creates_is_removed(self):
        criadas = set(re.findall(r"INSERT INTO\s+([a-z_]+)", SOURCE))
        destroy = SOURCE[SOURCE.index("def destroy("):SOURCE.index("def main(")]
        removidas = set(re.findall(r"(?:DELETE FROM)\s+([a-z_]+)", destroy)) | set(
            re.findall(r'\("([a-z_]+)", "organization_id=%s"\)', SOURCE)
        )
        # assessment_response_items sai pelo subselect de responses.
        removidas.add("assessment_response_items")
        faltando = criadas - removidas
        self.assertEqual(
            faltando, set(),
            f"O piloto cria mas nao remove: {sorted(faltando)}",
        )

    def test_removal_is_scoped_to_the_pilot(self):
        destroy = SOURCE[SOURCE.index("def destroy("):SOURCE.index("def main(")]
        for statement in re.findall(r"DELETE FROM [a-z_]+[^\"']*", destroy):
            self.assertIn(
                "WHERE", statement,
                f"DELETE sem WHERE apagaria a tabela inteira: {statement}",
            )

    def test_pilot_email_cannot_belong_to_a_real_person(self):
        # .invalid e reservado por RFC 2606 e nunca resolve.
        self.assertIn("@teste.invalid", SOURCE)

    def test_uses_a_fixed_namespace_so_removal_is_exact(self):
        self.assertIn("PILOT_NAMESPACE", SOURCE)
        self.assertIn("uuid.uuid5(PILOT_NAMESPACE", SOURCE)

    def test_simulated_answers_are_deterministic(self):
        # Duas execucoes precisam dar o mesmo numero, senao nao ha conferencia.
        self.assertIn("random.Random(", SOURCE)
        self.assertNotIn("random.seed()", SOURCE)


class PilotScenarioTests(unittest.TestCase):
    """O cenario simulado precisa exercitar os tres vereditos de eficacia."""

    def setUp(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("nr1_pilot_dryrun", TOOL)
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)

    def _mean(self, code, polarity, unit, wave, draws=400):
        import random

        rng = random.Random(f"{code}|{wave}")
        dimension = {"code": code, "polarity": polarity}
        valores = [
            self.tool.answer_for(rng, dimension, unit, wave) for _ in range(draws)
        ]
        return sum(valores) / len(valores)

    def test_overload_improves_between_waves(self):
        antes = self._mean("sobrecarga", "risk", self.tool.UNIT_ATENDIMENTO, "baseline")
        depois = self._mean("sobrecarga", "risk", self.tool.UNIT_ATENDIMENTO, "followup")
        self.assertGreater(
            antes - depois, 0.8,
            "o cenario precisa produzir uma melhora clara em sobrecarga",
        )

    def test_harassment_worsens_between_waves(self):
        antes = self._mean("assedio", "risk", self.tool.UNIT_ATENDIMENTO, "baseline")
        depois = self._mean("assedio", "risk", self.tool.UNIT_ATENDIMENTO, "followup")
        self.assertGreater(
            depois - antes, 0.8,
            "o cenario precisa produzir uma piora clara em assedio",
        )

    def test_other_dimensions_stay_inside_the_noise(self):
        antes = self._mean("relacoes", "risk", self.tool.UNIT_LOGISTICA, "baseline")
        depois = self._mean("relacoes", "risk", self.tool.UNIT_LOGISTICA, "followup")
        self.assertLess(
            abs(antes - depois), 0.3,
            "as demais dimensoes devem oscilar dentro do ruido, para que o "
            "veredito 'sem mudanca' seja exercitado",
        )

    def test_answers_stay_inside_the_scale(self):
        import random

        rng = random.Random("escala")
        for code, polarity in (("sobrecarga", "risk"), ("suporte_social", "protective")):
            for wave in ("baseline", "followup"):
                for _ in range(300):
                    valor = self.tool.answer_for(
                        rng, {"code": code, "polarity": polarity},
                        self.tool.UNIT_ATENDIMENTO, wave,
                    )
                    self.assertTrue(1 <= valor <= 5, f"{code} gerou {valor}")

    def test_pseudonyms_are_unique_across_the_whole_population(self):
        """O banco impõe um pseudônimo por pessoa por campanha.

        A primeira versão do roteiro numerava a partir de zero em cada unidade
        e colidia na segunda — simulava duas pessoas com o mesmo crachá. A
        restrição do banco estava certa; o gerador é que estava errado.
        """
        gerados = [
            self.tool.pseudonym_for(unit_id, indice)
            for unit_id, total in self.tool.POPULATION.items()
            for indice in range(total)
        ]
        self.assertEqual(
            len(gerados), len(set(gerados)),
            "pseudônimos colidem entre unidades da mesma campanha",
        )

    def test_pseudonym_is_deterministic(self):
        unit = self.tool.UNIT_ATENDIMENTO
        self.assertEqual(
            self.tool.pseudonym_for(unit, 7), self.tool.pseudonym_for(unit, 7)
        )

    def test_ids_are_unique_across_units(self):
        """Convite e resposta também derivam de (campanha, unidade, índice)."""
        import uuid as uuid_module

        vistos = set()
        for campaign in (self.tool.CAMPAIGN_BASE, self.tool.CAMPAIGN_FOLLOW):
            for unit_id, total in self.tool.POPULATION.items():
                for indice in range(total):
                    for prefixo in ("invite", "response"):
                        gerado = uuid_module.uuid5(
                            self.tool.PILOT_NAMESPACE,
                            f"{prefixo}/{campaign}/{unit_id}/{indice}",
                        )
                        self.assertNotIn(gerado, vistos, f"{prefixo} duplicado")
                        vistos.add(gerado)

    def test_population_crosses_both_cohort_floors(self):
        from nr1_compliance import MIN_COHORT_CUT, MIN_COHORT_TOTAL

        total = sum(self.tool.POPULATION.values())
        self.assertGreaterEqual(total, MIN_COHORT_TOTAL)
        for unit, count in self.tool.POPULATION.items():
            self.assertGreaterEqual(count, MIN_COHORT_CUT, f"{unit} abaixo do piso")


if __name__ == "__main__":
    unittest.main()
