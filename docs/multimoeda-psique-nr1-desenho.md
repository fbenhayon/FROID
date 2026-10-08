# Multimoeda — FROID Psique e FROID NR-1 — desenho

Data: 06/10/2026. Estado em 07/10/2026: **código das Fases A, B e C (Psique)
pronto e testado; NR-1 adiado pelo dono; produção aguarda a janela da seção
"Execução" no fim deste documento.**

## Decisões do dono (DECIDIDO em 06/10/2026)

1. Mesmo número em todas as moedas, sem conversão: R$ 199 = US$ 199 = € 199.
2. Moeda pelo idioma da página: pt → BRL, en → USD, es e fr → EUR.
3. Conta Stripe **real** (live).
4. Vale para FROID Psique e FROID NR-1.

## O que o código faz hoje (por que não basta criar preços no Stripe)

| Ponto | Onde | Hoje |
|---|---|---|
| Catálogo | `froid-server/psique_pricing.py:51` | recusa qualquer moeda que não seja `brl` |
| Tabela de preços no banco | `migrations/035_psique_v2_pricing.sql:9` | `CHECK (currency = 'brl')` |
| Compra de créditos | `migrations/036_psique_v2_purchases.sql:31` | `CHECK (currency='brl')` |
| Licença organizacional | `migrations/040_psique_org_license_test.sql:23` | `CHECK (currency='brl')` |
| Conferência do preço Stripe | `froid-server/psique_catalog_store.py:117` e `:203` | exige `price.currency == config.currency` e valor igual |
| Webhook | `migrations/039_psique_stripe_test_checkout.sql:276` | recusa sessão com moeda diferente da compra (`WRONG_CURRENCY`) |
| Site | `froid-site/site-assets/psique-pricing-v2.js:21` e `:51` | formata sempre `currency: "BRL"`; consulta `/api/psique/v2/pricing` sem moeda |
| NR-1 | `froid-server/pricing_nr1.py:219` | só `formatar_brl`; **não há cobrança Stripe no NR-1** — é proposta e contrato |

O que já ajuda: `migrations/035:28` tem índice único de tabela ativa por `(code, currency)`.
O desenho do banco já previa uma tabela por moeda; o que falta é deixar a moeda variar.

Criar preços em dólar e euro no Stripe sem essas mudanças deixaria os preços sem
uso (defeito 2.1), e mostrar US$ ou € no site com o checkout cobrando em reais
seria rótulo que promete o que não entrega (defeito 2.4).

## O que entra

**Fase A — banco e catálogo (dormente, sem chamador novo).**
- Migração `051`: amplia os três `CHECK` de moeda para `brl`, `usd` e `eur`,
  copiando as definições correntes verbatim (seção 9 da skill). Ampliar não falha
  sobre dados existentes.
- Catálogo: uma configuração por moeda com os mesmos números
  (`psique_pricing_v2.json` → BRL; `_usd`/`_eur` derivadas por código, não
  digitadas). `psique_pricing.py:51` passa a aceitar as três.
- Testes contra PostgreSQL real, Windows e Linux; aplicação incremental de `051`
  sobre o estado atual e reaplicação no-op.

**Fase B — Stripe e checkout.**
- Ferramenta `tools/psique_live_mode_sync.py` estendida: cria no Stripe live os
  preços USD e EUR dos seis pacotes e da licença, com `lookup_key` por moeda, e
  registra o mapeamento pela conferência já existente (valor e moeda iguais à
  configuração).
- Checkout e cotação da licença recebem a moeda escolhida pelo servidor a partir
  do idioma informado, numa lista fechada; o navegador continua mandando só o
  `product_code`. Moeda fora da lista é recusada com código próprio.
- `/api/psique/v2/pricing?moeda=usd` devolve o catálogo da moeda; sem o
  parâmetro, BRL, como hoje.

