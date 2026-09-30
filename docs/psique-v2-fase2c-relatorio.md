# FROID Psique V2.1 — resultado da Fase 2C (licença organizacional Stripe TEST)

Data: 29/09/2026, America/Sao_Paulo. Autorização do proprietário para revisar as instruções da fase e implementá-la; as regras vigentes são a seção 2C do [checklist](psique-v2-checklist-execucao.md) e o anexo V2.1 registrado em [billing V2](psique-billing-v2.md) — em especial: **sem `always_invoice`**, prorrata acumulada para o próximo vencimento, ativação clínica imediata e licença que nunca concede créditos.

**Resultado:** licença organizacional implementada e validada — **16 testes novos** com PostgreSQL real (134 na regressão Psique completa, zero skips), fórmula conferida em todos os pontos do checklist **e** na série exaustiva 1..200 contra os tiers, e homologação **real** no Sandbox: Price graduado criado, **16/16 previews reais exatos ao centavo**, assinatura real criada/aumentada/cancelada com a prorrata acumulada comprovada na fatura seguinte. Nenhum segredo neste relatório. **A execução PARA aqui; RBAC V2 (Fase 3) exige nova aprovação.**

## Objetos e homologação Stripe TEST

- Sandbox: `acct_1UL3JIAg9NSIrvBV` ("FROID Psique V2 QA"). Criados pelo operador (`tools/psique_license_stripe.py`, idempotente por `lookup_key`, nunca duplica): Product `FROID Psique - Licenca Organizacional` e Price `price_1UL8dPAg9NSIrvBV0cTTE8Ul`, mensal, BRL, `tiered/graduated`, `lookup_key froid_psique_org_license_v2_1`, metadata com versão `2.1` e hash `39b0ba03…d853`. Tiers: até 2 flat 49900; 3–5 unit 11900; 6–10 9900; 11–25 8900; 26–50 7900; 51–100 6900; 101+ 5900 (o teto 200 é imposto pela aplicação — 201+ é Enterprise e o preview recusa antes de qualquer chamada Stripe).
- **Tiers reproduzem o backend:** previews reais da primeira fatura para 1, 2, 3, 5, 6, 10, 11, 20, 25, 26, 30, 50, 51, 100, 101 e 200 clínicos — todos idênticos à fórmula (`49900 … 1401100`), zero divergências.
- Mapping registrada pelo caminho real do operador em banco descartável confirmado (runner explícito até `040` + catálogo em rascunho + `--register`), com validação tier a tier do Price real contra a regra do catálogo.
- Smoke real do ciclo de vida: assinatura criada com 2 assentos (`send_invoice` — coleta TEST sem cartão), aumento 2→3 com `create_prorations`, quantidade 3 confirmada no objeto real, **fatura seguinte real = 73700** (61800 do ciclo a 3 + 11900 da prorrata do assento novo; nenhuma fatura imediata), redução a zero → `cancel_at_period_end=true` real. A assinatura de smoke foi cancelada ao final (limpeza declarada).

## Implementação

Migration aditiva `040_psique_org_license_test.sql`: `psique_clinical_memberships` (habilitação clínica por membership; um usuário conta uma vez por organização), `psique_organization_licenses` (identidade Stripe imutável, `livemode=false` por CHECK, três contagens, versão otimista que só avança) e `psique_seat_changes` (preview versionado com snapshot de cotação; estados `PREVIEWED/CONFIRMED/SUPERSEDED/ABORTED`). Funções `SECURITY DEFINER` com `EXECUTE` ao runtime e nenhuma escrita direta em tabela: `clinical_set`, `license_state`, `license_price_mapping`, `seat_preview`, `seat_confirm`, `license_sync`.

