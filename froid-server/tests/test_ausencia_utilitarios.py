"""Os utilitarios que decidem, em cada campo, entre numero e ausencia.

Um teste por CONSUMIDOR do mapeamento de 04/09/2026, e nao um teste por funcao:
o que precisa continuar verdadeiro e o que cada consumidor faz com a ausencia,
nao a forma como a funcao chegou la.

Tudo aqui e puro. `duckdb` nao esta instalado na maquina de desenvolvimento e o
teste que exercita a gravacao de verdade e pulado inteiro — um teste que
dependesse dele passaria aqui sem nunca ter rodado.
"""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def _carrega_utilitarios():
    """Le as funcoes do `main.py` sem importar o modulo inteiro.

    Importar `main` levanta um servidor: exige chaves, banco e rede. As funcoes
    testadas aqui sao puras, entao o que se carrega e so o texto delas — pelo
    parser, por NOME de definicao, e nao por janela de linhas, que ja quebrou
    duas vezes nesta casa por crescimento de comentario.
    """
    import ast

    origem = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
    arvore = ast.parse(origem)
    queridas = {"_medida", "_delta", "_primeiro_presente", "_zona", "_cut_confidence", "_infer_patient_response"}
    corpo = [
        no
        for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name in queridas
    ]
    faltando = queridas - {no.name for no in corpo}
    if faltando:
        raise AssertionError("nao achei no main.py: " + ", ".join(sorted(faltando)))
    modulo = types.ModuleType("utilitarios_de_ausencia")
    modulo.__dict__["math"] = __import__("math")
    from typing import Optional

    modulo.__dict__["Optional"] = Optional
    exec(compile(ast.Module(body=corpo, type_ignores=[]), "<main.py>", "exec"), modulo.__dict__)
    return modulo


U = _carrega_utilitarios()


class MedidaDistingueAusenciaDeZero(unittest.TestCase):
    """C-raiz: e a distincao que o relatorio de 04/09/2026 perdeu."""

    def test_ausencia_vira_none(self):
        for entrada in (None, "", "abc", float("nan"), float("inf"), [], {}):
            with self.subTest(entrada=entrada):
                self.assertIsNone(U._medida(entrada))

    def test_zero_medido_continua_zero(self):
        """O ponto inteiro da regra 1.2: nao trocar uma suposicao por outra.

        Seria facil, e errado, tratar 0.0 como ausencia — um IPM real de zero
        existe, e um jitter de zero tambem. A ausencia chega como `None`, vinda
        do `averageNumeric` do navegador, e e so ela que vira NULL.
        """
        self.assertEqual(0.0, U._medida(0))
        self.assertEqual(0.0, U._medida(0.0))
        self.assertEqual(0.0, U._medida("0"))

    def test_booleano_nao_e_medida(self):
        """`float(True)` e 1.0, e um marcador booleano viraria a medida 1."""
        self.assertIsNone(U._medida(True))
        self.assertIsNone(U._medida(False))

    def test_numero_atravessa(self):
        self.assertEqual(62.5, U._medida(62.5))
        self.assertEqual(-3.25, U._medida("-3.25"))


class DeltaNaoInventaEstabilidade(unittest.TestCase):
    """C2 do mapa: os seis deltas do INSERT, o unico ponto que quebrava duro."""

    def test_operando_ausente_torna_o_delta_ausente(self):
        self.assertIsNone(U._delta(None, 10.0))
        self.assertIsNone(U._delta(10.0, None))
        self.assertIsNone(U._delta(None, None))

    def test_delta_real_e_calculado(self):
        self.assertEqual(-2.0, U._delta(8.0, 10.0))

    def test_delta_zero_e_diferente_de_delta_ausente(self):
        """`0.0` aqui afirma "nao mudou"; `None` afirma "nao da para dizer"."""
        self.assertEqual(0.0, U._delta(10.0, 10.0))
        self.assertIsNone(U._delta(None, 10.0))


