# FROID Psique V2 — Checklist de Aprovação por Fase

Atualizado em 29/09/2026 a partir de `FROID_Psique_Checklist_Aprovacao_V2.md` e do prompt da Fase 2A fornecidos pelo proprietário. **Autorização executada: somente Fase 2A local.** Itens futuros foram preservados como planejamento, não como autorização de execução. Marcação técnica não substitui aprovação do proprietário.

[Relatório da Fase 2A](psique-v2-fase2a-relatorio.md) · [Protocolo de créditos](psique-credits-v2.md) · [Migração e privilégios](psique-migration-v1-v2.md).

Antes de cada fase: conferir HEAD/working tree, preservar trabalho concorrente, conferir numeração real de migrations imediatamente antes de criar arquivos, executar os testes apropriados e entregar o resultado para revisão. Nenhum commit/push sem autorização. NR-1 permanece fora do escopo.

Antes de qualquer ativação para pacientes: integrar os provedores reais de identidade/histórico V1/material, validar a entrega pelo pipeline clínico, definir heartbeat/varredura de reservas e homologar o acesso aos relatórios. Nesta entrega, esses contratos foram exercitados com fixtures sintéticas declaradas.


## Fase 1 — Pricing/schema seguro
Status: APROVADA LOCALMENTE, com pré-requisitos de produção pendentes.

- [x] `ensure_schema()` não autoaplica migrations
- [x] runner explícito/auditável
- [x] catálogo V2 separado
- [x] pricing em centavos
- [x] hash/versionamento
- [x] catálogo draft/public=false
- [x] Purchase estrutural sem conceder créditos
- [x] PostgreSQL descartável testado
- [x] V1 preservada no escopo executado
- [ ] validar em Linux/runtime equivalente à produção
- [x] revalidar números de migration antes do merge — 035–038 únicos e sequenciais, conferidos em 29/09/2026 sobre o HEAD `a82e962a` imediatamente antes do commit
- [x] commit cirúrgico sem trabalho concorrente — autorizado pelo proprietário e executado em 29/09/2026, em três commits (auditoria, Fase 1, Fase 2A); os arquivos da frente concorrente ficaram fora
- [ ] runtime DB role sem DDL amplo antes de produção

Gate: pode avançar para Fase 2A local/homologação.

## Fase 2A — Trial + créditos + source identity

Status: IMPLEMENTADA E VALIDADA LOCALMENTE; revisão do proprietário pendente. Os itens marcados referem-se ao núcleo interno e aos testes, sem ativação pública.

- [x] `analysis_source_id` imutável
- [x] uma source = no máximo 1 consumo
- [x] SHA-256 auxiliar sem reescrita desnecessária
- [x] `reserved_balance`
- [x] reserva concorrente segura
- [x] consumo somente após entrega durável
- [x] `CREDIT_RELEASE`
- [x] `CREDIT_RESTORE` único por consumo
- [x] Trial +10 apenas uma vez
- [x] Trial 14 dias
- [x] Trial individual e organização
- [x] organização recebe 10 total, não por membro
- [x] Trial primeiro, saldo pago depois
- [x] expiração não remove pago
- [x] reserva atravessando vencimento conforme política
- [x] testes PostgreSQL concorrentes verdes
- [x] sem Stripe operacional
- [x] sem produção/LIVE

Evidências: **39 testes da Fase 2A aprovados**, incluindo conexões PostgreSQL independentes em concorrência; 26 testes da Fase 1 aprovados novamente; Ruff e Mypy aprovados. A regressão ampliada tem uma falha preexistente no anexo comercial NR-1 e cinco skips, detalhados no [relatório](psique-v2-fase2a-relatorio.md).

- [ ] Revisão e aprovação desta entrega pelo proprietário.
- [ ] Nova autorização explícita para iniciar Fase 2B.

Gate: Fase 2B não iniciada. A seção 24 do prompt 2A manda parar e aguardar nova aprovação.

## Fase 2B — Stripe TEST para pacotes PRO

Status: IMPLEMENTADA E VALIDADA LOCALMENTE em 29/09/2026, contra o Sandbox real `acct_1UL3JIAg9NSIrvBV`; homologação manual com cartões de teste pendente. [Relatório da Fase 2B](psique-v2-fase2b-relatorio.md).

