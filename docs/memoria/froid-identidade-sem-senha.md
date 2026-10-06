---
name: froid-identidade-sem-senha
description: Login Google nao grava credencial de senha; "nao tem senha" NAO significa "nao tem conta". Quase virou tomada de conta pelo convite publico (corrigido em aba2cd4a, 06/10/2026)
metadata:
  type: project
---

`PROFESSIONAL_CREDENTIALS` so tem quem se cadastrou por senha. Quem entra pelo Google existe em `users` (Postgres) e/ou `PROFESSIONAL_PROFILES`, mas nao ali. O aceite publico do convite (43c1dfc2) tratava "sem credencial" como "conta nova" e criava senha no e-mail: o admin de qualquer clinica convidava um profissional Google, abria o link e tomava a conta inteira (todas as clinicas e pacientes). Ficou no ar ~1 dia; a revisao de 06/10 achou e corrigiu (`_identidade_do_convidado` + `TENANT_STORE.user_status`).

**Why:** a identidade e por e-mail e cruza organizacoes; qualquer caminho que cria credencial sem prova de caixa e um caminho de tomada de conta.

**How to apply:** antes de criar ou trocar senha por um fluxo sem prova de caixa, classificar a identidade nas TRES fontes (credencial verificada, users, perfil). Credencial nao verificada nao conta como dono. Aceite nunca muda `users.status`. Ver [[froid-seguranca-rigor-maximo]].
