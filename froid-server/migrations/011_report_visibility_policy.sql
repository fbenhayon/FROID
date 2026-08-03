BEGIN;

-- Politica de visibilidade de relatorios dentro da clinica.
--
-- 'restricted' (padrao): supervisor/gestor enxergam a clinica inteira; o
--   profissional so enxerga o paciente atribuido a ele. E o comportamento que
--   ja vigorava, e continua sendo o padrao - abrir prontuario de saude mental
--   entre colegas nunca pode ser efeito colateral de uma migracao.
-- 'clinic_wide': todos os profissionais da clinica enxergam os relatorios da
--   clinica, para analise conjunta de conduta.
--
-- A escolha e prerrogativa do gestor (owner/administrator) e fica registrada na
-- trilha de auditoria, porque amplia o acesso a dado sensivel de saude.
ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS report_visibility text NOT NULL DEFAULT 'restricted';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'organizations_report_visibility_check'
    ) THEN
        ALTER TABLE organizations
            ADD CONSTRAINT organizations_report_visibility_check
            CHECK (report_visibility IN ('restricted', 'clinic_wide'));
    END IF;
END $$;

CREATE OR REPLACE FUNCTION froid_set_report_visibility(
  org uuid, member uuid, actor uuid, visibility text
) RETURNS TABLE (report_visibility text, changed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE previous text;
BEGIN
  IF froid_current_organization_id() IS DISTINCT FROM org OR
     froid_current_membership_id() IS DISTINCT FROM member THEN
    RAISE EXCEPTION 'visibility context mismatch' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM organization_memberships m
    WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
      AND m.status='active') OR
     NOT froid_has_role(ARRAY['owner','administrator']::text[]) THEN
    RAISE EXCEPTION 'role cannot manage report visibility' USING ERRCODE='42501';
  END IF;
  IF visibility NOT IN ('restricted','clinic_wide') THEN
    RAISE EXCEPTION 'invalid report visibility' USING ERRCODE='22023';
  END IF;
  SELECT o.report_visibility INTO previous FROM organizations o
    WHERE o.id=org FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'organization not found' USING ERRCODE='P0002';
  END IF;
  IF previous = visibility THEN
    RETURN QUERY SELECT previous, false; RETURN;
  END IF;
  UPDATE organizations SET report_visibility=visibility, updated_at=now()
    WHERE id=org;
  RETURN QUERY SELECT visibility, true;
END $$;

REVOKE ALL ON FUNCTION froid_set_report_visibility(uuid,uuid,uuid,text) FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
  GRANT EXECUTE ON FUNCTION froid_set_report_visibility(uuid,uuid,uuid,text) TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('011_report_visibility_policy')
ON CONFLICT DO NOTHING;

COMMIT;
