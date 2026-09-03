"""Toda aleatoriedade do motor mora num lugar so, e esse lugar e o fallback.

Auditoria de 02/09/2026, campo a campo, nos 98 que o motor publica. O criterio
que o dono do produto pediu, textual: "nenhum deles esta operando de forma
randomica e sem referencia nenhuma".

Tres coisas que costumam virar uma so, e nao sao:

  ALEATORIO           valor sorteado a cada tick, com ou sem audio.
  SIMULADO SEM AUDIO  deterministico, gerado so quando nao chega PCM. Legitimo:
                      e o fallback honesto, e a procedencia declara que e ele.
  SEM LASTRO          deterministico e consistente, mas de formula propria do
                      FROID, sem fonte publicada. Nao e defeito de engenharia —
                      e uma questao de como se comunica o resultado.

O que a auditoria achou de ALEATORIO, e que este teste impede de voltar:

  words_per_window       np.random.poisson(2.4) a cada tick
  words_per_minute_10m   media da janela alimentada pelo Poisson
  total_words_session    a soma, mais um randint(0, 20) por tick
  speech_rate_proxy      copia arredondada do words_per_minute_10m
  transcription_snippet  np.random.choice entre frases fixas
  emotional_tone         np.random.choice entre seis rotulos (removido antes)

Nenhum deles chegava a tela: o painel recalcula as palavras da transcricao real
e apaga a frase de amostra. Mas saida fabricada SEM LEITOR e pior que saida
errada COM leitor — ninguem a corrige, e o proximo que a ligar num grafico
recebe um numero inventado sem aviso nenhum.
"""

import ast
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

CORE_PATH = SERVER_DIR / "froid_core.py"
CORE = CORE_PATH.read_text(encoding="utf-8")
# Mesmo texto com todo espaco em branco colapsado. Duas vezes hoje uma
# assercao de string literal caiu por reformatacao do codigo que ela
# vigia, sem nada da garantia ter mudado: aqui se verifica a condicao,
# nao onde a linha quebrou.
CORE_LINEAR = " ".join(CORE.split())
# So o codigo, sem comentario nenhum: o historico dos defeitos antigos cita
# valores que nao devem mais ser emitidos, e apagar esse historico para o
# teste passar seria trocar a memoria pela conveniencia.
CORE_SEM_COMENTARIO = chr(10).join(
    linha for linha in CORE.splitlines()
    if not linha.lstrip().startswith("#")
)

# NAO HA MAIS LUGAR LEGITIMO PARA SORTEAR.
#
# Ate 02/09/2026 este arquivo tolerava np.random dentro de MockBiometricStream,
# o gerador de reserva. A determinacao do dono do produto encerrou a tolerancia:
# proibido simular, e sem capacidade de apuracao o sistema INFORMA que nao ha.
# O gerador foi removido inteiro; o motor agora devolve `_payload_sem_apuracao`.


def _linhas_com_random():
    """Linhas de CODIGO (nao comentario) que sorteiam, em qualquer lugar.

    Arvore sintatica, nao grep: este arquivo tem tres comentarios que MENCIONAM
    np.random para explicar a propria remocao, e comentario nao e uso.
    """
    arvore = ast.parse(CORE)
    suspeitas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Attribute):
            continue
        origem = getattr(no.value, "id", None) or getattr(
            getattr(no.value, "value", None), "id", None
        )
        if origem == "np" and getattr(no.value, "attr", None) == "random":
            suspeitas.append((no.lineno, no.attr))
    return suspeitas


class NadaEhSimulado(unittest.TestCase):
    def test_o_motor_nao_sorteia_em_lugar_nenhum(self):
        suspeitas = _linhas_com_random()
        self.assertEqual(
            suspeitas,
            [],
            "np.random no motor: "
            + ", ".join(f"linha {l} (np.random.{f})" for l, f in suspeitas),
        )

    def test_o_gerador_foi_REMOVIDO_e_nao_apenas_desligado(self):
        """Codigo que sabe inventar numero plausivel e arma carregada em cima
        da mesa: um `if` invertido por engano o religa inteiro."""
        self.assertNotIn("class MockBiometricStream", CORE)
        self.assertNotIn("def generate_voice_spectral", CORE)
        self.assertNotIn("def generate_facs_dissonance", CORE)

    def test_sem_medida_o_motor_DECLARA_a_ausencia(self):
        self.assertIn("_payload_sem_apuracao", CORE)
        self.assertIn('"apuracao_disponivel": False', CORE)
        self.assertIn('"coherence_status": "SEM_APURACAO"', CORE)

    def test_o_portao_barra_ANTES_de_calcular(self):
        """Se o retorno viesse depois, os 98 campos ja teriam sido derivados de
        ruido antes de alguem perguntar se havia medida.

        Mede por POSICAO relativa, nao por janela de caracteres: a primeira
        versao contava 1500 chars a partir de `def process_tick` e quebrou
        quando a docstring do metodo cresceu — falso alarme sobre codigo
        correto, que e o tipo de teste que se aprende a ignorar.
        """
        inicio = CORE.index("def process_tick")
        portao = CORE.index("if not tem_voz_medida:", inicio)
        # A primeira linha que de fato calcula algo sobre o espectro.
        calculo = CORE.index("self.baseline_buffer.append", inicio)
        self.assertLess(portao, calculo, "o portao ficou DEPOIS do calculo")
        # Ate o proximo `def`, nao numa janela de caracteres: e a SEGUNDA vez
        # que uma janela fixa quebra este teste por crescimento de comentario.
        # Sem "\n" no padrao: o arquivo usa CRLF e a busca por "\n    def "
        # nao casaria. O def indentado basta como fronteira do metodo.
        fim_do_metodo = CORE.index("    def ", portao)
        self.assertIn(
            "return self._payload_sem_apuracao(",
            CORE[portao:fim_do_metodo],
        )

    def test_sem_face_as_flags_sao_vazias_e_nao_sorteadas(self):
        self.assertIn('facs_source = "sem_apuracao"', CORE)
        self.assertIn("facs_dissonance_flags = {i: False for i in range(1, 13)}", CORE)


