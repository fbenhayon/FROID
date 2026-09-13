-- O elo convite-resposta deixa de existir quando a coleta fecha.
--
-- POR QUE. A promessa que o convite faz ao trabalhador — "ninguém consegue
-- saber quem respondeu o quê" — era, até aqui, uma garantia de CONDUTA e de
-- controle de acesso, e não de arquitetura. O desenho já separava o
-- conhecimento em duas mãos:
--
--   o FROID     tem respostas <-> pseudônimo, e NÃO tem pseudônimo <-> matrícula
--   a empresa   tem pseudônimo <-> matrícula, e NÃO tem as respostas
--
-- Sozinha, nenhuma das duas partes consegue parear pessoa e resposta. Juntas,
-- conseguiriam — sob ordem judicial, por conluio, ou num vazamento que
-- alcançasse o nosso banco e o CSV que a empresa baixou para despachar os
-- links. O elo que tornava isso possível era uma única coluna:
-- `assessment_responses.invitation_id`.
--
-- O QUE ESSA COLUNA FAZIA. Nada além de sustentar `UNIQUE (invitation_id)`, que
-- impede dois envios pelo mesmo convite. Ela é escrita uma vez e NUNCA LIDA:
-- nenhum SELECT, nenhum JOIN, nenhum agregado a menciona. Verificado por
-- varredura em 12/09/2026 e travado por teste.
--
-- Encerrada a coleta, a campanha não aceita mais resposta — e a partir daí a
-- coluna é só risco de reidentificação guardado sem finalidade. A minimização
-- do art. 6º, III da LGPD manda exatamente isto: dado que deixou de ser
-- necessário para a finalidade não se conserva.
--
-- O QUE NÃO SE PERDE. `assessment_invitations.status='responded'` e
-- `responded_at` continuam registrando a participação — é disso que a reemissão
-- precisa, e é o que permite à empresa acompanhar a adesão. O agregado é
-- calculado por campanha e por unidade, nunca por convite.
--
-- Depois desta migration, a frase do convite passa a ser verdade de
-- ARQUITETURA: o dado que permitiria o pareamento deixa de existir, e nem uma
-- ordem judicial o recupera, porque não há o que entregar.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. A coluna passa a aceitar nulo.
--
-- Em PostgreSQL, nulos são distintos entre si num índice único: a restrição
-- `UNIQUE (invitation_id)` continua impedindo envio duplo enquanto a coleta
-- está aberta, e não reclama de várias respostas com o elo já rompido.
-- ---------------------------------------------------------------------------
ALTER TABLE assessment_responses ALTER COLUMN invitation_id DROP NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. O rompimento, como função do dono do esquema.
--
-- SECURITY DEFINER pela mesma razão de todo o resto deste módulo: o papel da
-- aplicação teve TODOS os privilégios revogados sobre `assessment_responses`
-- na migration 014. Ele não lê uma resposta e não a altera — pode apenas pedir
-- que o dono do esquema rompa os elos de uma campanha que ele acabou de fechar.
--
-- A função é idempotente e devolve quantos elos rompeu, para a trilha de
-- auditoria registrar o número em vez de "executou".
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION froid_nr1_sever_response_links(p_campaign_id uuid)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_rompidos integer;
BEGIN
    -- Só para campanha JÁ FECHADA. Romper com a coleta aberta destruiria a
    -- guarda contra envio duplo, e a condição mora aqui — e não na aplicação —
    -- para que a garantia sobreviva a um erro na camada de cima.
    IF NOT EXISTS (
        SELECT 1 FROM assessment_campaigns
        WHERE id = p_campaign_id AND status = 'closed'
    ) THEN
        RAISE EXCEPTION 'campanha % nao esta fechada', p_campaign_id
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    UPDATE assessment_responses
       SET invitation_id = NULL
     WHERE campaign_id = p_campaign_id
       AND invitation_id IS NOT NULL;

    GET DIAGNOSTICS v_rompidos = ROW_COUNT;
    RETURN v_rompidos;
END;
$$;

REVOKE ALL ON FUNCTION froid_nr1_sever_response_links(uuid) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN
        GRANT EXECUTE ON FUNCTION froid_nr1_sever_response_links(uuid)
            TO froid_runtime;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. As campanhas que já fecharam antes desta migration.
--
-- Sem isto, a garantia valeria só para o futuro e as coletas antigas
-- continuariam carregando o elo — que é justamente onde o dado ficou parado por
-- mais tempo, sem finalidade nenhuma.
-- ---------------------------------------------------------------------------
UPDATE assessment_responses AS resposta
   SET invitation_id = NULL
  FROM assessment_campaigns AS campanha
 WHERE campanha.id = resposta.campaign_id
   AND campanha.status = 'closed'
   AND resposta.invitation_id IS NOT NULL;

INSERT INTO schema_migrations(version)
VALUES('034_anonimato_apos_o_fechamento') ON CONFLICT DO NOTHING;

COMMIT;
