-- Research consent as a state of the patient, and a revocation that bites.
--
-- Migration 018 records, on each administration, the consent version it was
-- collected under. That answers "was this row lawful when written". It does
-- not answer "may we ask this patient again", which is what the end-of-session
-- prompt needs to know before it appears at all.
--
-- The TCLE promises that withdrawing removes the patient's pairs from the
-- study. A promise like that has to be a function someone can run, not a
-- paragraph someone has to remember.

BEGIN;

CREATE TABLE IF NOT EXISTS patient_research_consent (
    patient_id      UUID PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    consent_version TEXT NOT NULL,
    granted_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    -- Who registered the decision. A consent with no responsible professional
    -- is not a consent.
    registered_by   UUID NOT NULL REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Granted or revoked, never neither and never both. The absence of a row
    -- is the third state, and it means "never asked".
    CONSTRAINT patient_research_consent_state CHECK (
        (granted_at IS NOT NULL AND revoked_at IS NULL)
        OR (revoked_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS patient_research_consent_org_idx
    ON patient_research_consent (organization_id);

ALTER TABLE patient_research_consent ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS patient_research_consent_tenant ON patient_research_consent;
CREATE POLICY patient_research_consent_tenant ON patient_research_consent
    USING (organization_id = current_setting('app.organization_id', TRUE)::uuid);

-- Withdrawal, executed rather than promised.
--
-- The observations go with the administrations by cascade. What cannot be
-- undone — analyses already published — is stated in the TCLE before the
-- patient consents, not discovered by them afterwards.
CREATE OR REPLACE FUNCTION froid_revoke_research_consent(
    p_patient_id UUID,
    p_registered_by UUID
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    removidos INTEGER;
BEGIN
    DELETE FROM validation_administrations WHERE patient_id = p_patient_id;
    GET DIAGNOSTICS removidos = ROW_COUNT;

    UPDATE patient_research_consent
       SET revoked_at = now(), registered_by = p_registered_by, updated_at = now()
     WHERE patient_id = p_patient_id;

    RETURN removidos;
END;
$$;

-- Is this patient currently participating? The end-of-session prompt asks this
-- and shows nothing when the answer is false, so that a patient who declined
-- is never asked again by a screen that forgot.
CREATE OR REPLACE FUNCTION froid_research_consent_active(p_patient_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT COALESCE(
        (SELECT granted_at IS NOT NULL AND revoked_at IS NULL
           FROM patient_research_consent WHERE patient_id = p_patient_id),
        FALSE
    );
$$;

-- Collection progress, without touching any identity.
--
-- The professional dashboard shows n/70 and deliberately no coefficient: a
-- partial correlation on a daily screen becomes a number people remember and
-- repeat out of context. Progress carries no such risk.
CREATE OR REPLACE FUNCTION froid_validation_progress()
RETURNS TABLE (pattern_key TEXT, instrument_code TEXT, pairs BIGINT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT o.pattern_key, i.code, count(*)
    FROM validation_observations o
    JOIN validation_administrations a ON a.id = o.administration_id
    JOIN validation_instruments i ON i.id = a.instrument_id
    WHERE a.research_consent = TRUE
      AND (o.coverage IS NULL OR o.coverage >= 0.80)
      AND (o.confidence IS NULL OR o.confidence >= 0.70)
    GROUP BY o.pattern_key, i.code;
$$;

INSERT INTO schema_migrations (version)
VALUES ('019_research_consent_state')
ON CONFLICT (version) DO NOTHING;

COMMIT;
