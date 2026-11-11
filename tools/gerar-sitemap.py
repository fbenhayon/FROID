# -*- coding: utf-8 -*-
"""Gera froid-site/sitemap.xml e froid-site/robots.txt.

Pedido do dono, 11/11/2026: "fazer o Google indexar as paginas". O site nao
tinha mapa nem robots.txt. O mapa lista so o que o servidor entrega como
pagina propria e indexavel:

- do site publico (froid-site): toda pagina, MENOS o Psique 1
  ([lang/]psique/, que o Caddy redireciona para /dev/);
- do Site II (froid-site-dev): so as paginas do Psique ([lang/]psique/),
  servidas em /dev/. As demais paginas do Site II repetem as do publico e
  declaram como canonica a URL publica: nao entram, para nao listar copia.

Fica de fora toda pagina com <meta name="robots" content="noindex"> (os
redirecionamentos e as paginas que o dono decidiu nao indexar, como etica,
termos e seguranca). A URL de cada pagina e a CANONICA que ela mesma declara;
sem canonica, a URL do servidor.

    python tools/gerar-sitemap.py            # gera
    python tools/gerar-sitemap.py --conferir # so acusa divergencia
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLICO = os.path.join(REPO, "froid-site")
DEV = os.path.join(REPO, "froid-site-dev")
BASE = "https://www.froid.com.br/"
PSIQUE = re.compile(r"^((en|fr|es)/)?psique/")
NOINDEX = re.compile(r'<meta\s+name="robots"\s+content="[^"]*noindex', re.I)
CANONICA = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"', re.I)


def paginas(raiz, prefixo, quer):
    for pasta, _d, arquivos in os.walk(raiz):
        for nome in sorted(arquivos):
            if not nome.endswith(".html"):
                continue
            caminho = os.path.join(pasta, nome)
            rel = os.path.relpath(caminho, raiz).replace(os.sep, "/")
            if not quer(rel):
                continue
            texto = io.open(caminho, encoding="utf-8").read()
            if NOINDEX.search(texto):
                continue
            m = CANONICA.search(texto)
            if m:
                yield m.group(1)
            else:
                url = BASE + prefixo + rel
                yield url[: -len("index.html")] if url.endswith("/index.html") else url


def gerar():
    urls = set(paginas(PUBLICO, "", lambda rel: not PSIQUE.match(rel)))
    urls |= set(paginas(DEV, "dev/", lambda rel: bool(PSIQUE.match(rel))))
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    linhas += ["  <url><loc>%s</loc></url>" % u for u in sorted(urls)]
    linhas.append("</urlset>")
    sitemap = "\n".join(linhas) + "\n"
    robots = "User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % BASE
    return sitemap, robots, len(urls)


def main():
    sitemap, robots, n = gerar()
    destinos = {os.path.join(PUBLICO, "sitemap.xml"): sitemap, os.path.join(PUBLICO, "robots.txt"): robots}
    if "--conferir" in sys.argv:
        diverge = [p for p, c in destinos.items()
                   if not os.path.exists(p) or io.open(p, encoding="utf-8").read() != c]
        print("divergem: " + (", ".join(os.path.basename(p) for p in diverge) or "nenhum"))
        return 1 if diverge else 0
    for p, c in destinos.items():
        io.open(p, "w", encoding="utf-8", newline="\n").write(c)
    print("sitemap.xml: %d paginas; robots.txt gravado" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
