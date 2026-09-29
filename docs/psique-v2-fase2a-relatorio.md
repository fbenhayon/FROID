# FROID Psique V2.1 — resultado da Fase 2A

Data: 29/09/2026, America/Sao_Paulo.

**Resultado:** núcleo de Trial, identidade de material e máquina de créditos implementado e validado localmente. Os 39 testes específicos passaram, incluindo concorrência em PostgreSQL real. A Fase 1 passou novamente. A regressão ampliada preserva uma falha anterior de NR-1 e cinco casos pulados, discriminados abaixo; não está integralmente verde.

A entrega contém um adaptador interno de processamento e recuperação. Não foi conectado às rotas públicas, onboarding ou WebSocket do produto. A validação usa fixtures sintéticas e não representa E2E com pacientes, motor clínico real, provedores reais de identidade ou Stripe. O caminho público permanece V1.

## Autorização e análise dos anexos

Foram lidos `C:/Users/Fabio/Downloads/FROID_Psique_Prompt_Fase_2A.md` e `C:/Users/Fabio/Downloads/FROID_Psique_Checklist_Aprovacao_V2.md`. O pedido de conferir e executar foi aplicado à autorização expressa do prompt: **exclusivamente Fase 2A local/homologação**. O checklist reconhece a Fase 1 como aprovada localmente e mantém produção pendente. Sua lista de fases futuras não autoriza executá-las.

O prompt é consistente com essa separação. As decisões operacionais adotadas foram: evoluir carteira/ledger existentes; manter saldo pago sem lotes; identificar a fonte pelo backend; cobrar somente após entrega durável; preservar reservas iniciadas antes do vencimento; compensar liberações/restores de Trial vencido na mesma transação; falhar fechado sem prova de identidade ou histórico. A execução por etapas e os pontos de aprovação estão no [checklist atualizado](psique-v2-checklist-execucao.md).

Não houve commit, push, deploy, publicação, acesso ao banco de produção ou chamada Stripe nesta fase. Não foram criados Product/Price TEST, webhook, LIVE, licença, RBAC V2, agenda ou FLEX.

## Base, pré-check e trabalho concorrente

HEAD de referência: `a82e962a1c9e73803a5f08cd19183af125e0ddd7`. A árvore já continha a implementação local da Fase 1 e trabalho de outra frente. Não foi atribuído a esta fase tudo o que aparece em `git status`.

Antes das migrations, foram conferidos HEAD, árvore, sequência existente, leitura/startup sem autoaplicação e manutenção do fluxo público V1. Os 26 testes da Fase 1 passaram nesse pré-check. Os números 037 e 038 foram verificados imediatamente antes da criação dos respectivos arquivos; não houve colisão nova.

Foram comparados SHA-256 antes/depois dos arquivos concorrentes abaixo, de `main.py`, `subscriptions.py`, `tenant_access.py` e das migrations preexistentes 001–036. Permaneceram intactos:

- `docs/memoria/MEMORY.md` e `docs/memoria/froid-derivadas-zeradas-decisao-adiada.md`;
- `froid-dashboard/src/components/indicators/RiskChart.tsx` e `SubharmonicChart.tsx`;
- `froid-dashboard/src/pages/LiveSession.tsx`;
- `froid-server/froid_core.py`, `froid_dissonance.py` e `tests/test_derivada_sem_referencia.py`.

Não houve edição própria do painel, site, política NR-1, preços NR-1 ou motor clínico. As migrations antigas com prefixos repetidos 010/011 foram preservadas; isso não é colisão criada nesta entrega.

## Migrations efetivas e estruturas

| Migration | Conteúdo |
|---|---|
| `037_psique_trial_credit_state` | Extensão de carteira/ledger; Trial, elegibilidade, fontes, tentativas e reservas; constraints, índices, imutabilidade e RLS |
| `038_psique_credit_commands` | Comando transacional com autorização, operações financeiras, entrega, leitura e reconciliação; grants restritos |

Ambas foram aplicadas pelo runner explícito em bancos filhos descartáveis criados pelos testes. A base local usada como ponto de conexão permaneceu até 036. A aplicação não concede créditos nem converte carteiras existentes. Não há auto-migration, backfill, nova wallet, `credit_grants`, `credit_lots` ou FIFO.

