"""O site publico leva ao Site II, e o Site II so abre com senha.

Pedido do dono, 11/11/2026: um botao no site publico (froid-site) para o
acesso ao Site II (froid-site-dev, servido em /dev/), protegido pela senha
que ele definiu. A senha e conferida pelo Caddy; a pagina so leva ate la.

O que estes testes guardam:
- toda pagina publica que nao e redirecionamento tem o botao, uma vez, e ele
  e o do gerador (tools/gerar-botao-site2.py);
- todo botao aponta para /dev/ e para uma pagina que existe no Site II;
- o Caddyfile serve /dev/ so atras de basic_auth, com hash padrao (falha
  fechada), e o compose monta a pasta e repassa a variavel da senha.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
PUBLICO = REPO / "froid-site"
DEV = REPO / "froid-site-dev"
STUB = "<!-- redirecionamento: pagina movida em 09/11/2026 -->"
INICIO = "<!-- site II: gerado por tools/gerar-botao-site2.py -->"
BLOCO = re.compile(re.escape(INICIO) + r"(.*?)<!-- /site II -->", re.S)


def _paginas_publicas():
    for caminho in sorted(PUBLICO.rglob("*.html")):
        texto = caminho.read_text(encoding="utf-8")
        if STUB not in texto:
            yield caminho, texto


class OBotaoEstaEmTodaPaginaPublica(unittest.TestCase):
    def test_a_varredura_encontra_as_paginas(self):
        self.assertGreaterEqual(len(list(_paginas_publicas())), 60)

    def test_toda_pagina_tem_um_botao_que_leva_ao_site_ii(self):
        for caminho, texto in _paginas_publicas():
            with self.subTest(pagina=str(caminho.relative_to(PUBLICO))):
                blocos = BLOCO.findall(texto)
                self.assertEqual(len(blocos), 1)
                href = re.search(r'href="([^"]+)"', blocos[0]).group(1)
                self.assertTrue(href.startswith("/dev/"), href)
                alvo = href[len("/dev/"):] or "index.html"
                self.assertTrue((DEV / alvo).exists(), href)

    def test_o_html_e_o_que_o_gerador_produz(self):
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "gerar-botao-site2.py"), "--conferir"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class AEntradaLevaOPsiqueAoSiteII(unittest.TestCase):
    """Pedido do dono, 11/11/2026: na pagina de entrada publica (os dois
    neuronios), clicar no FROID Psique leva ao Site II, que trata so do
    Psique; o NR-1 nao muda."""

    def test_o_psique_vai_ao_site_ii_e_o_nr1_fica(self):
        texto = (PUBLICO / "index.html").read_text(encoding="utf-8")
        psique = re.findall(r'<a class="(?:metade|escolha) psique" href="([^"]+)"', texto)
        nr1 = re.findall(r'<a class="(?:metade|escolha) nr1" href="([^"]+)"', texto)
        self.assertEqual(psique, ["/dev/psique/index.html"] * 2)
        self.assertEqual(len(nr1), 2)
        for href in nr1:
            self.assertFalse(href.startswith("/dev"), href)


class OSiteIISoAbreComSenha(unittest.TestCase):
    def test_o_caddy_serve_dev_atras_de_basic_auth_com_falha_fechada(self):
        caddy = (REPO / "Caddyfile").read_text(encoding="utf-8")
        bloco = caddy.split("handle_path /dev/* {", 1)[1].split("\n    }\n", 1)[0]
        self.assertIn("basic_auth bcrypt", bloco)
        # Sem a variavel, vale um hash padrao (segredo que ninguem guardou).
        self.assertRegex(bloco, r"\{\$FROID_DEV_SENHA_HASH:[A-Za-z0-9+/=]{40,}\}")
        self.assertIn("root * /srv/froid-site-dev", bloco)
        # O bloco de /dev/ vem antes do `handle {` sem matcher, que serve o
        # site publico inteiro e pegaria qualquer caminho que sobrasse.
        self.assertLess(caddy.index("handle_path /dev/*"), caddy.index("\n    handle {\n"))
        # A regra da pagina das 10 habilidades nao alcanca /dev/.
        self.assertIn("not path /dev /dev/*", caddy)

    def test_o_psique_publico_nao_e_mais_servido(self):
        """11/11/2026: "exclua o acesso ao Site 1". Todo caminho do Psique
        publico, em qualquer idioma, vai a mesma pagina no Site II."""
        caddy = (REPO / "Caddyfile").read_text(encoding="utf-8")
        regra = re.search(r"@psique_publico path_regexp psique_publico (\S+)", caddy)
        self.assertIsNotNone(regra)
        padrao = re.compile(regra.group(1).replace("(?i)", ""), re.I)
        for caminho in ("/psique/index.html", "/psique/", "/psique", "/en/psique/faq.html",
                        "/fr/psique/", "/es/psique/index.html"):
            self.assertRegex(caminho, padrao)
        for caminho in ("/nr1/index.html", "/termos.html", "/", "/dev/psique/index.html",
                        "/psiquex.html", "/en/nr1/index.html"):
            self.assertNotRegex(caminho, padrao)
        self.assertIn("redir @psique_publico /dev{uri} 302", caddy)

    def test_o_compose_monta_a_pasta_e_repassa_a_senha_sem_padrao(self):
        compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("./froid-site-dev:/srv/froid-site-dev:ro", compose)
        # `- VAR` sem valor: ausente, nao chega ao conteiner (falha fechada);
        # `${VAR:-}` a faria chegar vazia, e vazia o Caddy nao sobe.
        self.assertRegex(compose, r"\n\s+- FROID_DEV_SENHA_HASH\s*\n")
        self.assertNotIn("FROID_DEV_SENHA_HASH:-", compose)


if __name__ == "__main__":
    unittest.main()
