"""Invariantes numericos da gradacao e da prova de eficacia.

Os testes existentes cobrem casos escolhidos a mao. Estes varrem o espaco de
parametros e perguntam o que o numero significa quando o dado vier estranho —
escala 2x2, coorte no piso, dispersao zero, dimensao protetora.

Foram escritos depois de uma auditoria em que a primeira versao da sonda
acusou 315 falhas em risk_level. Nao havia defeito: eu comparava rotulos em
portugues contra RISK_LEVELS, que e em ingles. Por isso os testes abaixo leem
as constantes do modulo em vez de repetir valores.
"""

import itertools
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from nr1_compliance import (  # noqa: E402
    DEFAULT_CRITERIA,
    RISK_LEVELS,
    DimensionScore,
    criteria_for_scale,
    exposure_level,
    exposure_position,
    probability_from_exposure,
    risk_level,
)
from nr1_effectiveness import (  # noqa: E402
    MIN_COHORT_CUT,
    compare,
    correction_floor,
    effect_margin,
    effect_size,
    improvement_delta,
    pooled_stddev,
)

ESCALAS = list(itertools.product(range(2, 11), range(2, 11)))


def score(mean, *, favorable=1.0, critical=5.0, ratio=0.0, n=60, sd=0.8,
          polarity="demand", efficacy="none"):
    return DimensionScore(
        dimension_id="d", nr1_factor="f", polarity=polarity,
        cut_favorable=favorable, cut_critical=critical, cohort_size=n,
        mean_score=mean, critical_ratio=ratio, score_stddev=sd,
        measure_efficacy=efficacy, exposed_workers=n,
    )


class PosicaoDeExposicaoTests(unittest.TestCase):
    def test_sempre_entre_zero_e_um(self):
        for passo in range(-40, 200):
            p = exposure_position(score(passo / 20))
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_demanda_cresce_com_a_media(self):
        anterior = -1.0
        for passo in range(0, 140):
            p = exposure_position(score(passo / 20))
            self.assertGreaterEqual(p, anterior - 1e-12)
            anterior = p

    def test_protetora_decresce_com_a_media(self):
        # A polaridade e resolvida pelos cortes invertidos, nao por um ramo no
        # codigo. Se alguem "corrigir" isso com um if, este teste cai.
        anterior = 2.0
        for passo in range(0, 140):
            p = exposure_position(
                score(passo / 20, favorable=5.0, critical=1.0, polarity="protective")
            )
            self.assertLessEqual(p, anterior + 1e-12)
            anterior = p

    def test_cortes_iguais_nao_dividem_por_zero(self):
        casos = [("demand", 3.0, 1.0), ("demand", 2.9, 0.0),
                 ("protective", 3.0, 1.0), ("protective", 3.1, 0.0)]
        for polarity, mean, esperado in casos:
            p = exposure_position(
                score(mean, favorable=3.0, critical=3.0, polarity=polarity)
            )
            self.assertEqual(p, esperado, f"{polarity} media={mean}")


class EscalaDoClienteTests(unittest.TestCase):
    """1.5.4.4.2.2: a matriz do cliente vale, e precisa continuar coerente."""

    def test_bandas_de_exposicao_bem_formadas(self):
        for smax, pmax in ESCALAS:
            c = criteria_for_scale(smax, pmax)
            self.assertEqual(len(c.exposure_bands), pmax - 1, f"{smax}x{pmax}")
            self.assertTrue(all(0.0 < b < 1.0 for b in c.exposure_bands))
            self.assertEqual(list(c.exposure_bands),
                             sorted(c.exposure_bands, reverse=True))

    def test_bandas_de_risco_crescentes_e_dentro_do_teto(self):
        for smax, pmax in ESCALAS:
            c = criteria_for_scale(smax, pmax)
            a, b, d = c.risk_bands
            self.assertLess(a, b, f"{smax}x{pmax}")
            self.assertLess(b, d, f"{smax}x{pmax}")
            self.assertLessEqual(d, smax * pmax, f"{smax}x{pmax}")

    def test_magnitudes_cabem_na_escala(self):
        for smax, pmax in ESCALAS:
            c = criteria_for_scale(smax, pmax)
            for nome, valor in c.consequence_magnitudes.items():
                self.assertGreaterEqual(valor, 1, nome)
                self.assertLessEqual(valor, smax, nome)

    def test_nenhum_nivel_de_exposicao_estoura_a_escala(self):
        for smax, pmax in ESCALAS:
            c = criteria_for_scale(smax, pmax)
            for passo in range(0, 201):
                nivel = exposure_level(
                    score(1.0 + 4.0 * passo / 200, ratio=passo / 200), c
                )
                self.assertIn(nivel, range(1, pmax + 1), f"{smax}x{pmax}")


