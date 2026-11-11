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
    """Paginas que o servidor entrega: o Site II inteiro e o publico menos o
    Psique 1 (froid-site/[lang/]psique/, so redirecionado desde 11/11/2026)."""
    for caminho in sorted(DEV.rglob("*.html")):
        yield caminho
    for caminho in sorted(PUBLICO.rglob("*.html")):
        rel = caminho.relative_to(PUBLICO).as_posix()
        if not re.match(r"^((en|fr|es)/)?psique/", rel):
            yield caminho


class NenhumLinkAoPsique1(unittest.TestCase):
    """11/11/2026: "nao deve haver nenhum link ao site FROID Psique 1". Nem
    relativo (psique/... a partir do site publico), nem absoluto."""

    ABSOLUTO = re.compile(r"https://www\.froid\.com\.br/((en|fr|es)/)?psique\b")
    ATRIB = re.compile(r'(?:href|src)="([^"#?]*)')

    def test_nenhuma_pagina_servida_aponta_para_o_psique_1(self):
        for caminho in _servidas():
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(pagina=str(caminho.relative_to(REPO))):
                self.assertNotRegex(texto, self.ABSOLUTO)
                if PUBLICO in caminho.parents:
                    base = caminho.parent.relative_to(PUBLICO).as_posix()
                    for url in self.ATRIB.findall(texto):
                        if not url or url.startswith(("http", "/", "mailto:", "data:", "tel:")):
                            continue
                        alvo = (Path(base) / url).as_posix()
                        partes = []
                        for p in alvo.split("/"):
                            if p == "..":
                                partes and partes.pop()
                            elif p not in ("", "."):
                                partes.append(p)
                        self.assertNotRegex("/".join(partes), r"^((en|fr|es)/)?psique(/|$)", url)


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

    def test_o_caddy_serve_dev_sem_senha(self):
        caddy = (REPO / "Caddyfile").read_text(encoding="utf-8")
        ativas = [l for l in caddy.splitlines() if not l.strip().startswith("#")]
        self.assertFalse([l for l in ativas if "basic_auth" in l])
        bloco = caddy.split("handle_path /dev/* {", 1)[1].split("\n    }\n", 1)[0]
        self.assertIn("root * /srv/froid-site-dev", bloco)
        # O bloco de /dev/ vem antes do `handle {` sem matcher, que serve o
        # site publico inteiro e pegaria qualquer caminho que sobrasse.
        self.assertLess(caddy.index("handle_path /dev/*"), caddy.index("\n    handle {\n"))
        self.assertNotIn("FROID_PERCEPCAO_SENHA_HASH", caddy)

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
