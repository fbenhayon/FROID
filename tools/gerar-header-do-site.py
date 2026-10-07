# -*- coding: utf-8 -*-
"""Gera o <nav> do header das 84 paginas do froid-site.

RODE ESTE SCRIPT depois de mexer no NAV_SECOES do script.js, nos titulos das
secoes das paginas, ou na composicao dos menus aqui embaixo:

    python tools/gerar-header-do-site.py            # regera
    python tools/gerar-header-do-site.py --conferir # so acusa divergencia

Por que ele existe: o menu do header mostra as SECOES de cada pagina, e esses
rotulos passam a viver tambem no HTML. Isso e uma copia, e copia diverge em
silencio (secao 2.7 da skill-froid-master). O script e a fonte: o HTML e
resultado, nunca escrito a mao.

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
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.join(REPO, "froid-site")

# "Demonstracao" so entra no menu em pt-BR. A pagina existe nos quatro idiomas
# e o rodape ja a lista em todos, mas en/fr/es ainda tem o texto curto antigo,
# de quatro secoes; o percurso completo do Psique so foi escrito em pt-BR.
# Por em destaque no header uma pagina que nao entrega o que o rotulo promete e
# o defeito 2.4 da skill-froid-master. Ao traduzir, acrescente a linha nos
# outros tres idiomas e rode este script de novo.
IDIOMAS = {
    # pt-BR reescrito em 06/10/2026: a index virou institucional (dois produtos),
    # profissionais.html e a visao geral do Psique e empresas.html a do NR-1.
    # As traducoes seguem a arquitetura anterior ate serem traduzidas.
    "": {
        "familias": [
            ("FROID Psique", "profissionais.html", [
                ("Vis\u00e3o geral", "profissionais.html"),
                ("Como funciona", "como-funciona-clinico.html"),
                ("Demonstra\u00e7\u00e3o", "demonstracao.html"),
                ("FROID Explica", "froid-explica.html"),
                ("Data-Froid", "data-froid.html"),
            ]),
            ("FROID NR-1", "empresas.html", [
                ("Vis\u00e3o geral", "empresas.html"),
                ("Como funciona", "como-funciona-nr1.html"),
                ("Prontid\u00e3o", "diagnostico-nr1.html"),
                ("Proposta", "proposta-nr1.html"),
                ("FROID Explica NR-1", "froid-explica-nr1.html"),
                ("ISO 45003", "iso-45003.html"),
            ]),
        ],
        "tecnico": ("Ci\u00eancia e Tecnologia", "tecnologia.html", [
            ("Tecnologia", "tecnologia.html"),
            ("Mapas da face", "mapas-faciais.html"),
            ("Ci\u00eancia", "ciencia.html"),
        ]),
        "soltos": [("\u00c9tica", "etica.html"), ("Seguran\u00e7a", "seguranca.html"),
                   ("Pre\u00e7os", "precos.html"), ("Explorar", "menu.html")],
    },
    "en": {
        "familias": [
            ("FROID Psique", "index.html", [
                ("Overview", "index.html"),
                ("Professionals", "profissionais.html"),
                ("FROID Explains", "froid-explica.html"),
            ]),
            ("FROID NR-1/ISO-45003", "iso-45003.html", [
                ("Overview (ISO 45003)", "iso-45003.html"),
                ("For Employers", "empresas.html"),
                ("How it works", "como-funciona-nr1.html"),
                ("FROID Explains NR-1", "froid-explica-nr1.html"),
            ]),
        ],
        "tecnico": ("Science &amp; Technology", "ciencia.html", [
            ("Science", "ciencia.html"),
            ("Technology", "tecnologia.html"),
            ("Facial maps", "mapas-faciais.html"),
        ]),
        "soltos": [("Ethics", "etica.html"), ("Security", "seguranca.html"),
                   ("Pricing", "precos.html")],
    },
    "es": {
        "familias": [
            ("FROID Psique", "index.html", [
                ("Visi\u00f3n general", "index.html"),
                ("Profesionales", "profissionais.html"),
                ("FROID Explica", "froid-explica.html"),
            ]),
            ("FROID NR-1/ISO-45003", "iso-45003.html", [
                ("Visi\u00f3n general (ISO 45003)", "iso-45003.html"),
                ("Para Empresas", "empresas.html"),
                ("C\u00f3mo funciona", "como-funciona-nr1.html"),
                ("FROID Explica NR-1", "froid-explica-nr1.html"),
            ]),
        ],
        "tecnico": ("Ciencia y Tecnolog\u00eda", "ciencia.html", [
            ("Ciencia", "ciencia.html"),
            ("Tecnolog\u00eda", "tecnologia.html"),
            ("Mapas del rostro", "mapas-faciais.html"),
        ]),
        "soltos": [("\u00c9tica", "etica.html"), ("Seguridad", "seguranca.html"),
                   ("Precios", "precos.html")],
    },
    "fr": {
        "familias": [
            ("FROID Psique", "index.html", [
                ("Vue d'ensemble", "index.html"),
                ("Professionnels", "profissionais.html"),
                ("FROID Explique", "froid-explica.html"),
            ]),
            ("FROID NR-1/ISO-45003", "iso-45003.html", [
                ("Vue d'ensemble (ISO 45003)", "iso-45003.html"),
                ("Pour les Entreprises", "empresas.html"),
                ("Comment \u00e7a marche", "como-funciona-nr1.html"),
                ("FROID Explique NR-1", "froid-explica-nr1.html"),
            ]),
        ],
        "tecnico": ("Science et Technologie", "ciencia.html", [
            ("Science", "ciencia.html"),
            ("Technologie", "tecnologia.html"),
            ("Cartes du visage", "mapas-faciais.html"),
        ]),
        "soltos": [("\u00c9thique", "etica.html"), ("S\u00e9curit\u00e9", "seguranca.html"),
                   ("Tarifs", "precos.html")],
    },
}

NAV = re.compile(r'<nav class="nav-links">.*?</nav>', re.S)
TAG = re.compile(r"<[^>]+>")


def carregar_nav_secoes():
    js = io.open(os.path.join(RAIZ, "site-assets", "script.js"), encoding="utf-8").read()
    bloco = js.split("var NAV_SECOES = {", 1)[1].split("\n};", 1)[0]
    mapa = {}
    for m in re.finditer(r'"([a-z0-9.-]+\.html)":\s*\[(.*?)\]\s*,?\s*(?=\n  "|\Z)', bloco, re.S):
        mapa[m.group(1)] = re.findall(r'\["([^"]+)",\s*"([^"]+)"\]', m.group(2))
    return mapa


NAV_SECOES = carregar_nav_secoes()
# As traducoes (en/, es/, fr/) seguem a arquitetura ANTERIOR do site: em
# 06/10/2026 so o pt-BR foi trocado pela versao nova, e o NAV_SECOES do
# script.js passou a descrever as paginas novas. Este e o mapa que valia
# ate entao, e e por ele que as ancoras das traducoes sao procuradas. Ao
# traduzir as paginas novas, apague este mapa e deixe tudo usar o do script.
NAV_SECOES_TRADUCOES = {
    "index.html": [
        ('visao-geral', 'Visão geral'),
        ('data-froid', 'Data-Froid'),
        ('para-quem-e', 'Para quem é'),
        ('o-diferencial', 'O diferencial'),
        ('paciente', 'Portal do Paciente'),
        ('transparencia', 'Transparência'),
        ('explore', 'Por onde seguir'),
    ],
    "ciencia.html": [
        ('evidencia', 'Explorador de evidências'),
        ('percepcao-do-paciente', 'A percepção do paciente sobre a própria expressão'),
        ('data-froid-ciencia', 'O que o Data-Froid prova, e o que não'),
        ('bibliografia', 'Metodologia de verificação'),
    ],
    "tecnologia.html": [
        ('baseline', 'Calibração da linha de base'),
        ('extracao-acustica', 'Extração acústica'),
        ('facs', 'Dinâmica facial (FACS)'),
        ('zonas', 'As 12 Zonas de Percepção'),
        ('data-froid-engenharia', 'Por que o acervo não era possível'),
        ('ipm-idm', 'Os índices IPM e IDM'),
        ('estabilizacao', 'Estabilização clínica da tela'),
    ],
    "froid-explica.html": [
        ('veja-em-acao', 'Veja em ação'),
        ('como-funciona', 'Como funciona'),
        ('inteligencia-da-carteira', 'Inteligência da carteira'),
        ('prompts', 'Biblioteca de prompts'),
        ('personalizacao', 'Personalização'),
        ('datamart', 'A base que aprende com o mundo'),
    ],
    "etica.html": [
        ('pilar-1-diretrizes-inegociaveis', 'Diretrizes inegociáveis'),
        ('pilar-2-fairness-algoritmica', 'Fairness algorítmica'),
        ('pilar-3-produto', 'Produto'),
        ('pilar-4-conformidade-legal', 'Conformidade legal'),
        ('pilar-5-soberania-de-dados', 'Soberania de dados'),
        ('kit-de-conformidade', 'Kit de conformidade'),
    ],
    "seguranca.html": [
        ('protecao', 'Proteção de dados'),
        ('caminho', 'O caminho de uma sessão'),
        ('conformidade', 'Conformidade'),
    ],
    "profissionais.html": [
        ('sessao', 'Antes, durante e depois'),
        ('financeiro', 'Controle financeiro'),
        ('relatorios', 'Relatórios de pacientes'),
        ('data-froid', 'Data-Froid'),
        ('equipe', 'Compartilhamento entre profissionais'),
        ('seguranca-e-responsabilidade', 'Segurança e responsabilidade'),
        ('proximo-passo', 'Próximo passo'),
    ],
    "iso-45003.html": [
        ('indice', 'Como a página se organiza'),
        ('o-que-e', 'O que a ISO 45003 é'),
        ('lastro', 'O critério que decide numa perícia'),
        ('documental', 'Dever de conduta × dever documental'),
        ('ja-tem-45001', 'Se você já tem ISO 45001'),
        ('limites', 'O que não afirmamos'),
        ('proximo', 'Próximo passo'),
    ],
    "froid-explica-nr1.html": [
        ('duas-camadas', 'As duas camadas'),
        ('temas', 'Os oito temas'),
        ('trabalhador', 'O que o trabalhador pergunta'),
        ('acervo', 'O acervo, e o que é recusado'),
        ('limites', 'O que não é'),
        ('proximo-passo', 'Próximo passo'),
    ],
    "empresas.html": [
        ('indice', 'Como a página se organiza'),
        ('o-retrato-legal', 'O que mudou na norma'),
        ('o-que-a-fiscalizacao-pede', 'Os três documentos'),
        ('o-custo-da-omissao', 'O custo da omissão'),
        ('armadilhas', 'Seis erros que geram passivo'),
        ('solucao', 'A AEP psicossocial'),
        ('a-plataforma', 'A plataforma'),
        ('eficacia', 'Provar que a medida funcionou'),
        ('dado-insuficiente', 'Quando o dado não basta'),
        ('comparacao', 'Gestão tradicional × FROID'),
        ('perguntas-fornecedor', 'Cinco perguntas ao fornecedor'),
        ('precos-nr1', 'Quanto custa'),
        ('limites-e-responsabilidade', 'Limites e responsabilidade'),
        ('proximo-passo', 'Comece por um estabelecimento'),
    ],
    "como-funciona-nr1.html": [
        ('as-sete-etapas', 'As nove etapas'),
        ('dossie-verificavel', 'Comprovação de Gestão Diciplinar'),
        ('os-perigos', 'A listagem do Guia MTE'),
        ('o-que-e-igual-em-toda-empresa-e-o-que-muda', 'O que muda em cada empresa'),
        ('quando-a-segunda-avaliacao-reprova', 'E se a segunda avaliação reprovar?'),
        ('a-sua-empresa-tem-tamanho-para-isso', 'A sua empresa tem tamanho?'),
    ],
    "precos.html": [
        ('planos', 'Planos PRO, PLUS e MASTER'),
        ('comparacao', 'Comparação de habilidades'),
        ('creditos', 'Como funcionam os créditos'),
        ('nr1', 'Precisa cumprir a NR-1?'),
        ('antes-de-decidir', 'Antes de decidir'),
    ],
    "diagnostico-nr1.html": [
        ('por-que-existe-um-piso', 'Por que existe um piso'),
        ('se-a-sua-empresa-nao-atinge-o-piso', 'Se não atinge o piso'),
    ],
    "proposta-nr1.html": [
        ('o-que-esta-sendo-contratado', 'O que está sendo contratado'),
        ('fases', 'Fases'),
        ('condicoes-comerciais', 'Condições comerciais'),
        ('o-que-a-contratante-precisa-fornecer', 'O que a contratante fornece'),
        ('por-que-este-procedimento-e-nao-outro', 'Por que este procedimento'),
        ('protecao-de-dados', 'Proteção de dados'),
        ('limites-do-servico', 'Limites do serviço'),
        ('aceite', 'Aceite'),
    ],
    "sobre-contato.html": [
        ('quem-faz-o-froid', 'Quem faz o FROID'),
        ('fale-com-o-time', 'Contato'),
    ],
    "mapas-faciais.html": [
        ('dois-mapas', 'Dois mapas, duas perguntas'),
        ('vocabulario', 'O que cada AU significa'),
        ('composicao', 'Como as AUs se combinam'),
        ('leitura', 'Do rosto à leitura'),
        ('limites', 'O que os mapas não afirmam'),
    ],
    "demonstracao.html": [
        ('indice', 'Como a página se organiza'),
        ('o-que-e', 'As três camadas'),
        ('antes', 'Antes: conta, convite e sala'),
        ('calibracao', 'Os 60 primeiros segundos'),
        ('durante', 'Durante: o que a tela mostra'),
        ('sem-apuracao', 'Quando não há o que medir'),
        ('explica', 'Perguntar ao FROID Explica'),
        ('depois', 'Depois: o relatório'),
        ('liberacao', 'O documento do paciente'),
        ('acervo', 'O que volta ao Data-Froid'),
        ('limites', 'O que o FROID não afirma'),
        ('proximo-passo', 'Próximo passo'),
    ],
}
_cache = {}


def secoes_da_pagina(idioma, pagina):
    """(ancora, titulo) das secoes que EXISTEM neste arquivo, na ordem curada."""
    chave = (idioma, pagina)
    if chave in _cache:
        return _cache[chave]
    caminho = os.path.join(RAIZ, idioma, pagina) if idioma else os.path.join(RAIZ, pagina)
    achadas = []
    if os.path.exists(caminho):
        html = io.open(caminho, encoding="utf-8").read()
        mapa = NAV_SECOES if not idioma else NAV_SECOES_TRADUCOES
        for ancora, rotulo_curado in mapa.get(pagina, []):
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
            titulo = re.sub(r"^[^\w\u00c0-\u017f(]+", "", titulo).strip()
            if titulo:
                achadas.append((ancora, titulo))
    _cache[chave] = achadas
    return achadas


def escapar(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def coluna(rot_pagina, href, idioma, pagina_ativa, primeira_e_visao_geral):
    linhas = ['        <div class="nav-drop-col">']
    cls = ["nav-drop-pagina"]
    if primeira_e_visao_geral:
        cls.append("nav-drop-visao-geral")
    if href == pagina_ativa:
        cls.append("ativo")
    linhas.append('          <a class="%s" role="menuitem" href="%s">%s</a>'
                  % (" ".join(cls), href, rot_pagina))
    for ancora, titulo in secoes_da_pagina(idioma, href):
        linhas.append('          <a class="nav-drop-secao" role="menuitem" href="%s#%s">%s</a>'
                      % (href, ancora, escapar(titulo)))
    linhas.append("        </div>")
    return linhas


def bloco_menu(rotulo, href_rotulo, filhos, idioma, pagina_ativa):
    no_grupo = pagina_ativa == href_rotulo or any(h == pagina_ativa for _, h in filhos)
    cls_drop = "nav-drop nav-drop-mega"
    linhas = [
        '        <span class="nav-menu">',
        '          <a class="nav-familia-rotulo%s" href="%s">%s</a>'
        % (" ativo" if no_grupo else "", href_rotulo, rotulo),
        '          <div class="%s" role="menu">' % cls_drop,
    ]
    for i, (rot, href) in enumerate(filhos):
        linhas += ["  " + l for l in coluna(
            rot, href, idioma, pagina_ativa, i == 0 and href == href_rotulo)]
    linhas += ["          </div>", "        </span>"]
    return "\n".join(linhas)


def montar(idioma, pagina):
    cfg = IDIOMAS[idioma]
    out = ['<nav class="nav-links">']
    for rotulo, href, filhos in cfg["familias"]:
        out.append('      <span class="nav-familia">')
        out.append(bloco_menu(rotulo, href, filhos, idioma, pagina))
        out.append("      </span>")
    out.append('      <span class="nav-familia">')
    rot, href, filhos = cfg["tecnico"]
    out.append(bloco_menu(rot, href, filhos, idioma, pagina))
    for rotulo, h in cfg["soltos"]:
        cls = ' class="ativo"' if h == pagina else ""
        out.append('        <a%s href="%s">%s</a>' % (cls, h, rotulo))
    out.append("      </span>")
    out.append("    </nav>")
    return "\n".join(out)


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
    if de_idioma == para_idioma:
        return pagina
    subir = "../" if de_idioma else ""
    return subir + (para_idioma + "/" if para_idioma else "") + pagina


def existe(idioma, pagina):
    return os.path.exists(os.path.join(RAIZ, idioma, pagina) if idioma else os.path.join(RAIZ, pagina))


def bloco_idiomas(idioma, pagina):
    # Pill e hreflang so para traducao que EXISTE. Desde 06/10/2026 ha paginas
    # so em pt-BR (como-funciona-clinico, data-froid, menu, faq-nr1,
    # glossario-nr1, seguranca-nr1); uma pill para en/ delas daria 404.
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
    if pagina == "index.html":
        return SITE + (idioma + "/" if idioma else "")
    return SITE + (idioma + "/" if idioma else "") + pagina


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
    if 'name="robots" content="noindex"' in texto:
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


CONFERIR = "--conferir" in sys.argv

trocadas = 0
arquivos = 0
divergentes = []
for idioma in IDIOMAS:
    d = os.path.join(RAIZ, idioma) if idioma else RAIZ
    for nome in sorted(os.listdir(d)):
        if not nome.endswith(".html"):
            continue
        caminho = os.path.join(d, nome)
        if not os.path.isfile(caminho):
            continue
        arquivos += 1
        texto = io.open(caminho, encoding="utf-8").read()
        novo = texto
        if NAV.search(novo):
            novo = NAV.sub(lambda _m: montar(idioma, nome), novo, count=1)
        if LANG_GROUP.search(novo):
            novo = LANG_GROUP.sub(lambda _m: bloco_idiomas(idioma, nome), novo, count=1)
        novo = aplicar_hreflang(novo, nome)
        if novo == texto:
            continue
        if CONFERIR:
            divergentes.append(os.path.join(idioma, nome))
        else:
            io.open(caminho, "w", encoding="utf-8", newline="").write(novo)
            trocadas += 1

if CONFERIR:
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

# Ancora curada que existe no arquivo mas nao virou item de menu: some sem erro
# nenhum se ninguem contar. Aqui ela e listada.
print()
perdidas = []
for idioma in IDIOMAS:
    cfg = IDIOMAS[idioma]
    for _rot, _h, filhos in cfg["familias"] + [cfg["tecnico"]]:
        for _r, href in filhos:
            caminho = os.path.join(RAIZ, idioma, href) if idioma else os.path.join(RAIZ, href)
            if not os.path.exists(caminho):
                continue
            html = io.open(caminho, encoding="utf-8").read()
            ids = set(re.findall(r'\sid="([^"]+)"', html))
            no_menu = {a for a, _t in secoes_da_pagina(idioma, href)}
            for a, _rot in (NAV_SECOES if not idioma else NAV_SECOES_TRADUCOES).get(href, []):
                if a in ids and a not in no_menu:
                    perdidas.append("%s/%s#%s" % (idioma or "pt", href, a))
if perdidas:
    print("ANCORAS QUE EXISTEM E NAO ENTRARAM NO MENU (sem titulo extraivel):")
    for p in perdidas:
        print("   ", p)
else:
    print("nenhuma ancora existente ficou de fora do menu")

print()
print("secoes por coluna, por idioma:")
for idioma in IDIOMAS:
    cfg = IDIOMAS[idioma]
    grupos = cfg["familias"] + [cfg["tecnico"]]
    for rotulo, _h, filhos in grupos:
        alturas = [1 + len(secoes_da_pagina(idioma, h)) for _r, h in filhos]
        print("  %-3s %-22s colunas=%d  altura maxima=%2d linhas  %s"
              % (idioma or "pt", TAG.sub("", rotulo)[:22], len(filhos),
                 max(alturas), alturas))
