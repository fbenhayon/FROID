# Ficha tecnica: sinais espectrais e cepstrais (MFCC, bandas beta e gama)

Documento de referencia publica. Descreve as medidas de conteudo espectral do
FROID. Nao contem pesos, normalizacoes proprietarias nem limiares de
composicao.

## MFCC — coeficientes cepstrais em escala mel

**O que sao.** Uma representacao compacta do envelope espectral de curto prazo
da fala, em escala de frequencia aproximadamente perceptual. Sao a
representacao padrao em processamento de fala ha decadas — reconhecimento
automatico, identificacao de locutor, analise de qualidade vocal.

Cada coeficiente descreve uma caracteristica do formato do espectro. Os
coeficientes de ordem mais alta, como MFCC7 e MFCC9, carregam informacao de
detalhe do envelope, associada a configuracao do trato vocal e a estabilidade
de timbre.

**O que o FROID reporta.** Alem dos coeficientes, suas derivadas temporais:

- **delta (D)** — a taxa de variacao do coeficiente ao longo do tempo;
- **delta-delta (DD)** — a aceleracao dessa variacao.

Deltas e delta-deltas sao praxe consolidada em processamento de fala: capturam
dinamica, e nao apenas a configuracao instantanea.

**Como se le.** Contra a linha de base do proprio paciente, como todo o resto.
Um coeficiente cepstral nao tem interpretacao absoluta util em contexto
clinico.

**O que nao afirma.** Aceleracao cepstral elevada e um fato de dinamica do
sinal. Descreve-la como "contracao espastica involuntaria das cordas vocais"
excede o que a medida sustenta: essa seria uma afirmacao fisiologica que exige
verificacao instrumental direta — laringoscopia, eletroglotografia — e nao
pode ser inferida do cepstro. A descricao admissivel e de instabilidade de
timbre ou de formante.

## Bandas de modulacao beta (12-30 Hz) e gama (30-80 Hz)

**O que sao.** Energia nas taxas de modulacao da envoltoria da fala nessas
faixas. Nao confundir com bandas de EEG: a homonimia e coincidencia de
nomenclatura de faixa de frequencia, e nao correspondencia com ritmo cortical.
O FROID nao mede atividade cerebral.

Taxas de modulacao da envoltoria relacionam-se a estrutura temporal da fala —
ritmo silabico, transicoes articulatorias, estabilidade da producao.

**O que o FROID reporta.** A energia em cada banda e um indice espectral
normalizado (0-1) que resume a distribuicao entre elas, sempre lido contra a
referencia do paciente.

**O que nao afirma.** Estas bandas nao sao correlatos de estado emocional
validados. Nao ha, ate esta data, estudo publicado que estabeleca ponte entre
essas faixas de modulacao vocal e categoria diagnostica em saude mental. Sao
descritores de estrutura temporal da fala.

## Uma ressalva importante sobre nomenclatura

Varios rotulos historicamente usados em material interno do FROID sugerem
correspondencia fisiologica ou neurologica que a medida nao sustenta —
"contracao espastica", "inundacao autonomica", "shutdown", "sistema nervoso
autonomo". Nenhum desses fenomenos e medido pelo FROID. O que e medido e sinal
acustico e visual. Rotulos desse tipo nao devem aparecer em material voltado
ao usuario nem em saida de produto; onde aparecerem, sao remanescentes a
corrigir.

Ver tambem: [[froid-fronteira-medida-interpretacao]],
[[froid-ficha-tecnica-bioacustica]].
