"""O piso repetido em PROSA, que o teste de espelhos nao alcanca.

`test_nr1_espelhos_do_portao` procura copias escritas como CODIGO —
`PISO_CAMPANHA = 50`. Encontrou tres e as amarrou. Nao encontrou, e nao tinha
como encontrar, as copias escritas em portugues nas paginas comerciais:

    "anonimato (50 respostas na campanha, 10 por recorte)"
    "o de anonimato exige 50 respostas"
    "a partir de <strong>50 respostas concluidas</strong>"

Descoberto em 25/08/2026, montando a proposta do primeiro cliente. A migration
027 baixou MIN_COHORT_TOTAL de 50 para 15 no dia 24/08; `empresas.html` e
`proposta-nr1.html` continuaram afirmando 50 para o publico. O commit anterior
tinha ate um teste declarando "todo espelho conhecido esta coberto por este
arquivo" — e estava, para a definicao de espelho que ele usava.

**Por que isto e pior do que uma copia de codigo divergente.** Copia de codigo
errada produz numero errado na tela, e alguem estranha. Prosa errada vira
argumento de venda: a frase "abaixo de ~210 trabalhadores a campanha nao produz
resultado liberavel" fechava a porta para toda a faixa de 15 a 210 — empresas
que hoje entram por censo. O documento nao mostra defeito nenhum; ele so
descreve um produto pior do que o que existe, e a venda que ele perde nao
aparece em lugar nenhum.

**O recorte deste teste.** Nao proibe o numero 50 nas paginas — o diagnostico
usa "uma empresa de 3.000 pessoas com 50 respostas" como exemplo aritmetico
legitimo, e proibir o algarismo transformaria o teste em ruido. O que ele
verifica sao as FORMAS DE AFIRMACAO do piso: quando a pagina diz que o piso e
N, N tem de ser MIN_COHORT_TOTAL.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

REPO = SERVER_DIR.parent
SITE = REPO / "froid-site"

from nr1_compliance import MIN_COHORT_CUT, MIN_COHORT_TOTAL  # noqa: E402

# Cada padrao captura o numero que a frase AFIRMA ser o piso da campanha.
# Escritos contra as frases reais que estavam erradas, para que o teste falhe
# se elas voltarem — e nao contra uma ideia geral de como alguem escreveria.
AFIRMACOES_DO_PISO_DE_CAMPANHA = (
    r"anonimato\s*\(\s*(\d+)\s*respostas\s+na\s+campanha",
    r"anonimato\s+exige\s+(\d+)\s+respostas",
    r"a\s+partir\s+de\s+<strong>\s*(\d+)\s+respostas\s+conclu",
    r"piso\s+de\s+(\d+)\s+respostas",
    r"(\d+)\s+respostas\s+por\s+campanha",
)

AFIRMACOES_DO_PISO_DE_RECORTE = (
    r"(\d+)\s+por\s+recorte",
    r"recorte\s+por\s+unidade\s+exige\s+no\s+m[ií]nimo\s*<strong>\s*(\d+)",
)


def _paginas():
    return sorted(SITE.rglob("*.html"))


class OPisoAfirmadoEmProsa(unittest.TestCase):
    """Quando a pagina publica DIZ qual e o piso, ela tem de dizer o certo."""

    def test_nenhuma_pagina_afirma_piso_de_campanha_errado(self):
        divergentes = []
        for pagina in _paginas():
            texto = pagina.read_text(encoding="utf-8", errors="ignore")
            for padrao in AFIRMACOES_DO_PISO_DE_CAMPANHA:
                for achado in re.finditer(padrao, texto, re.IGNORECASE):
                    valor = int(achado.group(1))
                    if valor != MIN_COHORT_TOTAL:
                        divergentes.append(
                            f"{pagina.name}: afirma piso de campanha = {valor} "
                            f"(vale {MIN_COHORT_TOTAL}) em {achado.group(0)!r}"
                        )
        self.assertEqual(divergentes, [], "\n".join(divergentes))

    def test_nenhuma_pagina_afirma_piso_de_recorte_errado(self):
        divergentes = []
        for pagina in _paginas():
            texto = pagina.read_text(encoding="utf-8", errors="ignore")
            for padrao in AFIRMACOES_DO_PISO_DE_RECORTE:
                for achado in re.finditer(padrao, texto, re.IGNORECASE):
                    valor = int(achado.group(1))
                    if valor != MIN_COHORT_CUT:
                        divergentes.append(
                            f"{pagina.name}: afirma piso de recorte = {valor} "
                            f"(vale {MIN_COHORT_CUT}) em {achado.group(0)!r}"
                        )
        self.assertEqual(divergentes, [], "\n".join(divergentes))

    def test_a_varredura_realmente_pega_o_defeito_que_a_motivou(self):
        """Verificador que nao acusa nada nunca e verificador que funciona."""
        defeito = (
            "<p>Sao dois pisos e ambos valem sempre: "
            "anonimato (50 respostas na campanha, 10 por recorte).</p>"
        )
        achou = False
        for padrao in AFIRMACOES_DO_PISO_DE_CAMPANHA:
            encontrado = re.search(padrao, defeito, re.IGNORECASE)
            if encontrado and int(encontrado.group(1)) != MIN_COHORT_TOTAL:
                achou = True
        self.assertTrue(achou, "a varredura deixaria passar a frase que estava no ar")

    def test_a_varredura_nao_acusa_exemplo_aritmetico_legitimo(self):
        """Falso positivo custa mais caro que o defeito: ensina a ignorar."""
        # Frase real de diagnostico-nr1.html. Usa "50 respostas" para ilustrar
        # que anonimato preservado nao e o mesmo que representatividade — nao
        # afirma piso nenhum, e proibi-la seria proibir a explicacao.
        legitima = (
            "uma empresa de 3.000 pessoas com 50 respostas preserva o "
            "anonimato perfeitamente e mesmo assim produziria um inventario "
            "sobre 1,7% do quadro"
        )
        for padrao in AFIRMACOES_DO_PISO_DE_CAMPANHA:
            self.assertIsNone(
                re.search(padrao, legitima, re.IGNORECASE),
                f"padrao {padrao!r} acusou frase legitima",
            )


class APromessaDePorteNaoPodeFecharPorta(unittest.TestCase):
    """'~210 trabalhadores' e projecao de adesao, nao limite de porte."""

    def test_a_proposta_nao_afirma_que_abaixo_de_210_nao_ha_resultado(self):
        # A frase original dizia "Abaixo de aproximadamente 210 trabalhadores
        # (...) a campanha nao produz resultado liberavel". Falso desde a
        # migration 027: de 15 a 210 a campanha publica, em censo ou com
        # adesao proporcionalmente maior. A frase custava a faixa inteira.
        texto = (SITE / "proposta-nr1.html").read_text(encoding="utf-8")
        self.assertNotRegex(
            texto,
            r"Abaixo de aproximadamente 210 trabalhadores[^<]*n[aã]o produz resultado",
        )

    def test_a_proposta_diz_que_a_faixa_pequena_entra_por_censo(self):
        # E a frase que abre a faixa de 15 a 210 — e ela precisa vir com o
        # preco dito: nessa faixa uma unica recusa suspende o inventario.
        # Vender "agora atende empresa pequena" sem isso gera cliente
        # insatisfeito no fim da coleta.
        texto = (SITE / "proposta-nr1.html").read_text(encoding="utf-8")
        self.assertRegex(texto, r"a partir de 15 trabalhadores")
        self.assertRegex(texto, r"uma [uú]nica recusa suspende o invent[aá]rio")


if __name__ == "__main__":
    unittest.main()
