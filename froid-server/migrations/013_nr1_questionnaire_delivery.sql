-- Delivery of the questionnaire to the worker, and the support channel.
--
-- Two things this migration exists for.
--
-- 1. The respondent has no FROID login and no membership, so the form cannot be
--    fetched through RLS. froid_nr1_questionnaire() is the read counterpart of
--    froid_nr1_submit_response(): the single-use token is the whole
--    authorization, it returns only what is needed to render the form, and it
--    never returns the pseudonym or anything identifying the campaign's
--    population.
--
-- 2. The anonymous design has a consequence that must be decided on purpose
--    rather than discovered later: if a worker signals serious distress, nobody
--    can reach them. That is the correct trade — psychosocial risk management
--    is preventive and collective, and the MTE rejects individual clinical
--    screening as the instrument of this process. The answer is to decouple:
--    every questionnaire ends with a support channel offered to everyone,
--    identical regardless of what was answered, with no automatic trigger.
--    A campaign cannot be opened without one.

BEGIN;

ALTER TABLE assessment_campaigns
  ADD COLUMN IF NOT EXISTS support_channel_label text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS support_channel_detail text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS purpose_notice text NOT NULL DEFAULT '';

-- Guarding at the database rather than in a form validator: an open campaign
-- without a support channel is the one failure mode nobody should be able to
-- ship by accident.
CREATE OR REPLACE FUNCTION enforce_campaign_open_requirements() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'open' THEN
        IF coalesce(btrim(NEW.support_channel_label), '') = ''
           OR coalesce(btrim(NEW.support_channel_detail), '') = '' THEN
            RAISE EXCEPTION
                'campanha nao pode ser aberta sem canal de apoio ao colaborador';
        END IF;
        IF coalesce(btrim(NEW.purpose_notice), '') = '' THEN
            RAISE EXCEPTION
                'campanha nao pode ser aberta sem aviso de finalidade da coleta';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS assessment_campaigns_open_requirements ON assessment_campaigns;
CREATE TRIGGER assessment_campaigns_open_requirements
BEFORE INSERT OR UPDATE ON assessment_campaigns
FOR EACH ROW EXECUTE FUNCTION enforce_campaign_open_requirements();

-- The form, fetched by token. Returns null when the token is unusable, and it
-- is deliberately the same null for an unknown token, an already used one and a
-- closed campaign, so the endpoint cannot be used to probe who was invited.
CREATE OR REPLACE FUNCTION froid_nr1_questionnaire(submitted_token_hash text)
RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    invitation assessment_invitations%ROWTYPE;
    campaign assessment_campaigns%ROWTYPE;
    instrument assessment_instruments%ROWTYPE;
    payload jsonb;
BEGIN
    SELECT * INTO invitation
    FROM assessment_invitations
    WHERE token_hash = submitted_token_hash;

    IF NOT FOUND OR invitation.status <> 'pending' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO campaign
    FROM assessment_campaigns WHERE id = invitation.campaign_id;

    IF NOT FOUND OR campaign.status <> 'open' THEN
        RETURN NULL;
    END IF;
    IF now() < campaign.opens_at OR now() > campaign.closes_at THEN
        RETURN NULL;
    END IF;

    SELECT * INTO instrument
    FROM assessment_instruments WHERE id = campaign.instrument_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT jsonb_build_object(
        'campaign_title', campaign.title,
        'closes_at', campaign.closes_at,
        'purpose_notice', campaign.purpose_notice,
        'support_channel', jsonb_build_object(
            'label', campaign.support_channel_label,
            'detail', campaign.support_channel_detail
        ),
        'scale', jsonb_build_object(
            'min', instrument.scale_min,
            'max', instrument.scale_max,
            'labels', instrument.scale_labels
        ),
        'items', coalesce(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'item_id', item.id,
                        'statement', item.statement,
                        'dimension', dimension.title
                    )
                    ORDER BY dimension.display_order, item.display_order
                )
                FROM assessment_items item
                JOIN assessment_dimensions dimension
                  ON dimension.id = item.dimension_id
                WHERE item.instrument_id = instrument.id
            ),
            '[]'::jsonb
        )
    ) INTO payload;

    RETURN payload;
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_questionnaire(text) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_nr1_questionnaire(text) TO froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('013_nr1_questionnaire_delivery')
ON CONFLICT (version) DO NOTHING;

COMMIT;