Regras que o próprio banco exige como evidência: aumento só com `quantity` igual ao previsto **e** `proration_behavior=create_prorations`; redução/retorno dentro do faturado **recusa** qualquer chamada Stripe (`REDUCTION_MUST_NOT_CHARGE`); zero exige `cancel_at_period_end=true`; reativação vinda de cancelamento agendado exige o des-cancelamento. `10→8→9` mantém faturado 10 e não toca o Stripe; `10→8→11` atualiza quantidade uma única vez (cobra só o 11º). Preview supersede o anterior; confirmação aborta com `LICENSE_VERSION_CONFLICT`/`PREVIEW_STALE_SEAT_COUNT` quando versão ou contagem mudaram, e o serviço **compensa** a mudança Stripe já feita (exceto quando um confirm concorrente do mesmo preview aplicou o mesmo alvo — defeito encontrado e corrigido em revisão própria antes dos testes). `psique_v2_license_sync` espelha status/período da assinatura e marca `STRIPE_QUANTITY_DIVERGENT` sem jamais tocar o status clínico.

`psique_license.py` orquestra (cotação pura do catálogo — fonte única, sem espelho de número no SQL); `psique_billing.py` ganhou os métodos de assinatura e o webhook passou a sincronizar `customer.subscription.*` (faturas são auditadas e nunca movem créditos); rotas novas sob a mesma flag desligada: `GET /organization-license/quote`, `GET /organization-license`, `POST /organization-license/preview`, `POST /organization-license/changes` (409 em conflito), `PATCH /clinical-memberships/{id}`. Criar assinatura sem fonte de e-mail de faturamento **falha fechada** (`BILLING_EMAIL_RESOLVER_REQUIRED`) — a fonte real será ligada na fase de ativação; a exigência veio da homologação real (o dublê não a teria revelado).

## Testes e qualidade

| Verificação | Resultado |
|---|---|
| `tests/test_psique_phase2c.py` | **16 aprovados, 0 skips** (inclui prova exaustiva 1..200 dos tiers) |
| Regressão Psique completa (2C+2B+2A+F1+guards) | **134 aprovados, 59 subtestes, 0 skips** |
| Regressão V1 selecionada | 37 aprovados |
| Ruff / Mypy (módulos novos e tocados) | Aprovados |
| `git diff --check` | Aprovado |
| TypeScript | Não aplicável: painel/contratos não tocados |

Cobertura: ativação imediata/idempotente e restrita a owner/administrator; não clínicos gratuitos e ilimitados (zero ativos → nenhuma assinatura); primeira assinatura com a contagem ativa; aumento cobra só assentos novos com prorrata acumulada; `10→8→9` e `10→8→11`; zero cancela no fim do período e reativação des-cancela sem cobrar; Enterprise (201 ativos reais no banco) sem self-service; preview supersedido, versão errada e contagem defasada abortando **com compensação Stripe verificada chamada a chamada**; confirms concorrentes aplicando uma única vez; cross-org negado; `PAST_DUE` sem suspender clínico e divergência de quantidade marcada; licença sem nenhum lançamento no ledger. Guards de drift cobrem `clinical_status`, `license_status` e `change_status`.

## Limites, pendências e ponto de parada

- **Eventos reais de assinatura homologados em 30/09/2026**, na sessão manual conjunta com a 2B: assinatura criada e aumentada pela API de homologação, `customer.subscription.created/updated` e `invoice.created/finalized` reais entregues pelo `stripe listen`, assinatura verificada, licença sincronizada (`LICENSE_SYNC_OK`, `ACTIVE 3/3`) e faturas auditadas sem mover créditos; assinatura de homologação cancelada ao final.
- A aplicação da redução no vencimento (ajustar a quantidade Stripe para `next_cycle` na virada) é reconciliação operada — como o `reconcile` da 2A — e será exercitada na homologação com relógio de teste ou na ativação; o estado local (`billed` × `next_cycle` × `current_period_end`) já registra tudo.
- Falhas preexistentes conhecidas (anexo NR-1; mypy de `tenant_access.py`) permanecem fora do escopo, inalteradas.
- Sem LIVE, sem produção, sem publicação, sem FLEX, sem RBAC V2. **Fase 3 (RBAC V2) somente com nova aprovação explícita.**