class OServidorNaoInventaPalavras(unittest.TestCase):
    """A transcricao acontece no NAVEGADOR. O servidor nao tem o texto, entao
    nao tem como contar — e zero e a leitura honesta de quem nao mede."""

    def test_a_janela_de_palavras_e_zero_e_nao_sorteada(self):
        # Basta a atribuicao: o teste por arvore sintatica acima ja garante
        # que nao ha sorteio fora do fallback, e faz isso sem confundir
        # comentario com codigo — foi o que derrubou a primeira versao desta
        # asercao, que achava o np.random no comentario que explica sua saida.
        self.assertIn("words_this_window = 0", CORE)

    def test_o_total_da_sessao_nao_ganha_palavras_imaginarias(self):
        self.assertIn("total_words = sum(self.word_windows)", CORE)

    def test_a_frase_de_amostra_saiu(self):
        self.assertIn('transcription_snippet = ""', CORE)


class ProcedenciaDizAVerdade(unittest.TestCase):
    """Os campos de procedencia sao o que separa 'simulado sem audio' de
    'aleatorio': sem eles, quem le nao tem como saber em qual dos dois esta."""

    def test_o_motor_declara_a_origem_da_voz(self):
        # Sem casar formatacao: o campo existe, e o unico caminho para
        # "real_pcm" passa por features medidas.
        self.assertIn('"voice_features_source"', CORE)
        # A condicao, nao a formatacao: o unico caminho para "real_pcm"
        # passa por features de voz MEDIDAS.
        self.assertIn('"real_pcm" if (real and "zcr" in real)', CORE_LINEAR)

    def test_a_ausencia_nao_se_chama_simulacao(self):
        """`"mock"` prometia um gerador que nao existe mais. O valor negativo
        tem de ser a ausencia declarada, porque e o que a tela vai escrever.

        Verifica o CODIGO, nao os comentarios: a linha 542 cita "mock" para
        registrar o defeito antigo, e esse registro tem de sobreviver. O que
        nao pode e o motor EMITIR a palavra."""
        self.assertNotIn('"mock"', CORE_SEM_COMENTARIO)
        self.assertIn('"sem_apuracao"', CORE)

    def test_o_motor_declara_a_origem_da_f0(self):
        self.assertIn('"f0_source": "yin_pcm" if', CORE)

    def test_o_motor_declara_a_origem_da_face(self):
        self.assertIn('"facs_source": facs_source', CORE)


PAINEL_DIR = SERVER_DIR.parent / "froid-dashboard" / "src"
SESSAO = (PAINEL_DIR / "pages" / "LiveSession.tsx").read_text(encoding="utf-8")
RISCO = (PAINEL_DIR / "components" / "indicators" / "RiskChart.tsx").read_text(
    encoding="utf-8"
)


class ATelaCONSOMEaDeclaracaoDeAusencia(unittest.TestCase):
    """Declarar a ausencia sem ninguem ler e pior que nao declarar.

    A re-auditoria de 03/09/2026 pegou isto antes do deploy: o motor passou a
    emitir `apuracao_disponivel: False` e `coherence_status: "SEM_APURACAO"`, e
    o painel nao consumia nem um nem outro — o campo existia so na declaracao
    do tipo.

    O efeito seria pior que o estado anterior, porque cada consumidor tem o
    proprio valor de queda e todos eles AFIRMAM:

      - RiskChart tratava qualquer coerencia diferente de NEUTRO e COERENTE
        como alerta. "SEM_APURACAO" somaria +12 ao risco e, com todo o resto
        nulo, viraria 100% de "tensao laringea sustentada" — alarme clinico
        fabricado pela propria mudanca que veio acabar com a fabricacao.
      - O historico do IPM empilhava zero por tick sem medida, e zero e um
        valor legitimo de IPM: o grafico mostraria uma queda que ninguem viu.
    """

    def test_o_painel_LE_a_declaracao(self):
        self.assertIn("apuracao_disponivel === false", SESSAO)
        self.assertIn("semApuracaoAgora", SESSAO)

    def test_ausencia_nao_entra_no_historico_do_ipm(self):
        i = SESSAO.index("const nextHistory")
        trecho = SESSAO[i - 400 : i + 300]
        self.assertIn("semApuracao", trecho)
        self.assertNotIn('typeof p.ipm_score === "number" ? p.ipm_score : 0', trecho)

    def test_os_graficos_derivados_recebem_VAZIO(self):
        self.assertIn("const displayZones = semApuracaoAgora", SESSAO)
        self.assertIn("const displayIpm = semApuracaoAgora", SESSAO)
        self.assertIn("semApuracaoAgora ? {} :", SESSAO)

    def test_coerencia_vazia_em_vez_de_NEUTRO(self):
        """"NEUTRO" seria uma afirmacao de coerencia neutra sobre nada medido."""
        i = SESSAO.index("const displayCoherence")
        self.assertIn("semApuracaoAgora", SESSAO[i : i + 200])

    def test_ausencia_NAO_e_alerta_de_coerencia(self):
        self.assertIn('coherenceStatus === "SEM_APURACAO"', RISCO)
        i = RISCO.index("const isCoherenceAlert")
        self.assertIn("!semApuracao", RISCO[i : i + 200])

    def test_sem_ipm_nao_ha_carga_de_ipm(self):
        self.assertIn("ipmScore === null ? 0 :", RISCO)


if __name__ == "__main__":
    unittest.main()
