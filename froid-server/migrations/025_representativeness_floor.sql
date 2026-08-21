-- Portao A: a coorte precisa falar pelo efetivo, e nao apenas existir.
--
-- Ate aqui o unico piso era contagem absoluta: 50 respostas substantivas na
-- campanha, 10 por recorte. Esses numeros protegem ANONIMATO — impedem que a
-- coorte seja pequena o bastante para reidentificar quem respondeu. Nenhum
-- deles olha para o tamanho da empresa. Uma organizacao de 3.000 pessoas com 50
-- respostas cruzava o piso e gerava inventario sobre 1,7% do quadro.
--
-- Este arquivo acrescenta um segundo portao, de proposito diferente:
-- REPRESENTATIVIDADE. Os dois passam a valer ao mesmo tempo e nenhum substitui
-- o outro, porque falham em situacoes distintas. Um setor de 15 pessoas com 11
-- respostas passa no piso de anonimato (11 >= 10) e reprova no de representa-
-- tividade, que nesse tamanho exige censo. Uma empresa de 3.000 com 200
-- respostas faz o inverso: passa folgado no anonimato e reprova na amostra,
-- que pede 341.
--
-- O numero exigido nao e escolha nossa, e esse e o ponto. E o tamanho de
-- amostra para proporcao com correcao de populacao finita, a 95% de confianca e
-- margem de 5 pontos, em p=0,5 (a proporcao de maior variancia, portanto a
-- exigencia conservadora). Sendo formula publicada, entra no documento de
-- criterios de 1.5.4.4.2.2 como fundamentacao verificavel e afasta a alegacao
-- de amostragem por conveniencia.
--
-- A norma nao prescreve taxa nenhuma: a escolha do metodo e da organizacao. O
-- que a fiscalizacao cobra e suficiencia tecnica e coerencia. Por isso os tres
-- parametros ficam em gro_risk_criteria, versionados e imutaveis depois de
-- publicados junto com o resto dos criterios — um cliente cuja consultoria de
-- SST trabalhe com outra tolerancia muda o dado, nao o codigo.
--
-- Efetivo nao declarado bloqueia. froid_nr1_required_sample devolve NULL quando
-- a populacao e zero, e NULL reprova tanto no IF quanto no HAVING. Sem isso,
-- declarar zero seria o caminho mais curto para desligar o portao — e o campo
-- ainda aceitava zero por omissao.

BEGIN;

-- ---------------------------------------------------------------------------
-- Parametros de amostragem: o padrao da plataforma.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION froid_nr1_sampling_confidence_z() RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$ SELECT 1.96::numeric $$;

CREATE OR REPLACE FUNCTION froid_nr1_sampling_margin() RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$ SELECT 0.05::numeric $$;

-- Acima desta fracao da populacao a amostra deixa de economizar respostas e
-- vira censo. Alinha com o Guia MTE: em grupo pequeno o questionario perde
-- sentido e o caminho e dialogo e observacao da atividade.
CREATE OR REPLACE FUNCTION froid_nr1_census_threshold() RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$ SELECT 0.80::numeric $$;

ALTER TABLE gro_risk_criteria
  ADD COLUMN IF NOT EXISTS sampling_confidence_z numeric
      NOT NULL DEFAULT 1.96 CHECK (sampling_confidence_z > 0 AND sampling_confidence_z <= 4),
  ADD COLUMN IF NOT EXISTS sampling_margin_of_error numeric
      NOT NULL DEFAULT 0.05 CHECK (sampling_margin_of_error > 0 AND sampling_margin_of_error < 1),
  ADD COLUMN IF NOT EXISTS census_threshold_ratio numeric
      NOT NULL DEFAULT 0.80 CHECK (census_threshold_ratio > 0 AND census_threshold_ratio <= 1);

