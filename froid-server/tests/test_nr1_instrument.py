from pathlib import Path
import re
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from nr1_compliance import DEFAULT_CRITERIA, NR1_FACTORS, VALID_POLARITIES  # noqa: E402


SQL = (
    SERVER_DIR / "migrations" / "015_nr1_instrument_froid_v1.sql"
).read_text(encoding="utf-8")


def dimension_rows():
    """Parse the dimension VALUES block into tuples we can assert on."""
    block = SQL[SQL.index("AS dimension(code") - 6000: SQL.index("AS dimension(code")]
    return re.findall(
        r"\('([a-z_]+)', '([^']+)', '([a-z_]+)', '(risk|protective)', "
        r"([\d.]+), ([\d.]+), (\d+),",
        block,
    )


def item_rows():
    block = SQL[SQL.index("INSERT INTO assessment_items"):]
    return re.findall(r"\('([a-z_]+)', '([a-z]{3}_\d{2})', '([^']+)', (\d+)\)", block)


class InstrumentStructureTests(unittest.TestCase):
    def test_covers_the_thirteen_hazards_of_the_guide(self):
        self.assertEqual(len(dimension_rows()), 13)

    def test_every_dimension_maps_to_a_valid_nr1_factor(self):
        for row in dimension_rows():
            self.assertIn(row[2], NR1_FACTORS, f"{row[0]} has an unknown factor")

    def test_every_dimension_declares_a_valid_polarity(self):
        for row in dimension_rows():
            self.assertIn(row[3], VALID_POLARITIES)

    def test_protective_dimensions_have_the_favourable_cut_above_the_critical(self):
        # On a resource dimension a higher score is better, so the cuts invert.
        for code, _title, _factor, polarity, favorable, critical, _order in dimension_rows():
            if polarity == "protective":
                self.assertGreater(
                    float(favorable), float(critical),
                    f"{code}: em dimensão protetora o corte favorável fica acima do crítico",
                )
            else:
                self.assertLess(
                    float(favorable), float(critical),
                    f"{code}: em dimensão de risco o corte favorável fica abaixo do crítico",
                )

    def test_cuts_sit_inside_the_declared_scale(self):
        for code, _t, _f, _p, favorable, critical, _o in dimension_rows():
            for value in (float(favorable), float(critical)):
                self.assertTrue(1.0 <= value <= 5.0, f"{code}: corte fora da escala 1..5")

    def test_harassment_and_violence_use_a_stricter_critical_cut(self):
        # A single occurrence already matters; the band cannot demand the same
        # frequency as an ordinary workload complaint.
        cuts = {
            row[0]: float(row[5]) for row in dimension_rows() if row[2] == "harassment_violence"
        }
        self.assertLessEqual(cuts["assedio"], 3.0)
        self.assertLessEqual(cuts["violencia"], 3.0)

    def test_every_consequence_has_a_declared_magnitude(self):
        # Grading fails closed on an unknown consequence, so the seed must only
        # use consequences the default criteria can weigh.
        declared = set(re.findall(r"ARRAY\[([^\]]+)\]", SQL))
        used = set()
        for group in declared:
            used.update(re.findall(r"'([a-z_]+)'", group))
        unknown = used - set(DEFAULT_CRITERIA.consequence_magnitudes)
        self.assertEqual(unknown, set(), f"consequências sem magnitude: {sorted(unknown)}")


class InstrumentItemTests(unittest.TestCase):
    def test_three_items_per_dimension(self):
        items = item_rows()
        self.assertEqual(len(items), 39)
        by_dimension: dict = {}
        for dimension_code, _code, _statement, _order in items:
            by_dimension[dimension_code] = by_dimension.get(dimension_code, 0) + 1
        self.assertEqual(len(by_dimension), 13)
        for dimension_code, count in by_dimension.items():
            self.assertEqual(count, 3, f"{dimension_code} tem {count} itens")

    def test_every_item_belongs_to_a_declared_dimension(self):
        codes = {row[0] for row in dimension_rows()}
        for dimension_code, code, _statement, _order in item_rows():
            self.assertIn(dimension_code, codes, f"{code} aponta para dimensão inexistente")

    def test_item_codes_are_unique(self):
        codes = [row[1] for row in item_rows()]
        self.assertEqual(len(codes), len(set(codes)))

    def test_no_item_asks_about_symptoms_or_health(self):
        """The one rule that decides whether this belongs in the GRO at all.

        The Guia MTE draws the line explicitly: the assessment looks at the
        working conditions, not at whether the person feels unwell. An item
        about mood, sleep or diagnosis would put the instrument outside the
        scope of the norm — and turn it into the clinical screening the MTE
        rejects as the instrument of this process.
        """
        forbidden = (
            "ansios", "deprim", "triste", "insônia", "insonia", "dorme",
            "estresse", "estressad", "esgotad", "burnout", "cansaç",
            "sua saúde", "sua saude", "se sente", "sente-se", "humor",
            "sofriment", "adoec", "medicament", "terapia",
        )
        for _dimension, code, statement, _order in item_rows():
            lowered = statement.lower()
            for term in forbidden:
                self.assertNotIn(
                    term, lowered,
                    f"{code} pergunta sobre sintoma/saúde ('{term}'), não sobre "
                    f"condição de trabalho: {statement}",
                )

    def test_statements_are_questions_about_work(self):
        for _dimension, code, statement, _order in item_rows():
            self.assertTrue(statement.endswith("."), f"{code} sem pontuação final")
            self.assertGreater(len(statement), 25, f"{code} curto demais para ser claro")


class InstrumentProvenanceTests(unittest.TestCase):
    def test_the_seed_states_its_basis_and_its_limit(self):
        self.assertIn("Guia", SQL)
        self.assertIn("ISO 45003", SQL)
        # The absence of psychometric validation must be written down, not
        # implied: the organization has to justify the choice in its criteria.
        self.assertIn("validacao", SQL.lower().replace("ç", "c").replace("ã", "a"))
        self.assertIn("1.5.4.4.2.2", SQL)

    def test_scale_matches_what_the_frontend_renders(self):
        self.assertIn('"Nunca","Raramente","Às vezes","Frequentemente","Sempre"', SQL)
        self.assertIn("1, 5,", SQL)

    def test_ids_are_deterministic_so_reapplying_changes_nothing(self):
        self.assertIn("md5('froid-nr1-psicossocial|1.0')::uuid", SQL)
        self.assertEqual(SQL.count("ON CONFLICT"), 4)

    def test_migration_registers_itself(self):
        self.assertIn("'015_nr1_instrument_froid_v1'", SQL)


if __name__ == "__main__":
    unittest.main()
