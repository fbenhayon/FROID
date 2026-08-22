from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import nr1_compliance  # noqa: E402
from nr1_compliance import (  # noqa: E402
    MIN_COHORT_CUT,
    MIN_COHORT_TOTAL,
    DimensionScore,
    action_plan_seed,
    campaign_is_reportable,
    exposure_level,
    exposure_position,
    grade,
    grade_all,
    probability_from_exposure,
    risk_level,
    severity_from_consequences,
    suppression_notice,
    worst_consequence,
)
from tenant_access import (  # noqa: E402
    CLINICAL_IDENTIFIED_PERMISSIONS,
    AccessContext,
    decide,
    effective_role_permissions,
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
        unit_id=None,
    )
    base.update(overrides)
    return DimensionScore(**base)


class ExposurePositionTests(unittest.TestCase):
    def test_risk_dimension_runs_from_favorable_to_critical(self):
        self.assertAlmostEqual(exposure_position(score(mean_score=2.0)), 0.0)
        self.assertAlmostEqual(exposure_position(score(mean_score=3.0)), 0.5)
        self.assertAlmostEqual(exposure_position(score(mean_score=4.0)), 1.0)

    def test_protective_dimension_is_inverted(self):
        # "Support from leadership": a high score is a resource, not a risk, so
        # the favourable cut sits above the critical one.
        protective = dict(polarity="protective", cut_favorable=4.0, cut_critical=2.0)
        self.assertAlmostEqual(
            exposure_position(score(mean_score=4.0, **protective)), 0.0
        )
        self.assertAlmostEqual(
            exposure_position(score(mean_score=3.0, **protective)), 0.5
        )
        self.assertAlmostEqual(
            exposure_position(score(mean_score=2.0, **protective)), 1.0
        )

    def test_position_is_clamped_outside_the_cuts(self):
        self.assertAlmostEqual(exposure_position(score(mean_score=0.5)), 0.0)
        self.assertAlmostEqual(exposure_position(score(mean_score=9.0)), 1.0)

    def test_degenerate_cut_points_do_not_divide_by_zero(self):
        collapsed = score(cut_favorable=3.0, cut_critical=3.0, mean_score=3.5)
        self.assertAlmostEqual(exposure_position(collapsed), 1.0)


class SeverityTests(unittest.TestCase):
    """Severity is the magnitude of the agravo, not the survey score."""

    def test_severity_comes_from_the_consequence_not_the_score(self):
        mild_answers = score(mean_score=2.0, critical_ratio=0.0)
        harsh_answers = score(mean_score=4.0, critical_ratio=0.9)
        # Same perigo, same possible consequence: same severity. Only the
        # probability axis may move with the answers.
        self.assertEqual(
            grade(mild_answers).severity, grade(harsh_answers).severity
        )

    def test_worst_consequence_is_selected(self):
        # 1.5.4.4.4.1: when a perigo has more than one possible consequence,
        # the one of greatest magnitude is the one that counts.
        name, severity = worst_consequence(("fadiga", "transtorno_mental", "dort"))
        self.assertEqual(name, "transtorno_mental")
        self.assertEqual(severity, 4)
        self.assertEqual(
            severity_from_consequences(("fadiga", "doenca_cardiovascular")), 5
        )

    def test_unknown_consequence_fails_closed(self):
        with self.assertRaises(ValueError):
            grade(score(consequences=("mal_estar_generico",)))


