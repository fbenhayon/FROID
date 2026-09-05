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

# A FONTE. Mudou o preco? Muda aqui, e o teste aponta cada copia que ficou para tras.
BASE_POR_UNIDADE = 500.0
FAIXAS = (15.00, 12.50, 9.30, 6.55)
LIMITES = (100, 300, 1000)

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
            r"(?:Base da plataforma, por unidade|Platform base, per site|"
            r"Base de la plataforma, por sede|Base de la plateforme, par site)"
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
        pagina = (REPO / "froid-site" / "empresas.html").read_text(encoding="utf-8")
        self.assertIn("De 1 a 100 trabalhadores", pagina)
        self.assertIn("De 101 a 300", pagina)
        self.assertIn("De 301 a 1.000", pagina)
        self.assertIn("Acima de 1.000", pagina)


if __name__ == "__main__":
    unittest.main()
