"""O percurso do Psique em demonstracao.html: ancoras vivas e numeros com fonte.

O CASO QUE ISTO EXISTE PARA IMPEDIR
-----------------------------------
Ate 21/09/2026 `froid-site/demonstracao.html` tinha quatro paragrafos e nao
estava no menu. Tres botoes do site levavam ate ela, um deles escrito
"Conhecer o fluxo de uma sessao" — e quem clicava caia numa pagina que nao
descrevia fluxo nenhum. Rotulo que promete o que a pagina nao entrega e o
defeito 2.4 da skill-froid-master, e neste caso o rotulo estava certo: o que
faltava era a pagina.

Ao escreve-la inteira, duas classes de defeito passaram a ser possiveis, e
nenhuma delas quebra funcao alguma — as duas se manifestam na frente de um
cliente:

1. ANCORA MORTA. A pagina tem doze secoes, o menu do header e gerado a partir
   do `NAV_SECOES` do `script.js`, e a prosa das outras paginas passou a
   apontar para etapas especificas do percurso (`demonstracao.html#durante`,
   `#liberacao`). Renomear uma secao quebra os tres de uma vez, em silencio.
   O `tools/gerar-header-do-site.py` ja confere a direcao dele — que toda
   ancora existente entre no menu. O que ninguem conferia era o contrario, e
   os links escritos a mao dentro do texto.

2. ESPELHO DE NUMERO (secao 2.7). O percurso cita tres numeros que sao
   decisao do produto e vivem no codigo do painel: a janela do corte
   automatico, o minimo do corte manual e a calibracao. O mesmo formato do
   piso de coorte que ficou publicado com o valor velho por semanas.

O QUE ESTE TESTE PODE E O QUE NAO PODE
--------------------------------------
Para os numeros, a fonte e o `LiveSession.tsx`: e la que a decisao vale. Duas
delas tem constante com nome (`TRANSCRIPT_SUMMARY_WINDOW_MS` e
`SEGUNDOS_MINIMOS_DE_CORTE`) e sao lidas pelo nome. A calibracao NAO tem: o
`60` e literal repetido em quatro pontos do arquivo, mais o relatorio, mais o
servidor, mais o site. Aqui ele e lido de `baselineStart + 60`, ancorado no
nome da variavel e nao em numero de linha. Se alguem transformar isso numa
constante nomeada — que e o certo —, este teste falha pedindo para apontar
para ela, e nao passa a fingir que conferiu.
"""

import re
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
SITE = REPO / "froid-site"
PERCURSO = SITE / "demonstracao.html"
SCRIPT_JS = SITE / "site-assets" / "script.js"
LIVE_SESSION = REPO / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"


def _ler(caminho):
    return caminho.read_text(encoding="utf-8")


def _ancoras_do_menu():
    """Os pares [ancora, rotulo] que o NAV_SECOES declara para a pagina."""
    js = _ler(SCRIPT_JS)
    bloco = js.split('"demonstracao.html": [', 1)
    if len(bloco) != 2:
        raise AssertionError(
            "NAV_SECOES nao tem mais a entrada de demonstracao.html. Se a "
            "pagina saiu do menu, este teste precisa saber disso."
        )
    # O fechamento e "\n  ]", na indentacao do mapa. Cortar no primeiro "]"
    # pararia dentro do PRIMEIRO par — a lista voltaria vazia, e um teste que
    # compara conjunto vazio com conjunto vazio passa sempre. Aconteceu aqui,
    # na primeira versao deste arquivo.
    corpo = bloco[1].split("\n  ]", 1)[0]
    pares = re.findall(r'\["([^"]+)",\s*"([^"]+)"\]', corpo)
    if not pares:
        raise AssertionError(
            "nao consegui ler os pares do NAV_SECOES; o formato do script.js "
            "mudou e este teste conferiria nada"
        )
    return pares


