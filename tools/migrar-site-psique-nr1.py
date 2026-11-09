# -*- coding: utf-8 -*-
"""Separa o froid-site em duas pastas de produto: psique/ e nr1/.

Migracao de UMA vez, aprovada pelo dono em 09/11/2026 ("opcao b, com uma
pagina de entrada unica"). Rode da raiz do repositorio, com a arvore limpa:

    python tools/migrar-site-psique-nr1.py

O que faz, nos quatro idiomas (pt na raiz de froid-site/, en/, fr/ e es/), so
com as paginas que existem em cada um:

1. `git mv` de cada pagina para a pasta do produto (o historico acompanha).
   profissionais.html vira psique/index.html e empresas.html vira
   nr1/index.html. A pagina de entrada (entrada.html) vira a index.html da raiz
   em pt-BR; em en/fr/es a index.html vira a traducao dela.
2. Reescreve TODA referencia relativa (href, src, url() de CSS embutido, url do
   meta refresh) e toda URL absoluta do dominio (canonical, og:url, hreflang,
   JSON-LD), de modo que cada uma resolva a partir da pasta nova do arquivo.
   O caminho e calculado, nunca trocado por texto: resolve-se o destino a partir
   do lugar ANTIGO do arquivo, aplica-se o mapa, e recalcula-se o relativo a
   partir do lugar NOVO.
3. Deixa no caminho antigo um redirecionamento minimo (noindex, canonical,
   meta refresh e location.replace que preserva a ancora), para que link
   antigo, favorito e resultado de busca continuem chegando.

Depois dele, rode `python tools/gerar-header-do-site.py`, que monta o menu de
cada produto a partir da profundidade de cada pagina.
"""
import io
import os
import posixpath
import re
import subprocess
import sys
from urllib.parse import urlsplit

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.join(REPO, "froid-site")
SITE = "https://www.froid.com.br/"
IDIOMAS = ["", "en", "fr", "es"]

PSIQUE = [
    ("profissionais.html", "index.html"),
    "como-funciona-clinico.html", "froid-explica.html", "data-froid.html",
    "precos-psique.html", "percepcao-clinica.html", "landing-psique.html",
    "tecnologia.html", "mapas-faciais.html", "ciencia.html", "glossario.html",
    "faq.html", "seguranca.html",
]
NR1 = [
    ("empresas.html", "index.html"),
    "contratacao-nr1.html", "iso-45001.html", "apresentacao-nr1.html",
    "precos-nr1.html", "proposta-nr1.html",
]

MARCA_STUB = "<!-- redirecionamento: pagina movida em 09/11/2026 -->"


def git(*args):
    subprocess.check_call(["git"] + list(args), cwd=REPO)


def junta(idioma, rel):
    return posixpath.join(idioma, rel) if idioma else rel


def montar_mapa():
    """{caminho antigo: caminho novo}, relativos a froid-site/, com '/'."""
    mapa = {}
    for idioma in IDIOMAS:
        for pasta, lista in (("psique", PSIQUE), ("nr1", NR1)):
            for item in lista:
                antigo, novo = item if isinstance(item, tuple) else (item, item)
                origem = junta(idioma, antigo)
                if os.path.isfile(os.path.join(RAIZ, *origem.split("/"))):
                    mapa[origem] = junta(idioma, pasta + "/" + novo)
    return mapa


def url_publica(rel):
    """Caminho do site -> URL publica; index.html vira a forma de pasta."""
    if rel == "index.html":
        return SITE
    if rel.endswith("/index.html"):
        return SITE + rel[: -len("index.html")]
    return SITE + rel


def caminho_de_url_publica(path):
    rel = path.lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return rel


# ---------------------------------------------------------------------------
# Reescrita de referencias
# ---------------------------------------------------------------------------

EXTERNO = re.compile(r"^([a-z][a-z0-9+.-]*:|//|/|#|$)", re.I)
ATRIBUTO = re.compile(r'(\s(?:href|src)\s*=\s*")([^"]*)(")', re.I)
REFRESH = re.compile(r'(<meta[^>]+http-equiv="refresh"[^>]+content="[^"]*?url=)([^"]+)(")', re.I)
ESTILO = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S | re.I)
CSS_URL = re.compile(r"(url\(\s*['\"]?)([^'\")]+)(['\"]?\s*\))")
DOMINIO = re.compile(r"https://www\.froid\.com\.br(/[A-Za-z0-9/._-]*)?(#[A-Za-z0-9_-]*)?")