**Fase C — site.**
- `psique-pricing-v2.js` passa a ler a moeda do bloco `PSIQUE_PRECOS_V2_I18N`
  de cada idioma.
- NR-1: tabelas de faixas, simulador e simulação da proposta em US$ (en) e
  € (es, fr), mesmo número. O motor ganha formatação por moeda; os testes de
  espelho passam a comparar símbolo e número por idioma.

## O que NÃO entra (fronteira)

- Conversão cambial de qualquer tipo.
- Cobrança automática do NR-1 pelo Stripe: o NR-1 é contratado por proposta e
  contrato. Ver a pergunta 1 abaixo.
- Mudança de preço em reais.

## Janela de produção

Fase A e B exigem migração no banco de produção e rebuild do `froid-backend`,
que desloga todo profissional logado. Criação de preços live é cobrança real.
Nada disso roda sem janela combinada com o dono.

## Perguntas que bloqueavam o início (RESPONDIDAS em 07/10/2026)

1. **NR-1 no Stripe.** O NR-1 não tem checkout. "Cadastrar no Stripe" pode
   significar (a) só mostrar US$/€ no site e na proposta, com o contrato na moeda
   do cliente; ou (b) construir cobrança recorrente do NR-1 pelo Stripe, que hoje
   não existe e é um projeto à parte.
   **Decisão do dono: adiar o NR-1.** A multimoeda entra só no FROID Psique; a
   parte NR-1 da Fase C (faixas, simulador e proposta em US$/€) sai deste
   desenho e as páginas do NR-1 seguem em reais em todos os idiomas.
2. **Ordem live.** Recomendei provar cada fase no modo de teste do Stripe antes
   de criar os preços live. **Decisão do dono: direto no live.** Os preços USD e
   EUR nascem na conta live na primeira passagem, dentro da janela de produção.

## Execução (07/10/2026)

Respondidas as duas perguntas (NR-1 adiado; direto no live), as Fases A, B e
C foram construídas para o **Psique** e provadas contra PostgreSQL 16 real
(descartável, Docker local), sem nenhuma chamada de rede ao Stripe.

### O que mudou no código

| Peça | Mudança |
|---|---|
| `psique_pricing.py` | `CURRENCIES`, `LANGUAGE_CURRENCY` (pt brl, en usd, es/fr eur), `currency_for_language` (lista fechada), `version_for` (`2.1`, `2.1-usd`, `2.1-eur`), `config_for_currency` (deriva da BRL: mesmos números, outra moeda), `load_config(currency=)`. O JSON em `config/` continua a única fonte de números, só em BRL; `validate` exige que versão e moeda andem juntas. |
| `migrations/051_psique_multimoeda.sql` | Gerada por `tools/psique_multimoeda_sync.py` a partir do texto real da 046 (teste de espelho byte a byte). Amplia os três `CHECK (currency='brl')` para brl/usd/eur; `psique_v2_seat_confirm` grava a moeda da tabela do preview e recusa Price de outra tabela (`LICENSE_PRICE_NOT_FROM_PREVIEW_CATALOG`); função nova `psique_v2_seat_preview_catalog`. Está em `PSIQUE_V2_VERSIONS` (o arranque não a aplica sozinho). |
| `psique_billing.py` | `checkout` aceita `{"product_code","language"}`; o idioma vira moeda pela lista fechada e escolhe a tabela daquela moeda (versão sufixada). Sem idioma, BRL como sempre. Idioma desconhecido: `CHECKOUT_LANGUAGE_UNSUPPORTED`; `currency`/valor no corpo continuam recusados. Compra fora de BRL exige a 051 (recusa nomeada, não CHECK estourando). |
| `psique_license.py` | Catálogos por moeda; `quote(n, language)`, `preview(ctx, language)`; `confirm` resolve o Price pela versão **gravada no preview** antes de tocar o Stripe. |
| `psique_api.py` / `main.py` | `GET /pricing?language=`, `GET /organization-license/quote?…&language=`, `POST /organization-license/preview` com `{"language"}` opcional; idioma fora da lista = 422 `LANGUAGE_UNSUPPORTED`. |
| Ferramentas | `psique_live_stripe.py --moeda usd|eur` (Product por moeda, `lookup_key` sufixado, registra sob a versão da moeda); `psique_license_stripe.py --moeda`; `psique_pricing_catalog.py --moeda` e `--producao` (instala no banco de operação com `FROID_PSIQUE_OPERACAO_DATABASE_URL` + `--confirm-database`, como o `--register` do live). |
| Site | `psique-pricing-v2.js` v2 manda só o idioma e formata com a moeda que a API declarou (nunca "BRL" fixo); as quatro `precos.html` declaram `language`. Até o backend novo subir, a API ignora o parâmetro e as páginas en/es/fr seguem mostrando R$ — coerente com o que o servidor devolve. |

