-- NR-1 / Portaria MTE 1.419/2024 — psychosocial risk management for enterprise
-- organizations.
--
-- Design constraint that drives this whole migration: the employer is obliged
-- to map psychosocial risk, but is never entitled to read what an individual
-- employee answered. Raw answers therefore carry NO select policy at all. The
-- only way out of assessment_responses is froid_nr1_dimension_scores(), a
-- SECURITY DEFINER aggregate that clamps the cohort floor in SQL, so the
-- guarantee survives a bug in the application layer.

BEGIN;

-- ---------------------------------------------------------------------------
-- Organizational structure (unidade / setor / grupo homogêneo de exposição)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS organization_units (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    parent_unit_id uuid REFERENCES organization_units(id) ON DELETE RESTRICT,
    unit_type text NOT NULL DEFAULT 'sector'
        CHECK (unit_type IN ('site', 'sector', 'exposure_group')),
    name text NOT NULL,
    external_code text,
    headcount integer NOT NULL DEFAULT 0 CHECK (headcount >= 0),
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id)
);

CREATE INDEX IF NOT EXISTS organization_units_org_idx
    ON organization_units (organization_id, status);

-- ---------------------------------------------------------------------------
-- Instrument catalogue. Deliberately instrument-agnostic and versioned: the
-- COPSOQ III item bank is loaded as DATA, never hardcoded, so a revision of the
-- instrument never requires a schema change and historical campaigns keep
-- scoring against the exact version they were answered under.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_instruments (
    id uuid PRIMARY KEY,
    code text NOT NULL,
    version text NOT NULL,
    title text NOT NULL,
    language text NOT NULL DEFAULT 'pt-BR',
    scale_min integer NOT NULL,
    scale_max integer NOT NULL,
    scale_labels jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_reference text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'retired')),
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (code, version),
    CHECK (scale_max > scale_min)
);

CREATE TABLE IF NOT EXISTS assessment_dimensions (
    id uuid PRIMARY KEY,
    instrument_id uuid NOT NULL REFERENCES assessment_instruments(id) ON DELETE CASCADE,
    code text NOT NULL,
    title text NOT NULL,
    -- Maps the instrument dimension onto the four factor groups the revised
    -- item 1.5 of NR-1 requires the PGR to cover.
    nr1_factor text NOT NULL
        CHECK (nr1_factor IN (
            'work_organization', 'workload_demand',
            'harassment_violence', 'environment_modality'
        )),
    -- 'risk': a higher score means more exposure. 'protective': a higher score
    -- means more resource, so the gradation is inverted before grading.
    polarity text NOT NULL DEFAULT 'risk'
        CHECK (polarity IN ('risk', 'protective')),
    cut_favorable numeric(6,3) NOT NULL,
    cut_critical numeric(6,3) NOT NULL,
    display_order integer NOT NULL DEFAULT 0,
    UNIQUE (instrument_id, code)
);

CREATE TABLE IF NOT EXISTS assessment_items (
    id uuid PRIMARY KEY,
    instrument_id uuid NOT NULL REFERENCES assessment_instruments(id) ON DELETE CASCADE,
    dimension_id uuid NOT NULL REFERENCES assessment_dimensions(id) ON DELETE CASCADE,
    code text NOT NULL,
    statement text NOT NULL,
    reverse_scored boolean NOT NULL DEFAULT false,
    display_order integer NOT NULL DEFAULT 0,
    UNIQUE (instrument_id, code)
);

-- ---------------------------------------------------------------------------
-- Measurement rounds
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_campaigns (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    instrument_id uuid NOT NULL REFERENCES assessment_instruments(id) ON DELETE RESTRICT,
    unit_id uuid REFERENCES organization_units(id) ON DELETE RESTRICT,
    title text NOT NULL,
    reference_period text NOT NULL DEFAULT '',
    target_headcount integer NOT NULL DEFAULT 0 CHECK (target_headcount >= 0),
    opens_at timestamptz NOT NULL,
    closes_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'open', 'closed', 'cancelled')),
    created_by_membership_id uuid REFERENCES organization_memberships(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id),
    CHECK (closes_at > opens_at)
);

