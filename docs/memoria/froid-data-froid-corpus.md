---
name: froid-data-froid-corpus
description: A regra do Fábio para o acervo Data-Froid — preservar a substância vale mais que recusar por precaução
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fa4449fd-a259-4e7e-b569-32bb51c38167
  modified: 2026-09-04T19:13:52.641Z
---

Para o acervo Data-Froid, o Fábio decidiu em 04/09/2026: **mesmo imperfeita, a desidentificação tem de preservar o conteúdo da questão e da resposta.** Recusa por precaução que apaga a substância é pior do que uma limpeza imperfeita que a mantém.

**Why:** o acervo existe para outro profissional consultar em busca de recurso clínico. Registro recusado, ou cheio de buracos, não ensina nada — e um acervo vazio custa mais do que um acervo desidentificado de forma imperfeita, porque o piso de coorte (k=50) e a fronteira clínica já protegem por cima. Ele também não trata os defeitos que aparecem nesse ajuste como erro, e sim como afinação a ser feita sobre fala real ao longo das sessões.

**How to apply:** ao mexer em `froid_deidentify.py`, a pergunta certa não é "isto é seguro?" e sim "isto é seguro E ainda ensina alguma coisa?". Descarte deve ser o mais local possível — período, não a fala inteira —, e todo corte precisa ser visível (`[OMITIDO]`), porque texto que parece completo e não é engana quem consulta. Antes de apertar uma regra, medir a taxa de recusa por motivo em `professional_deid_reason`: apertar sem medir é trocar um acervo útil por um acervo limpo e inútil. A assimetria continua: fala do profissional entra desidentificada, fala do paciente nunca entra literal. Ver [[froid-nr1-corporate-module]] para a fronteira clínica e [[froid-sinal-sem-leitor]] para o padrão que criou as colunas vazias.