def reescrever_relativo(url, antigo, novo, mapa):
    if EXTERNO.match(url):
        return url
    partes = urlsplit(url)
    if not partes.path:
        return url
    dir_antigo = posixpath.dirname(antigo)
    alvo = posixpath.normpath(posixpath.join(dir_antigo, partes.path))
    if partes.path.endswith("/"):
        alvo = posixpath.join(alvo, "index.html")
    alvo_novo = mapa.get(alvo, alvo)
    if alvo_novo == alvo and antigo == novo:
        return url                       # nada se moveu: preserva o texto original
    rel = posixpath.relpath(alvo_novo, posixpath.dirname(novo) or ".")
    if partes.query:
        rel += "?" + partes.query
    if partes.fragment:
        rel += "#" + partes.fragment
    return rel


def reescrever_dominio(m, mapa):
    path, frag = m.group(1), m.group(2) or ""
    if path is None:
        return m.group(0)
    rel = caminho_de_url_publica(path)
    if rel not in mapa:
        return m.group(0)
    return url_publica(mapa[rel]) + frag


def reescrever_texto(texto, antigo, novo, mapa):
    f = lambda u: reescrever_relativo(u, antigo, novo, mapa)
    texto = ATRIBUTO.sub(lambda m: m.group(1) + f(m.group(2)) + m.group(3), texto)
    texto = REFRESH.sub(lambda m: m.group(1) + f(m.group(2)) + m.group(3), texto)
    texto = ESTILO.sub(
        lambda m: m.group(1)
        + CSS_URL.sub(lambda c: c.group(1) + f(c.group(2)) + c.group(3), m.group(2))
        + m.group(3),
        texto,
    )
    texto = DOMINIO.sub(lambda m: reescrever_dominio(m, mapa), texto)
    return texto


# ---------------------------------------------------------------------------
# Redirecionamento no caminho antigo
# ---------------------------------------------------------------------------

LANG = {"": "pt-BR", "en": "en", "fr": "fr", "es": "es"}
AVISO = {
    "": "Esta página mudou de endereço:",
    "en": "This page has moved:",
    "fr": "Cette page a changé d'adresse :",
    "es": "Esta página cambió de dirección:",
}


def stub(idioma, antigo, novo):
    rel = posixpath.relpath(novo, posixpath.dirname(antigo) or ".")
    publica = url_publica(novo)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="%(lang)s">\n'
        "<head>\n"
        "%(marca)s\n"
        '<meta charset="UTF-8" />\n'
        '<meta name="robots" content="noindex" />\n'
        '<link rel="canonical" href="%(publica)s" />\n'
        '<meta http-equiv="refresh" content="0; url=%(rel)s" />\n'
        "<title>FROID</title>\n"
        '<script>location.replace("%(rel)s" + location.hash);</script>\n'
        "</head>\n"
        "<body>\n"
        '<p>%(aviso)s <a href="%(rel)s">%(publica)s</a></p>\n'
        "</body>\n"
        "</html>\n"
    ) % {"lang": LANG[idioma], "marca": MARCA_STUB, "publica": publica,
         "rel": rel, "aviso": AVISO[idioma]}


# ---------------------------------------------------------------------------
# Pagina de entrada traduzida (en/fr/es)
# ---------------------------------------------------------------------------

