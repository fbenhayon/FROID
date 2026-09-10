-- Dossiê versionado do processo NR-1.
--
-- O SHA-256 detecta alteração do conteúdo consolidado. Ele não é assinatura
-- eletrônica e não identifica, sozinho, quem assinou. Por isso a tabela guarda
-- também organização, associação responsável, data, versão e encadeamento com
-- o hash anterior. Uma assinatura ICP-Brasil pode ser aplicada ao PDF/JSON
-- exportado sem mudar o registro de origem que o FROID consegue provar.

BEGIN;

CREATE TABLE IF NOT EXISTS psychosocial_compliance_dossiers (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    previous_sha256 text CHECK (
        previous_sha256 IS NULL OR previous_sha256 ~ '^[0-9a-f]{64}$'
    ),
    canonicalization text NOT NULL DEFAULT 'json-sort-keys-utf8-v1',
    payload jsonb NOT NULL,
    sealed_by_membership_id uuid
        REFERENCES organization_memberships(id) ON DELETE SET NULL,
    sealed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, version),
    UNIQUE (organization_id, content_sha256)
);

CREATE INDEX IF NOT EXISTS psychosocial_compliance_dossiers_org_idx
    ON psychosocial_compliance_dossiers (organization_id, version DESC);

CREATE OR REPLACE FUNCTION froid_prevent_nr1_dossier_mutation()
RETURNS trigger AS $dossier_guard$
BEGIN
    -- O gerador do piloto promete remoção completa. A exceção só aceita DELETE
    -- para organização explicitamente identificada como DADOS SIMULADOS e não
    -- é concedida ao papel de runtime.
    IF TG_OP = 'DELETE'
       AND current_setting('app.nr1_pilot_destroy', true) = 'allowed'
       AND EXISTS (
           SELECT 1 FROM organizations organization
           WHERE organization.id = OLD.organization_id
             AND upper(organization.legal_name) LIKE '%DADOS SIMULADOS%'
       ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'psychosocial_compliance_dossiers is append-only';
END;
$dossier_guard$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS psychosocial_compliance_dossiers_no_mutation
    ON psychosocial_compliance_dossiers;
CREATE TRIGGER psychosocial_compliance_dossiers_no_mutation
BEFORE UPDATE OR DELETE ON psychosocial_compliance_dossiers
FOR EACH ROW EXECUTE FUNCTION froid_prevent_nr1_dossier_mutation();

ALTER TABLE psychosocial_compliance_dossiers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS psychosocial_compliance_dossiers_read ON psychosocial_compliance_dossiers;
DROP POLICY IF EXISTS psychosocial_compliance_dossiers_insert ON psychosocial_compliance_dossiers;

CREATE POLICY psychosocial_compliance_dossiers_read
ON psychosocial_compliance_dossiers FOR SELECT USING (
    organization_id = froid_current_organization_id()
    AND froid_membership_is_active()
    AND froid_has_role(ARRAY[
        'owner', 'administrator', 'auditor',
        'compliance_manager', 'occupational_health'
    ]::text[])
);

CREATE POLICY psychosocial_compliance_dossiers_insert
ON psychosocial_compliance_dossiers FOR INSERT WITH CHECK (
    organization_id = froid_current_organization_id()
    AND sealed_by_membership_id = froid_current_membership_id()
    AND froid_membership_is_active()
    AND froid_has_role(ARRAY[
        'owner', 'administrator', 'compliance_manager', 'occupational_health'
    ]::text[])
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT SELECT, INSERT ON psychosocial_compliance_dossiers TO froid_runtime;
        REVOKE UPDATE, DELETE ON psychosocial_compliance_dossiers FROM froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('031_nr1_compliance_dossier')
ON CONFLICT (version) DO NOTHING;

COMMIT;