class ProbabilidadeTests(unittest.TestCase):
    def test_medida_ineficaz_nunca_reduz_a_probabilidade(self):
        """A trava do 1.5.5.3.2.1, em toda escala.

        Se 'insufficient' passar a conceder reducao, a empresa baixa o risco no
        papel com uma medida que o acompanhamento provou nao funcionar.
        """
        for _, pmax in ESCALAS:
            c = criteria_for_scale(5, pmax)
            for nivel in range(1, pmax + 1):
                self.assertEqual(
                    probability_from_exposure(nivel, "insufficient", c),
                    probability_from_exposure(nivel, "none", c),
                    f"pmax={pmax} nivel={nivel}",
                )

    def test_eficacia_melhor_nunca_aumenta_a_probabilidade(self):
        ordem = ["none", "insufficient", "partial", "effective", "eliminated"]
        for _, pmax in ESCALAS:
            c = criteria_for_scale(5, pmax)
            for nivel in range(1, pmax + 1):
                anterior = None
                for eficacia in ordem:
                    p = probability_from_exposure(nivel, eficacia, c)
                    self.assertIn(p, range(1, pmax + 1))
                    if anterior is not None:
                        self.assertLessEqual(p, anterior, f"{nivel}/{eficacia}")
                    anterior = p


class NivelDeRiscoTests(unittest.TestCase):
    def test_cresce_nos_dois_eixos(self):
        for _, pmax in ESCALAS:
            c = criteria_for_scale(5, pmax)
            topo_por_severidade = {}
            for severidade in range(1, 6):
                anterior = -1
                for probabilidade in range(1, pmax + 1):
                    indice = RISK_LEVELS.index(
                        risk_level(severidade, probabilidade, c)
                    )
                    self.assertGreaterEqual(
                        indice, anterior,
                        f"pmax={pmax} sev={severidade} prob={probabilidade}")
                    anterior = indice
                topo_por_severidade[severidade] = anterior
            for severidade in range(2, 6):
                self.assertGreaterEqual(
                    topo_por_severidade[severidade],
                    topo_por_severidade[severidade - 1],
                    f"pmax={pmax} sev={severidade}")


