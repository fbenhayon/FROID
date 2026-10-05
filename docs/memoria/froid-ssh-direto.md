---
name: froid-ssh-direto
description: Eu tenho acesso SSH direto a producao (ssh froid) desde 05/10/2026; o Fabio nao quer mais colar comandos. Como rodar com seguranca e as duas armadilhas
metadata:
  type: feedback
---

Rodo as janelas de producao eu mesmo, por `ssh -o BatchMode=yes froid '<comando>'` a partir do Bash local. O Fabio perguntou em 05/10/2026 "vc tem acesso ao servidor, por que eu tenho que fazer esse trabalho" — e tinha razao: a chave `froid` esta neste PC e funciona.

**Why:** dois dias de janelas em que ele colava bloco a bloco, errava placeholder e diretorio; com SSH direto a janela da etapa 3 da 7.4 fechou em minutos.

**How to apply:**
- Continua valendo commit so com "commit" e confirmar antes de acao destrutiva; o que muda e quem digita.
- Antes de rebuild do backend, olhar `docker compose logs --since 15m froid-backend | grep -ci /ws/` (sessao clinica ativa cai no rebuild).
- **Armadilha 1:** dentro de `ssh froid 'bash -s' <<EOF`, todo `docker compose exec -T` precisa de `</dev/null`, senao ele engole o resto do script e nada roda (aconteceu: a chave nao foi gravada e nao houve erro).
- **Armadilha 2:** `up -d` sem `build` recria o conteiner com a imagem velha. Provar com `docker compose exec -T froid-backend grep -c <simbolo-novo> main.py` e checar `ps` (frontend "Up 2 hours" = nao reconstruiu).
- Banco real: `docker exec froid-postgres-1` (outra pilha); `docker compose up froid-postgres` cria um conteiner vazio intruso — ja fiz isso uma vez. Ver [[froid-infra-producao]].
