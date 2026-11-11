# -*- coding: utf-8 -*-
"""Gera o header das paginas do froid-site: menu, marca, troca de produto,
chamada para acao, seletor de idioma e tags hreflang.

RODE ESTE SCRIPT depois de mexer no NAV_SECOES do script.js, nos titulos das
secoes das paginas, ou na composicao dos menus aqui embaixo:

    python tools/gerar-header-do-site.py            # regera
    python tools/gerar-header-do-site.py --conferir # so acusa divergencia

Por que ele existe: o menu do header mostra as SECOES de cada pagina, e esses
rotulos passam a viver tambem no HTML. Isso e uma copia, e copia diverge em
silencio (secao 2.7 da skill-froid-master). O script e a fonte: o HTML e
resultado, nunca escrito a mao.

Estrutura do site desde 09/11/2026 (aprovada pelo dono: "opcao b, com uma
pagina de entrada unica"), igual em cada idioma (pt na raiz, en/, fr/, es/):

    index.html          a entrada, com os dois neuronios (sem header)
    psique/...          FROID Psique   -> menu do Psique (+ Ciencia e Tecnologia)
    nr1/...             FROID NR-1     -> menu do NR-1
    *.html na raiz      paginas comuns -> os dois menus

Toda pagina e identificada pelo caminho RELATIVO a raiz do idioma
("psique/ciencia.html", "nr1/index.html", "menu.html"), e todo href emitido e
recalculado a partir da pasta da propria pagina. Ninguem escreve "../" a mao.

De onde sai cada texto:

- os rotulos dos grupos e das paginas, do mapa IDIOMAS aqui embaixo;
- em pt-BR, o rotulo de cada secao vem do NAV_SECOES do script.js, que ja
  existia e foi escrito para ser item de menu;
- nas traducoes nao ha mapa, e o titulo e lido do cabecalho da propria pagina,
  cortado no travessao ou nos dois pontos.

E o que NAO entra: ancora que nao existe naquele arquivo. As traducoes tem
menos secoes que o pt-BR, e emitir link para ancora inexistente seria criar o
link morto que a revisao de links ja encontrou uma vez.
"""
import io
import os
import posixpath
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.join(REPO, "froid-site")
PASTAS_DE_PRODUTO = ("psique", "nr1")
MARCA_STUB = "<!-- redirecionamento: pagina movida em 09/11/2026 -->"

