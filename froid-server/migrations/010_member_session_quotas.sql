BEGIN;

-- Cota individual por profissional dentro da clinica.
--
-- Regra de produto: por padrao o pool e livre - todo profissional da clinica
-- consome do saldo compartilhado sem limite proprio. O administrador PODE
-- estabelecer uma cota individual; a partir dai aquele profissional consome no
-- maximo `quota_sessions` sessoes do pool.
--
-- A cota e um TETO DE CONSUMO, nao uma sub-carteira. O saldo continua vivendo
-- exclusivamente em organization_wallets, preservando a invariante ja provada
-- (um unico numero, nunca negativo). Fatiar o pool em N sub-saldos criaria N
-- fontes de verdade que divergem; um teto nao.
CREATE TABLE IF NOT EXISTS organization_member_quotas (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    membership_id uuid NOT NULL REFERENCES organization_memberships(id) ON DELETE CASCADE,
    quota_sessions integer NOT NULL CHECK (quota_sessions >= 0),
    consumed_sessions integer NOT NULL DEFAULT 0 CHECK (consumed_sessions >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, membership_id)
);

ALTER TABLE organization_member_quotas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON organization_member_quotas;
CREATE POLICY tenant_isolation ON organization_member_quotas
    USING (organization_id = froid_current_organization_id())
    WITH CHECK (organization_id = froid_current_organization_id());

-- Define, ajusta ou remove a cota de um profissional. Apenas owner/administrator.
-- quota IS NULL remove a cota (o profissional volta a consumir livremente).
CREATE OR REPLACE FUNCTION froid_set_member_quota(
  org uuid, member uuid, actor uuid, target_member uuid, quota integer
) RETURNS TABLE (quota_sessions integer, consumed_sessions integer, removed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE row_quota organization_member_quotas%ROWTYPE;
BEGIN
  IF froid_current_organization_id() IS DISTINCT FROM org OR
     froid_current_membership_id() IS DISTINCT FROM member THEN
    RAISE EXCEPTION 'quota context mismatch' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM organization_memberships m
    WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
      AND m.status='active') OR
     NOT froid_has_role(ARRAY['owner','administrator']::text[]) THEN
    RAISE EXCEPTION 'role cannot manage member quotas' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM organization_memberships m
    WHERE m.id=target_member AND m.organization_id=org AND m.status='active') THEN
    RAISE EXCEPTION 'target membership not in organization' USING ERRCODE='42501';
  END IF;
  IF quota IS NULL THEN
    DELETE FROM organization_member_quotas
      WHERE organization_id=org AND membership_id=target_member;
    RETURN QUERY SELECT 0,0,true; RETURN;
  END IF;
  IF quota < 0 THEN
    RAISE EXCEPTION 'quota cannot be negative' USING ERRCODE='22023';
  END IF;
  INSERT INTO organization_member_quotas
      (organization_id, membership_id, quota_sessions)
  VALUES (org, target_member, quota)
  ON CONFLICT (organization_id, membership_id) DO UPDATE
    SET quota_sessions=EXCLUDED.quota_sessions, updated_at=now()
  RETURNING * INTO row_quota;
  RETURN QUERY SELECT row_quota.quota_sessions, row_quota.consumed_sessions, false;
END $$;

-- Reemite froid_apply_credit_event acrescentando a checagem de cota. A cota
-- precisa ser verificada e incrementada DENTRO da mesma transacao do debito do
-- pool; validar por fora deixaria uma janela para dois consumos simultaneos
-- ultrapassarem o teto. A ordem de travamento e sempre carteira -> cota, igual
-- em todos os caminhos, para nao criar deadlock.
CREATE OR REPLACE FUNCTION froid_apply_credit_event(
  org uuid, member uuid, actor uuid, delta integer, kind text,
  idem text, session_id text DEFAULT NULL, meta jsonb DEFAULT '{}'::jsonb
) RETURNS TABLE (ledger_id uuid,resulting_balance integer,applied boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE
  wallet organization_wallets%ROWTYPE;
  entry credit_ledger%ROWTYPE;
  quota_row organization_member_quotas%ROWTYPE;
  new_id uuid;
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
  IF kind='consumption' THEN
    SELECT * INTO quota_row FROM organization_member_quotas
      WHERE organization_id=org AND membership_id=member FOR UPDATE;
    IF FOUND THEN
      IF quota_row.consumed_sessions + 1 > quota_row.quota_sessions THEN
        RAISE EXCEPTION 'member quota exhausted' USING ERRCODE='P0001';
      END IF;
      UPDATE organization_member_quotas
        SET consumed_sessions=consumed_sessions+1, updated_at=now()
        WHERE organization_id=org AND membership_id=member;
    END IF;
  END IF;
  UPDATE organization_wallets SET balance=balance+delta,version=version+1,
    updated_at=now() WHERE organization_id=org RETURNING balance INTO wallet.balance;
  new_id:=gen_random_uuid();
  INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,
    legacy_session_id,idempotency_key,actor_user_id,metadata)
  VALUES(new_id,org,delta,wallet.balance,kind,session_id,idem,actor,coalesce(meta,'{}'));
  RETURN QUERY SELECT new_id,wallet.balance,true;
END $$;

REVOKE ALL ON FUNCTION froid_set_member_quota(uuid,uuid,uuid,uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION froid_apply_credit_event(uuid,uuid,uuid,integer,text,text,text,jsonb) FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
  GRANT EXECUTE ON FUNCTION froid_set_member_quota(uuid,uuid,uuid,uuid,integer) TO froid_runtime;
  GRANT EXECUTE ON FUNCTION froid_apply_credit_event(uuid,uuid,uuid,integer,text,text,text,jsonb) TO froid_runtime;
  GRANT SELECT, INSERT, UPDATE, DELETE ON organization_member_quotas TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('010_member_session_quotas')
ON CONFLICT DO NOTHING;

COMMIT;