- [x] webhook V2 TEST separado — rota própria, assinatura sobre corpo bruto, inbox durável; Event Destination fixo não criado (teste local usará Stripe CLI)
- [x] Products/Prices TEST para PRO10/25/50/100/200/500 — verificados no Sandbox real; metadata completada (única escrita, somente TEST)
- [x] Checkout recebe somente `product_code`
- [x] backend resolve amount/credits/Price ID
- [x] `checkout.session.completed` paid concede uma vez
- [x] async success se aplicável
- [x] PaymentIntent não duplica concessão
- [x] idempotência event + Checkout/Purchase
- [x] créditos exatos por SKU — matriz com eventos sintéticos assinados; cartões reais na página hospedada pendentes
- [x] pagamento recusado não concede
- [x] redirect browser não concede
- [x] dispute/refund externo apenas revisão
- [x] sem LIVE

- [x] Homologação manual executada em 30/09/2026, com o proprietário digitando os cartões: PRO 10 (4242), PRO 25 (cartão BR) e PRO 50 (3DS completado) aprovados → saldo exato 85, três Purchases APPLIED; recusa, fundos insuficientes e 3DS abandonado → +0, sem transição; `payment_intent.succeeded` reais só auditados; 13 entregas reais do `stripe listen`, todas 200 com assinatura verificada; reembolso real do PRO 10 → três eventos em revisão administrativa, saldo e Purchase intocados. [Detalhes no relatório](psique-v2-fase2b-relatorio.md).
- [ ] Revisão e aprovação desta entrega pelo proprietário

Gate: autorizar Fase 2C.

## Fase 2C — Licença organizacional Stripe TEST

Status: IMPLEMENTADA E VALIDADA LOCALMENTE em 29/09/2026, com homologação real dos tiers no Sandbox `acct_1UL3JIAg9NSIrvBV`. [Relatório da Fase 2C](psique-v2-fase2c-relatorio.md).

- [x] fórmula backend validada — todos os pontos do checklist e a série completa 1..200 contra os tiers
- [x] 1/2=499
- [x] 5=856
- [x] 10=1.351
- [x] 20=2.241
- [x] 25=2.686
- [x] 30=3.081
- [x] 50=4.661
- [x] 100=8.111
- [x] 200=14.011
- [x] 201+ Enterprise — sem preço/self-service; preview recusa antes de qualquer chamada Stripe
- [x] tiered pricing reproduz backend — 16 previews REAIS no Sandbox, 16/16 exatos ao centavo
- [x] `active_clinical_seat_count`
- [x] `billed_clinical_seat_count`
- [x] `next_cycle_clinical_seat_count`
- [x] clínico ACTIVE imediatamente
- [x] prorrata acumulada para próximo vencimento — fatura real seguinte 73700 = 61800 + 11900 do assento novo, sem fatura imediata
- [x] sem `always_invoice` — somente `create_prorations`, exigido como evidência pelo próprio banco
- [x] redução operacional imediata
- [x] redução financeira no ciclo seguinte
- [x] 10→8→9 sem nova cobrança — zero chamadas Stripe no caminho
- [x] 10→8→11 cobra apenas 11º — uma única atualização de quantidade
- [x] billing separado de clinical status — PAST_DUE não desativa clínico
- [x] não clínicos gratuitos/ilimitados
- [x] sem LIVE

- [x] Homologação manual executada em 30/09/2026: assinatura real criada e aumentada pela API de homologação; `customer.subscription.created/updated` e `invoice.*` reais entregues pelo `stripe listen`, assinados, sincronizados (`LICENSE_SYNC_OK`) e faturas auditadas sem mover créditos; assinatura de homologação cancelada ao final.
- [ ] Fonte real do e-mail de faturamento na fase de ativação (criação de assinatura falha fechada sem resolvedor)
- [ ] Revisão e aprovação desta entrega pelo proprietário

Gate: autorizar RBAC V2.

## Revisão financeira pré-Fase 3 (30/09/2026)

