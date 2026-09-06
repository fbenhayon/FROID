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
    """A garantia, e nao o mecanismo que a implementava.

    Este teste exigia literalmente a presenca de `if tone else ''` em main.py —
    a guarda da f-string que montava a resposta local por metrica. Em
    06/09/2026 aquela cadeia de respostas escritas a mao foi substituida pelo
    catalogo de `explica_clinico`, e a f-string deixou de existir: o teste caiu
    defendendo um mecanismo removido, sobre uma garantia que ficou MAIS forte.

    Reescrito para afirmar o que o paciente e o profissional precisam que seja
    verdade: nenhum caminho de main.py escreve um tom, e a ficha do TOM declara
    a ausencia de apuracao em vez de sugerir leitura.
    """

    def test_o_defeito_original_nao_volta(self):
        # `is not None` deixava passar string vazia e escrevia ' | tom: '.
        self.assertNotIn("if tone is not None else ''", MAIN)

    def test_main_nao_interpola_tom_em_texto_nenhum(self):
        self.assertNotIn("tom:", MAIN)
        self.assertFalse(
            re.search(r"\btone\b", MAIN),
            "voltou a existir uma variavel de tom no caminho de texto do servidor",
        )

    def test_a_ficha_do_tom_declara_que_nao_ha_apuracao(self):
        import explica_clinico

        ficha = explica_clinico.INDICE_POR_ROTULO["TOM"]
        self.assertIn("SEM CAPACIDADE DE APURACAO", ficha.medida)
        self.assertIn("ausencia declarada", ficha.leitura)

    def test_o_glossario_nao_afirma_tom_quando_o_painel_mostra_traco(self):
        import explica_clinico

        texto = explica_clinico.glossario_do_painel(
            "o que quer dizer TOM", {"panel_metrics": {"TOM": "--"}}
        )
        linha = next(l for l in texto.splitlines() if l.startswith("- Valor nesta sessao"))
        self.assertIn("SEM APURACAO", linha)
        self.assertNotIn("neutro", linha.lower())


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
