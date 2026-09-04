---
name: froid-nr1-fontes-normativas
description: Onde vive o texto da NR-1 no repositório, e três coisas que a norma não diz
metadata:
  type: reference
---

O texto integral do capítulo 1.5 da NR-1 e as publicações oficiais do MTE estão em **`docs/normas/`** do repositório, importados em 21/08/2026 (452KB). Não estão na memória de propósito: memória é um fato por arquivo e entra no contexto toda sessão.

- `primarias/` — Portaria 1.419/2024 com o texto integral, Portaria 765/2025, Guia MTE 2025, Manual GRO 2026, Cartilha com o FAQ da CGNOR. **Citável.**
- `secundarias/` — Revista do TST, Migalhas, FIEG, ClickCompliance. Interpretação, com atribuição.
- `nao-citavel/` — conversa de IA e material promocional que afirmam o que o produto NÃO faz (biomarcadores de voz/face no onboarding corporativo, "90% de redução de passivo", mapa de risco por colaborador). Ficam rotulados em vez de apagados.

`docs/normas/README.md` tem a tabela subitem → onde está implementado no código, conferida contra o texto.

**Why:** eu vinha respondendo sobre a norma pela paráfrase dos comentários do código. Com o texto em mãos confirmei os nove campos de 1.5.7.3.2, os seis gatilhos de 1.5.4.4.6 e que ISO 45001 serve para o prazo de 3 anos — mas também achei uma divergência que a paráfrase escondia.

**How to apply:** antes de afirmar qualquer coisa sobre a norma, ler `docs/normas/primarias/`. Três armadilhas confirmadas contra o texto:

1. **A NR-1 não fixa taxa de resposta nem piso de coorte.** Os dois portões do FROID são escolha metodológica nossa, defensável sob "suficiência técnica" — nunca apresentar como exigência legal. Ver [[froid-nr1-corporate-module]].
2. **A hierarquia de 1.5.5.1.2 termina em EPI**, e o `MEASURE_HIERARCHY` do FROID troca EPI por `monitoring` e acrescenta `substitution` (que vem do Manual). Defensável no psicossocial, mas é divergência do texto literal e tem de estar escrita no documento de critérios.
3. **Não há prazo legal para implementar a medida** — 1.5.5.2.2 exige cronograma; o prazo é da organização.

**Prazo que importa comercialmente:** a dupla visita orientativa de 90 dias após a vigência (26/05/2026) terminou em **24/08/2026**. A partir dali cabe auto de infração. Multas da NR-28: R$ 2.396,35 a R$ 6.708,08.
