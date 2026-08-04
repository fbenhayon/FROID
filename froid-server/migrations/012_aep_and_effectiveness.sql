-- Avaliação Ergonômica Preliminar (AEP) e prova de eficácia.
--
-- This is the migration that changes what the product is. Until now FROID
-- produced a questionnaire result that somebody else had to assemble into
-- compliance. The AEP is the document the inspection asks for first, it is
-- mandatory for every organization — including the micro and small companies
-- of grau de risco 1 and 2 that are exempt from the PGR itself — and it is the
-- method through which hazard identification and risk assessment for ergonomic
-- and psychosocial factors actually happen, under NR-17 read with NR-1.
--
-- Two things the norm insists on and that shape this schema:
--
--   * The AEP describes the *trabalho real*, the activity as it is actually
--     performed, not the prescribed task.
--   * A questionnaire never stands alone. The Guia MTE lists observation of the
--     activity, dialogue with the worker, standardised surveys and workshops as
--     alternatives or combinations, and the FAQ is explicit that questionnaire
--     results "não comprovam a gestão de riscos de forma isolada". So evidence
--     is a first-class table with a method on every row, and an AEP that rests
--     on one method alone is visible as such.
--
-- The second half adds the dispersion the effectiveness comparison needs. Item
-- 1.5.4.4.5.3 makes the efficacy of implemented measures part of probability;
-- proving it requires knowing whether a change is larger than the noise of the
-- cohort, which a mean alone cannot tell.

BEGIN;

-- ---------------------------------------------------------------------------
-- The AEP document
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aep_assessments (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    -- Unidade de avaliação: atividade, posto, função, setor ou grupo similar de
    -- exposição, as the FAQ suggests aligning with the PGR's own units.
    unit_id uuid NOT NULL REFERENCES organization_units(id) ON DELETE RESTRICT,
    criteria_id uuid REFERENCES gro_risk_criteria(id) ON DELETE RESTRICT,
    reference_period text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'in_progress', 'concluded', 'superseded')),

    -- The heart of it: how the work is really done, not how the manual says.
    real_work_description text NOT NULL DEFAULT '',
    -- Caracterização da exposição as the Guia describes it: duração,
    -- frequência, intensidade e cofatores.
    exposure_duration text NOT NULL DEFAULT '',
    exposure_frequency text NOT NULL DEFAULT '',
    exposure_intensity text NOT NULL DEFAULT '',
    exposure_cofactors text NOT NULL DEFAULT '',

    -- Preparação (Guia, cap. 3): the organization must gather health follow-up
    -- data, absenteeism, CAT, PCMSO indicators and prior assessments before
    -- deciding where to start.
    health_indicators text NOT NULL DEFAULT '',
    absenteeism_notes text NOT NULL DEFAULT '',
    previous_assessments text NOT NULL DEFAULT '',

    -- 1.5.7.2: the PGR documents are dated and signed, under the
    -- responsibility of the organization. The norm names no specific
    -- profession, so the qualification is recorded as text rather than
    -- constrained to a council registration.
    responsible_name text NOT NULL DEFAULT '',
    responsible_qualification text NOT NULL DEFAULT '',
    responsible_membership_id uuid REFERENCES organization_memberships(id) ON DELETE SET NULL,

    -- Whether an AET was triggered (NR-17 item 17.3.2) — the AEP is the initial
    -- approach and does not always close the matter.
    aet_required boolean NOT NULL DEFAULT false,
    aet_justification text NOT NULL DEFAULT '',

    opened_at timestamptz NOT NULL DEFAULT now(),
    concluded_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    CHECK (status <> 'concluded' OR concluded_at IS NOT NULL),
    -- A concluded AEP without a named responsible is not a document anyone can
    -- rely on in an inspection.
    CHECK (status <> 'concluded' OR responsible_name <> '')
);

CREATE INDEX IF NOT EXISTS aep_assessments_org_idx
    ON aep_assessments (organization_id, status);
CREATE INDEX IF NOT EXISTS aep_assessments_unit_idx
    ON aep_assessments (unit_id, opened_at DESC);

