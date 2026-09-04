"""O corte fica onde a mao ja esta, e o atalho nao pode divergir do botao.

Fechar um corte sempre foi possivel: o controle existia dentro do painel de
resumo, noutra coluna. Durante o atendimento o profissional olha para o rosto do
paciente — procurar o botao na lateral custa exatamente o momento que se quis
marcar.

Agora ha um botao redondo de um centimetro sobreposto ao video, embaixo a
esquerda, e o atalho Ctrl + Espaco. Duas entradas para a mesma acao criam um
risco especifico: divergirem. Se o atalho aceitar o que o botao recusa, o piso
de dez segundos deixa de existir na pratica, e dois cortes colados produzem dois
resumos dizendo a mesma coisa.

Por isso este arquivo guarda menos a aparencia e mais a equivalencia.
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
BOTAO = (PAINEL / "components" / "indicators" / "BotaoDeCorte.tsx").read_text(
    encoding="utf-8"
)


class OBotaoEstaOndeFoiPedido(unittest.TestCase):
    def test_e_redondo_e_de_um_centimetro(self):
        """`1cm` literal, e nao pixel: um centimetro e medida de dedo, e o alvo
        precisa do mesmo tamanho fisico em telas de densidade diferente."""
        self.assertIn("rounded-full", BOTAO)
        self.assertIn("h-[1cm] w-[1cm]", BOTAO)

    def test_e_ambar(self):
        self.assertIn("bg-amber-500", BOTAO)

    def test_se_sobrepoe_ao_video_embaixo_a_esquerda(self):
        self.assertIn("absolute bottom-3 left-3", BOTAO)

    def test_aparece_nos_TRES_layouts(self):
        """O corte nao pode depender de qual layout o profissional escolheu."""
        self.assertEqual(SESSAO.count("<BotaoDeCorte"), 3)

    def test_nao_fica_escondido_atras_do_aviso_de_audio(self):
        """O aviso de permissao de audio ocupava exatamente este canto, de ponta
        a ponta. Dois elementos no mesmo z-index: o ultimo desenhado ganha, e o
        botao era o primeiro."""
        self.assertNotIn("absolute bottom-3 left-3 right-3", SESSAO)
        self.assertIn("absolute bottom-3 left-[1.6cm] right-3", SESSAO)
        self.assertIn("left-3 z-30", BOTAO)


class OAtalhoFazEXATAMENTEoQueOBotaoFaz(unittest.TestCase):
    """A parte que importa. Aparencia se conserta olhando; divergencia de regra
    entre duas entradas so aparece num relatorio estranho, semanas depois."""

    def test_o_piso_de_dez_segundos_e_uma_constante_unica(self):
        """Era literal repetido em tres lugares. Constante nao impede a
        divergencia — mas faz a mudanca acontecer num lugar so."""
        self.assertIn("const SEGUNDOS_MINIMOS_DE_CORTE = 10;", SESSAO)
        self.assertNotIn("semanticCutElapsed < 10", SESSAO)

    def test_botao_e_atalho_usam_o_MESMO_piso(self):
        self.assertEqual(
            SESSAO.count(
                "semanticCutElapsed < SEGUNDOS_MINIMOS_DE_CORTE || semanticCutClosingRef.current"
            ),
            6,  # tres botoes de corte + tres paineis de resumo
        )
        self.assertIn("decorrido < SEGUNDOS_MINIMOS_DE_CORTE", SESSAO)

    def test_os_dois_recusam_enquanto_um_corte_esta_fechando(self):
        self.assertIn("semanticCutClosingRef.current", SESSAO)
        self.assertRegex(
            SESSAO,
            r"decorrido < SEGUNDOS_MINIMOS_DE_CORTE \|\|\s*semanticCutClosingRef\.current",
        )

    def test_os_dois_chamam_o_mesmo_caminho(self):
        """Nada de um segundo fluxo de fechamento para o teclado."""
        self.assertEqual(SESSAO.count('closeSemanticCut("manual")'), 7)


class OAtalhoNaoAtrapalhaQuemDigita(unittest.TestCase):
    def test_e_ctrl_mais_espaco_pela_TECLA_fisica(self):
        """`code` e a tecla; `key` para espaco e " ", que muda com o layout do
        teclado."""
        self.assertIn('evento.code !== "Space"', SESSAO)
        self.assertIn("evento.ctrlKey", SESSAO)

    def test_espaco_continua_sendo_espaco_dentro_de_campo_de_texto(self):
        self.assertIn("isContentEditable", SESSAO)
        self.assertRegex(SESSAO, r'"INPUT",\s*"TEXTAREA",\s*"SELECT"')

    def test_tecla_segurada_nao_enfileira_cortes(self):
        self.assertIn("evento.repeat", SESSAO)

    def test_o_atalho_esta_escrito_na_dica(self):
        """Atalho que ninguem descobre nao existe."""
        self.assertIn("Ctrl + Espaço", BOTAO)
        self.assertIn('aria-keyshortcuts="Control+Space"', BOTAO)

    def test_o_ouvinte_e_removido_ao_sair(self):
        """Sem isso, cada remontagem da tela deixa um ouvinte vivo e um
        Ctrl+Espaco fecharia varios cortes de uma vez."""
        self.assertIn('removeEventListener("keydown", aoTeclar)', SESSAO)


class NenhumaLinhaCorrompida(unittest.TestCase):
    """A mesma guarda do outro arquivo, aplicada ao componente novo: edicao
    mecanica ja deixou digito colado em JSX, e o typecheck aceitou."""

    def test_o_componente_esta_bem_formado(self):
        self.assertIsNone(re.search(r"^\d+[{<]", BOTAO, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
