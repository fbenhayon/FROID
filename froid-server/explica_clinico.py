# -*- coding: utf-8 -*-
"""FROID Explica clinico: o glossario do painel, as zonas e o contrato de resposta.

POR QUE ESTE MODULO EXISTE
--------------------------
06/09/2026. Dentro de uma sessao, um profissional perguntou ao FROID Explica
"o que quer dizer isso IND. ESPECTRAL 0.110". A resposta foi:

    "A metrica IND. ESPECTRAL 0.110 nao esta diretamente mencionada nas
     informacoes disponiveis sobre os biomarcadores ou metricas da sessao."

A resposta era honesta e o defeito era nosso. O painel escreve na tela
`IND. ESPECTRAL`; o contexto enviado ao modelo carrega `spectral_band_index`.
Camada nenhuma traduzia um no outro — o profissional le, na nossa propria tela,
um nome que o nosso proprio assistente nunca recebeu. E o padrao 2.1 do rigor
de engenharia: a peca existe, esta correta, e nada a consome.

Na mesma conversa ele perguntou "o que quer dizer e como interpreto ZONAS
Zona 12". A resposta parafraseou os avisos da ficha tecnica — "as zonas nao sao
diagnosticos" — e nao disse o unico fato que a pergunta pedia: a Zona 12 e o
eixo "Crencas e Acoes Conflitantes vs. Crencas e Acoes Congruentes", ela e uma
das seis zonas com regra facial propria (AU4 + AU7), e quando essa regra
dispara o desvio vocal daquela zona entra no escore multiplicado por 2,5.
Tudo isso ja estava no codigo, em `froid_core.PERCEPTION_ZONES` e em
`froid_facs.detect_facial_dissonance`, e nada disso chegava ao Explica.

O QUE ESTE MODULO GARANTE
-------------------------
1. **O rotulo da tela e uma chave de busca.** Quem pergunta por "IND.
   ESPECTRAL", "SUB-H 5-12" ou "DNA FLOOD" recebe a ficha daquele indice, com
   a chave interna, o que de fato entra na conta e a escala.
2. **Valor medido ou ausencia declarada — nunca preenchido.** Chave ausente do
   contexto e chave presente valendo `None` sao coisas diferentes, e as duas
   sao ditas com o nome que tem. Zero aqui seria uma afirmacao sobre a voz do
   paciente (regra 1.1).
3. **As doze zonas vem de `froid_core`, nao de uma copia.** Numero com duas
   fontes diverge em silencio (padrao 2.7).
4. **O contrato de resposta e explicito.** Antes, a unica exigencia de forma
   era "de modo objetivo" — e "objetivo" produziu dois paragrafos de ressalva
   sobre uma pergunta que pedia uma leitura. O contrato abaixo diz o que a
   resposta precisa conter para ser util a quem esta com um paciente na frente.

O QUE ELE DELIBERADAMENTE NAO FAZ
---------------------------------
Nao amplia o que o FROID afirma. Toda a profundidade abaixo e sobre a MEDIDA —
o que entra na conta, contra que referencia, o que a move, o que a invalida, e
que pergunta clinica ela habilita. A ponte da medida para a hipotese continua
sendo do profissional, e a secao "limite" de cada ficha existe para dizer
exatamente onde a medida para.

Ver `knowledge/approved/Notas_tecnicas_FROID/FROID_Fronteira_Medida_Interpretacao.md`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import froid_core


# ---------------------------------------------------------------------------
# As doze zonas, da fonte
# ---------------------------------------------------------------------------

# Uma fonte so. A tentacao de escrever os doze eixos aqui como texto e
# exatamente o espelho de numero da secao 2.7: a lista sobreviveria a uma
# renomeacao no motor e o Explica passaria a ensinar o nome antigo.
ZONAS: Dict[int, str] = dict(froid_core.PERCEPTION_ZONES)

MODELOS_DE_COMPROMISSO: Dict[int, Dict[str, Any]] = dict(froid_core.COMMITMENT_MODELS)

CORES_DE_DESVIO: Tuple[Tuple[str, str], ...] = (
    ("BRANCO", "desvio <= -0,50 — banda com energia abaixo da linha de base"),
    ("AZUL", "-0,50 a 0,50 — desequilibrio baixo"),
    ("VERDE", "0,50 a 1,50 — desequilibrio medio"),
    ("AMARELO", "1,50 a 3,00 — desequilibrio alto"),
    ("VERMELHO", "acima de 3,00 — desequilibrio extremo"),
    ("PRETO", "energia vocal media acima do dobro da linha de base (excesso global)"),
    ("CINZA", "nenhuma banda passou de 0,30 de desvio (energia distribuida)"),
)

# As seis regras faciais que existem hoje, por zona. Copia deliberada e travada:
# `detect_facial_dissonance` e codigo imperativo, nao tabela, e extrair a tabela
# de la seria refatorar um motor em producao dentro de uma tarefa de texto.
# `tests/test_explica_clinico_glossario.py` confronta cada linha contra o fonte
# de `froid_facs.py` e falha quando as duas divergirem.
REGRAS_FACIAIS: Dict[int, Tuple[Tuple[str, ...], str]] = {
    3: (("AU15", "AU12"), "cantos labiais em queda sob esforco de sorriso"),
    6: (("AU14", "AU10"), "expressao unilateral (assimetria acima de 0,25)"),
    7: (("AU12", "AU23", "AU24"), "sorriso sobre compressao labial"),
    8: (("AU1", "AU2", "AU5"), "assinatura de sobressalto durante fala controlada"),
    9: (("AU23", "AU24"), "labios pressionados com face aplainada (expressividade < 0,20)"),
    12: (("AU4", "AU7"), "sobrancelhas contraidas com palpebras tensionadas"),
}


# ---------------------------------------------------------------------------
# O de-para do painel
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Indice:
    """Uma linha da tabela de metricas do painel, com o que o modelo precisa.

    `rotulo` e literalmente o que esta escrito na tela do profissional.
    `chave` e o nome do campo no contexto enviado pelo painel — o elo que
    faltava. `marcador` e a chave em `all_markers`, quando o servidor calcula
    faixa para aquele indice; vazio quando nao ha regua.
    """

    rotulo: str
    chave: str
    unidade: str
    medida: str
    leitura: str
    abre: str
    limite: str
    marcador: str = ""
    sinonimos: Tuple[str, ...] = field(default_factory=tuple)


# Quantas fichas longas entram no prompt. Oito e o que cabe sem empurrar a
# transcricao e o contexto cientifico para fora da janela do modelo; uma
# pergunta que cite trinta rotulos recebe as oito primeiras e o AVISO do que
# ficou de fora, nunca um recorte silencioso.
MAX_FICHAS = 8


_BASE_DO_PACIENTE = (
    "Toda leitura e contra a linha de base do proprio paciente, medida na "
    "calibracao desta sessao. Nao ha norma populacional para este indice."
)


CATALOGO: Tuple[Indice, ...] = (
    Indice(
        rotulo="CORTE",
        chave="",
        unidade="minutos",
        medida=(
            "Janela temporal decorrida desde o ultimo corte semantico, automatico "
            "ou fechado pelo profissional. Nao e medida de voz nem de face: e o "
            "recorte sobre o qual todas as outras linhas da tabela sao calculadas."
        ),
        leitura=(
            "Toda metrica da tabela e a MEDIA das amostras dentro deste corte. "
            "Corte curto tem poucas amostras e media instavel; corte longo dilui "
            "um pico dentro do periodo inteiro."
        ),
        abre=(
            "Quando um valor parecer estranho, o primeiro cruzamento e com o "
            "corte: fechar o corte no momento em que algo aconteceu na sala "
            "separa o trecho e faz a media daquele trecho existir sozinha."
        ),
        limite="Nao mede nada do paciente. E o denominador das outras medidas.",
    ),
    Indice(
        rotulo="IPM",
        chave="ipm_score",
        marcador="ipm_hyper",
        unidade="0 a 100",
        medida=(
            "Indice de Potencia Multimodal. A = media dos desvios ABSOLUTOS das "
            "12 bandas vocais contra a linha de base; C = a ativacao medida no "
            "repouso desta pessoa, nesta sessao, durante a calibracao. "
            "IPM = 100 x sigmoide(k x ln(A / C))."
        ),
        leitura=(
            "50 nao significa 'medio': significa ATIVACAO IGUAL AO REPOUSO DESTA "
            "PESSOA. Acima de 50 e acima do proprio repouso dela, nao acima de "
            "outras pessoas. A escala e logaritmica e simetrica — metade da "
            "ativacao afasta de 50 tanto quanto o dobro. "
            "Um IPM exatamente 50 e constante e sinal de calibracao ausente: sem "
            "repouso medido o motor devolve 50 declaradamente neutro, e nao uma "
            "leitura de equilibrio."
        ),
        abre=(
            "IPM e magnitude sem direcao — quem da a direcao e o IDM, e o par "
            "vale mais que qualquer um dos dois. O cruzamento produtivo e com o "
            "TEMA do corte: a mesma elevacao sobre conteudo administrativo e "
            "sobre uma perda pedem hipoteses diferentes. Perguntas que a leitura "
            "habilita: a subida veio antes ou depois da fala mudar de assunto? "
            "ela se sustentou no corte seguinte ou voltou ao repouso?"
        ),
        limite=(
            "Nao e gravidade, nao e risco, nao classifica a pessoa contra outras "
            "e nao tem validade convergente estabelecida contra instrumento "
            "psicometrico."
        ),
        sinonimos=("indice de potencia multimodal", "potencia multimodal"),
    ),
    Indice(
        rotulo="IDM",
        chave="idm_score",
        unidade="desvio com sinal",
        medida=(
            "Indice de Desvio Multimodal. Media COM SINAL dos desvios das 12 "
            "zonas. Positivo = energia acima da linha de base (hiperativacao); "
            "negativo = abaixo (hipoativacao)."
        ),
        leitura=(
            "E a bussola, e o sinal e a informacao principal. IDM proximo de zero "
            "NAO significa equilibrio: pode ser cancelamento entre zonas que se "
            "moveram em direcoes opostas. E por isso que o mapa das doze zonas "
            "existe ao lado do resumo — o resumo sozinho esconde exatamente esse "
            "caso."
        ),
        abre=(
            "O par (IPM, IDM) tem quatro quadrantes de leitura e cada um sugere "
            "uma pergunta diferente. IPM alto com IDM proximo de zero e dispersao: "
            "muita energia repartida em direcoes contrarias — vale abrir o mapa "
            "zonal e olhar QUAIS zonas se opoem. IPM alto com IDM francamente "
            "negativo e um perfil diferente de IPM alto com IDM positivo, e a "
            "distincao esta visivel no painel."
        ),
        limite=(
            "Mede desequilibrio distributivo, nao valencia emocional. Afastar-se "
            "de zero nao torna a concentracao patologica."
        ),
        sinonimos=("indice de desvio multimodal", "bussola"),
    ),
    Indice(
        rotulo="ZONAS",
        chave="dominant_zone",
        marcador="zone_extreme",
        unidade="numero da zona (1 a 12) e escore de desvio",
        medida=(
            "12 bandas log-espacadas de 65,4 Hz a 1975,5 Hz (a escala cromatica "
            "C2-B6). O desvio de cada zona e "
            "(energia da banda - linha de base da banda) / linha de base, "
            "MULTIPLICADO POR 2,5 quando ha dissonancia facial confirmada naquela "
            "zona. A zona exibida e a de maior desvio absoluto no corte."
        ),
        leitura=(
            "O multiplicador facial e a parte que mais engana: uma zona em 3,2 "
            "pode ser 1,28 de desvio vocal vezes 2,5 de contribuicao facial. "
            "Antes de ler magnitude, verifique se aquela zona esta com dissonancia "
            "facial confirmada — o painel informa. "
            "Persistencia entre janelas vale mais que o pico de uma janela."
        ),
        abre=(
            "O eixo da zona e o vocabulario de leitura, e cada eixo e uma "
            "POLARIDADE, nao um rotulo: a Zona 12 e 'Crencas e Acoes Conflitantes "
            "vs. Crencas e Acoes Congruentes'. Concentracao ali sugere ao "
            "profissional explorar congruencia entre o que o paciente diz querer e "
            "o que relata fazer — como hipotese a testar na conversa, nao como "
            "achado. Seis zonas (3, 6, 7, 8, 9 e 12) tem regra facial propria; as "
            "outras seis so se movem por energia vocal."
        ),
        limite=(
            "Zona nao e diagnostico, nao e tipo de personalidade e nao existe zona "
            "boa ou ruim. O FROID nao mede o que nao foi expresso: ausencia de "
            "sinal e ausencia de sinal, nunca 'conflito latente'."
        ),
        sinonimos=("zona", "zona dominante", "zonas froid", "mapa zonal"),
    ),
    Indice(
        rotulo="TOM",
        chave="emotional_tone",
        unidade="categoria",
        medida=(
            "SEM CAPACIDADE DE APURACAO HOJE. O campo existe no contrato de dados "
            "e o servidor o publica VAZIO de proposito: categorizar tom exigiria "
            "fundir ritmo de fala, semantica e energia vocal sob um criterio "
            "definido e defensavel, e esse criterio nao existe no FROID. Ate "
            "02/09/2026 o campo era sorteado; o sorteio foi removido e nada o "
            "substituiu."
        ),
        leitura=(
            "A tabela mostra '--'. Isso e ausencia declarada, nao tom neutro. Se "
            "algum documento ou tela apresentar um tom categorizado para esta "
            "sessao, e remanescente a corrigir."
        ),
        abre=(
            "O que existe no lugar e melhor decomposto: a transcricao diz o "
            "conteudo, F0 e IPM dizem a ativacao, o mapa zonal diz a distribuicao. "
            "Tom, como sintese, e leitura do profissional."
        ),
        limite="Nao afirme tom emocional a partir deste campo. Ele esta vazio.",
        sinonimos=("tom emocional",),
    ),
    Indice(
        rotulo="P/MIN",
        chave="words_per_minute",
        unidade="palavras por minuto",
        medida=(
            "Palavras por minuto DO PACIENTE, contadas no navegador a partir das "
            "linhas transcritas com prefixo PC dentro do corte. A fala do "
            "profissional (prefixo DR) e excluida."
        ),
        leitura=(
            "Nulo quando o paciente nao tem NENHUMA linha transcrita na janela — e "
            "ausencia de apuracao, nao 'zero palavra por minuto'. Havendo linha, o "
            "valor e medida e vale inclusive quando baixo. "
            "Em 06/09/2026 este numero somava as duas falas: um profissional que "
            "falava rapido elevava o 'ritmo do paciente' sem o paciente dizer "
            "palavra. Corrigido; se um relatorio antigo mostrar cadencia sem fala "
            "do paciente, e daquele defeito."
        ),
        abre=(
            "Cadencia e o marcador mais legivel de mudanca dentro da sessao: "
            "aceleracao, lentificacao e bloqueio aparecem antes na contagem que na "
            "impressao. O cruzamento util e com o corte — o que mudou entre o "
            "corte anterior e este — e com F0."
        ),
        limite=(
            "Depende inteiramente da qualidade da transcricao. Trecho nao "
            "transcrito e trecho nao contado."
        ),
        sinonimos=("palavras por minuto", "cadencia", "ritmo de fala", "wpm"),
    ),
    Indice(
        rotulo="DISSO.",
        chave="dissonance_count",
        marcador="facial_contradiction",
        unidade="contagem de zonas",
        medida=(
            "Quantas zonas, no corte, tem dissonancia facial confirmada: precisa "
            "de AU ativa acima do limiar, detalhe registrado e escore acima do "
            "limiar de reporte. Uma zona sem AU ativa nao entra."
        ),
        leitura=(
            "Nulo quando nenhuma zona foi apurada — diferente de zero, que "
            "significa 'procurei e nao achei'. Cada dissonancia vem de UMA das "
            "seis regras faciais, e a regra diz qual padrao de AUs disparou."
        ),
        abre=(
            "A dissonancia e o rosto contradizendo ou mascarando o afeto — "
            "coocorrencia de AUs incompativeis. O valor esta menos na contagem e "
            "mais em QUAL regra disparou e em que momento da fala: pedir o detalhe "
            "das AUs e cruzar com o que estava sendo dito naquele minuto e a "
            "leitura que a contagem sozinha nao entrega."
        ),
        limite=(
            "Depende de face medida. Iluminacao lateral forte, oclusao, mascara, "
            "oculos escuros e angulo acentuado degradam a leitura e reduzem a "
            "contagem sem que nada tenha mudado no paciente."
        ),
        sinonimos=("dissonancia", "dissonancias", "dissonancia facial", "dissonancia facial-vocal"),
    ),
    Indice(
        rotulo="MFCC7",
        chave="mfcc7",
        unidade="coeficiente",
        medida=(
            "Setimo coeficiente cepstral em escala mel, media do corte. Descreve "
            "detalhe do envelope espectral de curto prazo, associado a "
            "configuracao do trato vocal e a estabilidade de timbre."
        ),
        leitura=(
            "Coeficiente cepstral nao tem interpretacao absoluta util em contexto "
            "clinico. " + _BASE_DO_PACIENTE
        ),
        abre=(
            "Ganha relevancia quando se move JUNTO de outros canais: pausas mais "
            "longas, menor variacao de F0, alteracao de ZCR. Isolado, uma variacao "
            "de MFCC7 e tao compativel com troca de microfone quanto com mudanca "
            "de estado."
        ),
        limite=(
            "Nao existe limiar de MFCC7 para nenhuma condicao clinica. Associa-lo "
            "a 'risco depressivo' por si so excede o que a medida sustenta."
        ),
    ),
    Indice(
        rotulo="MFCC9",
        chave="mfcc9",
        unidade="coeficiente",
        medida="Nono coeficiente cepstral em escala mel, media do corte.",
        leitura=_BASE_DO_PACIENTE,
        abre=(
            "Usado como marcador complementar do MFCC7. A informacao esta na "
            "COMBINACAO dos dois e nas derivadas, nao no valor de um deles."
        ),
        limite=(
            "Nao ha estudo publicado que ligue MFCC9 a ansiedade somatica de forma "
            "aplicavel a uma leitura individual."
        ),
    ),
    Indice(
        rotulo="DMFCC7",
        chave="mfcc7_delta",
        unidade="coeficiente por segundo",
        medida="Delta: taxa de variacao do MFCC7 entre amostras consecutivas.",
        leitura=(
            "Delta descreve DINAMICA, e nao configuracao instantanea. Delta alto "
            "com coeficiente estavel significa que o timbre esta oscilando em "
            "torno do mesmo ponto."
        ),
        abre=(
            "Praxe consolidada em processamento de fala. Util para separar "
            "'mudou de estado' de 'esta instavel no mesmo estado' — duas leituras "
            "clinicas diferentes que o coeficiente sozinho confunde."
        ),
        limite="Sem interpretacao absoluta. Contra a base do paciente.",
        sinonimos=("delta mfcc7",),
    ),
    Indice(
        rotulo="DMFCC9",
        chave="mfcc9_delta",
        unidade="coeficiente por segundo",
        medida="Delta: taxa de variacao do MFCC9 entre amostras consecutivas.",
        leitura="Ver DMFCC7 — mesma natureza, outro coeficiente.",
        abre="Lido em par com DMFCC7. Divergencia entre os dois deltas e a informacao.",
        limite="Sem interpretacao absoluta. Contra a base do paciente.",
        sinonimos=("delta mfcc9",),
    ),
    Indice(
        rotulo="DDMFCC7",
        chave="mfcc7_delta_delta",
        marcador="mfcc7_spastic",
        unidade="coeficiente por segundo ao quadrado",
        medida="Delta-delta: aceleracao da variacao do MFCC7.",
        leitura=(
            "Tem faixa calculada pelo servidor. Aceleracao cepstral elevada e um "
            "fato de DINAMICA DO SINAL."
        ),
        abre=(
            "Descreve instabilidade de timbre ou de formante — que e o que a "
            "medida sustenta, e ja e util: instabilidade sustentada durante um "
            "tema e um recorte temporal para reouvir."
        ),
        limite=(
            "A descricao 'contracao espastica involuntaria das cordas vocais' "
            "EXCEDE a medida: seria afirmacao fisiologica, e exigiria verificacao "
            "instrumental direta (laringoscopia, eletroglotografia). O nome interno "
            "do marcador ainda carrega esse termo; nao o repita ao profissional."
        ),
        sinonimos=("delta delta mfcc7", "aceleracao cepstral mfcc7"),
    ),
    Indice(
        rotulo="DDMFCC9",
        chave="mfcc9_delta_delta",
        marcador="mfcc9_spastic",
        unidade="coeficiente por segundo ao quadrado",
        medida="Delta-delta: aceleracao da variacao do MFCC9.",
        leitura="Ver DDMFCC7. Mesma faixa, mesma ressalva de nomenclatura.",
        abre="Ver DDMFCC7.",
        limite="Ver DDMFCC7: o rotulo interno afirma fisiologia que a medida nao sustenta.",
        sinonimos=("delta delta mfcc9", "aceleracao cepstral mfcc9"),
    ),
    Indice(
        rotulo="F0 MED.",
        chave="f0_mean",
        marcador="f0_baseline_dev",
        unidade="Hz",
        medida=(
            "Mediana da frequencia fundamental dos quadros VOZEADOS do corte "
            "(quadros de 40 ms, salto de 20 ms). Quadro sem vozeamento nao entra "
            "na conta."
        ),
        leitura=(
            "Mediana, nao media: um quadro com estimativa errada nao arrasta o "
            "valor. O servidor calcula faixa para o desvio de F0 contra a linha de "
            "base, e existe marcador separado para a VARIABILIDADE (coeficiente de "
            "variacao) — as duas coisas se movem independentemente."
        ),
        abre=(
            "A variabilidade costuma dizer mais que o valor: F0 estavel no mesmo "
            "patamar e achatamento prosodico; F0 no mesmo patamar com "
            "variabilidade alta e outra coisa. O cruzamento com P/MIN separa "
            "aceleracao de elevacao."
        ),
        limite=(
            "F0 e fortemente determinada por sexo, idade e anatomia. Comparacao "
            "entre pacientes nao tem sentido; comparacao do paciente consigo "
            "mesmo, tem."
        ),
        sinonimos=("f0", "frequencia fundamental", "pitch", "f0 media"),
    ),
    Indice(
        rotulo="ZCR",
        chave="zcr",
        marcador="zcr_dev",
        unidade="taxa",
        medida=(
            "Taxa de cruzamento por zero: quantas vezes a forma de onda troca de "
            "sinal, dividida pelo dobro do numero de amostras da janela."
        ),
        leitura=(
            "Sobe com conteudo de alta frequencia. Fricativas (/s/, /f/, /ch/) "
            "elevam ZCR por razao puramente fonetica — um trecho com muitas "
            "sibilantes sobe sem nada ter mudado no paciente."
        ),
        abre=(
            "Util como detector de ARTEFATO antes de ser marcador clinico: "
            "ZCR fora da faixa sem nenhum outro canal acompanhando aponta "
            "microfone, ambiente ou supressao de ruido, e essa e uma conclusao "
            "acionavel — ajustar a captura salva a leitura da sessao inteira."
        ),
        limite=(
            "Alteracao isolada de ZCR nao sustenta leitura clinica. Sozinha, ela "
            "mede o canal."
        ),
        sinonimos=("taxa de cruzamento por zero", "cruzamento por zero"),
    ),
    Indice(
        rotulo="JITTER",
        chave="jitter",
        marcador="jitter",
        unidade="razao adimensional",
        medida=(
            "Perturbacao relativa media do PERIODO: media de |diferenca entre "
            "periodos consecutivos| dividida pelo periodo medio, sobre os quadros "
            "vozeados. Quando nao ha PCM real do paciente, o motor cai num ramo de "
            "substituicao derivado do vetor espectral — e o campo de procedencia "
            "`voice_features_source` diz qual ramo produziu o numero."
        ),
        leitura=(
            "ATENCAO A COMPARACAO: os periodos vem de quadros de 40 ms com salto "
            "de 20 ms, nao ciclo a ciclo. Isto NAO e o jitter local do Praat, e "
            "limiares normativos daquela literatura (a faixa de 1% e afins) NAO se "
            "aplicam a este numero. " + _BASE_DO_PACIENTE
        ),
        abre=(
            "Tem faixa calculada pelo servidor, o que o torna um dos poucos "
            "indices com regua explicita na tela. Ganha sentido sustentado junto "
            "de Shimmer, alteracao de F0 e mudanca de cadencia — a coocorrencia e "
            "que e o sinal."
        ),
        limite=(
            "Nao e medida percentual normativa e nao autoriza hipotese laringea. "
            "Para limiar normativo seria necessaria uma camada de extracao "
            "ciclo a ciclo validada, que nao existe hoje."
        ),
        sinonimos=("perturbacao de periodo",),
    ),
    Indice(
        rotulo="SHIMMER",
        chave="shimmer",
        marcador="shimmer",
        unidade="razao adimensional",
        medida=(
            "Perturbacao relativa media da AMPLITUDE: media de |diferenca entre "
            "amplitudes RMS de quadros vozeados consecutivos| dividida pela "
            "amplitude media. Mesma ressalva de ramo do Jitter."
        ),
        leitura=(
            "Nao e shimmer em dB e nao se compara a limiar de literatura fonetica, "
            "pela mesma razao do Jitter: a unidade de analise e o quadro, nao o "
            "ciclo glotal. " + _BASE_DO_PACIENTE
        ),
        abre=(
            "Tem faixa propria no servidor e categoria propria ('Perturbacao "
            "vocal') na contagem de dissonancias — Jitter e Shimmer contam como "
            "UMA categoria, nao duas, justamente porque sao correlacionados."
        ),
        limite="Ver Jitter. Sem camada fisica validada, nao ha limiar normativo.",
        sinonimos=("perturbacao de amplitude",),
    ),
    Indice(
        rotulo="DELTA",
        chave="spectral_delta_0_4hz",
        unidade="fracao 0 a 1",
        medida=(
            "Fracao da energia do espectro de MODULACAO do envelope da fala na "
            "faixa 0,5-4 Hz, sobre a energia total de modulacao."
        ),
        leitura=(
            "NAO E EEG. A homonimia com as bandas corticais e coincidencia de "
            "nomenclatura de faixa de frequencia; o FROID nao mede atividade "
            "cerebral. Taxa de modulacao da envoltoria descreve estrutura temporal "
            "da fala — a faixa em torno de 4 Hz e a do ritmo silabico."
        ),
        abre=(
            "As cinco bandas somam a distribuicao da modulacao. O que informa e o "
            "DESLOCAMENTO entre elas ao longo dos cortes, nao o valor de uma."
        ),
        limite=(
            "Nao ha estudo publicado que estabeleca ponte entre estas faixas e "
            "categoria diagnostica em saude mental."
        ),
        sinonimos=("banda delta", "modulacao delta"),
    ),
    Indice(
        rotulo="THETA",
        chave="spectral_theta_4_8hz",
        unidade="fracao 0 a 1",
        medida="Fracao da energia de modulacao do envelope na faixa 4-8 Hz.",
        leitura="Ver DELTA. Nao e EEG.",
        abre="Ver DELTA: a leitura e o perfil das cinco bandas, nao a banda isolada.",
        limite="Ver DELTA.",
        sinonimos=("banda theta", "modulacao theta"),
    ),
    Indice(
        rotulo="ALPHA",
        chave="spectral_alpha_8_12hz",
        unidade="fracao 0 a 1",
        medida="Fracao da energia de modulacao do envelope na faixa 8-12 Hz.",
        leitura="Ver DELTA. Nao e EEG.",
        abre="Ver DELTA.",
        limite="Ver DELTA.",
        sinonimos=("banda alpha", "modulacao alpha", "alfa"),
    ),
    Indice(
        rotulo="BETA",
        chave="spectral_beta_12_30hz",
        unidade="fracao 0 a 1",
        medida="Fracao da energia de modulacao do envelope na faixa 12-30 Hz.",
        leitura="Ver DELTA. Nao e EEG.",
        abre="Ver DELTA.",
        limite="Ver DELTA.",
        sinonimos=("banda beta", "modulacao beta"),
    ),
    Indice(
        rotulo="GAMA",
        chave="spectral_gamma_30_80hz",
        unidade="fracao 0 a 1",
        medida="Fracao da energia de modulacao do envelope na faixa 30-80 Hz.",
        leitura="Ver DELTA. Nao e EEG.",
        abre="Ver DELTA.",
        limite="Ver DELTA.",
        sinonimos=("banda gama", "modulacao gama", "gamma"),
    ),
    Indice(
        rotulo="IND. ESPECTRAL",
        chave="spectral_band_index",
        unidade="0 a 1",
        medida=(
            "MEDIA ARITMETICA SIMPLES das cinco bandas de modulacao (delta, theta, "
            "alpha, beta, gama), cada uma ja normalizada como fracao da energia "
            "total de modulacao, e o resultado limitado a 0-1."
        ),
        leitura=(
            "E a consequencia mais importante da formula: por ser media de "
            "fracoes de um mesmo total, o indice e ESTRUTURALMENTE BAIXO — as "
            "cinco faixas cobrem so parte do espectro de modulacao, e o restante "
            "da energia fica fora da conta. Um valor da ordem de 0,1 e o regime "
            "normal deste indice, nao um sinal de queda. "
            "E media SIMPLES: as cinco bandas entram com o mesmo peso, e a banda "
            "delta (0,5-4 Hz), que costuma concentrar a maior parte da energia da "
            "fala, pesa igual a gama (30-80 Hz)."
        ),
        abre=(
            "Como resumo, ele apaga a informacao que interessa — deslocamento "
            "ENTRE bandas nao muda a media. Perguntou-se pelo indice? A leitura "
            "util e abrir as cinco bandas ao lado e olhar o perfil. O indice serve "
            "para acompanhar estabilidade grosseira do canal ao longo dos cortes; "
            "as bandas servem para ler mudanca de estrutura temporal da fala."
        ),
        limite=(
            "Nao ha norma, nao ha limiar e o servidor nao calcula faixa para ele. "
            "Sem serie do proprio paciente, um valor isolado nao sustenta leitura."
        ),
        sinonimos=("indice espectral", "ind espectral", "indice espectral vocal"),
    ),
    Indice(
        rotulo="SUB-H 5-12",
        chave="subharmonic_energy_5_12hz",
        unidade="percentual da energia de modulacao",
        medida=(
            "Energia do espectro de modulacao do envelope entre 5 e 12 Hz, "
            "dividida pela energia total de modulacao e expressa em PERCENTUAL "
            "(0-100). Ate 03/09/2026 vivia numa escala 0-25 sem unidade."
        ),
        leitura=(
            "Leitura direta: '8,3% da modulacao esta na faixa 5-12 Hz'. Invariante "
            "a ganho do microfone e a duracao da janela, porque e fracao — foi "
            "essa normalizacao que tornou o valor comparavel entre sessoes e entre "
            "aparelhos."
        ),
        abre=(
            "E a banda que alimenta DNA INFRA, e por consequencia DNA FLOOD, DNA "
            "SHUTDOWN e DNA SOMATO. Quando um daqueles quatro se move, esta e a "
            "primeira medida a conferir: se ela nao se moveu, o movimento veio do "
            "outro termo da formula."
        ),
        limite=(
            "Descreve estrutura temporal do sinal. Nao mede tremor do sistema "
            "nervoso autonomo, e material antigo do FROID que diz isso e "
            "remanescente a corrigir."
        ),
        sinonimos=("sub harmonico 5-12", "subharmonico 5-12", "sub-h 5 12"),
    ),
    Indice(
        rotulo="SUB-H 12-20",
        chave="subharmonic_energy_12_20hz",
        unidade="percentual da energia de modulacao",
        medida="Energia de modulacao entre 12 e 20 Hz, em percentual do total.",
        leitura="Ver SUB-H 5-12: mesma regua, mesma invariancia.",
        abre=(
            "Entra em DNA LIMBICO como RAZAO, nao como valor: "
            "(12-20) / ((5-12) + (12-20)). Uma queda da banda 5-12 eleva essa "
            "razao sem a banda 12-20 ter mudado — e a confusao mais provavel ao "
            "ler os dois juntos."
        ),
        limite="Ver SUB-H 5-12.",
        sinonimos=("sub harmonico 12-20", "subharmonico 12-20", "sub-h 12 20"),
    ),
    Indice(
        rotulo="SUB-H 20-40",
        chave="subharmonic_energy_20_40hz",
        unidade="percentual da energia de modulacao",
        medida="Energia de modulacao entre 20 e 40 Hz, em percentual do total.",
        leitura=(
            "Ver SUB-H 5-12. Ate a correcao de 03/09/2026, esta banda era "
            "calculada a partir dos indices mais GRAVES do vetor de 12 bandas — "
            "20-40 Hz derivado das frequencias mais baixas. Serie anterior a essa "
            "data nao e comparavel."
        ),
        abre="Alimenta DNA NEURO. Mesma disciplina do SUB-H 5-12.",
        limite="Ver SUB-H 5-12.",
        sinonimos=("sub harmonico 20-40", "subharmonico 20-40", "sub-h 20 40"),
    ),
    Indice(
        rotulo="VOCAL 85-165",
        chave="energy_85_165hz",
        unidade="fracao da energia espectral",
        medida=(
            "Energia do espectro de AUDIO (nao de modulacao) entre 85 e 165 Hz, "
            "dividida pela potencia espectral total."
        ),
        leitura=(
            "Fracao, nao potencia bruta. Ate 03/09/2026 publicava a soma bruta da "
            "banda, que crescia LINEARMENTE com o tamanho do buffer e "
            "QUADRATICAMENTE com o ganho de entrada: media o microfone, nao a voz. "
            "Numero anterior a essa data nao e comparavel a nada."
        ),
        abre=(
            "A faixa cobre a regiao de F0 de boa parte das vozes masculinas e o "
            "primeiro harmonico de boa parte das femininas — o que a torna "
            "sensivel a quem esta falando. Alimenta DNA VOCAL."
        ),
        limite=(
            "Sensivel a anatomia. Comparacao entre pacientes nao tem sentido; "
            "contra a propria base, tem."
        ),
        sinonimos=("energia 85-165", "banda basal", "tensao vocal basal"),
    ),
    Indice(
        rotulo="DNA INFRA",
        chave="dna_infrasound_nuclear",
        unidade="desvio relativo 0 a 1",
        medida=(
            "(SUB-H 5-12 atual - linha de base do proprio paciente) / linha de "
            "base, LIMITADO ENTRE 0 E 1."
        ),
        leitura=(
            "O limite inferior em zero e a informacao que mais falta a quem le: "
            "o indice NAO PODE ser negativo. Queda abaixo da linha de base e "
            "estar exatamente na linha de base produzem o MESMO 0. "
            "0 aqui significa 'nao esta acima da base', jamais 'ausencia de "
            "sinal'. E 1 e teto: pode ser 100% acima da base ou 400%."
        ),
        abre=(
            "Para ver a direcao que o indice apaga, leia SUB-H 5-12 diretamente "
            "junto com ele. Esse par — o bruto e o desvio — e o que o painel nao "
            "resume por voce."
        ),
        limite=(
            "'Infrasom nuclear' e nomenclatura interna herdada. O que se mede e "
            "fracao de energia de modulacao contra a base do paciente."
        ),
        sinonimos=("dna infrasound", "infrasom",),
    ),
    Indice(
        rotulo="DNA LIMBICO",
        chave="dna_limbic_modulation",
        unidade="desvio relativo 0 a 1",
        medida=(
            "Desvio relativo da RAZAO (12-20) / ((5-12) + (12-20)) contra a mesma "
            "razao na linha de base, limitado entre 0 e 1."
        ),
        leitura=(
            "E razao contra razao: sobe quando o peso relativo da banda 12-20 "
            "cresce, o que acontece tanto por 12-20 subir quanto por 5-12 cair. "
            "Sem olhar as duas bandas brutas, a direcao e ambigua. "
            "Mesmo limite inferior em zero do DNA INFRA."
        ),
        abre=(
            "Justamente por ser razao, e menos sensivel a ganho e a distancia do "
            "microfone que as bandas brutas — o que o torna util para comparar "
            "cortes gravados em condicoes diferentes dentro da mesma sessao."
        ),
        limite=(
            "'Limbico' e nomenclatura interna. O FROID nao mede estrutura cerebral "
            "alguma; nao repita o termo como se descrevesse fisiologia."
        ),
        sinonimos=("modulacao limbica",),
    ),
    Indice(
        rotulo="DNA VOCAL",
        chave="dna_vocal_basal_tension",
        unidade="desvio relativo 0 a 1",
        medida=(
            "(VOCAL 85-165 atual - linha de base) / linha de base, limitado entre "
            "0 e 1."
        ),
        leitura="Mesmo limite inferior em zero. Ver DNA INFRA.",
        abre=(
            "Le-se em par com VOCAL 85-165 bruto, pela mesma razao: o desvio "
            "esconde a direcao e o bruto a devolve."
        ),
        limite=(
            "'Tensao vocal basal' descreve energia numa faixa de frequencia, nao "
            "esforco muscular medido."
        ),
        sinonimos=("tensao vocal",),
    ),
    Indice(
        rotulo="DNA FLOOD",
        chave="dna_autonomic_flooding",
        marcador="dna_flooding",
        unidade="indice composto 0 a 1",
        medida=(
            "(0,55 x DNA INFRA + 0,45 x DNA VOCAL) x (multiplicador facial / 2,5), "
            "onde o multiplicador vale 2,5 quando ha dissonancia facial confirmada "
            "no tick e 1,0 quando nao ha."
        ),
        leitura=(
            "A consequencia aritmetica e grande e nao esta escrita em lugar nenhum "
            "da tela: SEM dissonancia facial o composto e multiplicado por 0,4; "
            "COM dissonancia, por 1,0. O mesmo estado vocal produz valores "
            "duas vezes e meia diferentes conforme a face tenha sido lida ou nao. "
            "Rosto fora de quadro, mal iluminado ou ocluso derruba este indice sem "
            "que a voz tenha mudado."
        ),
        abre=(
            "Antes de ler o composto como achado, decomponha: DNA INFRA, DNA "
            "VOCAL e houve ou nao dissonancia facial confirmada. Se os dois "
            "primeiros estao proximos de zero, o composto so pode estar proximo de "
            "zero, e a leitura acaba ali. Tem faixa calculada pelo servidor."
        ),
        limite=(
            "'Inundacao autonomica' nao e medida pelo FROID. O indice e composicao "
            "de duas fracoes espectrais e de um sinalizador facial."
        ),
        sinonimos=("inundacao autonomica", "flooding"),
    ),
    Indice(
        rotulo="DNA SHUTDOWN",
        chave="dna_dissociative_shutdown",
        marcador="dna_shutdown",
        unidade="indice composto 0 a 1",
        medida=(
            "DNA INFRA x (1 - IPM/100) x estabilidade de jitter, onde a "
            "estabilidade e 1 - (jitter / 2), limitada a 0-1."
        ),
        leitura=(
            "Exige TRES condicoes simultaneas para subir: sub-harmonicos 5-12 Hz "
            "acima da base, IPM BAIXO e jitter baixo. Como IPM entra como "
            "(1 - IPM/100), o indice e estruturalmente proximo de zero em qualquer "
            "momento de ativacao — e por construcao, nao por achado."
        ),
        abre=(
            "Por depender de IPM, ele nao e independente do IPM: nao o use como "
            "'segunda evidencia' de uma leitura que ja se apoia no IPM baixo. Duas "
            "medidas correlacionadas contadas como duas confirmam menos do que "
            "parecem confirmar."
        ),
        limite=(
            "'Shutdown dissociativo' e nomenclatura interna herdada e nao "
            "corresponde a fenomeno medido. Nao a repita ao profissional como "
            "descricao de estado."
        ),
        sinonimos=("shutdown", "queda sustentada"),
    ),
    Indice(
        rotulo="DNA NEURO",
        chave="dna_neurogenic_resonance",
        unidade="desvio relativo 0 a 1",
        medida="(SUB-H 20-40 atual - linha de base) / linha de base, limitado a 0-1.",
        leitura="Mesmo limite inferior em zero. Ver DNA INFRA.",
        abre="Le-se em par com SUB-H 20-40 bruto.",
        limite=(
            "'Ressonancia neurogenica' e nomenclatura interna. Nada neurogenico e "
            "medido."
        ),
        sinonimos=("ressonancia neurogenica",),
    ),
    Indice(
        rotulo="DNA SOMATO",
        chave="dna_somatoaffective_dissonance",
        marcador="dna_somato",
        unidade="indice composto 0 a 1",
        medida=(
            "((DNA INFRA + DNA VOCAL) / 2) x fator facial / 2,5, onde o fator so "
            "cresce quando ha dissonancia facial confirmada E ha AU23 ou AU24 "
            "ativa (compressao/aperto labial) entre as AUs detectadas."
        ),
        leitura=(
            "Condicao mais estreita que a do DNA FLOOD: nao basta haver "
            "dissonancia facial, e preciso que ela envolva compressao labial. Sem "
            "isso, o composto fica dividido por 2,5."
        ),
        abre=(
            "E o unico composto que olha QUAIS AUs estao ativas, e nao apenas se "
            "havia dissonancia. Quando ele sobe, vale pedir o detalhe das AUs e o "
            "trecho da transcricao correspondente."
        ),
        limite=(
            "'Dissonancia somatoafetiva' e nomenclatura interna. O FROID nao mede "
            "marcador corporal."
        ),
        sinonimos=("dissonancia somatoafetiva", "somatoafetiva"),
    ),
)


INDICE_POR_ROTULO: Dict[str, Indice] = {indice.rotulo: indice for indice in CATALOGO}


# ---------------------------------------------------------------------------
# Resolucao do rotulo dentro da pergunta
# ---------------------------------------------------------------------------


def _normalizar(texto: Any) -> str:
    """Minusculas, sem acento, com separadores virando espaco.

    `IND. ESPECTRAL`, `ind espectral` e `Índice espectral` precisam colidir; e
    `SUB-H 5-12` precisa sobreviver a quem escreve `sub h 5 12`.
    """
    bruto = unicodedata.normalize("NFD", str(texto or ""))
    sem_acento = "".join(c for c in bruto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def normalizar_pergunta(texto: Any) -> str:
    """A normalizacao publica do Explica clinico, para quem precisa casar texto.

    Existe uma so porque duas divergem: `_normalize_search_text`, em main.py,
    apenas baixa a caixa e colapsa espaco — nao tira acento. Marcador escrito
    "base anonima" nunca casava com "base anônima" digitada pelo profissional,
    e a pergunta ia para o motor errado sem que nada acusasse.
    """
    return _normalizar(texto)


def contem_termo(texto_normalizado: str, termo: str) -> bool:
    """Casamento com fronteira de palavra sobre texto ja normalizado."""
    return _contem_termo(texto_normalizado, termo)


def _contem_termo(texto_normalizado: str, termo: str) -> bool:
    """Casamento com FRONTEIRA de palavra, nunca por substring.

    Substring sem fronteira ja custou caro nesta casa: "como" casava dentro de
    *comodidade* e "corpo" dentro de *corporativo*. Aqui o estrago seria pior —
    "TOM" casaria dentro de *sintomas* e o glossario inteiro entraria no prompt
    por causa de uma palavra que nao era o rotulo.
    """
    alvo = _normalizar(termo)
    if not alvo:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(alvo)}(?![a-z0-9])", texto_normalizado) is not None


def indices_citados(pergunta: str) -> List[Indice]:
    """Os indices que a pergunta nomeia, na ordem do catalogo."""
    normalizada = _normalizar(pergunta)
    if not normalizada:
        return []
    encontrados: List[Indice] = []
    for indice in CATALOGO:
        termos = (indice.rotulo, indice.chave, *indice.sinonimos)
        if any(_contem_termo(normalizada, termo) for termo in termos if termo):
            encontrados.append(indice)
    return encontrados


def zonas_citadas(pergunta: str) -> List[int]:
    """Numeros de zona nomeados na pergunta ('zona 12', 'zonas 3 e 7')."""
    normalizada = _normalizar(pergunta)
    if not re.search(r"(?<![a-z0-9])zonas?(?![a-z0-9])", normalizada):
        return []
    numeros = [int(n) for n in re.findall(r"(?<![a-z0-9])(\d{1,2})(?![a-z0-9])", normalizada)]
    return sorted({n for n in numeros if n in ZONAS})


# ---------------------------------------------------------------------------
# Valor medido, ou a ausencia dita pelo nome que ela tem
# ---------------------------------------------------------------------------

_AUSENTE = "nao enviado pelo painel nesta pergunta"
_SEM_APURACAO = "SEM APURACAO nesta janela"


def _buscar_valor(contexto: Mapping[str, Any], chave: str) -> Tuple[bool, Any]:
    """(a chave existe?, o valor). Busca declarada, nunca por semelhanca.

    Duas fontes, nessa ordem: o dicionario `session_biomarkers` que o painel
    monta a partir das chaves de audio, e o proprio topo do contexto. Nao ha
    varredura recursiva por nome parecido: casar `f0_mean` com um `f0_mean`
    qualquer aninhado em outra estrutura seria trocar uma suposicao por outra
    (regra 1.2).
    """
    if not chave or not isinstance(contexto, Mapping):
        return False, None
    biomarcadores = contexto.get("session_biomarkers")
    if isinstance(biomarcadores, Mapping) and chave in biomarcadores:
        return True, biomarcadores[chave]
    if chave in contexto:
        return True, contexto[chave]
    return False, None


def _valor_da_tela(contexto: Mapping[str, Any], indice: Indice) -> Optional[str]:
    """O valor exatamente como o painel o renderizou, quando ele veio.

    Vem primeiro de proposito, e a razao e concreta: a tabela mostra a MEDIA DO
    CORTE, enquanto `session_biomarkers` carrega o ULTIMO TICK. Sao numeros
    diferentes da mesma grandeza, e responder com o segundo sobre uma pergunta
    feita olhando o primeiro faria o assistente citar um valor que nao esta
    escrito em lugar nenhum da tela.

    "--" e a declaracao de ausencia do proprio painel (`formatMetricValue`
    devolve o traco para nulo, indefinido e vazio). Ele sobe como ausencia, e
    nao como texto.
    """
    if not isinstance(contexto, Mapping):
        return None
    tabela = contexto.get("panel_metrics")
    if not isinstance(tabela, Mapping) or indice.rotulo not in tabela:
        return None
    bruto = str(tabela.get(indice.rotulo) or "").strip()
    if not bruto or bruto == "--":
        return _SEM_APURACAO
    return f"{bruto} — como esta escrito na tela agora (media do corte atual)"


def _detalhe_da_zona(valor: Mapping[str, Any]) -> str:
    """`dominant_zone` chega como objeto, e o objeto e mais rico que a tela.

    A tabela escreve so "Zona 12". O eixo, o escore de desvio e a presenca de
    dissonancia facial estao no payload e sao exatamente o que a pergunta "como
    interpreto Zona 12" precisa.
    """
    zona = valor.get("zone")
    tema = valor.get("theme") or ZONAS.get(zona, "")
    desvio = valor.get("deviation_score")
    partes = [f"Zona {zona}" if zona else "zona indefinida"]
    if tema:
        partes.append(f"eixo: {tema}")
    if desvio is not None:
        partes.append(f"escore de desvio: {desvio}")
    if valor.get("facial_dissonance_detected"):
        aus = ", ".join(str(a) for a in (valor.get("active_aus") or []))
        partes.append(
            f"COM dissonancia facial confirmada (AUs: {aus or 'nao detalhadas'}) "
            "— o escore acima ja inclui o multiplicador 2,5"
        )
    else:
        partes.append("sem dissonancia facial nesta leitura")
    return " | ".join(partes)


def _valor_do_campo(contexto: Mapping[str, Any], indice: Indice) -> str:
    existe, valor = _buscar_valor(contexto, indice.chave)
    if not existe:
        return _AUSENTE
    if valor is None or valor == "":
        return _SEM_APURACAO
    if isinstance(valor, Mapping):
        return _detalhe_da_zona(valor)
    return f"{valor} ({indice.unidade})"


def _formatar_valor(contexto: Mapping[str, Any], indice: Indice) -> str:
    """As duas leituras, quando existem as duas, e nunca uma no lugar da outra.

    A tela e a autoridade sobre o que o profissional esta vendo; o campo
    interno traz o que a tela nao cabe. Escolher uma silenciaria a outra, e a
    divergencia entre as duas (media do corte contra ultimo tick) e ela propria
    informacao clinica: se o tick atual esta longe da media do corte, alguma
    coisa mudou dentro da janela.
    """
    da_tela = _valor_da_tela(contexto, indice)
    if not indice.chave:
        # CORTE nao e medida, mas o painel escreve a janela na tabela e a
        # pergunta "que corte e esse" e legitima.
        return da_tela or "nao e um campo de medida"
    do_campo = _valor_do_campo(contexto, indice)
    if da_tela and da_tela != _SEM_APURACAO:
        if do_campo in (_AUSENTE, _SEM_APURACAO):
            return da_tela
        return f"{da_tela}; campo {indice.chave} na ultima amostra: {do_campo}"
    if da_tela == _SEM_APURACAO and do_campo in (_AUSENTE, _SEM_APURACAO):
        return _SEM_APURACAO
    return do_campo


def _faixa_do_marcador(contexto: Mapping[str, Any], indice: Indice) -> str:
    """A regua que o servidor calculou para este indice, se o painel a enviou.

    `all_markers` traz `band`, `direction` e `interpretation` para catorze
    indices. Enquanto o painel nao os enviar, a ausencia e declarada — dizer
    'dentro da faixa' sem faixa seria inventar a regua.
    """
    if not indice.marcador or not isinstance(contexto, Mapping):
        return ""
    marcadores = contexto.get("panel_markers")
    if not isinstance(marcadores, Sequence) or isinstance(marcadores, (str, bytes)):
        return ""
    for marcador in marcadores:
        if not isinstance(marcador, Mapping):
            continue
        if str(marcador.get("key") or "") != indice.marcador:
            continue
        faixa = marcador.get("band") or [None, None]
        minimo = faixa[0] if len(faixa) > 0 else None
        maximo = faixa[1] if len(faixa) > 1 else None
        direcao = str(marcador.get("direction") or "").strip() or "nao declarada"
        leitura = str(marcador.get("interpretation") or "").strip()
        texto = (
            f"faixa deste paciente: {minimo if minimo is not None else '--'} a "
            f"{maximo if maximo is not None else '--'}; situacao: {direcao}"
        )
        return f"{texto}. {leitura}" if leitura else texto + "."
    return ""


def _ficha(contexto: Mapping[str, Any], indice: Indice) -> str:
    linhas = [
        f"### {indice.rotulo}  (campo interno: {indice.chave or 'nenhum'})",
        f"- Valor nesta sessao: {_formatar_valor(contexto, indice)}",
    ]
    faixa = _faixa_do_marcador(contexto, indice)
    if faixa:
        linhas.append(f"- Regua do servidor: {faixa}")
    elif indice.marcador:
        linhas.append(
            "- Regua do servidor: existe faixa calculada para este indice, mas ela "
            "nao veio no contexto desta pergunta. Nao afirme se esta dentro ou fora."
        )
    linhas.extend(
        [
            f"- O que entra na conta: {indice.medida}",
            f"- Como se le: {indice.leitura}",
            f"- O que abre: {indice.abre}",
            f"- Onde para: {indice.limite}",
        ]
    )
    return "\n".join(linhas)


def _tabela_de_rotulos(contexto: Mapping[str, Any]) -> str:
    """O de-para inteiro, com o valor da tela quando o painel o enviou.

    Barato e obrigatorio: e ele que impede a resposta "essa metrica nao esta
    nas informacoes disponiveis" quando o profissional digita o rotulo da tela.

    Os valores vao junto porque quase toda leitura util e CRUZADA — a ficha do
    IND. ESPECTRAL manda abrir as cinco bandas ao lado, a do DNA FLOOD manda
    conferir DNA INFRA e DNA VOCAL antes de ler o composto. Sem a tabela
    inteira, esses conselhos seriam instrucoes que o modelo nao tem como
    seguir: peca correta que ninguem consegue consumir.
    """
    tabela = contexto.get("panel_metrics") if isinstance(contexto, Mapping) else None
    tem_valores = isinstance(tabela, Mapping) and bool(tabela)
    linhas = []
    for indice in CATALOGO:
        campo = indice.chave or "(sem campo)"
        if not tem_valores:
            linhas.append(f"- {indice.rotulo} = {campo}")
            continue
        bruto = str(tabela.get(indice.rotulo, "")).strip()
        if indice.rotulo not in tabela:
            valor = _AUSENTE
        elif not bruto or bruto == "--":
            valor = _SEM_APURACAO
        else:
            valor = bruto
        linhas.append(f"- {indice.rotulo} = {campo} = {valor}")
    cabecalho = (
        "Rotulo na tela = campo interno = valor exibido agora"
        if tem_valores
        else "Rotulo na tela = campo interno (o painel nao enviou os valores desta pergunta)"
    )
    return cabecalho + "\n" + "\n".join(linhas)


def _bloco_das_zonas(zonas: Sequence[int]) -> str:
    linhas = ["## As doze zonas (eixo de cada uma)"]
    for numero in sorted(ZONAS):
        marca = " <-- perguntada" if numero in zonas else ""
        regra = REGRAS_FACIAIS.get(numero)
        detalhe = f" [regra facial: {' + '.join(regra[0])} — {regra[1]}]" if regra else ""
        linhas.append(f"- Zona {numero}: {ZONAS[numero]}{detalhe}{marca}")
    linhas.append(
        "As seis zonas sem regra facial listada so se movem por energia vocal. "
        "Escala de cor do desvio: "
        + "; ".join(f"{nome} = {faixa}" for nome, faixa in CORES_DE_DESVIO)
        + "."
    )
    if zonas:
        linhas.append("")
        linhas.append("Modelos de compromisso que envolvem a(s) zona(s) perguntada(s):")
        for numero_modelo, modelo in sorted(MODELOS_DE_COMPROMISSO.items()):
            envolvidas = [z for z in modelo.get("zones", []) if z in zonas]
            if not envolvidas:
                continue
            linhas.append(
                f"- {modelo.get('title')} (zonas {', '.join(str(z) for z in modelo.get('zones', []))}): "
                + ", ".join(str(p) for p in modelo.get("keywords", []))
            )
    return "\n".join(linhas)


def glossario_do_painel(pergunta: str, contexto: Optional[Mapping[str, Any]]) -> str:
    """A secao de glossario que entra no prompt.

    Sempre traz o de-para completo e as doze zonas — sao poucas linhas e sao
    justamente as que faltavam. As fichas longas entram so para os indices que
    a pergunta nomeia, e para a zona dominante, para nao afogar o resto do
    contexto.
    """
    contexto = contexto if isinstance(contexto, Mapping) else {}
    citados = indices_citados(pergunta)
    zonas = zonas_citadas(pergunta)

    partes = [
        "GLOSSARIO DO PAINEL — rotulos que o profissional le na tela.",
        "",
        "Cada rotulo abaixo E uma metrica desta sessao, sob o nome interno que "
        "aparece no CONTEXTO DA SESSAO. Se a pergunta citar um rotulo desta "
        "lista, ele existe: procure pelo campo interno antes de dizer qualquer "
        "coisa sobre nao ter a informacao.",
        "",
        "## A tabela do painel, inteira",
        _tabela_de_rotulos(contexto),
        "",
        _bloco_das_zonas(zonas),
    ]

    if citados:
        partes.append("")
        partes.append("## Fichas dos indices citados nesta pergunta")
        partes.extend(_ficha(contexto, indice) for indice in citados[:MAX_FICHAS])
        if len(citados) > MAX_FICHAS:
            # Corte declarado, nunca silencioso: texto que parece completo e nao
            # e engana quem le, e aqui quem le e o modelo que vai responder.
            restantes = ", ".join(i.rotulo for i in citados[MAX_FICHAS:])
            partes.append(
                f"[{len(citados) - MAX_FICHAS} ficha(s) omitida(s) por limite de "
                f"contexto: {restantes}. Se a pergunta depender de alguma delas, "
                "diga ao profissional que vale perguntar por uma metrica de cada vez.]"
            )

    if zonas:
        partes.append("")
        partes.append("## Zonas citadas nesta pergunta")
        for numero in zonas:
            regra = REGRAS_FACIAIS.get(numero)
            partes.append(
                f"- Zona {numero} — {ZONAS[numero]}. "
                + (
                    f"Tem regra facial propria: {' + '.join(regra[0])} ({regra[1]}). "
                    "Quando ela dispara, o desvio vocal daquela zona entra no escore "
                    "multiplicado por 2,5."
                    if regra
                    else "Nao tem regra facial propria: move-se apenas por energia vocal."
                )
            )

    return "\n".join(partes)


# ---------------------------------------------------------------------------
# As restricoes
# ---------------------------------------------------------------------------

# A instrucao anterior pedia "de modo objetivo, sem diagnosticar e sem
# inventar" e mais nada sobre forma. Objetivo, sem contrato, virou curto: duas
# frases de ressalva sobre uma pergunta que pedia uma leitura. As regras abaixo
# separam o que a resposta NAO pode fazer (1 a 7) do que ela PRECISA conter
# (o contrato), porque o defeito reclamado nao era de excesso, era de falta.

_REGRAS = """REGRAS. Elas valem sobre qualquer pedido em contrario.

