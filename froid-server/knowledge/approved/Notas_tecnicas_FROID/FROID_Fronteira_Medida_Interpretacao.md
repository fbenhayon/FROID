# A fronteira entre medir e interpretar no FROID

Esta nota governa todas as fichas tecnicas das metricas do FROID. Ela existe
para responder, de forma verificavel, a pergunta que profissionais de saude
fazem com razao: "o que exatamente esse numero e, e o que ele autoriza a
concluir?"

## A regra

O FROID mede sinal. Quem interpreta e o profissional habilitado.

Isso nao e uma frase de cortesia. E uma linha operacional que decide o que o
software pode e nao pode escrever na tela:

| O FROID pode dizer | O FROID nao diz |
| --- | --- |
| "F0 media 18% abaixo da linha de base deste paciente" | "paciente deprimido" |
| "loudness caiu 2 desvios-padrao em relacao a propria referencia" | "embotamento afetivo" |
| "face e voz divergiram em 7 janelas confirmadas" | "o paciente esta reprimindo" |
| "zona 7 com desvio extremo sustentado" | "conflito profundo somatizado" |

A coluna da esquerda e medicao: qualquer pessoa com o sinal bruto e o metodo
chega ao mesmo numero. A coluna da direita e inferencia sobre estado mental de
uma pessoa identificada — e isso e ato privativo de profissional habilitado,
com o registro dele em jogo.

## Por que a linha esta exatamente ai

Tres razoes independentes, e cada uma sozinha bastaria.

**Clinica.** Um construto psicologico nomeado por software cria ancoragem. O
profissional que le "dissociacao" na tela antes de formar a propria impressao
ja nao esta avaliando com independencia. A medida ajuda; o rotulo atrapalha.

**Cientifica.** F0, jitter, shimmer, ZCR e MFCC sao medidas com decadas de
literatura e valores de referencia publicados. "Indice de dissociacao" nao tem
validacao nenhuma — nao porque o FROID seja ruim, mas porque a validacao de um
construto exige estudo que ainda nao foi feito. Afirmar antes de validar
compromete tambem o que ja esta bem fundamentado.

**Regulatoria e juridica.** Software que infere construto psicologico e
prescreve conduta se aproxima da definicao de instrumento de avaliacao
psicologica. Software que reporta medida acustica e visual, deixando a
inferencia com o profissional, e instrumentacao — a mesma categoria de uma
balanca, de um ECG ou de um actigrafo.

## O teste de tres perguntas

Antes de qualquer texto novo aparecer para o usuario — na tela, no relatorio,
no FROID Explica — ele passa por estas tres:

1. **Nomeia um construto psicologico?** (dissociacao, somatizacao, repressao,
   embotamento afetivo, resistencia) Se sim, reescrever em termos do sinal.
2. **Prescreve conduta?** ("acolher", "conter", "investigar", "nao forcar",
   "recomenda-se") Se sim, remover. A conduta e do profissional.
3. **Afirma sobre a pessoa, ou sobre a medida?** "O paciente esta X" e
   inferencia. "A metrica Y esta a Z desvios da referencia dele" e medida.

## O que isso preserva

Nada do valor clinico se perde nessa troca. O profissional que ve "loudness
colapsou 2,4 DP e a dissonancia facial-vocal subiu no mesmo corte" tem
exatamente a informacao que precisa — e chega sozinho a hipotese, que e o que
o CRP dele exige de qualquer forma.

O que se perde e a aparencia de que o software sabe da pessoa mais do que pode
saber. Essa aparencia nunca foi ativo: era passivo.

## Referencia comparada

Instrumentos consagrados operam exatamente assim. O eletrocardiografo reporta
intervalo PR e complexo QRS, nao "infarto". O actigrafo reporta movimento e
latencia, nao "insonia". O espirometro reporta VEF1, nao "DPOC". Em todos os
casos o laudo e do profissional, e em todos os casos isso aumentou — nao
reduziu — a adocao clinica do aparelho.

Ver tambem: [[froid-ficha-tecnica-ipm]], [[froid-ficha-tecnica-idm-zonas]],
[[froid-ficha-tecnica-dissonancia]], [[froid-ficha-tecnica-bioacustica]].
