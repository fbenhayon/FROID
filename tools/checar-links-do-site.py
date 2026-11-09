# -*- coding: utf-8 -*-
"""Confere todo link interno do froid-site.

Uso:
    python tools/checar-links-do-site.py            # raiz padrao: froid-site/
    python tools/checar-links-do-site.py <pasta>    # outra arvore (ex.: copia antiga)

Para cada froid-site/**/*.html, resolve todo href/src relativo, a url de
<meta http-equiv="refresh"> e os url(...) de CSS embutido, e exige:

- que o arquivo de destino exista (pasta "x/" vale como "x/index.html");
- que a ancora "#id", quando houver, exista como id (ou name) no destino.

URLs absolutas do proprio dominio (https://www.froid.com.br/...) tambem sao
conferidas contra a arvore, exceto as do painel (/app, /cadastro, /api...),
que nao sao arquivos do site. Links externos, mailto:, tel: e javascript: sao
ignorados.

Sai com codigo 1 se houver link quebrado.
"""
import io
import os
import re
import sys
from urllib.parse import unquote, urlsplit

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(REPO, "froid-site")

DOMINIO = re.compile(r"^https?://(www\.)?froid\.com\.br(?P<path>/[^\s]*)?$", re.I)
FORA_DO_SITE = ("/app", "/cadastro", "/api", "/login", "/entrar", "/paciente",
                "/avaliacao", "/access", "/convite", "/assets", "/ws", "/health")
ATRIBUTO = re.compile(r'\s(href|src)\s*=\s*"([^"]*)"', re.I)
REFRESH = re.compile(r'<meta[^>]+http-equiv="refresh"[^>]+content="[^"]*?url=([^"]+)"', re.I)
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
ESTILO = re.compile(r"<style[^>]*>(.*?)</style>|\sstyle=\"([^\"]*)\"", re.S | re.I)
ID = re.compile(r'\s(?:id|name)\s*=\s*"([^"]+)"', re.I)
COMENTARIO = re.compile(r"<!--.*?-->", re.S)

_ids = {}


def ids_de(caminho):
    if caminho not in _ids:
        try:
            texto = io.open(caminho, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            texto = ""
        _ids[caminho] = set(ID.findall(COMENTARIO.sub("", texto)))
    return _ids[caminho]


def destino_do_dominio(path):
    path = unquote(path or "/")
    if any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in FORA_DO_SITE):
        return None
    rel = path.lstrip("/")
    alvo = os.path.join(RAIZ, *rel.split("/")) if rel else RAIZ
    return alvo


def resolver_arquivo(alvo):
    if os.path.isdir(alvo):
        return os.path.join(alvo, "index.html")
    if os.path.exists(alvo):
        return alvo
    if not os.path.splitext(alvo)[1] and os.path.exists(alvo + ".html"):
        return alvo + ".html"
    return alvo


def conferir(origem, url, quebrados):
    url = url.strip().replace("&amp;", "&")
    if not url or url.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return
    m = DOMINIO.match(url)
    if m:
        partes = urlsplit(url)
        alvo = destino_do_dominio(partes.path)
        if alvo is None:
            return
        frag = partes.fragment
    else:
        if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I) or url.startswith("//"):
            return
        if url.startswith("/"):
            # raiz do dominio: so o que e arquivo do site interessa
            partes = urlsplit(url)
            alvo = destino_do_dominio(partes.path)
            if alvo is None:
                return
            frag = partes.fragment
        else:
            partes = urlsplit(url)
            frag = partes.fragment
            if partes.path:
                alvo = os.path.normpath(os.path.join(os.path.dirname(origem), unquote(partes.path)))
            else:
                alvo = origem
    arquivo = resolver_arquivo(alvo)
    if not os.path.isfile(arquivo):
        quebrados.append((origem, url, "arquivo inexistente"))
        return
    if frag and not frag.startswith("/") and arquivo.endswith(".html"):
        if unquote(frag) not in ids_de(arquivo):
            quebrados.append((origem, url, "ancora inexistente"))


def urls_da_pagina(texto):
    texto = COMENTARIO.sub("", texto)
    for _attr, valor in ATRIBUTO.findall(texto):
        yield valor
    for valor in REFRESH.findall(texto):
        yield valor.strip().strip("'")
    for bloco, inline in ESTILO.findall(texto):
        for valor in CSS_URL.findall(bloco or inline):
            yield valor


def main():
    quebrados = []
    paginas = 0
    links = 0
    for pasta, _dirs, arquivos in os.walk(RAIZ):
        for nome in sorted(arquivos):
            if not nome.endswith(".html"):
                continue
            origem = os.path.join(pasta, nome)
            paginas += 1
            texto = io.open(origem, encoding="utf-8").read()
            for url in urls_da_pagina(texto):
                links += 1
                conferir(origem, url, quebrados)
    print("paginas: %d   links conferidos: %d   quebrados: %d" % (paginas, links, len(quebrados)))
    for origem, url, motivo in sorted(set(quebrados)):
        print("  %-45s %-60s %s" % (os.path.relpath(origem, RAIZ).replace(os.sep, "/"), url, motivo))
    sys.exit(1 if quebrados else 0)


if __name__ == "__main__":
    main()
