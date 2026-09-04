"""A fala do profissional entra no acervo. A identidade de ninguém entra.

O DILEMA, como o Fábio o colocou: resumo perde aspectos importantes; texto
literal é mais rico e muito mais arriscado. Escolher um dos dois custa caro nos
dois sentidos.

A SAÍDA não é um meio-termo — é notar que os dois falam de coisas diferentes
dentro da mesma frase. O que torna a fala literal valiosa é o conteúdo
PROCEDIMENTAL: o que o profissional fez, com que palavras, em que ordem. O que a
torna arriscada é o conteúdo REFERENCIAL: quem, onde, quando.

    "e se você observasse isso sem responder, como fez com a Nathalie em maio?"
     |________ procedimento, é a técnica ________|  |__ referência, é a pessoa __|

Os dois são separáveis. Então a fala é guardada literalmente na FORMA, e cada
elemento referencial vira um marcador com tipo:

    "e se você observasse isso sem responder, como fez com a [NOME] em [DATA]?"

O verbo, a construção da pergunta, a hesitação, a ordem — tudo o que faz aquilo
ser uma técnica, e não um relato sobre uma técnica — permanece. É isso que outro
profissional precisa ler quando pergunta "o que se faz quando aparece isto?".

ASSIMETRIA DELIBERADA. Só a fala do PROFISSIONAL recebe este tratamento. A do
paciente não entra no acervo em nenhuma forma literal: ela é o material privado,
e a situação que o acervo precisa já está descrita pelo tema, pela resposta do
paciente e pelos deltas medidos. A fala do profissional é o ofício; a do paciente
é a pessoa. Não são a mesma coisa e não merecem a mesma regra.

O PROBLEMA DIFÍCIL, e como ele é tratado aqui.

Distinguir nome próprio de palavra comum, sem dicionário, é fácil no meio da
frase — capitalizado ali é nome. No INÍCIO da frase é indecidível: "Sugeri que
ele reparasse..." e "Sofia disse que..." têm a mesma forma.

A primeira versão deste módulo redigia `[NOME] que ele reparasse na respiração`.
Apagar o verbo principal não é conservador: é destruir o registro e ainda fazer
o leitor pensar que ali havia um nome. Os dois erros são graves e opostos.

A regra, então, não escolhe entre eles — ela RECUSA quando não sabe. Um token que
abre período só passa se for palavra gramatical conhecida ou tiver terminação
inequivocamente verbal. Não sendo nem uma coisa nem outra, a fala inteira é
descartada e o motivo fica registrado. Perde-se material; não se perde a
distinção entre o que se sabe e o que se supôs.

FALHA FECHADA em quatro situações: fala curta demais para conter técnica, começo
de período ambíguo, fala tão referencial que o resultado seria queijo suíço, e
sobra de identificador depois da limpeza. Nos quatro, não se guarda nada. Guardar
meia frase seria pior do que guardar nada, porque quem lê o acervo não tem como
saber o que faltou.

Nenhuma desidentificação é perfeita. O acervo deve ser tratado como o que é —
dado DESIDENTIFICADO, não dado anônimo — e é por isso que o piso de coorte
continua valendo por cima disto.
"""

from __future__ import annotations

import re
import unicodedata

VERSAO_DEID = "deid-v1"

#: Teto do que se guarda por corte. Não é limite de privacidade — é de utilidade:
#: além disso não é mais uma intervenção, é a transcrição do trecho.
LIMITE_PADRAO = 600

#: Acima desta fração de marcadores a frase virou queijo suíço. O que sobra não
#: ensina técnica nenhuma, e ainda ocupa uma linha do acervo parecendo que ensina.
TAXA_MAXIMA_DE_REDACAO = 0.25

#: Abaixo disto não há técnica a registrar. "Sim", "entendi", "pode falar" são
#: conversa, não intervenção — e enchem o acervo de linhas que não respondem nada.
MINIMO_DE_PALAVRAS = 6

