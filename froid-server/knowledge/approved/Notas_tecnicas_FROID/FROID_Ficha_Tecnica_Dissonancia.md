# Ficha tecnica: dissonancia facial-vocal

Documento de referencia publica. Descreve o que o FROID conta como evento de
dissonancia e o que esse numero autoriza a concluir.

## O que mede

Dissonancia, no FROID, e um **evento observavel de divergencia entre canais
medidos**: os sinais faciais e os sinais vocais apontam em direcoes diferentes
na mesma janela de tempo.

O que o campo "dissonancias" reporta e uma **contagem de eventos**, com
severidade agregada e as categorias de marcador envolvidas. E uma medida de
co-ocorrencia entre canais, nao um julgamento sobre a pessoa.

## Como um evento e registrado

O registro exige tres condicoes, e cada uma existe para reduzir falso positivo:

1. **Marcador fora da banda.** Ao menos um marcador ultrapassa sua metrica
   base — o limiar publicado da literatura quando existe, ou a linha de base do
   proprio paciente.
2. **Sinal real.** Marcadores que dependem da forma de onda so sao avaliados
   quando ha voz real captada; marcadores faciais, apenas com Unidades de Acao
   efetivamente medidas. O modo simulado nunca gera evento.
3. **Confirmacao temporal.** A condicao precisa se sustentar em ao menos 2 dos
   3 ultimos ticks de 1 segundo. Um pico de um unico tick e tratado como
   transitorio e nao confirma evento.

Um evento adicionalmente marcado como **dissonancia multipla** e aquele em que
dois ou mais marcadores de **categorias distintas** ocorrem juntos. A exigencia
de categorias distintas evita contar como confirmacao cruzada dois marcadores
fortemente correlacionados entre si — jitter e shimmer, por exemplo, medem
faces do mesmo fenomeno e nao se confirmam mutuamente.

## Os marcadores e suas ancoras

Os marcadores de perturbacao vocal usam limiares derivados de valores de
referencia publicados (Praat): jitter local em torno de 1% e shimmer local em
torno de 3,8% para voz saudavel. O FROID adota margens mais largas que esses
valores porque seu estimador por quadros e mais grosseiro que a medicao de
laboratorio — a escolha e deliberadamente conservadora, para errar no sentido
de nao alarmar.

Os marcadores prosodicos (variabilidade e desvio de F0), de energia
(loudness) e de timbre (ZCR) sao avaliados contra a **linha de base do proprio
paciente**, nunca contra norma populacional.

## O que a contagem nao afirma

- **Dissonancia nao e mentira, disfarce nem repressao.** O FROID nao detecta
  engano e nao faz qualquer afirmacao sobre intencao. Divergencia entre canais
  e um fato de medicao com muitas causas possiveis, das quais a maioria e
  banal.
- Nao e indicador de dissociacao, somatizacao ou qualquer quadro clinico.
- Contagem alta nao significa sessao "pior". Pode significar sessao mais
  mobilizada, ou captacao pior, ou paciente que gesticula e fala ao mesmo
  tempo.
- A severidade agregada e uma intensidade de sinal normalizada, nao uma escala
  de gravidade clinica.
- Nao ha, ate esta data, estudo de validade convergente da contagem de
  dissonancias contra desfecho clinico ou instrumento validado.

## Limites conhecidos

Depende de captacao simultanea boa nos dois canais; a perda de um deles zera a
possibilidade do evento sem sinalizar ausencia de fenomeno. Expressividade
facial e prosodica tem forte variacao cultural e individual. Pacientes com
condicoes neurologicas, motoras ou de voz podem produzir divergencia
persistente entre canais por razoes que nao tem relacao com afeto. Sessoes
curtas nao permitem linha de base estavel e, portanto, nao produzem leitura
confiavel dos marcadores relativos.

Ver tambem: [[froid-fronteira-medida-interpretacao]].
