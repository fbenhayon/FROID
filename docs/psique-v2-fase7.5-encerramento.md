# Fase 7.5 — encerramento da unificação de créditos (05/10/2026)

## O que ficou pronto (código, testado, no Git)
- **Rotas legadas `/api/billing/*`** passam a responder 410 atrás do mesmo
  interruptor da etapa 5 (`FROID_V1_COMMERCE_RETIRED`, já ligado em produção).
- **Páginas que ainda prometiam a cortesia antiga** (20 sessões para os primeiros
  100) foram trocadas pelo teste V2: as institucionais do painel mostram
  "10 créditos de análise por 14 dias", amarrado por teste a
  `psique_pricing.TRIAL_CREDITS/TRIAL_DAYS`; cinco frases do site público
  (pt, en, es, fr e demonstração) deixaram de falar em "faixas" e "sessões
  gratuitas", sem número no texto — os números ficam na página de Preços, que
  os lê ao vivo.
- **Defeito latente na fila de espelho da agenda** (migration **049**): a
  retirada não reservava o item, e dois consumidores pegavam o mesmo evento.
  Ninguém consome essa fila em produção ainda. A 049 está em
  `PSIQUE_V2_VERSIONS`, então **não se aplica sozinha**.
- **Testes que já falhavam antes desta semana**, corrigidos pela causa:
  permissões do Psique V2 (só por função, agora declarado e vigiado), rota de
  convite com chamador, rota de preços V2 montada por roteador, anexo do NR-1
  sem o desconto de pioneiro encerrado em 24/09.

## O que só você executa (a permissão desta sessão barrou escrita no banco)
Backup do banco já feito: `/root/froid-backups/manual/pre-7.5-20261005-2145.dump`.

1. **Marcar "já comprou" nas 3 contas da família e encerrar as assinaturas V1**
   (inclui desligar a recarga automática do cartão do Philippe). No Git Bash:
   ```
   ssh froid 'docker exec -i froid-postgres-1 sh -c "psql -U \"\$POSTGRES_USER\" -d froid_homologacao"' < docs/sql/7.5-encerrar-v1.sql
   ```
   Esperado no fim: 3 linhas com `ever_purchased = t`, `status = canceled`,
   `auto_replenish = f`, e `COMMIT`.
2. **Aplicar a 049** (só quando houver consumidor da fila de agenda, ou já).
   No console do servidor (depois de `ssh froid`), em `/root/froid-project`:
   ```
   docker compose run --rm froid-backend sh -c 'FROID_MIGRATION_DATABASE_URL="$FROID_DATABASE_URL" python tools/migrate_schema.py --apply --through 049_psique_outbox_lease --confirm-database froid_homologacao'
   ```
3. **Stripe (painel), desligar o webhook V1**: Developers → Webhooks → o
   endpoint `https://www.froid.com.br/api/stripe/webhook` → *Disable*. **Não
   mexer** no endpoint `.../api/psique/v2/stripe/webhook`, que é o da compra V2.
4. **Cartão salvo do Philippe no Stripe**: decisão sua (remover ou manter). Com
   o comércio V1 aposentado, ele não é mais cobrado por nenhum caminho.
5. **Google**: apagar a senha de app vazada no chat (`nasx…`) em
   `myaccount.google.com/apppasswords`, logado como `froid@froid.com.br`.
6. **Prova da 7.2**: atender uma sessão real na Froid Clinicas ltda e ver o
   saldo cair de 510 para 509.

Depois do item 3, as chaves V1 (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_PRICE_*`) podem sair do `.env`; nada mais as usa com o interruptor
ligado.
