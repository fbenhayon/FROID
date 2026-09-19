"""A diretriz de interpretacao integrada do FROID Explica clinico.

DETERMINACAO DO DONO, 19/09/2026. Resposta sobre metrica isolada, explicacao de
dicionario e relatorio neutro que nao permite decidir nada sao falha de produto.
Toda duvida sobre um parametro atravessa quatro movimentos: contra a regua do
proprio paciente (linha de base e F0), cruzada com os indices de sintese (IDM e
IPM), traduzida num padrao dito como conclusao, e entregue com um
direcionamento pratico.

A COLISAO QUE A DIRETRIZ CRIOU, E COMO FOI RESOLVIDA

Duas exigencias dela batem de frente com regras que o dono ja tinha fixado como
absolutas, e por isso a implementacao NAO e literal nos dois pontos abaixo. Os
testes deste arquivo travam as duas leituras ao mesmo tempo, para que nem a
diretriz nem as regras antigas sejam silenciosamente revogadas pela proxima
edicao do prompt.

1. "NUNCA ignore o F0 e a linha de base individual do paciente."

   F0, IDM, IPM e a linha de base PODEM NAO EXISTIR. A baseline so trava com voz
   real, e os indices saem `sem_apuracao` quando o PCM nao chegou ou a janela nao
   teve vozeamento — exatamente o caso que gerou o incidente de 19/09/2026 pela
   manha. Uma ordem de cruzar SEMPRE com algo que pode nao ter sido medido e uma
   ordem de inventar, e inventar e o que a determinacao de 03/09/2026 proibiu
   com todas as letras: "quando nao existe a capacidade de apuracao, informar".

   Resolucao: o movimento se cumpre DIZENDO qual peca faltou e o que ela teria
   acrescentado. Isso continua sendo conclusivo e acionavel — nao e o relatorio
   neutro que a diretriz proibe.

2. "Conclusao Fisiologica", com o exemplo "ansiedade emergente" e "contencao
   emocional".

   A regra 6 diz que sinal acustico nao vira fisiologia (o FROID mede voz e
   face, nao sistema nervoso autonomo). A regra 7 proibe afirmar condicao,
   porque nenhum indice tem norma populacional ou validade convergente. E o
   Anexo dos documentos juridicos assinados declara que o produto nao realiza
   diagnostico. Nomear "ansiedade" numa resposta contradiz o contrato do
   proprio servico.

   Resolucao: o movimento 3 entrega a conclusao em linguagem FUNCIONAL sobre o
   comportamento observado no sinal — a fala acelerando, a voz e a face
   divergindo —, e a hipotese clinica e entregue ao profissional no movimento 4,
   que e o passo que a diretriz ja previa. A exigencia de ser conclusivo e
   cumprida; o rotulo que o instrumento nao sustenta, nao.
"""
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import explica_clinico  # noqa: E402

INSTRUCAO = explica_clinico.instrucao()


def _corrido(texto: str) -> str:
    """Minusculas e espaco colapsado.

    As assercoes abaixo procuram FRASES, e o prompt e quebrado em colunas: a
    primeira versao deste arquivo reprovou porque "a hipotese clinica e do
    profissional" cai com "do" no fim de uma linha e "profissional" no inicio da
    seguinte. Travar a posicao da quebra seria testar a formatacao do arquivo,
    e nao a instrucao que chega ao modelo.
    """
    return " ".join(texto.lower().split())


BAIXA = _corrido(INSTRUCAO)
CONTRATO = _corrido(explica_clinico._CONTRATO)


class ADiretrizChegaAoModeloTests(unittest.TestCase):
    """O bloco existe E esta montado na instrucao — o padrao desta casa e a
    peca correta que ninguem consome."""

    def test_o_bloco_de_integracao_entra_na_instrucao(self):
        self.assertIn("INTERPRETACAO INTEGRADA", INSTRUCAO)
        self.assertIn(explica_clinico._INTEGRACAO, INSTRUCAO)

    def test_vem_depois_das_regras_e_antes_do_contrato(self):
        # As regras estabelecem o que e proibido; a integracao diz como
        # responder; o contrato diz em que forma. Fora de ordem, o contrato
        # (que manda cortar) chegaria antes do que manda incluir.
        self.assertLess(
            INSTRUCAO.index(explica_clinico._REGRAS),
            INSTRUCAO.index(explica_clinico._INTEGRACAO),
        )
        self.assertLess(
            INSTRUCAO.index(explica_clinico._INTEGRACAO),
            INSTRUCAO.index(explica_clinico._CONTRATO),
        )


class NuncaUmaMetricaIsoladaTests(unittest.TestCase):
    def test_proibe_explicacao_de_dicionario(self):
        self.assertIn("dicionario", BAIXA)
        self.assertIn("parametro isolado", BAIXA)

    def test_proibe_relatorio_neutro(self):
        self.assertIn("neutro", BAIXA)
        self.assertIn("acionavel", BAIXA)

    def test_exige_a_regua_do_proprio_paciente(self):
        self.assertIn("linha de base", BAIXA)
        self.assertIn("60 segundos", BAIXA)
        self.assertIn("f0", BAIXA)

    def test_exige_o_cruzamento_com_os_indices_de_sintese(self):
        self.assertIn("idm", BAIXA)
        self.assertIn("ipm", BAIXA)

    def test_os_quatro_movimentos_estao_todos_la(self):
        for movimento in ("regua deste paciente", "indices de sintese",
                          "dito com todas as letras", "leituras candidatas"):
            with self.subTest(movimento=movimento):
                self.assertIn(movimento.lower(), BAIXA)

    def test_nao_para_no_meio(self):
        self.assertIn("incompleta", BAIXA)

    def test_os_movimentos_sao_prosa_e_nao_secoes(self):
        """O contrato proibe titulo de secao e lista numerada. Sem isto, a
        diretriz viraria quatro cabecalhos por resposta."""
        self.assertIn("dissolvidos", BAIXA)
        self.assertIn("sem titulo de secao", CONTRATO)
        self.assertIn("sem lista numerada", CONTRATO)


