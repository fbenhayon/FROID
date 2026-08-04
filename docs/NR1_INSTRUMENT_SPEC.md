# NR-1 — o que as fontes responderam e o que ainda falta

Revisado em 03/08/2026 contra as fontes oficiais fornecidas (Portaria MTE nº
1.419/2024 e sua retificação, Portaria MTE nº 765/2025, Guia de Fatores de
Riscos Psicossociais MTE 2025, Manual GRO/PGR MTE 2026, FAQ CGNOR/DSST/SIT,
cartilha Fecomércio-RS, material FIEG e o artigo da Rev. TST v. 92 n. 1).

A versão anterior deste documento pedia treze coisas. As fontes responderam
quase todas. **Restam três.**

---

## Parte 1 — respondido pelas fontes e já implementado

| Pergunta que eu tinha | Resposta na norma | Onde entrou no código |
|---|---|---|
| Como se calcula a severidade | 1.5.4.4.4: magnitude das possíveis lesões ou agravos. 1.5.4.4.4.1: havendo mais de uma consequência, seleciona-se a de maior magnitude | `severity_from_consequences()`, `worst_consequence()` |
| Como se calcula a probabilidade | 1.5.4.4.5.3: exigências da atividade de trabalho **e** eficácia das medidas de prevenção implementadas | `probability_from_exposure()` |
| Periodicidade de revisão | 1.5.4.4.6: 2 anos; 1.5.4.4.6.1: até 3 com sistema de gestão de SST certificado, mais 6 gatilhos de revisão antecipada | `gro_risk_criteria.review_interval_months`, `psychosocial_risk_inventory.review_trigger` |
| Campos obrigatórios do inventário | 1.5.7.3.2, alíneas “a” a “i” | migration 011, colunas do `psychosocial_risk_inventory` |
| Retenção dos dados | 1.5.7.3.3.1: histórico do inventário por no mínimo 20 anos | `psychosocial_risk_inventory_history.retain_until` + trigger |
| Prazos do plano de ação | 1.5.5.2.2: cronograma, responsáveis, formas de acompanhamento e aferição. Sem prazo máximo por nível de risco na norma | colunas `monitoring_method`, `result_measurement`, `implemented_at` |
| Hierarquia de medidas | 1.4.1 “g” e 1.5.5.1.2; Guia MTE prefere medidas que mudem a organização do trabalho às individuais/comportamentais | `MEASURE_HIERARCHY`, sem EPI |
| Responsável técnico | Não há profissional específico exigido. Responsabilidade é da organização; PGR assinado por responsável legal, por estabelecimento | `organization_units.unit_type='establishment'` + `cnpj` |
| Unidades de avaliação | FAQ: atividade, posto de trabalho, função, setor ou grupo similar de exposição | CHECK ampliado em `organization_units` |
| Prioridade do plano de ação | 1.5.5.2.1.1: o número de trabalhadores possivelmente atingidos **deve** aumentar a prioridade | `action_priority()` |
| Terceiro documento do PGR | 1.5.4.4.2.2: documento de critérios de severidade, probabilidade, níveis, classificação e decisão | tabela `gro_risk_criteria`, imutável após publicação |
| Participação dos trabalhadores | 1.5.3.3 a/b/c, obrigatória e documentada; ausência gera presunção de omissão patronal | `worker_participation_records` |

**Correção que preciso registrar:** eu havia afirmado que não existe evento de
eSocial para risco psicossocial e que a integração era inviável. Está errado nos
termos em que coloquei. A exigência real não é gerar S-2210/S-2220/S-2240 a
partir da coorte anônima — é que o inventário seja **coerente** com o que a
empresa já envia nesses eventos, sob pena de autuação por inconsistência de
dados, e o FAQ confirma que a fiscalização consulta dados do eSocial. A página
foi corrigida para dizer isso.

---

## Parte 2 — o que ainda falta

### A. O item bank do COPSOQ III **[continua bloqueando]**

Nenhuma das fontes traz itens de instrumento, e nem poderia: o MTE **não indica
metodologia**, e essa é uma resposta explícita e repetida no Guia, na cartilha e
no FAQ. A escolha e a justificativa técnica são da organização.

Continuo precisando de três planilhas — cabeçalho, dimensões e itens — nas
colunas já especificadas no schema (`assessment_instruments`,
`assessment_dimensions`, `assessment_items`). Especificamente:

1. Escala: mínimo, máximo e o rótulo de cada ponto. **Se o instrumento tiver
   blocos em escalas diferentes** (frequência e intensidade), me avise: o schema
   assume uma escala por instrumento.
2. Pontos de corte por dimensão: os valores publicados da versão brasileira, ou
   a regra de cálculo. Corte fixo da literatura é defensável em fiscalização;
   tercil da própria amostra é relativo e contestável.
3. Lista dos itens de pontuação invertida.
4. Licenciamento para uso comercial.

Uma coisa mudou: o **de-para dimensão → perigo** ficou mais fácil, porque agora
existe a listagem de 13 perigos do Guia MTE 2025 como alvo. Cada dimensão do
COPSOQ precisa apontar para um perigo dessa lista (ou para um perigo próprio,
justificado). O campo `hazard_label` existe para isso.

Fica valendo a ressalva: as dimensões de **saúde e bem-estar** do COPSOQ
provavelmente não devem virar linha de inventário — são desfecho, não exposição,
e a norma avalia condição de trabalho.

### B. Magnitude das consequências **[calibra — e agora é obrigatório documentar]**

`CONSEQUENCE_SEVERITY` em `nr1_compliance.py` atribui severidade 1-5 a cada
consequência (transtorno mental 4, DORT 3, fadiga 2, doença cardiovascular 5).
**Esses números são meus.** A norma exige que a gradação de severidade esteja
detalhada no documento de critérios — então eles vão parar num documento que a
fiscalização lê.

Isso vale para a matriz também: hoje uso 5×5 com cortes em 15/8/4. Se a
consultoria de SST das empresas-cliente trabalha com outra matriz, o risco
psicossocial vai aparecer em escala diferente dos riscos físicos no mesmo PGR —
e o Manual é explícito que as avaliações devem usar **as mesmas gradações** para
permitir gestão integrada.

Preciso do seu aval ou dos valores corretos.

### C. Taxa de resposta mínima **[continua em aberto]**

Nenhuma fonte fixa taxa. O piso de 50 respostas por campanha continua sendo
decisão nossa, não da norma. O risco que apontei permanece: uma empresa de 3.000
pessoas com 50 respostas cruza o piso e gera inventário sobre 1,7% do efetivo.

O Guia dá a direção certa por outro caminho: para empresas grandes o
questionário é adequado; para grupos pequenos, observação da atividade e diálogo
são mais apropriados, e o FAQ trata explicitamente de grupos de 1 ou 2 pessoas.
Ou seja, **o produto de questionário não serve a toda empresa**, e isso é
defensável — mas alguém precisa decidir a partir de que taxa o resultado é
representativo o bastante para virar inventário.

### D. Canal de cuidado individual **[continua bloqueando a coleta em produção]**

Segue de pé, e as fontes reforçam por outro ângulo: o processo é preventivo e
coletivo, não rastreamento clínico individual. Isso confirma que **não deve
haver gatilho automático** a partir da resposta.

Continua faltando definir o canal de apoio que aparece ao final do questionário,
aberto a todos e independente do que foi respondido, e o texto que o acompanha.

### E. Base legal da LGPD **[continua bloqueando]**

A cartilha e as considerações finais tratam do tema (finalidade, necessidade,
confidencialidade, segurança, restrição de acesso), mas nenhuma fonte define a
base legal. Continuo precisando da posição formal do DPO ou do jurídico, porque
ela muda o texto de abertura, o registro no ledger e o RIPD.

---

## Parte 3 — documentos que eu ainda pediria

As dez fontes cobrem a norma e sua interpretação oficial com folga. Não preciso
de mais nada sobre a NR-1 em si. Os quatro itens abaixo não são sobre a norma:

1. **O instrumento** (item A). É o único bloqueio técnico restante.
2. **Nota Técnica SEI nº 4655/2024/MTE** — citada no Guia, trata de avaliação
   psicossocial no contexto de exame de aptidão. Útil para eu firmar a fronteira
   entre o módulo corporativo e a trilha clínica do FROID, que é exatamente onde
   este produto pode escorregar.
3. **Orientação Técnica SIT nº 3/2023** — profissional responsável pela
   elaboração do PGR. Fecha a questão de quem assina.
4. **Um PGR real e anonimizado** de empresa-cliente, se houver. Vale mais que
   qualquer guia: mostra a matriz de risco que a consultoria dela já usa, e é
   contra ela que a nossa gradação precisa se alinhar (item B).