CREATE INDEX IF NOT EXISTS assessment_campaigns_org_idx
    ON assessment_campaigns (organization_id, status);

-- One row per invited worker. subject_pseudonym is a salted hash of the payroll
-- number computed by the application; neither CPF nor name is ever stored here.
-- It exists to stop double submission and to allow longitudinal series, which
-- is the evidence that sustains the employer's defence.
CREATE TABLE IF NOT EXISTS assessment_invitations (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    campaign_id uuid NOT NULL REFERENCES assessment_campaigns(id) ON DELETE CASCADE,
    unit_id uuid REFERENCES organization_units(id) ON DELETE RESTRICT,
    subject_pseudonym text NOT NULL,
    token_hash text NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'responded', 'expired', 'revoked')),
    invited_at timestamptz NOT NULL DEFAULT now(),
    responded_at timestamptz,
    UNIQUE (campaign_id, subject_pseudonym),
    UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS assessment_invitations_campaign_idx
    ON assessment_invitations (campaign_id, status);

-- A submitted questionnaire. Note there is no patient_id and no user_id here:
-- the clinical track (employee as patient of the company's professional) and
-- the compliance track are joined only at the aggregate level, never per row.
CREATE TABLE IF NOT EXISTS assessment_responses (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    campaign_id uuid NOT NULL REFERENCES assessment_campaigns(id) ON DELETE CASCADE,
    invitation_id uuid NOT NULL REFERENCES assessment_invitations(id) ON DELETE RESTRICT,
    unit_id uuid REFERENCES organization_units(id) ON DELETE RESTRICT,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    completed boolean NOT NULL DEFAULT false,
    UNIQUE (invitation_id)
);

CREATE INDEX IF NOT EXISTS assessment_responses_campaign_idx
    ON assessment_responses (campaign_id, unit_id);

CREATE TABLE IF NOT EXISTS assessment_response_items (
    response_id uuid NOT NULL REFERENCES assessment_responses(id) ON DELETE CASCADE,
    item_id uuid NOT NULL REFERENCES assessment_items(id) ON DELETE RESTRICT,
    value integer NOT NULL,
    PRIMARY KEY (response_id, item_id)
);

-- ---------------------------------------------------------------------------
-- PGR outputs: risk inventory and action plan
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS psychosocial_risk_inventory (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    campaign_id uuid NOT NULL REFERENCES assessment_campaigns(id) ON DELETE RESTRICT,
    unit_id uuid REFERENCES organization_units(id) ON DELETE RESTRICT,
    dimension_id uuid NOT NULL REFERENCES assessment_dimensions(id) ON DELETE RESTRICT,
    nr1_factor text NOT NULL,
    cohort_size integer NOT NULL CHECK (cohort_size >= 0),
    mean_score numeric(6,3) NOT NULL,
    severity smallint NOT NULL CHECK (severity BETWEEN 1 AND 5),
    probability smallint NOT NULL CHECK (probability BETWEEN 1 AND 5),
    risk_level text NOT NULL
        CHECK (risk_level IN ('low', 'moderate', 'high', 'critical')),
    rationale text NOT NULL DEFAULT '',
    generated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, unit_id, dimension_id)
);

CREATE INDEX IF NOT EXISTS psychosocial_risk_inventory_org_idx
    ON psychosocial_risk_inventory (organization_id, campaign_id);

CREATE TABLE IF NOT EXISTS psychosocial_action_plan (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    inventory_id uuid NOT NULL REFERENCES psychosocial_risk_inventory(id) ON DELETE CASCADE,
    measure text NOT NULL,
    -- Follows the NR-1 hierarchy of control: eliminate the risk at source,
    -- reduce it, then administrative/organizational measures.
    measure_type text NOT NULL
        CHECK (measure_type IN ('elimination', 'reduction', 'administrative', 'monitoring')),
    responsible_membership_id uuid REFERENCES organization_memberships(id) ON DELETE SET NULL,
    due_date date,
    status text NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'done', 'cancelled')),
    evidence text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS psychosocial_action_plan_org_idx
    ON psychosocial_action_plan (organization_id, status);

