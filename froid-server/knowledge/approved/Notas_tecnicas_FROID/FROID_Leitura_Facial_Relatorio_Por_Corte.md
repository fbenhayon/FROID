# Leitura facial no FROID: captura, referencia individual e relatorio por corte

Documento de referencia publica, atualizado em 08/11/2026. Explica como o
FROID Psique capta o rosto do paciente, como o relatorio da sessao apresenta
os movimentos faciais e o que ainda esta em medicao.

## Como o rosto e captado

A captura acontece no navegador do paciente, a partir do video autorizado. A
camera filma a cerca de 24 quadros por segundo, mas a leitura facial analisa
cerca de **3 quadros por segundo**. Cada quadro vira coeficientes numericos de
movimento, e o servidor os descreve em 16 Unidades de Acao (o vocabulario do
FACS). Quinze tem mapeamento aproximado; a AU23 esta sem apuracao. Nao e
codificacao FACS certificada.

As combinacoes sao organizadas em **sete familias descritivas**: sorriso e
padroes compativeis com tristeza, raiva, medo, surpresa, nojo e assimetria
compativel com desprezo. "Compativel" quer dizer que a configuracao do
movimento se parece com o catalogo; nao quer dizer que a pessoa sente aquilo.

Um padrao so vira **evento registrado** quando se repete em pelo menos dois
quadros distintos. Isso evita registrar um quadro isolado, mas tambem deixa
passar movimentos brevissimos.

## Microexpressoes

O FROID **nao detecta microexpressoes**. Microexpressoes duram de 40 a 500
milissegundos; a 3 quadros por segundo, a maioria delas cai entre dois quadros.
Para registrar movimentos faciais breves seriam necessarios 25 a 30 quadros
por segundo, e mesmo assim a deteccao de microexpressoes em conversa real com
webcam continua sendo campo de pesquisa. O aumento da taxa de captura esta em
estudo e, se vier, sera anunciado como "movimentos faciais breves", nao como
deteccao de microexpressoes.

## Referencia facial individual (modo de medicao)

Desde 08/11/2026, o FROID calibra uma **referencia facial do proprio
paciente**, nos primeiros 60 segundos com rosto medido — a mesma janela de
calibracao da voz. Para cada Unidade de Acao, guarda o valor tipico em repouso
(mediana) e o quanto ele oscila naturalmente (dispersao robusta). A
calibracao precisa de pelo menos 30 quadros com rosto; abaixo disso, o
relatorio declara a referencia como insuficiente.

Por que isso importa: os limiares atuais sao os mesmos para todo rosto. Um
paciente com a sobrancelha naturalmente baixa, de oculos ou com luz lateral
pode parecer "sempre ativo"; outro, de movimentos sutis, quase nunca atinge o
limiar. A regua certa e a da propria pessoa.

**Nesta fase a referencia nao filtra nem reclassifica nada.** Ela apenas mede
quanto cada movimento se afastou do repouso do paciente, e cada evento passa a
guardar o seu "afastamento de pico da referencia". O limiar que separa
movimento de oscilacao natural **ainda nao foi definido**: sera escolhido a
partir de sessoes reais, e nao arbitrado. So depois disso o relatorio passara
a mostrar apenas os movimentos acima do limiar.

## Como o relatorio apresenta o rosto

A secao "Registros faciais" do relatorio mostra os **movimentos faciais por
corte**:

- cada corte da sessao (os automaticos de 10 minutos e os manuais), com a
  contagem por familia, ou "nenhum padrao facial registrado neste corte";
- cada evento com o minuto da sessao (mm:ss), a familia, o numero de quadros e
  a duracao;
- a **fala no momento**: a ultima linha da transcricao dita ate aquele
  segundo, quando a transcricao tem o instante de cada linha;
- a **qualidade da captura**: em quantas amostras da sessao o rosto foi
  realmente medido. Abaixo de 50%, a ausencia de padroes nao e informativa;
- o **estado da referencia facial individual**.

O minuto do evento e o instante em que ele chegou ao painel, que pode ficar
alguns segundos depois do inicio do movimento. Relatorios anteriores a
08/11/2026 nao tem esse minuto; seus eventos aparecem como "sem instante da
sessao registrado", sem serem encaixados por estimativa.

Os valores tecnicos das Unidades de Acao ("medidas subjacentes") deixaram de
ser exibidos no relatorio; continuam gravados no servidor. Os limites da
leitura facial ficam num link para a pagina de etica.

## O que a leitura facial nao afirma

- Nao comprova emocao, mentira, mascaramento ou conflito interno.
- Nao classifica sorriso como verdadeiro ou falso.
- Nao mede **dissonancia entre rosto e voz**: essa relacao nao foi validada e
  esta sem capacidade de apuracao. O que o FROID oferece e ver os canais lado a
  lado, no mesmo corte; perceber coerencia ou dissonancia e decidir o que fazer
  com ela e papel do profissional.
- "Nenhum padrao registrado" nao prova ausencia de emocao.

Iluminacao lateral, contraluz, oclusao, oculos, barba, angulo da camera, fala
e rede instavel degradam a leitura.

## Perguntas que o FROID Explica pode responder sobre o rosto

- "Em que cortes houve movimentos faciais, e o que estava sendo dito?"
- "A captura facial desta sessao foi boa o bastante para levar em conta?"
- "A referencia facial deste paciente foi calibrada?"
- "Por que o relatorio nao mostra mais os valores das AUs?"
- "O FROID detecta microexpressoes?"

Ver tambem: [[froid-ficha-tecnica-fluencia-e-face]],
[[froid-fronteira-medida-interpretacao]].
