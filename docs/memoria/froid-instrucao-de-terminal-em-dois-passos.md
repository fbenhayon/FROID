---
name: froid-instrucao-de-terminal-em-dois-passos
description: "Instrucao de deploy para o Fabio colar precisa separar \"entrar no servidor\" de \"colar o bloco\", com o sinal visivel do prompt; 01/10/2026 ele colou comandos bash do Hetzner no PowerShell local porque eu escrevi \"conecte e cole\" numa frase so"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 6ec3bea4-fdce-409b-b3dd-be8966cb8ab3
  modified: 2026-10-01T14:26:46.974Z
---

Em 01/10/2026, na janela da Fase 6 do Psique V2, escrevi "Conecte ao servidor (no PowerShell: `ssh froid`) e cole este bloco" — e o Fábio colou o bloco bash inteiro no PowerShell **local**, sem o ssh. Resultado: erros de parser (`&&`, `tail`, `$(date)`), uma pasta `C:\root\froid-backups` criada no Windows por engano, e ele me cobrou, com razão: "essa foi sua instrução???".

**Why:** quem cola comandos não tem o modelo mental do autor. "Conecte e cole" numa frase só lê-se como um gesto único. O custo do erro em deploy é alto (o bloco seguinte teria `git pull` e `up -d`), e a confiança dele na instrução é o que sustenta o fluxo de "ele cola no console" ([[froid-deploy-hetzner]]).

**How to apply:** toda instrução de terminal para o Fábio executar:
1. Um passo por vez, numerado, com **ponto de parada** ("pare e me cole a saída") entre passos de ambientes diferentes.
2. Ao trocar de ambiente (PowerShell→ssh, local→servidor), dizer **como reconhecer** que a troca aconteceu (o prompt muda de `PS C:\...>` para `root@...#`) antes de mandar colar qualquer coisa.
3. Comandos prontos para colagem: sem `\` de continuação de linha, sem depender de aliases; uma linha longa cola melhor do que três com barra.
4. Dizer explicitamente em qual máquina roda CADA bloco, mesmo quando parece óbvio — "é no Hetzner?" e "é no PowerShell?" são perguntas que ele JÁ precisou fazer duas vezes no mesmo dia.
5. **Ordem direta do Fábio, 01/10/2026**: toda instrução de comando DEVE abrir com a etiqueta do terminal — ele pediu literalmente "cada vez que você me indicar uma instrução, me diga se é no Git Bash ou no PowerShell". Formato: "🖥️ ONDE: ..." antes do bloco. Os três lugares dele: **PowerShell** (local, sem ssh), **Git Bash local** (prompt `Fabio@... MINGW64`), e **servidor Hetzner** (Git Bash DEPOIS do `ssh froid`, prompt `root@FROID:...#`). O terceiro não é um programa diferente — é a mesma janela do Git Bash com o prompt mudado, e isso precisa ser dito toda vez.
