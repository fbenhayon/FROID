-- Instrumento FROID NR-1 v1 — banco de itens.
--
-- Por que este instrumento e nao o COPSOQ III:
--
--   * O MTE nao define metodologia e o auditor-fiscal nao pode impor
--     ferramenta especifica. O que a norma exige e fundamentacao cientifica,
--     adequacao ao contexto, coerencia dos criterios e documentacao.
--   * Ancorar as dimensoes na propria listagem de perigos do Guia MTE 2025
--     mapeia um-para-um no que a fiscalizacao examina, sem precisar de um
--     de-para que alguem tenha de assinar.
--   * A ISO 45003:2021, citada nas referencias do Guia, e o orgao internacional
--     de SST que da embasamento a taxonomia.
--   * Nao ha risco de licenciamento comercial.
--
-- LIMITE QUE PRECISA ESTAR ESCRITO: este instrumento nao possui validacao
-- psicometrica publicada. Ele e defensavel para a NR-1 porque a norma julga o
-- processo, nao o certificado do instrumento — mas a organizacao que o adotar
-- deve registrar essa escolha nos seus criterios do GRO, e o estudo de
-- validacao segue no roteiro.
--
-- REGRA QUE GOVERNA CADA ITEM: pergunta-se sobre a CONDICAO DE TRABALHO, nunca
-- sobre sintoma, sensacao ou saude do respondente. O Guia MTE e explicito:
-- "Nao se trata de verificar sintomas individuais (...) mas de se verificar as
-- condicoes de trabalho a que ele esta submetido." Item que pergunte "voce tem
-- se sentido ansioso" esta fora do escopo do GRO e nao entra aqui.
--
-- Polaridade: dimensao 'risk' e redigida como demanda (quanto mais, pior);
-- dimensao 'protective' e redigida como recurso (quanto mais, melhor). Os
-- cortes acompanham: em recurso, o favoravel fica ACIMA do critico.

BEGIN;

-- ---------------------------------------------------------------------------
-- Cabecalho
-- ---------------------------------------------------------------------------
INSERT INTO assessment_instruments
    (id, code, version, title, language, scale_min, scale_max, scale_labels,
     source_reference, status, published_at)
