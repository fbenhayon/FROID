# -*- coding: utf-8 -*-
"""As boas praticas da sessao, nos dois lados, e os 60 segundos que elas citam.

Determinacao do dono, 06/10/2026: o convite ao paciente passa a trazer as boas
praticas da sessao, e a tela de envio do convite traz as do profissional. As
duas listas sao curtas e falam de coisas diferentes, porque as audiencias sao
duas:

  - o paciente recebe o que depende dele (comecar falando; nao falar em cima);
  - o profissional recebe o que depende de quem conduz (a janela de calibracao
    e o corte a cada troca de tema).

O QUE ESTE ARQUIVO GUARDA, E POR QUE

Nao e a redacao. E o numero: "60 segundos" aparece agora em TRES lugares
escritos em duas linguagens -- a mensagem do convite (Python), o bloco da tela
de envio (TSX) e a janela que o painel da sessao realmente trava
(`baselineStart + 60`, tambem TSX). Numero copiado diverge em silencio (secao
2.7): alguem muda a janela no painel, e o convite segue prometendo ao paciente
uma coisa que o sistema nao faz mais. Nao ha como importar a constante de uma
linguagem na outra, entao a saida e esta: um teste que confronta todas as copias
contra a fonte -- o painel, que e quem decide.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import main  # noqa: E402

PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"
SESSAO_AO_VIVO = (PAINEL / "pages" / "LiveSession.tsx").read_text(encoding="utf-8")
ENVIO_DO_CONVITE = (PAINEL / "pages" / "NewPatient.tsx").read_text(encoding="utf-8")

TITULO = "Boas Pr"  # prefixo comum: a mensagem vai sem acento, a tela com
TITULO_DA_MENSAGEM = "Boas Praticas para uma Sessao FROID:"
TITULO_DA_TELA = "Boas Práticas para uma Sessão FROID:"


def _mensagem_do_convite(**extra):
    convite = {
        "patient_name": "Paciente de Teste",
        "session_id": "froid-teste",
        "patient_known": False,
        "invite_url": "https://froid.com.br/app/#/convite/xyz",
        "payment": {"mode": "single", "session_value_brl": "R$ 300,00", "pix_code": ""},
    }
    convite.update(extra)
    return main._build_whatsapp_message(convite)


class JanelaDeCalibracao(unittest.TestCase):
    """A fonte do numero e o painel da sessao."""

    def setUp(self):
        casado = re.search(r"baselineStart\s*\+\s*(\d+)", SESSAO_AO_VIVO)
        self.assertIsNotNone(
            casado,
            "o painel da sessao nao declara mais a janela da baseline do PC; "
            "esta e a FONTE do numero citado no convite e na tela de envio.",
        )
        self.segundos = int(casado.group(1))

    def test_o_convite_ao_paciente_cita_a_janela_do_painel(self):
        mensagem = _mensagem_do_convite()
        self.assertIn(
            "%d segundos" % self.segundos, mensagem,
            "o convite ao paciente promete uma janela diferente da que o painel "
            "trava (%d s)." % self.segundos,
        )

    def test_a_tela_de_envio_cita_a_janela_do_painel(self):
        self.assertIn(
            "%d segundos" % self.segundos, ENVIO_DO_CONVITE,
            "a tela de envio do convite promete ao profissional uma janela "
            "diferente da que o painel trava (%d s)." % self.segundos,
        )


class BoasPraticasDoPaciente(unittest.TestCase):
    """Elas viajam no texto que o paciente recebe, nao numa tela que ele nunca abre."""

    def test_a_mensagem_traz_a_lista_com_titulo(self):
        mensagem = _mensagem_do_convite()
        self.assertIn(TITULO_DA_MENSAGEM, mensagem)

    def test_a_primeira_pratica_e_comecar_falando(self):
        mensagem = _mensagem_do_convite().lower()
        self.assertIn("inicie sua sessao falando", mensagem)
        self.assertIn("capturando a sua voz", mensagem)

    def test_a_segunda_pratica_e_nao_falar_em_cima(self):
        mensagem = _mensagem_do_convite().lower()
        self.assertIn("sobrepostas", mensagem)

    def test_as_praticas_acompanham_o_convite_de_paciente_ja_cadastrado(self):
        # O convite tem dois textos (cadastro novo e paciente conhecido) e as
        # praticas valem para a sessao, nao para o cadastro. Afirmar em CADA
        # ponto, e nao em algum ponto (secao 3).
        for conhecido in (False, True):
            mensagem = _mensagem_do_convite(patient_known=conhecido)
            self.assertIn(
                TITULO, mensagem,
                "convite de paciente %s saiu sem as boas praticas."
                % ("cadastrado" if conhecido else "novo"),
            )

    def test_as_praticas_ficam_depois_do_link(self):
        # Quem le no celular para no primeiro link acionavel. As praticas vem
        # depois dele de proposito: antes, empurrariam o link para baixo da
        # dobra, e o convite existe para ser aberto.
        mensagem = _mensagem_do_convite()
        self.assertLess(mensagem.index("https://"), mensagem.index(TITULO))


class BoasPraticasDoProfissional(unittest.TestCase):
    """Elas ficam na tela de envio do convite, que e onde ele esta ao enviar."""

    def test_a_tela_de_envio_traz_a_lista(self):
        self.assertIn(TITULO_DA_TELA, ENVIO_DO_CONVITE)

    def test_a_primeira_pratica_e_a_captacao_da_voz_do_paciente(self):
        self.assertIn("captando a voz do paciente", ENVIO_DO_CONVITE)

    def test_a_segunda_pratica_e_o_corte_a_cada_troca_de_tema(self):
        self.assertIn("mudar o tema da conversa", ENVIO_DO_CONVITE)

    def test_as_duas_listas_nao_sao_a_mesma(self):
        # Mandar ao profissional o texto escrito para o paciente foi um defeito
        # real desta casa (padrao 2.11): ler a quem a frase foi escrita.
        self.assertNotIn("Inicie sua sess", ENVIO_DO_CONVITE)


if __name__ == "__main__":
    unittest.main()