**Fora, por decisão:** NR-1 (faixas, simulador e proposta seguem em reais em
todos os idiomas); conversão cambial; mudança de preço em reais.

### Provas

- `tests/test_psique_multimoeda.py` (12): 051 byte a byte e opt-in; aplicação
  incremental da 051 sobre um banco com tabela BRL ativa, mapeamentos e licença,
  reaplicação no-op; os três CHECK ampliados e sem literal `'brl'`; compra em
  inglês com o Price USD, `currency='usd'`, versão `2.1-usd`, mesmo número, e
  crédito pelo webhook em USD; sessão em reais para compra em dólar →
  `WRONG_CURRENCY` e `REVIEW_REQUIRED`; espanhol e francês em euro; sem idioma
  continua em reais; idioma desconhecido e campos extras recusados com nome;
  pacote sem objeto Stripe na moeda → `STRIPE_*_MAPPING_REQUIRED`; cotação da
  licença por idioma (mesmo número, outra moeda); licença pré-visualizada em
  inglês assina com o Price USD e grava `usd`/`2.1-usd`; em português continua
  BRL; o banco recusa Price de outra tabela na confirmação.
- `tests/test_psique_pricing_v2.py` (+3): tabelas derivadas, lista fechada de
  idiomas, versão e moeda juntas. `tests/test_psique_phase5.py`: `/pricing`
  por idioma e 422; cada página declara o idioma e nenhuma embute moeda.
- Regressão Psique (2B, 2C, 3, 6, 1, 4, 7, 7.4, convites, contratos, docs):
  verde; `verificar-site.py` 108 páginas, 0 falhas.

### A moeda do painel (resolvido em 07/10/2026)

O painel é só pt-BR, então o idioma não serve para escolher a moeda ali. O que
serve já existia: **o cadastro pergunta o mercado** (Brasil, Estados Unidos,
Espanha, França) e grava `legal_jurisdiction` (BR/US/ES/FR), a mesma chave que
decide os documentos jurídicos. A compra V2 passou a usar essa resposta:

- `main.py` resolve a moeda da sessão pelo perfil (`_psique_moeda_do_profissional`:
  BR real, US dólar, ES/FR euro; sem perfil, real) e entrega o resolvedor ao
  router; o checkout e o preview da licença recebem a moeda **do servidor** e
  o corpo continua sendo só `product_code` (moeda, idioma ou valor no corpo
  seguem recusados com nome).
- `GET /pricing` sem `language` e com sessão devolve o catálogo nessa moeda;
  o painel passou a chamar a rota com a sessão e a formatar com a moeda que
  a API declarou. Exibição e cobrança saem da mesma chave gravada.
- As páginas públicas en/es/fr continuam pelo idioma; as duas regras caem nas
  mesmas três moedas.

**Achado lateral, pré-existente:** o cadastro lista também "Outros países da
União Europeia" e "China", mas o backend normaliza qualquer coisa fora de
US/ES/FR para **BR** — quem escolhe UE ou China é tratado como Brasil (em
documentos e, agora, em moeda). Não mexi: o texto dessas duas opções promete
euro e yuan que o backend nunca gravou; é decisão do dono se elas saem da
lista ou ganham tratamento próprio.

