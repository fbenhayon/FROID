# Data-FROID — Fase 1: cada corte com a sua fala e o seu tema

Desenho de 02/10/2026, lido contra o código em `main` (`f1f0b0db` + piso de
coorte). Objetivo do dono: cada corte do acervo representa **um assunto
tratado**, com **tema registrado**, para que o FROID Explica consulte por tema e
devolva ao profissional o que foi feito em situações análogas.

Esta fase só conserta o que já devia funcionar. Ela não liga a fala do
profissional (Fase 2), não cria a síntese do paciente (Fase 3) nem a busca por
tema (Fase 4).

## Decisões do dono

| Decisão | Data |
|---|---|
| Piso de coorte: **bloqueia abaixo de 7** (7 passa, 6 não) | DECIDIDO em 02/10/2026 |
| Tema livre (sem lista fixa), mas **desidentificado** antes de entrar | DECIDIDO em 02/10/2026 |
| Paciente entra como **síntese da questão**, nunca literal (Fase 3) | DECIDIDO em 02/10/2026 |
| Base legal do acervo: legítimo interesse sobre dado anonimizado (`lgpd_registry.py:117`) — registro e política serão reescritos na Fase 2 | DECIDIDO em 02/10/2026 |

## O que está quebrado hoje, com endereço

**D1 — o recorte por tempo não recorta.** `_transcript_for_range`
(`froid-server/main.py`, logo após `_summary_for_cut`) ignora `start_second` e
`end_second` e devolve a transcrição inteira. Cada corte recebe a fala da sessão
toda: contagens de palavras, `speech_density` e a categoria de intervenção são
da sessão, repetidas em todos os cortes. A causa: o relatório arquivado só tem
`transcript` (linhas unidas por `\n`), sem tempo — `LiveSession.tsx`, montagem
do relatório, `transcript: summarySourceTranscript`.

O navegador **tem** o tempo: cada linha nasce de um `transcriptSegmentsRef`
com `elapsedSeconds` (`appendTranscriptText`), e `transcript` é exatamente
`segments.map(s => s.text).join("\n")` — uma linha por segmento, porque
`appendTranscriptText` colapsa todo espaço em branco e nenhum texto contém
`\n`. O próprio navegador já recorta certo, com a regra
`start <= elapsedSeconds < end` (`collectTranscript`, `buildAnonymizedContext`).

**D2 — o tema não chega.** Três problemas somados:

1. `_anonymous_category` só aceita rótulos cujas palavras estejam numa lista de
   ~120 termos. O tema da IA é livre por contrato (`summary_prompt`: "must not
   come from a predefined list") e quase sempre cai em `nao_classificado`.
2. A coluna `theme` do corte recebe `cut.theme`, que **não é o tema da IA**: é
   `inferThemeFromTranscript`, as seis palavras mais frequentes da fala — que
   podem incluir nomes próprios minúsculos. O tema da IA vem em
   `conversationSummaries[].theme` e em `anonymizedContext.cuts[].themePredominant`.
3. `_summary_for_cut` é chamado e o resultado nunca é lido (`summary = ...`
   sem uso). E casa por minuto com `round`, enquanto o navegador casa com
   `ceil` — divergiriam se alguém passasse a ler.

**D3 — rótulos do próprio sistema descartados.** O mesmo filtro troca valores
legítimos que o código emite: `piora` e `sem_historico` → `nao_apurado`;
`oscilante` → `nao_apurada`; `primeira_sessao` → `seguimento` (afirmação falsa);
`remote`/`presential`/`presential_mobile` → `unknown`;
`sem_atribuicao_de_falante` → `intervencao_geral`. Só os rótulos favoráveis
sobrevivem — o acervo fica enviesado para melhora.

**D4 — o classificador corrigido nunca roda.** O servidor prefere
`cut_context.interventionCategory`, que o navegador sempre envia, calculado por
`inferInterventionCategory` (`LiveSession.tsx`) — a versão antiga, com
substring sem fronteira (`"como"` casa *comodidade*), indício de uma palavra
valendo ponto e empate decidido pela ordem da lista. `_infer_intervention_category`
no servidor, que corrigiu os três, só roda quando o navegador não manda nada.

**D5 — fala literal fora da criptografia.** `buildAnonymizedContext` envia, por
corte, `patientSummaryAnon` (até 80 palavras **literais** do paciente) e
`professionalSummaryAnon`, com limpeza mínima (`anonymizeForResearch`: só
e-mail, CPF, telefone, número). Esse objeto é gravado no relatório **em claro**:
`_save_session_reports` criptografa só o campo `transcript`. O servidor nunca
lê esses dois campos. Resultado: trechos literais do paciente vivem fora da
criptografia do prontuário (arquivo JSON e espelho PostgreSQL), sem leitor.

## O que muda

### Navegador (`LiveSession.tsx`)
- Relatório ganha `transcriptLineSeconds: number[]`, alinhado 1:1 com as linhas
  de `transcript` (o `elapsedSeconds` de cada segmento). Só números — nenhum
  texto novo sai do navegador.
- `anonymizedContext.cuts[]` **deixa de enviar** `patientSummaryAnon`,
  `professionalSummaryAnon` e `interventionCategory` (D4, D5).

### Servidor (`main.py`)
- `_transcript_for_range` recorta pela linha do tempo, com a mesma regra do
  navegador. Linha do tempo ausente ou desalinhada (relatório antigo, ou
  `len(linhas) != len(segundos)`) → **sem recorte**: devolve `None`, e o corte
  grava contagens e densidade como `NULL` e `transcript_scope =
  'sem_linha_do_tempo'`. Nunca a sessão inteira, nunca zero.
- Nova coluna `transcript_scope` em `anonymous_session_cuts`: `corte` |
  `sem_linha_do_tempo`.
- Categoria de intervenção: sempre `_infer_intervention_category` sobre a fala
  `DR.` **do corte**; sem recorte → `sem_recorte_temporal`.
- Tema: `theme_predominant` passa a ser o tema da IA do corte
  (`conversationSummaries`, casado por segundo, com recuo para
  `themePredominant`), desidentificado. `theme` (palavras frequentes) e
  `summary_theme` também passam pela desidentificação. Novas colunas
  `theme_deid_reason` (corte) e `summary_theme_deid_reason` (sessão).
- `_anonymous_category` passa a conhecer os rótulos que o próprio sistema
  emite (D3), por tabela explícita testada contra as fontes.

### Desidentificação do tema (`froid_deidentify.py`)
`desidentificar_tema(tema, transcricao)` → `(tema_seguro, motivo)`:
1. Padrões estruturados (link, e-mail, documento, CEP, telefone, data, hora,
   valor, número) → marcador.
2. Mês ou dia da semana por extenso → `[DATA]`.
3. **Nomes vistos na sessão**: palavra que aparece com maiúscula no meio de
   período na transcrição (nome próprio dito em voz alta) vira `[NOME]` no tema
   em qualquer posição e qualquer caixa. É isto que pega "conflito com joana" na
   lista de palavras frequentes, e "Joana e o divórcio" no começo do tema.
4. Palavra com maiúscula fora da primeira posição → `[NOME]`.
5. Recusa (tema vazio + motivo) quando: vazio; mais de 12 palavras (não é tema,
   é frase); marcadores acima de metade das palavras; nada além de marcador.

Motivos: `ok`, `vazio`, `longo_demais`, `referencial_demais`.

## O que não entra (fronteira)
- `FROID_DATAMART_FALA_PROFISSIONAL` continua desligada.
- `patient_summary_anon` continua `""`.
- `dominant_theme` (vocabulário fixo das zonas) não muda.
- Relatórios **já gravados** continuam com os trechos literais em claro (D5).
  Limpá-los é operação sobre dado de produção e pede janela e decisão própria.
- Linhas antigas do acervo não são reprocessadas: as transcrições antigas não
  têm linha do tempo.

## Auditoria de 05/10/2026 (antes de subir)

Pedido do dono: auditoria minuciosa do algoritmo antes de qualquer deploy.
Lida contra o código commitado em `562e2945`. O que se achou e o que mudou:

**Segurança da consulta (o mais grave, pré-existente, agravado pela Fase 1).**
O caminho pergunta → LLM escreve SQL → DuckDB não exigia agregação, aceitava
`SELECT *` e aplicava o piso de 7 numa SEGUNDA consulta, também escrita pelo
LLM — `GROUP BY theme_predominant` com grupos de uma sessão passava inteiro.
Agora o SQL é lido pelo próprio DuckDB (`json_serialize_sql`): `*`, UNION e
coluna vedada (`professional_summary_anon`, `*_json`, `*_summary_anon`) são
barrados em qualquer nível; o SELECT de topo tem de trazer
`COUNT(DISTINCT session_hash)`, que vira **piso por linha** — linha com menos
de 7 sessões distintas some inteira e a quantidade suprimida é declarada.
`_validate_duckdb_select`, `_coluna_de_sessoes`, `_suprimir_abaixo_do_piso`.

**Desidentificação do tema — duas frestas.** (1) Nome que a sessão só escreveu
abrindo frase ("Marcos não ligou.") não entrava em `nomes`; (2) um único
deslize do transcritor em minúscula ("joana") bastava para liberar o nome.
Agora `vocabulario_da_sessao` CONTA cada palavra em três formas (maiúscula no
meio, maiúscula abrindo período, minúscula) e a maioria decide: `nomes`,
`iniciais`, `comuns`. Segunda leitura sobre o resultado (dígito, `@`, link
sobrando → recusa). `VERSAO_DEID = deid-v2`.

**Rótulos gravados errado.** `cut_trigger` dizia `automatico_10min` em corte
manual (o navegador ignorava `summary.trigger`); o último corte gravava
`*_after_intervention = 0` e `response_*_direction = estabilidade` porque se
comparava consigo mesmo (`nextReference = nextCut || cut`); `dominant_theme`
gravava `nao_classificado` em TODA linha (o nome da zona não passava na lista
de palavras) — agora é o rótulo derivado de `PERCEPTION_ZONES`.

**Tema = só o tema da IA.** `theme` recebia `cut.theme`, a bolsa das seis
palavras mais frequentes da fala dos DOIS lados — forma degradada da fala do
paciente. `theme` e `theme_predominant` passam a ser o mesmo valor (tema da IA
desidentificado); sem resumo da IA, vazio com `theme_deid_reason =
sem_resumo_da_ia`. O mesmo para `summary_theme`.

**Era do acervo.** `schema_version` sobe para `anonymous_datamart_v5`
(`VERSAO_DO_ACERVO`): as colunas por corte mudaram de significado. O prompt do
Explica cita as eras pelas constantes e ensina a filtrar por v5 ou
`transcript_scope = 'corte'`.

**Precisão temporal.** A fala era carimbada na CHEGADA do texto (bloco de 7 s
+ latência ≈ 10 s depois); passa a ser carimbada no segundo em que o bloco de
áudio começou a gravar (`startedAtSecond`). Vale para o Data-FROID e para o
resumo da IA de cada corte.

**Desempenho.** A ingestão corria dentro do laço de eventos (um worker só) e
disparava ~280 `PRAGMA table_info` por sessão; agora lê o esquema uma vez por
tabela e corre em `asyncio.to_thread` sob trava. `_sem_acento` com cache.
Medido: vocabulário de 585 mil caracteres em 0,18 s.

**Auditoria do acervo.** `tools/audit_data_froid_privacy.py` passa a reprovar
dígito, `@` ou endereço nas colunas de tema.

**Fica de fora (anotado, não mexido):** bloco de áudio descartado quando o
gravador para fora de segmento (`recorder.onstop`, caminho de reinício);
`ipmAvg || 0` no navegador; `patientResponse` do navegador ainda vence o do
servidor (os dois têm a mesma regra hoje); `cut_label` sempre `cut`;
relatórios antigos com trechos literais em claro.

## Como se prova
- Recorte: relatório com três cortes e falas em segundos distintos → cada corte
  conta só as suas palavras; sem `transcriptLineSeconds` → `NULL` +
  `sem_linha_do_tempo`; linha do tempo desalinhada → idem.
- Tema: nomes ditos na sessão saem do tema em qualquer posição; recusas gravam
  motivo; tema comum passa intacto.
- Rótulos: tabela de rótulos emitidos pelo navegador e pelo servidor,
  enumerada, cada um sobrevivendo ao filtro.
- Gravação real com `duckdb` (o teste existente é pulado sem ele), mais o
  teste estático que conta colunas × placeholders × valores do `INSERT`.
- Suíte inteira com `.venv-win`.