class ProbabilityTests(unittest.TestCase):
    """1.5.4.4.5.3: work demands AND efficacy of implemented measures."""

    def test_probability_rises_with_the_demands_of_the_activity(self):
        low = grade(score(mean_score=2.0, critical_ratio=0.0))
        high = grade(score(mean_score=4.0, critical_ratio=0.9))
        self.assertLess(low.probability, high.probability)

    def test_effective_measures_lower_the_probability(self):
        exposed = dict(mean_score=4.0, critical_ratio=0.9)
        none = grade(score(measure_efficacy="none", **exposed))
        partial = grade(score(measure_efficacy="partial", **exposed))
        effective = grade(score(measure_efficacy="effective", **exposed))
        self.assertEqual(none.probability, 5)
        self.assertEqual(partial.probability, 4)
        self.assertEqual(effective.probability, 3)

    def test_measures_never_lower_the_severity(self):
        exposed = dict(mean_score=4.0, critical_ratio=0.9)
        none = grade(score(measure_efficacy="none", **exposed))
        eliminated = grade(score(measure_efficacy="eliminated", **exposed))
        self.assertEqual(none.severity, eliminated.severity)

    def test_measures_shown_ineffective_grant_no_reduction(self):
        # 1.5.5.3.2.1 requires ineffective measures to be corrected; they must
        # not lower the risk on paper while failing in practice.
        exposed = dict(mean_score=4.0, critical_ratio=0.9)
        self.assertEqual(
            grade(score(measure_efficacy="insufficient", **exposed)).probability,
            grade(score(measure_efficacy="none", **exposed)).probability,
        )

    def test_probability_is_clamped_to_the_scale(self):
        self.assertEqual(probability_from_exposure(1, "eliminated"), 1)
        self.assertEqual(probability_from_exposure(5, "none"), 5)

    def test_invalid_efficacy_fails_closed(self):
        with self.assertRaises(ValueError):
            probability_from_exposure(3, "mostly_ok")

    def test_exposure_level_reflects_demand_not_diagnosis(self):
        self.assertEqual(exposure_level(score(mean_score=2.0, critical_ratio=0.0)), 1)
        self.assertEqual(exposure_level(score(mean_score=4.0, critical_ratio=1.0)), 5)


class GradationTests(unittest.TestCase):
    def test_matrix_thresholds(self):
        self.assertEqual(risk_level(1, 1), "low")
        self.assertEqual(risk_level(2, 2), "moderate")
        self.assertEqual(risk_level(3, 3), "high")
        self.assertEqual(risk_level(5, 5), "critical")

    def test_grade_produces_a_traceable_rationale(self):
        graded = grade(score(mean_score=3.9, critical_ratio=0.42))
        self.assertIn("n=60", graded.rationale)
        self.assertIn("Eficacia das medidas", graded.rationale)
        self.assertIn("Consequencia de maior magnitude", graded.rationale)

    def test_grade_rejects_invalid_instrument_metadata(self):
        with self.assertRaises(ValueError):
            grade(score(polarity="inverted"))
        with self.assertRaises(ValueError):
            grade(score(nr1_factor="financial"))

    def test_grade_refuses_a_cohort_below_the_k_floor(self):
        with self.assertRaises(ValueError):
            grade(score(cohort_size=MIN_COHORT_CUT - 1))

    def test_grade_all_orders_worst_risk_first(self):
        graded = grade_all([
            score(dimension_id="mild", mean_score=2.0, critical_ratio=0.0),
            score(dimension_id="severe", mean_score=4.0, critical_ratio=0.80),
        ])
        self.assertEqual([item.dimension_id for item in graded], ["severe", "mild"])

    def test_exposed_headcount_raises_priority_on_a_tie(self):
        # 1.5.5.2.1.1: the number of workers possibly affected must be used as
        # a criterion to raise the priority of action.
        graded = grade_all([
            score(dimension_id="few", exposed_workers=12),
            score(dimension_id="many", exposed_workers=800),
        ])
        self.assertEqual([item.dimension_id for item in graded], ["many", "few"])


class CohortSuppressionTests(unittest.TestCase):
    def test_campaign_needs_the_total_floor(self):
        self.assertFalse(campaign_is_reportable(MIN_COHORT_TOTAL - 1))
        self.assertTrue(campaign_is_reportable(MIN_COHORT_TOTAL))

    def test_notice_is_empty_once_reportable(self):
        self.assertEqual(suppression_notice(MIN_COHORT_TOTAL), "")
        self.assertIn(str(MIN_COHORT_TOTAL), suppression_notice(10))

    def test_notice_does_not_leak_the_current_cohort_size(self):
        # Telling the employer "you have 47 of 50" is itself a slow leak when
        # the panel is refreshed as people answer.
        self.assertNotIn("47", suppression_notice(47))


