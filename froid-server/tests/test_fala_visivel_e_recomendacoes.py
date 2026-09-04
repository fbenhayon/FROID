"""A fala separada por falante pertence ao RELATORIO, nao a tela da sessao.

Historia curta, porque custou uma sessao real com paciente:

Em 03/09/2026 o pedido foi separar a fala do paciente e a do profissional. Eu li
isso como "mostrar na tela" e coloquei uma transcricao ao vivo nos tres layouts,
mais um aviso de recomendacoes de uso e um aviso de ausencia de apuracao. Em
04/09/2026, com paciente em atendimento, o dono corrigiu: a separacao DR/PC era
para as transcricoes DOS RELATORIOS. A tela da sessao tinha de continuar como
era.

Pior: a edicao que inseriu o bloco no layout simplificado saiu corrompida — sete
linhas ganharam um "10" literal no comeco, que o navegador renderizou como texto
solto na tela, em atendimento.

O que este arquivo passa a garantir:

1. Os canais continuam separados na captura (isso nunca esteve em questao, e e a
   base de tudo o que vem depois).
2. O relatorio mostra a fala com DR/PC — ali a separacao e o produto.
3. A tela da sessao NAO carrega transcricao ao vivo, recomendacoes de uso nem
   aviso de ausencia. Esta e a guarda contra eu reintroduzir o que foi removido.
4. Nenhum arquivo do painel volta a ter linha corrompida por edicao mecanica.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"
SESSAO = (PAINEL / "pages" / "LiveSession.tsx").read_text(encoding="utf-8")
PACIENTE = (PAINEL / "pages" / "PatientSessionPage.tsx").read_text(encoding="utf-8")
RELATORIO = (PAINEL / "pages" / "SessionReport.tsx").read_text(encoding="utf-8")


class OsCanaisContinuamSEPARADOS(unittest.TestCase):
    """A base de tudo. Se os dois canais virarem um, nenhum rotulo abaixo
    significa nada — e o Data-Froid perde a capacidade de distinguir o que o
    profissional propos do que o paciente encontrou."""

    def test_dois_gravadores_com_rotulo_FIXO_por_canal(self):
        self.assertIn(
            'startSpeechToText(patientTranscriptStream, "PC", "patient")', SESSAO
        )
        self.assertIn('startSpeechToText(stream, "DR", "professional")', SESSAO)

    def test_o_motor_acustico_e_alimentado_SO_pelo_paciente(self):
        """`acoustic-f0` e a entrada de audio do motor. Se o painel do
        profissional passar a chamar isso, a voz dele entra na medida."""
        self.assertIn("acoustic-f0", PACIENTE)
        self.assertNotIn("acoustic-f0", SESSAO)

    def test_a_fala_continua_sendo_acumulada_para_o_relatorio(self):
        """Sair da tela nao pode significar sair do registro: o ref alimenta o
        relatorio e o servidor."""
        self.assertIn("transcriptLinesRef.current", SESSAO)


class OhRelatorioMOSTRAaFala(unittest.TestCase):
    """Aqui — e so aqui — a separacao vira produto visivel."""

    def test_ha_secao_de_transcricao(self):
        self.assertIn("const TranscricaoDaSessao", RELATORIO)
        self.assertIn(
            "<TranscricaoDaSessao transcript={report.transcript} />", RELATORIO
        )

    def test_com_legenda_de_falante(self):
        self.assertIn("DR profissional", RELATORIO)
        self.assertIn("PC paciente", RELATORIO)

    def test_o_tooltip_explica_a_origem_do_rotulo(self):
        """O rotulo vem do CANAL de audio, nao de suposicao sobre o conteudo —
        e quem le o documento precisa saber disso."""
        self.assertIn("identificado por canal de áudio", RELATORIO)


class ATelaDaSessaoNAOCarregaNadaDisso(unittest.TestCase):
    """A guarda contra a reintroducao. Tres componentes foram removidos do
    atendimento em 04/09/2026, cada um por um motivo diferente:

    - transcricao ao vivo: pertence ao relatorio;
    - recomendacoes de uso: pertencem a tela em que o paciente aceita o convite;
    - aviso de ausencia de apuracao: o dono nao quer o cartaz na sessao.

    O que NAO mudou, e nao pode mudar: indice sem medida continua em branco. A
    proibicao de simular vale no dado, nao no cartaz.
    """

    def test_sem_transcricao_ao_vivo(self):
        self.assertNotIn("TranscricaoAoVivo", SESSAO)

    def test_sem_recomendacoes_de_uso(self):
        self.assertNotIn("RecomendacoesDeUso", SESSAO)

    def test_sem_aviso_de_ausencia_na_sessao(self):
        self.assertNotIn("AvisoVozSimulada", SESSAO)

    def test_o_video_ocupa_metade_da_coluna_nos_layouts_completos(self):
        """`basis-1/2` e metade de verdade; `flex-[0.8]` era peso relativo aos
        irmaos, que mudava sozinho conforme o que estivesse ao lado."""
        self.assertEqual(SESSAO.count("basis-1/2 shrink-0 items-center"), 2)

    def test_o_layout_simplificado_nao_ganhou_coluna_de_video(self):
        """No simplificado a tela e como sempre foi: video em aspect-video,
        titulo dos cortes e barra de tempo."""
        self.assertIn("flex aspect-video min-h-[220px] shrink-0", SESSAO)


class NenhumArquivoDoPainelTemLinhaCORROMPIDA(unittest.TestCase):
    """A edicao mecanica que inseriu "10" no comeco de sete linhas passou pelo
    typecheck (era texto dentro de JSX, valido) e so apareceu na tela, em
    atendimento. Nenhum teste pegava isso, porque nenhum teste olhava para a
    forma do arquivo."""

    SUSPEITA = re.compile(r"^\d+[{<]|^\d+\s{2}<", re.MULTILINE)

    def test_nenhuma_linha_comeca_com_digito_colado_em_jsx(self):
        for arquivo in sorted(PAINEL.rglob("*.tsx")):
            texto = arquivo.read_text(encoding="utf-8")
            achados = self.SUSPEITA.findall(texto)
            self.assertEqual(
                achados,
                [],
                f"{arquivo.relative_to(PAINEL)} tem linha iniciada por digito "
                f"colado em JSX — sinal de edicao mecanica corrompida: {achados}",
            )


if __name__ == "__main__":
    unittest.main()