-- ---------------------------------------------------------------------------
-- What the AEP rests on. One row per piece of evidence, each naming its method.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aep_evidence (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    aep_id uuid NOT NULL REFERENCES aep_assessments(id) ON DELETE CASCADE,
    method text NOT NULL
        CHECK (method IN (
            'activity_observation',  -- observação da atividade de trabalho
            'worker_dialogue',       -- diálogo com o trabalhador
            'questionnaire',         -- pesquisa padronizada (o FROID entra aqui)
            'workshop',              -- oficina moderada / grupo de discussão
            'focus_group',
            'document_analysis',     -- PCMSO, CAT, afastamentos, avaliações anteriores
            'cipa_manifestation'     -- manifestações da CIPA (1.5.3.3 "b")
        )),
    campaign_id uuid REFERENCES assessment_campaigns(id) ON DELETE SET NULL,
    participation_record_id uuid REFERENCES worker_participation_records(id) ON DELETE SET NULL,
    collected_on date NOT NULL,
    collected_by text NOT NULL DEFAULT '',
    summary text NOT NULL,
    evidence_reference text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS aep_evidence_aep_idx ON aep_evidence (aep_id, method);

-- The inventory row now points back at the AEP that produced it, which is what
-- alínea "h" of 1.5.7.3.2 asks for: os resultados da avaliação de ergonomia nos
-- termos da NR-17.
ALTER TABLE psychosocial_risk_inventory
  ADD COLUMN IF NOT EXISTS aep_id uuid REFERENCES aep_assessments(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS psychosocial_risk_inventory_aep_idx
    ON psychosocial_risk_inventory (aep_id);

-- ---------------------------------------------------------------------------
-- Measured effectiveness of the prevention measures.
--
-- Not an opinion field. Each row records a comparison of one unit against its
-- own earlier baseline, with the cohort sizes and the standardised difference,
-- so the figure feeding the next probability can be reconstructed by anyone.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS measure_effectiveness_reviews (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    unit_id uuid REFERENCES organization_units(id) ON DELETE RESTRICT,
    dimension_id uuid NOT NULL REFERENCES assessment_dimensions(id) ON DELETE RESTRICT,
    action_plan_id uuid REFERENCES psychosocial_action_plan(id) ON DELETE SET NULL,
    baseline_campaign_id uuid NOT NULL REFERENCES assessment_campaigns(id) ON DELETE RESTRICT,
    followup_campaign_id uuid NOT NULL REFERENCES assessment_campaigns(id) ON DELETE RESTRICT,
    baseline_cohort integer NOT NULL CHECK (baseline_cohort >= 0),
    followup_cohort integer NOT NULL CHECK (followup_cohort >= 0),
    baseline_mean numeric(6,3) NOT NULL,
    followup_mean numeric(6,3) NOT NULL,
    effect_size numeric(6,3) NOT NULL,
    verdict text NOT NULL
        CHECK (verdict IN (
            'eliminated', 'effective', 'partial',
            'no_change', 'worsened', 'inconclusive'
        )),
    measure_efficacy text NOT NULL
        CHECK (measure_efficacy IN
            ('none', 'insufficient', 'partial', 'effective', 'eliminated')),
    -- 1.5.5.3.2.1: a measure whose monitoring shows it ineffective must be
    -- corrected. Flagged here so it cannot quietly age into evidence of
    -- diligence.
    requires_correction boolean NOT NULL DEFAULT false,
    rationale text NOT NULL DEFAULT '',
    reviewed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (followup_campaign_id, unit_id, dimension_id),
    CHECK (baseline_campaign_id <> followup_campaign_id)
);

CREATE INDEX IF NOT EXISTS measure_effectiveness_reviews_org_idx
    ON measure_effectiveness_reviews (organization_id, requires_correction);

-- ---------------------------------------------------------------------------
-- Aggregate, now with dispersion and with efficacy taken from the measured
-- review rather than from the previous inventory's stored guess.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS froid_nr1_dimension_scores(uuid, integer);

CREATE OR REPLACE FUNCTION froid_nr1_dimension_scores(
    target_campaign_id uuid,
    requested_min_cohort integer DEFAULT NULL
)
RETURNS TABLE (
    unit_id uuid,
    dimension_id uuid,
    nr1_factor text,
    polarity text,
    cut_favorable numeric,
    cut_critical numeric,
    cohort_size bigint,
    mean_score numeric,
    critical_ratio numeric,
    score_stddev numeric,
    consequences text[],
    measure_efficacy text,
    exposed_workers integer
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    effective_cut_floor integer;
    campaign_total bigint;
    campaign_org uuid;
BEGIN
    effective_cut_floor := GREATEST(
        coalesce(requested_min_cohort, froid_nr1_min_cohort_cut()),
        froid_nr1_min_cohort_cut()
    );

    SELECT campaign.organization_id INTO campaign_org
    FROM assessment_campaigns campaign
    WHERE campaign.id = target_campaign_id;

    IF campaign_org IS NULL OR campaign_org <> froid_current_organization_id() THEN
        RETURN;
    END IF;

    IF NOT froid_membership_is_active() THEN
        RETURN;
    END IF;

    SELECT count(*) INTO campaign_total
    FROM assessment_responses response
    WHERE response.campaign_id = target_campaign_id
      AND response.completed;

    IF campaign_total < froid_nr1_min_cohort_total() THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH response_dimension AS (
        SELECT response.id AS response_id,
               response.unit_id AS response_unit_id,
               dimension.id AS response_dimension_id,
               avg(
                   CASE WHEN item.reverse_scored
                        THEN (instrument.scale_max + instrument.scale_min) - response_item.value
                        ELSE response_item.value
                   END
               )::numeric AS subject_score
        FROM assessment_responses response
        JOIN assessment_response_items response_item
          ON response_item.response_id = response.id
        JOIN assessment_items item
          ON item.id = response_item.item_id
        JOIN assessment_dimensions dimension
          ON dimension.id = item.dimension_id
        JOIN assessment_instruments instrument
          ON instrument.id = item.instrument_id
        WHERE response.campaign_id = target_campaign_id
          AND response.completed
        GROUP BY response.id, response.unit_id, dimension.id
    )
    SELECT scored.response_unit_id,
           dimension.id,
           dimension.nr1_factor,
           dimension.polarity,
           dimension.cut_favorable,
           dimension.cut_critical,
           count(*) AS cohort_size,
           round(avg(scored.subject_score), 3) AS mean_score,
           round(
               avg(
                   CASE
                       WHEN dimension.polarity = 'protective'
                            AND scored.subject_score <= dimension.cut_critical THEN 1.0
                       WHEN dimension.polarity = 'risk'
                            AND scored.subject_score >= dimension.cut_critical THEN 1.0
                       ELSE 0.0
                   END
               ), 3
           ) AS critical_ratio,
           -- Dispersion of the per-respondent dimension scores. Without it a
           -- later comparison cannot tell an effective measure from noise.
           round(coalesce(stddev_samp(scored.subject_score), 0), 3) AS score_stddev,
           dimension.consequences,
           coalesce(
               (
                   SELECT review.measure_efficacy
                   FROM measure_effectiveness_reviews review
                   WHERE review.organization_id = campaign_org
                     AND review.dimension_id = dimension.id
                     AND review.unit_id IS NOT DISTINCT FROM scored.response_unit_id
                     AND review.followup_campaign_id <> target_campaign_id
                   ORDER BY review.reviewed_at DESC
                   LIMIT 1
               ),
               'none'
           ) AS measure_efficacy,
           coalesce(max(unit.headcount), 0) AS exposed_workers
    FROM response_dimension scored
    JOIN assessment_dimensions dimension
      ON dimension.id = scored.response_dimension_id
    LEFT JOIN organization_units unit
      ON unit.id = scored.response_unit_id
    GROUP BY scored.response_unit_id, dimension.id, dimension.nr1_factor,
             dimension.polarity, dimension.cut_favorable, dimension.cut_critical,
             dimension.consequences
    HAVING count(*) >= effective_cut_floor;
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_dimension_scores(uuid, integer) FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------
ALTER TABLE aep_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE aep_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE measure_effectiveness_reviews ENABLE ROW LEVEL SECURITY;

-- 1.5.7.2.1 keeps the PGR documents available to the workers concerned and to
-- their unions, so the AEP is readable by every active member.
DROP POLICY IF EXISTS aep_assessments_read ON aep_assessments;
CREATE POLICY aep_assessments_read ON aep_assessments FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);
DROP POLICY IF EXISTS aep_assessments_manage ON aep_assessments;
CREATE POLICY aep_assessments_manage ON aep_assessments FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['compliance_manager','occupational_health']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['compliance_manager','occupational_health']::text[])
);