TRADUCOES = {
    "en": [
        ('<html lang="pt-BR">', '<html lang="en">'),
        ("<title>FROID | Escolha: FROID Psique ou FROID NR-1</title>",
         "<title>FROID | Choose: FROID Psique or FROID NR-1</title>"),
        ("FROID Psique, apoio à observação clínica em saúde mental. FROID NR-1, gestão de riscos psicossociais.",
         "FROID Psique, support for clinical observation in mental health. FROID NR-1, psychosocial risk management."),
        ('aria-label="Escolha o produto"', 'aria-label="Choose a product"'),
        ("Entrar no FROID Psique", "Enter FROID Psique"),
        ("Entrar no FROID NR-1", "Enter FROID NR-1"),
        ("Apoio à observação clínica em saúde mental, para profissionais e clínicas.",
         "Support for clinical observation in mental health, for professionals and clinics."),
        ("Gestão de riscos psicossociais, para empresas, RH, SST e jurídico.",
         "Psychosocial risk management, for companies, HR, OSH and legal teams."),
        (">Sobre e contato<", ">About and contact<"),
        (">Privacidade<", ">Privacy<"),
        (">Termos<", ">Contractual documents<"),
        ("Todos os direitos reservados.", "All rights reserved."),
    ],
    "fr": [
        ('<html lang="pt-BR">', '<html lang="fr">'),
        ("<title>FROID | Escolha: FROID Psique ou FROID NR-1</title>",
         "<title>FROID | Choisissez : FROID Psique ou FROID NR-1</title>"),
        ("FROID Psique, apoio à observação clínica em saúde mental. FROID NR-1, gestão de riscos psicossociais.",
         "FROID Psique, soutien à l'observation clinique en santé mentale. FROID NR-1, gestion des risques psychosociaux."),
        ('aria-label="Escolha o produto"', 'aria-label="Choisissez le produit"'),
        ("Entrar no FROID Psique", "Entrer dans FROID Psique"),
        ("Entrar no FROID NR-1", "Entrer dans FROID NR-1"),
        ("Apoio à observação clínica em saúde mental, para profissionais e clínicas.",
         "Soutien à l'observation clinique en santé mentale, pour les professionnels et les cliniques."),
        ("Gestão de riscos psicossociais, para empresas, RH, SST e jurídico.",
         "Gestion des risques psychosociaux, pour les entreprises, les RH, la SST et le juridique."),
        (">Sobre e contato<", ">À propos et contact<"),
        (">Privacidade<", ">Confidentialité<"),
        (">Termos<", ">Documents contractuels<"),
        ("Todos os direitos reservados.", "Tous droits réservés."),
    ],
    "es": [
        ('<html lang="pt-BR">', '<html lang="es">'),
        ("<title>FROID | Escolha: FROID Psique ou FROID NR-1</title>",
         "<title>FROID | Elija: FROID Psique o FROID NR-1</title>"),
        ("FROID Psique, apoio à observação clínica em saúde mental. FROID NR-1, gestão de riscos psicossociais.",
         "FROID Psique, apoyo a la observación clínica en salud mental. FROID NR-1, gestión de riesgos psicosociales."),
        ('aria-label="Escolha o produto"', 'aria-label="Elija el producto"'),
        ("Entrar no FROID Psique", "Entrar en FROID Psique"),
        ("Entrar no FROID NR-1", "Entrar en FROID NR-1"),
        ("Apoio à observação clínica em saúde mental, para profissionais e clínicas.",
         "Apoyo a la observación clínica en salud mental, para profesionales y clínicas."),
        ("Gestão de riscos psicossociais, para empresas, RH, SST e jurídico.",
         "Gestión de riesgos psicosociales, para empresas, RR. HH., SST y área jurídica."),
        (">Sobre e contato<", ">Acerca de y contacto<"),
        (">Privacidade<", ">Privacidad<"),
        (">Termos<", ">Documentos contractuales<"),
        ("Todos os direitos reservados.", "Todos los derechos reservados."),
    ],
}

# O redirect do painel que vivia na index antiga. O painel usa HashRouter
# (/#/dashboard): num refresh o servidor recebe "/" e serve o site. Sem isto,
# quem atualiza a pagina do painel cai na entrada e perde a tela.
HASH_REDIRECT = {
    "": ("  // O painel FROID usa HashRouter (/#/dashboard). Num refresh, o servidor recebe \"/\"\n"
         "  // e serve este site — este redirect devolve o utilizador ao painel em /app/.\n"),
    "en": ("  // The FROID panel uses a HashRouter (/#/dashboard). On a refresh the server receives \"/\"\n"
           "  // and serves this site — this redirect sends the user back to the panel at /app/.\n"),
}


