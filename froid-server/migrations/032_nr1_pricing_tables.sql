BEGIN;

-- Tabela comercial do FROID NR-1: versionada, com digital, e nunca sobrescrita.
--
-- POR QUE ELA EXISTE
-- Ate 11/09/2026 o preco do NR-1 nao tinha fonte de execucao. Vivia numa
-- constante de arquivo de TESTE, num gerador de planilha e em mais dez copias
-- publicadas, todas digitadas a mao. Foi assim que tres bases diferentes
-- chegaram a circular ao mesmo tempo para o MESMO componente: R$ 1.200 numa
-- proposta ja enviada, R$ 500 no site, R$ 200 no motor novo.
--
-- A regra de ouro deste par de tabelas: PRECO NOVO E LINHA NOVA. Editar
-- `base_establishment_cents` de uma tabela ja usada em proposta apaga a
-- explicacao de um numero que o cliente tem em maos.

CREATE TABLE IF NOT EXISTS nr1_pricing_tables (
    code text PRIMARY KEY,
    name text NOT NULL,
    version text NOT NULL,
    valid_from date NOT NULL,
    valid_to date,
    status text NOT NULL
        CHECK (status IN ('draft', 'active', 'inactive', 'archived')),
    base_establishment_cents integer NOT NULL
        CHECK (base_establishment_cents >= 0),
    -- sha256 do payload canonico, conferido pela aplicacao ANTES de calcular.
    -- Divergiu, o servico recusa em vez de precificar com tabela adulterada.
    config_hash char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS nr1_pricing_tiers (
    pricing_table_code text NOT NULL
        REFERENCES nr1_pricing_tables(code) ON DELETE CASCADE,
    tier_order integer NOT NULL CHECK (tier_order >= 1),
    lower_bound integer NOT NULL CHECK (lower_bound >= 1),
    -- Nulo so na ultima faixa. A aplicacao recusa tabela com buraco entre
    -- faixas, e o banco garante ao menos que nenhuma faixa seja invertida.
    upper_bound integer,
    worker_price_cents integer NOT NULL CHECK (worker_price_cents >= 0),
    PRIMARY KEY (pricing_table_code, tier_order),
    CHECK (upper_bound IS NULL OR upper_bound >= lower_bound)
);

-- Duas tabelas ativas ao mesmo tempo produziriam duas propostas com precos
-- diferentes no mesmo dia, e nada indicaria qual das duas valia.
--
-- Indice unico sobre `status` RESTRITO as ativas: como toda linha filtrada tem
-- o mesmo valor ('active'), duas delas colidem. A primeira versao usava
-- `((true))`, que e a forma esperta e sobre a qual eu nao tinha certeza — e
-- migration roda na SUBIDA do backend, entao sintaxe que o Postgres recusa nao
-- da erro de teste: derruba o servidor longe de quem escreveu.
CREATE UNIQUE INDEX IF NOT EXISTS nr1_pricing_uma_ativa_por_vez
    ON nr1_pricing_tables (status) WHERE status = 'active';

-- NAO existe tabela de simulacoes aqui, e isso e deliberado.
--
-- A primeira versao desta migration criava `nr1_pricing_simulations`, e ela
-- teria nascido sem escritor: o valor aceito pela empresa e gravado no
-- `commercial_snapshot` de `legal_acceptance_events` (migration 009), que ja
-- existe, ja e append-only por gatilho e ja amarra o preco AO ACEITE — que e
-- a amarracao que importa. Uma segunda tabela guardando a mesma coisa seria
-- o padrao que mais custou tempo nesta casa: peca correta que ninguem
-- consome, e que depois diverge da que e consumida.

-- A tabela vigente.
--
-- Estes numeros sao os mesmos de `pricing_nr1.TABELA_VIGENTE`, e
-- `test_pricing_nr1_no_banco.py` compara os dois lado a lado — inclusive o
-- hash. Copia entre SQL e Python diverge em silencio, e a divergencia aqui
-- seria um preco no painel e outro na simulacao publica.
INSERT INTO nr1_pricing_tables (
    code, name, version, valid_from, valid_to, status,
    base_establishment_cents, config_hash
) VALUES (
    'FROID-PRICING-2026-V01',
    'Tabela Comercial FROID NR-1',
    '1.0',
    DATE '2026-01-01',
    NULL,
    'active',
    20000,
    '043dcbeecb79c313e8c1fe5fe0373b70107efca6b1232a8b2f3bfe744c097fea'
) ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    version = EXCLUDED.version,
    valid_from = EXCLUDED.valid_from,
    valid_to = EXCLUDED.valid_to,
    status = EXCLUDED.status,
    base_establishment_cents = EXCLUDED.base_establishment_cents,
    config_hash = EXCLUDED.config_hash;

DELETE FROM nr1_pricing_tiers WHERE pricing_table_code = 'FROID-PRICING-2026-V01';
INSERT INTO nr1_pricing_tiers
    (pricing_table_code, tier_order, lower_bound, upper_bound, worker_price_cents)
VALUES
    ('FROID-PRICING-2026-V01', 1, 1, 100, 1500),
    ('FROID-PRICING-2026-V01', 2, 101, 300, 1250),
    ('FROID-PRICING-2026-V01', 3, 301, 1000, 930),
    ('FROID-PRICING-2026-V01', 4, 1001, NULL, 655);

ALTER TABLE nr1_pricing_tables ENABLE ROW LEVEL SECURITY;
ALTER TABLE nr1_pricing_tiers ENABLE ROW LEVEL SECURITY;

-- A tabela de preco e publica por natureza: ela ja esta impressa no site. O
-- que o runtime NAO pode e escreve-la nem ler simulacao de outra empresa.
REVOKE ALL ON nr1_pricing_tables FROM PUBLIC;
REVOKE ALL ON nr1_pricing_tiers FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT SELECT ON nr1_pricing_tables TO froid_runtime;
    GRANT SELECT ON nr1_pricing_tiers TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version)
VALUES('032_nr1_pricing_tables') ON CONFLICT DO NOTHING;

COMMIT;
