# Revisao do codigo de 15 a 19/10/2026, antes da fase 5 (Data-FROID)

Pedido do dono em 20/10/2026: rever os procedimentos entregues nesta semana
(commits 7db3fc80..79dd920a) e achar formas de melhorar o codigo. Dois
revisores independentes leram o diff (servidor e painel) e a autora fez a
propria passagem. Achados verificados contra o codigo; cada item diz onde,
o que falha e a correcao. Ordem: do que fere uma regra da casa ou um
usuario ao que so custa dinheiro ou tempo.

## Grupo 1 — corrigir antes de qualquer coisa (regra da casa ou acesso)

Feito em 20/10/2026 (itens 1 a 9, mais o 15 que caiu junto): migration 054
(cobranca conta sem recusar; nome so dos pacientes do clinico, `names_scope`),
`tenant_store.member_quota` levanta sem DSN, cortes sem instante declaram a
ausencia, instrucao sem FERRAMENTAS para Gemini/OpenAI e `tool_choice: none`
no teto de turnos, agenda em `FUSO_PADRAO` com `limitesDaSemana`, reagendar
so sai da edicao com `applied`, botao Agenda por `papelNaAgenda`, agenda
interna so em organizacao `clinic`. Provado em PostgreSQL (Windows e Linux).

| # | Onde | O que falha | Correcao |
|---|---|---|---|
| 1 | `migrations/052` (RAISE na cobranca) + `main.py` portao | A cobranca ao arquivar RECUSA quando a cota ja passou (corrida de duas sessoes com 1 restante, ou cota reduzida depois). O relatorio fica `credit_charge=falhou` e a nova tentativa falha para sempre: nao debita, nao vira pendencia, nao conta. O docstring do portao promete o contrario. | Migration 054: copia da 052 sem o RAISE — a sessao que aconteceu sempre conta e debita; quem barra e so o portao de inicio. Reescrever o teste que hoje afirma o RAISE como garantia. |
| 2 | `migrations/053` `psique_v2_scheduling_patients` | Qualquer CLINICIAN recebe o nome de TODOS os pacientes ativos da organizacao, mesmo com visibilidade restrita. O papel V1 `professional` so le pacientes atribuidos. | Para CLINICIAN, listar com nome so os pacientes atribuidos a ele ou com atendimento dele; os demais com identificador curto. Teste negativo. |
| 3 | `AgendaInterna.tsx` reagendar | Reagendamento recusado (versao vencida, conflito) sai do modo edicao com o formulario cheio; o proximo clique CRIA um segundo atendimento. | So sair do modo edicao quando `applied`; na recusa manter, mostrar o motivo e recarregar a versao. |
| 4 | `AgendaInterna.tsx` fusos | Limites da semana e pre-preenchimento do reagendamento em hora local do navegador; grade em Sao Paulo. Navegador fora de SP muda o dia em silencio. | Tudo em `FUSO_PADRAO`: `diaNoFuso` no pre-preenchimento e `instanteDe(dia, "00:00", fuso)` nos limites. |
| 5 | `main.py` instrucao por motor | O bloco FERRAMENTAS vai tambem ao Gemini/OpenAI, que nao tem ferramentas e podem "consultar" em texto. E no teto de turnos a resposta sai vazia, descartando os turnos ja pagos. | Instrucao montada por motor; no teto, uma ultima chamada sem `tools`. |
| 6 | `explica_ferramentas.py` cortes sem instante | `startSecond` ausente vira 0 (regra 1.1: ausencia nunca vira zero). | Propagar None e declarar "instante nao registrado" na linha do corte. |
| 7 | `tenant_store.member_quota` | None para duas causas (sem cota / sem DSN de runtime): o portao libera sem log na segunda. | Levantar ou sentinela quando nao da para ler; o portao registra o motivo. |
| 8 | `Dashboard.tsx` botao Agenda | So owner/admin/supervisor V1 veem o botao; quem recebeu SECRETARY V2 nao tem porta. Concessao que ninguem consome. | Decidir o botao por `papelNaAgenda(capacidades).geral`. |
| 9 | `ProfessionalDashboardSummary.tsx` | Profissional solo le "esta clinica ainda nao ativou os papeis V2" e e mandado a uma tela que nao tem. | Para organizacao solo: nao renderizar, ou dizer que a agenda interna e da clinica. |

