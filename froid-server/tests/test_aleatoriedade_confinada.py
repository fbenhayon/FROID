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

# Onde sortear e legitimo: o gerador de reserva, que so roda sem PCM real.
CLASSE_DE_FALLBACK = "MockBiometricStream"


def _linhas_com_random_fora_do_fallback():
    """Linhas de CODIGO (nao comentario) que sorteiam fora do fallback.

    Usa a arvore sintatica em vez de grep: comentario que MENCIONA np.random
    para explicar sua propria remocao nao pode contar como uso — e este arquivo
    tem tres deles, de proposito.
    """
    arvore = ast.parse(CORE)
    permitido = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == CLASSE_DE_FALLBACK:
            for interno in ast.walk(no):
                if hasattr(interno, "lineno"):
                    permitido.add(interno.lineno)

    suspeitas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Attribute):
            continue
        origem = getattr(no.value, "id", None) or getattr(
            getattr(no.value, "value", None), "id", None
        )
        alvo = getattr(no.value, "attr", None)
        if origem == "np" and alvo == "random":
            if no.lineno not in permitido:
                suspeitas.append((no.lineno, no.attr))
    return suspeitas


class AleatoriedadeConfinada(unittest.TestCase):
    def test_nenhum_sorteio_fora_do_gerador_de_reserva(self):
        suspeitas = _linhas_com_random_fora_do_fallback()
        self.assertEqual(
            suspeitas,
            [],
            "np.random fora de "
            + CLASSE_DE_FALLBACK
            + ": "
            + ", ".join(f"linha {l} (np.random.{f})" for l, f in suspeitas),
        )

    def test_o_gerador_de_reserva_continua_existindo(self):
        """O teste acima passaria trivialmente se o fallback sumisse — e sem ele
        uma sessao sem audio quebraria em vez de degradar."""
        self.assertIn(f"class {CLASSE_DE_FALLBACK}", CORE)
        self.assertIn("np.random.normal", CORE)


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
        self.assertIn('"voice_features_source": "real_pcm" if', CORE)

    def test_o_motor_declara_a_origem_da_f0(self):
        self.assertIn('"f0_source": "yin_pcm" if', CORE)

    def test_o_motor_declara_a_origem_da_face(self):
        self.assertIn('"facs_source": facs_source', CORE)


if __name__ == "__main__":
    unittest.main()