def ajustar_entrada(texto, idioma):
    """Tira o noindex, aponta os dois links para as pastas e devolve canonical
    e o redirect do painel, que a index antiga tinha."""
    texto = texto.replace('<meta name="robots" content="noindex" />\n', "")
    texto = texto.replace('href="profissionais.html"', 'href="psique/index.html"')
    texto = texto.replace('href="empresas.html"', 'href="nr1/index.html"')
    canonical = '<link rel="canonical" href="%s" />\n' % (SITE + (idioma + "/" if idioma else ""))
    comentario = HASH_REDIRECT.get(idioma, HASH_REDIRECT["en"])
    script = ("<script>\n" + comentario +
              '  if (location.hash.indexOf("#/") === 0) { location.replace("/app/" + location.hash); }\n'
              "</script>\n")
    m = re.search(r'<link rel="stylesheet"', texto)
    texto = texto[:m.start()] + canonical + texto[m.start():]
    texto = texto.replace("</style>\n</head>", "</style>\n" + script + "</head>", 1)
    return texto


def traduzir_entrada(texto_pt, idioma):
    texto = texto_pt
    for de, para in TRADUCOES[idioma]:
        if de not in texto:
            raise SystemExit("traducao da entrada: trecho nao encontrado: %r" % de)
        texto = texto.replace(de, para)
    # Mesma pagina, um nivel abaixo: os recursos compartilhados sobem um nivel.
    texto = texto.replace("'site-assets/", "'../site-assets/").replace('"site-assets/', '"../site-assets/')
    texto = texto.replace('href="https://www.froid.com.br/"', 'href="%s%s/"' % (SITE, idioma), 1)
    texto = texto.replace(HASH_REDIRECT[""], HASH_REDIRECT["en"])
    return texto


# ---------------------------------------------------------------------------

def ler(rel):
    return io.open(os.path.join(RAIZ, *rel.split("/")), encoding="utf-8").read()


def escrever(rel, texto):
    caminho = os.path.join(RAIZ, *rel.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    io.open(caminho, "w", encoding="utf-8", newline="").write(texto)


def main():
    if os.path.isdir(os.path.join(RAIZ, "psique")):
        raise SystemExit("froid-site/psique/ ja existe: a migracao ja foi aplicada.")
    mapa = montar_mapa()

    # 1. Mover.
    for antigo, novo in sorted(mapa.items()):
        os.makedirs(os.path.join(RAIZ, *posixpath.dirname(novo).split("/")), exist_ok=True)
        git("mv", "froid-site/" + antigo, "froid-site/" + novo)
    # A entrada substitui a home geral em pt-BR (git mv -f leva o historico dela).
    git("mv", "-f", "froid-site/entrada.html", "froid-site/index.html")

    # Onde cada arquivo estava antes (para resolver os relativos antigos).
    de_onde = {novo: antigo for antigo, novo in mapa.items()}
    de_onde["index.html"] = "entrada.html"

    # 2. Reescrever referencias em toda pagina.
    for pasta, _dirs, nomes in os.walk(RAIZ):
        for nome in nomes:
            if not nome.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(pasta, nome), RAIZ).replace(os.sep, "/")
            antigo = de_onde.get(rel, rel)
            texto = ler(rel)
            novo_texto = reescrever_texto(texto, antigo, rel, mapa)
            if novo_texto != texto:
                escrever(rel, novo_texto)

    # 3. A entrada: pt na raiz, e a traducao dela no lugar da index de en/fr/es.
    entrada_pt = ajustar_entrada(ler("index.html"), "")
    escrever("index.html", entrada_pt)
    for idioma in ("en", "fr", "es"):
        escrever(idioma + "/index.html",
                 ajustar_entrada_traduzida(entrada_pt, idioma))

    # 4. Redirecionamentos nos caminhos antigos.
    for antigo, novo in sorted(mapa.items()):
        idioma = antigo.split("/", 1)[0] if "/" in antigo else ""
        escrever(antigo, stub(idioma, antigo, novo))
        git("add", "froid-site/" + antigo)
    escrever("entrada.html", stub("", "entrada.html", "index.html"))
    git("add", "froid-site/entrada.html")

    print("paginas movidas: %d" % len(mapa))
    for antigo, novo in sorted(mapa.items()):
        print("  %-40s -> %s" % (antigo, novo))


def ajustar_entrada_traduzida(entrada_pt, idioma):
    texto = traduzir_entrada(entrada_pt, idioma)
    return texto


if __name__ == "__main__":
    main()
