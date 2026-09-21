---
name: froid-commit-assunto-vs-diff
description: "O assunto do commit tem de nomear a maior decisão do diff, não a última etapa que eu executei — o erro aparece ao commitar trabalho herdado de outra sessão"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7f710541-31e7-4249-8600-e7f0012a7abf
  modified: 2026-09-20T14:21:05.745Z
---

Em 19/09/2026 retomei uma sessão interrompida: `explica_clinico.py` já tinha, na
árvore, a revisão inteira do prompt pedida pelo Fábio ("parar de se esconder
atrás de uma covardia"). Eu fiz a última etapa que faltava — consertar um teste
do glossário que a mudança de redação quebrou — e commitei tudo junto com o
assunto *"O teste do glossario volta a afirmar a garantia"*. O corpo inteiro
falava do teste.

O diff eram 104 linhas: **59 do prompt** (regra 7 reescrita, bloco PROIBIDO SE
ESCONDER, A UNICA LINHA QUE NAO SE ATRAVESSA) e **9 do teste**. O Fábio leu e
respondeu "deve ser feita alguma alteração no commit". Estava certo: quem
abrisse o `git log` ou desse `git blame` no prompt cairia num assunto sobre
teste e não descobriria que a fronteira clínica do produto tinha sido reescrita
ali.

A armadilha é específica de **trabalho herdado**: quando eu commito o que outra
sessão deixou na árvore, a minha memória de trabalho contém a etapa que *eu*
fiz, e é ela que sai no assunto. O diff não concorda.

**Why:** rótulo que descreve outra coisa é pior que rótulo nenhum, porque quem
lê confia nele (padrão 2.4 da skill-froid-master) — e o `git log` é justamente
onde alguém vai procurar quando o prompt der problema daqui a meses.

**How to apply:** antes de escrever o assunto, rodar `git diff --cached --numstat`
e deixar o **maior bloco de mudança substantiva** ditar a primeira linha; a
etapa que acabei de fazer vira parágrafo. Se duas decisões separáveis
aparecerem no numstat, é sinal de commit que o dono decide separado
([[skill-froid-master]] §5.1). Corrigir depois é barato quando só a mensagem
está errada — ver [[froid-deploy-topologia]] para o amend sem rebuild.
