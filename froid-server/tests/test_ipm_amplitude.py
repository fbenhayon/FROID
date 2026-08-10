"""O IPM precisa se mover, e precisa se mover na direção certa.

Duas versões travaram antes desta, cada uma numa ponta. O mapa linear prendia o
índice em [50, 100]. A sigmoide que o substituiu foi centrada em ativação = 1.0
— "cada zona desviando 100% da linha de base, em média", que é evento extremo e
não ativação típica: medido, o índice ficava entre 19 e 25 com amplitude de 1 a
9 pontos numa escala de 100.

Minha primeira correção errou pelo outro lado: padronizei pela DISPERSÃO do
repouso, que mede o tremor do sinal parado e não a faixa percorrida falando —
saturava em 100 já na fala calma.

O que ficou: razão logarítmica contra o repouso da própria sessão. Estes testes
existem para que a próxima tentativa de "melhorar" a fórmula não volte a travar
o índice sem ninguém perceber, que foi como as duas primeiras passaram.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from froid_core import SessionState  # noqa: E402


def sessao_calibrada(desvio_repouso: float = 0.15, ticks: int = 60) -> SessionState:
    estado = SessionState(session_id="teste")
    rng = np.random.default_rng(11)
    base = np.full(12, 5.0)
    for _ in range(ticks):
        voz = base * (1.0 + rng.normal(0, desvio_repouso, 12))
        estado._update_activation_reference(float(np.mean(np.abs((voz - base) / base))))
    estado.baseline_locked = True
    return estado


def ipm(estado: SessionState, ativacao: float) -> float:
    centro = estado.activation_center
    if centro <= estado.ACTIVATION_SCALE_FLOOR:
        return 50.0
    z = estado.ACTIVATION_GAIN * float(np.log(max(ativacao, 1e-6) / centro))
    return float(np.clip(100.0 / (1.0 + np.exp(-z)), 0.0, 100.0))


class ReferenciaDaSessaoTests(unittest.TestCase):
    def test_a_calibracao_aprende_o_repouso(self):
        estado = sessao_calibrada()
        self.assertGreater(estado.activation_center, 0.0)
        self.assertGreaterEqual(estado.activation_scale, estado.ACTIVATION_SCALE_FLOOR)

    def test_poucas_amostras_nao_produzem_regua(self):
        estado = SessionState(session_id="curta")
        for _ in range(estado.ACTIVATION_MIN_SAMPLES - 1):
            estado._update_activation_reference(0.12)
        self.assertEqual(estado.activation_center, 0.0)
        self.assertEqual(ipm(estado, 0.30), 50.0)

    def test_a_regua_congela_depois_da_calibracao(self):
        """Senão o índice se readapta ao próprio movimento.

        Uma ativação sustentada viraria o novo "normal", o desvio desapareceria
        e a barra voltaria a parecer inerte — pelo caminho oposto.
        """
        estado = sessao_calibrada()
        centro = estado.activation_center
        for _ in range(200):
            estado._update_activation_reference(2.0)
        self.assertAlmostEqual(estado.activation_center, centro, places=9)

    def test_ruido_na_calibracao_nao_desloca_a_regua(self):
        # Mediana e MAD, não média e desvio-padrão: um pigarro ou uma porta
        # batendo durante a calibração deslocaria a sessão inteira.
        limpa = sessao_calibrada()
        suja = sessao_calibrada()
        suja.baseline_locked = False
        suja.activation_scale = 0.0
        for _ in range(3):
            suja._update_activation_reference(9.0)
        self.assertLess(
            abs(suja.activation_center - limpa.activation_center),
            limpa.activation_center * 0.25,
        )


class AmplitudeTests(unittest.TestCase):
    def setUp(self):
        self.estado = sessao_calibrada()
        self.centro = self.estado.activation_center

    def test_o_repouso_fica_no_meio(self):
        self.assertAlmostEqual(ipm(self.estado, self.centro), 50.0, delta=1.0)

    def test_dobrar_a_ativacao_move_o_indice_de_forma_visivel(self):
        subida = ipm(self.estado, self.centro * 2) - 50.0
        self.assertGreater(subida, 12.0, "dobrar a ativação mal moveu o índice")

    def test_a_leitura_e_simetrica(self):
        # Metade da ativação precisa afastar de 50 tanto quanto o dobro.
        acima = ipm(self.estado, self.centro * 2) - 50.0
        abaixo = 50.0 - ipm(self.estado, self.centro / 2)
        self.assertAlmostEqual(acima, abaixo, delta=1.0)

    def test_a_faixa_util_e_percorrida_de_ponta_a_ponta(self):
        baixo = ipm(self.estado, self.centro / 8)
        alto = ipm(self.estado, self.centro * 8)
        self.assertLess(baixo, 15.0)
        self.assertGreater(alto, 85.0)
        self.assertGreater(alto - baixo, 70.0)

    def test_a_fala_comum_nao_encosta_no_teto(self):
        """O erro da minha primeira correção, preso como teste.

        Saturar na fala calma é tão inútil quanto ficar inerte: em ambos os
        casos o profissional olha para uma barra que não diz nada.
        """
        self.assertLess(ipm(self.estado, self.centro * 2.5), 85.0)

    def test_cresce_sempre_com_a_ativacao(self):
        anterior = -1.0
        for passo in range(1, 200):
            atual = ipm(self.estado, self.centro * passo / 20)
            self.assertGreaterEqual(atual, anterior - 1e-9)
            anterior = atual

    def test_nunca_sai_de_zero_a_cem(self):
        for ativacao in (0.0, 1e-9, 0.001, 1.0, 50.0, 1e6):
            valor = ipm(self.estado, ativacao)
            self.assertGreaterEqual(valor, 0.0)
            self.assertLessEqual(valor, 100.0)


class ComparacaoComOAnteriorTests(unittest.TestCase):
    """A fórmula antiga, medida, para o ganho ficar registrado."""

    @staticmethod
    def antigo(ativacao: float) -> float:
        return float(np.clip(100.0 / (1.0 + np.exp(-1.5 * (ativacao - 1.0))), 0.0, 100.0))

    def test_a_formula_antiga_era_de_fato_inerte_na_faixa_real(self):
        # Desvio relativo de 5% a 35% por zona cobre repouso e fala comum.
        valores = [self.antigo(a) for a in np.linspace(0.04, 0.30, 40)]
        self.assertLess(max(valores) - min(valores), 10.0)
        self.assertLess(max(valores), 30.0)

    def test_a_nova_usa_muito_mais_faixa_na_mesma_entrada(self):
        estado = sessao_calibrada()
        valores = [ipm(estado, a) for a in np.linspace(0.04, 0.30, 40)]
        self.assertGreater(max(valores) - min(valores), 40.0)


if __name__ == "__main__":
    unittest.main()
