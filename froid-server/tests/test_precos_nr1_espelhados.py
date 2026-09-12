"""A tabela de precos do NR-1 tem uma fonte, e as copias sao conferidas contra ela.

O CASO QUE ISTO EXISTE PARA IMPEDIR
-----------------------------------
Em 28/08/2026 `empresas.html` dizia "piso de coorte (50 por campanha)" — valor
abandonado numa migration que o trocara por 15. A divergencia estava publicada
havia semanas, numa tabela que um auditor conferiria contra a proposta impressa,
que dizia 15.

Preco tem o mesmo formato de defeito e consequencia pior: nao quebra funcao
nenhuma, nao aparece em uso, e se manifesta na frente do cliente, no numero que
sustenta a negociacao. Ate 05/09/2026 nao havia teste nenhum sobre isso — os
valores viviam copiados em oito arquivos, em quatro idiomas, sem ninguem
comparando.

COMO ESTE TESTE FUNCIONA
------------------------
Ele nao verifica os arquivos que eu conhecia. Ele VARRE `froid-site/**/*.html` e
`docs/comercial/*.md` procurando qualquer valor por trabalhador/mes, em qualquer
idioma, e exige que cada um pertenca a tabela declarada aqui. Uma copia nova,
numa pagina que ainda nao existe, entra na varredura sozinha.

O QUE FICA DE FORA, E POR QUE
-----------------------------
`docs/comercial/2026-08-28-taticca-proposta.md` e uma proposta JA ENVIADA a um
cliente, com totais calculados sobre a tabela vigente naquela data. Reescreve-la
para "passar no teste" seria falsificar um registro comercial. Preco novo vale
para proposta nova; contrato existente e decisao do dono, nao do teste.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# A FONTE E `pricing_nr1.py`, e nao mais este arquivo.
#
# Ate 11/09/2026 o preco do NR-1 era declarado aqui, num TESTE, e copiado num
# gerador de planilha. Nenhum dos dois calculava: eram numeros digitados. Foi
# assim que tres bases diferentes chegaram a circular ao mesmo tempo para o
# mesmo componente — R$ 1.200 numa proposta enviada, R$ 500 no site e no
# simulador, R$ 200 no motor novo.
#
# Agora existe motor, e ele e a fonte. Este teste deixou de declarar preco e
# passou a CONFERIR o que esta publicado contra o que o motor calcula.
import pricing_nr1  # noqa: E402

BASE_POR_UNIDADE = pricing_nr1.reais(pricing_nr1.TABELA_VIGENTE["baseEstablishmentCents"])
FAIXAS = tuple(
    pricing_nr1.reais(f["workerPriceCents"]) for f in pricing_nr1.TABELA_VIGENTE["tiers"]
)
LIMITES = tuple(
    f["upperBound"] for f in pricing_nr1.TABELA_VIGENTE["tiers"] if f["upperBound"] is not None
)

# Registro historico: nao se reescreve documento que ja foi enviado.
FORA_DA_VARREDURA = {"2026-08-28-taticca-proposta.md"}

TRABALHADOR = r"(?:trabalhador|trabalhadores|worker|workers|trabajador|trabajadores|travailleur|travailleurs)"
# "R$ 15,00 / trabalhador / mes"  e  "15,00 R$ / travailleur / mois"
ANTES = re.compile(r"R\$\s*([\d.,]+)\s*/\s*" + TRABALHADOR, re.IGNORECASE)
DEPOIS = re.compile(r"([\d.,]+)\s*R\$\s*/\s*" + TRABALHADOR, re.IGNORECASE)


def _valor(texto: str) -> float:
    """Le um valor monetario em qualquer um dos quatro idiomas.

    Taxas por trabalhador ficam abaixo de mil, entao nao ha separador de milhar
    para desambiguar: virgula e ponto sao ambos decimais aqui.
    """
    return float(texto.replace(".", ".").replace(",", "."))


def _arquivos():
    for caminho in sorted((REPO / "froid-site").rglob("*.html")):
        yield caminho
    for caminho in sorted((REPO / "docs" / "comercial").glob("*.md")):
        if caminho.name not in FORA_DA_VARREDURA:
            yield caminho


class TodaCopiaDoPrecoConfereComAFonte(unittest.TestCase):
    def test_a_varredura_encontra_alguma_coisa(self):
        """Varredura que nao acha nada e indistinguivel de varredura limpa.

        Se as paginas de preco forem renomeadas, este teste grita em vez de
        passar vazio.
        """
        total = sum(
            len(ANTES.findall(c.read_text(encoding="utf-8")))
            + len(DEPOIS.findall(c.read_text(encoding="utf-8")))
            for c in _arquivos()
        )
        self.assertGreaterEqual(total, 8, "nenhuma tabela de preco encontrada na varredura")

    def test_nenhuma_copia_publica_diverge_da_fonte(self):
        permitidos = set(FAIXAS)
        divergentes = []
        for caminho in _arquivos():
            texto = caminho.read_text(encoding="utf-8")
            for padrao in (ANTES, DEPOIS):
                for bruto in padrao.findall(texto):
                    try:
                        valor = _valor(bruto)
                    except ValueError:
                        continue
                    if valor not in permitidos:
                        divergentes.append(
                            "%s: R$ %s por trabalhador nao esta na tabela"
                            % (caminho.relative_to(REPO).as_posix(), bruto)
                        )
        self.assertEqual(
            [],
            divergentes,
            "preco publicado diverge da fonte:\n  " + "\n  ".join(divergentes),
        )

    def test_a_base_por_unidade_e_a_mesma_em_toda_parte(self):
        """A base aparece com rotulo diferente em cada idioma; o numero, nao."""
        rotulos = re.compile(
            r"(?:Base da plataforma, por estabelecimento|Platform base, per establishment|"
            r"Base de la plataforma, por establecimiento|Base de la plateforme, par établissement)"
            r"</td><td>([^<]*)</td>"
        )
        achados, divergentes = 0, []
        for caminho in _arquivos():
            for celula in rotulos.findall(caminho.read_text(encoding="utf-8")):
                achados += 1
                numeros = re.findall(r"[\d.,\s]*\d", celula)
                if not numeros or _valor(numeros[0].replace(" ", "").strip()) != BASE_POR_UNIDADE:
                    divergentes.append(
                        "%s: base '%s'" % (caminho.relative_to(REPO).as_posix(), celula.strip())
                    )
        self.assertGreaterEqual(achados, 4, "a base nao foi encontrada nos quatro idiomas")
        self.assertEqual([], divergentes, "base divergente:\n  " + "\n  ".join(divergentes))

    def test_o_simulador_usa_a_mesma_tabela(self):
        """O `.xlsx` que vai ao cliente e gerado por este script."""
        origem = (SERVER_DIR / "tools" / "simulador_nr1.py").read_text(encoding="utf-8")
        self.assertIn("_entrada(ws, 11, 2, %d, MOEDA)" % int(BASE_POR_UNIDADE), origem)
        for linha, faixa in zip((12, 13, 14, 15), FAIXAS):
            self.assertIn(
                "_entrada(ws, %d, 2, %s, MOEDA)" % (linha, repr(round(faixa, 2)).rstrip("0").rstrip(".") if faixa != int(faixa) else "%.1f" % faixa),
                origem,
                "faixa %s ausente ou divergente no simulador" % faixa,
            )

    def test_os_limites_das_faixas_nao_mudaram_em_silencio(self):
        """Os limites decidem em que faixa cada trabalhador cai. Se um deles
        mudar sem os textos mudarem juntos, a conta publicada deixa de fechar."""
        self.assertEqual((100, 300, 1000), LIMITES)
        # O literal acima e proposital: ele afirma que os limites nao mudaram
        # em silencio. Se o motor mudar, este teste cai e obriga a atualizar os
        # textos das quatro faixas junto — que e o ponto.
        pagina = (REPO / "froid-site" / "empresas.html").read_text(encoding="utf-8")
        self.assertIn("Faixa 1 — de 1 a 100 trabalhadores", pagina)
        self.assertIn("Faixa 2 — de 101 a 300", pagina)
        self.assertIn("Faixa 3 — de 301 a 1.000", pagina)
        self.assertIn("Faixa 4 — acima de 1.000", pagina)

    def test_a_tabela_de_preco_nao_diz_unidade(self):
        """"Unidade" tinha DOIS sentidos em `empresas.html`.

        Na tabela de preco queria dizer estabelecimento; em "unidade de
        avaliacao" (atividade, posto, funcao, setor, grupo de exposicao) quer
        dizer outra coisa inteiramente — e as duas apareciam na mesma pagina.
        Duas tabelas abaixo da de preco, a pagina ja escrevia "Valor por
        estabelecimento", que e o termo do eSocial e da propria norma.

        O sentido de "unidade de avaliacao" continua valido e nao e varrido
        aqui: o que este teste proibe e a tabela de PRECO voltar a usa-lo.
        """
        pagina = (REPO / "froid-site" / "empresas.html").read_text(encoding="utf-8")
        inicio = pagina.index('id="precos-nr1"')
        fim = pagina.index('id="limites-e-responsabilidade"')
        secao = pagina[inicio:fim]
        self.assertIn("Base da plataforma, por estabelecimento", secao)
        self.assertNotIn("por unidade</td>", secao)


class OsTotaisDERIVADOSTambemConferem(unittest.TestCase):
    """A base e as faixas ja eram conferidas. Os TOTAIS nao eram.

    O CASO: em 11/09/2026 a base caiu de R$ 500 para R$ 200, e havia quatorze
    totais calculados a mao espalhados pelo material comercial — quatro linhas
    de simulacao em cada um dos quatro idiomas da proposta do site, e dez linhas
    do anexo de consulta por porte do modelo de proposta, com coluna de desconto.

    A varredura antiga passaria limpa com TODOS eles errados: ela so olhava o
    preco por trabalhador e a base. Um total desatualizado e pior que uma base
    desatualizada, porque e o numero que o cliente le primeiro e o unico que ele
    confere contra o boleto.

    As linhas aqui sao recalculadas pelo motor e procuradas no texto. Nao ha
    numero digitado neste teste.
    """

    # A simulacao publicada assume UM estabelecimento.
    PORTES_DO_SITE = (100, 300, 1000, 3000)
    PORTES_DO_ANEXO = (10, 20, 50, 97, 98, 150, 300, 500, 1000, 3000)
    IDIOMAS = {"": "pt", "en/": "en", "es/": "es", "fr/": "fr"}

    @staticmethod
    def _milhar(inteiro, sep):
        return f"{inteiro:,}".replace(",", sep)

    @classmethod
    def _moeda(cls, centavos, idioma, casas):
        inteiro, resto = divmod(centavos, 100)
        if idioma == "en":
            return "R$ " + cls._milhar(inteiro, ",") + (f".{resto:02d}" if casas else "")
        if idioma == "fr":
            return cls._milhar(inteiro, " ") + (f",{resto:02d}" if casas else "") + " R$"
        return "R$ " + cls._milhar(inteiro, ".") + (f",{resto:02d}" if casas else "")

    @staticmethod
    def _mensal(trabalhadores):
        return pricing_nr1.calculate_pricing(
            pricing_nr1.TABELA_VIGENTE, trabalhadores, 1
        )["monthlyTotalCents"]

    def test_a_simulacao_do_site_bate_com_o_motor_nos_quatro_idiomas(self):
        for prefixo, idioma in self.IDIOMAS.items():
            caminho = REPO / "froid-site" / prefixo / "proposta-nr1.html"
            texto = caminho.read_text(encoding="utf-8")
            for trabalhadores in self.PORTES_DO_SITE:
                mensal = self._mensal(trabalhadores)
                anual = mensal * 12
                esperado = (
                    f"<td>{self._moeda(mensal, idioma, 0)}</td>"
                    f"<td>{self._moeda(anual, idioma, 0)}</td>"
                    f"<td>{self._moeda(round(anual / trabalhadores), idioma, 2)}</td>"
                )
                with self.subTest(idioma=idioma or "pt", trabalhadores=trabalhadores):
                    # `assertTrue` e nao `assertIn`: o assertIn imprime o
                    # HAYSTACK, e aqui o haystack e a pagina inteira. Teste
                    # que falha despejando 40 KB nao ajuda quem vai corrigir.
                    self.assertTrue(
                        esperado in texto,
                        f"{caminho.relative_to(REPO).as_posix()}: a linha de "
                        f"{trabalhadores} trabalhadores nao bate com o motor. "
                        f"Esperado {esperado}",
                    )

    def test_o_anexo_por_porte_bate_com_o_motor(self):
        caminho = REPO / "docs" / "comercial" / "modelo-proposta-cliente-final.md"
        texto = caminho.read_text(encoding="utf-8")
        for trabalhadores in self.PORTES_DO_ANEXO:
            mensal = self._mensal(trabalhadores)
            anual = mensal * 12
            esperado = (
                f"| {self._moeda(mensal, 'pt', 2)} | {self._moeda(anual, 'pt', 2)} "
                f"| {self._moeda(round(anual * 85 / 100), 'pt', 2)} |"
            )
            with self.subTest(trabalhadores=trabalhadores):
                self.assertTrue(
                    esperado in texto,
                    f"anexo: a linha de {trabalhadores} trabalhadores nao bate "
                    f"com o motor. Esperado {esperado}",
                )

    def test_a_varredura_dos_derivados_encontra_alguma_coisa(self):
        """Varredura que nao acha nada e indistinguivel de varredura limpa."""
        achados = 0
        for prefixo in self.IDIOMAS:
            texto = (REPO / "froid-site" / prefixo / "proposta-nr1.html").read_text(
                encoding="utf-8"
            )
            achados += texto.count("<tr><td>")
        self.assertGreaterEqual(achados, 16, "as tabelas de simulacao sumiram do site")


class AConducaoEmCampoEDaContratante(unittest.TestCase):
    """O FROID nao conduz avaliacao em campo, e o material dizia o contrario.

    O CASO, 12/09/2026. O site e o modelo de proposta vendiam "Conducao da AEP
    em campo" com preco por estabelecimento — R$ 2.900, R$ 4.400 e R$ 1.600 —
    em quatro idiomas. A equipe NAO presta esse servico.

    Preco publicado de servico que nao existe e a pior especie de numero errado:
    os outros levam a cobrar a mais ou a menos, este leva o cliente a comprar o
    que ninguem vai entregar.

    Determinacao do dono: a conducao da AEP, a proposicao e a execucao das
    medidas de prevencao sao da CONTRATANTE. O FROID entrega o instrumento de
    mensuracao e de acompanhamento da eficacia, e mais nada. A razao e tecnica:
    quem conhece a atividade e a empresa, e a norma atribui a ela a decisao, a
    implementacao e a assinatura.
    """

    NEGACAO = {
        "": "não conduz avaliação em campo",
        "en/": "does not conduct field assessment",
        "es/": "no conduce evaluación en campo",
        "fr/": "ne conduit pas d'évaluation sur le terrain",
    }
    ILIMITADAS = {
        "": "Campanhas ilimitadas.",
        "en/": "Unlimited campaigns.",
        "es/": "Campañas ilimitadas.",
        "fr/": "Campagnes illimitées.",
    }
    PAGINAS = ("empresas.html", "proposta-nr1.html")

    def test_o_servico_que_nao_prestamos_saiu_do_material(self):
        """Os tres precos nao podem voltar a lugar nenhum da varredura."""
        proibidos = ("2.900", "4.400", "1.600", "2,900", "4,400", "1,600",
                     "2 900", "4 400", "1 600")
        achados = []
        for caminho in _arquivos():
            texto = caminho.read_text(encoding="utf-8")
            for valor in proibidos:
                if valor in texto:
                    achados.append(f"{caminho.relative_to(REPO).as_posix()}: {valor}")
        self.assertEqual(
            [],
            achados,
            "preco de conducao em campo de volta ao material:\n  " + "\n  ".join(achados),
        )

    def test_a_negacao_esta_nos_quatro_idiomas(self):
        """Dizer em portugues e calar nas traducoes deixa o comprador
        estrangeiro concluindo que a assinatura cobre a AEP inteira."""
        for prefixo, frase in self.NEGACAO.items():
            for pagina in self.PAGINAS:
                caminho = REPO / "froid-site" / prefixo / pagina
                with self.subTest(pagina=caminho.name, idioma=prefixo or "pt"):
                    self.assertIn(frase, caminho.read_text(encoding="utf-8"))

    def test_as_campanhas_ilimitadas_estao_declaradas(self):
        for prefixo, frase in self.ILIMITADAS.items():
            for pagina in self.PAGINAS:
                caminho = REPO / "froid-site" / prefixo / pagina
                with self.subTest(pagina=caminho.name, idioma=prefixo or "pt"):
                    self.assertIn(frase, caminho.read_text(encoding="utf-8"))

    def test_o_produto_CUMPRE_a_promessa_de_campanha_ilimitada(self):
        """A promessa publicada tem de ser verdade no codigo, e nao so no texto.

        Publicar "campanhas ilimitadas" com um teto escondido seria a mesma
        familia do preco sem fonte: afirmacao que ninguem confere. Aqui a
        afirmacao fica amarrada ao caminho que criaria a cobranca.
        """
        import ast

        main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        corpo = ""
        for no in ast.walk(ast.parse(main)):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == "create_nr1_campaign":
                corpo = ast.get_source_segment(main, no) or ""
        self.assertTrue(corpo, "create_nr1_campaign nao encontrado")
        for cobranca in ("consume_credit", "apply_credit_event", "used_sessions", "debit"):
            with self.subTest(cobranca=cobranca):
                self.assertNotIn(cobranca, corpo)

    def test_a_proposta_ja_enviada_nao_foi_reescrita(self):
        """Documento comercial enviado e registro, e nao rascunho.

        A proposta da TATICCA de 28/08/2026 carrega a conducao em campo com
        preco, porque era o que estava sendo oferecido naquela data. Reescreve-la
        para "passar no teste" falsificaria o registro — e a conversa com o
        cliente sobre o que mudou e do dono, nao do repositorio.
        """
        enviada = REPO / "docs" / "comercial" / "2026-08-28-taticca-proposta.md"
        self.assertIn("2026-08-28-taticca-proposta.md", FORA_DA_VARREDURA)
        self.assertIn("2.900", enviada.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
