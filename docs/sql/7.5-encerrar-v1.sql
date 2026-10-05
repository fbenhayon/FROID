-- Fase 7.5: encerrar o comercio V1 nas 3 contas que compraram por ele.
-- 1) "ja comprou" na carteira V2 (o portao V2 nao pede compra a quem ja comprou);
-- 2) assinatura V1 cancelada e recarga automatica desligada (cartao do Philippe);
-- 3) trilha em audit_events. Tudo numa transacao; erro aborta tudo.
\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE alvo AS SELECT organization_id FROM organization_subscriptions;
UPDATE organization_wallets w SET ever_purchased = true
  FROM alvo a WHERE w.organization_id = a.organization_id AND w.credit_model = 'psique_v2';
UPDATE organization_subscriptions SET auto_replenish = false, status = 'canceled',
  cancel_at_period_end = true, updated_at = now();
INSERT INTO audit_events(id, organization_id, actor_user_id, action, resource_type, resource_id)
SELECT gen_random_uuid(), a.organization_id,
  (SELECT m.user_id FROM organization_memberships m JOIN membership_roles r ON r.membership_id = m.id
    WHERE m.organization_id = a.organization_id AND r.role = 'owner' LIMIT 1),
  'psique.v1_commerce.retired', 'organization_subscription', a.organization_id::text
FROM alvo a;
SELECT left(w.organization_id::text, 8) AS org, w.credit_model, w.balance, w.ever_purchased,
       s.status, s.auto_replenish
  FROM organization_wallets w JOIN organization_subscriptions s ON s.organization_id = w.organization_id;
COMMIT;
