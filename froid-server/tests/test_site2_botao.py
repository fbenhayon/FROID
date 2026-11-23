"""O Site II (froid-site-dev) e o site servido; o froid-site so guarda o resto.

Historia: em 11/11/2026 o site publico (froid-site) ganhou um botao para o
Site II, entao em /dev/; em 18/11/2026 o Site II passou a ser servido na raiz;
em 23/11/2026, pedido do dono ("eliminar quaisquer dependencias externas e
deixar somente as paginas hoje no ar"), o froid-site perdeu tudo o que o Site
II ja cobre. Sobraram so redirecionamentos de enderecos antigos, robots.txt e
sitemap.xml. O botao e o gerador dele (tools/gerar-botao-site2.py) sairam
junto: nao ha mais pagina publica onde colocar o botao.

O que estes testes guardam:
- o froid-site nao tem nenhum arquivo que o Site II sombreie (seria arquivo
  morto, que nunca chega ao visitante);
- toda pagina que restou no froid-site e redirecionamento, e leva a uma pagina
  que existe no Site II;
- o Caddyfile serve o Site II na raiz, sem senha, e /dev/ antigo vira 301.
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


REFRESH = re.compile(r'<meta http-equiv="refresh" content="0; url=([^"#]+)')


class OPublicoSoGuardaOQueOSiteIINaoTem(unittest.TestCase):
    def test_nenhum_arquivo_do_publico_e_sombreado_pelo_site_ii(self):
        sombreados = [c.relative_to(PUBLICO).as_posix() for c in PUBLICO.rglob("*")
                      if c.is_file() and (DEV / c.relative_to(PUBLICO)).exists()]
        self.assertEqual([], sombreados)

    def test_toda_pagina_publica_e_redirecionamento_para_o_site_ii(self):
        paginas = sorted(PUBLICO.rglob("*.html"))
        self.assertTrue(paginas)
        for caminho in paginas:
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(pagina=caminho.relative_to(PUBLICO).as_posix()):
                m = REFRESH.search(texto)
                self.assertTrue(m, "sem redirecionamento")
                alvo = m.group(1).lstrip("/")
                if not alvo or alvo.endswith("/"):
                    alvo += "index.html"
                self.assertTrue((DEV / alvo).exists(), m.group(1))

    def test_fora_das_paginas_so_robots_e_sitemap(self):
        outros = sorted(c.relative_to(PUBLICO).as_posix() for c in PUBLICO.rglob("*")
                        if c.is_file() and c.suffix != ".html")
        self.assertEqual(["robots.txt", "sitemap.xml"], outros)


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
    entrega antes do froid-site. 23/11/2026: os arquivos do Psique 1 sairam
    do repositorio; a garantia passa a ser que nao exista nenhum."""

    def test_nao_resta_nenhum_arquivo_do_psique_1(self):
        psique1 = [c.relative_to(PUBLICO).as_posix() for c in PUBLICO.rglob("*")
                   if re.match(r"^((en|fr|es)/)?psique(/|$)", c.relative_to(PUBLICO).as_posix())]
        self.assertEqual([], psique1)

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
    # Ate 23/11/2026 header-site1.css era gerado a partir do CSS do froid-site;
    # esse CSS saiu do repositorio e o arquivo passou a ser a fonte.
    def test_o_css_do_header_existe_e_e_carregado(self):
        self.assertTrue((DEV / "site-assets" / "header-site1.css").exists())
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
