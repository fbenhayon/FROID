-- A adesao da campanha volta a ser legivel sem conceder leitura da resposta.
--
-- O QUE ESTAVA ERRADO
--
-- A migration 014 REVOGA todo acesso do papel de runtime a
-- assessment_responses, e essa revogacao e a base estrutural do anonimato do
-- modulo: o agregado sai por funcao SECURITY DEFINER justamente para que o
-- k-anonimato nao dependa de ninguem escrever a query certa.
--
-- A 023/024 acrescentaram a contagem de respostas substantivas ao progresso da
-- campanha, e nr1_campaign_progress passou a contar com dois subselects
-- diretos em assessment_responses. Em desenvolvimento e na suite isso passa,
-- porque ali a conexao e a de OWNER. Em producao a conexao e a de runtime, e o
-- resultado foi 503 em TODO painel NR-1:
--
--     psycopg.errors.InsufficientPrivilege:
--     permission denied for table assessment_responses
--
-- O sintoma aparecia como "painel NR-1 indisponivel" — a empresa com a coleta
-- encerrada nao via resultado nenhum e nao conseguia gerar o inventario, que
-- chama o mesmo progresso.
--
-- O QUE ESTA MIGRATION NAO FAZ, E POR QUE
--
-- Nao concede SELECT em assessment_responses. Seria o conserto de uma linha e
-- desfaria a decisao da 014: com leitura concedida, qualquer consulta futura
-- neste arquivo passa a poder trazer resposta individual de trabalhador, e a
-- fronteira que separa o empregador do dado clinico deixa de ser garantida
-- pelo banco para depender de revisao de codigo.
--
-- O QUE ELA FAZ
--
-- Move a contagem para dentro de uma funcao SECURITY DEFINER que devolve dois
-- inteiros e nada mais — nunca uma linha de resposta. Os guardas sao os mesmos
-- do agregado, e pela mesma razao: SECURITY DEFINER sem eles leria campanha de
-- outro inquilino.
--
-- Sem guarda de status, de proposito: a adesao e legivel enquanto a coleta
-- esta aberta — a organizacao precisa perseguir participacao, e contagem nao
-- revela resposta. O que espera o encerramento e o RESULTADO, e quem o segura
-- e froid_nr1_dimension_scores.

BEGIN;

CREATE OR REPLACE FUNCTION froid_nr1_campaign_response_counts(
    target_campaign_id uuid
)
RETURNS TABLE (recorded bigint, substantive bigint)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    campaign_org uuid;
BEGIN
    SELECT campaign.organization_id INTO campaign_org
    FROM assessment_campaigns campaign
    WHERE campaign.id = target_campaign_id;

    IF campaign_org IS NULL OR campaign_org <> froid_current_organization_id() THEN
        RETURN;
    END IF;

    IF NOT froid_membership_is_active() THEN
        RETURN;
    END IF;

    -- Gravadas e substantivas na mesma varredura. Separa-las em duas consultas
    -- deixaria os dois numeros divergirem quando uma resposta chega no meio,
    -- e a diferenca entre eles e exatamente o que a tela publica como
    -- "respostas parciais".
    RETURN QUERY
    SELECT count(*),
           count(*) FILTER (
               WHERE froid_nr1_response_is_substantive(response.id)
           )
    FROM assessment_responses response
    WHERE response.campaign_id = target_campaign_id
      AND response.completed;
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_campaign_response_counts(uuid) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_nr1_campaign_response_counts(uuid)
            TO froid_runtime;
    END IF;
END
$$;

INSERT INTO schema_migrations (version)
VALUES ('029_progresso_sem_ler_resposta')
ON CONFLICT (version) DO NOTHING;

COMMIT;
