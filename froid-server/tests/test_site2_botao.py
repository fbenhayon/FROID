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


def _servidas():
    """Paginas que o servidor entrega. Desde 18/11/2026 o Site II e servido na
    raiz: ele inteiro, e do publico so o que nao existe no Site II."""
    for caminho in sorted(DEV.rglob("*.html")):
        yield caminho
    for caminho in sorted(PUBLICO.rglob("*.html")):
        if not (DEV / caminho.relative_to(PUBLICO)).exists():
            yield caminho


class NenhumLinkAoPsique1(unittest.TestCase):
    """11/11/2026: "nao deve haver nenhum link ao site FROID Psique 1".
    18/11/2026: com o Site II na raiz, /psique/ e o Psique do Site II; a
    garantia passa a ser que NENHUMA pagina de froid-site/[lang/]psique/ e
    servida, porque toda ela tem a mesma pagina no Site II, que o Caddy
    entrega antes do froid-site."""

    def test_todo_caminho_do_psique_1_e_coberto_pelo_site_ii(self):
        psique1 = [c for c in PUBLICO.rglob("*.html")
                   if re.match(r"^((en|fr|es)/)?psique/", c.relative_to(PUBLICO).as_posix())]
        self.assertTrue(psique1)
        for caminho in psique1:
            rel = caminho.relative_to(PUBLICO)
            with self.subTest(pagina=rel.as_posix()):
                self.assertTrue((DEV / rel).exists(), rel)

    def test_nenhum_link_absoluto_leva_ao_antigo_dev(self):
        for caminho in _servidas():
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(pagina=str(caminho.relative_to(REPO))):
                self.assertNotRegex(texto, r"""(froid\.com\.br|["'(=])/dev/""")


class OExplorarSaiuDosDoisSites(unittest.TestCase):
    def test_nenhum_header_tem_explorar(self):
        for caminho in _servidas():
            texto = caminho.read_text(encoding="utf-8")
            nav = re.search(r'<nav class="nav-links">.*?</nav>', texto, re.S)
            if nav:
                with self.subTest(pagina=str(caminho.relative_to(REPO))):
                    self.assertNotRegex(nav.group(0), r'href="[^"]*menu\.html"')


class ACalculadoraDoPsiqueENaoADoNr1(unittest.TestCase):
    """11/11/2026: na pagina inicial do Site II, o calculo do NR-1 da lugar
    ao de profissionais e clinicas (pacotes de creditos e licenca por
    profissional clinico), com os valores do catalogo do servidor."""

    def test_a_pagina_inicial_do_site_ii(self):
        texto = (DEV / "psique" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("froidSimularNr1", texto)
        self.assertNotIn("simulador-nr1.js", texto)
        for exigido in ('id="psique-v2-precos"', 'id="pv2-ofertas"', 'id="pv2-calculadora"',
                        "psique-pricing-v2.js", 'id="calculadora-psique"'):
            self.assertIn(exigido, texto)
        # Nenhum valor escrito: os precos vem do servidor.
        bloco = texto[texto.index('id="calculadora-psique"'):texto.index("</section>", texto.index('id="calculadora-psique"'))]
        self.assertNotRegex(bloco, r"R\$\s*\d")


class OHeaderDoSiteIIEOVisualDoSite1(unittest.TestCase):
    def test_o_css_gerado_esta_em_dia_e_e_carregado(self):
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "gerar-header-site1-css.py"), "--conferir"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for caminho in sorted((DEV / "psique").glob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            if STUB in texto:
                continue
            with self.subTest(pagina=caminho.name):
                self.assertIn("header-site1.css", texto)
                self.assertLess(texto.index("psique-v2-site.css"), texto.index("header-site1.css"))


class OSiteIISemSenha(unittest.TestCase):
    """11/11/2026, a tarde: o dono mandou tirar a senha do Site II ("quando
    voce clica no FROID Psique na primeira pagina ele solicita a senha; tem
    que desabilitar agora essa restricao"). Antes, este teste exigia o
    basic_auth em /dev/; agora exige que nao haja nenhuma linha ATIVA de senha
    no Caddyfile (comentarios contando a historia podem citar a palavra)."""

    def test_o_caddy_serve_o_site_ii_na_raiz_sem_senha(self):
        caddy = (REPO / "Caddyfile").read_text(encoding="utf-8")
        ativas = [l for l in caddy.splitlines() if not l.strip().startswith("#")]
        self.assertFalse([l for l in ativas if "basic_auth" in l])
        bloco = caddy.split("handle @site2 {", 1)[1].split("\n    }\n", 1)[0]
        self.assertIn("root * /srv/froid-site-dev", bloco)
        # O bloco do Site II vem antes do `handle {` sem matcher, que serve o
        # froid-site e pegaria qualquer caminho que sobrasse.
        self.assertLess(caddy.index("handle @site2 {"), caddy.index("\n    handle {\n"))
        self.assertNotIn("FROID_PERCEPCAO_SENHA_HASH", caddy)

    def test_links_antigos_com_dev_viram_301_para_a_raiz(self):
        caddy = (REPO / "Caddyfile").read_text(encoding="utf-8")
        self.assertIn("redir /dev / 301", caddy)
        self.assertIn("redir @dev_antigo {re.dev_antigo.1} 301", caddy)
        self.assertIn("redir @dev_antigo_q {re.dev_antigo_q.1}?{query} 301", caddy)
        self.assertNotIn("handle_path /dev/*", caddy)

    def test_o_compose_monta_a_pasta_e_repassa_a_senha_sem_padrao(self):
        compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("./froid-site-dev:/srv/froid-site-dev:ro", compose)
        # `- VAR` sem valor: ausente, nao chega ao conteiner (falha fechada);
        # `${VAR:-}` a faria chegar vazia, e vazia o Caddy nao sobe.
        self.assertRegex(compose, r"\n\s+- FROID_DEV_SENHA_HASH\s*\n")
        self.assertNotIn("FROID_DEV_SENHA_HASH:-", compose)


class OGoogleIndexaOSiteII(unittest.TestCase):
    """11/11/2026: "fazer o Google indexar as paginas". /dev/ deixa de mandar
    noindex, e o site ganha sitemap.xml e robots.txt gerados."""

    def test_o_caddy_nao_manda_noindex_no_site_ii(self):
        caddy = (REPO / "Caddyfile").read_text(encoding="utf-8")
        ativas = [l for l in caddy.splitlines() if not l.strip().startswith("#")]
        self.assertFalse([l for l in ativas if "X-Robots-Tag" in l])

    def test_o_mapa_e_o_robots_estao_em_dia(self):
        r = subprocess.run([sys.executable, str(REPO / "tools" / "gerar-sitemap.py"), "--conferir"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        mapa = (PUBLICO / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("https://www.froid.com.br/psique/</loc>", mapa)
        self.assertNotIn("/dev/", mapa)
        self.assertIn("Sitemap: https://www.froid.com.br/sitemap.xml", (PUBLICO / "robots.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
