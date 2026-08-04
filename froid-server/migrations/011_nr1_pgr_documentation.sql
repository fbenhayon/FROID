-- NR-1 chapter 1.5 — the documentation the norm actually demands.
--
-- Migration 010 built the collection and the k-anonymity floor. This one closes
-- the gap between "we measured something" and "we can survive an inspection",
-- against the published text of Portaria MTE 1.419/2024:
--
--   1.5.7.3.2 a-i   nine mandatory fields of the inventário de riscos
--   1.5.4.4.2.2     the documento de critérios, third mandatory PGR document
--   1.5.3.3         participação, consulta e comunicação aos trabalhadores
--   1.5.4.4.5.3     eficácia das medidas de prevenção implementadas
--   1.5.4.4.6       revisão a cada 2 anos (3 with a certified SST system)
--   1.5.7.3.3.1     inventory history kept for at least 20 years
--   1.5.5.2.1.1     workers possibly affected raise the action priority
--
-- The Guia MTE 2025 is the reason the hazard metadata lives on the dimension
-- rather than on the answer: the perigo and its possible agravo are properties
-- of how the work is organized, not of how any person feels about it.

BEGIN;

-- ---------------------------------------------------------------------------
-- Unidades de avaliação. The FAQ names the ones inspection expects to see:
-- a atividade de trabalho, o posto de trabalho, a função, o setor ou o grupo
-- similar de exposição. The PGR itself is mandatory per estabelecimento (CNPJ).
-- ---------------------------------------------------------------------------
ALTER TABLE organization_units
  DROP CONSTRAINT IF EXISTS organization_units_unit_type_check;
ALTER TABLE organization_units
  ADD CONSTRAINT organization_units_unit_type_check
  CHECK (unit_type IN (
      'establishment', 'site', 'sector', 'exposure_group',
      'activity', 'job_position', 'workstation'
  ));

ALTER TABLE organization_units
  ADD COLUMN IF NOT EXISTS cnpj text,
  -- 1.5.7.3.2 "a" and "b": characterisation of the processes, environments and
  -- activities. Free text because the norm asks for description, not codes.
  ADD COLUMN IF NOT EXISTS process_description text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS activity_description text NOT NULL DEFAULT '';

-- ---------------------------------------------------------------------------
-- Hazard metadata on the instrument dimension: which perigo it detects and
-- which lesões ou agravos it may lead to (1.5.4.3.1 "a").
-- ---------------------------------------------------------------------------
ALTER TABLE assessment_dimensions
  -- Wording of the perigo as it will appear in the inventory, e.g. "Excesso de
  -- demandas no trabalho (sobrecarga)" from the Guia MTE listing.
  ADD COLUMN IF NOT EXISTS hazard_label text NOT NULL DEFAULT '',
  -- 1.5.7.3.2 "c": fontes e/ou circunstâncias do perigo.
  ADD COLUMN IF NOT EXISTS hazard_sources text NOT NULL DEFAULT '',
  -- 1.5.4.4.4.1: all possible consequences; the gradation picks the greatest
  -- magnitude among them.
  ADD COLUMN IF NOT EXISTS consequences text[] NOT NULL
      DEFAULT ARRAY['transtorno_mental']::text[];

-- ---------------------------------------------------------------------------
-- Documento de critérios (1.5.4.4.2.2) — the third mandatory PGR document.
--
-- The norm requires the organization to detail, in a document, the gradations
-- of severity and probability, the risk levels, the classification criteria and
-- the decision rules. Versioned and immutable once published, because a
-- campaign has to be explainable under the criteria in force when it ran.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gro_risk_criteria (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    severity_scale jsonb NOT NULL,
    probability_scale jsonb NOT NULL,
    risk_matrix jsonb NOT NULL,
    classification_rules jsonb NOT NULL,
    decision_rules jsonb NOT NULL,
    consequence_magnitudes jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- 1.5.4.4.6 / 1.5.4.4.6.1: two years, or up to three with a certified SST
    -- management system.
    review_interval_months integer NOT NULL DEFAULT 24
        CHECK (review_interval_months BETWEEN 1 AND 36),
    has_certified_sst_system boolean NOT NULL DEFAULT false,
    published_at timestamptz,
    published_by_membership_id uuid REFERENCES organization_memberships(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, version),
    -- Without certification the norm does not allow stretching past 24 months.
    CHECK (has_certified_sst_system OR review_interval_months <= 24)
);