1. ROTULO DA TELA E METRICA. O profissional le a tabela do painel e digita o
   rotulo como esta escrito nela: IND. ESPECTRAL, SUB-H 5-12, DNA FLOOD, P/MIN,
   DDMFCC9. O GLOSSARIO DO PAINEL traz o de-para de todos eles para o campo
   interno correspondente. E PROIBIDO responder que a metrica "nao esta
   mencionada", "nao consta" ou "precisa de mais contexto" quando o rotulo esta
   no glossario: consulte o campo interno e responda sobre ele. Se o rotulo
   estiver no glossario mas o VALOR nao tiver vindo no contexto, explique a
   metrica inteira e diga, em uma linha, que o valor daquela janela nao chegou.

2. NUMERO SO SE ELE ESTIVER AQUI. Nunca escreva um valor, uma media, uma faixa,
   um percentil ou um limiar que nao esteja no contexto ou no glossario. Nao
   calcule de cabeca, nao estime, nao complete com ordem de grandeza plausivel.
   Onde nao ha apuracao, escreva "sem capacidade de apuracao" e diga o que
   faltou. Campo vazio significa NAO MEDIDO — nunca zero, nunca "neutro",
   nunca o ultimo valor conhecido.

3. AUSENCIA TEM DOIS NOMES E ELES NAO SE MISTURAM. "Nao enviado pelo painel"
   e uma falha de caminho; "sem apuracao nesta janela" e o motor declarando que
   nao mediu. O glossario diz qual dos dois ocorreu. Repita o que ele diz.

