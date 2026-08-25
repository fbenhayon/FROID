-- Recorte sem coorte suficiente deixa de sumir e passa a ser declarado.
--
-- O QUE ESTAVA ERRADO
--
-- froid_nr1_dimension_scores aplica os dois portoes no HAVING: o recorte que
-- nao passa simplesmente nao volta. O endpoint do painel devolvia entao
-- "risks": [] e o de inventario devolvia HTTP 409 — a empresa pagava o ciclo e
-- nao recebia documento nenhum.
--
-- Suprimir e ocultar. Declarar insuficiente e documentar. Sao coisas
-- diferentes, e ate aqui o produto so fazia a primeira. Painel vazio nao e
-- neutro: e lido como "nao ha risco aqui", que e exatamente a conclusao que a
-- ausencia de dado NAO autoriza.
--
-- O contrato revisado em 25/08/2026 fechou essa porta em duas clausulas:
--
--   "o resultado daquela unidade podera ser suprimido, agregado a unidade
--    tecnicamente compativel, ou DECLARADO INSUFICIENTE PARA CLASSIFICACAO.
--    Nao sera criada artificialmente conclusao sobre ausencia ou baixo nivel
--    de risco em razao de insuficiencia de dados."
--
--   "A inexistencia de evidencia suficiente para classificar determinado risco
--    nao sera automaticamente interpretada como inexistencia de risco."
--
-- E a norma diz o mesmo por outro caminho: 1.5.4.2.1.3 manda registrar no
-- inventario o risco cuja medida nao pode ser adotada de imediato, e 1.5.7.3.1
-- manda consolidar no inventario os dados da identificacao de perigos — nao
-- apenas os riscos que couberam numa classificacao.
--
-- O QUE ESTA MIGRATION FAZ
--
-- 1. Abre o inventario para a linha declarada, com uma trava: ou a linha esta
--    inteiramente classificada, ou esta inteiramente declarada insuficiente.
--    Nunca meio a meio — linha pela metade e a que um auditor le como
--    classificacao de risco baixo.
--
-- 2. Cria froid_nr1_unclassifiable_cohorts, que devolve QUAL portao reprovou
--    cada recorte, e nada mais.
--
-- O QUE A FUNCAO NAO DEVOLVE, E POR QUE
--
-- Nao devolve contagem de respostas do recorte reprovado. Devolvesse, e o
-- numero estaria abaixo do piso por definicao — seria publicar exatamente a
-- coorte pequena que o piso existe para proteger, pela porta dos fundos.
--
-- Devolve o portao que reprovou, e isso e deliberado: o remedio depende dele.
-- Recorte abaixo do piso de anonimato nao publica por mais adesao que haja, e o
-- caminho e a AEP; recorte reprovado na representatividade ainda publica se a
-- adesao subir. Dizer so "insuficiente" faria a empresa perseguir adesao que
-- nao resolve. A informacao que isso revela e sobre ADESAO, nao sobre resposta:
-- ninguem fica sabendo o que alguem respondeu, e a adesao da campanha ja e
-- legivel durante a coleta.
--
-- Devolve tambem a amostra exigida, que e calculada sobre o efetivo declarado
-- pela propria contratante — numero que ela ja tem.
--
-- Abaixo do piso da campanha a funcao nao devolve linha alguma. Ali nada e
-- publicavel, e uma quebra por recorte revelaria quais unidades tiveram ao
-- menos uma resposta numa campanha minuscula. A insuficiencia, nesse caso, e da
-- campanha inteira e e o chamador que a declara.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. A linha declarada cabe no inventario, e so inteira.
-- ---------------------------------------------------------------------------

ALTER TABLE psychosocial_risk_inventory
    ALTER COLUMN cohort_size DROP NOT NULL,
    ALTER COLUMN mean_score DROP NOT NULL,
    ALTER COLUMN severity DROP NOT NULL,
    ALTER COLUMN probability DROP NOT NULL;

