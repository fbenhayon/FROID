---
name: froid-espelhos-de-numero
description: "Pisos e fórmulas do NR-1 têm cópias no site público e nos documentos comerciais, e já divergiram por semanas"
metadata: 
  node_type: memory
  type: project
  originSessionId: fa4449fd-a259-4e7e-b569-32bb51c38167
  modified: 2026-08-28T11:55:45.723Z
---

Todo número do módulo NR-1 — piso de anonimato, margem de amostra, corte de
censo, faixas de preço — existe copiado em pelo menos quatro lugares fora do
código: `froid-site/*.html`, `docs/comercial/*.md`, `proposta-nr1.html` e
`tools/simulador_nr1.py`. Nenhum deles é gerado a partir da fonte.

Em 28/08/2026 achei `empresas.html` dizendo "piso de coorte (50 por campanha)"
— valor abandonado na migration 027, que o trocou por 15. A divergência estava
publicada havia semanas, numa tabela de comparação que um auditor conferiria
contra a proposta impressa, que dizia 15.

**Why:** o defeito não aparece em teste nem em uso; aparece na frente do
cliente, no número que sustenta o argumento central. É a categoria de erro mais
cara deste repositório porque destrói credibilidade em vez de quebrar função.

**How to apply:** ao mudar piso, margem, corte de censo ou preço, varrer os
quatro lugares acima antes de commitar e rodar
`froid-server/tests/test_nr1_espelhos_do_portao.py`. Ao escrever qualquer
matemática em página pública, conferir contra o código e não contra a memória —
a fórmula da amostra está em `migrations/025_representativeness_floor.sql` e a
do efeito em `froid-server/nr1_effectiveness.py`. A regra real de classificação
da eficácia é `|d| − margem ≥ 0,20`, mais rigorosa do que "o intervalo não pode
tocar o zero", que era como o site a descrevia.

Relacionado: [[froid-nr1-corporate-module]], [[froid-html-encoding-pitfall]],
[[froid-sinal-sem-leitor]].
