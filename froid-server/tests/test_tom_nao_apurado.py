"""Campo sem medida se declara vazio, nunca sorteia um valor.

Ate 02/09/2026, `emotional_tone` era um np.random.choice entre seis rotulos —
SEM CONDICAO NENHUMA. Nao era o modo simulado: era sempre, inclusive com audio
real chegando. Um dado de seis faces.

O valor sorteado nao ficava no servidor. Chegava ao painel do profissional, ao
relatorio, a AREA DO PROPRIO PACIENTE, ao acervo anonimizado do Data-Froid, e
ao prompt da IA que redige os resumos — onde influenciava texto que o clinico
leria como leitura de sessao.

Categorizar tom exigiria fundir ritmo de fala, semantica e energia da voz sob
um criterio definido. Esse criterio nao existe. Inventa-lo no lugar do sorteio
seria trocar aleatorio por arbitrario — pior, porque arbitrario parece
fundamentado.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

CORE = (SERVER_DIR / "froid_core.py").read_text(encoding="utf-8")
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
PAINEL = (
    SERVER_DIR.parent / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
).read_text(encoding="utf-8")


class OSorteioSaiu(unittest.TestCase):
    def test_o_tom_nao_e_mais_sorteado(self):
        self.assertNotIn(
            'np.random.choice(["neutro", "ansioso", "triste", "irritado", "alegre", "suprimido"])',
            CORE,
        )

    def test_o_tom_sai_vazio(self):
        self.assertIn('emotional_tone = ""', CORE)

    def test_nenhum_random_alimenta_o_campo_de_tom(self):
        """A atribuicao de `emotional_tone` nao pode voltar a ser aleatoria."""
        atribuicoes = re.findall(r"^\s*emotional_tone\s*=\s*(.+)$", CORE, re.M)
        self.assertTrue(atribuicoes, "o campo sumiu do motor")
        for valor in atribuicoes:
            self.assertNotIn("random", valor)


class NaoVazaParaOTexto(unittest.TestCase):
    def test_tom_vazio_nao_entra_no_prompt_da_IA(self):
        """`is not None` deixava passar string vazia e escrevia ' | tom: '.

        O prompt e o que a IA le para redigir o resumo da sessao. Um rotulo
        sorteado ali nao ficava num campo discreto: virava prosa clinica.
        """
        self.assertNotIn("if tone is not None else ''", MAIN)
        self.assertIn("if tone else ''", MAIN)


class NaoRessuscitaNoPainel(unittest.TestCase):
    def test_vazio_nao_vira_neutro(self):
        """`|| "neutro"` transformava NAO APURADO em afirmacao de neutralidade.

        Seria a mesma fabricacao com outro nome, e mais dificil de achar: um
        campo preenchido nao levanta suspeita nenhuma.
        """
        self.assertNotIn('|| ""),\n      "neutro"', PAINEL)
        trecho = PAINEL[PAINEL.index("emotionalTone:") : PAINEL.index("emotionalTone:") + 400]
        self.assertNotIn('"neutro"', trecho)

    def test_duas_ausencias_nao_viram_constancia_observada(self):
        """Dois cortes sem tom nao provam que o tom ficou igual."""
        self.assertIn('"nao_apurado"', PAINEL)
        i = PAINEL.index("emotionalToneShift:")
        trecho = PAINEL[i : i + 400]
        self.assertIn("nao_apurado", trecho)


class NenhumLugarRessuscitaONeutro(unittest.TestCase):
    """Ontem removi o sorteio no servidor e o `|| "neutro"` de UM lugar do
    painel. Sobravam QUATRO — e cada um reconvertia o vazio numa afirmacao de
    neutralidade.

    Isso e pior que o sorteio original em um aspecto: campo preenchido nao
    levanta suspeita. "neutro" na tela parece leitura; vazio parece o que e.
    """

    def test_nenhuma_LINHA_DE_CODIGO_fabrica_neutro(self):
        suspeitas = []
        for numero, linha in enumerate(PAINEL.splitlines(), 1):
            despida = linha.strip()
            if despida.startswith("//") or despida.startswith("*"):
                continue  # comentario explicando a ausencia nao e a ausencia
            if '"neutro"' in linha:
                suspeitas.append(f"{numero}: {despida[:90]}")
        self.assertEqual(suspeitas, [], "codigo ainda fabrica tom neutro")

    def test_o_valor_de_queda_e_vazio(self):
        self.assertIn('|| latestAudio.emotional_tone || ""', PAINEL)
        self.assertIn('emotional_tone: (prev?.emotional_tone as string) || ""', PAINEL)


if __name__ == "__main__":
    unittest.main()
