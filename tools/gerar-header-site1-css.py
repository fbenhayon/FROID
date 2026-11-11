# -*- coding: utf-8 -*-
"""Gera froid-site-dev/site-assets/header-site1.css: o visual do header do
Site 1 (site publico) aplicado as paginas do Psique do Site II.

Pedido do dono, 11/11/2026: "adotar o header links do Site 1" - visual e
seletor de idiomas; os links continuam levando as paginas do Site II.

    python tools/gerar-header-site1-css.py            # gera
    python tools/gerar-header-site1-css.py --conferir # so acusa divergencia

Por que um gerador: o visual do header do Site 1 vive em style.css e
refinement.css, misturado ao estilo do resto do site. Copiar a mao seria uma
copia que diverge em silencio (skill-froid-master, 2.7). Este script le os
dois arquivos e extrai so as regras de header (site-header, nav-*, brand,
lang-*, site-menu-toggle, e os .btn usados nas acoes), cada seletor restrito
a `body > header.site-header`, para nao alcancar nada fora do header. As
variaveis do :root do Site 1 que essas regras usam entram no proprio header.
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES = [os.path.join(REPO, "froid-site", "site-assets", n) for n in ("style.css", "refinement.css")]
DESTINO = os.path.join(REPO, "froid-site-dev", "site-assets", "header-site1.css")
ESCOPO = "body > header.site-header"
DO_HEADER = re.compile(r"site-header|\.nav-|\.brand|\.lang-|site-menu-toggle|menu-open|^\.btn|\s\.btn")


def blocos(css):
    """Devolve (prefixo_at_rule ou None, seletor, corpo) para cada regra,
    descendo um nivel em @media/@supports."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        cabeca = css[i:j].strip()
        prof, k = 1, j + 1
        while k < n and prof:
            if css[k] == "{":
                prof += 1
            elif css[k] == "}":
                prof -= 1
            k += 1
        corpo = css[j + 1:k - 1]
        if cabeca.startswith("@media") or cabeca.startswith("@supports"):
            for _p, sel, c in blocos(corpo):
                yield cabeca, sel, c
        elif not cabeca.startswith("@"):
            yield None, cabeca, corpo.strip()
        i = k


def escopar(seletor):
    s = seletor.strip()
    if not s or s.startswith((":root", "html", "body", "*")):
        return None
    if not DO_HEADER.search(" " + s):
        return None
    for prefixo in ("header.site-header", ".site-header"):
        if s.startswith(prefixo):
            return ESCOPO + s[len(prefixo):]
    return ESCOPO + " " + s


def gerar():
    saida = [
        "/* GERADO por tools/gerar-header-site1-css.py - nao editar a mao.",
        "   O visual do header do Site 1 (froid-site: style.css, refinement.css),",
        "   restrito ao header, para as paginas do Psique do Site II.",
        "   Pedido do dono, 11/11/2026. */",
    ]
    variaveis = []
    for fonte in FONTES:
        css = io.open(fonte, encoding="utf-8").read()
        saida.append("")
        saida.append("/* --- de froid-site/site-assets/%s --- */" % os.path.basename(fonte))
        for media, sel, corpo in blocos(css):
            if sel == ":root" and media is None:
                variaveis.append(corpo)
                continue
            escopados = [e for e in (escopar(s) for s in sel.split(",")) if e]
            if not escopados or not corpo:
                continue
            # rem -> px: no Site 1 a raiz tem 16px; no Site II, ~10% mais, e
            # todo rem do header crescia junto. Em px o header fica do tamanho
            # do Site 1 nas duas.
            corpo = re.sub(r"(?<![\w.-])(\d*\.?\d+)rem\b",
                           lambda m: "%gpx" % round(float(m.group(1)) * 16, 2), corpo)
            regra = "%s { %s }" % (", ".join(escopados), " ".join(corpo.split()))
            saida.append("%s { %s }" % (media, regra) if media else regra)
    # Base do Site 1 que o header herdava do body de la (style.css: corpo em
    # 16px, Inter, altura de linha 1,65). No Site II o body e ~10% maior e o
    # header saia maior; e os links tinham um fundo que o Site 1 nao tem.
    # Entra ANTES das regras extraidas, que a sobrescrevem onde definem algo.
    base = [
        "%s { font-size: 16px; font-family: var(--font); line-height: 1.65; }" % ESCOPO,
        "%s .nav-links a { background: transparent; }" % ESCOPO,
    ]
    if variaveis:
        base.insert(0, "%s { %s }" % (ESCOPO, " ".join(" ".join(variaveis).split())))
    saida[4:4] = base
    return "\n".join(saida) + "\n"


def main():
    novo = gerar()
    atual = io.open(DESTINO, encoding="utf-8").read() if os.path.exists(DESTINO) else ""
    if "--conferir" in sys.argv:
        print("em dia" if novo == atual else "DIVERGE")
        return 0 if novo == atual else 1
    io.open(DESTINO, "w", encoding="utf-8", newline="\n").write(novo)
    print("gerado: %s (%d regras)" % (DESTINO, novo.count("{") - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
