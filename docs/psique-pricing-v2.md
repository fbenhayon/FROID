# FROID Psique — catálogo V2, Fase 1

Estado em 29/09/2026: implementado localmente, sem exposição pública. A autorização é a seção 59 do `FROID_Psique_Prompt_Final_VSCode_V2_1.md`. Resultado da validação: [relatório da Fase 1](psique-v2-fase1-relatorio.md).

A fonte comercial executável é [psique_pricing_v2.json](../froid-server/config/psique_pricing_v2.json). Os valores não são copiados para o site, catálogo V1 ou NR-1. O arquivo é uma configuração para instalação explícita; não substitui um catálogo indisponível no banco.

`psique_pricing.py` valida centavos inteiros, moeda BRL, créditos, faixas contíguas e ofertas únicas. Calcula a licença por faixas progressivas, gera JSON canônico e SHA-256. A ordem das ofertas e das chaves não altera o hash; alterações comerciais alteram. A exibição unitária usa Decimal, sem recalcular o total da compra por arredondamento.

Os seis PRO são ativos dentro do catálogo, todos com `public=false`. O catálogo é instalado como `draft`, sem vigência. FLEX e licença estão descritos e inativos; o cálculo da licença é uma função pura, sem contrato, cobrança ou contagem de membros. Acima do limite de autoatendimento, a cotação informa Enterprise e devolve total ausente, nunca um valor estimado.

`psique_catalog_store.py` instala uma versão de forma idempotente e transacional, confere as ofertas contra o conteúdo assinado pelo hash e rejeita substituir o conteúdo de uma versão existente. A leitura normal exige vigência e estado `active`; `include_draft=True` é explícito e restrito às ferramentas/testes desta fase. Catálogo ausente ou inconsistente gera erro.

A migration 035 cria `psique_pricing_tables` e `psique_pricing_offers`. O banco verifica hash/conteúdo, impede alterações de ofertas e exclusões do histórico. Uma versão que saiu de rascunho não pode retornar a ele para reescrever a vigência. RLS e ausência de grants mantêm o runtime sem acesso nesta fase.

Para inspecionar a configuração, sem banco:

```powershell
python froid-server/tools/psique_pricing_catalog.py
```

Para instalar o rascunho, somente após migrations explícitas em banco descartável, a ferramenta exige `FROID_PSIQUE_TEST_DATABASE_URL`, `--install-draft`, `--confirm-database psique_v2_test_...` e `--actor`. Ela não oferece ativação nem Checkout.

Aceitação: `tests/test_psique_pricing_v2.py`, `tests/test_psique_phase1_postgres.py` e a guarda adicional de `billing_type` em `tests/test_enum_drift.py`.
