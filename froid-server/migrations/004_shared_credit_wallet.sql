BEGIN;

ALTER TABLE organization_wallets
    ADD COLUMN IF NOT EXISTS version bigint NOT NULL DEFAULT 0;

CREATE OR REPLACE FUNCTION froid_apply_credit_event(
    target_organization_id uuid,
    target_membership_id uuid,
    target_actor_user_id uuid,
    credit_delta integer,
    target_event_type text,
    target_idempotency_key text,
    target_session_id text DEFAULT NULL,
    target_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (ledger_id uuid, resulting_balance integer, applied boolean)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    current_balance integer;
    existing_entry credit_ledger%ROWTYPE;
    new_ledger_id uuid;
BEGIN
    IF froid_current_organization_id() IS DISTINCT FROM target_organization_id THEN
        RAISE EXCEPTION 'organization context mismatch' USING ERRCODE = '42501';
    END IF;
    IF froid_current_membership_id() IS DISTINCT FROM target_membership_id THEN
        RAISE EXCEPTION 'membership context mismatch' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM organization_memberships membership
        WHERE membership.id = target_membership_id
          AND membership.organization_id = target_organization_id
          AND membership.user_id = target_actor_user_id
          AND membership.status = 'active'
    ) THEN
        RAISE EXCEPTION 'inactive or mismatched actor' USING ERRCODE = '42501';
    END IF;
    IF target_event_type NOT IN (
        'purchase', 'consumption', 'refund', 'adjustment'
    ) THEN
        RAISE EXCEPTION 'invalid credit event type' USING ERRCODE = '22023';
    END IF;
    IF target_event_type = 'consumption' AND credit_delta <> -1 THEN
        RAISE EXCEPTION 'session consumption must debit exactly one credit'
            USING ERRCODE = '22023';
    END IF;
    IF target_event_type IN ('purchase', 'refund') AND credit_delta <= 0 THEN
        RAISE EXCEPTION 'purchase and refund must add credits'
            USING ERRCODE = '22023';
    END IF;
    IF target_event_type IN ('purchase', 'refund', 'adjustment')
       AND NOT froid_has_role(ARRAY['owner', 'administrator']::text[]) THEN
        RAISE EXCEPTION 'role cannot manage credits' USING ERRCODE = '42501';
    END IF;
    IF target_event_type = 'consumption'
       AND NOT froid_has_role(
           ARRAY['owner', 'administrator', 'professional']::text[]
       ) THEN
        RAISE EXCEPTION 'role cannot consume credits' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO existing_entry
    FROM credit_ledger
    WHERE organization_id = target_organization_id
      AND idempotency_key = target_idempotency_key;
    IF FOUND THEN
        RETURN QUERY SELECT existing_entry.id, existing_entry.balance_after, false;
        RETURN;
    END IF;

    INSERT INTO organization_wallets (organization_id, balance)
    VALUES (target_organization_id, 0)
    ON CONFLICT (organization_id) DO NOTHING;

    SELECT balance INTO current_balance
    FROM organization_wallets
    WHERE organization_id = target_organization_id
    FOR UPDATE;

    IF current_balance + credit_delta < 0 THEN
        RAISE EXCEPTION 'insufficient organization credits' USING ERRCODE = 'P0001';
    END IF;

    UPDATE organization_wallets
    SET balance = balance + credit_delta,
        version = version + 1,
        updated_at = now()
    WHERE organization_id = target_organization_id
    RETURNING balance INTO current_balance;

    new_ledger_id := gen_random_uuid();
    INSERT INTO credit_ledger
        (id, organization_id, delta, balance_after, event_type,
         legacy_session_id, idempotency_key, actor_user_id, metadata)
    VALUES
        (new_ledger_id, target_organization_id, credit_delta,
         current_balance, target_event_type, target_session_id,
         target_idempotency_key, target_actor_user_id,
         coalesce(target_metadata, '{}'::jsonb));

    RETURN QUERY SELECT new_ledger_id, current_balance, true;
END;
$$;

REVOKE ALL ON FUNCTION froid_apply_credit_event(
    uuid, uuid, uuid, integer, text, text, text, jsonb
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_apply_credit_event(
            uuid, uuid, uuid, integer, text, text, text, jsonb
        ) TO froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('004_shared_credit_wallet')
ON CONFLICT (version) DO NOTHING;

COMMIT;