class EficaciaTests(unittest.TestCase):
    def test_piso_de_correcao_cabe_na_escala(self):
        for _, pmax in ESCALAS:
            piso = correction_floor(criteria_for_scale(5, pmax))
            self.assertIn(piso, range(1, pmax + 1), f"pmax={pmax}")

    def test_desvio_combinado_fica_entre_os_dois(self):
        for sd1, sd2 in itertools.product([0.0, 0.5, 2.0], repeat=2):
            sp = pooled_stddev(score(3.0, sd=sd1), score(2.0, sd=sd2))
            self.assertGreaterEqual(sp, min(sd1, sd2) - 1e-9)
            self.assertLessEqual(sp, max(sd1, sd2) + 1e-9)

    def test_sem_dispersao_nao_ha_efeito(self):
        # Padronizar por zero produziria um numero em outra escala, comparado
        # depois contra as bandas de Cohen como se fosse a mesma coisa.
        self.assertIsNone(effect_size(score(3.0, sd=0.0), score(2.0, sd=0.0)))

    def test_efeito_e_antissimetrico(self):
        for m1, m2 in itertools.product([1.5, 2.5, 3.5], repeat=2):
            a, z = score(m1), score(m2)
            e1, e2 = effect_size(a, z), effect_size(z, a)
            self.assertAlmostEqual(e1 + e2, 0.0, places=9, msg=f"{m1},{m2}")

    def test_sinal_do_efeito_acompanha_a_melhora(self):
        for m1, m2 in itertools.product([1.5, 2.5, 3.5], repeat=2):
            a, z = score(m1), score(m2)
            e = effect_size(a, z)
            if e:
                self.assertEqual(e > 0, improvement_delta(a, z) > 0)

    def test_margem_encolhe_com_a_amostra(self):
        for efeito in [0.0, 0.3, 0.8, 1.5]:
            anterior = float("inf")
            for n in [5, 10, 30, 60, 120, 500]:
                m = effect_margin(efeito, n, n)
                self.assertGreaterEqual(m, 0.0)
                self.assertLessEqual(m, anterior + 1e-12, f"efeito={efeito} n={n}")
                anterior = m

    def test_coorte_abaixo_do_piso_nao_produz_veredito(self):
        v = compare(score(4.0, sd=1.0, n=MIN_COHORT_CUT - 1, ratio=0.6),
                    score(2.0, sd=1.0, n=MIN_COHORT_CUT - 1, ratio=0.6))
        self.assertEqual(v.verdict, "inconclusive")
        self.assertFalse(v.significant)

    def test_todos_os_vereditos_sao_alcancaveis(self):
        """Banda que nunca sai e banda que nao existe.

        'partial' quase passou por inalcancavel numa varredura minha — era a
        grade de parametros que pulava a faixa entre 0,20 e 0,50. Se um dia ela
        realmente sumir, a gradacao passa a saltar de 'insuficiente' para
        'eficaz' sem meio-termo, e ninguem percebe pelo teste de caso unico.
        """
        vistos = set()
        for delta in range(0, 300, 3):
            for n in (12, 30, 80, 400):
                for sd in (0.5, 1.0, 2.0):
                    dm = delta / 100
                    vistos.add(compare(
                        score(3.0, sd=sd, n=n, ratio=0.6),
                        score(3.0 - dm * sd, sd=sd, n=n, ratio=0.6),
                    ).verdict)
        # Piora e piso de coorte vem de configuracoes proprias.
        vistos.add(compare(score(2.0, sd=1.0, n=80, ratio=0.6),
                           score(4.0, sd=1.0, n=80, ratio=0.6)).verdict)
        vistos.add(compare(score(4.0, sd=1.0, n=5), score(2.0, sd=1.0, n=5)).verdict)
        for esperado in ("eliminated", "effective", "partial", "no_change",
                         "worsened", "inconclusive"):
            self.assertIn(esperado, vistos, f"veredito inalcancavel: {esperado}")

    def test_veredito_e_eficacia_nao_se_contradizem(self):
        for mb, mf, sd in itertools.product([2.0, 3.5, 4.5],
                                            [1.0, 2.0, 3.5, 4.5],
                                            [0.4, 1.2]):
            v = compare(score(mb, sd=sd, ratio=0.5, n=80),
                        score(mf, sd=sd, ratio=0.5, n=80))
            reducao = DEFAULT_CRITERIA.efficacy_reductions[v.measure_efficacy]
            if v.verdict == "worsened":
                self.assertEqual(reducao, 0, f"{v.verdict}/{v.measure_efficacy}")
            if v.verdict in ("effective", "eliminated"):
                self.assertGreaterEqual(reducao, 1, f"{v.verdict}/{v.measure_efficacy}")


class PrecoPorFaixaTests(unittest.TestCase):
    """A tabela comercial publicada em empresas.html e na proposta.

    O argumento de venda e "sem degraus": crescer de 300 para 301 nao muda de
    plano. Isso e uma afirmacao aritmetica, e por isso da para prender aqui.
    """

    BASE = 1200
    TETOS = (100, 300, 1000)
    PRECOS = (9.0, 7.0, 5.0, 3.0)

    def faixas(self, n):
        t1, t2, t3 = self.TETOS
        return (
            max(0, min(n, t1)),
            max(0, min(n - t1, t2 - t1)),
            max(0, min(n - t2, t3 - t2)),
            max(0, n - t3),
        )

    def mensal(self, n, unidades=1):
        return unidades * self.BASE + sum(
            q * p for q, p in zip(self.faixas(n), self.PRECOS)
        )

    def test_as_faixas_somam_o_efetivo(self):
        for n in range(0, 5001):
            self.assertEqual(sum(self.faixas(n)), n, f"n={n}")

    def test_receita_nunca_cai_e_unitario_nunca_sobe(self):
        anterior, unitario_anterior = -1.0, float("inf")
        for n in range(1, 5001):
            m = self.mensal(n)
            self.assertGreaterEqual(m, anterior - 1e-9, f"n={n}")
            unitario = m / n
            self.assertLessEqual(unitario, unitario_anterior + 1e-9, f"n={n}")
            anterior, unitario_anterior = m, unitario

    def test_nao_ha_degrau_nas_fronteiras(self):
        # Um trabalhador a mais custa o preco da faixa em que ele cai, e nada
        # alem disso. Se algum dia isso deixar de valer, a pagina de precos
        # passa a prometer o que a conta nao entrega.
        for teto, preco in zip(self.TETOS, self.PRECOS[1:]):
            salto = self.mensal(teto + 1) - self.mensal(teto)
            self.assertAlmostEqual(salto, preco, places=6, msg=f"teto={teto}")

    def test_valores_publicados_conferem(self):
        for efetivo, esperado in ((300, 3500), (1000, 7000), (3000, 13000)):
            self.assertAlmostEqual(self.mensal(efetivo), esperado, places=2)


if __name__ == "__main__":
    unittest.main()
