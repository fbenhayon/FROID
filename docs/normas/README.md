# Fontes normativas da NR-1 psicossocial

Texto das normas que o módulo NR-1 implementa, guardado aqui para que qualquer
afirmação do produto possa ser conferida contra a fonte sem depender de busca na
internet — e para que o documento de critérios que a fiscalização lê cite o
subitem certo.

Importado em 21/08/2026 de `~/Desktop/lei nr-1/`, sem alteração de conteúdo. Os
arquivos são exportações em markdown dos PDF oficiais; a URL de origem está na
primeira linha de cada um. **Em caso de divergência prevalece o texto publicado
no Diário Oficial da União**, não estas cópias.

## O que é citável e o que não é

| pasta | o que é | pode citar ao cliente/auditor? |
|---|---|---|
| `primarias/` | texto da norma e publicações oficiais do MTE | **sim** |
| `secundarias/` | doutrina e material de entidades | com atribuição, como interpretação |

**O que foi deliberadamente deixado de fora.** No mesmo lote vieram dois
documentos — uma conversa exploratória com IA e um material promocional — que
afirmavam o que o FROID **não faz**: captação de biomarcadores de voz e face de
colaborador no onboarding corporativo, "mitigação de até 90% dos passivos
trabalhistas" e mapa de risco por colaborador. As três coisas contrariam a
decisão de produto de 04/08/2026 e, as duas últimas, a própria norma — cujo
objeto é a condição de trabalho, nunca a pessoa. Foram removidos do repositório
em 22/08/2026 a pedido do Fábio, para que ninguém os copie para uma proposta por
engano. Os originais seguem fora do projeto, em `~/Desktop/lei nr-1/`.

## Onde cada exigência está implementada

| subitem | o que exige | onde vive no FROID |
|---|---|---|
| 1.5.3.1.4 | psicossocial dentro do GRO | módulo inteiro |
| 1.5.3.2.1 | considerar condições de trabalho nos termos da NR-17 | `aep_assessments` (migration 012) |
| 1.5.3.3 | participação, consulta e comunicação | `worker_participation_records` (011) |
| 1.5.4.3.1 a–c | descrição do perigo, fontes, grupo exposto | `assessment_dimensions` (015) |
| 1.5.4.4.2.2 | documento de critérios de gradação | `gro_risk_criteria` (011) |
| 1.5.4.4.4 / .4.1 | severidade = magnitude da pior consequência | `worst_consequence()` |
| 1.5.4.4.5.3 | probabilidade = exigências da atividade + eficácia das medidas | `probability_from_exposure()` |
| 1.5.4.4.6 a–f | seis gatilhos de revisão | coluna `review_trigger` (011) |
| 1.5.4.4.6.1 | 3 anos com sistema de gestão de SST certificado | `has_certified_sst_system` + CHECK (011) |
| 1.5.5.1.2 | hierarquia das medidas | `MEASURE_HIERARCHY` — **ver ressalva** |
| 1.5.5.2.1.1 | nº de trabalhadores atingidos aumenta a prioridade | `action_priority()` |
| 1.5.5.2.2 | cronograma, responsáveis, acompanhamento, aferição | `psychosocial_action_plan` |
| 1.5.5.3.1 | registro da implementação | `implemented_at`, `evidence` |
| 1.5.5.3.2.1 | corrigir medida comprovadamente ineficaz | `requires_correction` (012) |
| 1.5.7.3.2 a–i | nove campos do inventário | `psychosocial_risk_inventory` (011) |
| 1.5.7.3.3.1 | histórico por 20 anos | `retain_until` + trigger que recusa DELETE |

**Ressalva sobre a hierarquia (1.5.5.1.2).** A norma manda priorizar proteção
coletiva e, quando ela não bastar, seguir: (a) medidas administrativas ou de
organização do trabalho; (b) **EPI**. O `MEASURE_HIERARCHY` do FROID acrescenta
`substitution` (que vem do Manual, não do texto) e substitui EPI por
`monitoring`. É decisão de produto defensável — não existe EPI contra a forma
como o trabalho é organizado, e o Guia MTE prefere medidas que mudem a
organização às individuais —, **mas é divergência do texto literal e precisa
estar escrita no documento de critérios**, senão um auditor que compare os dois
encontra sozinho.

## Três coisas que a norma NÃO diz, e que costumam ser afirmadas

1. **Não existe taxa mínima de resposta nem piso de coorte na NR-1.** Nenhum dos
   dois portões do FROID (50/10 de anonimato; amostra com correção de população
   finita) vem da norma. São escolha metodológica nossa, defensável sob a
   exigência de *suficiência técnica* — e por isso têm de estar no documento de
   critérios, com a fundamentação, e não apresentados como exigência legal.
2. **Não existe metodologia obrigatória.** O MTE é explícito nas duas fontes
   oficiais: não indica nem sugere ferramenta. A organização escolhe e justifica.
3. **Não existe prazo fixo para implementar a medida.** 1.5.5.2.2 exige
   *cronograma* com responsáveis — o prazo é da organização, dentro dos próprios
   critérios que ela documentou. O Quadro 5 do Manual traz prazos por nível de
   risco, mas explicitamente como *exemplo* a ser customizado.

## Datas

| data | o que é |
|---|---|
| 27/08/2024 | publicação da Portaria MTE nº 1.419 |
| 30/07/2025 | retificação no DOU — renumera 1.5.4.4.5.1 → **1.5.4.4.6.1** e 1.5.4.2.1.3 → 1.5.4.2.1.4 |
| 26/05/2026 | vigência plena (prorrogada pela Portaria MTE nº 765/2025) |
| **24/08/2026** | **fim dos 90 dias de dupla visita orientativa; a partir daí cabe auto de infração** |

O prazo de dupla visita consta da resposta da CGNOR/DSST/SIT reproduzida em
`primarias/cartilha-fecomercio-rs-com-FAQ-CGNOR.md`: nos 90 dias seguintes à
vigência a fiscalização *tende a priorizar* orientação e notificação, "sem
prejuízo da adoção de medidas administrativas nos casos aplicáveis". Não é
isenção — é prioridade declarada.