### Roteiro da janela (ele cola, um comando por vez)

Pré-condições: commit + push deste trabalho; `git pull` no servidor **não**
muda a cobrança (a API velha ignora `language`). A sequência abaixo é a da
janela 7.2 (`docs/psique-v2-fase7.2-janela.md`): backup, build, migration,
subir. Nunca dois `docker compose run` colados (o 1º engole a linha do 2º).

1. **Backup** (uma linha, no console do servidor), conferindo tamanho > 0 com
   `ls -lh /root/froid-backups/manual/ | tail -2`:
   ```
   docker exec froid-postgres-1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc froid_homologacao' > /root/froid-backups/manual/pre-multimoeda-$(date +%Y%m%d-%H%M).dump
   ```
2. **Build** — `docker compose build froid-backend` (não derruba nada).
3. **Migration 051** (uma linha):
   ```
   docker compose run --rm -e FROID_MIGRATION_DATABASE_URL="$FROID_DATABASE_URL" froid-backend python tools/migrate_schema.py --apply --through 051_psique_multimoeda --confirm-database froid_homologacao
   ```
   Esperado: `{"action": "apply", "result": ["051_psique_multimoeda"]}`.
   Qualquer `{"status": "failed", ...}` interrompe a janela.
4. **Tabelas USD e EUR** (uma por vez):
   ```
   docker compose run --rm -e FROID_PSIQUE_OPERACAO_DATABASE_URL="$FROID_DATABASE_URL" froid-backend python tools/psique_pricing_catalog.py --install-draft --producao --moeda usd --confirm-database froid_homologacao --actor fabio
   ```
   e o mesmo com `--moeda eur`. Esperado: `"status": "draft"`, `"version": "2.1-usd"` / `"2.1-eur"`.
   Conferência: `SELECT version,currency,status FROM psique_pricing_tables ORDER BY version;` deve listar `2.1 brl`, `2.1-eur eur`, `2.1-usd usd` (o status das novas segue o da BRL; nenhum caminho de compra lê o status).
5. **Objetos Stripe live por moeda** — como em 01/10, com a chave live do
   `.env` (da máquina dele ou de dentro do contêiner), uma moeda por vez:
   ```
   python tools/psique_live_stripe.py --create-objects --homolog --moeda usd
   ```
   Esperado: 6 Prices novos (`lookup_key` `…_v2_1_usd`), licença `froid_psique_org_license_v2_1_usd`, `homolog_failures: 0` (16/16). Depois `--moeda eur`. Se o Stripe recusar a moeda na conta (`STRIPE_HTTP_400`), a ferramenta para antes de registrar qualquer coisa.
6. **Registro dos mapeamentos** no banco de produção (uma moeda por vez):
   ```
   docker compose run --rm -e FROID_PSIQUE_OPERACAO_DATABASE_URL="$FROID_DATABASE_URL" froid-backend python tools/psique_live_stripe.py --register --moeda usd --confirm-database froid_homologacao --actor fabio
   ```
   Esperado: `"registered": 6` e `license_mapping_id`. Depois `--moeda eur`.
7. **Subir o backend novo** — `docker compose up -d froid-backend` (desloga
   os profissionais logados).
8. **Sondas** (read-only):
   - `curl -s "https://www.froid.com.br/api/psique/v2/pricing?language=en"` → `"currency": "usd"` e os mesmos `total_cents`;
   - `…?language=de` → 422 `LANGUAGE_UNSUPPORTED`;
   - `curl -s "https://www.froid.com.br/api/psique/v2/organization-license/quote?clinical_seat_count=10&language=fr"` → `"currency": "eur"`, `135100`;
   - `python tools/conferir-deploy.py` sem divergência; abrir `/en/precos.html` e ver US$.