class AConclusaoEDecisivaSemAtravessarALinhaTests(unittest.TestCase):
    """Decisao do dono, 19/09/2026: parar de se esconder.

    "devemos encontrar uma forma de ser mais decisivos, pontuais e coerentes em
    detrimento a nos escondermos atras de uma covardia e medo de dizer a verdade
    apurada (...) somente seja ameno se for possivel, caso contrario vamos
    expressar claramente as nossas conclusoes."

    A sintese aplicada: nomear as leituras candidatas COM o discriminador e o
    dado que as separa e decisivo, util e defensavel; afirmar a condicao como
    fato nao e — nao por prudencia, mas porque nenhum indice tem validade
    convergente e o Anexo II do contrato assinado declara que o servico nao
    realiza diagnostico.

    Se um dia a decisao for atravessar tambem essa linha, estes casos caem — de
    olhos abertos, que e como se toma uma decisao dessas, e nao como efeito
    colateral de uma edicao de prompt.
    """

    def test_proibe_afirmar_condicao_como_fato(self):
        self.assertIn("afirmar uma condicao como fato", BAIXA)
        self.assertIn("o paciente tem ansiedade", BAIXA)
        self.assertIn("escore de risco", BAIXA)

    def test_o_motivo_e_falta_de_base_e_nao_cautela(self):
        # Se o motivo fosse "cautela", a proxima edicao do prompt o removeria
        # como excesso de zelo. O motivo e que a base nao existe, e isso e
        # verificavel: nenhum indice tem validade convergente medida.
        self.assertIn("nao por cautela", BAIXA)
        self.assertIn("norma populacional", BAIXA)
        self.assertIn("anexo ii", BAIXA)

    def test_nao_descreve_mecanismo_interno_que_o_froid_nao_mede(self):
        self.assertIn("mecanismo interno que o froid nao mede", BAIXA)
        self.assertIn("SINAL ACUSTICO NAO VIRA FISIOLOGIA", explica_clinico._REGRAS)

    def test_a_regra_7_deixou_de_ser_ordem_de_calar(self):
        # Determinacao do dono, 19/09/2026: a regra existia e estava sendo lida
        # como licenca para respostas mornas. Ela continua proibindo o
        # diagnostico e passa a EXIGIR a leitura candidata.
        regras = _corrido(explica_clinico._REGRAS)
        self.assertIn("nao e ordem de calar nem de amenizar", regras)
        self.assertIn("leituras candidatas", regras)


class AusenciaNaoVirarSuposicaoTests(unittest.TestCase):
    """A exigencia de cruzar SEMPRE, sobre medidas que podem nao existir, e uma
    ordem de inventar. Este e o ponto onde a diretriz nova encosta na
    determinacao de 03/09/2026, e ele precisa estar travado nos dois sentidos:
    o cruzamento continua obrigatorio, e a lacuna continua sendo declarada."""

    def test_reconhece_que_as_pecas_podem_nao_existir(self):
        self.assertIn("podem nao existir", BAIXA)
        self.assertIn("sem apuracao", BAIXA)

    def test_a_lacuna_e_declarada_em_vez_de_preenchida(self):
        self.assertIn("qual peca faltou", BAIXA)
        for proibido in ("valor plausivel", "provavelmente", "ultimo valor conhecido"):
            with self.subTest(proibido=proibido):
                self.assertIn(proibido, BAIXA)

    def test_declarar_a_ausencia_conta_como_resposta_conclusiva(self):
        # Sem isto as duas ordens se contradizem, e o modelo resolve a
        # contradicao do jeito errado: inventando para nao parecer neutro.
        self.assertIn("e uma resposta conclusiva e acionavel", BAIXA)

    def test_nenhuma_norma_populacional(self):
        self.assertIn("norma populacional", BAIXA)


class OContratoDaRespostaAcomodaOsQuatroTests(unittest.TestCase):
    def test_o_contrato_aponta_para_os_movimentos_em_vez_de_redescreve_los(self):
        # Duas descricoes da mesma coisa divergem — ja divergiram nesta casa.
        self.assertIn("quatro movimentos", CONTRATO)
        self.assertIn("nao uma segunda lista", CONTRATO)

    def test_o_que_encolhe_quando_o_orcamento_aperta_esta_dito(self):
        self.assertIn("nunca", CONTRATO)
        self.assertIn("movimento 3", CONTRATO)
        self.assertIn("movimento 4", CONTRATO)

    def test_o_limite_de_palavras_continua_existindo(self):
        # Quem le esta com um paciente na frente. A diretriz pede profundidade,
        # nao volume.
        self.assertIn("150 palavras", CONTRATO)


if __name__ == "__main__":
    unittest.main()
