# FROID Psique — Stripe V2

Estado em 29/09/2026: schema e validação local para TEST; integração operacional não implementada. Não houve criação, edição ou arquivamento de objetos Stripe nesta Fase 1.

O inventário remoto anterior está no [relatório de pré-implementação](psique-v2-pre-implementacao.md). Naquela observação, o processo de produção carregava credencial TEST e os objetos retornaram `livemode=false`. Isso não constitui inventário LIVE nem comprovação do estado remoto atual. Não foi feita nova consulta remota nesta etapa de testes locais.

`psique_stripe_price_mappings` relaciona oferta/versão à conta, ambiente, Product e Price. `livemode=false` é uma restrição do banco, não uma preferência do frontend. Mapeamentos não podem ser reescritos ou excluídos; outra oferta/versão deve manter outra identidade histórica.

`register_test_mapping` valida objetos já fornecidos por um operador/teste: ambiente, ativação, ligação Product/Price, preço único em BRL, valor inteiro, créditos e metadados de produto/versão/hash. Não chama Stripe nem comprova a procedência desses objetos. A integração futura deverá buscá-los no backend autenticado na conta declarada; dados enviados pelo navegador não servem como verificação.

Os objetos `acct_SYNTHETIC`, `prod_SYNTHETIC` e `price_SYNTHETIC` usados nos testes são fixtures locais. Não são objetos reais nem evidência de uma chamada à API Stripe. A instalação do catálogo também não cria objetos externos.

Checkout, webhook, transição para pago, crédito idempotente, reembolso, assinatura organizacional e preview de prorrata permanecem para fases futuras. Os testes atuais provam restrições do schema e validação de dados; não provam pagamento, entrega de webhook ou funcionamento no Stripe TEST real.

Nenhuma credencial de migração ou de teste foi adicionada ao Compose. As variáveis dedicadas pertencem às ferramentas explícitas do operador e não devem ser herdadas pelo processo web.
