# Ficha tecnica: IPM (Indice de Potencia Multimodal)

Documento de referencia publica. Descreve o que o IPM mede e como le-lo. Nao
contem pesos, limiares proprietarios nem parametros de calibracao.

## O que mede

O IPM e um indice composto, em escala 0-100, da **intensidade global de
ativacao** presente na expressao vocal e facial em uma janela de tempo.

Ele responde a pergunta "quanta energia expressiva esta sendo mobilizada
agora?" — e apenas ela. Nao responde "energia para que", "por que", nem "isso
e bom ou ruim". A direcao e assunto do [[froid-ficha-tecnica-idm-zonas]].

Analogia util: o IPM e o tacometro, nao o velocimetro nem a bussola. Mostra a
rotacao do motor. Nao diz para onde o carro vai.

## De que sinais deriva

O IPM e composto a partir do vetor espectral da voz e dos sinais faciais
medidos, agregados sobre todas as zonas de percepcao. As familias de sinal que
o alimentam estao descritas em [[froid-ficha-tecnica-bioacustica]] e
[[froid-ficha-tecnica-espectral-cepstral]] — todas sao medidas acusticas e
visuais padronizadas, nao escalas autorreferidas.

A composicao especifica (pesos e normalizacao) e proprietaria e nao consta
deste documento. O que consta, e o que importa para o uso clinico, e a
natureza do que entra: sinal fisico medido, nao resposta a questionario.

## Como se le

**Sempre contra a propria linha de base do paciente.** O IPM nao tem norma
populacional e o FROID nao afirma que exista. Um IPM de 62 nao significa nada
isoladamente; um IPM de 62 em um paciente cuja linha de base e 38 significa
uma elevacao de magnitude mensuravel.

O painel reporta:

- **linha de base** — a referencia daquele paciente, estabelecida em periodo
  de calibracao antes da leitura valer;
- **delta percentual** contra essa linha de base;
- **escore z** — de quantos desvios-padrao da propria referencia a leitura se
  afastou;
- **cobertura e confianca** da amostra na janela.

Os avisos de "Alerta" (z >= 2) e "Critico" (z >= 3) sinalizam **afastamento
estatistico da referencia do proprio paciente**. Nao sao categorias clinicas,
nao classificam a pessoa e nao implicam gravidade clinica: implicam que aquela
janela se afastou do padrao habitual daquele individuo o suficiente para
merecer o olhar do profissional.

Quando a cobertura da amostra fica abaixo de 80% ou a confianca abaixo de 70%,
a leitura e marcada como "Revisar qualidade" e nao deve ser usada. Ruido,
microfone ruim, rede instavel e iluminacao ruim produzem numero — e o FROID
prefere dizer que o numero nao presta a deixar o profissional confiar nele.

## O que o IPM nao afirma

- Nao e medida de humor, de motivacao subjetiva nem de engajamento terapeutico.
- Nao distingue a origem da ativacao. IPM alto e compativel com entusiasmo,
  raiva, ansiedade, esforco vocal, sala barulhenta e cafe em excesso.
- IPM baixo nao e "embotamento", "shutdown" nem "dissociacao". E menos energia
  expressiva na janela medida, e as causas possiveis incluem cansaco, timidez,
  cultura, microfone distante e o paciente estar simplesmente ouvindo.
- Nao tem valor diagnostico, nem isolado nem combinado.
- Nao substitui, nao replica e nao aproxima nenhum instrumento psicometrico
  validado.

## Limites conhecidos

Sensivel a qualidade de captacao (microfone, distancia, ganho automatico,
supressao de ruido do navegador). Sensivel a lingua e a estilo prosodico
cultural. A linha de base precisa de tempo de fala suficiente para estabilizar
— leituras antes disso sao exibidas como pendentes, nao como zero. Nao ha, ate
esta data, estudo de validade convergente do IPM contra instrumento
psicometrico validado; enquanto nao houver, o indice deve ser tratado como
medida de sinal e nao como estimador de construto.

## Estabilizacao temporal

O valor exibido nao e o instante: e uma agregacao ponderada de microjanelas
recentes, para que a tela nao oscile a cada respiracao. O racional clinico
dessa escolha esta em [[froid-estabilizacao-clinica-da-tela]].
