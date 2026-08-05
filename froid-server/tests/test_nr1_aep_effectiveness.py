from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import nr1_compliance
import nr1_effectiveness
from nr1_compliance import (  # noqa: E402
    DEFAULT_CRITERIA,
    MIN_COHORT_CUT,
    DimensionScore,
    GradationCriteria,
    criteria_for_scale,
    grade,
    risk_level,
)
from nr1_effectiveness import (  # noqa: E402
    compare,
    compare_campaigns,
    efficacy_index,
    measures_requiring_correction,
)


def score(**overrides):
    base = dict(
        dimension_id="dimension-a",
        nr1_factor="workload_demand",
        polarity="risk",
        cut_favorable=2.0,
        cut_critical=4.0,
        cohort_size=60,
        mean_score=3.0,
        critical_ratio=0.10,
        unit_id="unit-a",
        score_stddev=0.80,
    )
    base.update(overrides)
    return DimensionScore(**base)


class ConfigurableCriteriaTests(unittest.TestCase):
    """1.5.4.4.2.2 makes the gradations the organization's, not ours."""

    def test_default_matrix_is_five_by_five(self):
        self.assertEqual(DEFAULT_CRITERIA.severity_max, 5)
        self.assertEqual(DEFAULT_CRITERIA.probability_max, 5)
        self.assertEqual(risk_level(1, 1), "low")
        self.assertEqual(risk_level(5, 5), "critical")

    def test_client_matrix_of_another_shape_is_supported(self):
        # The Manual requires every risk type in a PGR to share the same
        # gradations, so a client on 3x3 must keep 3x3.
        three = criteria_for_scale(3, 3)
        self.assertEqual(three.severity_max, 3)
        self.assertEqual(len(three.exposure_bands), 2)
        self.assertEqual(risk_level(1, 1, three), "low")
        self.assertEqual(risk_level(3, 3, three), "critical")

    def test_rescaled_magnitudes_stay_inside_the_scale(self):
        three = criteria_for_scale(3, 3)
        for name, magnitude in three.consequence_magnitudes.items():
            self.assertTrue(1 <= magnitude <= 3, f"{name} escaped the 1..3 scale")

    def test_document_round_trip_preserves_the_gradation(self):
        document = DEFAULT_CRITERIA.as_document()
        restored = GradationCriteria.from_document({**document, "version": 3})
        self.assertEqual(restored.risk_bands, DEFAULT_CRITERIA.risk_bands)
        self.assertEqual(restored.exposure_bands, DEFAULT_CRITERIA.exposure_bands)
        self.assertEqual(restored.version, 3)

    def test_document_states_the_normative_basis_of_each_axis(self):
        document = DEFAULT_CRITERIA.as_document()
        self.assertIn("1.5.4.4.4", document["severity_scale"]["basis"])
        self.assertIn("1.5.4.4.5.3", document["probability_scale"]["basis"])

    def test_inconsistent_criteria_fail_closed(self):
        with self.assertRaises(ValueError):  # bands do not match the scale
            GradationCriteria(
                consequence_magnitudes={"transtorno_mental": 4},
                exposure_bands=(0.5,),
                efficacy_reductions=dict(DEFAULT_CRITERIA.efficacy_reductions),
                risk_bands=(4, 8, 15),
            )
        with self.assertRaises(ValueError):  # bands out of order
            GradationCriteria(
                consequence_magnitudes={"transtorno_mental": 4},
                exposure_bands=(0.2, 0.4, 0.6, 0.8),
                efficacy_reductions=dict(DEFAULT_CRITERIA.efficacy_reductions),
                risk_bands=(4, 8, 15),
            )
        with self.assertRaises(ValueError):  # magnitude beyond the scale
            GradationCriteria(
                consequence_magnitudes={"transtorno_mental": 9},
                exposure_bands=DEFAULT_CRITERIA.exposure_bands,
                efficacy_reductions=dict(DEFAULT_CRITERIA.efficacy_reductions),
                risk_bands=(4, 8, 15),
            )

    def test_grading_reports_which_criteria_produced_it(self):
        criteria = GradationCriteria.from_document(
            {**DEFAULT_CRITERIA.as_document(), "version": 5}
        )
        graded = grade(score(mean_score=3.9, critical_ratio=0.5), criteria)
        self.assertEqual(graded.criteria_version, 5)
        self.assertIn("Criterios v5", graded.rationale)