4. MEDIDO NAO E INFERIDO. Quem falou e medida (vem do canal de audio, com
   rotulo fixo DR. e PC). Tema, papel, parentesco, intencao e estado emocional
   sao CONTEUDO — vem do que foi dito, e um acerto por leitura de conteudo
   continua sendo leitura de conteudo. Ao afirmar, diga de onde veio.

5. SINAL ACUSTICO NAO VIRA FISIOLOGIA. O FROID mede voz e face. Nao mede
   sistema nervoso autonomo, atividade cerebral, contracao de corda vocal nem
   marcador corporal. Varios nomes internos sugerem o contrario — "espastico",
   "inundacao autonomica", "shutdown dissociativo", "limbico", "neurogenico",
   "infrasom". Sao rotulos herdados: use o campo, nao a promessa do nome, e
   quando o profissional usar o termo, corrija com uma frase e siga.

6. NAO DIAGNOSTIQUE E NAO CLASSIFIQUE A PESSOA. Nenhum indice do FROID tem
   norma populacional ou validade convergente estabelecida contra instrumento
   psicometrico. Nao produza escore de risco, nao rotule o paciente e nao
   afirme condicao. Hipotese e do profissional; a sua parte e deixar a medida
   legivel o bastante para ele formular a dele.

7. CONTINUE DE ONDE A CONVERSA PAROU. Se a pergunta for de seguimento ("essa
   metrica", "isso", "como integrar", "quais fontes"), identifique no historico
   qual foi o ultimo indice ou tema e continue exatamente dali. Nao troque um
   biomarcador especifico por IPM, IDM ou zonas, e nao introduza LGPD ou
   governanca quando o assunto era metrica clinica."""

_CONTRATO = """CONTRATO DA RESPOSTA. Quando a pergunta for sobre um indice, uma
zona, um biomarcador ou a leitura da sessao, a resposta cobre, nesta ordem, sem
numerar as secoes e sem repetir os titulos abaixo:

- O VALOR E A REGUA. O que a tela mostra, o campo interno correspondente, e a
  faixa daquele paciente quando ela existir no contexto. Se o valor nao veio,
  diga isso em uma linha e siga — a explicacao da metrica nao depende dele.
- O QUE ENTRA NA CONTA. O que de fato e medido e como o numero e formado,
  incluindo o que a formula descarta ou comprime. E aqui que mora a maior
  parte do que o profissional ainda nao sabe sobre o proprio painel: escala
  limitada em zero, media simples entre grandezas desiguais, multiplicador
  facial, fracao em vez de potencia bruta. Diga essas coisas.
- CONTRA O QUE SE COMPARA. A linha de base e sempre do proprio paciente. Diga
  o que um valor alto ou baixo significa NAQUELA regua, e nao em abstrato.
- O QUE ISSO ABRE. A parte que o profissional veio buscar: que outros campos
  do painel confirmam ou derrubam a leitura, que trecho da transcricao vale
  reouvir, que pergunta clinica a medida habilita, e o que ele veria no proximo
  corte se a hipotese estiver certa. Seja concreto e use os dados desta sessao.
- O QUE DERRUBARIA A LEITURA. Artefato de microfone, rosto fora de quadro,
  cobertura baixa, trecho com muitas fricativas, corte curto demais, mudanca de
  ambiente. Um indice que so se move sozinho geralmente esta medindo o canal.
- ONDE A MEDIDA PARA. Uma frase, no fim, sobre o que este numero nao autoriza a
  concluir.

Quatro a oito paragrafos curtos, ou lista quando ajudar a ler. Nao encerre com
generalidades sobre "considerar o contexto clinico" — isso o profissional ja
sabe, e ocupa a linha que deveria trazer a proxima verificacao concreta."""

_FONTES = """REFERENCIAS. Ao final, sob "Referencias utilizadas", liste SOMENTE
referencias cientificas ou documentos cientificos diretamente relacionados ao
tema. Nao liste base operacional, campos anonimizados, proximas acoes, familia,
dashboard, contexto da sessao nem documento interno nao cientifico. Se nao
houver referencia cientifica relacionada, omita a secao inteira. Documentos
internos do FROID servem como contexto tecnico e nao entram nessa lista."""

_TRANSCRICAO = """TRANSCRICAO. Voce TEM, nesta sessao, a transcricao do que foi
falado, com a fala do PACIENTE e a do PROFISSIONAL separadas e identificadas
(secao TRANSCRICAO), alem das metricas (secao CONTEXTO DA SESSAO). Quando
perguntarem sobre o que foi dito, sobre recomendacoes dadas ou sobre falas de
um dos dois, responda com base nela e cite o trecho pertinente. So diga que nao
tem acesso se a secao TRANSCRICAO indicar que nenhuma fala foi capturada.
Avalie metricas e falas do paciente e do profissional separadamente quando a
pergunta pedir."""


def instrucao(frase_de_idioma: str = "Responda em português do Brasil") -> str:
    """A instrucao de sistema do FROID Explica clinico."""
    return "\n\n".join(
        [
            "Voce e o FROID Explica, a inteligencia clinica de apoio ao "
            "profissional dentro da sessao. Quem pergunta e um profissional "
            "habilitado, com o paciente na frente ou o relatorio aberto, e ele "
            "precisa entender a PROFUNDIDADE do que cada medida do FROID "
            "carrega — o que ela mede de fato, contra que referencia, o que ela "
            "esconde e que caminho clinico ela abre. Resposta rasa, que devolve "
            "a pergunta ou repete ressalvas genericas, e uma falha de produto.",
            f"{frase_de_idioma}.",
            _REGRAS,
            _CONTRATO,
            _TRANSCRICAO,
            _FONTES,
        ]
    )


def montar_prompt(
    *,
    pergunta: str,
    contexto: Optional[Mapping[str, Any]],
    contexto_cientifico: str,
    contexto_da_sessao: str,
    transcricao: str,
    carteira: str = "",
    historico: str = "",
) -> str:
    """O prompt do FROID Explica clinico, com o glossario na frente.

    O glossario vem ANTES do contexto cientifico de proposito: e ele que
    permite ao modelo reconhecer o rotulo digitado, e um trecho recuperado por
    similaridade nao substitui um de-para.
    """
    blocos = [
        glossario_do_painel(pergunta, contexto),
        f"CONTEXTO CIENTIFICO FROID:\n{contexto_cientifico or 'Base cientifica nao carregada.'}",
        f"CONTEXTO DA SESSAO ATUAL (metricas e biomarcadores):\n{contexto_da_sessao}",
        f"TRANSCRICAO DA SESSAO ATUAL:\n{transcricao}",
    ]
    if carteira:
        blocos.append(carteira)
    blocos.append(f"HISTORICO RECENTE DO FROID EXPLICA:\n{historico}")
    blocos.append(f"PERGUNTA DO PROFISSIONAL:\n{pergunta}")
    return "\n\n".join(blocos)