## Grupo 2 — estado, erro e uso real no painel

Feito em 20/10/2026 (itens 10 a 14 e 16): listas de clinicos e pacientes com
estado proprio (carregando, lida, falhou com motivo); so o 404 vira "agenda nao
ligada", o resto diz o que falhou; `PapeisV2` segura o botao ate recarregar,
limpa o aviso por acao e mostra o motivo das falhas; cancelamento inline com
motivo e sem clique duplo, status em portugues, botoes so em marcado e
confirmado; o clinico e reconhecido pelo `membership_id` que a rota de
capacidades passou a devolver; transcricao ao vivo e trecho da ferramenta
cortados em linhas inteiras, declarando as linhas omitidas.

| # | Onde | O que falha | Correcao |
|---|---|---|---|
| 10 | `AgendaInterna.tsx` listas | Falha de API ao listar clinicos/pacientes vira "Nenhum clinico" (indistinguivel de clinica vazia). | Estado "nao lido" com o motivo, separado de lista vazia. |
| 11 | `agenda-interna.ts` motivos | Qualquer `indisponivel` vira "agenda nao ligada no servidor"; `negado` descarta o motivo. | So 404/flag vira "nao ligada"; o resto "nao pode ser lida: motivo". |
| 12 | `PapeisV2.tsx` | Clique duplo inverte a concessao (`ocupado` libera antes de recarregar); `aviso` nunca limpa; falha de rede some ou fica "confirmando..." para sempre. | `ocupado` ate recarregar; limpar aviso por acao; renderizar o motivo nos estados de erro. |
| 13 | `AgendaInterna.tsx` cancelar | `window.confirm` bloqueante, sem guarda de clique duplo, motivo fixo "painel", codigo cru no erro; status em ingles; botoes em COMPLETED/NO_SHOW. | Confirmacao inline, botao desativado enquanto pende, `traduzirMotivo` nos tres ramos, dicionario de status, campo de motivo. |
| 14 | `AgendaInterna.tsx` clinico proprio | Reconhecido por igualdade de e-mail; alias ou e-mail ausente deixa o clinico sem agenda e sem causa. | Servidor devolve o `membership_id` proprio (capabilities); casar por id. |
| 15 | `AgendaInterna.tsx` `minutosDe` | Copia de `horaParaMinutos` sem o limite 23/59: "25:00" vira janela valida. | Importar o helper e apagar a copia. |
| 16 | `LiveSession.tsx` transcricao ao vivo | Corte por caracteres depois do carimbo: a primeira linha sai sem [mm:ss] enquanto o contexto afirma que todas tem. | Truncar por linhas inteiras e declarar linhas omitidas. Idem `explica_ferramentas.LIMITE_DO_TRECHO`. |

## Grupo 3 — custo e tempo

Feito em 20/10/2026 (itens 17 a 21): prompt como bloco com `cache_control`
(reenviado ate sete vezes por pergunta) e um cliente Anthropic por processo;
acervo lido uma vez por requisicao (`_relatorios_acessiveis_da_requisicao`),
transcricao decifrada so da sessao pedida (`_revelar_transcricao`, regra
unica com o carregador), convites indexados por sessao, leituras de disco
em `to_thread`; orcamento de tempo por pergunta (`FROID_EXPLICA_ORCAMENTO_S`,
240 s) e uma tentativa a menos no SDK; `effort` e piso de tokens por chamada
(SQL low/2k, narracao medium/4k, NR-1 4k, clinico inalterado); cortes do
Explica ao vivo em cache por estado dos cortes fechados. O cache do prompt
entre perguntas da mesma sessao exigiria mover o glossario (que depende da
pergunta) para depois da transcricao: decisao de produto, nao feita.