DROP POLICY IF EXISTS aep_evidence_read ON aep_evidence;
CREATE POLICY aep_evidence_read ON aep_evidence FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);
DROP POLICY IF EXISTS aep_evidence_manage ON aep_evidence;
CREATE POLICY aep_evidence_manage ON aep_evidence FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['compliance_manager','occupational_health']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['compliance_manager','occupational_health']::text[])
);

DROP POLICY IF EXISTS measure_effectiveness_reviews_read ON measure_effectiveness_reviews;
CREATE POLICY measure_effectiveness_reviews_read ON measure_effectiveness_reviews
FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY[
      'owner','administrator','compliance_manager','occupational_health','auditor'
  ]::text[])
);
DROP POLICY IF EXISTS measure_effectiveness_reviews_manage ON measure_effectiveness_reviews;
CREATE POLICY measure_effectiveness_reviews_manage ON measure_effectiveness_reviews
FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['compliance_manager','occupational_health']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['compliance_manager','occupational_health']::text[])
);

-- ---------------------------------------------------------------------------
-- Runtime grants
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT SELECT, INSERT, UPDATE ON
            aep_assessments, aep_evidence, measure_effectiveness_reviews
        TO froid_runtime;
        GRANT DELETE ON aep_evidence TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_dimension_scores(uuid, integer)
            TO froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('012_aep_and_effectiveness')
ON CONFLICT (version) DO NOTHING;

COMMIT;
