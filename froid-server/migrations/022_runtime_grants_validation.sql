-- Acesso do papel de runtime às tabelas das migrations 018 a 021.
--
-- As quatro migrations anteriores criaram tabela e política de RLS e
-- esqueceram o GRANT. O efeito é traiçoeiro: a migration aplica, a tabela
-- aparece em schema_migrations, tudo parece pronto — e a primeira escrita
-- falha por permissão, longe do deploy que a causou.
--
-- Foi assim que o formulário de captação devolveu 503 com a tabela já criada
-- e vazia. E o módulo de validade teria feito o mesmo no primeiro uso real,
-- só que na frente de um profissional em vez de num curl de verificação.
--
-- O padrão é o da migration 003: só concede o que cada caminho precisa, e
-- nada além.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime') THEN

        -- 018: estudo de validade convergente.
        --
        -- Instrumentos são catálogo: leitura apenas. Quem decide que o PHQ-9
        -- existe é a migration, não o runtime.
        GRANT SELECT ON validation_instruments TO froid_runtime;
        GRANT SELECT, INSERT ON
            validation_administrations, validation_observations
        TO froid_runtime;
        -- A retirada do participante apaga as administrações; as observações
        -- vão junto por cascade.
        GRANT DELETE ON validation_administrations TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_validation_pairs(TEXT, TEXT)
            TO froid_runtime;

        -- 019: consentimento de pesquisa.
        GRANT SELECT, INSERT, UPDATE ON patient_research_consent TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_revoke_research_consent(UUID, UUID)
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_research_consent_active(UUID)
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_validation_progress()
            TO froid_runtime;

        -- 020: retenção de respostas.
        --
        -- Sem DELETE direto em assessment_responses: a purga passa
        -- obrigatoriamente pela função, que é onde moram as duas travas —
        -- campanha encerrada e inventário já consolidado.
        GRANT EXECUTE ON FUNCTION froid_purge_candidates(INTEGER)
            TO froid_runtime;
        GRANT EXECUTE ON FUNCTION froid_purge_campaign_responses(UUID, INTEGER)
            TO froid_runtime;

        -- 021: captação do site. Sem DELETE: o descadastro marca opt_out_at
        -- em vez de apagar, para que o pedido de oposição fique registrado.
        GRANT SELECT, INSERT, UPDATE ON marketing_leads TO froid_runtime;

    END IF;
END
$$;

INSERT INTO schema_migrations (version)
VALUES ('022_runtime_grants_validation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
