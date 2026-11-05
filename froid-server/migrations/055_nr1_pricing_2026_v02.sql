BEGIN;

-- Nova condicao comercial do FROID NR-1, vigente a partir de 05/11/2026.
-- Preco novo e linha nova: a V01 permanece no historico para propostas ja
-- emitidas, e a V02 passa a ser a unica tabela ativa para simulacao publica.

UPDATE nr1_pricing_tables
SET status = 'inactive',
    valid_to = DATE '2026-11-04'
WHERE code = 'FROID-PRICING-2026-V01'
  AND status = 'active';

INSERT INTO nr1_pricing_tables (
    code, name, version, valid_from, valid_to, status,
    base_establishment_cents, config_hash
) VALUES (
    'FROID-PRICING-2026-V02',
    'Tabela Comercial FROID NR-1',
    '1.1',
    DATE '2026-11-05',
    NULL,
    'active',
    27670,
    '36164a02ad5d2ece58053efd746c17de755afb4a41402dc85048941cbd0acc19'
) ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    version = EXCLUDED.version,
    valid_from = EXCLUDED.valid_from,
    valid_to = EXCLUDED.valid_to,
    status = EXCLUDED.status,
    base_establishment_cents = EXCLUDED.base_establishment_cents,
    config_hash = EXCLUDED.config_hash;

DELETE FROM nr1_pricing_tiers WHERE pricing_table_code = 'FROID-PRICING-2026-V02';
INSERT INTO nr1_pricing_tiers
    (pricing_table_code, tier_order, lower_bound, upper_bound, worker_price_cents)
VALUES
    ('FROID-PRICING-2026-V02', 1, 1, 100, 2075),
    ('FROID-PRICING-2026-V02', 2, 101, 300, 1729),
    ('FROID-PRICING-2026-V02', 3, 301, 1000, 1487),
    ('FROID-PRICING-2026-V02', 4, 1001, NULL, 993);

INSERT INTO schema_migrations(version)
VALUES('055_nr1_pricing_2026_v02') ON CONFLICT DO NOTHING;

COMMIT;