IDIOMAS = {
    "": {
        "psique": ("FROID Psique", "psique/index.html", [
            ("Visão geral", "psique/index.html"),
            ("Como funciona", "psique/como-funciona-clinico.html"),
            ("FROID Explica", "psique/froid-explica.html"),
            ("Data-Froid", "psique/data-froid.html"),
        ]),
        "nr1": ("FROID NR-1", "nr1/index.html", [
            ("Visão geral", "nr1/index.html"),
            ("Cadeia de Comando", "nr1/contratacao-nr1.html"),
            ("FROID ISO 45001", "nr1/iso-45001.html"),
            ("Apresentação NR-1", "nr1/apresentacao-nr1.html"),
        ]),
        "tecnico": ("Ciência e Tecnologia", "psique/tecnologia.html", [
            ("Tecnologia", "psique/tecnologia.html"),
            ("Mapas da face", "psique/mapas-faciais.html"),
            ("Ciência", "psique/ciencia.html"),
        ]),
        "soltos": [("Explorar", "menu.html"), ("Contato", "sobre-contato.html")],
    },
    "en": {
        "psique": ('FROID Psique', "psique/index.html", [
            ('Overview', 'psique/index.html'),
            ('How it works', 'psique/como-funciona-clinico.html'),
            ('FROID Explains', 'psique/froid-explica.html'),
            ('Data-Froid', 'psique/data-froid.html'),
        ]),
        "nr1": ('FROID NR-1', "nr1/index.html", [
            ('Overview', 'nr1/index.html'),
            ('Proposal', 'nr1/proposta-nr1.html'),
            ('FROID ISO 45001', 'nr1/iso-45001.html'),
        ]),
        "tecnico": ('Science &amp; Technology', "psique/tecnologia.html", [
            ('Technology', 'psique/tecnologia.html'),
            ('Facial maps', 'psique/mapas-faciais.html'),
            ('Science', 'psique/ciencia.html'),
        ]),
        "soltos": [('Explore', 'menu.html'), ('Contact', 'sobre-contato.html')],
    },
    "es": {
        "psique": ('FROID Psique', "psique/index.html", [
            ('Visión general', 'psique/index.html'),
            ('Cómo funciona', 'psique/como-funciona-clinico.html'),
            ('FROID Explica', 'psique/froid-explica.html'),
            ('Data-Froid', 'psique/data-froid.html'),
        ]),
        "nr1": ('FROID NR-1', "nr1/index.html", [
            ('Visión general', 'nr1/index.html'),
            ('Propuesta', 'nr1/proposta-nr1.html'),
            ('FROID ISO 45001', 'nr1/iso-45001.html'),
        ]),
        "tecnico": ('Ciencia y Tecnología', "psique/tecnologia.html", [
            ('Tecnología', 'psique/tecnologia.html'),
            ('Mapas del rostro', 'psique/mapas-faciais.html'),
            ('Ciencia', 'psique/ciencia.html'),
        ]),
        "soltos": [('Explorar', 'menu.html'), ('Contacto', 'sobre-contato.html')],
    },
    "fr": {
        "psique": ('FROID Psique', "psique/index.html", [
            ("Vue d'ensemble", 'psique/index.html'),
            ('Comment ça marche', 'psique/como-funciona-clinico.html'),
            ('FROID Explique', 'psique/froid-explica.html'),
            ('Data-Froid', 'psique/data-froid.html'),
        ]),
        "nr1": ('FROID NR-1', "nr1/index.html", [
            ("Vue d'ensemble", 'nr1/index.html'),
            ('Proposition', 'nr1/proposta-nr1.html'),
            ('FROID ISO 45001', 'nr1/iso-45001.html'),
        ]),
        "tecnico": ('Science et Technologie', "psique/tecnologia.html", [
            ('Technologie', 'psique/tecnologia.html'),
            ('Cartes du visage', 'psique/mapas-faciais.html'),
            ('Science', 'psique/ciencia.html'),
        ]),
        "soltos": [('Explorer', 'menu.html'), ('Contact', 'sobre-contato.html')],
    },
}

# Troca de produto e chamada para acao, no nav-actions de toda pagina com
# header. Pagina do Psique leva ao NR-1 e oferece o cadastro; pagina do NR-1
# leva ao Psique e oferece o contato; pagina comum mostra os dois.
# O texto da chamada NAO traz quantidade de sessoes nem de dias: numero
# comercial vive na pagina de precos, que tem fonte (secao 2.7 da skill).
ACOES = {
    "": {
        "ir_para": "Ir para o %s",
        "psique": ("Cadastre-se e comece o teste grátis", "Teste grátis"),
        "nr1": ("Entre em contato", "Contato"),
    },
    "en": {
        "ir_para": "Go to %s",
        "psique": ("Sign up and start your free trial", "Free trial"),
        "nr1": ("Contact us", "Contact"),
    },
    "fr": {
        "ir_para": "Aller à %s",
        "psique": ("Inscrivez-vous et commencez l'essai gratuit", "Essai gratuit"),
        "nr1": ("Contactez-nous", "Contact"),
    },
    "es": {
        "ir_para": "Ir a %s",
        "psique": ("Regístrese y empiece la prueba gratuita", "Prueba gratuita"),
        "nr1": ("Contáctenos", "Contacto"),
    },
}
CADASTRO = "https://www.froid.com.br/cadastro"

