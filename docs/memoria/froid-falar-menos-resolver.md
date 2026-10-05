---
name: froid-falar-menos-resolver
description: Ordem do Fabio (05/10/2026) apos 2 dias presos no convite de profissional: falar menos e resolver; quando pedir "so os comandos", entregar blocos sem explicacao
metadata:
  type: feedback
---

Falar menos e resolver. Quando o Fabio diz "nao quero mais ler nada, me passa apenas os comandos", a resposta e so blocos de comando numerados, com rotulo de uma linha (onde roda), sem diagnostico, sem opcoes, sem pedagogia. Decidir o caminho por ele quando a escolha e tecnica.

**Why:** o convite de profissional levou 2+ dias e cinco tentativas; cada rodada vinha com paginas de explicacao, opcoes e perguntas, e ele perdeu a paciencia ("um absurdo", "fala menos e resolve"). O que destravou no fim foram 4 comandos secos. Nao e indiferenca a seguranca: e economia de palavras.

**How to apply:** resposta curta por padrao; opcoes so quando a decisao e dele de verdade (dinheiro, acesso, dado clinico); comandos sempre com `cd /root/froid-project` quando forem de compose (ele ja caiu em `~` e o compose falhou); nunca pedir para ele editar placeholders dentro de um comando (ele colou "NOVASENHA16" literal) — usar `read -s` para capturar segredos.
