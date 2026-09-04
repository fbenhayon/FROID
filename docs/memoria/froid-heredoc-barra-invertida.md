---
name: froid-heredoc-barra-invertida
description: "Heredoc do Bash nesta máquina colapsa `\\\\` em `\\` — quebrou três arquivos num dia"
metadata: 
  node_type: memory
  type: project
  originSessionId: fa4449fd-a259-4e7e-b569-32bb51c38167
  modified: 2026-09-03T14:24:11.214Z
---

Ao escrever arquivos com `python - <<'PYEOF'` pelo Bash tool nesta máquina, pares
de barra invertida são colapsados antes de o Python ver o código: `\\s` chega como
`\s` (SyntaxWarning) e `\\n` chega como `\n`, que o Python então interpreta como
newline real — quebrando strings no meio.

Isso acontece **mesmo com o heredoc entre aspas simples** (`<<'PYEOF'`), que em
teoria não deveria sofrer expansão nenhuma.

**Why:** em 03/09/2026 isso quebrou três arquivos em sequência (uma string TS, um
teste Python com `assertRegex`, e um `"\n".join`) — cada um custou uma rodada de
diagnóstico que parecia erro de lógica e era só a barra desaparecida.

**How to apply:** em código gerado por heredoc, não use barra invertida nenhuma.
Para newline use `chr(10)`; para barra use `chr(92)`. Para regex, prefira
reformular sem regex (`" ".join(texto.split())` e `assertIn`). Quando não houver
como evitar, escreva com a ferramenta Write em vez do heredoc.

Relacionado: [[froid-html-encoding-pitfall]] — a outra armadilha de escrita de
arquivo, e o mesmo remédio de conferir o resultado antes de commitar.
