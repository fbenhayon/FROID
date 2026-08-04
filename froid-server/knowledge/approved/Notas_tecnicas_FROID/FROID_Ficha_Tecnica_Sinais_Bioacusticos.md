# Ficha tecnica: sinais bioacusticos (F0, jitter, shimmer, ZCR, loudness)

Documento de referencia publica. Estas sao as medidas mais bem estabelecidas do
conjunto FROID: todas possuem definicao padronizada, decadas de literatura e
valores de referencia publicados, independentes do FROID.

## F0 — frequencia fundamental

**O que e.** A taxa de vibracao das pregas vocais, em Hz. E a medida acustica
correlata do que se percebe como altura da voz.

**O que o FROID reporta.** A F0 media da janela e duas derivadas:

- **variabilidade (coeficiente de variacao)** — a razao entre dispersao e media
  da F0 na janela. Fala expressiva natural situa-se tipicamente na faixa de
  0,08 a 0,35. Valores muito baixos indicam fala monotona; muito altos,
  instabilidade prosodica.
- **desvio contra a linha de base** — quanto a F0 daquela janela se afastou da
  referencia do proprio paciente.

**O que nao afirma.** F0 baixa nao e tristeza. Monotonia prosodica nao e
"achatamento afetivo" — e menor variacao de altura na janela medida, e as
causas incluem fadiga, leitura em voz alta, resfriado, estilo pessoal e
cultura. A F0 absoluta varia enormemente por sexo, idade e anatomia; e por
isso que o FROID a le contra a referencia do proprio paciente e nao contra
norma populacional.

## Jitter — perturbacao de periodo

**O que e.** A irregularidade ciclo a ciclo do periodo da onda glotica. Mede
estabilidade da vibracao das pregas vocais.

**Referencia.** Voz saudavel apresenta jitter local abaixo de aproximadamente
1% (limiar classico do Praat, 1,04%). O FROID adota margem mais larga porque
seu estimador por quadros e mais grosseiro que a medicao de laboratorio.

**O que nao afirma.** Jitter elevado indica instabilidade glotica — um fato
fisiologico da fonacao. Nao indica ansiedade, nao indica emocao especifica e
nao tem valor diagnostico. Alteracao de voz por causa organica (laringite,
refluxo, tabagismo, patologia de prega vocal) produz jitter elevado sem
qualquer relacao com estado psiquico.

## Shimmer — perturbacao de amplitude

**O que e.** A irregularidade ciclo a ciclo da amplitude. Correlato acustico
da rouquidao e do esforco vocal.

**Referencia.** Limiar classico do Praat em torno de 3,81% para voz saudavel;
o FROID novamente adota margem mais larga, pela mesma razao.

**O que nao afirma.** Mesmas ressalvas do jitter. Jitter e shimmer medem faces
correlacionadas do mesmo fenomeno e, no motor de dissonancia, pertencem
deliberadamente a mesma categoria — para que a ocorrencia conjunta dos dois
nao seja contada como confirmacao entre sistemas independentes.

## ZCR — taxa de cruzamentos por zero

**O que e.** Quantas vezes o sinal cruza o eixo zero por unidade de tempo. E
um descritor de conteudo espectral: correlaciona com a proporcao de energia em
altas frequencias e, perceptualmente, com o brilho ou a soprosidade do timbre.

**O que o FROID reporta.** O desvio do ZCR contra a linha de base do paciente.
Descricoes admissiveis sao de timbre — voz mais opaca ou mais soprosa —, nunca
de estado mental.

## Loudness

**O que e.** Intensidade percebida, em LUFS. Diferente de amplitude bruta:
incorpora ponderacao perceptual.

**O que o FROID reporta.** O desvio contra a linha de base do paciente, em dB.

**O que nao afirma.** Queda de loudness nao e "colapso" nem "embotamento". E
menos intensidade na janela, e a primeira hipotese a descartar e sempre
tecnica: o paciente se afastou do microfone, mudou de postura, o ganho
automatico do navegador atuou, ou a supressao de ruido cortou sinal.

## Sub-harmonicos

**O que e.** Energia em componentes abaixo da fundamental, associada a
irregularidade do padrao vibratorio e a fenomenos de duplicacao de periodo.

**O que nao afirma.** E um descritor de qualidade vocal. Nao possui, nesta
aplicacao, correspondencia validada com estado psiquico.

## Limites comuns a todos

Todas estas medidas dependem criticamente da cadeia de captacao: microfone,
distancia, ganho automatico, supressao de ruido, codec e perda de pacote. O
FROID marca leituras com cobertura abaixo de 80% ou confianca abaixo de 70%
como nao utilizaveis, e essa marcacao deve ser respeitada — numero ruim e pior
que numero ausente, porque parece informacao.

Nenhuma dessas medidas, isoladamente ou em conjunto, constitui teste
diagnostico. Elas descrevem propriedades fisicas da voz produzida naquela
janela.

Ver tambem: [[froid-fronteira-medida-interpretacao]],
[[froid-ficha-tecnica-espectral-cepstral]].