ALTER TABLE psychosocial_risk_inventory
    DROP CONSTRAINT IF EXISTS psychosocial_risk_inventory_risk_level_check;

ALTER TABLE psychosocial_risk_inventory
    ADD CONSTRAINT psychosocial_risk_inventory_risk_level_check
    CHECK (risk_level IN ('low', 'moderate', 'high', 'critical', 'insuficiente'));

-- Por que a coorte tambem some na linha declarada: gravar o tamanho real de um
-- recorte reprovado seria guardar no DOCUMENTO QUE O EMPREGADOR LE a contagem
-- que o piso recusou publicar no painel.
ALTER TABLE psychosocial_risk_inventory
    ADD COLUMN IF NOT EXISTS suppression_gate text
        CHECK (suppression_gate IS NULL OR suppression_gate IN (
            'anonimato',              -- coorte menor que o piso de recorte
            'representatividade',     -- coorte nao fala pelo efetivo declarado
            'efetivo_nao_declarado',  -- sem denominador nao ha o que representar
            'campanha_abaixo_do_piso' -- a campanha inteira nao publica
        )),
    ADD COLUMN IF NOT EXISTS escalation_note text NOT NULL DEFAULT '';

-- A trava do tudo-ou-nada. NOT VALID para nao quebrar linha antiga de tenant
-- que ja esteja gravada; o que interessa e o que entra daqui em diante.
ALTER TABLE psychosocial_risk_inventory
    DROP CONSTRAINT IF EXISTS psychosocial_risk_inventory_classificada_ou_declarada;

ALTER TABLE psychosocial_risk_inventory
    ADD CONSTRAINT psychosocial_risk_inventory_classificada_ou_declarada
    CHECK (
        (
            risk_level <> 'insuficiente'
            AND cohort_size IS NOT NULL
            AND mean_score IS NOT NULL
            AND severity IS NOT NULL
            AND probability IS NOT NULL
            AND suppression_gate IS NULL
        )
        OR
        (
            risk_level = 'insuficiente'
            AND cohort_size IS NULL
            AND mean_score IS NULL
            AND severity IS NULL
            AND probability IS NULL
            AND suppression_gate IS NOT NULL
            AND escalation_note <> ''
        )
    ) NOT VALID;

