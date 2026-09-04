"""O instrumento não entra no prontuário, e o falante não se adivinha.

Duas coisas apareceram no mesmo relatório real de 04/09/2026, e as duas vinham
do resumidor.

A primeira: um trecho inteiro virou o tema "Conexão e funcionamento do FROID", e
o resumo relatou que "são mencionados problemas com gráficos e a falta de
apuração de índices acústicos". Os defeitos do nosso próprio produto, redigidos
dentro do documento pessoal e confidencial de um paciente. Operar o instrumento
não é material clínico — e escrever sobre ele ali é pior do que não escrever
nada, porque o documento é a pauta da próxima sessão.

A segunda: "O filho, por outro lado, defende uma abordagem mais acolhedora."
Naquela sessão a frase estava certa. Mas o sistema não sabe quem é filho de
quem: ele leu isso do conteúdo das palavras. Acertou por sorte.

E é justamente o mecanismo que o produto inteiro passou semanas eliminando. Quem
falou é MEDIDA — vem do canal de áudio, com rótulo fixo, dois gravadores
separados. Parentesco e papel são CONTEÚDO — vêm do que foi dito. Deixar a
camada semântica reintroduzir o palpite por outra porta desfaz a garantia sem
tocar em nenhuma linha que a sustenta. Foi esse mesmo mecanismo que trocou a
cidade e produziu o trecho incoerente que um paciente apontou.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from localization import (  # noqa: E402
    SESSION_LANGUAGES,
    summary_prompt,
    summary_system_prompt,
)


class OInstrumentoFicaDeForaDoProntuario(unittest.TestCase):
    def setUp(self):
        self.prompt = summary_prompt("DR. - teste", 0, 10, "pt-BR")

    def test_manda_deixar_de_fora_a_conversa_sobre_a_ferramenta(self):
        self.assertIn("recording tool", self.prompt)
        self.assertIn("Leave", self.prompt)

    def test_nomeia_o_que_conta_como_ferramenta(self):
        """Lista explícita: o resumidor não tem de adivinhar o que é operação."""
        for palavra in ("connection", "microphone", "camera", "charts", "defects"):
            with self.subTest(palavra=palavra):
                self.assertIn(palavra, self.prompt)

    def test_trecho_so_de_operacao_e_DECLARADO(self):
        """Silenciar não basta: um trecho vazio no relatório lê como se aquele
        pedaço da sessão não tivesse valido nada. Dizer que não houve material
        clínico é diferente de não dizer nada."""
        self.assertIn("no clinical material", self.prompt)

    def test_a_regra_tambem_esta_no_papel_do_sistema(self):
        """A instrução do usuário pode ser diluída num transcript longo; a do
        sistema, não."""
        self.assertIn("recording tool", summary_system_prompt("pt-BR"))


class OFalanteVemDoCanalENaoDoConteudo(unittest.TestCase):
    def setUp(self):
        self.prompt = summary_prompt("DR. - teste", 0, 10, "pt-BR")

    def test_os_rotulos_reais_estao_no_prompt(self):
        """`DR.` e `PC` são os prefixos que `appendTranscriptText` grava. Se
        divergirem, o resumidor volta a adivinhar sem nada acusar."""
        self.assertIn("'DR.'", self.prompt)
        self.assertIn("'PC'", self.prompt)

    def test_proibe_atribuir_fala_a_quem_o_rotulo_nao_diz(self):
        self.assertIn("by that label", self.prompt)
        self.assertIn(
            "never attribute an utterance to a speaker other than the one the transcript labels",
            summary_system_prompt("pt-BR").lower(),
        )

    def test_parentesco_e_papel_sao_fala_relatada(self):
        self.assertIn("reported speech", self.prompt)
        self.assertIn("never something you know", self.prompt)


class AsDuasRegrasValemEmTODOSOsIdiomas(unittest.TestCase):
    """O produto tem edição em quatro idiomas. Uma regra que só vale em
    português é uma regra que não vale."""

    def test_todo_idioma_recebe_as_duas_instrucoes(self):
        self.assertGreaterEqual(len(SESSION_LANGUAGES), 2)
        for locale in SESSION_LANGUAGES:
            with self.subTest(locale=locale):
                prompt = summary_prompt("DR. - teste", 0, 10, locale)
                self.assertIn("recording tool", prompt)
                self.assertIn("reported speech", prompt)
                self.assertIn("recording tool", summary_system_prompt(locale))


if __name__ == "__main__":
    unittest.main()