class EffectivenessTests(unittest.TestCase):
    """The differentiator: measured, not asserted."""

    def test_a_real_improvement_is_called_effective(self):
        verdict = compare(score(mean_score=3.9), score(mean_score=3.0))
        self.assertGreater(verdict.effect_size, 0)
        self.assertEqual(verdict.verdict, "effective")
        self.assertEqual(verdict.measure_efficacy, "effective")
        self.assertFalse(verdict.requires_correction)

    def test_change_smaller_than_the_noise_is_not_success(self):
        # An improvement the statistics cannot support is exactly what an
        # opposing expert takes apart.
        verdict = compare(score(mean_score=3.90), score(mean_score=3.88))
        self.assertEqual(verdict.verdict, "no_change")
        self.assertEqual(verdict.measure_efficacy, "insufficient")
        self.assertTrue(verdict.requires_correction)

    def test_deterioration_is_flagged_for_correction(self):
        verdict = compare(score(mean_score=3.0), score(mean_score=3.8))
        self.assertLess(verdict.effect_size, 0)
        self.assertEqual(verdict.verdict, "worsened")
        self.assertEqual(verdict.measure_efficacy, "none")
        self.assertTrue(verdict.requires_correction)
        self.assertTrue(verdict.triggers_review)
        self.assertIn("1.5.5.3.2.1", verdict.rationale)

    def test_protective_dimension_improves_upwards(self):
        # On a resource dimension a higher mean is better, so the sign of the
        # improvement has to flip.
        protective = dict(polarity="protective", cut_favorable=4.0, cut_critical=2.0)
        verdict = compare(
            score(mean_score=2.2, **protective),
            score(mean_score=3.4, **protective),
        )
        self.assertGreater(verdict.effect_size, 0)
        self.assertIn(verdict.verdict, ("effective", "eliminated"))

    def test_a_suppressed_cohort_yields_no_verdict(self):
        verdict = compare(
            score(cohort_size=MIN_COHORT_CUT - 1, mean_score=3.9),
            score(mean_score=2.0),
        )
        self.assertEqual(verdict.verdict, "inconclusive")
        self.assertEqual(verdict.measure_efficacy, "none")
        self.assertFalse(verdict.requires_correction)

    def test_comparison_requires_the_same_unit_and_dimension(self):
        with self.assertRaises(ValueError):
            compare(score(), score(dimension_id="other"))
        with self.assertRaises(ValueError):
            compare(score(), score(unit_id="other"))

    def test_sem_dispersao_nao_se_afirma_eficacia(self):
        """Sem desvio-padrao nao existe efeito padronizado.

        A versao anterior caia numa diferenca de posicoes normalizadas e a
        comparava contra as bandas de Cohen. Sao escalas diferentes: aquele
        numero vive em [-1, 1] e o d nao, e effect_margin aplicava a ele o erro
        padrao do d, que so vale para uma diferenca padronizada. O veredito
        passava a depender de o score_stddev ter sido gravado — acidente de
        disponibilidade de dado, e nao propriedade da medida adotada.

        Uma melhora enorme (4.0 -> 2.0) era anunciada como eficaz sem que
        houvesse base para padronizar.
        """
        verdict = compare(
            score(mean_score=4.0, score_stddev=0.0),
            score(mean_score=2.0, score_stddev=0.0),
        )
        self.assertEqual(verdict.verdict, "inconclusive")
        self.assertFalse(verdict.significant)
        self.assertFalse(verdict.requires_correction)
        self.assertIn("dispersao", verdict.rationale)

    def test_com_dispersao_a_mesma_melhora_e_avaliada(self):
        # O contraste: o unico dado que muda e o desvio-padrao.
        verdict = compare(
            score(mean_score=4.0, score_stddev=0.8),
            score(mean_score=2.0, score_stddev=0.8),
        )
        self.assertNotEqual(verdict.verdict, "inconclusive")
        self.assertGreater(verdict.effect_size, 0)

    def test_unpaired_rows_are_skipped_not_guessed(self):
        verdicts = compare_campaigns(
            [score(dimension_id="a")],
            [score(dimension_id="a", mean_score=2.5),
             score(dimension_id="b", mean_score=2.5)],
        )
        self.assertEqual([item.dimension_id for item in verdicts], ["a"])

    def test_index_feeds_the_next_probability_calculation(self):
        verdicts = compare_campaigns(
            [score(mean_score=3.9)], [score(mean_score=3.0)]
        )
        index = efficacy_index(verdicts)
        self.assertEqual(index[("unit-a", "dimension-a")], "effective")

    def test_failed_measures_are_listed_for_correction(self):
        verdicts = compare_campaigns(
            [score(dimension_id="worked", mean_score=3.9),
             score(dimension_id="failed", mean_score=3.0)],
            [score(dimension_id="worked", mean_score=3.0),
             score(dimension_id="failed", mean_score=3.8)],
        )
        failing = measures_requiring_correction(verdicts)
        self.assertEqual([item.dimension_id for item in failing], ["failed"])

    def test_measured_efficacy_lowers_the_next_probability(self):
        # This is the loop the norm describes: efficacy is measured, then it
        # enters the probability of the following cycle.
        exposed = dict(mean_score=4.0, critical_ratio=0.9)
        before = grade(score(measure_efficacy="none", **exposed))
        after = grade(score(measure_efficacy="effective", **exposed))
        self.assertLess(after.probability, before.probability)
        self.assertEqual(after.severity, before.severity)


