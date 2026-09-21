---
name: froid-seguranca-rigor-maximo
description: Instrução permanente do Fábio — adotar sempre a providência mais rígida de segurança no servidor, e o limite que essa instrução não dispensa
metadata:
  node_type: memory
  type: feedback
---

Instrução dada em 21/09/2026, ao abrir o acesso SSH direto: **"sempre adotar as providências mais rígidas com relação a preservar ao máximo a segurança no servidor"**. Vale como padrão, não como resposta a um caso — entre duas opções defensáveis, escolher a mais fechada sem perguntar.

O que isso decide na prática: chave dedicada por finalidade em vez de chave partilhada; remover credencial sem uso em vez de deixar "por via das dúvidas"; fechar porta de firewall órfã em vez de manter por conveniência futura; `prohibit-password` em vez de `yes`; backup antes de editar configuração de acesso.

**O que a instrução NÃO dispensa.** Ela é sobre a escolha entre opções, não sobre pular a apuração. No mesmo dia, "desligar autenticação por senha" era claramente a providência mais rígida — e teria cortado o único caminho por onde o Fábio entrava no servidor, porque os logins interativos dele eram por senha e não por chave. Isso só apareceu porque conferi o journal antes de aplicar. Rigor aplicado sem apurar o que depende do que não é rigor, é incidente. Ver [[froid-deploy-hetzner]].

**Why:** o Fábio disse explicitamente que não tem como avaliar a eficácia técnica das medidas e confia no critério — o que transfere para mim o ónus de não confundir "mais fechado" com "melhor", e de nunca fechar sem antes saber quem fica de fora.

**How to apply:** propor e aplicar a opção mais rígida por defeito, com backup e com verificação depois. Antes de qualquer medida que feche um caminho de acesso, apurar por evidência (journal, `last`, `ss`, config) quem usa aquele caminho hoje — e se houver alguém, entregar o caminho novo funcionando ANTES de fechar o velho. Medida que dependa de ação do Fábio (digitar uma passphrase, testar um login) é dita em uma linha, com o comando pronto.