VALUES (
    md5('froid-nr1-psicossocial|1.0')::uuid,
    'froid-nr1-psicossocial',
    '1.0',
    'FROID NR-1 — Fatores de risco psicossociais relacionados ao trabalho',
    'pt-BR',
    1, 5,
    '["Nunca","Raramente","Às vezes","Frequentemente","Sempre"]'::jsonb,
    'Dimensoes ancoradas na listagem exemplificativa do Guia de informacoes '
    'sobre os Fatores de Riscos Psicossociais Relacionados ao Trabalho '
    '(MTE, 2025), com embasamento na ISO 45003:2021. Sem validacao '
    'psicometrica publicada; escolha a ser justificada nos criterios do GRO '
    'da organizacao, conforme NR-1 subitem 1.5.4.4.2.2.',
    'published',
    now()
)
ON CONFLICT (code, version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Dimensoes: os 13 perigos do Guia MTE, distribuidos nos quatro grupos de
-- fatores, com a consequencia possivel que a propria tabela do Guia indica.
-- ---------------------------------------------------------------------------
INSERT INTO assessment_dimensions
    (id, instrument_id, code, title, nr1_factor, polarity,
     cut_favorable, cut_critical, display_order,
     hazard_label, hazard_sources, consequences)
SELECT
    md5('froid-nr1-psicossocial|1.0|' || dimension.code)::uuid,
    md5('froid-nr1-psicossocial|1.0')::uuid,
    dimension.code, dimension.title, dimension.nr1_factor, dimension.polarity,
    dimension.cut_favorable, dimension.cut_critical, dimension.display_order,
    dimension.hazard_label, dimension.hazard_sources, dimension.consequences
FROM (VALUES
    -- Gestao e organizacao do trabalho
    ('mudanca_organizacional', 'Gestão de mudanças', 'work_organization', 'risk', 2.0, 4.0, 1,
     'Má gestão de mudanças organizacionais',
     'Reestruturações, troca de liderança, mudança de processo ou de sistema conduzidas sem preparação nem comunicação.',
     ARRAY['transtorno_mental','dort']),
    ('clareza_papel', 'Clareza de papel e função', 'work_organization', 'protective', 4.0, 2.0, 2,
     'Baixa clareza de papel/função',
     'Atribuições indefinidas, ordens divergentes de mais de um superior, metas ambíguas.',
     ARRAY['transtorno_mental']),
    ('reconhecimento', 'Recompensas e reconhecimento', 'work_organization', 'protective', 4.0, 2.0, 3,
     'Baixas recompensas e reconhecimento',
     'Esforço não reconhecido, ausência de retorno sobre o trabalho entregue.',
     ARRAY['transtorno_mental']),
    ('suporte_social', 'Suporte e apoio no trabalho', 'work_organization', 'protective', 4.0, 2.0, 4,
     'Falta de suporte/apoio no trabalho',
     'Ausência de apoio da chefia ou dos colegas diante de dificuldade ou erro.',
     ARRAY['transtorno_mental']),
    ('autonomia', 'Controle e autonomia', 'work_organization', 'protective', 4.0, 2.0, 5,
     'Baixo controle no trabalho / falta de autonomia',
     'Ritmo, ordem e método de execução integralmente impostos, sem margem de decisão.',
     ARRAY['transtorno_mental','dort']),
    ('justica_organizacional', 'Justiça organizacional', 'work_organization', 'protective', 4.0, 2.0, 6,
     'Baixa justiça organizacional',
     'Critérios de promoção, escala e distribuição de tarefas percebidos como parciais ou opacos.',
     ARRAY['transtorno_mental']),

    -- Carga e demanda de trabalho
    ('sobrecarga', 'Excesso de demandas', 'workload_demand', 'risk', 2.0, 4.0, 7,
     'Excesso de demandas no trabalho (sobrecarga)',
     'Volume incompatível com a jornada, prazos simultâneos, interrupção de pausas, hiperconectividade fora do expediente.',
     ARRAY['transtorno_mental','dort']),
    ('subcarga', 'Subcarga e monotonia', 'workload_demand', 'risk', 2.0, 4.0, 8,
     'Baixa demanda no trabalho (subcarga)',
     'Tarefas repetitivas e sem desafio, ocupação abaixo da qualificação, tempo ocioso imposto.',
     ARRAY['transtorno_mental']),

    -- Assedio e violencia laboral
    ('assedio', 'Assédio', 'harassment_violence', 'risk', 1.5, 3.0, 9,
     'Assédio de qualquer natureza no trabalho',
     'Assédio moral, sexual ou institucional; humilhação, isolamento deliberado, exposição vexatória.',
     ARRAY['transtorno_mental','afastamento_prolongado']),
    ('violencia', 'Eventos violentos ou traumáticos', 'harassment_violence', 'risk', 1.5, 3.0, 10,
     'Eventos violentos ou traumáticos',
     'Agressão física ou verbal, ameaça, assalto, contato com situação traumática no exercício da função.',
     ARRAY['transtorno_mental','afastamento_prolongado']),
    ('relacoes', 'Relações no local de trabalho', 'harassment_violence', 'risk', 2.0, 4.0, 11,
     'Más relações no local de trabalho',
     'Conflitos recorrentes não mediados, clima hostil, competição predatória entre equipes.',
     ARRAY['transtorno_mental']),

    -- Ambiente e modalidade
    ('isolamento', 'Trabalho remoto e isolado', 'environment_modality', 'risk', 2.0, 4.0, 12,
     'Trabalho remoto e isolado',
     'Teletrabalho, turno solitário ou posto afastado, sem contato regular com equipe ou liderança.',
     ARRAY['transtorno_mental','fadiga']),
    ('comunicacao', 'Condições de comunicação', 'environment_modality', 'risk', 2.0, 4.0, 13,
     'Trabalho em condições de difícil comunicação',
     'Ruído, distância, barreira de idioma, ferramenta inadequada ou ausência de canal para pedir ajuda.',
     ARRAY['transtorno_mental'])
) AS dimension(code, title, nr1_factor, polarity, cut_favorable, cut_critical,
               display_order, hazard_label, hazard_sources, consequences)
ON CONFLICT (instrument_id, code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Itens. Tres por dimensao, 39 no total — cerca de sete minutos de resposta.
-- Nenhum item pergunta sobre sintoma, humor ou saude: todos perguntam sobre a
-- condicao de trabalho.
-- ---------------------------------------------------------------------------
INSERT INTO assessment_items
    (id, instrument_id, dimension_id, code, statement, reverse_scored, display_order)
SELECT
    md5('froid-nr1-psicossocial|1.0|item|' || item.code)::uuid,
    md5('froid-nr1-psicossocial|1.0')::uuid,
    md5('froid-nr1-psicossocial|1.0|' || item.dimension_code)::uuid,
    item.code, item.statement, false, item.display_order
FROM (VALUES
    ('mudanca_organizacional', 'mud_01', 'Mudanças no meu trabalho são anunciadas em cima da hora.', 1),
    ('mudanca_organizacional', 'mud_02', 'Sou informado do motivo das mudanças que afetam minha rotina.', 2),
    ('mudanca_organizacional', 'mud_03', 'Depois de uma mudança, fico sem saber como executar minha tarefa.', 3),

    ('clareza_papel', 'cla_01', 'Sei exatamente o que se espera de mim no meu cargo.', 1),
    ('clareza_papel', 'cla_02', 'As metas que recebo são claras e compatíveis entre si.', 2),
    ('clareza_papel', 'cla_03', 'Recebo ordens que não se contradizem entre diferentes chefias.', 3),

    ('reconhecimento', 'rec_01', 'Meu esforço no trabalho é reconhecido por quem me lidera.', 1),
    ('reconhecimento', 'rec_02', 'Recebo retorno sobre a qualidade do que entrego.', 2),
    ('reconhecimento', 'rec_03', 'O que faço é considerado importante para a organização.', 3),

    ('suporte_social', 'sup_01', 'Posso contar com minha chefia quando o trabalho fica difícil.', 1),
    ('suporte_social', 'sup_02', 'Meus colegas me ajudam quando preciso.', 2),
    ('suporte_social', 'sup_03', 'Consigo pedir ajuda sem receio de ser mal visto.', 3),

    ('autonomia', 'aut_01', 'Posso decidir a ordem em que executo minhas tarefas.', 1),
    ('autonomia', 'aut_02', 'Tenho influência sobre o ritmo do meu trabalho.', 2),
    ('autonomia', 'aut_03', 'Minha opinião é considerada em decisões que afetam meu trabalho.', 3),

    ('justica_organizacional', 'jus_01', 'As regras de distribuição de tarefas são aplicadas de forma igual para todos.', 1),
    ('justica_organizacional', 'jus_02', 'Os critérios de escala, folga e férias são transparentes.', 2),
    ('justica_organizacional', 'jus_03', 'Situações de conflito são tratadas com imparcialidade.', 3),

    ('sobrecarga', 'sob_01', 'Preciso trabalhar em ritmo acelerado para dar conta das minhas tarefas.', 1),
    ('sobrecarga', 'sob_02', 'Deixo de fazer pausas ou de tirar o intervalo por causa do volume de trabalho.', 2),
    ('sobrecarga', 'sob_03', 'Sou acionado sobre trabalho fora do meu horário de expediente.', 3),

    ('subcarga', 'sub_01', 'Passo parte da jornada sem ter o que fazer.', 1),
    ('subcarga', 'sub_02', 'Minhas tarefas são repetitivas e não exigem o que sei fazer.', 2),
    ('subcarga', 'sub_03', 'Executo trabalho abaixo da minha qualificação.', 3),

    ('assedio', 'ass_01', 'Presencio ou sofro humilhação, deboche ou exposição no ambiente de trabalho.', 1),
    ('assedio', 'ass_02', 'Alguém é isolado ou tem trabalho retirado como forma de punição informal.', 2),
    ('assedio', 'ass_03', 'Ocorrem comentários ou investidas de natureza sexual não desejadas.', 3),

    ('violencia', 'vio_01', 'Ocorrem agressões verbais no meu ambiente de trabalho.', 1),
    ('violencia', 'vio_02', 'Sofro ameaça ou intimidação no exercício da minha função.', 2),
    ('violencia', 'vio_03', 'Minha função me expõe a situações de violência vindas de fora da empresa.', 3),

    ('relacoes', 'rel_01', 'Existem conflitos entre pessoas que ninguém resolve.', 1),
    ('relacoes', 'rel_02', 'O clima entre as equipes atrapalha a execução do trabalho.', 2),
    ('relacoes', 'rel_03', 'A competição entre colegas prejudica a colaboração.', 3),

    ('isolamento', 'iso_01', 'Trabalho sem contato com colegas durante a maior parte da jornada.', 1),
    ('isolamento', 'iso_02', 'Fico sem falar com minha liderança por vários dias seguidos.', 2),
    ('isolamento', 'iso_03', 'Quando trabalho a distância, tenho dificuldade de acompanhar o que acontece na equipe.', 3),

    ('comunicacao', 'com_01', 'Tenho dificuldade de me comunicar com quem preciso para fazer meu trabalho.', 1),
    ('comunicacao', 'com_02', 'As informações que preciso chegam incompletas ou atrasadas.', 2),
    ('comunicacao', 'com_03', 'Não tenho um canal claro para pedir ajuda quando algo dá errado.', 3)
) AS item(dimension_code, code, statement, display_order)
ON CONFLICT (instrument_id, code) DO NOTHING;

INSERT INTO schema_migrations (version)
VALUES ('015_nr1_instrument_froid_v1')
ON CONFLICT (version) DO NOTHING;

COMMIT;
