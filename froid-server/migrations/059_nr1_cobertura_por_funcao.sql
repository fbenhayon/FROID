-- Cobertura de um grupo por função nos estabelecimentos: Leitura de Governança.
--
-- 26/11/2026, decisão do dono. A avaliação da liderança passa a poder ser feita
-- por FUNÇÃO (grupo de exposição similar): "Gerentes de loja" atravessando as
-- 40 lojas, em vez de um gerente diluído em cada equipe de 8 pessoas. A NR-1
-- admite organizar a avaliação assim: 1.5.3.1.1.1 ("por unidade operacional,
-- setor ou atividade"), o Manual MTE 2026 ("função, setor ou grupo de exposição
-- similar") e o FAQ da CGNOR ("unidades de avaliação: ... a função").
--
-- O QUE FALTAVA
-- -------------
-- O PGR continua sendo POR ESTABELECIMENTO (1.5.3.1.1.1), e o inventário
-- descobria o estabelecimento de cada linha pela unidade pai do recorte. Um
-- grupo por função não tem pai: a linha saía sem dizer ONDE está o risco, que é
-- a primeira coisa que a fiscalização procura e o destino da medida corretiva.
--
-- Esta tabela diz em quais estabelecimentos cada grupo por função existe, e com
-- quantas pessoas. Com ela, o resultado do grupo é lançado no inventário de
-- cada estabelecimento coberto, com o mesmo texto em todos, e o efetivo por
-- endereço serve à representatividade.
--
-- ANONIMATO
-- ---------
-- Nada aqui toca resposta. A cobertura é estrutura da empresa, como o efetivo
-- de um setor. As respostas continuam em um único recorte (o grupo por função),
-- e a partição que impede descobrir alguém por subtração não muda. O efetivo
-- por endereço é número da empresa, não de pessoa, e nunca é cruzado com
-- resposta: a projeção copia o nível do grupo, não o recalcula por loja.

BEGIN;

CREATE TABLE IF NOT EXISTS organization_unit_coverage (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    unit_id uuid NOT NULL,
    establishment_unit_id uuid NOT NULL,
    headcount integer NOT NULL CHECK (headcount > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (unit_id, establishment_unit_id),
    -- Chave composta com a organização: o grupo e o estabelecimento precisam
    -- ser da MESMA empresa, e o banco garante isso sem depender da aplicação.
    FOREIGN KEY (organization_id, unit_id)
        REFERENCES organization_units (organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, establishment_unit_id)
        REFERENCES organization_units (organization_id, id) ON DELETE CASCADE,
    CHECK (unit_id <> establishment_unit_id)
);

CREATE INDEX IF NOT EXISTS organization_unit_coverage_establishment_idx
    ON organization_unit_coverage (organization_id, establishment_unit_id);

-- O tipo de cada ponta é regra de negócio que CHECK não alcança (está em outra
-- linha de outra tabela). Sem esta trava, um setor poderia ser "coberto" por um
-- grupo e a mesma resposta acabaria lançada em dois lugares do inventário.
CREATE OR REPLACE FUNCTION froid_nr1_coverage_types_check()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    tipo_grupo text;
    tipo_endereco text;
BEGIN
    SELECT unit_type INTO tipo_grupo
      FROM organization_units WHERE id = NEW.unit_id;
    SELECT unit_type INTO tipo_endereco
      FROM organization_units WHERE id = NEW.establishment_unit_id;
    IF tipo_grupo IS DISTINCT FROM 'exposure_group' THEN
        RAISE EXCEPTION 'cobertura exige um grupo por funcao (exposure_group)';
    END IF;
    IF tipo_endereco IS DISTINCT FROM 'site' THEN
        RAISE EXCEPTION 'cobertura exige um estabelecimento (site)';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS organization_unit_coverage_types
    ON organization_unit_coverage;
CREATE TRIGGER organization_unit_coverage_types
    BEFORE INSERT OR UPDATE ON organization_unit_coverage
    FOR EACH ROW EXECUTE FUNCTION froid_nr1_coverage_types_check();

ALTER TABLE organization_unit_coverage ENABLE ROW LEVEL SECURITY;

-- Mesma regra de organization_units: quem lê a estrutura lê a cobertura, e só
-- quem gere a estrutura a altera.
DROP POLICY IF EXISTS organization_unit_coverage_read ON organization_unit_coverage;
CREATE POLICY organization_unit_coverage_read ON organization_unit_coverage
FOR SELECT USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
);
DROP POLICY IF EXISTS organization_unit_coverage_manage ON organization_unit_coverage;
CREATE POLICY organization_unit_coverage_manage ON organization_unit_coverage
FOR ALL
USING (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
)
WITH CHECK (
  organization_id=froid_current_organization_id()
  AND froid_membership_is_active()
  AND froid_has_role(ARRAY['owner','administrator','compliance_manager']::text[])
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON organization_unit_coverage
        TO froid_runtime;
    END IF;
END $$;

INSERT INTO schema_migrations (version)
VALUES ('059_nr1_cobertura_por_funcao')
ON CONFLICT (version) DO NOTHING;

COMMIT;