#: Identificadores estruturados: os únicos casos em que o padrão é a própria
#: prova. Nenhuma frase clínica contém um CPF por acidente.
PADROES_ESTRUTURADOS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE), "[LINK]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[DOCUMENTO]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[CEP]"),
    (re.compile(r"\b\+?\d[\d\s().-]{7,}\d\b"), "[TELEFONE]"),
    (re.compile(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b"), "[DATA]"),
    (re.compile(r"\b\d{1,2}h(\d{2})?\b", re.IGNORECASE), "[HORA]"),
    (re.compile(r"R\$\s?[\d.,]+"), "[VALOR]"),
    (re.compile(r"\b\d+\b"), "[NUM]"),
)

#: Meses e dias por extenso: data sem dígito nenhum continua sendo data.
TEMPORAIS = frozenset(
    (
        "janeiro fevereiro marco abril maio junho julho agosto setembro outubro "
        "novembro dezembro segunda terca quarta quinta sexta sabado domingo"
    ).split()
)

#: Palavras que aparecem capitalizadas por POSIÇÃO, e não por serem nome.
#:
#: Só entra aqui palavra que não pode ser nome de gente, de lugar ou de
#: instituição: gramatical, advérbio, ou verbo de uso corrente na fala clínica.
#: Errar para dentro desta lista é o erro perigoso — um nome que passa.
COMUNS_CAPITALIZAVEIS = frozenset(
    """
    a as o os um uma uns umas e ou mas porem porque pois entao logo assim
    de do da dos das em no na nos nas por para pelo pela com sem sob sobre
    ate desde entre apos antes depois durante contra conforme segundo
    eu tu voce vc ele ela nos vos eles elas me te se lhe lhes si
    meu minha teu tua seu sua nosso nossa dele dela deles delas
    este esta esse essa aquele aquela isto isso aquilo tudo nada algo alguem
    que quem qual quais quando onde como quanto quanta quantos quantas
    nao sim talvez nunca sempre ja ainda agora hoje ontem amanha
    aqui ali la ca bem mal muito pouco mais menos tao tanto so apenas
    certo claro exato perfeito otimo bom boa melhor pior tambem alem inclusive
    ha have tem temos tinha teve houve era eram ser estar ter haver
    e esta estao estava estavam sera serao foi foram fui vou vamos vai
    veja olha escuta espera pense repare note percebe entende sente
    entendi entendo lembro imagino acho penso vejo sinto quero posso
    disse falei perguntei sugeri propus pedi devolvi retomei convidei
    apontei nomeei chamei ofereci repeti segui fiz vi dei
    """.split()
)

#: Terminações que só verbo tem. Deliberadamente NÃO incluem "ia" nem "ava":
#: Maria, Sofia, Lívia, Otávia e Ava terminam assim, e o objetivo desta lista é
#: justamente não deixar nome passar por verbo.
SUFIXOS_VERBAIS = ("ei", "ou", "amos", "emos", "imos", "aram", "eram", "iram",
                   "asse", "esse", "isse", "ando", "endo", "indo", "ram")

_TOKEN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'-]*")
_MARCADOR = re.compile(r"\[[A-Z]+\]")
_FIM_DE_PERIODO = ".!?;:"


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _e_comum(token: str) -> bool:
    return _sem_acento(token).lower() in COMUNS_CAPITALIZAVEIS


def _e_temporal(token: str) -> bool:
    return _sem_acento(token).lower() in TEMPORAIS


def _tem_forma_de_verbo(token: str) -> bool:
    """Terminação inequivocamente verbal, para o token que abre período."""
    limpo = _sem_acento(token).lower()
    if limpo.endswith(SUFIXOS_VERBAIS):
        return True
    # "Sugeri", "Devolvi", "Repeti": pretérito em -i. Exige comprimento porque
    # Levi e Pedi têm quatro letras, e aí a dúvida volta.
    return len(limpo) >= 5 and limpo.endswith("i")


def _abre_periodo(texto: str, inicio: int) -> bool:
    """O token em `inicio` é o primeiro de um período?"""
    anterior = texto[:inicio].rstrip()
    if not anterior:
        return True
    return anterior[-1] in _FIM_DE_PERIODO


#: Fração de períodos que pode ser descartada antes de a fala inteira cair.
#:
#: Descartar o período ambíguo em vez da fala toda foi a decisão de 04/09/2026,
#: e a razão é do Fábio: mesmo imperfeita, a desidentificação tem de preservar o
#: conteúdo da questão e da resposta — é isso que serve a quem consulta o acervo
#: depois. Uma palavra indecidível na abertura de uma frase não pode custar as
#: outras cinco frases.
#:
#: Mas metade do registro em buracos não ensina técnica nenhuma, e ainda ocupa
#: uma linha do acervo parecendo que ensina. Daí o teto.
MAXIMO_DE_PERIODOS_DESCARTADOS = 0.5

_SEPARA_PERIODO = re.compile(r"(?<=[.!?;])\s+")


def _limpa_periodo(periodo: str) -> tuple[str, bool]:
    """Devolve `(periodo_limpo, ambiguo)`.

    `ambiguo` significa que o período abre com um token que pode tanto ser nome
    quanto verbo. Nesse caso o período inteiro é descartado por quem chama: as
    duas saídas possíveis aqui — apagar o verbo principal ou deixar passar um
    nome — são ruins, e escolher entre elas seria supor.
    """
    primeiro = _TOKEN.search(periodo)
    inicio = primeiro.start() if primeiro else -1
    ambiguo = False

    def _troca(match: re.Match[str]) -> str:
        nonlocal ambiguo
        token = match.group(0)
        if _e_temporal(token):
            return "[DATA]"
        if not token[:1].isupper() or _e_comum(token):
            return token
        if match.start() == inicio:
            if _tem_forma_de_verbo(token):
                return token
            ambiguo = True
            return token
        return "[NOME]"

    return _TOKEN.sub(_troca, periodo), ambiguo


def _sobrou_identificador(texto: str) -> bool:
    """Segunda leitura, sobre o RESULTADO.

    A primeira confia nas substituições; esta não confia em nada. Uma sobra
    significa que a limpeza não entendeu a frase, e aí não há grau: a fala cai.
    """
    sem_marcadores = _MARCADOR.sub(" . ", texto)
    if re.search(r"\d", sem_marcadores):
        return True
    if re.search(r"@|https?://", sem_marcadores, re.IGNORECASE):
        return True
    for achado in _TOKEN.finditer(sem_marcadores):
        token = achado.group(0)
        if not token[:1].isupper() or _e_comum(token):
            continue
        if _abre_periodo(sem_marcadores, achado.start()) and _tem_forma_de_verbo(token):
            continue
        return True
    return False


def desidentificar_fala(
    texto: str,
    limite: int = LIMITE_PADRAO,
) -> tuple[str, str]:
    """Prepara uma fala do profissional para o acervo compartilhado.

    Devolve `(texto_seguro, motivo)`. Vazio significa NÃO GUARDAR — nunca uma
    versão parcial da frase —, e o motivo diz por quê. Com texto, o motivo é
    "ok"; períodos descartados por ambiguidade aparecem como `[OMITIDO]`, para
    quem lê saber que houve corte em vez de ler um texto que parece completo.
    """
    bruto = re.sub(r"\s+", " ", str(texto or "")).strip()
    if not bruto:
        return "", "vazio"

    palavras_originais = len(_TOKEN.findall(bruto))
    if palavras_originais < MINIMO_DE_PALAVRAS:
        return "", "curta_demais"

    limpo = bruto
    for padrao, marcador in PADROES_ESTRUTURADOS:
        limpo = padrao.sub(marcador, limpo)

    periodos = _SEPARA_PERIODO.split(limpo)
    saida: list[str] = []
    descartados = 0
    for periodo in periodos:
        tratado, ambiguo = _limpa_periodo(periodo)
        if ambiguo or _sobrou_identificador(tratado):
            descartados += 1
            if not saida or saida[-1] != "[OMITIDO]":
                saida.append("[OMITIDO]")
            continue
        saida.append(tratado)

    if descartados >= max(1, len(periodos) * MAXIMO_DE_PERIODOS_DESCARTADOS):
        return "", "inicio_ambiguo" if descartados == len(periodos) else "referencial_demais"

    limpo = " ".join(saida).strip()
    if not limpo or limpo == "[OMITIDO]":
        return "", "inicio_ambiguo"

    marcadores = len(_MARCADOR.findall(limpo))
    if palavras_originais and marcadores / palavras_originais > TAXA_MAXIMA_DE_REDACAO:
        return "", "referencial_demais"

    if len(limpo) > limite:
        # Corta em fronteira de palavra: metade de um nome ainda é pedaço de
        # nome, e "…Nath" numa coluna de acervo não ajuda ninguém.
        limpo = limpo[:limite].rsplit(" ", 1)[0].rstrip() + " […]"

    return limpo, "ok"
