# FROID Psique V2.1 — resultado da Fase 2B (Stripe TEST)

Data: 29/09/2026, America/Sao_Paulo. Autorização: `FROID_Psique_Prompt_Final_Fase_2B_Stripe_TEST.md`, fornecido pelo proprietário com a tabela oficial dos seis objetos TEST.

**Resultado:** Checkout V2, webhook V2 separado, estados de Purchase, idempotência e concessão única de créditos implementados e validados — 37 testes novos com PostgreSQL real e concorrência, 117 no total com a regressão Psique, todos verdes e sem skips. O pré-check consultou o Sandbox real, a metadata TEST foi completada (única escrita autorizada no Stripe), os seis mappings foram registrados a partir dos objetos reais e um smoke criou e releu uma Checkout Session real. Pagamento com cartão de teste na página hospedada e entrega real de webhook ficam para a homologação manual descrita ao final. Nenhum segredo aparece neste relatório.

## 1–2. Conta, modo e objetos confirmados

- Account/Sandbox: `acct_1UL3JIAg9NSIrvBV` ("FROID Psique V2 QA", BR). Chave local com prefixo `sk_test_`; objetos todos `livemode=false`.
- Os seis Products e seis Prices conferem com a tabela autorizada: ativos, BRL, `one_time`, `per_unit`, valores exatos (19900/46900/91500/169000/318000/745000) e lookup_keys exatas.
- `pricing_version=2.1`, `pricing_hash=39b0ba03b384c49ec57844bbfed6ef537c7a1ba97a13885599c447e6e74cd853` — idênticos no catálogo do backend e agora na metadata dos doze objetos.
- **Divergência encontrada e corrigida (somente TEST, sem duplicar):** os Prices não tinham `pricing_hash` e os Products não tinham nenhuma das seis chaves de metadata. Complementadas via update de metadata; estrutura e valores não foram alterados. Reconferência pós-correção: doze objetos completos.
- Webhook/Event Destination TEST: **não criado** nesta fase; nenhum existia para a V2 e o teste local usará Stripe CLI.

## 3–5. Mapeamento, Checkout e estados

Mappings registrados no banco descartável de homologação pelo caminho real do operador: runner explícito até `039`, catálogo em rascunho, e `tools/psique_stripe_mappings.py --register` validando os objetos reais (GET) contra o catálogo — `{"account": "acct_1UL3JIAg9NSIrvBV", "objects_verified": 6, "registered": 6}`. Mapping é imutável, `livemode=false` por CHECK, com `lookup_key` único por conta/modo.

`POST /api/psique/v2/checkout` aceita somente `{"product_code"}`; `amount`, `credits`, `currency`, `stripe_price_id` e `product_id` vindos do navegador são recusados com motivo, não ignorados. O backend resolve tudo no catálogo/mapping, cria a Purchase antes do redirect (idempotência por organização + chave), cria a sessão com `mode=payment`, Price mapeado e `quantity=1`, e grava `purchase_id` em `client_reference_id` e `metadata`. Nenhum dado clínico vai ao Stripe. Estados: `CREATED → CHECKOUT_CREATED → PENDING_PAYMENT → PAID → APPLIED`, com `CANCELED/EXPIRED/FAILED/REVIEW_REQUIRED`; terminais e imutabilidades garantidos por trigger; `prepared/canceled` da Fase 1 preservados com o significado histórico.

## 6–10. Webhook, eventos e idempotência

Endpoint separado `POST /api/psique/v2/stripe/webhook`, sem reuso da lógica V1. Assinatura obrigatória sobre o corpo bruto (`t`/`v1`, HMAC-SHA256, comparação em tempo constante, tolerância de 5 minutos); inválida → 400 sem registro. Evento LIVE no endpoint TEST → 400 com `LIVE_EVENT_REFUSED`. Todo evento válido é gravado duravelmente em `psique_stripe_events` antes de qualquer efeito; estados do inbox: `received/credited/resolved/review/rejected`.

`checkout.session.completed` só concede com `payment_status=paid`, e a verdade aplicada é a sessão relida **pela nossa chave** com `line_items` expandidos — sessão de outra conta não resolve e não concede. Antes de aplicar: conta, moeda, `amount_total`, Price, Product, `quantity=1`, vínculo com a Purchase e snapshot. `completed` não pago → `PENDING_PAYMENT`; `async_payment_succeeded` conclui; `async_payment_failed` → `FAILED`; `expired` → `EXPIRED`; `payment_intent.succeeded` é auditoria e nunca concede; dispute/refund abrem revisão administrativa sem tocar créditos.

Idempotência em camadas: `UNIQUE(stripe_event_id)` com conflito de payload detectado por hash; `UNIQUE(stripe_checkout_session_id)`; índice único parcial `psique_one_grant_per_purchase` no ledger (uma `CREDIT_PURCHASE` por Purchase, no banco); locks `FOR UPDATE` no evento e na Purchase serializam entregas concorrentes; falha na concessão reverte a transação e deixa o evento `received`, reprocessável.

## 11–15. Testes executados

Ambiente: Windows, Python 3.13, PostgreSQL 16.15 descartável recém-criado (porta 55441), bancos filhos aleatórios, transições como `froid_runtime` sem SUPERUSER/BYPASSRLS. Stripe nos testes automatizados é um dublê que devolve a verdade de sessão definida pelo teste; as assinaturas usam o verificador real com segredo sintético.