| Estrutura | Garantias principais |
|---|---|
| `organization_wallets` existente | `reserved_balance`, `credit_model`, saldo/reserva não negativos, reserva até o saldo, V2 compartilhada |
| `credit_ledger` existente | Versão explícita, deltas de reserva, fonte, reserva, origem do consumo, motivo; V1 preservada; histórico V2 imutável |
| `psique_trials` | Um por organização; dez créditos/336 horas ou inelegível sem benefício; contadores não negativos e limitados ao concedido |
| `psique_trial_eligibility` | HMAC/versão únicos; origem V1/V2; evidência histórica imutável que sobrevive ao encerramento da conta |
| `psique_analysis_sources` | UUID do backend; organização/material únicos; proprietário/sessão/tipo/hash imutáveis |
| `psique_analysis_attempts` | Fonte/execução únicas; uma tentativa em processamento por fonte; prazo e recibo de entrega coerentes |
| `psique_credit_reservations` | Uma reserva por tentativa e uma ativa por fonte; vínculo composto à organização/fonte/tentativa |

Índices únicos adicionais garantem um `CREDIT_CONSUMPTION` por fonte e um `CREDIT_RESTORE` por consumo original. O runtime não recebe escrita direta nas estruturas financeiras nem acesso às primitivas internas. A função pública de comando verifica contexto, vínculo ativo e papéis persistidos; seu `SECURITY DEFINER` usa search path fixo. O único grant novo de leitura direta é de versões em `schema_migrations`, sem conteúdo clínico. [Procedimento e limites dos privilégios](psique-migration-v1-v2.md).

## Máquina de estados e Trial

Saldo disponível é `balance - reserved_balance`. Reserva, consumo, liberação, restore, ajuste e expiração usam transação com lock da carteira. O relógio é consultado depois de adquirir o lock. Reserva não reduz saldo; aumenta o reservado. Consumo reduz ambos em um. Liberação reduz apenas a reserva. Restore incrementa saldo, referencia o consumo original e exige motivo/evidência, sem alterar o lançamento anterior.

Tentativas passam de `PROCESSING` a `DELIVERED` ou `FAILED`; reservas passam de `RESERVED` a `CONSUMED` ou `RELEASED`. Crédito consumido não retorna por release. Restore é operação distinta, uma vez por consumo. Cada evento financeiro grava auditoria.

Trial concede dez créditos por organização após e-mail verificado e consulta confirmada do histórico V1. Convidar membros não concede benefícios. E-mail normalizado conserva pontos e aliases. HMAC-SHA256 depende de segredo externo versionado: chave ausente, versão histórica ausente, identidade divergente ou histórico V1 não consultado bloqueiam a concessão. Benefício V1 comprovado registra inelegibilidade sem novo crédito. A retenção histórica não depende da existência posterior da conta.

Trial é reservado antes do pago. Seu vencimento é exatamente 336 horas após a concessão. Esgotamento impede nova reserva Trial; uma liberação/restore antes do prazo pode restituir a unidade gratuita válida. Ao vencer, expira somente o Trial livre. Compra sintética durante Trial foi testada sem Stripe: o saldo pago permanece após o vencimento.

Reserva Trial iniciada antes do prazo é honrada para a mesma tentativa depois do vencimento. Falha após o prazo produz `CREDIT_RELEASE` e `TRIAL_EXPIRATION` compensatório na mesma transação; restore após o prazo também expira a unidade restaurada atomicamente. Os testes verificam inclusive identidade transacional dos lançamentos compensatórios.

## Fonte, SHA-256 e entrega durável

`analysis_source_id` é UUID emitido no PostgreSQL e vinculado ao material autorizado por um carregador do backend. UUID enviado pelo navegador não prova propriedade. Organização e proprietário são revalidados nos comandos; fontes de outra organização ou outro profissional são recusadas.

O SHA-256 de arquivo é incremental sobre bytes originais fornecidos pelo carregador; não depende da divisão em chunks. Mudança de bytes na mesma identidade é recusada. No streaming, o hash fica `NULL`, explicitamente não apurado. Não foi adicionado manifesto avançado nem armazenamento de áudio bruto.

`AnalysisWorkflow.run()` confirma a reserva antes de chamar o processador. O processador deve entregar um relatório protegido e confirmar conclusão técnica/resultado mínimo. O backend persiste em `session_reports` com chave V2 própria, sem sobrescrever relatório V1; a tentativa guarda referência, timestamps e hash do resultado persistido.

Somente depois do commit da entrega e de sua leitura autorizada ocorre consumo. A transação de consumo confere novamente o relatório, proprietário, organização, não exclusão e hash correspondente. Resultado clinicamente inconclusivo pode ser entregue; ausência de resultado técnico não é sucesso. Transcrição aberta é recusada, e o produtor continua responsável pela proteção do restante do conteúdo clínico.

Crash antes de entrega deixa reserva recuperável pelo prazo explícito da execução. Crash após persistência permite liquidar sem refazer a análise e sem apagar relatório. Timeout, resposta repetida ou conclusão atrasada não duplicam cobrança. `heartbeat`, `reconcile` e `reconcile_pending` foram implementados; não foi instalado daemon de varredura.

