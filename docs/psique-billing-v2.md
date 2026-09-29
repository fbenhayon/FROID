# FROID Psique — billing V2

Estado em 29/09/2026: estrutura preparatória da Fase 1 e núcleo interno de Trial/créditos da Fase 2A implementados localmente. [Resultado e limitações da Fase 2A](psique-v2-fase2a-relatorio.md). V1 continua sendo o fluxo público; não há operação Stripe V2.

`psique_purchases`, criada pela migration 036, guarda organização, oferta, versão/hash da tabela, moeda, total em centavos, créditos, mapeamento Stripe, conta, ambiente, idempotência e autoria. O snapshot é imutável. A referência ao Checkout pode ser preenchida uma vez e é única. A idempotência é única por organização.

Nesta fase, os únicos estados são `prepared` e `canceled`; cancelamento é terminal. O banco recusa LIVE, Checkout LIVE e estado `paid`. A organização deve ser `solo` ou `clinic`. Não existe endpoint de compra V2, processamento de pagamento ou ligação com a carteira. Não há concessão de crédito por INSERT em Purchase.

O catálogo e o mapeamento precisam corresponder ao snapshot. Alteração de preço requer nova versão, sem reescrever compras. Conta Stripe e ambiente fazem parte das referências. V1 mantém catálogo, checkout, recargas, assinaturas e ledger existentes.

Regras implementadas no núcleo local da Fase 2A, com testes em PostgreSQL real:

- Trial por organização, com dez créditos e até quatorze dias; consumir saldo gratuito antes do pago, sem expirar créditos comprados.
- Honrar reserva iniciada antes do vencimento mesmo quando a conclusão ocorre depois. Falha após o vencimento exige `CREDIT_RELEASE` e `TRIAL_EXPIRATION` na mesma transação, sem saldo gratuito reutilizável. Restauração técnica após o vencimento exige expiração compensatória.
- Identidade canônica de fonte clínica e cobrança no máximo uma vez por fonte; reanálise/reprocessamento sem nova cobrança. O ledger distingue reserva, consumo, liberação, restauração e origem do saldo.

O [protocolo de créditos](psique-credits-v2.md) documenta evidência de identidade, HMAC versionado, fonte, entrega durável, locks e reconciliação. Carteira V2 exige adesão explícita de organização Psique sem saldo/histórico V1. Os provedores reais de identidade/material e o pipeline público ainda precisam de integração e homologação. Não há compra V2 operacional nem job periódico de recuperação instalado.

Regras V2.1 da licença organizacional, **implementadas na Fase 2C** (29/09/2026, [relatório](psique-v2-fase2c-relatorio.md)) e exigidas como evidência pelo próprio banco na migration 040:

- Entrada clínica produz `clinical_status=ACTIVE` imediatamente. Estado de cobrança (`PENDING_PAYMENT`, `PAST_DUE`) nunca suspende o profissional — o sync de assinatura não toca status clínico.
- `active_clinical_seat_count` (derivado do banco), `billed_clinical_seat_count` e `next_cycle_clinical_seat_count` são contagens separadas. Aumento acima do faturado cobra o assento novo desde a confirmação, com prorrata **acumulada para a próxima fatura** (`create_prorations`; `always_invoice` é recusado). Redução é operacional imediata e financeira no ciclo seguinte, sem crédito negativo e **sem chamada Stripe no dia** — `10→8→9` não gera cobrança; `10→8→11` cobra apenas o 11º. Zero clínicos nunca cria assinatura; a volta a zero cancela no fim do período.
- A licença organizacional não concede créditos (o ledger permanece intocado por ela). Usuários não clínicos são gratuitos e ilimitados. 201+ é Enterprise, sem preço self-service.

Mudança de assento é preview versionado + confirmação: preview supersede o anterior, e a confirmação aborta em conflito de versão ou contagem defasada, compensando a alteração Stripe já feita. A cobrança pública, o e-mail de faturamento real e o RBAC V2 continuam pendentes de fases próprias; o [checklist por fase](psique-v2-checklist-execucao.md) registra o que resta.