| Verificação | Resultado |
|---|---|
| `tests/test_psique_phase2b.py` | **37 aprovados, 0 skips** |
| Regressão Psique completa (2B+2A+Fase 1+guards) | **117 aprovados, 59 subtestes, 0 skips** |
| Regressão V1 selecionada (tenant_store, wallet, billing, ordering) | 37 aprovados |
| Ruff / Mypy (módulos novos e tocados) | Aprovados |
| `git diff --check` | Aprovado |
| TypeScript | Não executado: nenhum contrato compartilhado ou painel foi tocado |

Cobertura da matriz: seis SKUs com valor e créditos exatos; corpo adulterado recusado; idempotência de checkout; webhook duplicado e reload sem nova concessão; dois deliveries simultâneos do mesmo evento e dois eventos simultâneos da mesma Purchase concedendo uma única vez; `amount/currency/price/product/quantity/conta/referência` errados rejeitados com Purchase em revisão; sessão desconhecida e Purchase inexistente sem concessão; fluxo assíncrono pendente→pago concedendo uma vez; recusa/expiração/falha assíncrona sem crédito; assinatura inválida/expirada/ausente rejeitada sem registro; conflito de payload no mesmo event id; falha da concessão com rollback e reprocessamento bem-sucedido do mesmo evento; estado de compra cross-org negado.

Smoke real (Sandbox): `prepare → Checkout Session real → attach` com o Price exato do PRO 10, `quantity=1`, BRL 19900, `livemode=false`, URL hospedada presente, `client_reference_id` correto e idempotência devolvendo a mesma Purchase. A sessão não foi paga.

## 16–18. Migration, arquivos e limites

Migration única e aditiva `039_psique_stripe_test_checkout.sql` (número conferido livre imediatamente antes da criação): lookup_key/active no mapping; estados e colunas de recibo na Purchase com guarda de imutabilidade ampliada; `purchase_id` no ledger com unicidade de concessão; inbox `psique_stripe_events` com RLS e sem grants diretos; funções `SECURITY DEFINER` (`checkout_prepare`, `checkout_attach`, `stripe_event`, `apply_purchase`, `purchase_outcome`, `purchase_state`) — o runtime recebe somente EXECUTE nelas.

Novos: `psique_billing.py`, `psique_api.py`, `tools/psique_stripe_mappings.py`, `tests/test_psique_phase2b.py`, este relatório. Atualizados: `psique_catalog_store.py` (lookup_key aditivo, compatível com a Fase 1), `froid_schema.py` (039 opcional para V1), `tests/test_enum_drift.py` (domínio do inbox), `main.py` (bloco final, montagem sob `FROID_PSIQUE_V2_BILLING_ENABLED=false` por padrão), `.env.example`, `froid-server/.env.multitenant.example`, `docker-compose.yml` (variáveis novas, vazias/false), `docs/psique-stripe-v2.md` e o [checklist](psique-v2-checklist-execucao.md).

Sem LIVE, sem produção, sem deploy, sem website, sem licença organizacional, sem FLEX, sem alteração NR-1, sem reinterpretação V1. Falhas preexistentes (anexo comercial NR-1; mypy de `tenant_access.py`) permanecem documentadas nos relatórios anteriores, fora deste escopo, e não foram tocadas.

## Homologação manual — executada em 30/09/2026

Sessão conduzida com o proprietário digitando os cartões na página hospedada real, app local expondo o roteador V2 desta entrega (única diferença: contexto de autenticação sintético de homologação) e `stripe listen` (CLI 1.52.1) encaminhando eventos reais assinados ao webhook. Banco descartável preparado pelo caminho completo do operador (runner explícito, catálogo, mappings reais).

| Cenário real | Resultado |
|---|---|
| PRO 10 com 4242…, PRO 25 com cartão BR, PRO 50 com 3DS completado | Aprovados; saldo exato **85** (10+25+50); três Purchases `APPLIED`; três `checkout.session.completed` → `credited` |
| Recusa (…0002), fundos insuficientes (…9995), 3DS abandonado | **+0**; três `payment_intent.payment_failed` reais → `resolved (PAYMENT_FAILED_NO_GRANT)`; Purchases permanecem `CHECKOUT_CREATED` |
| `payment_intent.succeeded` reais (3) | Somente auditados; nenhuma dupla concessão |
| Reembolso real do PRO 10 (`re_…`, R$ 199,00 no Sandbox) | `refund.created`, `charge.refunded` e `refund.updated` → **revisão administrativa**; saldo continua 85 e a Purchase continua `APPLIED` |
| Entregas do listener | 13, todas HTTP 200, todas com assinatura verificada |

Encerramento: assinatura e objetos de homologação limpos no Sandbox; PostgreSQL descartável removido; arquivos locais contendo o `whsec` do CLI apagados. Pendência remanescente: decidir se haverá Event Destination TEST fixo em staging HTTPS (o teste local usa o CLI).

## Proposta de Fase 2C e parada

Próxima fase (licença organizacional Stripe TEST) somente após nova aprovação: Price mensal `licensed/tiered/graduated`, contagens de assento real/faturada/pendente, preview de prorrata comparado linha a linha e reduções sem crédito intermediário. **Nada disso foi iniciado.** Conforme a seção 19, a execução PARA aqui e aguarda aprovação explícita.
