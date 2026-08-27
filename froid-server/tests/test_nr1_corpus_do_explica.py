# -*- coding: utf-8 -*-
"""O corpus do FROID Explica e o quinto espelho dos pisos, e ninguem o vigiava.

Os pisos do NR-1 ja eram espelhados em quatro lugares — SQL, `nr1_compliance`,
a calculadora publica, o espelho TypeScript do painel — e o teste de espelhos
varre os tres ultimos atras de copia nova.

Nenhum deles varria `knowledge/approved/`. E o corpus do FROID Explica e um
espelho como qualquer outro: ele afirma numeros ao cliente. Descoberto em
27/08/2026, a nota `FROID_NR1_Riscos_Psicossociais.md` ainda dizia "a partir de
50 respostas concluidas" — piso abandonado na migration 027, tres dias antes.

O defeito e pior do que uma copia desatualizada em codigo. Numero errado em
codigo quebra alguma coisa; numero errado aqui e **respondido com confianca a
quem esta decidindo comprar**, citando a nossa propria documentacao como fonte.
E o texto sobrevive a migration em silencio, porque prosa nao compila.

Este arquivo confere o que a prosa afirma contra o que a funcao calcula.
"""

from __future__ import annotations

import io
import re
import unittest
from pathlib import Path

import sys

SERVER = Path(__file__).resolve().parents[1]
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import nr1_compliance  # noqa: E402

CORPUS = SERVER / "knowledge" / "approved" / "Notas_tecnicas_FROID"
NOTAS_NR1 = sorted(CORPUS.glob("FROID_NR1_*.md"))


def _texto(caminho: Path) -> str:
    with io.open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


class OCorpusExiste(unittest.TestCase):
    def test_ha_notas_de_nr1_para_conferir(self):
        # Sem esta checagem, apagar o corpus faria todos os testes abaixo
        # passarem por vacuidade — o modo de falha classico de teste que varre
        # arquivos.
        self.assertGreaterEqual(len(NOTAS_NR1), 4, "corpus NR-1 sumiu ou encolheu")


class OsPisosAfirmadosConferem(unittest.TestCase):
    """Prosa que cita piso tem de citar o piso que o banco aplica."""

    def test_o_piso_da_campanha_afirmado_e_o_vigente(self):
        padrao = re.compile(r"a partir de (\d+) respostas", re.IGNORECASE)
        for nota in NOTAS_NR1:
            for achado in padrao.finditer(_texto(nota)):
                with self.subTest(nota=nota.name, trecho=achado.group(0)):
                    self.assertEqual(
                        int(achado.group(1)),
                        nr1_compliance.MIN_COHORT_TOTAL,
                        f"{nota.name} afirma piso de campanha desatualizado",
                    )

    def test_o_piso_de_recorte_afirmado_e_o_vigente(self):
        padrao = re.compile(r"exige no minimo (\d+)", re.IGNORECASE)
        for nota in NOTAS_NR1:
            for achado in padrao.finditer(_texto(nota)):
                with self.subTest(nota=nota.name, trecho=achado.group(0)):
                    self.assertEqual(
                        int(achado.group(1)),
                        nr1_compliance.MIN_COHORT_CUT,
                        f"{nota.name} afirma piso de recorte desatualizado",
                    )

    def test_nenhuma_nota_ressuscita_o_piso_de_cinquenta(self):
        # Regressao direta do que foi encontrado. O numero 50 pode aparecer
        # legitimamente (efetivo de exemplo), mas nao colado a "respostas".
        proibido = re.compile(r"\b50 respostas\b", re.IGNORECASE)
        for nota in NOTAS_NR1:
            with self.subTest(nota=nota.name):
                self.assertIsNone(
                    proibido.search(_texto(nota)),
                    f"{nota.name} voltou a citar 50 respostas como piso",
                )


class ATabelaComercialConfere(unittest.TestCase):
    """A tabela de porte e o numero que vai para a proposta.

    Foi uma copia dessa tabela, num simulador, que quase pos um valor obsoleto
    numa planilha comercial. Aqui ela e conferida linha a linha contra
    `required_sample`.
    """

    NOTA = CORPUS / "FROID_NR1_Quantas_Respostas_Minha_Empresa_Precisa.md"

    def test_a_nota_de_porte_existe(self):
        self.assertTrue(self.NOTA.exists())

    def test_cada_par_efetivo_exigencia_confere(self):
        linha_de_tabela = re.compile(r"^\|\s*([\d.]+)\s*\|\s*(\d+)")
        conferidos = 0
        for linha in _texto(self.NOTA).splitlines():
            achado = linha_de_tabela.match(linha.strip())
            if not achado:
                continue
            efetivo = int(achado.group(1).replace(".", ""))
            afirmado = int(achado.group(2))
            with self.subTest(efetivo=efetivo):
                self.assertEqual(
                    afirmado,
                    nr1_compliance.required_sample(efetivo),
                    f"tabela de porte erra para efetivo {efetivo}",
                )
            conferidos += 1
        self.assertGreaterEqual(conferidos, 5, "tabela de porte sumiu da nota")

    def test_a_fronteira_do_censo_afirmada_e_a_real(self):
        # A nota diz "de 15 a 97 censo, 98 ou mais amostra". Se a margem ou o
        # corte mudarem, essa fronteira anda e a frase passa a mentir.
        texto = _texto(self.NOTA)
        ultimo_censo = max(
            n for n in range(nr1_compliance.MIN_COHORT_TOTAL, 400)
            if nr1_compliance.required_sample(n) == n
        )
        self.assertIn(str(ultimo_censo), texto)
        self.assertIn(str(ultimo_censo + 1), texto)


class OSegundoPortaoNaoSomeDoCorpus(unittest.TestCase):
    """A representatividade entrou na migration 025 e o corpus nao a mencionava.

    Um corpus que fala so do anonimato descreve o produto de antes: responde
    "quantas respostas eu preciso?" com o piso de 15 e omite a amostra, que e a
    exigencia que realmente barra empresa grande.
    """

    def test_alguma_nota_explica_a_representatividade(self):
        junto = "\n".join(_texto(nota) for nota in NOTAS_NR1).lower()
        for termo in ("representatividade", "margem de 5 pontos", "censo"):
            with self.subTest(termo=termo):
                self.assertIn(termo, junto)

    def test_alguma_nota_explica_o_recorte_declarado_insuficiente(self):
        # Migration 028. Sem isso o Explica responde que recorte reprovado
        # "e suprimido" — que era verdade ate 25/08/2026 e deixou de ser.
        junto = "\n".join(_texto(nota) for nota in NOTAS_NR1).lower()
        self.assertIn("declarada insuficiente", junto)


if __name__ == "__main__":
    unittest.main()