# Botao de acesso restrito as 10 habilidades (psique/percepcao-clinica.html).
# Pedido do dono, 10/11/2026: a pagina so abre com a senha que ele fornece.
# A senha e conferida pelo Caddy (basic_auth no Caddyfile), nao no navegador:
# senha conferida em JavaScript estaria escrita na propria pagina. So existe
# em pt-BR, e so aparece nas paginas do Psique.
RESTRITO = {
    "": ("As 10 habilidades do FROID Psique, acesso com senha", "10 habilidades"),
}
ICONE_CADEADO = ('<svg class="nav-restrito-icone" viewBox="0 0 16 16" width="13" height="13" '
                 'aria-hidden="true" focusable="false"><rect x="3" y="7" width="10" height="7" rx="1.5" '
                 'fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" '
                 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>')
NOME_PRODUTO = {"psique": "FROID Psique", "nr1": "FROID NR-1"}
ICONE_TROCA = ('<svg class="nav-troca-icone" viewBox="0 0 16 16" width="14" height="14" '
               'aria-hidden="true" focusable="false"><path d="M2 5.5h10.5L9.5 2.5M14 10.5H3.5l3 3" '
               'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
               'stroke-linejoin="round"/></svg>')

NAV = re.compile(r'<nav class="nav-links">.*?</nav>', re.S)
BRAND = re.compile(r'(<a class="brand" href=")[^"]*(")')
ACOES_GERADAS = re.compile(
    r'[ \t]*<!-- produto e chamada: gerado por tools/gerar-header-do-site\.py -->\n'
    r'.*?<!-- /produto e chamada -->\n', re.S)
NAV_ACTIONS = re.compile(r'<div class="nav-actions">\n')
TAG = re.compile(r"<[^>]+>")


def rel(pagina, alvo):
    """Href de `alvo` a partir de `pagina` (os dois relativos a raiz do idioma)."""
    return posixpath.relpath(alvo, posixpath.dirname(pagina) or ".")


def produto_de(pagina):
    pasta = pagina.split("/", 1)[0] if "/" in pagina else ""
    return pasta if pasta in PASTAS_DE_PRODUTO else None


def caminho_local(idioma, pagina):
    return os.path.join(RAIZ, idioma, *pagina.split("/")) if idioma \
        else os.path.join(RAIZ, *pagina.split("/"))


def carregar_nav_secoes():
    js = io.open(os.path.join(RAIZ, "site-assets", "script.js"), encoding="utf-8").read()
    bloco = js.split("var NAV_SECOES = {", 1)[1].split("\n};", 1)[0]
    mapa = {}
    for m in re.finditer(r'"([a-z0-9./-]+\.html)":\s*\[(.*?)\]\s*,?\s*(?=\n  "|\Z)', bloco, re.S):
        mapa[m.group(1)] = re.findall(r'\["([^"]+)",\s*"([^"]+)"\]', m.group(2))
    return mapa


NAV_SECOES = carregar_nav_secoes()
_cache = {}


def secoes_da_pagina(idioma, pagina):
    """(ancora, titulo) das secoes que EXISTEM neste arquivo, na ordem curada."""
    chave = (idioma, pagina)
    if chave in _cache:
        return _cache[chave]
    caminho = caminho_local(idioma, pagina)
    achadas = []
    if os.path.exists(caminho):
        html = io.open(caminho, encoding="utf-8").read()
        for ancora, rotulo_curado in NAV_SECOES.get(pagina, []):
            # Em pt-BR o rotulo curto ja existe no NAV_SECOES — ele foi escrito
            # para ser item de menu. Nas traducoes nao existe, e o titulo sai do
            # cabecalho da propria pagina, cortado no travessao ou nos dois
            # pontos: "Calibracao da linha de base — 60 segundos" vira
            # "Calibracao da linha de base". Cabecalho inteiro num menu quebra
            # em quatro linhas e deixa de ser navegavel.
            if not idioma:
                if ancora in re.findall(r'\sid="([^"]+)"', html):
                    achadas.append((ancora, rotulo_curado))
                continue
            # Dois padroes convivem no site: o id no contentor da secao, com o
            # cabecalho logo dentro, e o id no PROPRIO <h2>. So o primeiro era
            # tratado, e tres secoes de como-funciona-nr1 sumiam do menu sem
            # erro nenhum — o defeito 2.2 desta casa.
            m = re.search(
                r'<h[123][^>]*\sid="' + re.escape(ancora) + r'"[^>]*>(.*?)</h[123]>',
                html, re.S)
            if not m:
                m = re.search(
                    r'\sid="' + re.escape(ancora) + r'"(.{0,1200}?)<h[123][^>]*>(.*?)</h[123]>',
                    html, re.S)
            if not m:
                continue
            titulo = TAG.sub("", m.group(m.lastindex))
            titulo = re.sub(r"\s+", " ", titulo).strip()
            titulo = re.split(r"\s+[—–:]\s+", titulo)[0].strip()
            # Emoji decorativo no comeco de alguns titulos nao ajuda num menu.
            titulo = re.sub(r"^[^\wÀ-ſ(]+", "", titulo).strip()
            if titulo:
                achadas.append((ancora, titulo))
    _cache[chave] = achadas
    return achadas


def escapar(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def coluna(rot_pagina, alvo, idioma, pagina_ativa, primeira_e_visao_geral):
    href = rel(pagina_ativa, alvo)
    linhas = ['        <div class="nav-drop-col">']
    cls = ["nav-drop-pagina"]
    if primeira_e_visao_geral:
        cls.append("nav-drop-visao-geral")
    if alvo == pagina_ativa:
        cls.append("ativo")
    linhas.append('          <a class="%s" role="menuitem" href="%s">%s</a>'
                  % (" ".join(cls), href, rot_pagina))
    for ancora, titulo in secoes_da_pagina(idioma, alvo):
        linhas.append('          <a class="nav-drop-secao" role="menuitem" href="%s#%s">%s</a>'
                      % (href, ancora, escapar(titulo)))
    linhas.append("        </div>")
    return linhas


def bloco_menu(rotulo, alvo_rotulo, filhos, idioma, pagina_ativa):
    no_grupo = pagina_ativa == alvo_rotulo or any(h == pagina_ativa for _, h in filhos)
    cls_drop = "nav-drop nav-drop-mega"
    linhas = [
        '        <span class="nav-menu">',
        '          <a class="nav-familia-rotulo%s" href="%s">%s</a>'
        % (" ativo" if no_grupo else "", rel(pagina_ativa, alvo_rotulo), rotulo),
        '          <div class="%s" role="menu">' % cls_drop,
    ]
    for i, (rot, alvo) in enumerate(filhos):
        linhas += ["  " + l for l in coluna(
            rot, alvo, idioma, pagina_ativa, i == 0 and alvo == alvo_rotulo)]
    linhas += ["          </div>", "        </span>"]
    return "\n".join(linhas)


def familias_da_pagina(cfg, pagina):
    """Cada produto mostra o proprio menu; pagina comum mostra os dois."""
    produto = produto_de(pagina)
    if produto == "psique":
        return [cfg["psique"]], True
    if produto == "nr1":
        return [cfg["nr1"]], False
    return [cfg["psique"], cfg["nr1"]], True


def montar(idioma, pagina):
    cfg = IDIOMAS[idioma]
    familias, com_tecnico = familias_da_pagina(cfg, pagina)
    out = ['<nav class="nav-links">']
    for rotulo, alvo, filhos in familias:
        out.append('      <span class="nav-familia">')
        out.append(bloco_menu(rotulo, alvo, filhos, idioma, pagina))
        out.append("      </span>")
    out.append('      <span class="nav-familia">')
    if com_tecnico:
        rot, alvo, filhos = cfg["tecnico"]
        out.append(bloco_menu(rot, alvo, filhos, idioma, pagina))
    for rotulo, alvo in cfg["soltos"]:
        cls = ' class="ativo"' if alvo == pagina else ""
        out.append('        <a%s href="%s">%s</a>' % (cls, rel(pagina, alvo), rotulo))
    out.append("      </span>")
    out.append("    </nav>")
    return "\n".join(out)


def bloco_acoes(idioma, pagina):
    """Troca de produto + chamada para acao, antes do botao Entrar."""
    txt = ACOES[idioma]
    produto = produto_de(pagina)
    trocas = {"psique": ["nr1"], "nr1": ["psique"]}.get(produto, ["psique", "nr1"])
    chamadas = [produto] if produto else ["psique", "nr1"]
    linhas = ["      <!-- produto e chamada: gerado por tools/gerar-header-do-site.py -->"]
    if produto == "psique" and idioma in RESTRITO:
        aria, rotulo = RESTRITO[idioma]
        linhas.append(
            '      <a class="nav-restrito" href="%s" aria-label="%s">%s<span>%s</span></a>'
            % (rel(pagina, "psique/percepcao-clinica.html"), escapar(aria), ICONE_CADEADO,
               escapar(rotulo)))
    for destino in trocas:
        nome = NOME_PRODUTO[destino]
        # Com as duas trocas (pagina comum) o "FROID " some na tela, para o
        # header caber numa linha; o aria-label continua com o nome inteiro.
        compacta = " nav-troca-compacta" if len(trocas) > 1 else ""
        linhas.append(
            '      <a class="nav-troca-produto nav-troca-%s%s" href="%s" aria-label="%s">%s'
            '<span><span class="nav-troca-marca">FROID </span>%s</span></a>'
            % (destino, compacta, rel(pagina, destino + "/index.html"),
               escapar(txt["ir_para"] % nome), ICONE_TROCA, nome.replace("FROID ", "", 1)))
    for chamada in chamadas:
        longo, curto = txt[chamada]
        href = CADASTRO if chamada == "psique" else rel(pagina, "sobre-contato.html") + "#nr1"
        classe = "btn-solid" if len(chamadas) == 1 or chamada == "psique" else "btn-ghost"
        # Pagina comum leva as duas chamadas e as duas trocas: com o rotulo
        # longo o header passava da largura em 1280px (medido com
        # tools/checar-telas-do-site.mjs). Ali vale o rotulo curto.
        if len(chamadas) > 1:
            classe += " nav-cta-compacto"
        linhas.append(
            '      <a class="btn %s nav-cta nav-cta-%s" href="%s" aria-label="%s">'
            '<span class="nav-cta-longo">%s</span><span class="nav-cta-curto" aria-hidden="true">%s</span></a>'
            % (classe, chamada, href, escapar(longo), escapar(longo), escapar(curto)))
    linhas.append("      <!-- /produto e chamada -->")
    return "\n".join(linhas) + "\n"


def aplicar_acoes(texto, idioma, pagina):
    bloco = bloco_acoes(idioma, pagina)
    if ACOES_GERADAS.search(texto):
        return ACOES_GERADAS.sub(lambda _m: bloco, texto, count=1)
    m = NAV_ACTIONS.search(texto)
    if not m:
        return texto
    return texto[:m.end()] + bloco + texto[m.end():]


# --------------------------------------------------------------------------
# Seletor de idioma e tags hreflang — mesma disciplina do menu: uma fonte só.
#
# Escritos a mão, saíam errados sem ninguém perceber: em empresas.html o
# seletor tinha SÓ a pill PT, sem link nenhum para EN/FR/ES — quem chegasse
# ali em português não tinha como trocar de idioma, e a página só declarava
# 2 das 5 tags hreflang. O rótulo de acessibilidade em pt-BR também estava em
# inglês ("Choose language") enquanto es e fr tinham o seu.
# --------------------------------------------------------------------------

SITE = "https://www.froid.com.br/"
ORDEM = ["", "en", "fr", "es"]            # ordem das pills: PT EN FR ES
SIGLA = {"": "PT", "en": "EN", "fr": "FR", "es": "ES"}
ARIA = {
    "": "Escolher idioma",
    "en": "Choose language",
    "fr": "Choisir la langue",
    "es": "Elegir idioma",
}

LANG_GROUP = re.compile(r'<div class="lang-group"[^>]*>.*?</div>', re.S)
HREFLANG = re.compile(
    r'[ \t]*<link rel="alternate" hreflang="[^"]*" href="[^"]*" />\n', re.S)
STYLESHEET = re.compile(r'[ \t]*<link rel="stylesheet"')


def caminho_relativo(de_idioma, para_idioma, pagina):
    """Href de uma pasta de idioma para a mesma página em outra."""
    origem = posixpath.join(de_idioma, pagina) if de_idioma else pagina
    alvo = posixpath.join(para_idioma, pagina) if para_idioma else pagina
    return posixpath.relpath(alvo, posixpath.dirname(origem) or ".")


def existe(idioma, pagina):
    caminho = caminho_local(idioma, pagina)
    if not os.path.exists(caminho):
        return False
    # O redirecionamento no endereco antigo nao e a pagina.
    return MARCA_STUB not in io.open(caminho, encoding="utf-8").read(400)


def bloco_idiomas(idioma, pagina):
    # Pill e hreflang so para traducao que EXISTE. Desde 06/10/2026 ha paginas
    # so em pt-BR (como-funciona-clinico, data-froid, menu); uma pill para en/
    # delas daria 404.
    outros = [o for o in ORDEM if o != idioma and existe(o, pagina)]
    if not outros:
        return ""
    partes = ['<div class="lang-group" role="group" aria-label="%s">' % ARIA[idioma]]
    for outro in ORDEM:
        if outro == idioma:
            partes.append('<span class="lang-pill lang-current">%s</span>' % SIGLA[outro])
        elif outro in outros:
            partes.append('<a class="lang-pill" href="%s">%s</a>'
                          % (caminho_relativo(idioma, outro, pagina), SIGLA[outro]))
    partes.append("</div>")
    return "".join(partes)


def url_publica(idioma, pagina):
    # index.html é servida pela URL do diretório; é a forma canônica e é a que
    # o site já declarava. Manter, para não trocar URL canônica por descuido.
    base = SITE + (idioma + "/" if idioma else "")
    if pagina == "index.html":
        return base
    if pagina.endswith("/index.html"):
        return base + pagina[: -len("index.html")]
    return base + pagina


def bloco_hreflang(pagina):
    linhas = []
    for outro in ["", "en", "fr", "es"]:
        if not existe(outro, pagina):
            continue
        sigla = "pt-BR" if not outro else outro
        linhas.append('<link rel="alternate" hreflang="%s" href="%s" />'
                      % (sigla, url_publica(outro, pagina)))
    linhas.append('<link rel="alternate" hreflang="x-default" href="%s" />'
                  % url_publica("", pagina))
    return "\n".join(linhas) + "\n"


def aplicar_hreflang(texto, pagina):
    """Substitui o bloco existente; se não houver, insere antes do stylesheet."""
    if re.search(r'name="robots"\s+content="[^"]*\bnoindex\b', texto):
        return texto                      # página fora do índice não declara alternativas
    novo = bloco_hreflang(pagina)
    if HREFLANG.search(texto):
        primeiro = [True]

        def troca(_m):
            if primeiro[0]:
                primeiro[0] = False
                return novo
            return ""

        return HREFLANG.sub(troca, texto)
    m = STYLESHEET.search(texto)
    if not m:
        return texto
    return texto[:m.start()] + novo + texto[m.start():]


def paginas_do_idioma(idioma):
    """Caminhos relativos a raiz do idioma: raiz + pastas de produto."""
    base = os.path.join(RAIZ, idioma) if idioma else RAIZ
    for sub in ("",) + PASTAS_DE_PRODUTO:
        d = os.path.join(base, sub) if sub else base
        if not os.path.isdir(d):
            continue
        for nome in sorted(os.listdir(d)):
            if nome.endswith(".html") and os.path.isfile(os.path.join(d, nome)):
                yield (sub + "/" + nome) if sub else nome


def processar(texto, idioma, pagina):
    if MARCA_STUB in texto:
        return texto
    novo = texto
    tem_header = bool(NAV.search(novo))
    if tem_header:
        novo = NAV.sub(lambda _m: montar(idioma, pagina), novo, count=1)
        novo = BRAND.sub(lambda m: m.group(1) + rel(pagina, "index.html") + m.group(2), novo, count=1)
        novo = aplicar_acoes(novo, idioma, pagina)
    if LANG_GROUP.search(novo):
        novo = LANG_GROUP.sub(lambda _m: bloco_idiomas(idioma, pagina), novo, count=1)
    return aplicar_hreflang(novo, pagina)


def main():
    conferir = "--conferir" in sys.argv
    trocadas = 0
    arquivos = 0
    divergentes = []
    for idioma in IDIOMAS:
        for pagina in paginas_do_idioma(idioma):
            caminho = caminho_local(idioma, pagina)
            arquivos += 1
            texto = io.open(caminho, encoding="utf-8").read()
            novo = processar(texto, idioma, pagina)
            if novo == texto:
                continue
            if conferir:
                divergentes.append(posixpath.join(idioma, pagina) if idioma else pagina)
            else:
                io.open(caminho, "w", encoding="utf-8", newline="").write(novo)
                trocadas += 1

    if conferir:
        if divergentes:
            print("HEADER FORA DE SINCRONIA em %d arquivo(s):" % len(divergentes))
            for p in divergentes:
                print("   ", p)
            print()
            print("Rode `python tools/gerar-header-do-site.py` para regerar.")
            sys.exit(1)
        print("header em dia nos", arquivos, "arquivos")
    else:
        print("headers reescritos:", trocadas)

    # Ancora curada que existe no arquivo mas nao virou item de menu: some sem
    # erro nenhum se ninguem contar. Aqui ela e listada.
    print()
    perdidas = []
    for idioma in IDIOMAS:
        cfg = IDIOMAS[idioma]
        for _rot, _h, filhos in (cfg["psique"], cfg["nr1"], cfg["tecnico"]):
            for _r, alvo in filhos:
                caminho = caminho_local(idioma, alvo)
                if not os.path.exists(caminho):
                    continue
                html = io.open(caminho, encoding="utf-8").read()
                ids = set(re.findall(r'\sid="([^"]+)"', html))
                no_menu = {a for a, _t in secoes_da_pagina(idioma, alvo)}
                for a, _rot in NAV_SECOES.get(alvo, []):
                    if a in ids and a not in no_menu:
                        perdidas.append("%s/%s#%s" % (idioma or "pt", alvo, a))
    if perdidas:
        print("ANCORAS QUE EXISTEM E NAO ENTRARAM NO MENU (sem titulo extraivel):")
        for p in perdidas:
            print("   ", p)
    else:
        print("nenhuma ancora existente ficou de fora do menu")

    # Item de menu para pagina que nao existe naquele idioma: link morto.
    ausentes = []
    for idioma in IDIOMAS:
        cfg = IDIOMAS[idioma]
        for _rot, h, filhos in (cfg["psique"], cfg["nr1"], cfg["tecnico"]):
            for alvo in [h] + [a for _r, a in filhos] + [a for _r, a in cfg["soltos"]]:
                if not existe(idioma, alvo):
                    ausentes.append("%s/%s" % (idioma or "pt", alvo))
    if ausentes:
        print("MENU APONTA PARA PAGINA INEXISTENTE:")
        for p in sorted(set(ausentes)):
            print("   ", p)
        if conferir:
            sys.exit(1)

    print()
    print("secoes por coluna, por idioma:")
    for idioma in IDIOMAS:
        cfg = IDIOMAS[idioma]
        for rotulo, _h, filhos in (cfg["psique"], cfg["nr1"], cfg["tecnico"]):
            alturas = [1 + len(secoes_da_pagina(idioma, h)) for _r, h in filhos]
            print("  %-3s %-22s colunas=%d  altura maxima=%2d linhas  %s"
                  % (idioma or "pt", TAG.sub("", rotulo)[:22], len(filhos),
                     max(alturas), alturas))


if __name__ == "__main__":
    main()
