# Fase 7.4, etapa 3 — conta nova nasce no V2, onboarding sem pacote, portão V2 (desenho)

Escrito em 05/10/2026 a partir de leitura do código. **Nada implementado.** Pré:
etapas 1 (`e6d7f9d2`) e 2 (`76a80497`) no ar. Decisões já tomadas e que valem
aqui: **D2** (onboarding com trial V2 de 10 créditos/14 dias, compra depois) e
**D2a** (portão de início preservado, reexpresso em V2).

## 1. Como a conta nasce hoje
- `POST /api/professional/profile` (main.py:14241) grava o perfil e dá a
  **cortesia V1**: 20 sessões para as posições 1–100, 10 para 101–200, depois
  `FROID_TRIAL_SESSIONS` (main.py:431/447/2360). Depois `_save_identity_state`
  → espelho → `_contribute_legacy_balance` cria a carteira **`credit_model='v1'`**
  e grava um `migration_opening` no ledger (tenant_store.py:4557/4580).
- Por isso **o ENROLL nunca funciona numa conta nova** (exige carteira vazia e
  ledger vazio → `V1_WALLET_CONVERSION_NOT_AUTHORIZED`). O caminho que aceita
  carteira com ledger é o **backfill da 048**.
- O **trial V2** (`grant_trial`, 10 créditos, 336 h, deduplicado por HMAC do
  e-mail) **nunca é chamado em produção**: os loaders de identidade não estão
  ligados e não existe chave `FROID_PSIQUE_TRIAL_HMAC_KEYS` no servidor.
- O **portão de início** é só V1: `_trial_blocks_new_session` → 402 em
  `/session/create` e `/api/session-invites` (main.py:2448/8040/8058).
- O **onboarding** exige escolher pacote e manda ao checkout V1
  (ProfessionalOnboarding.tsx:599/705).

## 2. Desenho
1. **Interruptor próprio** `FROID_PSIQUE_V2_NEW_ACCOUNTS` (padrão `false`). Ligado,
   vale para conta **nova**; desligado, tudo como hoje. Volta atrás sem deploy.
2. **Conta nova no V2**, no `POST /api/professional/profile`, quando o perfil é
   criado (não na edição) e o interruptor está ligado:
   - não concede a cortesia V1 (`trial_sessions=0`, sem `trial-froid`);
   - depois do espelho criar a carteira, chama `backfill_from_v1(net=0,
     ever_purchased=False)` → carteira vira `psique_v2` com saldo 0, trilha
     preservada (é a mesma máquina da etapa 1, com `net` zero);
   - chama `grant_trial` com a identidade **já provada** pelo login: Google
     (`email_verified` do Google) ou senha com `email_verified`
     (`verified_via` = e-mail ou convite de clínica). `legacy_history_checked`
     = o e-mail não tem benefício V1 anterior no JSON; se tiver, o trial nasce
     `INELIGIBLE` (anti-abuso: quem já ganhou cortesia V1 não ganha de novo).
   - falha do trial **não derruba o cadastro**: a conta fica V2 com saldo 0 e o
     erro vai para o log e para a resposta (`trial: "nao_concedido", motivo`).
3. **Portão V2 de início de sessão** (D2a), só para org `psique_v2`: pode iniciar
   se `available_balance > 0` **ou** `ever_purchased` **ou** existe
   `CREDIT_PURCHASE` no ledger. Senão 402 com "Seu teste terminou; compre
   créditos em Administrativo". Org V1 segue no portão V1. O relatório de sessão
   já em andamento **nunca** é bloqueado (política A da 7.2).
4. **Onboarding**: com o interruptor ligado, some o bloco "Plano e pagamento";
   o botão vira **"Começar meu teste gratuito"** → salva o perfil → painel. A
   compra fica no Administrativo (seção Psique V2, etapa 2).

## 3. O que é operação (não código)
- Gerar a chave do trial e pôr no `.env` do servidor:
  `FROID_PSIQUE_TRIAL_HMAC_KEYS` (≥32 bytes) e `..._ACTIVE_VERSION`. Sem ela o
  trial V2 não é concedido (falha fechada, cadastro continua).
- Ligar `FROID_PSIQUE_V2_NEW_ACCOUNTS=true` + `up -d froid-backend`.

## 4. Decisão do dono (só uma)
- **D3-1 — cortesia de conta nova:** o trial V2 dá **10 créditos por 14 dias**.
  Hoje a conta nova recebe **20 sessões sem prazo** (posições 1–100). Com o
  interruptor ligado, a conta nova passa a receber os 10/14 dias da D2.
  Confirmar a troca.

## 5. Invariantes
- Conta existente não muda nesta etapa (só a conta **nova**); a frota converte
  na etapa 4.
- Ninguém paga sem receber: a compra da conta nova já é a V2 (etapa 2).
- Registro clínico nunca bloqueado; IPM intocável.
- Testes: PostgreSQL real, Windows **e** Linux; painel 821+ verdes.

## 6. Implementação (05/10/2026)
- `main.py`: `FROID_PSIQUE_V2_NEW_ACCOUNTS`; `_psique_v2_identidade_para_trial`
  (Google, ou senha com e-mail verificado); `_psique_v2_conta_nova_pode_nascer`
  (interruptores, DSN de runtime, chave do trial válida, identidade provada e
  **organização só desta conta** — clínica que já existe pelo CNPJ fica no V1);
  `_psique_v2_nascer` (backfill net=0 + `grant_trial`); no cadastro, perfil novo
  que pode nascer no V2 não recebe a cortesia V1 e fica `credit_origin =
  psique_v2_trial`. Se falhar **antes** de converter, volta à cortesia V1
  (`v1_trial_fallback`); se converteu e só o trial falhou, fica
  `psique_v2_sem_trial` no log (o operador concede com a ferramenta de cortesia).
- Portão V2 em `/session/create` e `/api/session-invites`
  (`_psique_v2_start_block_detail`): só org V2; libera saldo > 0 ou "já comprou"
  (`TenantStore.psique_v2_ever_purchased`); falha de leitura **libera**.
- `/api/auth/config` → `onboarding_trial_first`; onboarding sem pacote, botão
  "Começar meu teste gratuito".
- `docker-compose.yml` e `.env.example` passam a levar o interruptor.
- Testes: `tests/test_psique_phase74_etapa3.py` (7). Windows: 7/7 + 74 da família
  Psique/cortesia; Linux (python 3.12, postgres:16): idem. Suíte completa do
  servidor: só as 16 falhas que já existiam no HEAD (site/NR-1/rotas/grants),
  nenhuma nova. Painel 821 verdes.

## 7. Janela
1. Servidor: `git pull --ff-only`, `docker compose build froid-backend
   froid-frontend`, `docker compose up -d froid-backend froid-frontend`. Com o
   interruptor desligado nada muda para conta nova; o portão V2 já vale para
   orgs V2 (hoje só a demo, que tem 510).
2. Chave do trial no `.env` (gerada no servidor, nunca colada em chat), ligar
   `FROID_PSIQUE_V2_NEW_ACCOUNTS=true`, `up -d froid-backend`.
3. Prova: cadastrar uma conta nova real → Administrativo mostra 10 créditos de
   teste; `credit_origin` = `psique_v2_trial`.