-- ---------------------------------------------------------------------------
-- k-anonymity floors, enforced in SQL rather than in application code.
-- FROID_NR1_MIN_COHORT_TOTAL  = 50 responses before a campaign yields anything
-- FROID_NR1_MIN_COHORT_CUT    = 10 responses before a unit-level cut is shown
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION froid_nr1_min_cohort_total() RETURNS integer
LANGUAGE sql IMMUTABLE AS $$ SELECT 50 $$;

CREATE OR REPLACE FUNCTION froid_nr1_min_cohort_cut() RETURNS integer
LANGUAGE sql IMMUTABLE AS $$ SELECT 10 $$;

-- The only sanctioned path out of the raw answer tables.
--
-- Callers may raise the floor but never lower it: the requested minimum is
-- clamped with GREATEST against the hard floor. A campaign that has not reached
-- the total floor returns zero rows, not a partial view.
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
    critical_ratio numeric
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
-- The OUT parameters share names with the columns being selected. Resolve any
-- such reference to the column, so the aggregate never silently reads back an
-- uninitialised OUT variable.
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

    -- Never let one tenant aggregate another tenant's campaign, even though
    -- this function runs as definer and bypasses RLS.
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

    -- Two stages on purpose. The per-respondent dimension score has to exist
    -- before the cohort statistics, otherwise 'probability' would be guessed
    -- from a mean instead of measured as the share of workers actually in the
    -- critical band — and NR-1 grades risk by severity AND probability.
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
           ) AS critical_ratio
    FROM response_dimension scored
    JOIN assessment_dimensions dimension
      ON dimension.id = scored.response_dimension_id
    GROUP BY scored.response_unit_id, dimension.id, dimension.nr1_factor,
             dimension.polarity, dimension.cut_favorable, dimension.cut_critical
    HAVING count(*) >= effective_cut_floor;
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_dimension_scores(uuid, integer) FROM PUBLIC;

-- Anonymous submission. The worker has no FROID login and no membership: the
-- single-use invitation token is the whole authorization, so this runs as
-- definer. It validates the campaign window, refuses a second submission, and
-- silently drops any answer whose item does not belong to the campaign's own
-- instrument, so a token holder cannot inject foreign items.
CREATE OR REPLACE FUNCTION froid_nr1_submit_response(
    submitted_token_hash text,
    answers jsonb
)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    invitation assessment_invitations%ROWTYPE;
    campaign assessment_campaigns%ROWTYPE;
    new_response_id uuid;
    accepted_items integer;
BEGIN
    SELECT * INTO invitation
    FROM assessment_invitations
    WHERE token_hash = submitted_token_hash;

    IF NOT FOUND OR invitation.status <> 'pending' THEN
        RETURN false;
    END IF;

    SELECT * INTO campaign
    FROM assessment_campaigns
    WHERE id = invitation.campaign_id;

    IF NOT FOUND OR campaign.status <> 'open' THEN
        RETURN false;
    END IF;
    IF now() < campaign.opens_at OR now() > campaign.closes_at THEN
        RETURN false;
    END IF;

    new_response_id := gen_random_uuid();

    INSERT INTO assessment_responses
        (id, organization_id, campaign_id, invitation_id, unit_id, completed)
    VALUES (
        new_response_id, invitation.organization_id, invitation.campaign_id,
        invitation.id, invitation.unit_id, true
    );

    INSERT INTO assessment_response_items (response_id, item_id, value)
    SELECT new_response_id, item.id, (entry.value)::int
    FROM jsonb_each_text(answers) AS entry(key, value)
    JOIN assessment_items item
      ON item.id = (entry.key)::uuid
     AND item.instrument_id = campaign.instrument_id
    JOIN assessment_instruments instrument
      ON instrument.id = item.instrument_id
    WHERE (entry.value)::int BETWEEN instrument.scale_min AND instrument.scale_max;

    GET DIAGNOSTICS accepted_items = ROW_COUNT;
    IF accepted_items = 0 THEN
        RAISE EXCEPTION 'submission carries no valid item for this instrument';
    END IF;

    UPDATE assessment_invitations
    SET status = 'responded', responded_at = now()
    WHERE id = invitation.id;

    RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_submit_response(text, jsonb) FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------
