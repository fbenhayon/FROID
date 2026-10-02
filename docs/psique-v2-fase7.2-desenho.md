# Fase 7.2 — Religar o atendimento ao consumo V2 (desenho)

Escrito em 02/10/2026 após leitura do código exato. **Nada implementado ainda.**
Decisão D1 já tomada: preservar "entregar e acertar depois" (o registro clínico
nunca bloqueia por falta de saldo).

## Fronteira da 7.2 (o que entra e o que NÃO entra)
- **ENTRA:** unificar o *crédito consumido* ao atender — orgs com carteira
  `credit_model='psique_v2'` passam a descontar da carteira V2 ao salvar um
  relatório de sessão nova, com política A.
- **NÃO ENTRA (de propósito):** mudar *onde o relatório é armazenado*. Hoje o
  relatório vive no JSON (file-first, nunca se perde, provado em
  `test_credit_exhaustion_preserves_report`). Mover o armazenamento do prontuário
  para o PostgreSQL é uma camada de dados separada, grande e arriscada — fica
  fora da 7.2. A 7.2 unifica o **crédito**, não o **prontuário**.

## O ponto de religamento
Em `save_session_report` ([main.py:15194](../froid-server/main.py#L15194)), o
relatório é gravado no JSON e **depois** vem o consumo
([main.py:15277](../froid-server/main.py#L15277)). A mudança é só no consumo:
- Org com `credit_model='psique_v2'` → caminho V2 (novo).
- Org ainda em V1 → `_consume_session_credit` intocado, até a 7.3 migrá-la.

Esse caminho duplo é **temporário e explícito**, não permanente — some quando a
7.3 migrar todas as orgs para V2.

## A bifurcação (decisão sua): como o V2 cobra uma sessão

### Opção A — reaproveitar a máquina de análise (REGISTER_SOURCE→BEGIN→DELIVER→CONSUME)
A sessão vira uma "fonte"; o relatório (sem transcrição) vira o `protected_report`;
roda o `AnalysisWorkflow` existente.
- **A favor:** usa a máquina já provada; idempotência nativa "uma fonte = um
  consumo"; é a visão original do V2 ("sessão = análise").
- **Contra:** o DELIVER **também grava** o relatório no PostgreSQL → o prontuário
  passaria a existir em dois lugares (JSON + PG), com risco de divergência; exige
  separar transcrição do relatório e carregar bytes de fonte. Puxa, na prática,
  parte da mudança de armazenamento que dissemos ficar fora da 7.2.

### Opção B — comando enxuto novo no ledger V2 (recomendada)
Uma migration 047 acrescenta ao `psique_v2_credit_command` um ramo
`SESSION_CONSUMPTION`: cobra **1 crédito** de forma atômica por `session_id`
(idempotente), evento `ledger_version=2`, respeitando imutabilidade e os CHECKs.
- **A favor:** encaixa exato em "1 sessão = 1 crédito"; o prontuário continua no
  JSON (zero risco à camada clínica provada); mudança menor e mais auditável na
  máquina de dinheiro; tudo numa carteira, um ledger, uma fronteira SECURITY
  DEFINER — continua sendo **um sistema só**.
- **Contra:** adiciona um segundo *tipo* de consumo no V2 (sessão, além da
  análise) — mas no mesmo ledger/carteira, não é sistema paralelo.

> **Recomendação:** Opção B. Mantém o prontuário onde ele é seguro, cobra
> exatamente por sessão, e é a mudança mais contida na lógica de dinheiro.

## Política A (entregar e acertar depois) no V2
O ledger V2 é imutável e não-negativo (não dá para "gastar no vermelho"). Então,
quando a sessão é atendida sem saldo disponível:
1. O relatório já está salvo (JSON) — nunca se perde.
2. O comando registra um evento auditável de **pendência** (delta=0, marcando a
   sessão a descoberto) no próprio ledger V2 — não move o saldo, não bloqueia.
3. Quando entra crédito (compra/cortesia), uma **reconciliação** consome as
   pendências na ordem. Mesma política do V1, mas no ledger único do V2.

## Autorização (C6)
Hoje o save usa `reports.write` (RBAC V1). O comando V2 exige contexto GUC
(`app.organization_id`/`app.membership_id`) e papel (CLINICIAN no RBAC v2, ou
owner/administrator/professional sem ele). O caminho V2 fia esse contexto a
partir do `context` que o endpoint já resolve.

## Plano de implementação da 7.2 (após sua escolha A/B)
1. Migration 047 (se Opção B): ramo `SESSION_CONSUMPTION` + evento de pendência +
   reconciliação; espelho/teste byte-a-byte se gerado por transformação.
2. Serviço: método em `PsiqueCredits` (ou no executor) para a cobrança de sessão.
3. `material_loader` real (se Opção A) OU resolutor de `session_id` (se Opção B).
4. Religar `save_session_report`: roteamento por `credit_model`, política A,
   contexto RBAC/GUC. Preservar a invariante "relatório salvo antes, nunca
   descartado".
5. Testes novos (Fase 7.2) contra PostgreSQL descartável (Windows + Linux):
   cobra 1 por sessão nova; idempotência por session_id; esgotado → pendência,
   nunca bloqueia; reconciliação ao creditar; org V1 intocada.
6. Regressão completa + evidência + gate.

Nada em produção até o plano ser aprovado e a janela ser sua.

## Execução (02/10/2026) — implementada e testada, aguardando "commit"
Opção B realizada como uma **função nova e separada**, não um ramo no comando
grande (menor superfície, zero risco ao `psique_v2_credit_command` de 250 linhas):

- **`migrations/047_psique_session_consumption.sql`** — `psique_v2_session_charge(
  org, member, actor, session_id, note)` SECURITY DEFINER: valida GUC + membership
  ativo + papel (reusa o guarda de 042 pelo comando `SESSION_CHARGE` → CLINICIAN no
  RBAC v2, owner/admin/professional no legado), trava a carteira, expira trial,
  liquida pendências antigas em FIFO (`ORDER BY created_at,id`) enquanto houver
  saldo, e então cobra a sessão atual (`SESSION_CONSUMPTION` delta=-1, funding
  TRIAL-se-houver-senão-PAID) ou marca `SESSION_PENDING` (delta=0) sem bloquear.
  Idempotente por `session_id` (UNIQUE de 001). Dois eventos novos no CHECK de
  tipos e no contrato fechado `credit_ledger_version_semantics` (cópia verbatim de
  037 + duas linhas). `psique_v2_session_pending_total` conta a dívida aberta.
- **`psique_credits.PsiqueCredits.charge_session`** — serviço que fia o contexto
  (GUC `app.organization_id`/`app.membership_id`) e chama a função; nunca levanta
  por falta de saldo (devolve `pending`).
- **`tenant_store.organization_credit_model`** — leitura administrativa do
  `credit_model` da carteira (o runtime não tem SELECT direto na tabela).
- **`main.py`** — `save_session_report` roteia: org com `credit_model='psique_v2'`
  (e flag ligada) desconta pela máquina V2 (`_consume_session_credit_v2`); as demais
  seguem no V1 por-profissional, intocadas. Serviço dedicado `_psique_session_charger`
  **não depende do Stripe** (só o DSN de runtime), para que pagamento fora do ar
  jamais afete o registro clínico. Invariante preservada: relatório salvo antes,
  nunca descartado; falha de infraestrutura → 503 e o relatório permanece.

**Testes** (`tests/test_psique_phase7.py`, 12 casos contra PostgreSQL descartável):
cobra 1 por sessão nova; idempotência por `session_id`; sessões distintas custam 1
cada; esgotado → pendência que nunca bloqueia; pendência idempotente; reconciliação
FIFO ao creditar; crédito parcial liquida só o que cobre; clínico (professional)
cobra; carteira V1 recusada e intocada; `session_id` em branco recusado; contexto
divergente recusado (42501); `organization_credit_model` roteia V2/V1/ausência.
Regressão Psique completa: 173 verdes (a única falha é o flake de concorrência já
conhecido do outbox da Fase 4, alheio à 7.2). Ruff/mypy limpos nos módulos novos.

**Fora de teste automatizado (validar na homologação da janela):** o caminho ponta
a ponta de `save_session_report` (app completo + estado JSON) — a cola em `main.py`
é fina e espelha padrões existentes, mas o atendimento real da clínica demo deve ser
conferido na janela. **Nada em produção sem você colar/aprovar.**