Reanálise, reprocessamento, novo modelo e regeneração usam nova execução da mesma fonte e permanecem gratuitos, inclusive após restore e com saldo zero. Histórico/relatórios não dependem do gate de saldo. Quotas V1 não viram limite por profissional V2.

## Concorrência e testes executados

Ambiente: Windows, Python 3.13, psycopg 3.3.4, PostgreSQL 16.15 próprio em `127.0.0.1:55439`. Os testes criaram bancos descartáveis aleatórios; comandos da aplicação usaram `froid_runtime` sem SUPERUSER/BYPASSRLS. Chaves HMAC, identidades, materiais, pagamentos e relatórios dos testes são fixtures declaradamente sintéticas. Nenhuma credencial de produção foi usada.

| Verificação | Resultado desta fase |
|---|---|
| `pytest tests/test_psique_phase2a.py` | **39 aprovados**, sem skips; 3 unitários e 36 casos com PostgreSQL |
| Fase 1: pricing, integração PostgreSQL e schema sem escrita | **26 aprovados**, com 55 subtestes aprovados na execução final |
| Regressão selecionada V1/NR-1/schema | **279 testes: 273 aprovados, 5 pulados, 1 com falhas em 10 subcasos** |
| Guardas de enum/schema, incluídas na regressão | 14 aprovadas |
| Ruff: três módulos 2A, verificador de schema e testes 2A/integração Fase 1 | Aprovado |
| Mypy: três módulos 2A e verificador de schema | Aprovado, quatro arquivos |
| TypeScript | Não executado nesta fase: painel e contratos compartilhados não foram alterados |
| `git diff --check` | Aprovado |

Concorrência foi exercitada com threads sincronizadas e conexões independentes: último crédito disputado por dois workers; mesma fonte com execução igual/diferente; consumo contra liberação; expiração contra conclusão; restore duplicado; dupla concessão de Trial na mesma organização e em organizações diferentes. Retry após timeout e retomada depois de entrega confirmaram idempotência. Não foram usados mocks como substitutos do PostgreSQL.

Também passaram: Trial 10/14, histórico V1, e-mail não verificado, ausência/rotação de chave, encerramento de conta, organização compartilhada, consumo Trial primeiro, preservação de pago, compensação após vencimento, fonte imutável/cross-org, relatório inacessível sem cobrança, falha do processador, reconciliação preservando relatório, ajuste auditado, saldo não negativo, privilégio forjado negado e semântica real V1 com quota/idempotência preservadas.

**Encerramento e revalidação.** A sessão que produziu esta entrega foi interrompida na conferência final. A retomada de 29/09/2026 reexecutou a validação em um cluster PostgreSQL descartável recém-criado, com credencial própria e `froid_runtime` sem SUPERUSER/BYPASSRLS: 39 testes 2A aprovados sem skips; 26 da Fase 1 e 14 do guard de enum aprovados, com 59 subtestes; Ruff e `git diff --check` aprovados; Mypy sem problemas nos quatro módulos da entrega. Os links relativos dos onze documentos Psique V2 resolvem, e não há mojibake nos documentos novos. Os dois servidores de teste (portas 55439 e 55440) foram encerrados; `pg_ctl status` confirmou ausência de servidor em execução e nenhuma porta 5543x ficou escutando. Os SHA-256 dos onze arquivos protegidos do pré-check permaneceram idênticos após a retomada. Em seguida, o proprietário autorizou o commit local: a entrega foi commitada em 29/09/2026 em três commits cirúrgicos — auditoria de pré-implementação, Fase 1 e Fase 2A — sem nenhum arquivo do trabalho concorrente.

O teste de integração da Fase 1 passou a limitar sua contagem de auditoria ao destino 036 que ele próprio aplica; não passou a exigir migrations futuras. O guard de enum passou a reconhecer dígitos/maiúsculas e conferir os domínios novos. As garantias antigas não foram removidas ou enfraquecidas.

## Falhas anteriores e limites da regressão

`test_precos_nr1_espelhados.OsTotaisDERIVADOSTambemConferem.test_o_anexo_por_porte_bate_com_o_motor` continua falhando em dez subcasos: espera uma coluna de anual com desconto de 15% ausente no anexo. Essa falha foi reproduzida no HEAD anterior durante a Fase 1. Não houve alteração desses testes, documento comercial ou código de preços nesta fase. Os valores mensal/anual não foram reinterpretados para esconder a divergência.

Na revalidação, o Mypy com imports seguidos acusa um erro preexistente `var-annotated` em `tenant_access.py:158`. O arquivo está idêntico ao HEAD e não pertence a esta entrega; a correção fica para frente própria, conforme a regra de não corrigir falhas preexistentes dentro desta tarefa.

