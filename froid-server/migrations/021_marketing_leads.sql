-- Contatos deixados no diagnóstico de prontidão do site.
--
-- Dado de contato profissional, deixado voluntariamente por quem quer o
-- material. Base legal: legítimo interesse (art. 7º, IX) para o contato
-- comercial B2B, com a finalidade dita na própria página e o direito de
-- oposição garantido — que é o que o art. 7º, §. exige de quem usa essa base.
--
-- Nada aqui é dado sensível, e não pode passar a ser: este é o formulário
-- público do site, sem autenticação. Se um dia alguém quiser guardar resposta
-- de questionário aqui, o lugar certo é outro, com outra base legal e outra
-- proteção.

BEGIN;

CREATE TABLE IF NOT EXISTS marketing_leads (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome          TEXT NOT NULL,
    email         TEXT NOT NULL,
    empresa       TEXT NOT NULL,
    cargo         TEXT NOT NULL DEFAULT '',
    -- O resultado da calculadora no momento do envio: porte, setores e
    -- adesão. Serve para o comercial saber, antes de ligar, se aquele lead
    -- tem porte para a avaliação completa ou se o caminho dele é a AEP.
    contexto      TEXT NOT NULL DEFAULT '',
    origem        TEXT NOT NULL DEFAULT 'diagnostico-nr1',
    -- Oposição ao tratamento (art. 18, § 2º). Marcado, para de receber.
    opt_out_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT marketing_leads_email_check CHECK (position('@' IN email) > 1),
    CONSTRAINT marketing_leads_nome_check CHECK (length(btrim(nome)) > 1)
);

-- Um mesmo e-mail pode voltar ao site e recalcular; guardamos a visita mais
-- recente em vez de duplicar a pessoa na base.
CREATE UNIQUE INDEX IF NOT EXISTS marketing_leads_email_idx
    ON marketing_leads (lower(btrim(email)));

CREATE INDEX IF NOT EXISTS marketing_leads_created_idx
    ON marketing_leads (created_at DESC);

INSERT INTO schema_migrations (version)
VALUES ('021_marketing_leads')
ON CONFLICT (version) DO NOTHING;

COMMIT;