class AsSecoesDoPercursoEOMenuNaoDivergem(unittest.TestCase):
    """Nem ancora de menu sem secao, nem secao sem entrada no menu."""

    def setUp(self):
        self.html = _ler(PERCURSO)
        self.secoes = set(re.findall(r'<section[^>]*\sid="([^"]+)"', self.html))
        self.menu = _ancoras_do_menu()

    def test_toda_ancora_do_menu_existe_na_pagina(self):
        faltando = [a for a, _ in self.menu if a not in self.secoes]
        self.assertEqual(
            [], faltando,
            "NAV_SECOES aponta para secoes que nao existem em "
            "demonstracao.html: %s" % faltando,
        )

    def test_toda_secao_da_pagina_esta_no_menu(self):
        # O caminho inverso, que e o que some sem ninguem notar: secao nova
        # escrita na pagina e nunca acrescentada ao mapa fica inalcancavel
        # pelo header, exatamente como a pagina inteira ficou ate 21/09/2026.
        no_menu = {a for a, _ in self.menu}
        de_fora = sorted(self.secoes - no_menu)
        self.assertEqual(
            [], de_fora,
            "Secoes de demonstracao.html fora do NAV_SECOES: %s. Acrescente-as "
            "e rode tools/gerar-header-do-site.py." % de_fora,
        )

    def test_o_menu_nao_repete_ancora(self):
        vistas = [a for a, _ in self.menu]
        self.assertEqual(len(vistas), len(set(vistas)), "ancora repetida no menu")


class NenhumLinkInternoApontaParaAncoraInexistente(unittest.TestCase):
    """Varre o site inteiro, e nao a lista de paginas que eu conhecia.

    O gerador do header ja garante a sua propria direcao. Isto cobre o resto:
    os links escritos a mao dentro do texto das paginas, que foram varios
    neste trabalho, e as quatro pastas de idioma.
    """

    def test_todo_href_com_ancora_resolve(self):
        paginas = sorted(SITE.rglob("*.html"))
        ids = {
            p.resolve(): set(re.findall(r'\sid="([^"]+)"', _ler(p)))
            for p in paginas
        }
        quebrados = []
        for pagina in paginas:
            for href in re.findall(r'href="([^"]+)"', _ler(pagina)):
                if href.startswith(("http", "mailto:", "tel:", "/")):
                    continue
                arquivo, _, ancora = href.partition("#")
                if not ancora:
                    continue
                alvo = (pagina.parent / arquivo).resolve() if arquivo else pagina.resolve()
                onde = "%s -> %s" % (pagina.relative_to(REPO), href)
                if alvo not in ids:
                    quebrados.append(onde + " (arquivo inexistente)")
                elif ancora not in ids[alvo]:
                    quebrados.append(onde + " (ancora inexistente)")
        self.assertEqual([], quebrados, "links internos quebrados:\n" + "\n".join(quebrados))


class OsNumerosDoPercursoTemUmaFonte(unittest.TestCase):
    """O site nao pode contar uma historia diferente da que o painel executa."""

    def setUp(self):
        self.tsx = _ler(LIVE_SESSION)
        self.html = _ler(PERCURSO)

    def _constante(self, nome, padrao):
        achado = re.search(padrao, self.tsx)
        self.assertIsNotNone(
            achado,
            "nao achei %s em LiveSession.tsx. A fonte mudou de forma; conserte "
            "este teste em vez de deixa-lo passar sem conferir nada." % nome,
        )
        return achado

    def test_a_janela_do_corte_automatico_e_a_do_codigo(self):
        m = self._constante(
            "TRANSCRIPT_SUMMARY_WINDOW_MS",
            r"TRANSCRIPT_SUMMARY_WINDOW_MS\s*=\s*(\d+)\s*\*\s*60\s*\*\s*1000",
        )
        minutos = int(m.group(1))
        self.assertIn(
            "a cada %d minutos" % minutos, self.html,
            "demonstracao.html nao diz que o corte automatico fecha a cada %d "
            "minutos, que e o que TRANSCRIPT_SUMMARY_WINDOW_MS vale." % minutos,
        )

    def test_o_minimo_do_corte_manual_e_o_do_codigo(self):
        m = self._constante(
            "SEGUNDOS_MINIMOS_DE_CORTE",
            r"SEGUNDOS_MINIMOS_DE_CORTE\s*=\s*(\d+)",
        )
        segundos = int(m.group(1))
        self.assertIn(
            "a partir de %d segundos" % segundos, self.html,
            "demonstracao.html nao diz o minimo real do corte manual (%d s)."
            % segundos,
        )

    def test_a_calibracao_do_site_e_a_do_painel(self):
        m = self._constante("baseline do PC", r"baselineStart\s*\+\s*(\d+)")
        segundos = int(m.group(1))
        self.assertIn(
            "%d segundos de calibra" % segundos, self.html,
            "demonstracao.html descreve uma calibracao diferente da que o "
            "painel trava (%d s)." % segundos,
        )
        # A pagina de Tecnologia e dona do assunto e tem a sua propria copia.
        # As duas divergirem e o defeito 2.7 na sua forma mais barata de achar.
        tecnologia = _ler(SITE / "tecnologia.html")
        self.assertIn("%d segundos de calibra" % segundos, tecnologia)


if __name__ == "__main__":
    unittest.main()
