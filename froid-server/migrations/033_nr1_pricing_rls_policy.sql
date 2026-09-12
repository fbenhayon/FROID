BEGIN;

-- RLS ligado SEM politica devolve zero linhas, e nao erro.
--
-- O CASO, 11/09/2026. A migration 032 fez `ENABLE ROW LEVEL SECURITY` nas duas
-- tabelas de preco e concedeu SELECT ao `froid_runtime` — e nao criou politica
-- nenhuma. No Postgres isso nao e "acesso liberado com RLS desligado": e RLS
-- ativo com regra vazia, e regra vazia nao casa com linha nenhuma.
--
-- O dono da tabela ignora RLS (nao ha FORCE aqui), entao o INSERT da propria
-- 032 funcionou e a leitura do livro de aceites, que vai pela conexao de dono,
-- tambem. So a leitura pelo papel de runtime — que e a da rota publica de preco
-- — enxergava zero linhas. Sem excecao, sem log, sem sintoma no servidor.
--
-- O defeito NAO se manifestou como erro em producao porque a rota declara de
-- onde veio a tabela: a resposta trouxe `"source":"modulo"` em vez de
-- `"postgres"`, e foi esse campo que denunciou. Sem ele o numero estaria certo,
-- a tabela do banco estaria sendo ignorada, e ninguem saberia.
--
-- POR QUE A POLITICA AQUI E ABERTA, e nao por organizacao como as demais.
-- Esta tabela nao e dado de cliente: e UMA tabela comercial global, sem coluna
-- `organization_id`, cujo conteudo ja esta impresso nas oito paginas publicas
-- do site em quatro idiomas. Restringi-la por organizacao nao protegeria nada e
-- quebraria a rota publica, que e anonima por desenho. A escrita continua fora
-- do alcance do runtime: a 032 so concedeu SELECT.

DROP POLICY IF EXISTS nr1_pricing_tables_leitura ON nr1_pricing_tables;
DROP POLICY IF EXISTS nr1_pricing_tiers_leitura ON nr1_pricing_tiers;

CREATE POLICY nr1_pricing_tables_leitura
ON nr1_pricing_tables FOR SELECT USING (true);

CREATE POLICY nr1_pricing_tiers_leitura
ON nr1_pricing_tiers FOR SELECT USING (true);

INSERT INTO schema_migrations(version)
VALUES('033_nr1_pricing_rls_policy') ON CONFLICT DO NOTHING;

COMMIT;
