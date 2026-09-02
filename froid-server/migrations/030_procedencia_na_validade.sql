-- Um par de validade so vale se o lado do FROID tiver sido MEDIDO.
--
-- O QUE ESTAVA ERRADO
--
-- A funcao froid_validation_pairs ja filtrava por qualidade de aquisicao, e o
-- comentario dela enuncia o principio certo: "a window the clinician is told
-- not to trust must not silently become evidence". Os pisos eram cobertura
-- >= 0.80 e confianca >= 0.70.
--
-- Em 02/09/2026 apareceu uma dimensao que esses dois pisos nao alcancam. Uma
-- sessao real de 24 minutos rodou inteira com o motor em modo SIMULADO: o
-- audio do paciente nunca chegou, e o motor gerou os indices acusticos em vez
-- de medi-los. O detalhe que importa aqui e este: dado simulado tem cobertura
-- e confianca EXCELENTES, porque e gerado limpo. Os dois pisos existentes o
-- aprovariam sem hesitar.
--
-- O que a tela envia como `prosodic_activation` e o IPM medio da sessao. Numa
-- sessao simulada isso e um numero que o sistema inventou. Pareado com um
-- PHQ-9 verdadeiro, ele produz um coeficiente, um intervalo e um grafico — e
-- nada por tras. E o modo de falha mais caro possivel para um estudo de
-- validade: quanto mais dado se acumulasse, mais convincente ficaria o erro.
--
-- O QUE MUDA
--
-- A observacao passa a carregar a fracao das amostras da sessao que foram
-- medidas sobre a voz real do paciente, e a funcao de pares exige essa fracao.
--
-- O piso e 0.80, o mesmo da cobertura — nao por analogia estetica, mas porque
-- responde a mesma pergunta: quanto da janela e leitura de verdade. O valor
-- e uma decisao de protocolo e pode ser revisto por quem assina o estudo;
-- esta aqui, num lugar so, para que revisa-lo seja uma linha e nao uma cacada.
--
-- NULL fica de fora, e isso e deliberado. NULL significa "coletado antes de a
-- procedencia existir", ou seja, procedencia DESCONHECIDA — exatamente o caso
-- que pode ter sido simulado. Os outros dois filtros tratam NULL como
-- permissivo porque ali a ausencia era ruido de instrumentacao; aqui a
-- ausencia e a duvida inteira. Incluir por omissao seria repetir o defeito
-- que esta migration existe para fechar.

BEGIN;

ALTER TABLE validation_observations
    ADD COLUMN IF NOT EXISTS voice_measured_ratio NUMERIC;

COMMENT ON COLUMN validation_observations.voice_measured_ratio IS
    'Fracao das amostras da sessao medidas sobre voz real do paciente '
    '(0.0 a 1.0). NULL = procedencia desconhecida, e excluida dos pares.';

-- Mesma assinatura, mesmo contrato: so o filtro cresce.
CREATE OR REPLACE FUNCTION froid_validation_pairs(
    p_pattern_key TEXT,
    p_instrument_code TEXT
)
RETURNS TABLE (pattern_value NUMERIC, instrument_score NUMERIC)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT o.pattern_value, a.total_score
    FROM validation_observations o
    JOIN validation_administrations a ON a.id = o.administration_id
    JOIN validation_instruments i ON i.id = a.instrument_id
    WHERE o.pattern_key = p_pattern_key
      AND i.code = p_instrument_code
      AND a.research_consent = TRUE
      AND (o.coverage IS NULL OR o.coverage >= 0.80)
      AND (o.confidence IS NULL OR o.confidence >= 0.70)
      -- Sem OR ... IS NULL: procedencia desconhecida nao entra.
      AND o.voice_measured_ratio >= 0.80;
$$;

INSERT INTO schema_migrations (version)
VALUES ('030_procedencia_na_validade')
ON CONFLICT (version) DO NOTHING;

COMMIT;
