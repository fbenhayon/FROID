-- Proposta personalizada junto com o kit de demonstração NR-1.
--
-- 24/11/2026, pedido do dono: quem pede o kit no site informa razão social,
-- CNPJ, número de estabelecimentos e de trabalhadores, e recebe no mesmo
-- e-mail a proposta já com o valor mensal calculado (froid-server/proposta_nr1.py).
--
-- `proposta` é o retrato do que foi calculado no pedido: valores já escritos,
-- e o código, a versão e a digital da tabela comercial que os produziu. A página
-- da proposta lê só este retrato, para que ela continue dizendo o que foi
-- proposto mesmo depois de a tabela mudar.
--
-- O link continua sendo o do kit (kit_token_sha256 / kit_expira_em, da 057):
-- um token só abre os dois documentos. proposta_acessos diz ao comercial se a
-- proposta foi aberta, separado do kit.
--
-- Continua valendo o aviso da 021: nada aqui é dado sensível. CNPJ e efetivo
-- são dados da empresa, não de pessoa.

BEGIN;

ALTER TABLE marketing_leads
    ADD COLUMN IF NOT EXISTS cnpj TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS estabelecimentos INTEGER,
    ADD COLUMN IF NOT EXISTS trabalhadores INTEGER,
    ADD COLUMN IF NOT EXISTS proposta JSONB,
    ADD COLUMN IF NOT EXISTS proposta_acessos INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS proposta_ultimo_acesso_em TIMESTAMPTZ;

INSERT INTO schema_migrations (version)
VALUES ('058_marketing_leads_proposta')
ON CONFLICT (version) DO NOTHING;

COMMIT;