CREATE OR REPLACE FUNCTION prevent_published_criteria_mutation() RETURNS trigger AS $$
BEGIN
    IF OLD.published_at IS NOT NULL THEN
        RAISE EXCEPTION
            'critérios do GRO já publicados são imutáveis; publique uma nova versão';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS gro_risk_criteria_immutable ON gro_risk_criteria;
CREATE TRIGGER gro_risk_criteria_immutable
BEFORE UPDATE OR DELETE ON gro_risk_criteria
FOR EACH ROW EXECUTE FUNCTION prevent_published_criteria_mutation();

ALTER TABLE assessment_campaigns
  ADD COLUMN IF NOT EXISTS criteria_id uuid REFERENCES gro_risk_criteria(id) ON DELETE RESTRICT;

-- ---------------------------------------------------------------------------
-- Inventário de riscos: the nine minimum fields of 1.5.7.3.2.
-- ---------------------------------------------------------------------------
ALTER TABLE psychosocial_risk_inventory
  ADD COLUMN IF NOT EXISTS criteria_id uuid REFERENCES gro_risk_criteria(id) ON DELETE RESTRICT,
  -- a) caracterização dos processos e ambientes de trabalho
  ADD COLUMN IF NOT EXISTS process_characterization text NOT NULL DEFAULT '',
  -- b) caracterização das atividades
  ADD COLUMN IF NOT EXISTS activity_characterization text NOT NULL DEFAULT '',
  -- c) descrição do perigo, com fontes e/ou circunstâncias
  ADD COLUMN IF NOT EXISTS hazard_description text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS hazard_sources text NOT NULL DEFAULT '',
  -- d) possíveis lesões ou agravos à saúde
  ADD COLUMN IF NOT EXISTS possible_harms text[] NOT NULL DEFAULT ARRAY[]::text[],
  ADD COLUMN IF NOT EXISTS selected_consequence text NOT NULL DEFAULT '',
  -- e) grupos de trabalhadores expostos
  ADD COLUMN IF NOT EXISTS exposed_groups text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS exposed_workers integer NOT NULL DEFAULT 0
      CHECK (exposed_workers >= 0),
  -- f) medidas de prevenção implementadas
  ADD COLUMN IF NOT EXISTS implemented_measures text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS measure_efficacy text NOT NULL DEFAULT 'none'
      CHECK (measure_efficacy IN
          ('none', 'insufficient', 'partial', 'effective', 'eliminated')),
  -- g) caracterização da exposição
  ADD COLUMN IF NOT EXISTS exposure_characterization text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS exposure_level smallint
      CHECK (exposure_level IS NULL OR exposure_level BETWEEN 1 AND 5),
  -- h) dados da análise preliminar / resultados da avaliação de ergonomia
  --    nos termos da NR-17 (a AEP a que este inventário se integra)
  ADD COLUMN IF NOT EXISTS aep_reference text NOT NULL DEFAULT '',
  -- i) classificação para fins de elaboração do plano de ação
  ADD COLUMN IF NOT EXISTS risk_classification text NOT NULL DEFAULT ''
  ;

-- 1.5.4.4.6: the assessment is a continuous process with a due date.
ALTER TABLE psychosocial_risk_inventory
  ADD COLUMN IF NOT EXISTS review_due_at timestamptz,
  ADD COLUMN IF NOT EXISTS review_trigger text
      CHECK (review_trigger IS NULL OR review_trigger IN (
          'scheduled',              -- a cada dois anos
          'residual_risk',          -- a) após implementação das medidas
          'process_change',         -- b) inovações e modificações
          'measure_ineffective',    -- c) inadequação/insuficiência/ineficácia
          'accident_or_disease',    -- d) acidente ou doença relacionada
          'legal_change',           -- e) mudança nos requisitos legais
          'worker_or_cipa_request'  -- f) solicitação justificada
      ));