class ActionPlanTests(unittest.TestCase):
    def test_low_risk_does_not_seed_a_measure(self):
        seeds = action_plan_seed(
            grade_all([
                score(
                    mean_score=2.0,
                    critical_ratio=0.0,
                    consequences=("fadiga",),
                    measure_efficacy="effective",
                )
            ])
        )
        self.assertEqual(seeds, [])

    def test_critical_risk_seeds_elimination_at_the_top_of_the_hierarchy(self):
        seeds = action_plan_seed(
            grade_all([
                score(
                    nr1_factor="harassment_violence",
                    mean_score=4.0,
                    critical_ratio=0.90,
                    consequences=("transtorno_mental",),
                )
            ])
        )
        self.assertEqual(len(seeds), 1)
        self.assertEqual(seeds[0]["measure_type"], "elimination")
        self.assertEqual(seeds[0]["risk_level"], "critical")

    def test_seed_carries_the_fields_1_5_5_2_2_requires_filling(self):
        seeds = action_plan_seed(
            grade_all([score(mean_score=4.0, critical_ratio=0.90)])
        )
        self.assertEqual(len(seeds), 1)
        for required in ("responsible_membership_id", "due_date", "monitoring_method"):
            self.assertIn(required, seeds[0])

    def test_epi_is_absent_from_the_measure_hierarchy(self):
        from nr1_compliance import MEASURE_HIERARCHY

        # There is no personal protective equipment against how work is
        # organized, and the Guia MTE prefers measures that change the
        # organization of work over individual or behavioural ones.
        self.assertNotIn("epi", MEASURE_HIERARCHY)
        self.assertEqual(MEASURE_HIERARCHY[0], "elimination")


class EnterpriseClinicalBoundaryTests(unittest.TestCase):
    """The employer maps the risk; it never reads the employee's record."""

    def enterprise(self, *roles):
        return AccessContext.create(
            organization_id="org-a",
            membership_id="membership-a",
            user_id="user-a",
            roles=roles,
            organization_type="enterprise",
        )

    def clinic(self, *roles):
        return AccessContext.create(
            organization_id="org-a",
            membership_id="membership-a",
            user_id="user-a",
            roles=roles,
            organization_type="clinic",
        )

    def test_clinic_behaviour_is_unchanged(self):
        owner = self.clinic("owner")
        self.assertTrue(decide(owner, "patients.read").allowed)
        self.assertTrue(decide(owner, "reports.read").allowed)
        self.assertTrue(decide(owner, "assignments.manage").allowed)

    def test_enterprise_owner_cannot_read_employee_records(self):
        owner = self.enterprise("owner")
        self.assertFalse(decide(owner, "patients.read").allowed)
        self.assertFalse(decide(owner, "reports.read").allowed)
        self.assertFalse(decide(owner, "reports.read_all").allowed)

    def test_enterprise_employer_roles_lose_every_clinical_permission(self):
        for role in ("owner", "administrator", "supervisor", "compliance_manager"):
            granted = effective_role_permissions(role, "enterprise")
            leaked = granted & CLINICAL_IDENTIFIED_PERMISSIONS
            self.assertEqual(
                leaked, frozenset(), f"{role} leaked {sorted(leaked)} in an enterprise"
            )

    def test_enterprise_owner_cannot_self_assign_a_patient(self):
        # Without this, the employer would just bind an employee to itself and
        # read the record through the professional scope.
        self.assertFalse(
            decide(self.enterprise("owner"), "assignments.manage").allowed
        )
        self.assertFalse(
            decide(self.enterprise("compliance_manager"), "assignments.manage").allowed
        )

    def test_occupational_health_binds_but_does_not_read(self):
        health = self.enterprise("occupational_health")
        self.assertTrue(decide(health, "assignments.manage").allowed)
        self.assertFalse(decide(health, "patients.read").allowed)
        self.assertFalse(decide(health, "reports.read").allowed)

    def test_professional_keeps_the_assigned_clinical_scope_in_an_enterprise(self):
        professional = self.enterprise("professional")
        self.assertTrue(
            decide(professional, "patients.read", assigned=True).allowed
        )
        self.assertFalse(
            decide(professional, "patients.read", assigned=False).allowed
        )

    def test_owner_who_is_also_a_clinician_keeps_only_the_assigned_scope(self):
        both = self.enterprise("owner", "professional")
        self.assertTrue(decide(both, "patients.read", assigned=True).allowed)
        self.assertFalse(decide(both, "patients.read", assigned=False).allowed)

    def test_compliance_roles_reach_the_aggregate_panel_only(self):
        manager = self.enterprise("compliance_manager")
        self.assertTrue(decide(manager, "nr1.aggregate.read").allowed)
        self.assertTrue(decide(manager, "nr1.campaigns.manage").allowed)
        self.assertFalse(decide(manager, "patients.read_all").allowed)

    def test_unknown_organization_type_fails_closed(self):
        with self.assertRaises(ValueError):
            AccessContext.create(
                organization_id="org-a",
                membership_id="membership-a",
                user_id="user-a",
                roles=["owner"],
                organization_type="holding",
            )


