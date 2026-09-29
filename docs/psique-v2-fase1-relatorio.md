# FROID Psique V2.1 — resultado da Fase 1

Data: 29/09/2026, America/Sao_Paulo.

**Resultado:** Fase 1 implementada e validada localmente nos testes específicos de Psique. A regressão ampliada não está integralmente verde: há falhas anteriores nos testes do NR-1, reproduzidas no estado anterior às alterações. Nenhuma dessas falhas foi corrigida dentro deste escopo. Não há autorização para considerar V2 completa, implantar em produção ou avançar às fases operacionais.

Referência: `C:/Users/Fabio/Downloads/FROID_Psique_Prompt_Final_VSCode_V2_1.md`, especialmente seções 50A e 59. O escopo autorizado é Psique em ambiente controlado. HEAD de referência: `a82e962a1c9e73803a5f08cd19183af125e0ddd7`. Não houve commit, push, deploy, migration em produção, alteração clínica ou operação Stripe LIVE durante a execução desta fase. Atualização de 29/09/2026: o proprietário autorizou o commit local, e esta entrega foi commitada separada da auditoria, da Fase 2A e do trabalho concorrente; push e produção permanecem não executados.

## O que foi implementado

1. **Leitura sem aplicação de migrations.** `TenantStore.ensure_schema()` agora verifica versões e informa ausências; não executa SQL de migration. O mecanismo compartilhado foi alterado apenas para separar a operação de schema, conforme a seção 50A. V1/NR-1 continuam exigindo seu schema legado; ausência das tabelas opcionais Psique V2 não bloqueia esses produtos.
2. **Comando explícito e auditável.** `tools/migrate_schema.py` planeja em modo somente leitura por padrão. Aplicação exige credencial dedicada, versão de destino e confirmação do nome do banco. O log registra hash, usuário, início/fim e sucesso/falha. Repetição não reaplica versões registradas; alteração de um arquivo já auditado é recusada.
3. **Catálogo separado.** Preços e créditos V2 estão em configuração própria, com validação no servidor, JSON canônico, SHA-256 e cálculo em centavos. A fórmula organizacional é pura; não produz cobrança, assentos ou permissão.
4. **Histórico protegido no banco.** Catálogo/ofertas têm validação do conteúdo, imutabilidade e RLS. A instalação é explícita e transacional. O catálogo permanece `draft`; todas as ofertas têm `public=false`.
5. **Estrutura mínima TEST.** Mapeamento Stripe e Purchase guardam conta/ambiente, versão/hash, valores e idempotência. O banco recusa LIVE, snapshot divergente e compra para organização `enterprise`/`legacy`. Purchase admite somente preparação/cancelamento; não concede créditos nem processa pagamento.

Não foram criados endpoints públicos, rotas V2, webhooks, trial novo, ledger V2, reserva clínica, papéis V2, agenda organizacional ou telas/site de preços. Não foram criados objetos Stripe reais. Os testes de mapeamento usam fixtures sintéticas declaradas.

## Migrations e catálogo

| Migration nova | Conteúdo |
|---|---|
| `035_psique_v2_pricing` | Tabelas de catálogo e ofertas, hash, vigência e imutabilidade |
| `036_psique_v2_purchases` | Mapeamentos Stripe TEST, Purchase, snapshot e idempotência |

O runner também cria `schema_migration_execution_log` como infraestrutura operacional de auditoria. As migrations antigas não foram modificadas. Não houve backfill nem transferência de saldo.

Catálogo instalado apenas no banco descartável: `FROID_PSIQUE_V2`, versão `2.1`, hash `39b0ba03b384c49ec57844bbfed6ef537c7a1ba97a13885599c447e6e74cd853`. A execução repetida da ferramenta de instalação retornou o mesmo identificador e manteve um único catálogo em rascunho.

## Validação executada

Ambiente: Windows, Python 3.13, psycopg 3.3.4 e PostgreSQL 16.15 local, ouvindo apenas em `127.0.0.1:55439`. Venv e cluster próprios em `.codex-tmp/`, sem uso da credencial do produto. O Docker local não ficou operacional; o PostgreSQL portátil permitiu os testes reais. As bases auxiliares dos testes foram removidas pelos próprios testes. Ao concluir, o PostgreSQL temporário foi encerrado e `pg_ctl status` confirmou que não havia servidor em execução. O Docker Desktop iniciado para a tentativa de testes também foi encerrado.

| Verificação | Resultado |
|---|---|
| Pricing Psique V2 | 10 testes aprovados |
| Integração Psique em PostgreSQL real | 9 testes aprovados |
| Verificação de schema sem escrita | 7 testes aprovados, incluídos também na regressão abaixo |
| Regressão selecionada V1/NR-1 e schema | 278 testes: 272 aprovados, 5 pulados e 1 teste com falhas em 10 subcasos |
| Suítes PostgreSQL NR-1 existentes | 21 testes: 18 aprovados, 1 com falha e 2 com erros em 25 subcasos |
| Ruff nos cinco módulos novos e três arquivos de teste novos | Aprovado |
| Mypy nos cinco módulos novos | Aprovado |
| TypeScript do painel, `tsc --noEmit` | Aprovado |
| `git diff --check` | Aprovado |

Os cinco casos pulados são de `ReportVisibilityStoreTests`, que dependem de uma base/fixtures legadas específicas. A execução da regressão sem banco não os habilitou. Eles não são contabilizados como aprovados. O teste novo de drift de `billing_type` foi adicionado à suíte existente, mantendo as verificações antigas.

As seguintes garantias foram exercitadas em PostgreSQL, e não apenas pela leitura dos SQL:

- Banco vazio: leitura informa schema ausente e não cria sequer `schema_migrations`.
- Banco até 034: `ensure_schema()` executa sob `default_transaction_read_only=on`, com 035/036 pendentes; leitura V2 recusa a ausência sem aplicar arquivos.
- Aplicação explícita: ordem completa, destino confirmado, registro de execução, repetição sem aplicação e detecção de hash alterado.
- Migration propositalmente inválida: rollback da tabela de teste e log `failed` com classe do erro.
- Catálogo: instalação idempotente, rascunho sem vigência operacional, recusa de alteração/exclusão e de hash/oferta incompatíveis.
- Compra: preço, créditos, moeda, hash, conta e ambiente coerentes; Checkout e idempotência únicos; snapshot imutável e cancelamento terminal.
- Isolamento: runtime sem privilégios nas quatro tabelas novas; RLS não expõe linhas mesmo sob grant de leitura temporário no teste.
- Preservação: comparação das estruturas, funções, políticas, privilégios e gatilhos legados antes/depois de 035/036; saldo e ledger testemunhais intactos. Os novos gatilhos internos da FK de Purchase para organização foram verificados separadamente como a adição esperada.

## Falhas anteriores identificadas e reproduzidas

**Anexo comercial NR-1:** `test_o_anexo_por_porte_bate_com_o_motor` procura uma coluna adicional de anual com desconto de 15%. O anexo atual apresenta mensal, anual, respostas exigidas e caminho; a coluna de desconto não existe. Os valores mensal/anual apresentados nas dez linhas coincidem com os valores esperados exibidos pelo teste. A falha não demonstra, por si, um novo preço incorreto. O mesmo teste falhou nos dez subcasos com teste, motor e documento extraídos diretamente do HEAD anterior.

**Plano de ação NR-1:** `test_veredito_sem_data_de_revisao_e_recusado` espera o nome `psychosocial_action_plan_review_pairs_with_verdict`, mas o PostgreSQL rejeita a entrada por `psychosocial_action_plan_efficacy_after_implementation`. A entrada foi recusada; falhou a expectativa sobre qual restrição dispara. Reproduzido com migrations e teste do HEAD anterior, até 034.

**Representatividade NR-1:** `test_parametros_alternativos_batem` e `test_parametros_invalidos_levantam` produziram 25 erros `UndefinedFunction`. Nesses subcasos, o driver envia valores de ponto flutuante para uma função cuja assinatura usa `numeric`, sem cast correspondente na chamada do teste. Os mesmos 25 erros foram reproduzidos com os arquivos e migrations do HEAD anterior, sem 035/036.

As falhas foram mantidas visíveis. Não foram modificados testes NR-1 para torná-los verdes, preços NR-1, funções NR-1 ou o documento comercial. Não há evidência de regressão nova nesse conjunto executado, mas também não há uma suíte geral integralmente aprovada.

## Arquivos desta entrega

Existentes alterados:

- `.env.example`, `froid-server/.env.multitenant.example` e `docker-compose.yml`: autoaplicação desligada explicitamente.
- `froid-server/tenant_store.py`: verificação de schema sem executar migrations e distinção do schema V2 opcional.
- `froid-server/tests/test_enum_drift.py`: cobertura adicional do tipo de cobrança Psique, sem remover verificações.
- `docs/psique-v2-pre-implementacao.md`: aviso de registro histórico e links para o estado V2.1.

Arquivos novos de código/configuração/teste:

- `froid-server/froid_schema.py`
- `froid-server/psique_pricing.py`
- `froid-server/psique_catalog_store.py`
- `froid-server/config/psique_pricing_v2.json`
- `froid-server/tools/migrate_schema.py`
- `froid-server/tools/psique_pricing_catalog.py`
- `froid-server/migrations/035_psique_v2_pricing.sql`
- `froid-server/migrations/036_psique_v2_purchases.sql`
- `froid-server/tests/test_schema_read_only.py`
- `froid-server/tests/test_psique_pricing_v2.py`
- `froid-server/tests/test_psique_phase1_postgres.py`

Documentação nova:

- [Pricing](psique-pricing-v2.md)
- [Billing e decisões V2.1 para fases futuras](psique-billing-v2.md)
- [Stripe](psique-stripe-v2.md)
- [RBAC: escopo futuro](psique-rbac-v2.md)
- [Migração, execução explícita e retorno seguro](psique-migration-v1-v2.md)
- [Agenda: escopo futuro](psique-scheduling.md)
- Este relatório.

O trabalho concorrente já presente em `docs/memoria/`, nos gráficos e `LiveSession.tsx` do painel, em `froid_core.py`, `froid_dissonance.py` e `test_derivada_sem_referencia.py` foi preservado e não é atribuído a esta entrega. Não houve alterações próprias em `froid-site/` ou `froid-dashboard/`.

## Limites e próximo passo

A neutralização está implementada e testada **no código local**. A instância em produção não foi modificada nem revalidada nesta fase. A exigência operacional da seção 50A continua como pré-requisito de uma implantação futura: primeiro entregar somente a proteção contra autoaplicação, verificar o processo efetivo e só então considerar disponibilizar migrations V2. O procedimento está no documento de migração.

Os testes de Stripe desta fase não substituem homologação da API TEST real, pagamento ou webhook. A documentação de billing/RBAC/agenda distingue decisões futuras de funções entregues. As flags operacionais futuras não foram adicionadas sem consumidores. V1 segue sendo o caminho público.

Próximo passo proposto: revisar esta entrega e as ressalvas da validação antes de autorizar qualquer fase seguinte. Não alterar o NR-1 para solucionar as falhas antigas dentro da tarefa Psique. Não iniciar Trial/créditos/Stripe operacional/RBAC/agenda/website sem nova autorização, conforme a seção 59: “Aguardar nova aprovação antes de avançar”.