-- 1.5.7.3.3.1: the history of updates is kept for at least twenty years, so
-- superseded rows are versioned rather than overwritten.
CREATE TABLE IF NOT EXISTS psychosocial_risk_inventory_history (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    inventory_id uuid NOT NULL,
    snapshot jsonb NOT NULL,
    superseded_at timestamptz NOT NULL DEFAULT now(),
    retain_until timestamptz NOT NULL DEFAULT (now() + interval '20 years')
);

CREATE INDEX IF NOT EXISTS psychosocial_risk_inventory_history_org_idx
    ON psychosocial_risk_inventory_history (organization_id, inventory_id);

CREATE OR REPLACE FUNCTION prevent_inventory_history_loss() RETURNS trigger AS $$
BEGIN
    IF OLD.retain_until > now() THEN
        RAISE EXCEPTION
            'histórico do inventário deve ser mantido por 20 anos (NR-1 1.5.7.3.3.1)';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS psychosocial_risk_inventory_history_retention
    ON psychosocial_risk_inventory_history;
CREATE TRIGGER psychosocial_risk_inventory_history_retention
BEFORE UPDATE OR DELETE ON psychosocial_risk_inventory_history
FOR EACH ROW EXECUTE FUNCTION prevent_inventory_history_loss();

-- ---------------------------------------------------------------------------
-- Plano de ação: 1.5.5.2.2 requires cronograma, responsáveis, formas de
-- acompanhamento e aferição de resultados; 1.5.5.3.1 requires the record of
-- implementation. The measure hierarchy follows 1.4.1 "g" and 1.5.5.1.2 — with
-- no EPI, because there is none against how work is organized.
-- ---------------------------------------------------------------------------
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_measure_type_check;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_measure_type_check
  CHECK (measure_type IN (
      'elimination', 'substitution', 'collective', 'administrative', 'monitoring'
  ));

ALTER TABLE psychosocial_action_plan
  ADD COLUMN IF NOT EXISTS monitoring_method text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS result_measurement text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS implemented_at timestamptz,
  ADD COLUMN IF NOT EXISTS effectiveness_reviewed_at timestamptz,
  ADD COLUMN IF NOT EXISTS effectiveness text
      CHECK (effectiveness IS NULL OR effectiveness IN
          ('none', 'insufficient', 'partial', 'effective', 'eliminated')),
  -- 1.5.5.2.1.1: workers possibly affected raise the priority of the action.
  ADD COLUMN IF NOT EXISTS exposed_workers integer NOT NULL DEFAULT 0
      CHECK (exposed_workers >= 0),
  ADD COLUMN IF NOT EXISTS priority_rank integer;

