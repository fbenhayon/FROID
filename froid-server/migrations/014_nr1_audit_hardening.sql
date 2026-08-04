-- Hardening from the general audit of the NR-1 module.
--
-- The important one is the first. The others are correctness.
--
-- 1. DIFFERENCING ATTACK ON AN OPEN CAMPAIGN.
--    Until now the aggregate was served while the campaign was still
--    collecting. A cohort floor stops a small group being reported, but it does
--    not stop an observer who watches the same cohort grow: read the panel at
--    n=50, read it again at n=51, and the shift in the mean gives you the
--    fifty-first person's score. Whoever answered in between is identifiable by
--    timing. The floor was never the whole guarantee — stability of the cohort
--    is the other half.
--    From here the aggregate is only produced for a closed campaign. The
--    response count stays available while collecting, so adhesion can still be
--    followed without any result leaking.
--
-- 2. The runtime role held INSERT on the raw answer tables. It never needed it:
--    froid_nr1_submit_response is SECURITY DEFINER and writes as the owner. The
--    grant only widened what a bug in the application layer could reach, so it
--    goes. The runtime role now has no access at all to raw answers — neither
--    read nor write.
--
-- 3. exposed_workers fell back to zero on an organization-wide campaign, which
--    silently disabled the priority rule of 1.5.5.2.1.1 exactly where the most
--    workers are affected.
--
-- 4. The efficacy carried into probability could be picked up from a review
--    belonging to a LATER cycle, which would grade a campaign using knowledge
--    that did not exist when it ran. It must come from a cycle that closed
--    before this one opened.

BEGIN;

-- ---------------------------------------------------------------------------
-- 2. Raw answers become unreachable for the runtime role.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        REVOKE ALL ON assessment_responses FROM froid_runtime;
        REVOKE ALL ON assessment_response_items FROM froid_runtime;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1, 3 and 4: the aggregate, rebuilt.
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
    campaign_status text;
    campaign_opens timestamptz;
    campaign_headcount integer;
BEGIN
    effective_cut_floor := GREATEST(
        coalesce(requested_min_cohort, froid_nr1_min_cohort_cut()),
        froid_nr1_min_cohort_cut()
    );

    SELECT campaign.organization_id, campaign.status, campaign.opens_at,
           campaign.target_headcount
      INTO campaign_org, campaign_status, campaign_opens, campaign_headcount
    FROM assessment_campaigns campaign
    WHERE campaign.id = target_campaign_id;

    IF campaign_org IS NULL OR campaign_org <> froid_current_organization_id() THEN
        RETURN;
    END IF;

    IF NOT froid_membership_is_active() THEN
        RETURN;
    END IF;

    -- A cohort that is still growing can be differenced. Results wait for the
    -- campaign to close; the response count remains readable meanwhile.
    IF campaign_status <> 'closed' THEN
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
           round(coalesce(stddev_samp(scored.subject_score), 0), 3) AS score_stddev,
           dimension.consequences,
           coalesce(
               (
                   SELECT review.measure_efficacy
                   FROM measure_effectiveness_reviews review
                   JOIN assessment_campaigns prior
                     ON prior.id = review.followup_campaign_id
                   WHERE review.organization_id = campaign_org
                     AND review.dimension_id = dimension.id
                     AND review.unit_id IS NOT DISTINCT FROM scored.response_unit_id
                     AND review.followup_campaign_id <> target_campaign_id
                     -- Only a cycle that had already closed when this campaign
                     -- opened. Otherwise a later review would retroactively
                     -- change how an earlier campaign was graded.
                     AND prior.closes_at <= campaign_opens
                   ORDER BY prior.closes_at DESC, review.reviewed_at DESC
                   LIMIT 1
               ),
               'none'
           ) AS measure_efficacy,
           -- On an organization-wide campaign there is no unit headcount, so
           -- fall back to the campaign's target population. Zero here would
           -- silently switch off the priority rule of 1.5.5.2.1.1 precisely
           -- where the most workers are affected.
           GREATEST(
               coalesce(max(unit.headcount), 0),
               CASE WHEN scored.response_unit_id IS NULL
                    THEN coalesce(campaign_headcount, 0) ELSE 0 END
           ) AS exposed_workers
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

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_nr1_dimension_scores(uuid, integer)
            TO froid_runtime;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Closing a campaign is what makes its result readable, so it is recorded.
-- ---------------------------------------------------------------------------
ALTER TABLE assessment_campaigns
  ADD COLUMN IF NOT EXISTS closed_at timestamptz,
  ADD COLUMN IF NOT EXISTS closed_by_membership_id uuid
      REFERENCES organization_memberships(id) ON DELETE SET NULL;

INSERT INTO schema_migrations (version)
VALUES ('014_nr1_audit_hardening')
ON CONFLICT (version) DO NOTHING;

COMMIT;
