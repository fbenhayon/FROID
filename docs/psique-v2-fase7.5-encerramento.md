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
2. **Aplicar a 049 e a 050** (as duas de uma vez; a 050 corrige a cobrança de
   sessão que já estava pendente). No console do servidor (depois de
   `ssh froid`), em `/root/froid-project`:
   ```
   docker compose run --rm froid-backend sh -c 'FROID_MIGRATION_DATABASE_URL="$FROID_DATABASE_URL" python tools/migrate_schema.py --apply --through 050_psique_session_charge_fix --confirm-database froid_homologacao'
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

## Revisão minuciosa (06/10/2026)
Três revisões independentes (motor de créditos, segurança do convite, telas);
cada achado conferido no código antes de corrigir.

**Corrigido e testado:**
- **Crítico — tomada de conta pelo convite.** Login Google não grava credencial;
  o aceite público criava senha no e-mail de quem só entrava pelo Google. Agora
  o servidor classifica a identidade: senha provada → pede a senha; identidade
  sem senha → recusa e manda ao Google; credencial não verificada (cadastro
  abandonado de outra pessoa) é substituída, nunca promovida.
- **Alto — aceite reativava usuário desativado.** O banco recusa e não renomeia
  a identidade existente.
- **Médio — papel de gestão por link.** Owner/administrator só aceitam com a
  conta; o link público concede só profissional/supervisor.
- **Médio — identidade criada só pelo convite** não abre teste grátis próprio
  (trial INELIGIBLE), fechando a fábrica de testes com e-mails inventados.
- **Alto — cobrança V2 que falhava nunca era refeita.** Agora o atendimento
  segue (política A) e o relatório marcado é cobrado na próxima gravação.
- **Alto — cortesia V1 barrava conta já no V2** (quem esgotou e comprou V2).
- **Médio — 047 cobrava duas vezes a sessão pendente** → migration **050**.
- **Médio — entrega atrasada da fila de agenda** → 049 recusa após a reserva.
- **Médio — travas da compra V1** mesmo com o interruptor desligado: recarga
  automática e checkout V1 recusam carteira V2 no servidor.
- **Médio — conta nova em organização com outros membros** só no banco: não
  nasce V2.
- Leituras de banco do portão V2 e do nascimento fora do laço de eventos; cache
  do modelo da carteira (só V1→V2).
- Telas: onboarding de teste travava com aceite jurídico; envio só depois da
  configuração; carteira com erro passageiro não vira "V1"; botões "Comprar"
  desativados sem permissão e durante o checkout; retorno do Stripe visível;
  saldo do topo e do administrativo pela carteira V2; página do convite trata
  conta Google, gestão e desativado, grava a sessão só após o aceite e recarrega
  o painel; campo para colar o código; retorno pós-verificação só no formato
  exato do link.

**Registrado, não corrigido (motivo):**
- Saldo por organização de trabalho vs. organização do perfil (convidado de
  clínica com perfil solo zerado): pede redesenho do estado de acesso por
  contexto; hoje o portão V2 por organização já decide o início de sessão.
- Ferramenta de conversão não percorre segundas contas (`profile_views`): a frota
  já foi convertida e contas novas nascem V2; só importa numa nova rodada.
- Nova tentativa do trial que falhou após converter (`psique_v2_sem_trial`):
  raro; o operador concede com a ferramenta de cortesia.
- Nascer V2 depende de `FROID_TRIAL_SESSIONS > 0` (configuração de produção = 10).
- Campos obrigatórios do cadastro (sexo, RG, país, estado, cidade, profissão):
  decisão do dono de 05/10/2026, mantida.
- Cancelamento de convite pendente pela clínica: funcionalidade nova, não defeito.

