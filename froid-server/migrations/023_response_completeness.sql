-- Uma resposta quase vazia não é um respondente.
--
-- froid_nr1_submit_response aceita a submissão quando ao menos UM item é
-- válido — o que é a decisão certa na hora de gravar, porque descartar o que
-- a pessoa respondeu seria pior. Mas essa mesma resposta conta como um
-- respondente inteiro para o piso de 50 da campanha.
--
-- O efeito é sutil e ruim: cinquenta respostas de um item cada liberariam o
-- painel, e a gradação sairia de dimensões que quase ninguém respondeu. O
-- piso deixaria de significar "cinquenta pessoas avaliaram este trabalho" e
-- passaria a significar "cinquenta requisições chegaram".
--
-- Por dimensão o dado já estava protegido: o agrupamento é por resposta e
-- dimensão, então quem não respondeu nada de uma dimensão não entra na coorte
-- dela. O que faltava era o piso da campanha.
--
-- A resposta continua sendo gravada por inteiro. O que muda é quem conta para
-- liberar o painel.

BEGIN;

-- Proporção mínima das dimensões do instrumento que uma resposta precisa
-- cobrir para contar como respondente. Metade é deliberadamente tolerante:
-- quem abandonou no meio ainda conta, quem tocou em uma pergunta não.
CREATE OR REPLACE FUNCTION froid_nr1_min_response_coverage()
RETURNS numeric
LANGUAGE sql
IMMUTABLE
AS $$ SELECT 0.50::numeric $$;

-- Quantas dimensões do instrumento esta resposta efetivamente cobriu, e
-- quantas o instrumento tem. Serve tanto ao piso quanto ao diagnóstico de
-- adesão: uma campanha cheia de respostas parciais é um problema de
-- comunicação, e o gestor precisa poder ver isso.
CREATE OR REPLACE FUNCTION froid_nr1_response_is_substantive(p_response_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    WITH cobertas AS (
        SELECT count(DISTINCT item.dimension_id) AS n
        FROM assessment_response_items response_item
        JOIN assessment_items item ON item.id = response_item.item_id
        WHERE response_item.response_id = p_response_id
    ),
    totais AS (
        SELECT count(DISTINCT item.dimension_id) AS n
        FROM assessment_responses response
        JOIN assessment_campaigns campaign ON campaign.id = response.campaign_id
        JOIN assessment_items item ON item.instrument_id = campaign.instrument_id
        WHERE response.id = p_response_id
    )
    SELECT CASE
        WHEN (SELECT n FROM totais) = 0 THEN FALSE
        ELSE (SELECT n FROM cobertas)::numeric
             >= (SELECT n FROM totais)::numeric * froid_nr1_min_response_coverage()
    END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_min_response_coverage() FROM PUBLIC;
REVOKE ALL ON FUNCTION froid_nr1_response_is_substantive(uuid) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_nr1_min_response_coverage()
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_nr1_response_is_substantive(uuid)
            TO froid_runtime;
    END IF;
END
$$;

INSERT INTO schema_migrations (version)
VALUES ('023_response_completeness')
ON CONFLICT (version) DO NOTHING;

COMMIT;