ALTER TABLE organization_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_response_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE psychosocial_risk_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE psychosocial_action_plan ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS organization_units_read ON organization_units;
CREATE POLICY organization_units_read ON organization_units FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);
DROP POLICY IF EXISTS organization_units_manage ON organization_units;
CREATE POLICY organization_units_manage ON organization_units FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
);

DROP POLICY IF EXISTS assessment_campaigns_read ON assessment_campaigns;
CREATE POLICY assessment_campaigns_read ON assessment_campaigns FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY[
      'owner','administrator','compliance_manager','occupational_health','auditor'
  ]::text[])
);
DROP POLICY IF EXISTS assessment_campaigns_manage ON assessment_campaigns;
CREATE POLICY assessment_campaigns_manage ON assessment_campaigns FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
);

-- Invitations are dispatch state, not answers. Even so, no role may enumerate
-- the pseudonym list together with responses, so SELECT is limited to the
-- roles that run the campaign and the table carries no join to answers that
-- would survive the aggregate function.
DROP POLICY IF EXISTS assessment_invitations_manage ON assessment_invitations;
CREATE POLICY assessment_invitations_manage ON assessment_invitations FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
);

-- Raw answers: INSERT only. There is deliberately NO select/update/delete
-- policy on these two tables. With RLS enabled and no permissive SELECT policy,
-- PostgreSQL denies every read to non-owner roles, so the aggregate function
-- above is the only exit — including for the employer, for the professional,
-- and for FROID's own support staff operating through the runtime role.
DROP POLICY IF EXISTS assessment_responses_insert ON assessment_responses;
CREATE POLICY assessment_responses_insert ON assessment_responses FOR INSERT
WITH CHECK (
  organization_id=froid_current_organization_id()
);

DROP POLICY IF EXISTS assessment_response_items_insert ON assessment_response_items;
CREATE POLICY assessment_response_items_insert ON assessment_response_items FOR INSERT
WITH CHECK (true);

DROP POLICY IF EXISTS psychosocial_risk_inventory_read ON psychosocial_risk_inventory;
CREATE POLICY psychosocial_risk_inventory_read ON psychosocial_risk_inventory FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY[
      'owner','administrator','compliance_manager','occupational_health','auditor'
  ]::text[])
);
DROP POLICY IF EXISTS psychosocial_risk_inventory_manage ON psychosocial_risk_inventory;
CREATE POLICY psychosocial_risk_inventory_manage ON psychosocial_risk_inventory FOR ALL
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

DROP POLICY IF EXISTS psychosocial_action_plan_read ON psychosocial_action_plan;
CREATE POLICY psychosocial_action_plan_read ON psychosocial_action_plan FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY[
      'owner','administrator','compliance_manager','occupational_health','auditor'
  ]::text[])
);
DROP POLICY IF EXISTS psychosocial_action_plan_manage ON psychosocial_action_plan;
CREATE POLICY psychosocial_action_plan_manage ON psychosocial_action_plan FOR ALL
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
        GRANT SELECT ON
            organization_units, assessment_instruments, assessment_dimensions,
            assessment_items, assessment_campaigns, assessment_invitations,
            psychosocial_risk_inventory, psychosocial_action_plan
        TO froid_runtime;
        -- Note the absence of SELECT on assessment_responses and
        -- assessment_response_items: the runtime role can write an answer and
        -- can aggregate, but cannot read one back.
        GRANT INSERT ON assessment_responses, assessment_response_items
        TO froid_runtime;
        GRANT INSERT, UPDATE ON
            organization_units, assessment_campaigns, assessment_invitations,
            psychosocial_risk_inventory, psychosocial_action_plan
        TO froid_runtime;
        GRANT DELETE ON psychosocial_action_plan TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_dimension_scores(uuid, integer)
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_submit_response(text, jsonb)
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_min_cohort_total() TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_min_cohort_cut() TO froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('010_nr1_psychosocial_compliance')
ON CONFLICT (version) DO NOTHING;

COMMIT;
