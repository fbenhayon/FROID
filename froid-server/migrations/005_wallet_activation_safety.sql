BEGIN;

ALTER TABLE organization_wallets ADD COLUMN IF NOT EXISTS authority text
NOT NULL DEFAULT 'legacy' CHECK (authority IN ('legacy','shared'));

CREATE OR REPLACE FUNCTION froid_activate_shared_wallet(
  org uuid, member uuid, actor uuid, expected_balance integer
) RETURNS TABLE (resulting_balance integer, activated boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE wallet organization_wallets%ROWTYPE;
BEGIN
  IF froid_current_organization_id() IS DISTINCT FROM org OR
     froid_current_membership_id() IS DISTINCT FROM member THEN
    RAISE EXCEPTION 'wallet activation context mismatch' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM organization_memberships m
    WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
      AND m.status='active') OR
     NOT froid_has_role(ARRAY['owner','administrator']::text[]) THEN
    RAISE EXCEPTION 'role cannot activate shared wallet' USING ERRCODE='42501';
  END IF;
  SELECT * INTO wallet FROM organization_wallets
    WHERE organization_id=org FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'organization wallet not found' USING ERRCODE='P0002';
  END IF;
  IF wallet.authority='shared' THEN
    RETURN QUERY SELECT wallet.balance,false; RETURN;
  END IF;
  IF wallet.balance<>expected_balance THEN
    RAISE EXCEPTION 'legacy balance reconciliation failed' USING ERRCODE='P0001';
  END IF;
  UPDATE organization_wallets SET authority='shared',version=version+1,
    updated_at=now() WHERE organization_id=org RETURNING balance INTO wallet.balance;
  RETURN QUERY SELECT wallet.balance,true;
END $$;

CREATE OR REPLACE FUNCTION froid_apply_credit_event(
  org uuid, member uuid, actor uuid, delta integer, kind text,
  idem text, session_id text DEFAULT NULL, meta jsonb DEFAULT '{}'::jsonb
) RETURNS TABLE (ledger_id uuid,resulting_balance integer,applied boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE wallet organization_wallets%ROWTYPE; entry credit_ledger%ROWTYPE; new_id uuid;
BEGIN
  IF froid_current_organization_id() IS DISTINCT FROM org OR
     froid_current_membership_id() IS DISTINCT FROM member THEN
    RAISE EXCEPTION 'wallet event context mismatch' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM organization_memberships m
    WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
      AND m.status='active') THEN
    RAISE EXCEPTION 'inactive or mismatched actor' USING ERRCODE='42501';
  END IF;
  IF kind NOT IN ('purchase','consumption','refund','adjustment') OR
     delta=0 OR idem IS NULL OR length(trim(idem))=0 THEN
    RAISE EXCEPTION 'invalid credit event' USING ERRCODE='22023';
  END IF;
  IF kind='consumption' AND delta<>-1 THEN
    RAISE EXCEPTION 'session consumption must debit exactly one credit' USING ERRCODE='22023';
  END IF;
  IF kind IN ('purchase','refund') AND delta<=0 THEN
    RAISE EXCEPTION 'purchase and refund must add credits' USING ERRCODE='22023';
  END IF;
  IF kind IN ('purchase','refund','adjustment') AND
     NOT froid_has_role(ARRAY['owner','administrator']::text[]) THEN
    RAISE EXCEPTION 'role cannot manage credits' USING ERRCODE='42501';
  END IF;
  IF kind='consumption' AND NOT froid_has_role(
    ARRAY['owner','administrator','professional']::text[]) THEN
    RAISE EXCEPTION 'role cannot consume credits' USING ERRCODE='42501';
  END IF;
  SELECT * INTO entry FROM credit_ledger
    WHERE organization_id=org AND idempotency_key=idem;
  IF FOUND THEN RETURN QUERY SELECT entry.id,entry.balance_after,false; RETURN; END IF;
  SELECT * INTO wallet FROM organization_wallets
    WHERE organization_id=org FOR UPDATE;
  IF NOT FOUND OR wallet.authority<>'shared' THEN
    RAISE EXCEPTION 'shared wallet is not active' USING ERRCODE='55000';
  END IF;
  SELECT * INTO entry FROM credit_ledger
    WHERE organization_id=org AND idempotency_key=idem;
  IF FOUND THEN RETURN QUERY SELECT entry.id,entry.balance_after,false; RETURN; END IF;
  IF wallet.balance+delta<0 THEN
    RAISE EXCEPTION 'insufficient organization credits' USING ERRCODE='P0001';
  END IF;
  UPDATE organization_wallets SET balance=balance+delta,version=version+1,
    updated_at=now() WHERE organization_id=org RETURNING balance INTO wallet.balance;
  new_id:=gen_random_uuid();
  INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,
    legacy_session_id,idempotency_key,actor_user_id,metadata)
  VALUES(new_id,org,delta,wallet.balance,kind,session_id,idem,actor,coalesce(meta,'{}'));
  RETURN QUERY SELECT new_id,wallet.balance,true;
END $$;

REVOKE ALL ON FUNCTION froid_activate_shared_wallet(uuid,uuid,uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION froid_apply_credit_event(uuid,uuid,uuid,integer,text,text,text,jsonb) FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
  GRANT EXECUTE ON FUNCTION froid_activate_shared_wallet(uuid,uuid,uuid,integer) TO froid_runtime;
  GRANT EXECUTE ON FUNCTION froid_apply_credit_event(uuid,uuid,uuid,integer,text,text,text,jsonb) TO froid_runtime;
END IF; END $$;
INSERT INTO schema_migrations(version) VALUES('005_wallet_activation_safety') ON CONFLICT DO NOTHING;
COMMIT;
