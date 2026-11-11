# -*- coding: utf-8 -*-
"""Poe no site PUBLICO (froid-site) o botao de acesso ao Site II.

Pedido do dono, 11/11/2026: "e necessario instalar um botao para o acesso ao
Site II atraves da senha". O Site II e froid-site-dev, servido em /dev/ com
basic_auth no Caddy (ver o Caddyfile): o botao so leva ate la; quem pede e
confere a senha e o servidor, nunca a pagina.

    python tools/gerar-botao-site2.py            # aplica
    python tools/gerar-botao-site2.py --conferir # so acusa divergencia

Onde entra:
- paginas com header: no nav-actions, logo antes de "Entrar no FROID", fora
  do bloco do gerador do header (que reescreveria o que estivesse dentro);
- paginas de entrada (index.html de cada idioma, sem header): no rodape.

Cada botao leva a MESMA pagina dentro do Site II (/dev/<caminho>), quando ela
existe la; senao, a entrada do Site II (/dev/). Os redirecionamentos deixados
nos enderecos antigos ficam de fora.
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLICO = os.path.join(REPO, "froid-site")
DEV = os.path.join(REPO, "froid-site-dev")
STUB = "<!-- redirecionamento: pagina movida em 09/11/2026 -->"
INICIO = "<!-- site II: gerado por tools/gerar-botao-site2.py -->"
FIM = "<!-- /site II -->"
GERADO = re.compile(r"[ \t]*" + re.escape(INICIO) + r".*?" + re.escape(FIM) + r"\r?\n?", re.S)
ENTRAR = re.compile(r'[ \t]*<a class="btn btn-ghost" href="https://www\.froid\.com\.br/app/#/login"')
# A landing do Psique tem header e CSS proprios (sem .nav-troca-produto): o
# botao entra no inicio das acoes, com o mesmo visual escrito na propria tag.
ACOES_LANDING = re.compile(r'(<header class="site-header">.*?<div class="nav-actions">\r?\n)', re.S)
VISUAL = ("display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid #354052;"
          "border-radius:999px;font-size:.74rem;font-weight:700;color:#cbd5e1;text-decoration:none;"
          "white-space:nowrap")
RODAPE = re.compile(r'(<footer class="rodape">\r?\n)')

# Desde 11/11/2026 (tarde) o Site II nao tem senha: o rotulo deixou de dizer
# "acesso restrito" e o cadeado virou uma seta. Rotulo que promete uma
# restricao que nao existe engana quem le (skill-froid-master, 2.4).
ROTULO = {"": "Ir para o Site II", "en": "Go to Site II",
          "fr": "Aller au Site II", "es": "Ir al Sitio II"}
CURTO = {"": "Site II", "en": "Site II", "fr": "Site II", "es": "Sitio II"}
CADEADO = ('<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" focusable="false">'
           '<path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" fill="none" stroke="currentColor" '
           'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def destino(rel):
    if os.path.exists(os.path.join(DEV, *rel.split("/"))):
        return "/dev/" + ("" if rel == "index.html" else rel)
    return "/dev/"


def idioma(rel):
    primeiro = rel.split("/", 1)[0]
    return primeiro if primeiro in ("en", "fr", "es") else ""


def bloco_header(rel, nl, estilo="", compacto=False):
    """Compacto: paginas comuns, que ja levam as duas trocas de produto. Com o
    rotulo, o header passava a duas linhas em 1366px (medido com
    tools/checar-telas-do-site.mjs em 11/11/2026); ali fica so o cadeado, e o
    nome continua no title e no aria-label. A classe nav-troca-marca e a que
    refinement.css ja esconde dentro do nav-actions."""
    i = idioma(rel)
    atributo = ' style="%s"' % estilo if estilo else ""
    classe_rotulo = ' class="nav-troca-marca"' if compacto else ""
    return ('      %s<a class="nav-troca-produto nav-site2" href="%s" aria-label="%s" title="%s"%s>%s'
            '<span%s>%s</span></a>%s%s') % (INICIO, destino(rel), ROTULO[i], ROTULO[i], atributo,
                                            CADEADO, classe_rotulo, CURTO[i], FIM, nl)


def bloco_rodape(rel, nl):
    i = idioma(rel)
    return '  %s<a href="%s">%s</a>%s%s' % (INICIO, destino(rel), ROTULO[i], FIM, nl)


def aplicar(texto, rel):
    nl = "\r\n" if "\r\n" in texto else "\n"
    texto = GERADO.sub("", texto)
    m = ENTRAR.search(texto)
    if m:
        compacto = "nav-troca-compacta" in texto
        return texto[:m.start()] + bloco_header(rel, nl, compacto=compacto) + texto[m.start():]
    m = ACOES_LANDING.search(texto)
    if m:
        return texto[:m.end()] + bloco_header(rel, nl, VISUAL) + texto[m.end():]
    m = RODAPE.search(texto)
    if m:
        return texto[:m.end()] + bloco_rodape(rel, nl) + texto[m.end():]
    return None


def main():
    conferir = "--conferir" in sys.argv
    divergentes, sem_lugar, total = [], [], 0
    for raiz, _dirs, arquivos in os.walk(PUBLICO):
        for nome in sorted(arquivos):
            if not nome.endswith(".html"):
                continue
            caminho = os.path.join(raiz, nome)
            rel = os.path.relpath(caminho, PUBLICO).replace(os.sep, "/")
            texto = io.open(caminho, encoding="utf-8", newline="").read()
            if STUB in texto:
                continue
            novo = aplicar(texto, rel)
            if novo is None:
                sem_lugar.append(rel)
                continue
            total += 1
            if novo != texto:
                divergentes.append(rel)
                if not conferir:
                    io.open(caminho, "w", encoding="utf-8", newline="").write(novo)
    print("paginas com o botao: %d" % total)
    print(("divergem: " if conferir else "atualizadas: ") + str(len(divergentes)))
    if sem_lugar:
        print("SEM LUGAR para o botao: " + ", ".join(sem_lugar))
    return 1 if (conferir and divergentes) or sem_lugar else 0


if __name__ == "__main__":
    sys.exit(main())