class StatisticalHonestyTests(unittest.TestCase):
    """Achados do piloto contra o banco real, em 04/08/2026.

    O motor estava chamando ruído de resultado — nos dois sentidos — e enchendo
    o plano de ação de obrigações inexistentes. Nenhum teste anterior pegou
    porque todos usavam coortes grandes e diferenças limpas.
    """

    def small(self, mean, **overrides):
        return score(cohort_size=22, mean_score=mean, score_stddev=0.46, **overrides)

    def large(self, mean, **overrides):
        return score(cohort_size=64, mean_score=mean, score_stddev=0.46, **overrides)

    def test_margin_of_error_shrinks_as_the_cohort_grows(self):
        from nr1_effectiveness import effect_margin

        self.assertGreater(effect_margin(0.3, 22, 22), effect_margin(0.3, 64, 64))
        self.assertGreater(effect_margin(0.3, 64, 64), effect_margin(0.3, 200, 200))

    def test_small_effect_on_a_small_cohort_is_not_a_result(self):
        # d=+0.33 com 22 pessoas: o intervalo alcança o zero.
        verdict = compare(self.small(2.44), self.small(2.29))
        self.assertEqual(verdict.verdict, "no_change")
        self.assertFalse(verdict.significant)
        self.assertIn("intervalo alcanca o zero", verdict.rationale)

    def test_the_same_effect_on_a_large_cohort_can_be_a_result(self):
        # A mesma queda de 0,30 na média: indistinguível de ruído com 22
        # pessoas, sustentável com 64. É o número de respostas que decide se
        # há afirmação a fazer, não o tamanho da diferença isolado.
        pequeno = compare(self.small(3.20), self.small(2.90))
        grande = compare(self.large(3.20), self.large(2.90))
        self.assertAlmostEqual(pequeno.effect_size, grande.effect_size, places=2)
        self.assertEqual(pequeno.verdict, "no_change")
        self.assertEqual(grande.verdict, "partial")

    def test_an_interval_that_touches_zero_is_never_a_success(self):
        """O falso positivo que o piloto produziu, travado.

        d=+0.60 com margem +/-0.60 dá o intervalo [0,00; 1,20]. Anunciar
        "medida eficaz" a partir dele é afirmar mais do que o dado sustenta —
        e foi o que aconteceu com uma melhora de assédio que eu nunca plantei,
        surgida do ruído de uma coorte de 22.
        """
        verdict = compare(
            self.small(2.50, cut_favorable=1.5, cut_critical=3.0),
            self.small(2.14, cut_favorable=1.5, cut_critical=3.0),
        )
        self.assertGreater(verdict.effect_size, 0.5)
        self.assertLess(verdict.effect_size - verdict.effect_margin, 0.20)
        self.assertEqual(verdict.verdict, "no_change")

    def test_verdict_reflects_the_magnitude_the_interval_supports(self):
        # O ponto pode sugerir eficácia; vale o que o intervalo inteiro sustenta.
        verdict = compare(self.large(3.90), self.large(3.00))
        sustentada = verdict.effect_size - verdict.effect_margin
        if sustentada >= 0.50:
            self.assertEqual(verdict.verdict, "effective")
        else:
            self.assertEqual(verdict.verdict, "partial")

    def test_rationale_states_the_interval(self):
        verdict = compare(self.large(3.9), self.large(3.0))
        self.assertIn("intervalo [", verdict.rationale)

    def test_noise_is_not_called_worsening_either(self):
        # O rigor tem de valer nos dois sentidos: se melhora pequena não vira
        # sucesso, piora pequena não vira piora.
        verdict = compare(self.large(2.36), self.large(2.46))
        self.assertEqual(verdict.verdict, "no_change")

    def test_a_large_effect_still_reads_as_worsening(self):
        verdict = compare(
            self.large(1.85, cut_favorable=1.5, cut_critical=3.0),
            self.large(3.17, cut_favorable=1.5, cut_critical=3.0),
        )
        self.assertEqual(verdict.verdict, "worsened")
        self.assertTrue(verdict.significant)
        self.assertTrue(verdict.requires_correction)

    def test_stable_low_exposure_creates_no_obligation(self):
        """Não havia medida a corrigir onde nunca houve risco a tratar.

        O subitem 1.5.5.3.2.1 manda corrigir a medida cujo acompanhamento
        mostrou ineficácia — o que pressupõe medida. Apontar uma dimensão
        tranquila como falha enche o plano de ação de ruído e esconde o que
        importa.
        """
        parado = compare(self.small(2.33, critical_ratio=0.02),
                         self.small(2.33, critical_ratio=0.02))
        self.assertEqual(parado.verdict, "no_change")
        self.assertFalse(parado.requires_correction)
        self.assertIn("nao havia medida associada", parado.rationale)

    def test_stagnant_high_exposure_does_create_an_obligation(self):
        parado = compare(
            self.large(3.90, critical_ratio=0.5), self.large(3.88, critical_ratio=0.5)
        )
        self.assertEqual(parado.verdict, "no_change")
        self.assertTrue(parado.requires_correction)

    def test_the_rationale_always_states_the_margin(self):
        verdict = compare(self.large(3.9), self.large(3.0))
        self.assertIn("margem de erro", verdict.rationale)


class AepMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (
            SERVER_DIR / "migrations" / "012_aep_and_effectiveness.sql"
        ).read_text(encoding="utf-8")

    def test_aep_describes_the_real_work(self):
        # NR-17 asks for the activity as performed, not the prescribed task.
        self.assertIn("CREATE TABLE IF NOT EXISTS aep_assessments", self.sql)
        self.assertIn("real_work_description", self.sql)

    def test_aep_characterises_the_exposure(self):
        for field in (
            "exposure_duration", "exposure_frequency",
            "exposure_intensity", "exposure_cofactors",
        ):
            self.assertIn(field, self.sql)

    def test_aep_records_the_preparation_data_the_guide_requires(self):
        for field in ("health_indicators", "absenteeism_notes", "previous_assessments"):
            self.assertIn(field, self.sql)

    def test_every_method_of_the_guide_is_a_first_class_evidence_type(self):
        for method in (
            "activity_observation", "worker_dialogue", "questionnaire",
            "workshop", "focus_group", "document_analysis", "cipa_manifestation",
        ):
            self.assertIn(method, self.sql)

    def test_a_concluded_aep_must_name_a_responsible(self):
        self.assertIn("status <> 'concluded' OR responsible_name <> ''", self.sql)

    def test_aet_escalation_is_modelled(self):
        # The AEP is the initial approach; NR-17 17.3.2 may require an AET.
        self.assertIn("aet_required", self.sql)

    def test_inventory_links_back_to_the_aep(self):
        # 1.5.7.3.2 "h": os resultados da avaliação de ergonomia da NR-17.
        self.assertIn("ADD COLUMN IF NOT EXISTS aep_id", self.sql)

    def test_aggregate_now_reports_dispersion(self):
        # Without it, no comparison can tell a real change from noise.
        self.assertIn("score_stddev numeric", self.sql)
        self.assertIn("stddev_samp(scored.subject_score)", self.sql)

    def test_effectiveness_is_stored_with_its_evidence(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS measure_effectiveness_reviews", self.sql)
        for column in (
            "baseline_cohort", "followup_cohort", "effect_size",
            "requires_correction",
        ):
            self.assertIn(column, self.sql)

    def test_probability_reads_measured_efficacy_not_a_stored_guess(self):
        self.assertIn("FROM measure_effectiveness_reviews review", self.sql)

    def test_effectiveness_cannot_compare_a_campaign_with_itself(self):
        self.assertIn("baseline_campaign_id <> followup_campaign_id", self.sql)

    def test_migration_registers_itself(self):
        self.assertIn("'012_aep_and_effectiveness'", self.sql)


class AepAuthoringTests(unittest.TestCase):
    """Filling in and signing the document, not just holding its shape."""

    @classmethod
    def setUpClass(cls):
        cls.main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.store = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")

    def test_editing_is_restricted_to_an_allow_list(self):
        # A request body must never reach status, concluded_at or the tenant.
        self.assertIn("NR1_AEP_EDITABLE_FIELDS", self.store)
        for forbidden in ("status", "concluded_at", "organization_id"):
            self.assertNotIn(
                f'"{forbidden}",\n        "real_work_description"', self.store
            )
        self.assertIn("real_work_description", self.store)

    def test_concluding_requires_substance_not_just_a_click(self):
        # 1.5.7.2 wants a dated, signed document; an empty one signed is worse
        # than none, because it is presented as evidence of diligence.
        conclude = self.store[self.store.index("def nr1_conclude_aep"):]
        conclude = conclude[: conclude.index("def nr1_list_aep")]
        self.assertIn("btrim(real_work_description) <> ''", conclude)
        self.assertIn("btrim(responsible_name) <> ''", conclude)
        self.assertIn("FROM aep_evidence evidence", conclude)

    def test_a_concluded_aep_can_no_longer_be_edited(self):
        update = self.store[self.store.index("def nr1_update_aep"):]
        update = update[: update.index("def nr1_conclude_aep")]
        self.assertIn("status IN ('draft','in_progress')", update)

    def test_first_edit_moves_the_document_out_of_draft(self):
        self.assertIn(
            "status=CASE WHEN status='draft' THEN 'in_progress' ELSE status END",
            self.store,
        )

    def test_endpoints_exist_for_the_whole_lifecycle(self):
        for route in (
            '@app.get("/api/organizations/{organization_id}/nr1/aep")',
            '@app.patch("/api/organizations/{organization_id}/nr1/aep/{aep_id}")',
            '@app.post("/api/organizations/{organization_id}/nr1/aep/{aep_id}/conclude")',
        ):
            self.assertIn(route, self.main)


class AuditHardeningTests(unittest.TestCase):
    """Findings from the general audit of the module."""

    @classmethod
    def setUpClass(cls):
        cls.sql = (
            SERVER_DIR / "migrations" / "014_nr1_audit_hardening.sql"
        ).read_text(encoding="utf-8")
        cls.main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.store = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")

    def test_open_campaign_yields_no_aggregate(self):
        # A cohort that is still growing can be differenced one respondent at a
        # time; the floor alone does not protect whoever answers last.
        self.assertIn("IF campaign_status <> 'closed' THEN", self.sql)

    def test_runtime_role_loses_all_access_to_raw_answers(self):
        # froid_nr1_submit_response is SECURITY DEFINER and writes as owner, so
        # the runtime role never needed INSERT.
        self.assertIn("REVOKE ALL ON assessment_responses FROM froid_runtime", self.sql)
        self.assertIn(
            "REVOKE ALL ON assessment_response_items FROM froid_runtime", self.sql
        )

    def test_prior_efficacy_cannot_come_from_a_later_cycle(self):
        # Otherwise a later review would retroactively regrade an earlier
        # campaign.
        self.assertIn("prior.closes_at <= campaign_opens", self.sql)

    def test_organization_wide_campaign_keeps_the_headcount_priority(self):
        # Zero here would switch off 1.5.5.2.1.1 exactly where most workers are
        # affected.
        self.assertIn("campaign_headcount", self.sql)
        self.assertIn("GREATEST(", self.sql)

    def test_effectiveness_review_is_not_a_get(self):
        # It records the verdict that the next cycle grades against, so it is an
        # act rather than a lookup.
        self.assertIn(
            '@app.post("/api/organizations/{organization_id}/nr1/effectiveness")',
            self.main,
        )
        self.assertNotIn(
            '@app.get("/api/organizations/{organization_id}/nr1/effectiveness")',
            self.main,
        )

    def test_closing_a_campaign_is_recorded(self):
        self.assertIn("closed_at timestamptz", self.sql)
        self.assertIn("def nr1_close_campaign", self.store)
        self.assertIn("nr1.campaign.close", self.main)

    def test_progress_is_readable_while_results_are_not(self):
        # Adhesion can be chased during collection; a count leaks nothing.
        self.assertIn("def nr1_campaign_progress", self.store)
        self.assertIn("response_rate", self.store)

    def test_panel_explains_an_open_campaign_instead_of_going_silent(self):
        self.assertIn("A coleta ainda está aberta", self.main)

    def test_migration_registers_itself(self):
        self.assertIn("'014_nr1_audit_hardening'", self.sql)


class CriteriosDaOrganizacaoTests(unittest.TestCase):
    """Os criterios documentados precisam chegar ate a comparacao.

    A gradacao do inventario ja os honrava; a comparacao de eficacia nao. Uma
    organizacao que publicou matriz 3x3 tinha o inventario graduado na propria
    escala e a exigencia da atividade lida na escala padrao do FROID — e o
    piso de correcao, fixo em 3, virava o TETO daquela escala, fazendo a
    obrigacao de corrigir quase desaparecer justamente para quem tinha a regua
    mais curta.
    """

    def test_piso_de_correcao_acompanha_a_escala(self):
        self.assertEqual(nr1_effectiveness.correction_floor(), 3)
        for escala, esperado in ((3, 2), (4, 3), (5, 3)):
            criterios = nr1_compliance.criteria_for_scale(escala, escala)
            self.assertEqual(
                nr1_effectiveness.correction_floor(criterios), esperado, escala
            )

    def test_piso_nunca_excede_a_escala(self):
        for escala in range(2, 11):
            criterios = nr1_compliance.criteria_for_scale(escala, escala)
            piso = nr1_effectiveness.correction_floor(criterios)
            self.assertGreaterEqual(piso, 1, escala)
            self.assertLessEqual(piso, escala, escala)

    def test_compare_aceita_e_usa_os_criterios(self):
        criterios = nr1_compliance.criteria_for_scale(3, 3)
        verdict = compare(
            score(mean_score=4.2, score_stddev=0.9),
            score(mean_score=4.1, score_stddev=0.9),
            criterios,
        )
        # Nao explode, e o parecer cita o nivel lido na escala da organizacao.
        self.assertIn("nivel", verdict.rationale)

    def test_endpoint_passa_os_criterios(self):
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        i = fonte.index("nr1_effectiveness.compare_campaigns(")
        self.assertIn("_nr1_criteria_for(context)", fonte[i:i + 400])


class EficaciaConcordaComOParecerTests(unittest.TestCase):
    """A eficacia registrada nao pode contradizer a propria justificativa."""

    def test_sem_medida_associada_a_eficacia_e_none_e_nao_insuficiente(self):
        # Dimensao que ja estava baixa e continua baixa: o texto diz que nao
        # havia medida associada, entao rotula-la "insufficient" faria o
        # inventario do ciclo seguinte ler "medida insuficiente" onde nenhuma
        # medida existiu.
        verdict = compare(
            score(mean_score=1.2, score_stddev=0.5),
            score(mean_score=1.25, score_stddev=0.5),
        )
        self.assertEqual(verdict.verdict, "no_change")
        self.assertFalse(verdict.requires_correction)
        self.assertEqual(verdict.measure_efficacy, "none")
        self.assertIn("nao havia medida associada", verdict.rationale)

    def test_com_exposicao_alta_o_no_change_continua_insuficiente(self):
        verdict = compare(
            score(mean_score=4.5, score_stddev=0.5),
            score(mean_score=4.45, score_stddev=0.5),
        )
        self.assertEqual(verdict.verdict, "no_change")
        self.assertTrue(verdict.requires_correction)
        self.assertEqual(verdict.measure_efficacy, "insufficient")

class EscalaDeRiscoTests(unittest.TestCase):
    """Propriedade verificada em vez de suposta.

    A auditoria suspeitou que os pisos fixos de criteria_for_scale
    (max(2,...), max(3,...), max(4,...)) pudessem inverter ou colapsar as
    bandas numa matriz pequena. Nao invertem. A verificacao ficou como teste
    para que a suspeita nao precise ser refeita, e para que uma mudanca futura
    nos pisos nao quebre a monotonicidade em silencio.
    """

    def test_bandas_sempre_estritamente_crescentes(self):
        for escala in range(2, 11):
            criterios = nr1_compliance.criteria_for_scale(escala, escala)
            bandas = list(criterios.risk_bands)
            self.assertEqual(bandas, sorted(set(bandas)), f"{escala}x{escala}")

    def test_todos_os_niveis_alcancaveis_a_partir_de_3x3(self):
        # Numa 2x2 ha apenas tres produtos possiveis para quatro niveis, entao
        # um nivel fica inalcancavel por aritmetica e nao por defeito.
        for escala in range(3, 9):
            criterios = nr1_compliance.criteria_for_scale(escala, escala)
            niveis = {
                nr1_compliance.risk_level(s, p, criterios)
                for s in range(1, escala + 1)
                for p in range(1, escala + 1)
            }
            self.assertEqual(
                niveis, set(nr1_compliance.RISK_LEVELS), f"{escala}x{escala}"
            )

    def test_o_pior_caso_e_sempre_critico_e_o_melhor_sempre_baixo(self):
        for escala in range(2, 11):
            criterios = nr1_compliance.criteria_for_scale(escala, escala)
            self.assertEqual(
                nr1_compliance.risk_level(escala, escala, criterios), "critical"
            )
            self.assertEqual(nr1_compliance.risk_level(1, 1, criterios), "low")

if __name__ == "__main__":
    unittest.main()