-- ---------------------------------------------------------------------------
-- Quantas respostas substantivas uma coorte precisa para falar por `population`.
--
--   n0 = z^2 * p(1-p) / d^2                  amostra para populacao infinita
--   n  = n0 / (1 + (n0 - 1) / N)             correcao de populacao finita
--   n  = N  quando n > threshold * N         transicao para censo
--
-- Devolve NULL para populacao nao declarada, e NULL reprova onde for usado.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION froid_nr1_required_sample(
    population integer,
    margin_of_error numeric DEFAULT NULL,
    confidence_z numeric DEFAULT NULL,
    census_threshold numeric DEFAULT NULL
)
RETURNS integer
LANGUAGE plpgsql IMMUTABLE
AS $$
DECLARE
    d numeric := coalesce(margin_of_error, froid_nr1_sampling_margin());
    z numeric := coalesce(confidence_z, froid_nr1_sampling_confidence_z());
    threshold numeric := coalesce(census_threshold, froid_nr1_census_threshold());
    unlimited numeric;
    corrected numeric;
    needed integer;
BEGIN
    IF population IS NULL OR population <= 0 THEN
        RETURN NULL;
    END IF;
    IF d <= 0 OR d >= 1 OR z <= 0 OR threshold <= 0 OR threshold > 1 THEN
        RAISE EXCEPTION
            'parametros de amostragem invalidos: margem=%, z=%, censo=%',
            d, z, threshold;
    END IF;
    unlimited := (z * z) * 0.25 / (d * d);
    corrected := unlimited / (1 + (unlimited - 1) / population);
    -- A transicao para censo e decidida sobre o valor continuo, antes do teto.
    -- Comparando o inteiro ja arredondado, o arredondamento empurra populacoes
    -- logo acima do corte para o outro lado e a exigencia oscila: 100 pessoas
    -- pedindo amostra de 80, 101 pedindo censo de 101, 102 pedindo amostra de
    -- novo. Quem tivesse 101 no quadro pagaria por declarar uma pessoa a mais.
    IF corrected > threshold * population THEN
        RETURN population;
    END IF;
    -- O arredondamento antes do teto existe para que 80,0000000001, que e ruido
    -- da divisao e nao exigencia, nao vire 81 respostas.
    needed := LEAST(population, ceil(round(corrected, 9))::integer);
    RETURN needed;
END;
$$;

-- ---------------------------------------------------------------------------
-- Efetivo declarado passa a ser condicao de abertura.
--
-- Reproduz enforce_campaign_open_requirements() da 013 com uma exigencia a
-- mais. Guardar no banco e nao no validador de formulario pela mesma razao da
-- 013: campanha aberta sem efetivo e falha que ninguem deveria conseguir
-- publicar por acidente, e aqui ela e impossivel por construcao.
--
-- O efetivo e declarado pelo empregador. Subdeclarar para baixar a exigencia
-- cria justamente a inconsistencia com os eventos de S-2200/S-2210 que a
-- empresa ja envia, e o FAQ CGNOR confirma que a fiscalizacao consulta o
-- eSocial — o atalho custa mais caro que o caminho.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enforce_campaign_open_requirements() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'open' THEN
        IF coalesce(btrim(NEW.support_channel_label), '') = ''
           OR coalesce(btrim(NEW.support_channel_detail), '') = '' THEN
            RAISE EXCEPTION
                'campanha nao pode ser aberta sem canal de apoio ao colaborador';
        END IF;
        IF coalesce(btrim(NEW.purpose_notice), '') = '' THEN
            RAISE EXCEPTION
                'campanha nao pode ser aberta sem aviso de finalidade da coleta';
        END IF;
        IF coalesce(NEW.target_headcount, 0) <= 0 THEN
            RAISE EXCEPTION
                'campanha nao pode ser aberta sem o efetivo de trabalhadores declarado';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- A funcao de agregacao, reproduzida da 024 por copia byte a byte, com tres