-- ---------------------------------------------------------------------------
-- 2. Qual portao reprovou cada recorte — sem a contagem.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION froid_nr1_unclassifiable_cohorts(
    target_campaign_id uuid,
    requested_min_cohort integer DEFAULT NULL
)
RETURNS TABLE (
    unit_id uuid,
    dimension_id uuid,
    nr1_factor text,
    gate text,
    required_responses integer,
    declared_headcount integer
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    effective_cut_floor integer;
    campaign_total bigint;
    campaign_org uuid;
    campaign_status text;
    campaign_headcount integer;
    campaign_criteria uuid;
    sampling_margin numeric;
    sampling_z numeric;
    sampling_census numeric;
    required_total integer;
BEGIN
    effective_cut_floor := GREATEST(
        coalesce(requested_min_cohort, froid_nr1_min_cohort_cut()),
        froid_nr1_min_cohort_cut()
    );

    SELECT campaign.organization_id, campaign.status,
           campaign.target_headcount, campaign.criteria_id
      INTO campaign_org, campaign_status, campaign_headcount, campaign_criteria
    FROM assessment_campaigns campaign
    WHERE campaign.id = target_campaign_id;

    -- Os mesmos guardas do agregado, e pela mesma razao. Esta funcao e
    -- SECURITY DEFINER: sem eles ela leria campanha de outro inquilino.
    IF campaign_org IS NULL OR campaign_org <> froid_current_organization_id() THEN
        RETURN;
    END IF;

    IF NOT froid_membership_is_active() THEN
        RETURN;
    END IF;

    IF campaign_status <> 'closed' THEN
        RETURN;
    END IF;

    SELECT criteria.sampling_margin_of_error,
           criteria.sampling_confidence_z,
           criteria.census_threshold_ratio
      INTO sampling_margin, sampling_z, sampling_census
    FROM gro_risk_criteria criteria
    WHERE criteria.id = campaign_criteria;

    SELECT count(*) INTO campaign_total
    FROM assessment_responses response
    WHERE response.campaign_id = target_campaign_id
      AND response.completed
      AND froid_nr1_response_is_substantive(response.id);

    -- Abaixo de qualquer dos portoes da CAMPANHA nao ha quebra por recorte: a
    -- insuficiencia e do conjunto, e quem declara isso e o chamador.
    IF campaign_total < froid_nr1_min_cohort_total() THEN
        RETURN;
    END IF;

    required_total := froid_nr1_required_sample(
        campaign_headcount, sampling_margin, sampling_z, sampling_census
    );
    IF required_total IS NULL OR campaign_total < required_total THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH response_dimension AS (
        SELECT response.id AS response_id,
               response.unit_id AS response_unit_id,
               dimension.id AS response_dimension_id
        FROM assessment_responses response
        JOIN assessment_response_items response_item
          ON response_item.response_id = response.id
        JOIN assessment_items item
          ON item.id = response_item.item_id
        JOIN assessment_dimensions dimension
          ON dimension.id = item.dimension_id
        WHERE response.campaign_id = target_campaign_id
          AND response.completed
        GROUP BY response.id, response.unit_id, dimension.id
    )
    SELECT scored.response_unit_id,
           dimension.id,
           dimension.nr1_factor,
           CASE
               WHEN count(*) < effective_cut_floor THEN 'anonimato'
               WHEN froid_nr1_required_sample(
                        GREATEST(
                            coalesce(max(unit.headcount), 0),
                            CASE WHEN scored.response_unit_id IS NULL
                                 THEN coalesce(campaign_headcount, 0) ELSE 0 END
                        ),
                        sampling_margin, sampling_z, sampling_census
                    ) IS NULL THEN 'efetivo_nao_declarado'
               ELSE 'representatividade'
           END AS gate,
           froid_nr1_required_sample(
               GREATEST(
                   coalesce(max(unit.headcount), 0),
                   CASE WHEN scored.response_unit_id IS NULL
                        THEN coalesce(campaign_headcount, 0) ELSE 0 END
               ),
               sampling_margin, sampling_z, sampling_census
           ) AS required_responses,
           GREATEST(
               coalesce(max(unit.headcount), 0),
               CASE WHEN scored.response_unit_id IS NULL
                    THEN coalesce(campaign_headcount, 0) ELSE 0 END
           )::integer AS declared_headcount
    FROM response_dimension scored
    JOIN assessment_dimensions dimension
      ON dimension.id = scored.response_dimension_id
    LEFT JOIN organization_units unit
      ON unit.id = scored.response_unit_id
    GROUP BY scored.response_unit_id, dimension.id, dimension.nr1_factor
    -- A negacao exata do HAVING de froid_nr1_dimension_scores: aqui entram
    -- justamente os recortes que la nao entraram.
    HAVING count(*) < effective_cut_floor
        OR froid_nr1_required_sample(
               GREATEST(
                   coalesce(max(unit.headcount), 0),
                   CASE WHEN scored.response_unit_id IS NULL
                        THEN coalesce(campaign_headcount, 0) ELSE 0 END
               ),
               sampling_margin, sampling_z, sampling_census
           ) IS NULL
        OR count(*) < froid_nr1_required_sample(
               GREATEST(
                   coalesce(max(unit.headcount), 0),
                   CASE WHEN scored.response_unit_id IS NULL
                        THEN coalesce(campaign_headcount, 0) ELSE 0 END
               ),
               sampling_margin, sampling_z, sampling_census
           );
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_unclassifiable_cohorts(uuid, integer) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_nr1_unclassifiable_cohorts(uuid, integer)
            TO froid_runtime;
    END IF;
END
$$;

INSERT INTO schema_migrations (version)
VALUES ('028_recorte_insuficiente_declarado')
ON CONFLICT (version) DO NOTHING;

COMMIT;
