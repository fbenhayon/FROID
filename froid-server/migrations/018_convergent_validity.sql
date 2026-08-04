-- Convergent validity: the evidence that answers "who validated this?".
--
-- FROID does not administer the instrument. The professional applies the
-- PHQ-9, the GAD-7 or whatever their practice already uses, and records the
-- resulting score here. That boundary is the reason this schema stores a
-- score and never an item response: a system that administered and scored a
-- psychometric instrument would be one, which is exactly what the product
-- must not become. It also avoids holding copyrighted item text.
--
-- Participation is opt-in and separable from care. A patient who declines
-- research must still get the full clinical product, so nothing here is
-- required by any clinical path.

BEGIN;

CREATE TABLE IF NOT EXISTS validation_instruments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    score_min       NUMERIC NOT NULL,
    score_max       NUMERIC NOT NULL,
    -- Higher score means more of the construct. False for instruments scored
    -- the other way round; without it, a correlation sign is uninterpretable.
    higher_is_more  BOOLEAN NOT NULL DEFAULT TRUE,
    source_citation TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT validation_instruments_range CHECK (score_max > score_min)
);

INSERT INTO validation_instruments
    (code, display_name, score_min, score_max, higher_is_more, source_citation)
VALUES
    ('PHQ-9', 'Patient Health Questionnaire-9', 0, 27, TRUE,
     'Kroenke K, Spitzer RL, Williams JBW. J Gen Intern Med. 2001;16(9):606-13.'),
    ('GAD-7', 'Generalized Anxiety Disorder-7', 0, 21, TRUE,
     'Spitzer RL, Kroenke K, Williams JBW, Lowe B. Arch Intern Med. 2006;166(10):1092-7.')
ON CONFLICT (code) DO NOTHING;

-- One administration of one instrument to one patient, by the professional.
CREATE TABLE IF NOT EXISTS validation_administrations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id       UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    instrument_id    UUID NOT NULL REFERENCES validation_instruments(id),
    session_id       TEXT,
    administered_at  TIMESTAMPTZ NOT NULL,
    total_score      NUMERIC NOT NULL,
    -- Who applied it. A score with no responsible professional is not
    -- evidence of anything.
    administered_by  UUID NOT NULL REFERENCES users(id),
    -- Research consent is a column, not a policy note. A row cannot exist
    -- without it being explicitly true, so no later query has to remember to
    -- filter: the unconsented row was never written.
    research_consent BOOLEAN NOT NULL,
    consent_version  TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT validation_admin_consent CHECK (research_consent = TRUE),
    CONSTRAINT validation_admin_consent_version CHECK (length(trim(consent_version)) > 0),
    CONSTRAINT validation_admin_unique UNIQUE (patient_id, instrument_id, administered_at)
);

CREATE INDEX IF NOT EXISTS validation_admin_org_idx
    ON validation_administrations (organization_id, administered_at);

-- The FROID side of the pair: what the patterns measured in the window that
-- corresponds to this administration.
CREATE TABLE IF NOT EXISTS validation_observations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    administration_id UUID NOT NULL REFERENCES validation_administrations(id) ON DELETE CASCADE,
    pattern_key       TEXT NOT NULL,
    pattern_value     NUMERIC NOT NULL,
    -- Quality of the acquisition that produced the value. A validity study
    -- built on unusable windows measures the microphone, not the patient.
    coverage          NUMERIC,
    confidence        NUMERIC,
    window_seconds    INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT validation_obs_unique UNIQUE (administration_id, pattern_key)
);

CREATE INDEX IF NOT EXISTS validation_obs_pattern_idx
    ON validation_observations (pattern_key);

ALTER TABLE validation_administrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE validation_observations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS validation_admin_tenant ON validation_administrations;
CREATE POLICY validation_admin_tenant ON validation_administrations
    USING (organization_id = current_setting('froid.organization_id', TRUE)::uuid);

DROP POLICY IF EXISTS validation_obs_tenant ON validation_observations;
CREATE POLICY validation_obs_tenant ON validation_observations
    USING (EXISTS (
        SELECT 1 FROM validation_administrations a
        WHERE a.id = validation_observations.administration_id
          AND a.organization_id = current_setting('froid.organization_id', TRUE)::uuid
    ));

-- The pairs, already joined and already filtered for usable acquisition.
--
-- SECURITY DEFINER and no patient identifier in the output: a validity study
-- needs the pairs, never the people. The quality floors match the ones the
-- product uses to mark a reading unusable on screen — a window the clinician
-- is told not to trust must not silently become evidence.
CREATE OR REPLACE FUNCTION froid_validation_pairs(
    p_pattern_key TEXT,
    p_instrument_code TEXT
)
RETURNS TABLE (pattern_value NUMERIC, instrument_score NUMERIC)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT o.pattern_value, a.total_score
    FROM validation_observations o
    JOIN validation_administrations a ON a.id = o.administration_id
    JOIN validation_instruments i ON i.id = a.instrument_id
    WHERE o.pattern_key = p_pattern_key
      AND i.code = p_instrument_code
      AND a.research_consent = TRUE
      AND (o.coverage IS NULL OR o.coverage >= 0.80)
      AND (o.confidence IS NULL OR o.confidence >= 0.70);
$$;

INSERT INTO schema_migrations (version)
VALUES ('018_convergent_validity')
ON CONFLICT (version) DO NOTHING;

COMMIT;
