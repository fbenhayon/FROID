# FROID Psique — Stripe V2

Estado em 29/09/2026, após a Fase 2B: Checkout e webhook V2 implementados e validados contra o Sandbox TEST real (`acct_1UL3JIAg9NSIrvBV`, "FROID Psique V2 QA"). Nenhum objeto LIVE foi tocado; a única escrita no Stripe foi a complementação de metadata dos doze objetos TEST, autorizada pelo prompt da fase. [Relatório da Fase 2B](psique-v2-fase2b-relatorio.md).

O inventário remoto anterior está no [relatório de pré-implementação](psique-v2-pre-implementacao.md); ele descreve outra conta (a carregada pelo backend V1). O Sandbox da V2 é separado e dedicado.

## Objetos TEST oficiais da V2

Catálogo `FROID_PSIQUE_V2` versão `2.1`, hash `39b0ba03b384c49ec57844bbfed6ef537c7a1ba97a13885599c447e6e74cd853`. Todos `one_time`, BRL, `per_unit`, `livemode=false`, com metadata completa (`froid_product`, `family`, `product_code`, `credits`, `pricing_version`, `pricing_hash`):

| product_code | Product | Price | Centavos | lookup_key |
|---|---|---|---:|---|
| FROID_PRO_10 | prod_VLl3bMw1tZJQuA | price_1UL3XJAg9NSIrvBV3VTX3ybq | 19900 | froid_psique_pro_10_v2_1 |
| FROID_PRO_25 | prod_VLl4nNVvpxxcxc | price_1UL3YkAg9NSIrvBV6IRjcdsj | 46900 | froid_psique_pro_25_v2_1 |
| FROID_PRO_50 | prod_VLl5GzlS0a3GpK | price_1UL3ZOAg9NSIrvBVPwXMuaDn | 91500 | froid_psique_pro_50_v2_1 |
| FROID_PRO_100 | prod_VLl6eS8CVPTMvf | price_1UL3a2Ag9NSIrvBV5s7lNuaW | 169000 | froid_psique_pro_100_v2_1 |
| FROID_PRO_200 | prod_VLl6H6AGS2lgrl | price_1UL3alAg9NSIrvBVzKmjHPEc | 318000 | froid_psique_pro_200_v2_1 |
| FROID_PRO_500 | prod_VLl89PtmMJFb9z | price_1UL3bwAg9NSIrvBV8b47kl4L | 745000 | froid_psique_pro_500_v2_1 |

`tools/psique_stripe_mappings.py` busca esses objetos com GET, confere valor, moeda, `one_time`, metadata e `lookup_key` contra o catálogo instalado e registra os mappings imutáveis no banco descartável confirmado. Divergência interrompe a execução; nada é corrigido em silêncio.

## Fluxo implementado (migration 039 + psique_billing/psique_api)

- **Checkout** (`POST /api/psique/v2/checkout`): o corpo aceita somente `{"product_code"}` — qualquer campo a mais é recusado com motivo. O backend resolve oferta, centavos, créditos e Price ID; `psique_v2_checkout_prepare` cria a Purchase (`CREATED`) sob idempotência por organização; a sessão Stripe é criada com `mode=payment`, o Price mapeado e `quantity=1`; `psique_v2_checkout_attach` grava o `cs_test_` imutável (`CHECKOUT_CREATED`). Comprar exige papel owner/administrator e carteira `psique_v2`.
- **Webhook** (`POST /api/psique/v2/stripe/webhook`, separado do V1): assinatura verificada em tempo constante sobre o corpo bruto; evento LIVE é recusado com erro nomeado. O evento é gravado de forma durável (`psique_stripe_events`, `UNIQUE(stripe_event_id)`) antes de qualquer efeito; a aplicação relê a sessão **pela nossa chave** (com `line_items` expandidos) e valida conta, moeda, valor, Price, Product, quantity e vínculo com a Purchase. Divergência marca o evento `rejected` e a Purchase `REVIEW_REQUIRED`, sem crédito.
- **Concessão**: só com `payment_status=paid`; `psique_v2_apply_purchase` transiciona `PAID → APPLIED` e lança `CREDIT_PURCHASE` na carteira compartilhada da Fase 2A, com vínculo à Purchase e índice único que impede segunda concessão. `completed` sem pagamento (meios assíncronos) leva a `PENDING_PAYMENT`; `async_payment_succeeded` conclui. `payment_intent.succeeded` é auditado e nunca concede. Dispute/refund só abrem revisão administrativa.
- **Estados de Purchase**: `CREATED, CHECKOUT_CREATED, PENDING_PAYMENT, PAID, APPLIED, CANCELED, EXPIRED, FAILED, REVIEW_REQUIRED` (os históricos `prepared/canceled` da Fase 1 mantêm o significado original). `APPLIED/EXPIRED/FAILED/CANCELED` são terminais por trigger; snapshot, sessão, PaymentIntent e recibo de aplicação são imutáveis.
- **Falha na concessão** reverte a transação inteira e deixa o evento `received`, reprocessável; o navegador/redirect apenas consulta `GET /purchases/{id}`.

A ativação pública segue desligada: `FROID_PSIQUE_V2_BILLING_ENABLED=false` por padrão, transmitida literalmente pelo Compose; ligar sem chave TEST, segredo de webhook e DSN restrito falha fechado com motivo nomeado. A chave do Sandbox e o `whsec` vivem só em ambiente/secret local, nunca no repositório.

## O que ainda não foi executado

- Pagamentos reais com os cartões de teste na página hospedada (4242…, recusa, fundos insuficientes, 3DS) e entrega real de webhook (Stripe CLI `stripe listen` local ou endpoint TEST em staging HTTPS). A matriz correspondente foi coberta com eventos sintéticos assinados pelo mesmo verificador; a homologação com cartão é o passo manual seguinte.
- Webhook/Event Destination TEST no Stripe: não criado nesta fase; o smoke usou somente Checkout Session real (criada e consultada, não paga).
- LIVE, produção, licença organizacional, FLEX: intocados. Fase 2C exige nova aprovação.
