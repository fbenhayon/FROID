---
name: froid-sessoes-simultaneas
description: Duas sessões no mesmo repositório — o git reset de uma apaga o trabalho não commitado da outra, e como não perder de novo
metadata:
  node_type: memory
  type: project
---

Em 05/09/2026 duas sessões trabalhavam no mesmo clone: uma no `froid-site/`,
outra no `froid-server/`. A do site rodou `git reset` para dividir um commit
(fluxo da seção 5.1 da skill). O reset apagou as alterações **não commitadas**
do `froid-server/main.py` — quatro horas de trabalho na correção do
`_safe_float`, já revisado e testado.

O reflog registrou: `reset: moving to 6bb81723`. Não houve erro nem aviso; o
arquivo simplesmente voltou ao estado do HEAD, e o `git status` passou a mostrar
a árvore limpa como se nada tivesse existido.

**O que salvou:** os quatro arquivos de teste eram **novos** (não rastreados), e
`git reset` não remove arquivo não rastreado. Foram eles — 673 linhas que
descrevem o que o código tem de fazer — que permitiram refazer o `main.py` e
*provar* a equivalência, em vez de refazer de memória e torcer.

**Why:** o territóro combinado (`froid-server/` para uma sessão, `froid-site/`
para outra) protege contra edição concorrente do mesmo arquivo, mas **não**
protege contra comando de git, que age no repositório inteiro. Dividir escopo
por pasta dá uma falsa sensação de isolamento.

**How to apply:**

- **Commitar cedo.** Enquanto houver outra sessão aberta, trabalho não
  commitado é trabalho em risco. Um commit intermediário custa nada e pode ser
  reorganizado depois pelo fluxo da seção 5.1.
- **Antes de `git reset`, `checkout` ou `stash`, verificar o que mais está
  modificado:** `git status --short` mostra o repositório todo, não só a sua
  pasta. Se aparecer arquivo de outra frente, pare e avise.
- **Escrever o teste antes** ajuda duas vezes: além de guardar a garantia, ele
  sobrevive ao reset por ser arquivo novo, e vira a especificação para
  reconstruir.
- **Antes do deploy, fechar as outras sessões.** O `git pull` no servidor não
  deve pegar um estado pela metade.
- Ao publicar, lembrar que `git push` envia **toda a fila** de commits abaixo do
  seu — commit de outra sessão que ainda não subiu vai junto. Isso não é perda
  (o contrário: passa a estar guardado), mas precisa ser dito a quem lê, sem a
  palavra "levou junto", que assusta e sugere destruição.

Relacionado: [[froid-deploy-topologia]], [[froid-deploy-hetzner]].