class Nr1MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (
            SERVER_DIR / "migrations" / "010_nr1_psychosocial_compliance.sql"
        ).read_text(encoding="utf-8")

    def test_raw_answers_have_no_select_policy(self):
        # The whole privacy guarantee rests on this: with RLS enabled and no
        # permissive SELECT policy, PostgreSQL denies every read.
        self.assertIn(
            "ALTER TABLE assessment_responses ENABLE ROW LEVEL SECURITY", self.sql
        )
        self.assertIn(
            "ALTER TABLE assessment_response_items ENABLE ROW LEVEL SECURITY", self.sql
        )
        self.assertNotIn("ON assessment_responses FOR SELECT", self.sql)
        self.assertNotIn("ON assessment_response_items FOR SELECT", self.sql)
        self.assertNotIn("ON assessment_responses FOR ALL", self.sql)
        self.assertNotIn("ON assessment_response_items FOR ALL", self.sql)

    def test_runtime_role_cannot_select_raw_answers(self):
        grant_block = self.sql[self.sql.index("GRANT SELECT ON"):]
        select_grant = grant_block[: grant_block.index("TO froid_runtime")]
        self.assertNotIn("assessment_responses", select_grant)
        self.assertNotIn("assessment_response_items", select_grant)

    def test_cohort_floors_are_clamped_in_sql(self):
        self.assertIn("froid_nr1_min_cohort_total() RETURNS integer", self.sql)
        self.assertIn("froid_nr1_min_cohort_cut() RETURNS integer", self.sql)
        # A caller may raise the floor, never lower it.
        self.assertIn("GREATEST(", self.sql)
        self.assertIn("HAVING count(*) >= effective_cut_floor", self.sql)

    def test_aggregate_is_tenant_scoped_despite_security_definer(self):
        self.assertIn("SECURITY DEFINER", self.sql)
        self.assertIn("campaign_org <> froid_current_organization_id()", self.sql)

    def test_aggregate_never_leaks_below_the_total_floor(self):
        self.assertIn("campaign_total < froid_nr1_min_cohort_total()", self.sql)

    def test_python_floors_mirror_the_sql_ones(self):
        self.assertIn(f"SELECT {MIN_COHORT_TOTAL} $$", self.sql)
        self.assertIn(f"SELECT {MIN_COHORT_CUT} $$", self.sql)

    def test_anonymous_submission_validates_the_campaign_window(self):
        submit = self.sql[self.sql.index("froid_nr1_submit_response("):]
        self.assertIn("invitation.status <> 'pending'", submit)
        self.assertIn("campaign.status <> 'open'", submit)
        self.assertIn("now() < campaign.opens_at OR now() > campaign.closes_at", submit)

    def test_anonymous_submission_rejects_foreign_instrument_items(self):
        # A token holder must not be able to inject items belonging to another
        # instrument, which would corrupt another campaign's aggregate.
        submit = self.sql[self.sql.index("froid_nr1_submit_response("):]
        self.assertIn("item.instrument_id = campaign.instrument_id", submit)
        self.assertIn(
            "BETWEEN instrument.scale_min AND instrument.scale_max", submit
        )

    def test_definer_functions_are_revoked_from_public(self):
        for signature in (
            "froid_nr1_dimension_scores(uuid, integer)",
            "froid_nr1_submit_response(text, jsonb)",
        ):
            self.assertIn(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC", self.sql)

    def test_migration_registers_itself(self):
        self.assertIn("'010_nr1_psychosocial_compliance'", self.sql)
        self.assertIn("BEGIN;", self.sql)
        self.assertIn("COMMIT;", self.sql)


class PgrDocumentationMigrationTests(unittest.TestCase):
    """Migration 011 against the published text of the norm."""

    @classmethod
    def setUpClass(cls):
        cls.sql = (
            SERVER_DIR / "migrations" / "011_nr1_pgr_documentation.sql"
        ).read_text(encoding="utf-8")

    def test_inventory_carries_the_nine_mandatory_fields(self):
        # 1.5.7.3.2 alíneas a-i
        for column in (
            "process_characterization",    # a
            "activity_characterization",   # b
            "hazard_description",          # c
            "hazard_sources",              # c
            "possible_harms",              # d
            "exposed_groups",              # e
            "implemented_measures",        # f
            "exposure_characterization",   # g
            "aep_reference",               # h
            "risk_classification",         # i
        ):
            self.assertIn(column, self.sql, f"inventory is missing {column}")

    def test_criteria_document_exists_and_is_immutable_once_published(self):
        # 1.5.4.4.2.2 — third mandatory PGR document.
        self.assertIn("CREATE TABLE IF NOT EXISTS gro_risk_criteria", self.sql)
        for scale in (
            "severity_scale", "probability_scale", "risk_matrix",
            "classification_rules", "decision_rules",
        ):
            self.assertIn(scale, self.sql)
        self.assertIn("gro_risk_criteria_immutable", self.sql)

    def test_review_interval_respects_the_two_year_rule(self):
        # 1.5.4.4.6 two years; 1.5.4.4.6.1 up to three only with certification.
        self.assertIn("review_interval_months integer NOT NULL DEFAULT 24", self.sql)
        self.assertIn(
            "CHECK (has_certified_sst_system OR review_interval_months <= 24)",
            self.sql,
        )

    def test_every_review_trigger_of_1_5_4_4_6_is_modelled(self):
        for trigger in (
            "residual_risk", "process_change", "measure_ineffective",
            "accident_or_disease", "legal_change", "worker_or_cipa_request",
        ):
            self.assertIn(trigger, self.sql)

    def test_inventory_history_is_retained_for_twenty_years(self):
        # 1.5.7.3.3.1
        self.assertIn("interval '20 years'", self.sql)
        self.assertIn("psychosocial_risk_inventory_history_retention", self.sql)

    def test_worker_participation_is_recorded(self):
        # 1.5.3.3 a/b/c — absent records are read as omissão patronal.
        self.assertIn("CREATE TABLE IF NOT EXISTS worker_participation_records", self.sql)
        for record_type in ("cipa_minutes", "consultation", "training", "risk_communication"):
            self.assertIn(record_type, self.sql)

    def test_measure_hierarchy_excludes_epi(self):
        # 1.5.5.1.2 lists EPI last, but there is no EPI against how work is
        # organized; the Guia MTE prefers organizational measures.
        constraint = self.sql[
            self.sql.index("ADD CONSTRAINT psychosocial_action_plan_measure_type_check"):
        ]
        constraint = constraint[: constraint.index(";")]
        self.assertIn("elimination", constraint)
        self.assertIn("substitution", constraint)
        self.assertNotIn("epi", constraint.lower())

    def test_action_plan_records_what_1_5_5_2_2_requires(self):
        for column in ("monitoring_method", "result_measurement", "implemented_at"):
            self.assertIn(column, self.sql)

    def test_aggregate_now_carries_hazard_metadata(self):
        # Probability needs measure efficacy (1.5.4.4.5.3) and severity needs
        # the consequences (1.5.4.4.4.1); neither may be guessed by the app.
        self.assertIn("consequences text[]", self.sql)
        self.assertIn("measure_efficacy text", self.sql)
        self.assertIn("exposed_workers integer", self.sql)

    def test_evaluation_units_match_the_ones_inspection_expects(self):
        for unit in ("establishment", "activity", "job_position", "workstation", "exposure_group"):
            self.assertIn(unit, self.sql)

    def test_migration_registers_itself(self):
        self.assertIn("'011_nr1_pgr_documentation'", self.sql)


if __name__ == "__main__":
    unittest.main()


class DocumentoDeCriteriosTests(unittest.TestCase):
    """1.5.4.4.2.2 pede quatro coisas, e duas chegavam vazias.

    gro_risk_criteria tem classification_rules e decision_rules como colunas NOT
    NULL, e as_document() nao as preenchia: o INSERT gravava '{}' nas duas. O
    documento que a fiscalizacao le — o terceiro documento obrigatorio do PGR —
    chegava pela metade, e a metade que faltava era justamente a que explica
    COMO a organizacao decide.
    """

    def setUp(self):
        self.doc = nr1_compliance.DEFAULT_CRITERIA.as_document()

    def test_as_quatro_exigencias_do_subitem_estao_no_documento(self):
        for chave in (
            "severity_scale",        # gradacoes de severidade
            "probability_scale",     # gradacoes de probabilidade
            "risk_matrix",           # niveis de risco
            "classification_rules",  # criterios de classificacao
            "decision_rules",        # criterios de tomada de decisao
        ):
            with self.subTest(chave=chave):
                self.assertIn(chave, self.doc)
                self.assertTrue(self.doc[chave], f"{chave} nao pode ir vazio")

    def test_a_divergencia_do_epi_e_declarada_e_nao_escondida(self):
        """A hierarquia de 1.5.5.1.2 termina em EPI; a nossa nao.

        Nao adotar o degrau de EPI no psicossocial e defensavel — nao existe
        equipamento de protecao individual contra organizacao do trabalho. O que
        nao e defensavel e um auditor descobrir a diferenca comparando o
        documento com o texto e nao achar a justificativa no mesmo lugar.
        """
        hierarquia = self.doc["decision_rules"]["measure_hierarchy"]
        self.assertNotIn("epi", [d.lower() for d in hierarquia["order"]])
        divergencia = hierarquia["declared_divergence"]
        self.assertIn("1.5.5.1.2", divergencia)
        self.assertRegex(divergencia, r"protecao individual")
        self.assertIn("1.5.5.3.2", divergencia)

    def test_os_pisos_nao_sao_apresentados_como_exigencia_da_norma(self):
        """A NR-1 nao prescreve taxa de resposta nem piso de coorte."""
        origem = self.doc["classification_rules"]["cohort_floors"]["origin"]
        self.assertIn("NAO EXIGENCIA NORMATIVA", origem)
        self.assertRegex(origem, r"nao prescreve")

    def test_a_regra_de_medida_por_nivel_e_a_mesma_que_o_codigo_aplica(self):
        """Regra declarada num lugar e aplicada noutro diverge com o tempo."""
        declarada = self.doc["decision_rules"]["measure_by_level"]
        for nivel in nr1_compliance.RISK_LEVELS:
            with self.subTest(nivel=nivel):
                self.assertEqual(
                    declarada[nivel],
                    nr1_compliance.suggested_measure_type_for_level(nivel),
                )

    def test_os_seis_gatilhos_de_revisao_estao_no_documento(self):
        revisao = self.doc["decision_rules"]["review"]
        self.assertEqual(len(revisao["immediate_triggers"]), 6)
        self.assertEqual(revisao["interval_months_default"], 24)
        self.assertEqual(revisao["interval_months_with_certified_sst_system"], 36)
        # O prazo de dois anos e teto, nao cadencia — e a alinea "a" dispara
        # pela implementacao da medida, nao por data.
        self.assertIn("teto", revisao["note"])

    def test_o_documento_diz_que_a_norma_nao_fixa_prazo_de_implementacao(self):
        prazo = self.doc["decision_rules"]["action_deadline"]
        self.assertIn("1.5.5.2.2", prazo)
        self.assertRegex(prazo, r"nao fixa prazo")

    def test_o_documento_sobrevive_a_reescala_para_outra_matriz(self):
        """Cliente com matriz 3x3 recebe o mesmo documento, na escala dele."""
        doc = nr1_compliance.criteria_for_scale(3, 3).as_document()
        self.assertEqual(doc["risk_matrix"]["type"], "3x3")
        self.assertTrue(doc["classification_rules"])
        self.assertTrue(doc["decision_rules"])
