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

- [ ] webhook V2 TEST separado
- [ ] Products/Prices TEST para PRO10/25/50/100/200/500
- [ ] Checkout recebe somente `product_code`
- [ ] backend resolve amount/credits/Price ID
- [ ] `checkout.session.completed` paid concede uma vez
- [ ] async success se aplicável
- [ ] PaymentIntent não duplica concessão
- [ ] idempotência event + Checkout/Purchase
- [ ] créditos exatos por SKU
- [ ] pagamento recusado não concede
- [ ] redirect browser não concede
- [ ] dispute/refund externo apenas revisão
- [ ] sem LIVE

Gate: autorizar Fase 2C.

## Fase 2C — Licença organizacional Stripe TEST

- [ ] fórmula backend validada
- [ ] 1/2=499
- [ ] 5=856
- [ ] 10=1.351
- [ ] 20=2.241
- [ ] 25=2.686
- [ ] 30=3.081
- [ ] 50=4.661
- [ ] 100=8.111
- [ ] 200=14.011
- [ ] 201+ Enterprise
- [ ] tiered pricing reproduz backend ou alternativa documentada
- [ ] `active_clinical_seat_count`
- [ ] `billed_clinical_seat_count`
- [ ] `next_cycle_clinical_seat_count`
- [ ] clínico ACTIVE imediatamente
- [ ] prorrata acumulada para próximo vencimento
- [ ] sem `always_invoice`
- [ ] redução operacional imediata
- [ ] redução financeira no ciclo seguinte
- [ ] 10→8→9 sem nova cobrança
- [ ] 10→8→11 cobra apenas 11º
- [ ] billing separado de clinical status
- [ ] não clínicos gratuitos/ilimitados
- [ ] sem LIVE

Gate: autorizar RBAC V2.

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
