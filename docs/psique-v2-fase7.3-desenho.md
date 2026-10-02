# Fase 7.3 — Migrar os saldos V1 para a carteira única V2 (desenho)

Escrito em 02/10/2026 a partir de leitura do código exato (auditoria de
leitura). **Nada implementado ainda.** Este documento é para você aprovar o
gate e, antes disso, decidir os pontos marcados **DECISÃO** — eles mudam o que
o backfill faz. Continua valendo: nada em produção sem você colar/aprovar.

Pré-requisito: a 7.2 (religar o atendimento ao V2) está commitada (`e47e64ca`);
o deploy dela é a janela de [psique-v2-fase7.2-janela.md](psique-v2-fase7.2-janela.md).

---

## 1. O problema, em uma página

Hoje o saldo V1 de uma organização vive em **dois lugares**:

- **JSON por-profissional** (`PROFESSIONAL_PROFILES` em `identity_state.json`,
  [main.py:648-654](../froid-server/main.py#L648)) — é a **fonte autoritativa em
  produção** (modo `FROID_SHARED_CREDITS_MODE=off`). Campos: `trial_sessions`
  (cortesia, [main.py:14150](../froid-server/main.py#L14150)), `contracted_sessions`
  + `bonus_sessions` (comprado, [main.py:14145-14146](../froid-server/main.py#L14145)),
  `total_sessions`/`used_sessions`/`remaining_sessions`
  ([main.py:14155-14157](../froid-server/main.py#L14155)), e
  `session_credit_purchases` ([main.py:5733](../froid-server/main.py#L5733)) — a
  lista que marca **"já comprou alguma vez"**. Saldo por profissional =
  `max(0, total_sessions - used_sessions)` ([main.py:2485-2490](../froid-server/main.py#L2485)).
- **Pool Postgres** (`organization_wallets`, `credit_model='v1'`): o espelho dual
  grava a linha e soma o pool a **cada** `_save_identity_state`
  ([tenant_store.py:4482-4555](../froid-server/tenant_store.py#L4482)), mas o pool só
  é **autoridade de consumo** em `enforce`.

**Por que não dá para só chamar ENROLL:** o ENROLL do V2 exige carteira
**vazia** — `balance<>0` OU qualquer linha em `credit_ledger` dispara
`V1_WALLET_CONVERSION_NOT_AUTHORIZED`
([migration 038:88-89](../froid-server/migrations/038_psique_credit_commands.sql#L88)).
Como o espelho já criou o pool e gravou `migration_opening`, **quase nenhuma org
está "vazia"**. Foi exatamente o que a conta demo bateu; lá resolvemos com
DELETE do ledger v1 + carteira e ENROLL em seguida — caminho **destrutivo** que
apaga a trilha. Para a frota inteira isso não serve.

**Por que o migrador atual não basta:** `_contribute_legacy_balance` lê **só**
`remaining_sessions` e o colapsa num único `balance`
([tenant_store.py:4927](../froid-server/tenant_store.py#L4927)); `trial_sessions`
(cortesia) e `contracted+bonus` (comprado) ficam **indistinguíveis**, e
`session_credit_purchases` não viaja. A distinção "nunca comprou" — que governa
o bloqueio de início de sessão — **se perde**.

**O bloqueio de trial V1** (`_trial_blocks_new_session`,
[main.py:2431-2440](../froid-server/main.py#L2431)): impede **só o início** de uma
sessão nova, e **só** para conta que **nunca comprou** (`session_credit_purchases`
vazia, [main.py:2414-2416](../froid-server/main.py#L2414)) **e** esgotou a cortesia.
HTTP 402 em `/session/create` ([main.py:7889](../froid-server/main.py#L7889)) e
`/api/session-invites` ([main.py:7907](../froid-server/main.py#L7907)). **Não**
alcança o salvar relatório — de propósito. É proteção de receita (impede uso
grátis infinito), diferente da política A da 7.2 (que protege o relatório de uma
sessão **já em curso**).

---

## 2. A fronteira da 7.3 (o que entra e o que NÃO entra)

- **ENTRA:** um caminho **não destrutivo, idempotente e auditado** que leva cada
  organização para a carteira única V2 preservando o **saldo líquido** e a
  **trilha V1**; e a decisão sobre o que acontece com o bloqueio de trial.
- **NÃO ENTRA:** mudar o armazenamento do prontuário (como na 7.2) e unificar o
  **comércio** (isso é a 7.4). Ver o acoplamento 7.3↔7.4 na seção 5.

---

## 3. Mecanismo proposto: conversão no lugar, sem DELETE

Uma migration **048** acrescenta um comando SECURITY DEFINER
`psique_v2_backfill_from_v1(org, member, actor, net, pending_ids[], note)` que,
numa transação:

1. Trava a carteira; exige `credit_model='v1'`. Se já for `psique_v2`,
   **no-op** (idempotente por organização).
2. Valida `net` (inteiro ≥ 0) contra `wallet.balance` do pool — **recusa** se
   divergir além de uma tolerância (o pool é a soma espelhada de
   `remaining_sessions`; a ferramenta recomputa do JSON e passa o número).
3. Zera o número do pool e **vira** `credit_model='psique_v2'`,
   `authority='shared'` (a trilha v1 — `migration_opening` etc. — **permanece**
   como histórico; o gatilho de imutabilidade só barra *novas* linhas v1 sob
   carteira v2, e nenhuma será inserida: o espelho fica inerte quando
   `authority<>'legacy'`, [tenant_store.py:4528](../froid-server/tenant_store.py#L4528)).
4. Escreve o lançamento de abertura V2 de `+net` como **evento próprio**
   `V2_MIGRATION_OPENING` (delta>0, funding `PAID`, reason obrigatório),
   idempotente por `v2-backfill-opening:<org>`. Assim o saldo V2 fica explicado
   por um evento V2 auditável (o paralelo exato do `migration_opening` do V1),
   distinguível de um `MANUAL_ADJUSTMENT` de operador.
5. **(se a DECISÃO D2c for sim)** para cada pendência V1 em aberto
   (`pending_settlement_session_ids` do JSON) escreve um `SESSION_PENDING`
   (delta 0) com a mesma chave de 7.2, para que a dívida **carregue** e seja
   liquidada pela reconciliação FIFO quando entrar crédito.

Isso reusa a mecânica provada (o `psique_v2_append` de 038/039, os CHECKs
fechados de 037 ampliados como fiz na 047) e **não** reescreve o comando grande.
A ferramenta `tools/psique_v2_backfill.py` (espelho de `psique_demo_cortesia.py`)
lê o `identity_state.json`, computa o `net` por organização (soma de
`remaining_sessions` dos profissionais **ativos**) + a flag "já comprou" +
a lista de pendências, roda **ensaio por padrão** e `--aplicar` para executar,
pulando orgs já `psique_v2` e **recusando** qualquer org cujo `net` do JSON
divirja do pool.

---

## 4. Decisões que SÓ você toma (bloqueiam o início)

> **DECIDIDO pelo proprietário em 02/10/2026:**
> - **D2a = Preservar o portão, reexpresso em V2.** Carregar `ever_purchased`;
>   manter o 402 no início de sessão quando a carteira V2 está zerada E a org
>   nunca comprou E o trial V2 expirou/esgotou. O código do portão aterrissa na
>   7.4/7.5; a 7.3 **carrega o sinal**.
> - **D2b = Carregar como `PAID`** (permanente, sem expiração).
> - **D2c = Carregar as pendências V1** como `SESSION_PENDING` V2.
> - **D2d = Mecanismo + piloto agora; conversão em massa na janela da 7.4.**
>
> **Escopo desta entrega (02/10/2026):** migration 048 (comando de backfill +
> evento `V2_MIGRATION_OPENING` + coluna `ever_purchased`), serviço e testes
> contra PostgreSQL descartável. A **ferramenta** de enumeração da frota e o
> **portão V2** de início de sessão ficam para a janela da 7.4, quando houver o
> `identity_state.json` real em mãos.


**DECISÃO D2a — o bloqueio de trial V1 (a mais importante).**
Hoje uma conta que **nunca comprou** e esgotou a cortesia **não consegue iniciar**
uma sessão nova (402). Depois do backfill, o que vale?
- **Opção A (como o plano D2 escreveu): aposentar o bloqueio.** Simples e
  alinhado a "um sistema só". Mas abre um buraco: uma org de saldo zero que nunca
  comprou passaria a **iniciar sessões sem limite**, cada uma virando pendência
  V2 (dívida que nunca bloqueia). Uso grátis infinito com dívida acumulada.
- **Opção B (recomendada): preservar o portão, reexpresso em V2.** Carregar um
  sinal `ever_purchased` e manter o 402 no **início** de sessão quando a carteira
  V2 está zerada **e** a org nunca comprou **e** o trial V2 expirou/esgotou.
  Protege a receita, e **não conflita** com a política A (que é sobre o relatório
  de uma sessão já em curso, não sobre começar uma nova). Mais trabalho: um
  pequeno portão no lado V2 e o transporte do sinal `ever_purchased`.
> Recomendo **B**. O portão de início não abandona paciente nenhum (não há ato
> clínico ainda) e é a única defesa contra uso grátis indefinido. A mudança do
> código do portão pode aterrissar junto da 7.5 (quando o V1 morto sai); na 7.3
> basta **carregar o sinal** `ever_purchased` para a carteira V2.

**DECISÃO D2b — como rotular o saldo carregado.**
- **Recomendada: tudo como `PAID` (permanente, sem expiração).** O crédito V1
  carregado não expira (o V1 não expira créditos; só tem o portão de trial). Como
  o portão vira decisão D2a à parte, o saldo pode ser carregado como crédito
  comum permanente. Não faz sentido carregar como `TRIAL` (que expira em 14 dias
  na 037) — isso **apagaria** saldo real.

**DECISÃO D2c — carregar as pendências V1 em aberto.**
- **Recomendada: sim.** Semear `SESSION_PENDING` V2 para cada sessão já entregue
  sem crédito no V1 (`pending_settlement_session_ids`), para a dívida carregar e a
  reconciliação FIFO da 7.2 liquidá-la quando entrar crédito. Não fazer isso
  **perdoaria** silenciosamente dívidas reais de atendimento.

**DECISÃO D2d — sequência com a 7.4 (acoplamento real).**
Converter uma org para V2 **sem** unificar o comércio deixa uma janela em que ela
não consegue comprar: o checkout V1 ainda vivo (`apply_checkout_purchase`,
[main.py:14628](../froid-server/main.py#L14628)) tentaria gravar um evento v1 numa
carteira já v2 → `WALLET_CREDIT_MODEL_MISMATCH`.
- **Recomendada:** na 7.3 **construir e testar** o mecanismo de backfill e
  converter o **piloto** (a demo já está em V2; o backfill nela é no-op). A
  **conversão em massa** da frota roda **na mesma janela da 7.4** (comércio),
  org a org, para nenhuma ficar sem como comprar. O plano continua com gates
  separados, mas 7.3-mecanismo e 7.4-execução andam juntas.

---

## 5. Invariantes inegociáveis
- **Nenhuma organização perde saldo.** O `net` carregado é conferido contra o
  pool; divergência **recusa** (não adivinha).
- **A trilha V1 é preservada** (sem DELETE), para conciliação.
- **Idempotente:** reexecutar não dobra saldo (no-op se já `psique_v2`; abertura
  com chave fixa por org).
- **Registro clínico nunca bloqueado** (política A da 7.2 segue valendo).
- **IPM intocável.**

---

## 6. Plano de implementação (após suas decisões D2a–d)
1. **Migration 048:** comando `psique_v2_backfill_from_v1` + evento
   `V2_MIGRATION_OPENING` nos CHECKs (cópia verbatim de 037/047 + 1 linha) +
   grant a `froid_runtime`; **se D2a=B**, uma coluna/flag de `ever_purchased` na
   carteira ou em `psique_trials` para o portão V2 reexpresso.
2. **Ferramenta `tools/psique_v2_backfill.py`:** lê o JSON, computa `net` +
   `ever_purchased` + pendências por org, ensaio/`--aplicar`, cruza com o pool.
3. **Serviço** (`PsiqueCredits.backfill_from_v1` ou no executor) fiando o
   contexto GUC/owner, como a cortesia.
4. **(se D2a=B)** portão V2 de início de sessão reexpresso + transporte de
   `ever_purchased`; os endpoints `/session/create` e `/api/session-invites`
   passam a consultar o estado V2 para orgs `psique_v2`.
5. **Testes** contra PostgreSQL descartável com dados **no formato de produção**
   (carteira v1 + `migration_opening` + JSON sintético): saldo preservado exato;
   idempotência; no-op em org já v2; trilha v1 intacta; pendências carregadas;
   `ever_purchased` transportado; recusa em divergência JSON↔pool; org V1 não
   convertida intocada.
6. **Regressão completa + evidência + seu gate.** Conversão em massa só na janela
   coordenada com a 7.4.

---

## 7. Referências-âncora (para a execução)
- Saldo JSON: `main.py:14120-14158` (perfil), `2485-2490` (saldo), `5659-5733`
  (compra + `session_credit_purchases`), `2762-2789`/`2733-2747` (pendências).
- Pool/migrador V1: `tenant_store.py:4482-4555` (`_contribute_legacy_balance`),
  `4921-4933` (chamador), `1619-1649` (`activate_shared_wallet`), `4432-4480`
  (`apply_credit_event`); espelho `main.py:2264-2278`.
- Bloqueio de trial: `main.py:2392-2460` (estado/decisão/mensagem), `2431-2440`
  (bloqueio), `7889-7890`/`7907-7908` (enforço), `2576-2578` (`clinico_pronto`).
- ENROLL/ADJUST + guarda: `migrations/038_...sql:48-349` (`86-95` a guarda,
  `190-204` o ADJUST); serviço `psique_credits.py:187-191`; demo
  `tools/psique_demo_cortesia.py:132-134`.
- Trial V2: `migrations/037_...sql:28-42`; `GRANT_TRIAL` `038:111-162`.
- Roteamento 7.2: `tenant_store.py:433-454`, `main.py` `_organization_uses_psique_v2`.
- Diagnóstico no plano: `docs/psique-v2-fase7-unificacao-plano.md:76-83,113-116`.
