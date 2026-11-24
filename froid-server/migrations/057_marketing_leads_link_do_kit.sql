-- Link individual do kit de demonstração NR-1.
--
-- 23/11/2026, determinação do dono: o kit só sai para quem se cadastra pelo
-- site, e só por e-mail. Até aqui o PDF ficava num endereço público fixo
-- (/site-assets/docs/...) e o botão aparecia na tela logo após o envio: quem
-- tivesse o endereço baixava sem cadastro, e um e-mail inventado também
-- liberava o kit.
--
-- Agora cada cadastro recebe por e-mail um link próprio, que expira. Guarda-se
-- só o SHA-256 do token — o token em si existe apenas no e-mail do visitante —,
-- e um novo pedido do mesmo e-mail troca o token, invalidando o anterior.
-- kit_acessos e kit_ultimo_acesso_em dizem ao comercial se o kit foi aberto.
--
-- Continua valendo o aviso da 021: nada aqui é dado sensível.

BEGIN;

ALTER TABLE marketing_leads
    ADD COLUMN IF NOT EXISTS kit_token_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS kit_expira_em TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS kit_acessos INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS kit_ultimo_acesso_em TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS marketing_leads_kit_token_idx
    ON marketing_leads (kit_token_sha256)
    WHERE kit_token_sha256 IS NOT NULL;

INSERT INTO schema_migrations (version)
VALUES ('057_marketing_leads_link_do_kit')
ON CONFLICT (version) DO NOTHING;

COMMIT;
