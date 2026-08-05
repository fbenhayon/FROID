-- Purga das respostas individuais depois que o inventário já as consolidou.
--
-- A NR-1 exige vinte anos de histórico do inventário (1.5.7.3.3.1). Isso é
-- uma obrigação sobre o INVENTÁRIO — documento agregado — e não sobre as
-- respostas cruas que o produziram. Guardar resposta individual de saúde
-- mental por vinte anos porque o inventário precisa durar vinte anos confunde
-- as duas coisas, e viola minimização sem ganhar nada: depois de consolidado,
-- a resposta crua não responde nenhuma pergunta que o agregado não responda.
--
-- Duas travas antes de qualquer DELETE.
--
-- A campanha precisa estar encerrada. Purgar campanha aberta destruiria a
-- coleta em curso.
--
-- O agregado precisa já existir. Se ninguém consolidou o inventário, apagar a
-- resposta apaga a única evidência de que a avaliação aconteceu — e aí a
-- empresa perde a prova de conformidade justamente por excesso de zelo com o
-- dado.
--
-- O que sobrevive: o inventário, o agregado por dimensão, a contagem de
-- participação e a trilha de auditoria. Tudo que o fiscal pede, nada que
-- identifique alguém.

BEGIN;

ALTER TABLE assessment_campaigns
  ADD COLUMN IF NOT EXISTS responses_purged_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS responses_purged_count INTEGER;

-- Quais campanhas já podem ser purgadas, e por quê ainda não podem.
--
-- Devolve o motivo do bloqueio em vez de apenas omitir a campanha: "não
-- aparece na lista" é a forma mais comum de um controle parecer funcionar
-- enquanto esconde um defeito.
CREATE OR REPLACE FUNCTION froid_purge_candidates(p_grace_days INTEGER DEFAULT 90)
RETURNS TABLE (
    campaign_id UUID,
    title TEXT,
    closes_at TIMESTAMPTZ,
    responses BIGINT,
    has_aggregate BOOLEAN,
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT
        c.id,
        c.title,
        c.closes_at,
        (SELECT count(*) FROM assessment_responses r WHERE r.campaign_id = c.id),
        EXISTS (SELECT 1 FROM psychosocial_risk_inventory i WHERE i.campaign_id = c.id),
        (
            c.closes_at < now() - make_interval(days => p_grace_days)
            AND c.responses_purged_at IS NULL
            AND EXISTS (SELECT 1 FROM psychosocial_risk_inventory i WHERE i.campaign_id = c.id)
            AND EXISTS (SELECT 1 FROM assessment_responses r WHERE r.campaign_id = c.id)
        ),
        CASE
            WHEN c.responses_purged_at IS NOT NULL THEN 'ja purgada'
            WHEN c.closes_at >= now() THEN 'coleta ainda aberta'
            WHEN c.closes_at >= now() - make_interval(days => p_grace_days)
                THEN 'dentro da carencia de ' || p_grace_days || ' dias'
            WHEN NOT EXISTS (SELECT 1 FROM psychosocial_risk_inventory i WHERE i.campaign_id = c.id)
                THEN 'inventario ainda nao consolidado — purgar apagaria a unica evidencia'
            WHEN NOT EXISTS (SELECT 1 FROM assessment_responses r WHERE r.campaign_id = c.id)
                THEN 'sem respostas a purgar'
            ELSE 'elegivel'
        END
    FROM assessment_campaigns c
    ORDER BY c.closes_at DESC;
$$;

-- A purga em si. Recusa em vez de purgar quando qualquer trava falha.
CREATE OR REPLACE FUNCTION froid_purge_campaign_responses(
    p_campaign_id UUID,
    p_grace_days INTEGER DEFAULT 90
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    elegivel BOOLEAN;
    motivo TEXT;
    removidas INTEGER;
BEGIN
    SELECT c.eligible, c.reason INTO elegivel, motivo
    FROM froid_purge_candidates(p_grace_days) c
    WHERE c.campaign_id = p_campaign_id;

    IF elegivel IS NULL THEN
        RAISE EXCEPTION 'campanha % nao encontrada', p_campaign_id;
    END IF;
    IF NOT elegivel THEN
        RAISE EXCEPTION 'campanha % nao pode ser purgada: %', p_campaign_id, motivo;
    END IF;

    DELETE FROM assessment_responses WHERE campaign_id = p_campaign_id;
    GET DIAGNOSTICS removidas = ROW_COUNT;

    UPDATE assessment_campaigns
       SET responses_purged_at = now(), responses_purged_count = removidas
     WHERE id = p_campaign_id;

    RETURN removidas;
END;
$$;

INSERT INTO schema_migrations (version)
VALUES ('020_response_retention')
ON CONFLICT (version) DO NOTHING;

COMMIT;
