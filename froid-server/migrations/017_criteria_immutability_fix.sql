-- Corrige o gatilho de imutabilidade dos criterios do GRO.
--
-- Dois defeitos, ambos encontrados no piloto contra o banco real.
--
-- 1. O gatilho cobria UPDATE OR DELETE. A imutabilidade que interessa e a do
--    CONTEUDO: um criterio publicado nao pode ser reescrito, senao uma campanha
--    passada deixa de ser explicavel pelos criterios vigentes quando rodou.
--    Impedir a remocao e outra coisa, e ja esta garantida onde importa: as
--    tabelas que referenciam gro_risk_criteria usam ON DELETE RESTRICT, entao
--    um criterio em uso nao sai de jeito nenhum. Bloquear tambem o que nao esta
--    em uso so impedia limpar dado de teste, sem proteger nada.
--
-- 2. Num gatilho BEFORE DELETE, devolver NEW — que e nulo nesse contexto —
--    cancela a operacao. Na pratica nem criterio NAO publicado podia ser
--    apagado, e sem erro nenhum: o DELETE simplesmente nao acontecia e o
--    chamador achava que tinha funcionado. Esse era o mais perigoso dos dois,
--    porque falhava em silencio.

BEGIN;

DROP TRIGGER IF EXISTS gro_risk_criteria_immutable ON gro_risk_criteria;

CREATE OR REPLACE FUNCTION prevent_published_criteria_mutation() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.published_at IS NOT NULL THEN
        RAISE EXCEPTION
            'critérios do GRO já publicados são imutáveis; publique uma nova versão';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER gro_risk_criteria_immutable
BEFORE UPDATE ON gro_risk_criteria
FOR EACH ROW EXECUTE FUNCTION prevent_published_criteria_mutation();

INSERT INTO schema_migrations (version)
VALUES ('017_criteria_immutability_fix')
ON CONFLICT (version) DO NOTHING;

COMMIT;
