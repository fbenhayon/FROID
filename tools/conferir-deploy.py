# -*- coding: utf-8 -*-
"""Responde "o que esta no ar e diferente do que esta no repositorio?".

    python tools/conferir-deploy.py                 # confere producao
    python tools/conferir-deploy.py --base URL      # confere outro ambiente

POR QUE ELE EXISTE

Em 11/09/2026 o formulario de Sobre & Contato estava quebrado em producao, nas
quatro versoes de idioma. A pagina chamava `/api/contato` e o servidor devolvia
404 — nao porque a rota estivesse errada, mas porque o BACKEND nao tinha subido.

A causa e estrutural e vai continuar existindo: os tres componentes sobem por
caminhos diferentes.

    froid-site       bind mount   -> entra com `git pull`, imediato
    froid-dashboard  imagem       -> exige `docker compose build`
    froid-server     imagem       -> exige `docker compose build`, derruba sessao

Como o site entra sozinho e o backend nao, e trivial publicar uma pagina que
chama uma rota que ainda nao existe do outro lado. Nada acusa: nao ha erro de
build, nao ha teste vermelho, nao ha linha de log. O visitante e que descobre.

O `DEPLOY_LOG.md` deveria responder isso e parou em 03/06/2026, descrevendo um
`uvicorn --reload` num IP e porta que nao existem mais. Log escrito a mao
envelhece, e log de implantacao velho nao e registro incompleto: e registro que
MENTE, porque quem o le conclui que aquilo esta no ar.

Este script nao anota nada. Ele PERGUNTA ao servidor, por HTTP publico — sem
SSH, porque a chave da sessao de trabalho nao esta autorizada no servidor e uma
ferramenta que exigisse acesso de shell simplesmente nao seria rodada.

O QUE ELE NAO FAZ

Nao compara commit: o servidor nao publica o SHA que esta rodando. Ele compara
COMPORTAMENTO e CONTEUDO — a rota responde, o arquivo servido bate com o do
disco, as frases do painel sao as mesmas. Onde nao consegue apurar, diz que nao
conseguiu, em vez de assumir que esta tudo bem.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "froid-site"
PAINEL_DIST = REPO / "froid-dashboard" / "dist"
MAIN = REPO / "froid-server" / "main.py"

BASE_PADRAO = "https://froid.com.br"
TEMPO_LIMITE = 25

VERDE, VERMELHO, AMARELO, CINZA, FIM = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


class Resultado:
    """Acumula achados e decide o codigo de saida.

    `indefinido` existe para separar "conferi e esta certo" de "nao consegui
    conferir". Somar os dois num unico "ok" seria a mesma mentira do log antigo.
    """

    def __init__(self) -> None:
        self.divergencias: list[str] = []
        self.indefinidos: list[str] = []

    def ok(self, texto: str) -> None:
        print(f"  {VERDE}OK{FIM}    {texto}")

    def falha(self, texto: str, correcao: str = "") -> None:
        print(f"  {VERMELHO}DIVERGE{FIM} {texto}")
        self.divergencias.append(texto + (f"\n        -> {correcao}" if correcao else ""))

    def indefinido(self, texto: str) -> None:
        print(f"  {AMARELO}?{FIM}     {texto}")
        self.indefinidos.append(texto)


def _buscar(url: str, metodo: str = "GET", corpo: bytes | None = None):
    """Devolve (status, bytes). Nunca levanta: falha de rede tambem e resposta."""
    requisicao = urllib.request.Request(url, data=corpo, method=metodo)
    if corpo is not None:
        requisicao.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            return resposta.status, resposta.read()
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read()
    except Exception as erro:  # rede, DNS, TLS
        return None, str(erro).encode("utf-8")


def _rotas_do_backend() -> set:
    texto = MAIN.read_text(encoding="utf-8")
    return {
        achado.group(2)
        for achado in re.finditer(
            r'@app\.(get|post|patch|put|delete|websocket)\("([^"]+)"', texto
        )
    }


def _rotas_que_o_site_chama() -> dict:
    """Cada `/api/...` citado pelo site publico, e onde aparece."""
    chamadas: dict = {}
    if not SITE.exists():
        return chamadas
    for caminho in SITE.rglob("*"):
        if not caminho.is_file() or caminho.suffix not in {".html", ".js"}:
            continue
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        for rota in re.findall(r"[\"'](/api/[A-Za-z0-9/_-]+)[\"']", texto):
            chamadas.setdefault(rota, set()).add(caminho.name)
    return chamadas


def conferir_backend(base: str, r: Resultado) -> None:
    print(f"\n{CINZA}BACKEND{FIM}")
    status, corpo = _buscar(f"{base}/health")
    if status != 200:
        r.falha(f"/health respondeu {status}", "o backend pode estar fora do ar")
        return
    try:
        saude = json.loads(corpo.decode("utf-8"))
    except Exception:
        r.indefinido("/health respondeu 200 mas o corpo nao e JSON")
        return
    r.ok(f"/health responde ({saude.get('status')})")

    persistencia = saude.get("persistence") or {}
    if persistencia.get("last_error"):
        r.falha(f"espelho PostgreSQL com erro: {persistencia['last_error']}")
    elif persistencia.get("schema_ready"):
        r.ok(f"espelho PostgreSQL sincronizado ({persistencia.get('last_sync_at')})")
    elif persistencia.get("postgres_mirror_enabled") and not persistencia.get("last_sync_at"):
        # NAO E INCIDENTE, e dizer so "sem schema pronto" assustava a cada deploy.
        #
        # `ensure_schema()` roda na PRIMEIRA operacao de tenant, e nao no start
        # do conteiner. Logo depois de subir o backend o espelho fica assim:
        # habilitado, sem erro, sem sincronizacao ainda. Vira pronto no primeiro
        # login. Sem esta distincao o comando gritaria em toda publicacao, e
        # alarme que sempre toca deixa de ser lido.
        r.ok(
            "espelho PostgreSQL habilitado e sem erro; schema inicializa na "
            "primeira operacao de tenant (normal logo apos reiniciar o backend)"
        )
    else:
        r.indefinido(
            f"espelho PostgreSQL sem schema pronto e sem erro declarado "
            f"(mirror={persistencia.get('postgres_mirror_enabled')}, "
            f"ultima sincronizacao={persistencia.get('last_sync_at')})"
        )

    midia = saude.get("media") or {}
    if midia.get("turn_configured") and midia.get("turn_reachable"):
        r.ok(f"TURN configurado e respondendo ({midia.get('turn_detail')})")
    elif midia.get("turn_configured"):
        r.falha("TURN configurado mas NAO responde — sessao remota cai atras de NAT")
    else:
        r.indefinido("TURN nao configurado neste ambiente")

    # A CHECAGEM DO INCIDENTE DE 11/09/2026.
    #
    # Corpo vazio de proposito: o que se pergunta e se a rota EXISTE, e nao se
    # ela aceita o payload. 404 e a resposta que denuncia o backend atrasado;
    # 400 ou 422 provam que a rota esta la e validou a entrada.
    rotas_codigo = _rotas_do_backend()
    for rota, arquivos in sorted(_rotas_que_o_site_chama().items()):
        if rota not in rotas_codigo:
            r.falha(f"{rota} e chamada por {sorted(arquivos)} e NAO existe em main.py")
            continue
        status, _ = _buscar(f"{base}{rota}", metodo="POST", corpo=b"{}")
        if status == 404:
            r.falha(
                f"{rota} existe no codigo e responde 404 no servidor",
                "backend atrasado: docker compose build froid-backend && "
                "docker compose up -d froid-backend",
            )
        elif status is None:
            r.indefinido(f"{rota} nao respondeu (rede)")
        else:
            r.ok(f"{rota} responde {status} (rota publicada)")


def conferir_site(base: str, r: Resultado) -> None:
    print(f"\n{CINZA}SITE{FIM}")
    paginas = [
        ("/", SITE / "index.html"),
        ("/sobre-contato", SITE / "sobre-contato.html"),
        ("/precos", SITE / "precos.html"),
        ("/empresas", SITE / "empresas.html"),
    ]
    for rota, arquivo in paginas:
        if not arquivo.exists():
            r.indefinido(f"{rota}: {arquivo.name} nao existe no repositorio")
            continue
        status, corpo = _buscar(f"{base}{rota}")
        if status != 200:
            r.falha(f"{rota} respondeu {status}")
            continue
        local = arquivo.read_bytes()
        if corpo == local:
            r.ok(f"{rota} identico ao repositorio ({len(local)} bytes)")
        else:
            r.falha(
                f"{rota} difere do repositorio (servido {len(corpo)}b, local {len(local)}b)",
                "site atrasado: cd ~/froid-project && git pull",
            )


def _frases_de_aplicacao(texto: str) -> set:
    """So o texto que a pessoa le.

    O resto do bundle e nome de variavel minificado, que muda entre versoes do
    empacotador sem nada ter mudado no produto. Comparar o arquivo inteiro
    acusaria diferenca em toda build e o alarme viraria ruido.
    """
    achados = re.findall(r'"([A-ZÀ-Üa-zà-ü][^"{}();=<>]{18,150})"', texto)
    return {s for s in achados if " " in s}


def conferir_painel(base: str, r: Resultado) -> None:
    print(f"\n{CINZA}PAINEL{FIM}")
    indice_local = PAINEL_DIST / "index.html"
    if not indice_local.exists():
        r.indefinido(
            "froid-dashboard/dist nao existe — rode `npm run build` antes de comparar"
        )
        return

    # BUILD LOCAL VELHO DA FALSO "OK", e esse e o pior defeito que esta
    # ferramenta poderia ter: ela compara o servidor contra o dist, e se o dist
    # tambem estiver atrasado os dois batem e o comando declara que esta tudo
    # certo sem ter conferido nada. Concordancia entre duas copias velhas nao e
    # prova de nada.
    fontes = [c for c in (REPO / "froid-dashboard" / "src").rglob("*") if c.is_file()]
    mais_nova = max((c.stat().st_mtime for c in fontes), default=0)
    if mais_nova > indice_local.stat().st_mtime:
        r.indefinido(
            "froid-dashboard/dist e mais antigo que a fonte — rode `npm run build` "
            "antes de comparar, ou a comparacao abaixo nao vale"
        )
        return

    status, corpo = _buscar(f"{base}/app/")
    if status != 200:
        r.falha(f"/app/ respondeu {status}")
        return
    servido_html = corpo.decode("utf-8", errors="ignore")
    bundle_servido = re.search(r'src="(/assets/index-[^"]+\.js)"', servido_html)
    bundle_local = re.search(
        r'src="(/?assets/index-[^"]+\.js)"', indice_local.read_text(encoding="utf-8")
    )
    if not bundle_servido or not bundle_local:
        r.indefinido("nao encontrei o bundle de entrada para comparar")
        return

    # CONFERIR SO O BUNDLE DE ENTRADA ERA UM PONTO CEGO, e ele quase me enganou.
    #
    # O painel e dividido em pedacos carregados sob demanda: cada tela vive no
    # seu. A correcao do tooltip do dossie, por exemplo, mora inteira em
    # `Nr1Dossier-*.js` e NAO toca o `index-*.js`. Comparar so a entrada
    # responderia "mesmo produto" com a tela antiga no ar — um OK que nao
    # verificou o que importava.
    #
    # Agora compara TODOS os pedacos que a entrada referencia. O casamento entre
    # servido e local e pelo nome-base antes do hash (`Nr1Dossier-` casa com
    # `Nr1Dossier-`), porque o hash e justamente o que difere.
    status, corpo_entrada = _buscar(f"{base}{bundle_servido.group(1)}")
    if status != 200:
        r.indefinido("nao consegui baixar o bundle de entrada servido")
        return
    texto_entrada = corpo_entrada.decode("utf-8", errors="ignore")

    def _base_do_chunk(nome: str) -> str:
        return re.sub(r"-[A-Za-z0-9_-]{6,}\.js$", "", nome)

    servidos = {bundle_servido.group(1).lstrip("/").split("/")[-1]}
    servidos.update(re.findall(r"[A-Za-z0-9_.-]+-[A-Za-z0-9_-]{6,}\.js", texto_entrada))
    locais = {c.name for c in (PAINEL_DIST / "assets").glob("*.js")}
    por_base_local = {_base_do_chunk(n): n for n in locais}

    conferidos = 0
    faltando_total: list[str] = []
    sem_par: list[str] = []
    for nome_servido in sorted(servidos):
        chave = _base_do_chunk(nome_servido)
        nome_local = por_base_local.get(chave)
        if not nome_local:
            sem_par.append(nome_servido)
            continue
        st, dados = _buscar(f"{base}/assets/{nome_servido}")
        if st != 200:
            sem_par.append(nome_servido)
            continue
        frases_servidas = _frases_de_aplicacao(dados.decode("utf-8", errors="ignore"))
        frases_locais = _frases_de_aplicacao(
            (PAINEL_DIST / "assets" / nome_local).read_text(encoding="utf-8")
        )
        conferidos += 1
        for frase in sorted(frases_locais - frases_servidas):
            faltando_total.append(f"{chave}: {frase[:70]}")

    if faltando_total:
        r.falha(
            f"{len(faltando_total)} frase(s) do build local NAO estao no ar "
            f"— ex.: {faltando_total[0]!r}",
            "painel atrasado: docker compose build froid-frontend && "
            "docker compose up -d froid-frontend",
        )
    else:
        r.ok(f"mesmo produto em {conferidos} pedaco(s) do painel")
    if sem_par:
        r.indefinido(
            f"{len(sem_par)} pedaco(s) servidos sem par local para comparar "
            f"— ex.: {sem_par[0]}"
        )


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--base", default=BASE_PADRAO, help="URL do ambiente")
    argumentos = analisador.parse_args()
    base = argumentos.base.rstrip("/")

    print(f"Conferindo {base} contra o repositorio em {REPO}")
    r = Resultado()
    conferir_backend(base, r)
    conferir_site(base, r)
    conferir_painel(base, r)

    print()
    if r.divergencias:
        print(f"{VERMELHO}{len(r.divergencias)} divergencia(s):{FIM}")
        for item in r.divergencias:
            print(f"  - {item}")
    if r.indefinidos:
        print(f"{AMARELO}{len(r.indefinidos)} ponto(s) sem apuracao:{FIM}")
        for item in r.indefinidos:
            print(f"  - {item}")
    if not r.divergencias and not r.indefinidos:
        print(f"{VERDE}Servidor e repositorio conferem.{FIM}")
    # Sai diferente de zero so quando ha DIVERGENCIA. Ponto sem apuracao avisa
    # e nao reprova: quebrar por indeterminacao faria o comando ser ignorado.
    return 1 if r.divergencias else 0


if __name__ == "__main__":
    sys.exit(main())
