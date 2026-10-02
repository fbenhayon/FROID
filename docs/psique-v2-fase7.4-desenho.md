# Fase 7.4 — Unificar o comércio no V2 (desenho)

Escrito em 02/10/2026 a partir de leitura do código (varredura dedicada). **Nada
implementado.** Para o seu gate e para decidir os pontos marcados **DECISÃO**.
É a maior fase do programa — mexe em pagamento real —, então o desenho é por
**etapas com gate**; não se conclui num lance. Pré: 7.2/7.3 no ar (migrations
047/048 aplicadas; backend servindo).

## 1. Diagnóstico
- **Comércio V1 vivo:** `GET/POST /api/subscriptions/*` (checkout de pacotes
  PRO/PLUS, [main.py:14289-14897](../froid-server/main.py#L14289)) + webhook
  `POST /api/stripe/webhook` ([main.py:14676](../froid-server/main.py#L14676)) →
  `apply_checkout_purchase` credita `organization_wallets` com um evento
  **ledger_version=1** ([tenant_store.py:2066](../froid-server/tenant_store.py#L2066)).
  Módulo `subscriptions.py` (SESSION_PACKAGES) + migration 006. Env:
  `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/`STRIPE_PRICE_*`
  ([main.py:353-359](../froid-server/main.py#L353)). Família legada `/api/billing/*`
  já meio desligada (410 atrás de `FROID_SUBSCRIPTIONS_REQUIRED`).
- **Comércio V2 (destino):** `/api/psique/v2/*` (checkout + webhook,
  [psique_api.py:66,350](../froid-server/psique_api.py#L66)) → `CREDIT_PURCHASE` na
  carteira V2; já **LIVE** (flag ligada em produção).
- **UI (painel):** `Settings.tsx` tem os **dois** comércios lado a lado — a V1
  (`/api/subscriptions/checkout`, [Settings.tsx:566](../froid-dashboard/src/pages/Settings.tsx#L566))
  e a `SecaoPsiqueV2` (só aparece com a flag ligada). **`ProfessionalOnboarding.tsx`
  só conhece V1** ([:705](../froid-dashboard/src/pages/ProfessionalOnboarding.tsx#L705))
  — **maior lacuna**: conta nova não tem caminho de compra V2.
- **Dois tetos de assento (C5), desconexos:** entitlement `organization_members`
  (plano V1, imposto no convite/aceite em
  [tenant_store.py:1288/1398](../froid-server/tenant_store.py#L1288)) vs **assento
  clínico faturado V2** (`psique_clinical_memberships` + `PsiqueLicense`,
  assinatura por quantidade).
- **Pronto vs faltando:** o **backfill está pronto** (048 + `backfill_from_v1` +
  testes), mas **a ferramenta de conversão em massa NÃO existe** (nenhum código lê
  `identity_state.json` e chama o backfill). O **portão de sessão V2** também não
  existe (`/session/create` e `/api/session-invites` ainda usam o
  `_trial_blocks_new_session` V1, [main.py:7889/7907](../froid-server/main.py#L7889)).

## 2. O acoplamento que dita a ordem
`psique_credit_history_guard` recusa um INSERT ledger_version=1 numa carteira já
`psique_v2` (`WALLET_CREDIT_MODEL_MISMATCH`,
[037:161-164](../froid-server/migrations/037_psique_trial_credit_state.sql#L161)). Como
a compra V1 insere ledger_version=1, **converter a carteira de uma org antes de a
compra dela apontar para o V2 faz o cliente pagar e não receber crédito.** Logo:
**UI→V2 precede a conversão; conversão precede aposentar o V1.**

## 3. Sequência segura (cada etapa um gate)
1. **Ferramenta de conversão em massa** (pré-requisito de tudo): lê
   `identity_state.json`, calcula por org `net` (soma de `remaining_sessions` dos
   membros) + `ever_purchased` (de `session_credit_purchases`) + pendências, e
   chama `PsiqueCredits.backfill_from_v1` org a org. **Ensaio por padrão**,
   `--aplicar` para valer; pula orgs já `psique_v2`; testada contra PostgreSQL
   descartável com `identity_state.json` sintético. **Não roda em massa até a UI
   estar em V2.** (mecanismo e testes já prontos; falta o orquestrador)
2. **Checkout V2 em TODAS as superfícies de compra** do painel — inclusive o
   **onboarding** (que hoje só conhece V1). `SecaoPsiqueV2` já cobre o Settings;
   falta um fluxo de compra V2 no `ProfessionalOnboarding.tsx`. Esconder/retirar o
   bloco de pacotes V1 das telas.
3. **Portão de sessão V2** em `/session/create` e `/api/session-invites`: pode
   iniciar se `ever_purchased` OU existe `CREDIT_PURCHASE` v2 OU o trial V2 tem
   saldo — **ativado org a org só DEPOIS de a carteira dela estar convertida**.
4. **Converter as carteiras em massa** (ferramenta da etapa 1), org a org, cada
   uma já com a compra apontando para V2.
5. **Aposentar webhook/rotas V1** (`/api/stripe/webhook`, `/api/subscriptions/*`,
   e as legadas `/api/billing/*`) — só quando nenhuma UI as chama e as carteiras
   ativas estão convertidas. Vários já têm interruptor (410 atrás de
   `FROID_SUBSCRIPTIONS_REQUIRED`).
6. **Descomissionar as env V1** (`STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/
   `STRIPE_PRICE_*`) por último, após drenar checkouts pendentes.
7. **Reconciliar assentos (C5)** ao longo do caminho (ver D1).

## 4. Decisões que são suas (DECISÃO)
- **D1 — Assentos (C5):** o **assento clínico V2** (`PsiqueLicense`, assinatura por
  profissional) passa a ser a **única** fonte de "quantos profissionais a org
  paga", substituindo o entitlement `organization_members` V1 na imposição de
  convite/aceite? Ou os dois medem coisas diferentes e só um governa o acesso?
  *Recomendo:* o V2 governa; o convite/aceite deixa de ler o entitlement V1 e passa
  a consultar o estado de licença V2. (é o que "um sistema só" pede)
- **D2 — Onboarding:** construir um fluxo de compra **V2 no onboarding** (hoje
  inexistente) — confirmar, porque é a maior peça de UI nova.
- **D3 — Famílias legadas `/api/billing/*`:** aposentar de vez nesta fase
  (já estão 410-gated) ou deixar para a 7.5? *Recomendo:* retirar na 7.5 junto com
  o resto do V1 morto, para a 7.4 focar no caminho vivo (`/api/subscriptions/*`).

## 5. Invariantes
- **Nenhuma compra paga sem crédito:** a ordem (UI→V2 antes de converter) existe
  exatamente para isto; nenhuma org recebe tráfego de compra depois de convertida
  sem o checkout dela já ser V2.
- **Nenhuma org perde saldo** na conversão (garantido pelo backfill: `net` do JSON,
  trilha preservada, idempotente).
- **Registro clínico nunca bloqueado** (o portão novo é de *início* de sessão, não
  do salvamento — como o V1).
- **Nada em produção sem você colar**; cada etapa: teste (Windows+Linux) → gate →
  janela.

## 6. O que dá para adiantar com segurança (sem tocar produção)
A **etapa 1 (ferramenta de conversão em massa)** é contida, testável e dormente
(não roda sozinha). É o próximo passo natural de construção — como foi o mecanismo
da 7.3. As etapas 2–6 mexem em pagamento/tela e pedem gate e janela.

## 7. Âncoras
- V1: `main.py:14289-14897` (subscriptions), `14676` (webhook), `353-359` (env);
  `tenant_store.py:2015/2066` (apply_checkout_purchase); `subscriptions.py:35/77`;
  migration 006. Legado: `main.py:14908/15066` (`/api/billing/*`).
- V2: `psique_api.py:55-355`; `psique_billing.py:257/300`; migrations 035/036/039/046.
- UI: `Settings.tsx:566/1044` (`SecaoPsiqueV2`), `ProfessionalOnboarding.tsx:705`;
  `lib/psique-v2-api.ts`, `components/psique/SecaoPsiqueV2.tsx`.
- Assentos: `tenant_store.py:1288/1398` (entitlement V1), `psique_license.py` (V2),
  `psique_api.py:90-130`.
- Backfill pronto: migration 048, `psique_credits.py:105`; portão V1:
  `main.py:2431/7889/7907`.
