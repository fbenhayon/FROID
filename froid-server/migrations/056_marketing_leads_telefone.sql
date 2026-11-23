-- Telefone do contato que pede o kit de demonstração NR-1.
--
-- 23/11/2026, determinação do dono: quem baixa o kit deixa os dados para o
-- comercial entrar em contato — e contato comercial B2B, na prática, é
-- telefone. A coluna é opcional (vazia quando não informado), com a mesma base
-- legal da 021: legítimo interesse, finalidade dita no próprio formulário,
-- oposição garantida por opt_out_at.
--
-- Continua valendo o aviso da 021: nada aqui é dado sensível, e não pode
-- passar a ser.

BEGIN;

ALTER TABLE marketing_leads
    ADD COLUMN IF NOT EXISTS telefone TEXT NOT NULL DEFAULT '';

INSERT INTO schema_migrations (version)
VALUES ('056_marketing_leads_telefone')
ON CONFLICT (version) DO NOTHING;

COMMIT;