class PrimeiroPresenteNaoDescartaZeroMedido(unittest.TestCase):
    """O defeito `0.0 or -120.0`, que ja pos o fundo de escala num relatorio."""

    def test_zero_medido_ganha_do_proximo(self):
        self.assertEqual(0.0, U._primeiro_presente(0.0, 7.0))

    def test_ausente_cede_ao_proximo(self):
        self.assertEqual(7.0, U._primeiro_presente(None, 7.0))
        self.assertEqual(7.0, U._primeiro_presente(None, None, 7.0))

    def test_tudo_ausente_e_ausencia(self):
        self.assertIsNone(U._primeiro_presente(None, None))
        self.assertIsNone(U._primeiro_presente())


class ZonaNuncaEZero(unittest.TestCase):
    """As zonas do FROID sao 1..12. O `GROUP BY dominant_zone` do Data-FROID
    tinha um balde "0" que era ausencia disfarcada de zona."""

    def test_ausencia_e_none(self):
        self.assertIsNone(U._zona(None))
        self.assertIsNone(U._zona(""))

    def test_zero_e_recusado(self):
        self.assertIsNone(U._zona(0))

    def test_fora_da_faixa_e_recusado(self):
        self.assertIsNone(U._zona(13))
        self.assertIsNone(U._zona(-1))

    def test_zonas_validas_atravessam(self):
        for z in range(1, 13):
            self.assertEqual(z, U._zona(z))


class ConfiancaDoCorteNaoSaiDeNada(unittest.TestCase):
    """C4 do mapa: `quality_confidence` construida sobre campos ausentes."""

    def test_corte_sem_amostra_nao_tem_confianca(self):
        self.assertIsNone(U._cut_confidence({"startSecond": 0, "endSecond": 600}))

    def test_corte_sem_fronteira_nao_tem_confianca(self):
        self.assertIsNone(U._cut_confidence({"sampleCount": 60}))

    def test_corte_medido_tem_confianca(self):
        valor = U._cut_confidence(
            {"sampleCount": 60, "startSecond": 0, "endSecond": 600, "wordsPerMinute": 80}
        )
        self.assertIsNotNone(valor)
        self.assertGreater(valor, 0.0)
        self.assertLessEqual(valor, 1.0)

    def test_sem_palavra_contada_ainda_ha_cobertura(self):
        """Ritmo de fala vem da transcricao e nao da apuracao acustica: ausente
        aqui e cobertura zero, que e medida, nao lacuna."""
        valor = U._cut_confidence({"sampleCount": 60, "startSecond": 0, "endSecond": 600})
        self.assertIsNotNone(valor)


class RespostaDoPacienteNaoAfirmaEstabilidade(unittest.TestCase):
    """C3 do mapa, e o mais grave dos silenciosos.

    Sem voz apurada, `0 - 0 = 0` caia em "estabilidade" — o rotulo mais
    tranquilizador do conjunto, gravado no acervo sobre uma sessao da qual nao
    se mediu nada.
    """

    def test_sem_referencia_a_resposta_e_nao_apurado(self):
        self.assertEqual(
            "nao_apurado",
            U._infer_patient_response({"ipmAvg": 40.0, "dissonanceCount": 2}, None, {}),
        )

    def test_com_referencia_classifica(self):
        self.assertEqual(
            "melhora_regulacao",
            U._infer_patient_response(
                {"ipmAvg": 40.0, "dissonanceCount": 1},
                {"ipmAvg": 50.0, "dissonanceCount": 3},
                {},
            ),
        )
        self.assertEqual(
            "aumento_ativacao",
            U._infer_patient_response(
                {"ipmAvg": 60.0, "dissonanceCount": 4},
                {"ipmAvg": 50.0, "dissonanceCount": 3},
                {},
            ),
        )

    def test_sem_variacao_a_resposta_e_estabilidade(self):
        self.assertEqual(
            "estabilidade",
            U._infer_patient_response(
                {"ipmAvg": 50.0, "dissonanceCount": 3},
                {"ipmAvg": 50.0, "dissonanceCount": 3},
                {},
            ),
        )


if __name__ == "__main__":
    unittest.main()
