-- O plano de acao deixa de ser rascunho e vira documento.
--
-- 1.5.7.1 lista DOIS documentos minimos do PGR: inventario de riscos e plano de
-- acao. O FROID gravava o primeiro (nr1_store_inventory) e nao o segundo:
-- action_plan_seed() devolvia um rascunho na resposta da API e ele evaporava.
-- A tabela psychosocial_action_plan existia desde a 010, com RLS, com grants ao
-- froid_runtime e ate com permissao propria em tenant_access.py
-- (nr1.action_plan.manage, concedida a compliance_manager e occupational_health)
-- — e nunca recebeu um INSERT. O desenho estava inteiro; faltava a camada que o
-- usa.
--
-- Esta migration nao cria a tabela. Ela acrescenta a coluna que 1.5.5.2.1 exige
-- e transforma em restricao de banco o que a norma exige do documento, para que
-- nenhuma destas falhas seja possivel por acidente:
--
--   1.5.5.2.1    medidas a serem INTRODUZIDAS, APRIMORADAS ou MANTIDAS
--   1.5.5.2.2    cronograma com responsaveis, formas de acompanhamento e
--                afericao de resultados
--   1.5.5.3.1    a implementacao e seus ajustes devem ser REGISTRADOS
--   1.5.4.4.6 a) apos implementar, reavaliar o risco residual
--
-- O ultimo e o que nenhuma planilha faz: o gatilho da alinea "a" nao e uma data,
-- e um EVENTO. A obrigacao de reavaliar nasce no instante em que a organizacao
-- implementa a medida. Aqui ela passa a nascer sozinha.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1.5.5.2.1: o plano indica medidas a serem introduzidas, aprimoradas ou
-- mantidas. Sao tres verbos distintos e a norma os nomeia; guardar so o texto da
-- medida perde a informacao de qual dos tres o inventario determinou.
--
-- 'maintain' existe por causa de um caso que o seed descartava: risco BAIXO com
-- medida ja implementada e eficaz nao exige medida nova, mas exige manter a
-- existente e acompanha-la. O Manual do GRO e explicito no Quadro 5 ("nenhum
-- controle adicional necessario; manter o monitoramento para assegurar que os
-- controles sejam mantidos"). Um plano que omite essas linhas sugere que nada
-- foi feito naquele risco.
-- ---------------------------------------------------------------------------
ALTER TABLE psychosocial_action_plan
  ADD COLUMN IF NOT EXISTS plan_action text NOT NULL DEFAULT 'introduce';

ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_plan_action_check;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_plan_action_check
  CHECK (plan_action IN ('introduce', 'improve', 'maintain'));

-- Vinculo com a origem: qual campanha e quais criterios produziram esta linha.
-- Sem isso o plano flutua — o inventario e versionado por ciclo, e a prova de
-- eficacia compara ciclos. O plano precisa dizer a qual ciclo pertence.
ALTER TABLE psychosocial_action_plan
  ADD COLUMN IF NOT EXISTS campaign_id uuid
      REFERENCES assessment_campaigns(id) ON DELETE RESTRICT,
  ADD COLUMN IF NOT EXISTS criteria_id uuid
      REFERENCES gro_risk_criteria(id) ON DELETE RESTRICT;

-- ---------------------------------------------------------------------------
-- As restricoes abaixo sao NOT VALID de proposito.
--
-- A tabela nunca recebeu escrita da aplicacao, entao em producao deve estar
-- vazia — mas pode haver linha de piloto inserida a mao. NOT VALID aplica a
-- regra a toda escrita futura sem reprovar o passado, e assim esta migration nao
-- consegue derrubar o primeiro login de um tenant. Migration que quebra login e
-- pior que restricao que chega um ciclo depois. O DO block no fim reporta o que
-- existir, para que a decisao sobre linha antiga seja tomada com o numero na mao
-- em vez de descoberta pelo suporte.
-- ---------------------------------------------------------------------------

-- 1.5.5.3.1. Medida concluida sem data de implementacao e afirmacao sem
-- registro — e o registro e exatamente o que a norma manda guardar.
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_done_needs_implementation;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_done_needs_implementation
  CHECK (status <> 'done' OR implemented_at IS NOT NULL) NOT VALID;

-- 1.5.5.2.2. Cronograma COM RESPONSAVEIS. Medida que ninguem assinou e prazo que
-- ninguem marcou e o que a fiscalizacao trata como medida nenhuma.
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_done_needs_schedule;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_done_needs_schedule
  CHECK (
      status <> 'done'
      OR (responsible_membership_id IS NOT NULL AND due_date IS NOT NULL)
  ) NOT VALID;

-- 1.5.5.2.2. Formas de acompanhamento E de afericao de resultados. Sao coisas
-- diferentes: como se verifica que a medida continua de pe, e como se mede se
-- ela produziu efeito. Sem a segunda nao ha o que comparar no ciclo seguinte, e
-- a prova de eficacia — que e o diferencial do produto e a exigencia de
-- 1.5.4.4.5.3 — deixa de existir.
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_done_needs_monitoring;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_done_needs_monitoring
  CHECK (
      status <> 'done'
      OR (btrim(monitoring_method) <> '' AND btrim(result_measurement) <> '')
  ) NOT VALID;

-- Medida sem texto so se admite em rascunho. Assim que sai de 'planned', alguem
-- precisa ter escrito o que sera feito.
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_measure_not_blank;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_measure_not_blank
  CHECK (status = 'planned' OR btrim(measure) <> '') NOT VALID;

-- Cancelar medida planejada para risco identificado e decisao que precisa de
-- motivo escrito. O campo evidence recebe a justificativa; cancelamento mudo e
-- indistinguivel de esquecimento, e e assim que um auditor o le.
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_cancel_needs_reason;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_cancel_needs_reason
  CHECK (status <> 'cancelled' OR btrim(evidence) <> '') NOT VALID;

-- Eficacia e veredito sobre medida implementada. Julgar antes de implementar nao
-- e otimismo, e dado falso com consequencia: 1.5.4.4.5.3 usa a eficacia para
-- calcular a probabilidade, entao um veredito inventado rebaixa o risco no
-- inventario inteiro.
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_efficacy_after_implementation;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_efficacy_after_implementation
  CHECK (
      effectiveness IS NULL
      OR (implemented_at IS NOT NULL AND effectiveness_reviewed_at IS NOT NULL)
  ) NOT VALID;

-- Data de revisao sem veredito, ou veredito sem data, e meia informacao.
ALTER TABLE psychosocial_action_plan
  DROP CONSTRAINT IF EXISTS psychosocial_action_plan_review_pairs_with_verdict;
ALTER TABLE psychosocial_action_plan
  ADD CONSTRAINT psychosocial_action_plan_review_pairs_with_verdict
  CHECK ((effectiveness_reviewed_at IS NULL) = (effectiveness IS NULL)) NOT VALID;

-- ---------------------------------------------------------------------------
-- Guarda de escrita: o que foi registrado nao se desfaz.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION froid_nr1_action_plan_guard() RETURNS trigger AS $guard$
BEGIN
    -- 1.5.5.3.1 manda registrar a implementacao. Registro que pode ser apagado
    -- nao e registro — e apagar a data e a unica forma de fazer a obrigacao de
    -- reavaliar risco residual desaparecer sem deixar rastro.
    IF TG_OP = 'UPDATE'
       AND OLD.implemented_at IS NOT NULL
       AND NEW.implemented_at IS NULL THEN
        RAISE EXCEPTION
            'a data de implementacao registrada nao pode ser apagada (NR-1 1.5.5.3.1)';
    END IF;
    -- Mover a medida para outra linha de inventario reescreveria a que risco ela
    -- responde, e com isso a historia do que foi feito.
    IF TG_OP = 'UPDATE' AND NEW.inventory_id <> OLD.inventory_id THEN
        RAISE EXCEPTION
            'uma medida nao muda de risco; cancele esta e abra outra no risco correto';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$guard$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS psychosocial_action_plan_guard ON psychosocial_action_plan;
CREATE TRIGGER psychosocial_action_plan_guard
BEFORE INSERT OR UPDATE ON psychosocial_action_plan
FOR EACH ROW EXECUTE FUNCTION froid_nr1_action_plan_guard();

-- ---------------------------------------------------------------------------
-- O gatilho da alinea "a" de 1.5.4.4.6, feito mecanismo.
--
-- "apos implementacao das medidas de prevencao, para avaliacao de riscos
-- residuais". Nao ha prazo na norma porque nao ha data: a obrigacao nasce do
-- evento. Implementou, deve reavaliar.
--
-- review_due_at recebe o MENOR entre o que ja estava marcado (tipicamente a
-- revisao programada de 24 ou 36 meses) e a data desta implementacao — porque a
-- revisao residual antecipa a programada, nunca a adia. E review_trigger passa a
-- 'residual_risk' para que o painel diga POR QUE a revisao esta devida, e nao
-- apenas que esta.
--
-- SECURITY DEFINER porque a linha de inventario pertence a mesma organizacao mas
-- a politica de RLS do inventario exige papel de escrita; o gatilho tem de valer
-- mesmo quando quem registra a implementacao so tem papel sobre o plano.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION froid_nr1_flag_residual_risk_review() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $residual$
BEGIN
    IF NEW.implemented_at IS NOT NULL
       AND (TG_OP = 'INSERT' OR OLD.implemented_at IS NULL) THEN
        UPDATE psychosocial_risk_inventory
           SET review_trigger = 'residual_risk',
               review_due_at = LEAST(
                   coalesce(review_due_at, NEW.implemented_at),
                   NEW.implemented_at
               )
         WHERE id = NEW.inventory_id
           AND organization_id = NEW.organization_id;
    END IF;
    RETURN NULL;
END;
$residual$;

DROP TRIGGER IF EXISTS psychosocial_action_plan_residual_review ON psychosocial_action_plan;
CREATE TRIGGER psychosocial_action_plan_residual_review
AFTER INSERT OR UPDATE OF implemented_at ON psychosocial_action_plan
FOR EACH ROW EXECUTE FUNCTION froid_nr1_flag_residual_risk_review();

-- A listagem do plano e sempre por organizacao e por risco, e a ordem que
-- importa e a de prioridade (1.5.5.2.1.1).
CREATE INDEX IF NOT EXISTS psychosocial_action_plan_inventory_idx
    ON psychosocial_action_plan (organization_id, inventory_id, priority_rank);
CREATE INDEX IF NOT EXISTS psychosocial_action_plan_campaign_idx
    ON psychosocial_action_plan (organization_id, campaign_id, priority_rank);

-- A 010 ja concedeu SELECT/INSERT/UPDATE/DELETE ao froid_runtime nesta tabela.
-- Redeclarar e barato e protege o caso em que a 010 rodou antes de o papel
-- existir — que ja aconteceu neste projeto, e o sintoma aparece longe da causa.
DO $grants$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON psychosocial_action_plan TO froid_runtime;
        GRANT SELECT, INSERT, UPDATE ON psychosocial_risk_inventory TO froid_runtime;
    END IF;
END
$grants$;

-- Diagnostico do que ja existe, para que ninguem descubra pelo suporte.
DO $diagnostico$
DECLARE
    linhas integer;
    inventarios_sem_plano integer;
BEGIN
    SELECT count(*) INTO linhas FROM psychosocial_action_plan;
    IF linhas > 0 THEN
        RAISE NOTICE
            '% linha(s) ja existiam em psychosocial_action_plan e nao foram '
            'validadas contra as novas restricoes (NOT VALID). Conferir antes de '
            'trata-las como documento.', linhas;
    END IF;

    SELECT count(*) INTO inventarios_sem_plano
    FROM psychosocial_risk_inventory inventario
    WHERE inventario.risk_level <> 'low'
      AND NOT EXISTS (
          SELECT 1 FROM psychosocial_action_plan plano
          WHERE plano.inventory_id = inventario.id
      );
    IF inventarios_sem_plano > 0 THEN
        RAISE NOTICE
            '% risco(s) acima de baixo no inventario sem nenhuma linha de plano '
            'de acao. Sao inventarios gerados antes desta migration: o PGR deles '
            'esta com um dos dois documentos obrigatorios faltando. Regerar o '
            'plano a partir do inventario resolve.', inventarios_sem_plano;
    END IF;
END
$diagnostico$;

INSERT INTO schema_migrations (version)
VALUES ('026_action_plan_documento')
ON CONFLICT (version) DO NOTHING;

COMMIT;
