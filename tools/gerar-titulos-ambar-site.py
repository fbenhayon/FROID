# -*- coding: utf-8 -*-
"""Insere o titulo curto da pagina no topo do hero do froid-site.

Uso:
    python tools/gerar-titulos-ambar-site.py
    python tools/gerar-titulos-ambar-site.py --conferir

O rotulo vem do <title>, cortado antes do primeiro "|". A pagina tecnica
nr1/contratacao-nr1.html preserva o nome publico "Cadeia de Comando".
Os redirecionamentos deixados nos enderecos antigos (09/11/2026) nao tem hero
e sao ignorados.
"""
import html as html_lib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.join(REPO, "froid-site")
MARCA_STUB = "<!-- redirecionamento: pagina movida em 09/11/2026 -->"

TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
BADGE = re.compile(r"\n[ \t]*<p class=\"page-title-amber\">.*?</p>\n", re.S)

ROTULOS_ESPECIAIS = {
    "nr1/contratacao-nr1.html": "Cadeia de Comando",
}


def relpath(caminho):
    return os.path.relpath(caminho, RAIZ).replace(os.sep, "/")


def titulo_curto(caminho, html):
    rel = relpath(caminho)
    if rel in ROTULOS_ESPECIAIS:
        return ROTULOS_ESPECIAIS[rel]
    m = TITLE.search(html)
    if not m:
        return None
    titulo = re.sub(r"\s+", " ", m.group(1)).strip()
    titulo = titulo.split("|", 1)[0].strip()
    return titulo or None


def inserir(html, rotulo):
    limpo = BADGE.sub("\n", html)
    rotulo = html_lib.escape(rotulo, quote=False)

    home = re.search(
        r'(<section class="hero-neuro"[^>]*>\s*\n(?P<divindent>[ \t]*)'
        r'<div class="home-intro"[^>]*>\s*\n)',
        limpo,
    )
    if home:
        indent = home.group("divindent") + "  "
        return limpo[:home.end()] + f'{indent}<p class="page-title-amber">{rotulo}</p>\n' + limpo[home.end():]

    hero = re.search(
        r'(<section class="[^"]*\bhero\b[^"]*"[^>]*>\s*\n(?P<divindent>[ \t]*)'
        r'<div class="container[^"]*"[^>]*>\s*\n)',
        limpo,
    )
    if hero:
        indent = hero.group("divindent") + "  "
        return limpo[:hero.end()] + f'{indent}<p class="page-title-amber">{rotulo}</p>\n' + limpo[hero.end():]

    return limpo


def arquivos_html():
    for raiz, _, nomes in os.walk(RAIZ):
        for nome in nomes:
            if nome.endswith(".html"):
                yield os.path.join(raiz, nome)


def main():
    conferir = "--conferir" in sys.argv
    pendentes = []
    sem_hero = []

    for caminho in sorted(arquivos_html()):
        with open(caminho, encoding="utf-8", newline="") as f:
            atual = f.read()
        if MARCA_STUB in atual:
            continue
        rotulo = titulo_curto(caminho, atual)
        if not rotulo:
            sem_hero.append(relpath(caminho))
            continue
        novo = inserir(atual, rotulo)
        if novo == BADGE.sub("\n", atual):
            sem_hero.append(relpath(caminho))
            continue
        if novo != atual:
            pendentes.append(relpath(caminho))
            if not conferir:
                with open(caminho, "w", encoding="utf-8", newline="") as f:
                    f.write(novo)

    if sem_hero:
        print("sem hero reconhecido:")
        for item in sem_hero:
            print("  " + item)
        return 1

    if conferir:
        if pendentes:
            print("titulos ambar fora de sincronia:")
            for item in pendentes:
                print("  " + item)
            return 1
        print("titulos ambar em dia nos arquivos")
        return 0

    print("titulos ambar atualizados em %d arquivo(s)" % len(pendentes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
