# NR-1 — o que as fontes responderam e o que ainda falta

Revisado em 03/08/2026 contra as fontes oficiais fornecidas (Portaria MTE nº
1.419/2024 e sua retificação, Portaria MTE nº 765/2025, Guia de Fatores de
Riscos Psicossociais MTE 2025, Manual GRO/PGR MTE 2026, FAQ CGNOR/DSST/SIT,
cartilha Fecomércio-RS, material FIEG e o artigo da Rev. TST v. 92 n. 1).

**Atualizado em 21/08/2026.** Entre 04/08 e 21/08 o módulo resolveu quatro dos
cinco pendentes, e este documento tinha ficado para trás — descrevia como
bloqueio o que já estava em produção. A Parte 2 abaixo foi reescrita contra o
código, e não contra a versão anterior do texto.

A versão original deste documento pedia treze coisas. As fontes responderam
quase todas, e restaram cinco. **Hoje resta uma, e ela não depende de mim.**

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

### A. O instrumento **[resolvido em 04/08/2026 — por outro caminho]**

O COPSOQ III foi abandonado. Nenhuma das fontes traz itens de instrumento, e nem
poderia: o MTE **não indica metodologia**, e essa é uma resposta explícita e
repetida no Guia, na cartilha e no FAQ — a escolha e a justificativa técnica são
da organização. Esperar as planilhas do COPSOQ mantinha o módulo parado por um
banco de itens com risco de licença comercial.

Em vez disso foi escrito o **instrumento psicossocial FROID v1**, ancorado nos
13 perigos do Guia MTE 2025 e na ISO 45003, carregado como dado em
`migrations/015_nr1_instrument_froid_v1.sql`. As tabelas
(`assessment_instruments`, `assessment_dimensions`, `assessment_items`)
continuam sendo a fronteira: instrumento é dado, nunca código, e trocá-lo não
exige deploy.

Fica valendo a ressalva de origem: dimensões de **saúde e bem-estar** não viram
linha de inventário — são desfecho, não exposição, e a norma avalia condição de
trabalho.

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

O mecanismo já existe: `gro_risk_criteria` guarda magnitudes, faixas e matriz, e
`criteria_for_scale()` reescala para 3×3 ou 4×4. **O que continua faltando é o
seu aval sobre os números** — eles vão parar num documento que a fiscalização
lê, e hoje são proposta minha.

### C. Taxa de resposta mínima **[resolvido em 21/08/2026]**

Nenhuma fonte fixa taxa, e isso não mudou: a escolha do método é da organização.
O que a fiscalização cobra é **suficiência técnica** — que a metodologia seja
adequada à dimensão da empresa e tenha fundamentação sólida.

A decisão foi não inventar percentual. O piso passou a ser o **tamanho de
amostra para proporção com correção de população finita**, a 95% de confiança e
margem de 5 pontos, em p=0,5. Sendo fórmula publicada, entra no documento de
critérios de 1.5.4.4.2.2 como fundamentação verificável e afasta a alegação de
amostragem por conveniência.

| Efetivo | Respostas exigidas | |
|---|---|---|
| 3.000 | 341 | 11% |
| 1.000 | 278 | 28% |
| 300 | 169 | 56% |
| 150 | 109 | 73% |
| 100 | 80 | 80% |
| ≤ 97 | todas | censo |

A transição para censo acontece sozinha, e é onde o Guia MTE já dizia que
questionário não é o instrumento: em grupo pequeno o caminho é diálogo e
observação da atividade. **O produto de questionário não serve a toda empresa** —
agora o sistema diz isso em vez de fingir que serve.

Dois pontos que valem registro:

- **São dois portões, não um.** O piso de 50/10 protege anonimato; este protege
  representatividade. Ambos valem sempre e nenhum substitui o outro. Uma empresa
  de 3.000 com 200 respostas passa folgado no primeiro e reprova no segundo.
- **Efetivo não declarado bloqueia.** `target_headcount` aceitava zero por
  omissão, o que teria feito de "não declarar" o atalho para desligar o portão.
  Passou a ser condição de abertura da campanha, no banco.

Onde está: `migrations/025_representativeness_floor.sql` (autoridade),
`nr1_compliance.required_sample()` (espelho, para a tela explicar), testes em
`tests/test_nr1_representatividade.py`.

### D. Canal de cuidado individual **[resolvido]**

As fontes reforçaram o desenho por outro ângulo: o processo é preventivo e
coletivo, não rastreamento clínico individual — logo, **nenhum gatilho
automático** a partir da resposta.

O canal é campo da campanha (`support_channel_label`, `support_channel_detail`)
e a `013` recusa abrir coleta sem ele, no banco. Aparece ao final do
questionário, igual para todos, independente do que foi respondido.

### E. Base legal da LGPD **[resolvido em 05/08/2026]**

Definida como **cumprimento de obrigação legal** — art. 7º, II e, para dado
sensível, art. 11, II, "a". Não é consentimento: o colaborador é informado, não
consultado, porque a empresa tem obrigação legal de levantar estes riscos, e
pedir consentimento onde não há escolha real seria pior que não pedir.

Está em `froid-server/lgpd_registry.py`, que anexa a base legal ao aviso de
forma estrutural em vez de confiar no texto livre da empresa, e mantém o
cadastro de operações em forma citável para o RIPD.

---

## Parte 3 — documentos que eu ainda pediria

As dez fontes cobrem a norma e sua interpretação oficial com folga. Não preciso
de mais nada sobre a NR-1 em si. Os quatro itens abaixo não são sobre a norma:

1. **O aval sobre as magnitudes** (item B). É o único pendente restante, e é
   decisão sua ou da consultoria de SST — não há fonte que a responda. Um PGR
   real de empresa-cliente (item 4 abaixo) resolveria os dois de uma vez.
2. **Nota Técnica SEI nº 4655/2024/MTE** — citada no Guia, trata de avaliação
   psicossocial no contexto de exame de aptidão. Útil para eu firmar a fronteira
   entre o módulo corporativo e a trilha clínica do FROID, que é exatamente onde
   este produto pode escorregar.
3. **Orientação Técnica SIT nº 3/2023** — profissional responsável pela
   elaboração do PGR. Fecha a questão de quem assina.
4. **Um PGR real e anonimizado** de empresa-cliente, se houver. Vale mais que
   qualquer guia: mostra a matriz de risco que a consultoria dela já usa, e é
   contra ela que a nossa gradação precisa se alinhar (item B).
