"""A fala aparece, com quem falou, na ordem em que aconteceu.

O sistema separava os canais desde sempre — dois microfones, dois gravadores,
dois rotulos fixos:

    LiveSession.tsx:4476   startSpeechToText(patientTranscriptStream, "PC", "patient")
    LiveSession.tsx:4685   startSpeechToText(stream, "DR", "professional")

E `appendTranscriptText` acumulava cada fala prefixada com "DR. - " ou "PC - ",
em ordem, sem duplicata. Havia ate um limite chamado
MAX_VISIBLE_TRANSCRIPT_LINES.

Nada renderizava. As linhas viviam num `useRef`, que nao dispara render, e o
relatorio tambem nao as mostrava — nem na tela nem no PDF. O nome da constante
prometia uma visibilidade que nunca existiu.

Isso custou caro num caso concreto: dos quatro erros que um paciente apontou no
relatorio dele, tres eram da camada semantica — cidade trocada, trecho
incoerente, palavra perdida. Nenhum daria para perceber durante a consulta,
porque a transcricao so aparecia depois, dentro do resumo ja redigido.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"
SESSAO = (PAINEL / "pages" / "LiveSession.tsx").read_text(encoding="utf-8")
RELATORIO = (PAINEL / "pages" / "SessionReport.tsx").read_text(encoding="utf-8")
AO_VIVO = (PAINEL / "components" / "indicators" / "TranscricaoAoVivo.tsx").read_text(
    encoding="utf-8"
)
RECOMENDA = (
    PAINEL / "components" / "indicators" / "RecomendacoesDeUso.tsx"
).read_text(encoding="utf-8")


class OsCanaisContinuamSEPARADOS(unittest.TestCase):
    """A base de tudo. Se os dois canais virarem um, nenhum rotulo abaixo
    significa nada — e o Data-Froid perde a capacidade de distinguir o que o
    profissional propos do que o paciente encontrou."""

    def test_dois_gravadores_com_rotulo_FIXO_por_canal(self):
        self.assertIn('startSpeechToText(patientTranscriptStream, "PC", "patient")', SESSAO)
        self.assertIn('startSpeechToText(stream, "DR", "professional")', SESSAO)

    def test_o_motor_acustico_e_alimentado_SO_pelo_paciente(self):
        """`acoustic-f0` e a entrada de audio do motor. Se o painel do
        profissional passar a chamar isso, a voz dele entra na medida."""
        paciente = (PAINEL / "pages" / "PatientSessionPage.tsx").read_text(encoding="utf-8")
        self.assertIn("acoustic-f0", paciente)
        self.assertNotIn("acoustic-f0", SESSAO)


class AFalaAPARECE(unittest.TestCase):
    def test_as_linhas_estao_em_ESTADO_e_nao_so_num_ref(self):
        """Em `useRef` nao ha render: era por isso que MAX_VISIBLE_TRANSCRIPT_LINES
        existia sem nada visivel."""
        self.assertIn("const [transcriptLines, setTranscriptLines] = useState<string[]>", SESSAO)
        self.assertIn("setTranscriptLines(transcriptLinesRef.current)", SESSAO)

    def test_aparece_nos_TRES_layouts(self):
        """Quem escolhe o layout simplificado quer menos ruido na tela, nao
        menos informacao sobre o que foi dito."""
        self.assertEqual(SESSAO.count("<TranscricaoAoVivo"), 3)

    def test_a_ordem_e_cronologica_e_rola_sozinha(self):
        # Sem rolagem automatica, o profissional teria de rolar a cada frase
        # durante o atendimento — ninguem faria, e o painel voltaria a ser
        # decorativo.
        self.assertIn("scrollIntoView", AO_VIVO)

    def test_o_falante_e_distinguido_por_COR_e_rotulo(self):
        self.assertIn('doProfissional ? "DR" : "PC"', AO_VIVO)
        self.assertIn("border-sky-500", AO_VIVO)
        self.assertIn("border-emerald-500", AO_VIVO)


class OhRelatorioMOSTRAaFala(unittest.TestCase):
    def test_ha_secao_de_transcricao(self):
        self.assertIn("const TranscricaoDaSessao", RELATORIO)
        self.assertIn("<TranscricaoDaSessao transcript={report.transcript} />", RELATORIO)

    def test_com_legenda_de_falante(self):
        self.assertIn("DR profissional", RELATORIO)
        self.assertIn("PC paciente", RELATORIO)

    def test_o_tooltip_explica_a_origem_do_rotulo(self):
        """O rotulo vem do CANAL de audio, nao de suposicao sobre o conteudo —
        e quem le o documento precisa saber disso."""
        self.assertIn("identificado por canal de áudio", RELATORIO)


class ORecomendacoesAntesDeComecar(unittest.TestCase):
    """Tres comportamentos mudaram de um jeito que, sem explicacao, parecem
    defeito. O terceiro e o mais caro de descobrir depois."""

    def test_o_aviso_existe_nos_layouts(self):
        self.assertEqual(SESSAO.count("<RecomendacoesDeUso"), 2)

    def test_avisa_sobre_o_primeiro_minuto(self):
        self.assertIn("Deixe o paciente falar no primeiro minuto", RECOMENDA)

    def test_avisa_que_o_ambar_NAO_e_defeito(self):
        self.assertIn("não é defeito", RECOMENDA)
        self.assertIn('nunca "zero"', RECOMENDA)

    def test_avisa_do_presencial_sem_voz_cadastrada(self):
        """Com um microfone so e sem assinatura, o audio e atribuido INTEIRO ao
        paciente — e os primeiros minutos sao tipicamente o profissional
        falando."""
        self.assertIn("presencialSemVoz", RECOMENDA)
        self.assertIn("inteiro ao paciente", RECOMENDA)

    def test_o_aviso_e_lembrado_por_sessao(self):
        """Instrucao repetida a cada render vira ruido que se aprende a
        ignorar — e a que mais importa e a que some primeiro."""
        self.assertIn("sessionStorage", RECOMENDA)
        self.assertIn("froid_recomendacoes_vistas", RECOMENDA)

    def test_da_para_reabrir_depois_de_fechado(self):
        self.assertIn("Recomendações de uso", RECOMENDA)
        self.assertIn("setAberto(true)", RECOMENDA)


if __name__ == "__main__":
    unittest.main()
