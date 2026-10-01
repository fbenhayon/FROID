# Fase 6 — Roteiro da janela de produção (Etapas 2–5)

Escrito em 01/10/2026, depois da Etapa 1 (inventário LIVE) e da frente de
código do modo LIVE (migration 046 + cliente com modo explícito). Nenhum
comando daqui roda sozinho: o Fábio decide a janela e cola (ou autoriza) cada
bloco. Pré-condição absoluta: **commit + push antes de qualquer comando no
servidor** — o deploy lê o GitHub, não o disco local.

## O que a Etapa 1 encontrou (somente leitura, 01/10/2026)

- Conta real `acct_1TCUwiAYhukisMIH`, cobranças habilitadas, moeda BRL.
- Modo live praticamente virgem: 0 produtos, 0 preços, 0 assinaturas,
  0 clientes, 0 cupons. Campo limpo para os objetos V2.
- 1 webhook órfão de 08/05/2026 apontando para um túnel trycloudflare morto
  (`we_1TUuQwAYhukisMIHdXdRMnl8`, eventos checkout/payment_intent).
  **Recomendação: remover na Etapa 3** — túnel expirado pode ser realocado a
  terceiros, e eventos live seriam entregues a um estranho. Aguarda aprovação.
- Histórico inerte: 4 checkout sessions expiradas (mai–jul/2026) e 1 cobrança
  FALHADA de USD 1,50 — nenhum dinheiro jamais se moveu em live.

## Aviso estrutural da janela

O site institucional é bind mount: **o `git pull` da Etapa 2 já publica a
página de preços V2**. Com o flag desligado ela declara indisponibilidade
(honesta, mas visível). Por isso as Etapas 2→4 rodam comprimidas na mesma
janela, em minutos. O rebuild do backend desloga os profissionais logados.

## Etapa 2 — Infraestrutura (comandos no console do Hetzner)

```bash
cd /root/froid-project && git status --short   # árvore limpa antes de tudo
# 1. Backup do banco de produção (froid_homologacao, pilha do froid-postgres-1)
docker exec froid-postgres-1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc froid_homologacao' \
  > /root/froid-backups/manual/pre-fase6-$(date +%Y%m%d-%H%M).dump
ls -lh /root/froid-backups/manual/ | tail -2   # conferir tamanho > 0
# 2. Código (ATENÇÃO: este pull já vira a página pública de preços)
git pull --ff-only && git log --oneline -1
# 3. Build das imagens (não derruba nada ainda)
docker compose build froid-backend froid-frontend
# 4. Migrations 035–046 pelo runner explícito, com o DSN administrativo da pilha
docker compose run --rm -e FROID_MIGRATION_DATABASE_URL="$FROID_DATABASE_URL" \
  froid-backend python tools/migrate_schema.py --apply \
  --through 046_psique_live_mode --confirm-database froid_homologacao
# 5. Variáveis no .env da pilha (flag AINDA false; liga na Etapa 4):
#    FROID_PSIQUE_STRIPE_MODE=live
#    FROID_PSIQUE_STRIPE_LIVE_SECRET_KEY=<a mesma do froid-server/.env local>
#    FROID_PSIQUE_BILLING_EMAIL=froid@froid.com.br
#    FROID_PSIQUE_STRIPE_LIVE_WEBHOOK_SECRET=<vem da Etapa 3>
# 6. Sobe (derruba sessões ativas — este é o momento da janela)
docker compose up -d froid-backend froid-frontend
docker compose exec froid-backend printenv FROID_PSIQUE_STRIPE_MODE
```

## Etapa 3 — Objetos Stripe LIVE (da máquina local, com a sk_live do .env)

1. Adaptar `tools/psique_license_stripe.py` / `psique_stripe_mappings.py` para
   `--live` (hoje constroem `StripeTestClient` sem modo) — tarefa minha,
   antes da janela.
2. Criar os 6 Prices de crédito + o Price graduado da licença na conta real
   (lookup_keys `*_v2_1`, idempotente por lookup_key), conferir 16/16 previews.
3. Registrar os mappings live no banco de produção
   (`register_test_mapping(..., live=True)` via `docker compose run`).
4. Webhook LIVE no Dashboard: `https://www.froid.com.br` + rota do webhook V2,
   eventos do inbox 2B/2C; copiar o `whsec_` para o .env (item 5 da Etapa 2) e
   `docker compose up -d froid-backend`.
5. Com aprovação: deletar o webhook órfão `we_1TUuQwAYhukisMIH...`.
6. Cupom de demonstração `FROID-DEMO-100` (100% off, duration=forever) para o
   customer da clínica demo — a licença da demo fatura R$ 0,00.

## Etapa 4 — Ativação piloto

1. `FROID_PSIQUE_V2_BILLING_ENABLED=true` no .env + `up -d froid-backend`.
2. Sondas: `GET /api/psique/v2/pricing` público com os preços reais; página de
   preços ×4 línguas deixa de declarar indisponibilidade; seção V2 aparece nas
   Configurações do painel.
3. **Smoke aprovado pelo Fábio**: compra real PRO 10 (R$ 199,00) com cartão
   dele → 10 créditos exatos → reembolso pelo Dashboard → prova de que o
   reembolso NÃO remove créditos sozinho (vira revisão).
4. Conta de demonstração: Fábio cadastra fbenhayon@gmail.com (clínica FROID);
   `tools/psique_demo_cortesia.py` concede +500 (ensaio → `--aplicar`);
   licença só quando houver profissionais clínicos REAIS (sem assentos de
   mentira — decisão de 01/10/2026), com o cupom 100%.

## Etapa 5 — Fechamento público

1. `python tools/conferir-deploy.py` verde camada a camada.
2. Conferir as quatro línguas da página de preços ao vivo (grep servido, não
   cache), âncoras #trial, calculadora com quote real.
3. Registrar evidências no checklist e na memória; marcar a Fase 6 executada.