Cinco casos de `ReportVisibilityStoreTests` foram pulados na regressão sem `FROID_TEST_DATABASE_URL` e fixtures legadas. Não contam como aprovados. Os testes novos 2A usaram variável dedicada e tiveram PostgreSQL real.

As falhas anteriores de expectativa de constraint do plano de ação e de assinatura numérica de representatividade permanecem documentadas no [relatório da Fase 1](psique-v2-fase1-relatorio.md). Essas suítes PostgreSQL NR-1 não foram reexecutadas nesta fase; não se atribui resultado novo a elas. Não foi feita correção de NR-1 neste trabalho.

## Arquivos desta etapa

Novos:

- `froid-server/migrations/037_psique_trial_credit_state.sql`;
- `froid-server/migrations/038_psique_credit_commands.sql`;
- `froid-server/psique_identity.py`, `psique_credits.py` e `psique_analysis.py`;
- `froid-server/tests/test_psique_phase2a.py`;
- [Protocolo de Trial/créditos](psique-credits-v2.md), [checklist por fase](psique-v2-checklist-execucao.md) e este relatório.

Atualizados sobre a base local da Fase 1:

- `froid-server/froid_schema.py`: 037/038 opcionais para V1; serviço 2A exige sua presença sem aplicá-las;
- `froid-server/tests/test_psique_phase1_postgres.py`: contagem da auditoria conforme destino explícito;
- `froid-server/tests/test_enum_drift.py`: cobertura dos novos domínios;
- `.env.example`, `froid-server/.env.multitenant.example` e `docker-compose.yml`: configuração HMAC externa, vazia por padrão;
- [Billing](psique-billing-v2.md), [migração V1/V2](psique-migration-v1-v2.md) e aviso de estado no [registro histórico de pré-implementação](psique-v2-pre-implementacao.md).

`tenant_store.py`, catálogo, ferramentas e migrations 035/036 já pertenciam à Fase 1; não são implementação nova de créditos desta etapa. Os artefatos locais de teste em `.codex-tmp/` não são arquivos de produto.

## Riscos, decisões de implementação e pendências

1. **Integração pública não executada.** Foram entregues serviço e workflow internos, com provedores explícitos de identidade/material. Antes de uso real, ligar e homologar esses provedores com autenticação, histórico V1 e ingestão reais. Sem confirmação de histórico, não há Trial. Não há conversão automática de carteira V1 usada.
2. **Contrato clínico mínimo delegado ao produtor.** O núcleo valida prova estrutural e persistência; não inventa nem avalia conteúdo clínico. O pipeline real precisa comprovar o resultado mínimo contratado e relatório protegido. Não se afirma homologação clínica E2E.
3. **Reconciliação exige chamador.** Prazo, heartbeat e varredura precisam ser operados pelo worker/controlador. A rotina existe e foi testada, mas não há agendamento automático; reservas órfãs não devem ser ignoradas na homologação. Operação com vínculo encerrado precisa de procedimento autorizado, sem ampliar acesso automaticamente.
4. **Segredos e histórico.** Perder chave histórica bloqueia novas concessões. Proteger, versionar e conservar essas chaves fora do banco/repositório; preservar as evidências históricas de elegibilidade.
5. **Ativação e privilégios pendentes.** Validar Linux/runtime equivalente, owner/search path das funções, grants reais, acessos aos relatórios e o caminho público completo antes de piloto. Os papéis atuais validam esta fase; não substituem RBAC V2.
6. **Regressão parcial declarada.** Falhas antigas e skips não foram ocultados. Corrigir NR-1 exige frente própria, fora desta autorização.

Decisões técnicas além dos nomes sugeridos no prompt: `credit_model` separa explicitamente semânticas; `credits_expired` impede expiração repetida; prazo de execução é argumento obrigatório; relatório tem namespace V2; histórico é retido por HMAC versionado. O manifesto de streaming foi adiado conforme autorização. A ausência de integração pública é um limite deliberado e registrado, não uma declaração de que o produto V2 já está operacional.

## Proposta de Fase 2B e ponto de parada

A próxima fase proposta é Stripe **TEST** para os pacotes PRO, após nova autorização: rever esta entrega e prerequisites; conferir conta/ambiente e catálogo draft; criar Products/Prices TEST; implementar Checkout resolvendo preço/créditos no backend; conceder uma vez por pagamento confirmado, com idempotência evento/Checkout/Purchase; testar recusas, duplicatas, notificações assíncronas e separação V1/V2. Nenhuma dessas ações foi iniciada.

A seção 24 do prompt determina: “NÃO avance automaticamente para Stripe TEST operacional. Aguardar nova aprovação.” A execução termina na Fase 2A e entrega este relatório e checklist para revisão. O commit local foi autorizado e executado em 29/09/2026; produção, LIVE e push continuam pendentes de autorização própria.