-- alteracoes e nenhuma outra: le os parametros de amostragem dos criterios da
-- campanha, exige a amostra no total da campanha e exige a amostra tambem em
-- cada recorte. Transcrever 140 linhas de SQL a mao para acrescentar uma
-- clausula seria o jeito mais provavel de introduzir um defeito pior que o
-- corrigido.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION froid_nr1_dimension_scores(
    target_campaign_id uuid,
    requested_min_cohort integer DEFAULT NULL
)
RETURNS TABLE (
    unit_id uuid,
    dimension_id uuid,
    nr1_factor text,
    polarity text,
    cut_favorable numeric,
    cut_critical numeric,
    cohort_size bigint,
    mean_score numeric,
    critical_ratio numeric,
    score_stddev numeric,
    consequences text[],
    measure_efficacy text,
    exposed_workers integer
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
    campaign_opens timestamptz;
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

    SELECT campaign.organization_id, campaign.status, campaign.opens_at,
           campaign.target_headcount, campaign.criteria_id
      INTO campaign_org, campaign_status, campaign_opens, campaign_headcount,
           campaign_criteria
    FROM assessment_campaigns campaign
    WHERE campaign.id = target_campaign_id;

    IF campaign_org IS NULL OR campaign_org <> froid_current_organization_id() THEN
        RETURN;
    END IF;

    IF NOT froid_membership_is_active() THEN
        RETURN;
    END IF;

    -- A cohort that is still growing can be differenced. Results wait for the
    -- campaign to close; the response count remains readable meanwhile.
    IF campaign_status <> 'closed' THEN
        RETURN;
    END IF;

    -- Tolerancia da amostra conforme os criterios vigentes quando a campanha
    -- rodou. Campanha sem criterios vinculados cai no padrao da plataforma,
    -- porque as tres variaveis ficam nulas e a funcao faz coalesce.
    SELECT criteria.sampling_margin_of_error,
           criteria.sampling_confidence_z,
           criteria.census_threshold_ratio
      INTO sampling_margin, sampling_z, sampling_census
    FROM gro_risk_criteria criteria
    WHERE criteria.id = campaign_criteria;

    -- So respostas substantivas contam para o piso da campanha.
    --
    -- froid_nr1_submit_response aceita o envio quando ao menos UM item e
    -- valido, e isso esta certo na hora de gravar: descartar o que a pessoa
    -- respondeu seria pior. Mas contar essa resposta como um respondente
    -- inteiro faria o piso de cinquenta significar "cinquenta requisicoes
    -- chegaram" em vez de "cinquenta pessoas avaliaram este trabalho".
    --
    -- Por dimensao o dado ja estava protegido, porque o agrupamento e por
    -- resposta e dimensao. Faltava o piso.
    SELECT count(*) INTO campaign_total
    FROM assessment_responses response
    WHERE response.campaign_id = target_campaign_id
      AND response.completed
      AND froid_nr1_response_is_substantive(response.id);

    -- Portao de anonimato: coorte pequena demais para nao reidentificar.
    IF campaign_total < froid_nr1_min_cohort_total() THEN
        RETURN;
    END IF;

    -- Portao de representatividade: coorte pequena demais para falar pelo
    -- efetivo. NULL aqui significa efetivo nao declarado, e reprova.
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
               dimension.id AS response_dimension_id,
               avg(
                   CASE WHEN item.reverse_scored
                        THEN (instrument.scale_max + instrument.scale_min) - response_item.value
                        ELSE response_item.value
                   END
               )::numeric AS subject_score
        FROM assessment_responses response
        JOIN assessment_response_items response_item
          ON response_item.response_id = response.id
        JOIN assessment_items item
          ON item.id = response_item.item_id
        JOIN assessment_dimensions dimension
          ON dimension.id = item.dimension_id
        JOIN assessment_instruments instrument
          ON instrument.id = item.instrument_id
        WHERE response.campaign_id = target_campaign_id
          AND response.completed
        GROUP BY response.id, response.unit_id, dimension.id
    )
    SELECT scored.response_unit_id,
           dimension.id,
           dimension.nr1_factor,
           dimension.polarity,
           dimension.cut_favorable,
           dimension.cut_critical,
           count(*) AS cohort_size,
           round(avg(scored.subject_score), 3) AS mean_score,
           round(
               avg(
                   CASE
                       WHEN dimension.polarity = 'protective'
                            AND scored.subject_score <= dimension.cut_critical THEN 1.0
                       WHEN dimension.polarity = 'risk'
                            AND scored.subject_score >= dimension.cut_critical THEN 1.0
                       ELSE 0.0
                   END
               ), 3
           ) AS critical_ratio,
           round(coalesce(stddev_samp(scored.subject_score), 0), 3) AS score_stddev,
           dimension.consequences,
           coalesce(
               (
                   SELECT review.measure_efficacy
                   FROM measure_effectiveness_reviews review
                   JOIN assessment_campaigns prior
                     ON prior.id = review.followup_campaign_id
                   WHERE review.organization_id = campaign_org
                     AND review.dimension_id = dimension.id
                     AND review.unit_id IS NOT DISTINCT FROM scored.response_unit_id
                     AND review.followup_campaign_id <> target_campaign_id
                     -- Only a cycle that had already closed when this campaign
                     -- opened. Otherwise a later review would retroactively
                     -- change how an earlier campaign was graded.
                     AND prior.closes_at <= campaign_opens
                   ORDER BY prior.closes_at DESC, review.reviewed_at DESC
                   LIMIT 1
               ),
               'none'
           ) AS measure_efficacy,
           -- On an organization-wide campaign there is no unit headcount, so
           -- fall back to the campaign's target population. Zero here would
           -- silently switch off the priority rule of 1.5.5.2.1.1 precisely
           -- where the most workers are affected.
           GREATEST(
               coalesce(max(unit.headcount), 0),
               CASE WHEN scored.response_unit_id IS NULL
                    THEN coalesce(campaign_headcount, 0) ELSE 0 END
           ) AS exposed_workers
    FROM response_dimension scored
    JOIN assessment_dimensions dimension
      ON dimension.id = scored.response_dimension_id
    LEFT JOIN organization_units unit
      ON unit.id = scored.response_unit_id
    GROUP BY scored.response_unit_id, dimension.id, dimension.nr1_factor,
             dimension.polarity, dimension.cut_favorable, dimension.cut_critical,
             dimension.consequences
    -- Os dois portoes no recorte. O de anonimato conta cabecas; o de
    -- representatividade compara com o efetivo daquele recorte, que e o mesmo
    -- numero ja usado em exposed_workers. Recorte sem efetivo declarado produz
    -- NULL e nao aparece: sem denominador nao ha o que representar.
    HAVING count(*) >= effective_cut_floor
       AND count(*) >= froid_nr1_required_sample(
               GREATEST(
                   coalesce(max(unit.headcount), 0),
                   CASE WHEN scored.response_unit_id IS NULL
                        THEN coalesce(campaign_headcount, 0) ELSE 0 END
               ),
               sampling_margin, sampling_z, sampling_census
           );
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_dimension_scores(uuid, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION froid_nr1_required_sample(integer, numeric, numeric, numeric) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_nr1_dimension_scores(uuid, integer)
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_required_sample(integer, numeric, numeric, numeric)
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_sampling_confidence_z() TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_sampling_margin() TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_census_threshold() TO froid_runtime;
    END IF;
END
$$;

-- Campanha ja encerrada com efetivo nao declarado deixa de render inventario a
-- partir daqui. Nao ha o que migrar automaticamente — ninguem alem da empresa
-- sabe qual era o quadro no periodo de referencia — mas o deploy tem que saber
-- que existem, em vez de descobrir pelo suporte.
DO $$
DECLARE
    orfas integer;
BEGIN
    SELECT count(*) INTO orfas
    FROM assessment_campaigns
    WHERE status = 'closed' AND coalesce(target_headcount, 0) <= 0;
    IF orfas > 0 THEN
        RAISE NOTICE
            '% campanha(s) encerrada(s) sem efetivo declarado: o inventario '
            'delas fica suspenso ate a organizacao informar target_headcount.',
            orfas;
    END IF;
END
$$;

INSERT INTO schema_migrations (version)
VALUES ('025_representativeness_floor')
ON CONFLICT (version) DO NOTHING;

COMMIT;