-- ---------------------------------------------------------------------------
-- Participação, consulta e comunicação (1.5.3.3).
--
-- The Cartilha is blunt about why this table exists: em caso de fiscalização, a
-- ausência desses registros pode gerar presunção de omissão patronal. A CIPA
-- minute or an attendance list is evidence; a claim of consultation is not.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS worker_participation_records (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    unit_id uuid REFERENCES organization_units(id) ON DELETE RESTRICT,
    campaign_id uuid REFERENCES assessment_campaigns(id) ON DELETE SET NULL,
    record_type text NOT NULL
        CHECK (record_type IN (
            'cipa_minutes',        -- manifestações da CIPA (1.5.3.3 "b")
            'consultation',        -- consulta formal aos trabalhadores
            'training',            -- noções básicas de GRO (1.5.3.3 "a")
            'risk_communication',  -- comunicação do inventário e do plano ("c")
            'focus_group',
            'workplace_observation'
        )),
    occurred_on date NOT NULL,
    subject text NOT NULL,
    attendee_count integer NOT NULL DEFAULT 0 CHECK (attendee_count >= 0),
    evidence_reference text NOT NULL DEFAULT '',
    recorded_by_membership_id uuid REFERENCES organization_memberships(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS worker_participation_records_org_idx
    ON worker_participation_records (organization_id, occurred_on DESC);

-- ---------------------------------------------------------------------------
-- The aggregate now carries the hazard metadata the gradation needs, so the
-- application never has to guess a consequence or an efficacy.
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
           dimension.consequences,
           coalesce(max(inventory.measure_efficacy), 'none') AS measure_efficacy,
           coalesce(max(unit.headcount), 0) AS exposed_workers
    FROM response_dimension scored
    JOIN assessment_dimensions dimension
      ON dimension.id = scored.response_dimension_id
    LEFT JOIN organization_units unit
      ON unit.id = scored.response_unit_id
    -- Efficacy of what is already in place for this hazard, from the previous
    -- inventory cycle. 1.5.4.4.5.3 makes it part of the probability, and
    -- 1.5.4.4.6 "a" makes the next round an assessment of residual risk.
    LEFT JOIN psychosocial_risk_inventory inventory
      ON inventory.dimension_id = dimension.id
     AND inventory.organization_id = campaign_org
     AND inventory.campaign_id <> target_campaign_id
    GROUP BY scored.response_unit_id, dimension.id, dimension.nr1_factor,
             dimension.polarity, dimension.cut_favorable, dimension.cut_critical,
             dimension.consequences
    HAVING count(*) >= effective_cut_floor;
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_dimension_scores(uuid, integer) FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Row level security for the new tables
-- ---------------------------------------------------------------------------
ALTER TABLE gro_risk_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_participation_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE psychosocial_risk_inventory_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS gro_risk_criteria_read ON gro_risk_criteria;
CREATE POLICY gro_risk_criteria_read ON gro_risk_criteria FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);
DROP POLICY IF EXISTS gro_risk_criteria_manage ON gro_risk_criteria;
CREATE POLICY gro_risk_criteria_manage ON gro_risk_criteria FOR ALL
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

-- 1.5.7.2.1 puts the PGR documents at the disposal of the workers themselves
-- and of their unions, so participation records are readable by every active
-- member, not only by the compliance side.
DROP POLICY IF EXISTS worker_participation_records_read ON worker_participation_records;
CREATE POLICY worker_participation_records_read ON worker_participation_records
FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);
DROP POLICY IF EXISTS worker_participation_records_manage ON worker_participation_records;
CREATE POLICY worker_participation_records_manage ON worker_participation_records FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY[
      'owner','administrator','compliance_manager','occupational_health'
  ]::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY[
      'owner','administrator','compliance_manager','occupational_health'
  ]::text[])
);

DROP POLICY IF EXISTS psychosocial_risk_inventory_history_read
    ON psychosocial_risk_inventory_history;
CREATE POLICY psychosocial_risk_inventory_history_read
ON psychosocial_risk_inventory_history FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY[
      'owner','administrator','compliance_manager','occupational_health','auditor'
  ]::text[])
);
DROP POLICY IF EXISTS psychosocial_risk_inventory_history_insert
    ON psychosocial_risk_inventory_history;
CREATE POLICY psychosocial_risk_inventory_history_insert
ON psychosocial_risk_inventory_history FOR INSERT WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);

-- ---------------------------------------------------------------------------
-- Runtime grants
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT SELECT ON
            gro_risk_criteria, worker_participation_records,
            psychosocial_risk_inventory_history
        TO froid_runtime;
        GRANT INSERT ON
            gro_risk_criteria, worker_participation_records,
            psychosocial_risk_inventory_history
        TO froid_runtime;
        GRANT UPDATE ON gro_risk_criteria, worker_participation_records
        TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_dimension_scores(uuid, integer)
            TO froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('011_nr1_pgr_documentation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