Revisão de ponta a ponta do núcleo financeiro (fórmulas, máquina de créditos, checkout, licença) a pedido do proprietário, antes do RBAC V2. A fórmula, as invariantes de carteira/ledger da 037 e a semântica por evento foram reconferidas e estavam corretas. Quatro melhorias executadas, todas testadas:

- [x] Migration 041: índices que os lookups financeiros realmente usam — as buscas de consumo/restauração não casavam com o predicado (`ledger_version=2`) dos índices parciais da 037 e varriam o ledger inteiro; contagem de assentos e supersessão de preview ganharam índices parciais por organização.
- [x] `X-Idempotency-Key` passou a ser obrigatório no checkout (422 nomeado): retry de rede não pode virar segunda compra com chave inventada pelo servidor.
- [x] Compra em estado terminal com a mesma chave é recusada com motivo (`PURCHASE_TERMINAL_USE_NEW_IDEMPOTENCY_KEY`) em vez de devolver URL de sessão morta.
- [x] Guarda de espelhos de número: teste novo compara os preços copiados nos documentos (pontos da licença no checklist e tabela PRO do doc Stripe) contra o catálogo-fonte.

## Fase 3 — RBAC V2

- [ ] papéis cumulativos
- [ ] CLINICIAN / SECRETARY / FINANCE / ORG_ADMIN
- [ ] CLINICAL_SUPERVISOR / AUDITOR_COMPLIANCE / SUPERADMIN
- [ ] admin sem clínico por padrão
- [ ] secretaria sem conteúdo clínico
- [ ] financeiro sem conteúdo clínico
- [ ] supervisor apenas escopo explícito
- [ ] backend/API/WS/SQL/RLS protegidos
- [ ] policy V1 não contorna V2
- [ ] cross-org negado
- [ ] NR-1 preservado

Gate: autorizar agenda.

## Fase 4 — Agenda organizacional

- [ ] Appointment interno é autoridade
- [ ] Google apenas espelho
- [ ] secretaria cria/reagenda/cancela sem conteúdo clínico
- [ ] profissional vê agenda autorizada
- [ ] version/expected_version + 409
- [ ] audit trail
- [ ] disponibilidade
- [ ] vínculo appointment→session/source
- [ ] falha Google não perde agendamento
- [ ] tokens externos não expostos

Gate: autorizar UI/site.

## Fase 5 — App e website V2

- [ ] pricing vem do backend
- [ ] falha API não mostra preço antigo/zero
- [ ] todos PRO visíveis
- [ ] Trial 10/14 comunicado
- [ ] pioneiros removidos
- [ ] créditos e licença separados
- [ ] calculadora clínica usa backend
- [ ] administrativos gratuitos/ilimitados
- [ ] paywall bloqueia só nova análise
- [ ] histórico permanece acessível
- [ ] menus respeitam capabilities
- [ ] quatro idiomas consistentes
- [ ] nenhum hardcode conflitante

Gate: preparar LIVE.

## Fase 6 — Homologação de produção / LIVE

- [ ] Linux/container equivalente validado
- [ ] runtime DB role sem DDL
- [ ] migration role separado
- [ ] migrations rechecadas contra branch final
- [ ] inventário Stripe LIVE read-only
- [ ] Products/Prices LIVE planejados
- [ ] webhook LIVE V2 planejado
- [ ] secrets via ambiente/secret manager
- [ ] sem secrets em logs
- [ ] rollback
- [ ] monitoramento
- [ ] backup/janela de migration
- [ ] migrations aplicadas explicitamente
- [ ] objetos LIVE V2 criados
- [ ] webhook LIVE validado
- [ ] piloto/allowlist
- [ ] smoke tests
- [ ] website/app somente após backend pronto

## Pós-LIVE

- [ ] reconciliação Stripe↔Purchase↔Wallet
- [ ] monitorar webhook failures
- [ ] monitorar reservas órfãs/restores
- [ ] monitorar prorratas
- [ ] monitorar RBAC denials
- [ ] revisar Trial→Compra
- [ ] revisar custo real por análise
- [ ] manter V1 histórica
- [ ] FLEX continua projeto separado até homologação própria