| # | Onde | O que custa | Correcao |
|---|---|---|---|
| 17 | `_claude_responde` | So a instrucao (~3,5k tokens) esta em cache; o prompt (ate ~100k caracteres) e reenviado a cada turno de ferramenta e a cada pergunta seguinte sobre a mesma sessao. | Prompt como bloco de texto com `cache_control`; cliente Anthropic de modulo, nao por chamada. Maior alavanca de custo: leitura de cache custa um vigesimo. |
| 18 | `_acervo_do_explica` + `transcricao_de` | Le o acervo inteiro do disco por pergunta, de novo em `_build_portfolio_summary`, e DECIFRA todas as transcricoes a cada chamada de `trecho_da_transcricao`; tudo sincrono dentro de corrotina. `_enrich_report_patient` varre os convites linearmente por relatorio. | Carregar o acervo uma vez por pergunta, em `to_thread`; decifrar so o relatorio pedido; indexar convites por sessao. |
| 19 | `_claude_responde` tempo | 90 s x 3 tentativas x ate 7 chamadas: pior caso de meia hora com a rota esperando. | Orcamento total por pergunta e `max_retries` menor dentro do laco. |
| 20 | `_claude_responde` esforco | O passo de SQL do Data-FROID e a narracao agregada usam `effort=high` e piso de 16k tokens. | `effort` por chamada (low no SQL); piso so no caminho clinico. |
| 21 | `LiveSession.getFroidExplicaContext` | `buildReportCuts` sobre todas as amostras a cada pergunta. | Cachear por numero de resumos e de amostras. |

## Grupo 4 — simplificacao, limpeza e testes

| # | Onde | O que | Correcao |
|---|---|---|---|
| 22 | `main.py` carteira | Com Claude ativo, a carteira ainda entra no prompt por palavra-gatilho enquanto as ferramentas entregam o mesmo. `_valor_medido` e `_fmt_carteira` sem uso. | Sem carteira no prompt quando ha acervo; apagar aliases. |
| 23 | `_claude_responde` | 130 linhas com o laco dentro. | Extrair `_laco_de_ferramentas`. |
| 24 | testes Psique | Harness copiado em tres arquivos (fase 4, supervisor, cota). | `tests/psique_harness.py` compartilhado. |
| 25 | `test_psique_scheduling_supervisor` espelho | Fontes fixas em 044/045: uma 054 que regravasse a funcao passaria despercebida. | Derivar a definicao corrente da ultima migration anterior que define cada funcao. |
| 26 | `registrar_notas_no_manifesto` | Grava caminho absoluto; `pacientes_do_profissional` conta "(sem id)" como paciente. | Caminho relativo a `knowledge/approved`; separar sessoes sem id. |
| 27 | testes que faltam | Fronteira de acesso de `_acervo_do_explica` (dois usuarios, um nao decifra o do outro); `AgendaInterna`/`PapeisV2` sem teste; `instanteDe` so com fuso sem horario de verao; `blocosDaResposta` com `**` em celula; `carimboDaOrganizacao` com `organization_type` ausente. | Escrever os cinco. |

## Ordem proposta

1. Grupo 1 inteiro (nove itens), com migration 054 e testes, numa janela.
2. Grupo 3, itens 17 e 18, porque mudam o custo por pergunta e o tempo de
   resposta antes de o Data-FROID acrescentar chamadas.
3. Grupo 2 e o resto do 3.
4. Grupo 4.
5. Fase 5, Data-FROID.

Decisoes do dono que os itens pedem: o item 1 confirma a leitura de
"sessao que aconteceu conta e debita, mesmo acima da cota"; o item 2 define
o que o clinico ve ao escolher paciente (so os seus, com nome; os outros por
identificador).
