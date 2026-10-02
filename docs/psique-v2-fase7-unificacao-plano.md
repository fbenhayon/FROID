# Fase 7 — Unificação no V2 (sistema único) + higienização

Plano escrito em 01/10/2026 a partir de auditoria minuciosa do código (cinco
varreduras somente-leitura). **Nada foi alterado.** Este documento é para o
proprietário aprovar o gate antes de qualquer mudança em produção. Ordem do
proprietário: "não deve haver dois sistemas paralelos… utilizar exclusivamente
o V2… deletar o lixo remanescente… o melhor e mais perfeito código do planeta".

---

## 1. O diagnóstico, em uma página

Hoje há **três conceitos de crédito** vivendo ao mesmo tempo:

1. **V1 cortesia/trial** — `trial_sessions` por profissional, no arquivo JSON
   (`PROFESSIONAL_PROFILES`, `identity_state.json`).
2. **V1 comprado** — `contracted_sessions`+`bonus_sessions` por profissional (JSON),
   ou um **pool** compartilhado por organização no PostgreSQL (só no modo `enforce`).
3. **V2** — carteira **única** por organização (`organization_wallets` com
   `credit_model='psique_v2'`), máquina de **reservar→entregar→consumir**.

**Onde desconta ao atender, hoje:** salvar o relatório de sessão nova
([main.py:15277](../froid-server/main.py#L15277)) → `_consume_session_credit`
([main.py:2850](../froid-server/main.py#L2850)). Com a flag `FROID_SHARED_CREDITS_MODE`
em **"off"** (o padrão em produção), o débito sai do **saldo por-profissional no
JSON**. O pool PostgreSQL só entra em `enforce`. **O V2 não participa de nenhum
atendimento** — está completo no banco e nos serviços, mas sem rota HTTP, não
chamado por nada, com os *loaders* de identidade/material em stub
([main.py:15937-15950](../froid-server/main.py#L15937)).

**Consequência concreta:** os 500 créditos V2 da clínica demo não podem ser
gastos atendendo. A venda real do PRO 10 caiu na carteira V2, que o atendimento
não lê. É a duplicidade a eliminar.

**Comércio:** o checkout V1 **vivo** é `/api/subscriptions/*` +
`/api/stripe/webhook` + `subscriptions.py` + migration 006. O `/api/billing/*`
já é **legado órfão** (responde 410, sem chamador). O V2 vende por
`/api/psique/v2/*`. Dois webhooks Stripe coexistem.

---

## 2. Os seis pontos de conflito (o que torna isto grande)

| # | Conflito | V1 (hoje) | V2 (destino) | Decisão/risco |
|---|---|---|---|---|
| C1 | **Esgotamento de saldo** | entrega a sessão e registra pendência (nunca bloqueia) | bloqueia no BEGIN (`INSUFFICIENT_CREDITS`) | **Decisão de produto D1** — a mais importante |
| C2 | **Onde o relatório grava** | arquivo JSON + espelho | o DELIVER grava direto no Postgres e **recusa transcript no payload** | separar transcrição (registro clínico) do `protected_report` |
| C3 | **Unidade de cobrança** | 1 sessão = −1 imediato | 1 análise de 1 "fonte", reserva→consumo, idempotente por fonte | mapear `sessionId` → identidade de fonte |
| C4 | **Saldo existente** | por profissional no JSON | carteira única por org; ENROLL exige carteira **vazia** | migração dedicada (backfill), não ENROLL direto |
| C5 | **Comércio/assentos** | `/api/subscriptions/*`, limite por `organization_members` | `/api/psique/v2/*`, limite por assentos da licença | dois webhooks + duas contagens sobre a mesma tabela de membros |
| C6 | **Autorização** | `save_session_report` usa `reports.write` (RBAC V1) | comando V2 exige grant CLINICIAN (RBAC v2) ou owner/admin/professional + GUC | fiar o contexto SECURITY DEFINER no atendimento |

---

## 3. Decisões de produto que SÓ você decide (bloqueiam o início)

> **DECIDIDO pelo proprietário em 01/10/2026: Opção A (preservar).** O V2 passará
> a admitir "entregar agora, acertar depois" — o registro clínico nunca é
> bloqueado por falta de saldo. A pendência vira evento de ledger próprio na
> Fase 7.2.

**D1 — Política de esgotamento (a mais crítica).**
Hoje o V1 **nunca recusa um atendimento**: entrega o relatório mesmo sem saldo e
registra "pendência de acerto" ([main.py:2762](../froid-server/main.py#L2762)).
O V2, do jeito que foi construído, **bloquearia** a análise sem saldo. Religar o
atendimento ao V2 sem cuidado **inverteria essa política** — um profissional com
carteira zerada deixaria de conseguir fechar o relatório no meio do cuidado.
- **Opção A (recomendada):** preservar a política V1 — o V2 passa a admitir
  "entregar agora, acertar depois" (entrega sem reserva quando esgotado, grava a
  dívida como evento de ledger próprio). Mais trabalho, mas o registro clínico
  nunca é bloqueado. É o que protege o profissional e o paciente.
- **Opção B:** adotar a política V2 pura — sem saldo, o atendimento não fecha a
  análise. Mais simples, mas é uma regressão de cuidado e quebra o contrato
  travado em `test_credit_exhaustion_preserves_report.py`.

**D2 — Migração dos saldos existentes.**
Clínicas reais (ex.: Jose Camargo) têm saldo V1 espalhado por profissional
(cortesia + comprado). O migrador existente colapsa tudo num número e **perde a
distinção "nunca comprou"** que hoje governa o bloqueio de trial. Proposta:
converter o saldo líquido de cada org em créditos V2 por concessão auditada
(mesma mecânica da cortesia), preservando o histórico V1 para conciliação, e
**aposentar a regra de bloqueio de trial V1** em favor do modelo de trial próprio
do V2 (10 créditos, 14 dias). Confirmar se concorda.

**D3 — Clínica FROID institucional.** Permanece como está: clínica V2 normal com
créditos concedidos por cortesia (sem Stripe). Nenhum caminho especial. ✔ (já feito)

---

## 4. Plano por etapas (cada uma com gate e testes; nada em produção sem seu aval)

### 7.1 — Higienização de baixo risco (EXECUTADA em 01/10/2026)
Remoções de alta confiança, sem relação com a lógica de crédito (feitas, aguardando commit):
- `froid-dashboard/=` — arquivo vazio rastreado por acidente de shell.
- `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `GEMINI_MODEL` em `.env.example` — lidos por
  ninguém (a IA do Explica usa `FROID_EXPLICA_MODEL`/`GEMINI_API_KEY`).
- `STRIPE_PRICE_MASTER_25` em `.env.example`, `.env.multitenant.example`,
  `docker-compose.yml` e docs — órfã desde a retirada do `master_25` (nenhum teste depende).
- **NÃO tocar** (fora de escopo, protegido por teste): as 7 lápides, `_safe_float`
  (morta mas sua remoção quebra o recorte de `test_data_subject_rights.py`),
  `precos-v2.html`×4 e `proposta-nr1.html`×4 (noindex, V2/NR-1).

### 7.2 — Religar o consumo ao V2 (coração)
- `material_loader` real: transformar o material do atendimento (sessionId +
  áudio/transcrição) em `AuthorizedMaterial` com `material_key` estável.
- Separar **transcrição** (armazenamento clínico) do **`protected_report`** (C2).
- Desviar `save_session_report`: para org com `credit_model='psique_v2'`, usar o
  ciclo V2 (`AnalysisWorkflow`); para as demais, manter V1 até migrarem (caminho
  duplo **temporário e explícito**, não permanente).
- Implementar a política de D1 (pendência no V2, se Opção A).
- Fiar contexto RBAC/GUC (C6).

### 7.3 — Migração dos saldos (dados)
- Backfill idempotente: por org, ENROLL + converter o saldo V1 líquido em créditos
  V2 por concessão auditada; preservar trilha; testado contra PostgreSQL
  descartável com dados no formato de produção. Nenhuma org perde saldo.

### 7.4 — Unificar o comércio
- Toda compra passa a ser V2 (`/api/psique/v2/checkout`); aposentar
  `/api/subscriptions/*` + webhook V1; migrar a UI de cobrança
  (`Settings.tsx`, `ProfessionalOnboarding.tsx`) para V2; conciliar as duas
  contagens de assento (C5); descomissionar os envs Stripe V1.

### 7.5 — Remoção do V1 morto (só depois de tudo rodando em V2)
- Deletar o consumo/comércio V1 agora inerte, o `/api/billing/*` órfão,
  `FROID_ACCESS_PLANS`, andaimes de migração; rever/aposentar os testes V1
  (`test_phase4_billing`, `test_shared_wallet_postgres`, `test_auto_recharge_safety`,
  `test_legacy_balance_consolidation`, `test_credit_exhaustion_preserves_report`);
  decidir as 8 rotas `DIVIDA_CONHECIDA` (criar tela ou aposentar).

---

## 5. Princípios inegociáveis durante toda a Fase 7
- **Registro clínico nunca se perde** por falha de cobrança (invariante atual).
- **Nenhuma org perde saldo** na migração; tudo auditável e idempotente.
- **IPM intocável** (ordem permanente).
- **Nada em produção sem você colar/aprovar**; commits só com "commit".
- Cada etapa: revisão minuciosa → testes contra PostgreSQL real (Windows + Linux)
  → evidência → seu gate.

---

## 6. Referências-âncora (para a execução)
- Consumo V1: `main.py:2850` (dispatcher), `2792` (perfil), `2762` (pendência),
  `15277` (gatilho no save do relatório).
- Comércio V1 vivo: `main.py:14194-14810` + webhook `14581`; `subscriptions.py`;
  migration 006; UI `Settings.tsx:1045-1191`, `ProfessionalOnboarding.tsx`.
- V2 consumo (pronto, não ligado): `psique_credits.py:68-164`,
  `psique_analysis.py:27-58`, migration 038 (REGISTER_SOURCE/BEGIN/DELIVER/CONSUME),
  037 (estado/invariantes), 042 (RBAC+fronteira). Stubs: `main.py:15937-15950`.
- Migração de saldo: `tenant_store.py:4459-4532` (+ chamador `4898-4910`).
- Lixo removível: `froid-dashboard/=`; envs em `.env.example:13-16,23`.
