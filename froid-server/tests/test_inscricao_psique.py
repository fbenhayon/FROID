"""A inscricao gratuita esta em toda pagina do Psique, leva ao cadastro real e
anuncia o teste do catalogo.

Pedido do dono, 10/11/2026: a secao "Inscricao Profissional Gratuita" deve
estar na pagina das 10 habilidades, na pagina inicial do Psique e em todas as
outras, para o profissional se cadastrar a qualquer momento.

O que estes testes guardam, e o caso que justifica cada um:

- a secao existe em TODA pagina de froid-site-dev/psique/ que nao e
  redirecionamento, e e a do gerador (tools/gerar-inscricao-psique.py). Uma
  pagina nova entra na varredura sozinha;
- o numero escrito no HTML (o que aparece se a consulta ao servidor falhar)
  e o do catalogo, psique_pricing.TRIAL_CREDITS / TRIAL_DAYS;
- nenhuma pagina volta a ter o formulario que descartava os dados digitados,
  nem o "voucher" simulado que dizia ter enviado e-mail e WhatsApp.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
# A inscricao existe no site em desenvolvimento (froid-site-dev, em /dev/,
# com senha). O publico, froid-site/, voltou a versao anterior em 11/11/2026.
SITE = REPO / "froid-site-dev"
PSIQUE = SITE / "psique"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import psique_pricing  # noqa: E402

STUB = "<!-- redirecionamento: pagina movida em 09/11/2026 -->"
INICIO = "<!-- inscricao gratuita: gerado por tools/gerar-inscricao-psique.py -->"
CADASTRO = 'href="https://www.froid.com.br/cadastro"'


def _paginas_do_psique():
    for caminho in sorted(PSIQUE.glob("*.html")):
        texto = caminho.read_text(encoding="utf-8")
        if STUB not in texto:
            yield caminho, texto


class AInscricaoEstaEmTodaPaginaDoPsique(unittest.TestCase):
    def test_a_varredura_encontra_as_paginas(self):
        nomes = [c.name for c, _ in _paginas_do_psique()]
        self.assertIn("index.html", nomes)
        # percepcao-clinica.html (as 10 habilidades) foi desativada em
        # 11/11/2026 e fundida em index.html#habilidades: e redirecionamento.
        self.assertNotIn("percepcao-clinica.html", nomes)
        self.assertGreaterEqual(len(nomes), 10)

    def test_toda_pagina_tem_a_secao_uma_vez_dentro_do_main(self):
        for caminho, texto in _paginas_do_psique():
            with self.subTest(pagina=caminho.name):
                self.assertEqual(texto.count(INICIO), 1)
                self.assertEqual(texto.count('id="resgate-bonificacao"'), 1)
                self.assertLess(texto.index(INICIO), texto.index("</main>"))
                bloco = texto[texto.index(INICIO):texto.index("<!-- /inscricao gratuita -->")]
                self.assertIn(CADASTRO, bloco)
                self.assertIn("inscricao-psique.js", bloco)

    def test_o_html_e_o_que_o_gerador_produz(self):
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "gerar-inscricao-psique.py"), "--conferir"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ONumeroEscritoEODoCatalogo(unittest.TestCase):
    CONDICOES = re.compile(
        r'class="teste-condicoes">(\d+) sessões gratuitas, válidas por (\d+) dias<')
    QTD = re.compile(r'class="teste-qtd">(\d+)<')

    def test_toda_copia_escrita_confere(self):
        achados = 0
        for caminho in sorted(SITE.rglob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            for creditos, dias in self.CONDICOES.findall(texto):
                achados += 1
                self.assertEqual(
                    (int(creditos), int(dias)),
                    (psique_pricing.TRIAL_CREDITS, psique_pricing.TRIAL_DAYS),
                    caminho,
                )
            for creditos in self.QTD.findall(texto):
                achados += 1
                self.assertEqual(int(creditos), psique_pricing.TRIAL_CREDITS, caminho)
        # Varredura que nao acha nada e indistinguivel de varredura limpa.
        self.assertGreaterEqual(achados, 20)

    def test_toda_pagina_com_numero_escrito_carrega_a_leitura_ao_vivo(self):
        for caminho in sorted(SITE.rglob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            if "teste-condicoes" in texto or "teste-qtd" in texto:
                self.assertIn("inscricao-psique.js", texto, caminho)


class SoUmaChamadaDeCadastroPorPagina(unittest.TestCase):
    """Determinacao do dono, 10/11/2026: "mantem apenas um formulario, delete
    aquele ineficaz". Cada pagina terminava num bloco `chamada-final` com um
    titulo e um botao de cadastro, as vezes com texto que nao combinava com o
    botao ("Solicite uma apresentacao..." num botao de cadastro). Sairam todos;
    a inscricao gerada e a unica chamada no corpo da pagina. O botao do hero,
    no topo, continua: e um botao, nao um formulario.
    """

    def test_fora_do_hero_so_a_inscricao_leva_ao_cadastro(self):
        for caminho, texto in _paginas_do_psique():
            corpo = texto[texto.index("<main"):texto.index("</main>")]
            corpo = re.sub(
                re.escape(INICIO) + r".*?<!-- /inscricao gratuita -->", "", corpo, flags=re.S)
            for atributos, conteudo in re.findall(r"<section([^>]*)>(.*?)</section>", corpo, re.S):
                if "hero-banner" in atributos:
                    continue
                with self.subTest(pagina=caminho.name, secao=atributos.strip()):
                    self.assertNotIn("froid.com.br/cadastro", conteudo)


class OFormularioQueDescartavaNaoVolta(unittest.TestCase):
    def test_nenhuma_pagina_simula_voucher_nem_coleta_o_que_descarta(self):
        for caminho in sorted(SITE.rglob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            for proibido in ("voucher-form", "handleClaimVoucher", "FROID-PSI-",
                             "Suas 10 Sessões Foram Liberadas"):
                self.assertNotIn(proibido, texto, caminho)


class OFormularioPublicoEntregaOsDados(unittest.TestCase):
    """O site PUBLICO (froid-site, versao anterior) ainda tem o formulario de
    resgate, na landing do Psique. Ate 11/11/2026 ele lia os dados e os
    descartava (so redirecionava ao /cadastro) e guardava um painel de
    "voucher" que dizia "Parabens! Suas 10 Sessoes Foram Liberadas" e ter
    enviado e-mail e WhatsApp. Determinacao do dono: o formulario nao pode
    descartar dados. Toda pagina, em qualquer dos dois sites, que tenha o
    formulario precisa envia-lo ao /api/contato e nao pode simular nada.
    """

    def test_todo_formulario_de_resgate_envia_ao_contato(self):
        achados = 0
        for site in ("froid-site", "froid-site-dev"):
            for caminho in sorted((REPO / site).rglob("*.html")):
                texto = caminho.read_text(encoding="utf-8")
                if 'id="voucher-form"' not in texto:
                    continue
                achados += 1
                with self.subTest(pagina=str(caminho.relative_to(REPO))):
                    self.assertIn("fetch('/api/contato'", texto)
                    self.assertNotIn("window.location.href = 'https://www.froid.com.br/cadastro'", texto)
                    for proibido in ("FROID-PSI-", "Foram Liberadas", "claimedVoucher",
                                     "Termo de Consentimento para Demonstração Clínica"):
                        self.assertNotIn(proibido, texto)
        # A landing publica tem o formulario; se ele sumir, o teste avisa.
        self.assertGreaterEqual(achados, 1)


if __name__ == "__main__":
    unittest.main()
