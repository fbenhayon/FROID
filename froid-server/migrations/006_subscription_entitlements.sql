BEGIN;

CREATE TABLE IF NOT EXISTS subscription_plans (
    code text PRIMARY KEY CHECK (code IN ('pro', 'plus', 'master')),
    display_name text NOT NULL,
    catalog_version integer NOT NULL DEFAULT 1 CHECK (catalog_version > 0),
    entitlements jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO subscription_plans(code, display_name, catalog_version, entitlements)
VALUES
  ('pro','FROID PRO',1,'{"session_layouts":["simplified","detailed"],"clinical_metrics":true,"froid_explica":true,"organization_members":1,"audit_export":false,"supervision":false}'::jsonb),
  ('plus','FROID PLUS',1,'{"session_layouts":["simplified","detailed"],"clinical_metrics":true,"froid_explica":true,"organization_members":10,"audit_export":true,"supervision":true}'::jsonb),
  ('master','FROID MASTER',1,'{"session_layouts":["simplified","detailed"],"clinical_metrics":true,"froid_explica":true,"organization_members":35,"audit_export":true,"supervision":true}'::jsonb)
ON CONFLICT (code) DO UPDATE SET
  display_name=EXCLUDED.display_name,
  catalog_version=EXCLUDED.catalog_version,
  entitlements=EXCLUDED.entitlements,
  active=true,
  updated_at=now();

CREATE TABLE IF NOT EXISTS organization_subscriptions (
    organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE RESTRICT,
    plan_code text NOT NULL REFERENCES subscription_plans(code) ON DELETE RESTRICT,
    package_code text NOT NULL,
    sessions_per_recharge integer NOT NULL CHECK (sessions_per_recharge > 0),
    recharge_amount_cents integer NOT NULL CHECK (recharge_amount_cents > 0),
    currency text NOT NULL DEFAULT 'brl' CHECK (currency IN ('brl','usd','eur','cny')),
    status text NOT NULL CHECK (status IN (
      'incomplete','incomplete_expired','trialing','active','past_due','canceled','unpaid','paused'
    )),
    stripe_customer_id text,
    stripe_payment_method_id text,
    auto_replenish boolean NOT NULL DEFAULT false,
    auto_replenish_consent_at timestamptz,
    auto_replenish_terms_version text,
    last_recharge_status text NOT NULL DEFAULT 'not_started' CHECK (
      last_recharge_status IN ('not_started','pending','succeeded','failed','action_required')
    ),
    current_period_start timestamptz,
    current_period_end timestamptz,
    cancel_at_period_end boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS automatic_recharges (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    package_code text NOT NULL,
    session_credits integer NOT NULL CHECK (session_credits > 0),
    amount_cents integer NOT NULL CHECK (amount_cents > 0),
    currency text NOT NULL DEFAULT 'brl' CHECK (currency IN ('brl','usd','eur','cny')),
    status text NOT NULL CHECK (status IN ('pending','processing','succeeded','failed','action_required')),
    stripe_payment_intent_id text UNIQUE,
    idempotency_key text NOT NULL UNIQUE,
    failure_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Keeps the migration safe for homologation databases that received an earlier
-- draft of migration 006 before the multi-currency catalogue was introduced.
ALTER TABLE organization_subscriptions
  ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'brl';
ALTER TABLE organization_subscriptions
  ADD COLUMN IF NOT EXISTS auto_replenish_consent_at timestamptz;
ALTER TABLE organization_subscriptions
  ADD COLUMN IF NOT EXISTS auto_replenish_terms_version text;
ALTER TABLE automatic_recharges
  ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'brl';

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'organization_subscriptions_currency_check'
      AND conrelid = 'public.organization_subscriptions'::regclass
  ) THEN
    ALTER TABLE organization_subscriptions
      ADD CONSTRAINT organization_subscriptions_currency_check
      CHECK (currency IN ('brl','usd','eur','cny'));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'automatic_recharges_currency_check'
      AND conrelid = 'public.automatic_recharges'::regclass
  ) THEN
    ALTER TABLE automatic_recharges
      ADD CONSTRAINT automatic_recharges_currency_check
      CHECK (currency IN ('brl','usd','eur','cny'));
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS automatic_recharges_one_open_per_org
  ON automatic_recharges(organization_id)
  WHERE status IN ('pending','processing','action_required');

CREATE INDEX IF NOT EXISTS organization_subscriptions_status_idx
  ON organization_subscriptions(status, current_period_end);

CREATE TABLE IF NOT EXISTS stripe_webhook_events (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    payload_sha256 text NOT NULL,
    processed_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION froid_membership_is_active()
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM organization_memberships membership
    JOIN organizations organization ON organization.id=membership.organization_id
    JOIN users user_account ON user_account.id=membership.user_id
    WHERE membership.id=froid_current_membership_id()
      AND membership.organization_id=froid_current_organization_id()
      AND membership.status='active'
      AND organization.status='active'
      AND user_account.status='active'
  )
$$;

REVOKE ALL ON FUNCTION froid_membership_is_active() FROM PUBLIC;

ALTER TABLE organization_subscriptions ENABLE ROW LEVEL SECURITY;
-- The restricted runtime role is governed by RLS. The migration/webhook owner
-- must retain its normal owner bypass because Stripe events have no user session.
ALTER TABLE organization_subscriptions NO FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS organization_subscriptions_read ON organization_subscriptions;
CREATE POLICY organization_subscriptions_read ON organization_subscriptions
FOR SELECT USING (
  organization_id = froid_current_organization_id()
  AND froid_membership_is_active()
);

REVOKE ALL ON subscription_plans, organization_subscriptions, automatic_recharges, stripe_webhook_events FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
  GRANT SELECT ON subscription_plans, organization_subscriptions TO froid_runtime;
  GRANT EXECUTE ON FUNCTION froid_membership_is_active() TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('006_subscription_entitlements') ON CONFLICT DO NOTHING;
COMMIT;
