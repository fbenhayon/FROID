---
name: froid-derivadas-zeradas-decisao-adiada
description: DMFCC/DDMFCC em 0.0000 tem causa achada e correção pronta, mas Fábio adiou a instalação em 23/09/2026 para juntar evidência de mais sessões
metadata:
  type: project
---

Em 22–23/09/2026 apurei por que os quatro campos de derivada cepstral
(`DMFCC7`, `DMFCC9`, `DDMFCC7`, `DDMFCC9`) aparecem cravados em `0.0000` no
painel. **A correção existe, está testada, e NÃO foi instalada por decisão do
Fábio** — ele quer rodar mais sessões antes de decidir.

**A causa, em duas peças:**

- `froid_core.py` resolvia a falta de referência subtraindo o valor dele mesmo
  (`mfcc7 - (previous if previous is not None else mfcc7)`), que dá `0.0` exato;
  `previous_delta_*` nascia `0.0`, e a segunda derivada saía zero pelo mesmo
  caminho.
- `SpectralBandsChart.tsx` lia os campos com um helper `|| 0` e imprimia
  `.toFixed(4)` — mesmo com o motor declarando `null`, a tela escreveria
  `0.0000`. **Esta metade já está no ar** (commit `c9445b9`, 23/09).

Havia ainda uma guarda que não guardava: o bloco que zerava a referência na
troca de ramo real↔proxy rodava **depois** do cálculo e era sobrescrito duas
linhas abaixo. Código morto descrevendo proteção que nunca aconteceu.

**Erro meu que vale registrar:** afirmei primeiro que a troca de ramo zerava a
referência a cada tique, sem conferir a ordem de execução. Era falso. Ver
[[froid-site-afirma-o-que-o-painel-nao-faz]] — mesma falta, outro domínio.

**Why:** instalar mexe no backend, e rebuild de backend desloga todo
profissional logado, inclusive em atendimento ([[froid-deploy-topologia]]). E o
efeito visível é contraintuitivo: onde hoje há `0.0000`, passará a haver "sem
apuração" — vai *parecer* regressão enquanto o sinal chegar esparso.

**How to apply:** não reinvestigar nem "corrigir" de novo por conta própria. Se
os zeros voltarem ao assunto, perguntar ao Fábio se a decisão mudou. Um zero em
proxy consecutivo é legítimo (o cálculo é clipado em zero abaixo do piso) — o
defeito é o zero por falta de janela anterior. Antes de qualquer build, marcar
as imagens em execução como rollback: não existe ponto de volta exato do
backend que está rodando.
