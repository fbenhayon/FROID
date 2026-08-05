"""Did the prevention measure actually work?

Subitem 1.5.4.4.5.3 makes *a eficácia das medidas de prevenção implementadas*
part of the probability itself, and 1.5.5.3.2.1 requires measures whose
monitoring shows them ineffective to be corrected. Most organizations will
assert effectiveness; almost none can demonstrate it.

This module measures it, by comparing a unit against its own earlier baseline —
the same principle the clinical product uses for a patient, applied to a sector:
never against a generic population, always against what that group looked like
before the measure was implemented.

The output feeds two places:

  * the `measure_efficacy` term of the next cycle's probability, closing the
    loop the norm describes rather than leaving it to opinion;
  * the plano de ação, where a measure that failed must be flagged for
    correction instead of quietly ageing into evidence of diligence.

A caveat that is deliberately built in: a difference smaller than the noise of
the cohort is reported as "insufficient", never as success. An improvement the
statistics cannot support is exactly what an opposing expert takes apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from typing import Dict, Iterable, List, Optional, Tuple

from nr1_compliance import (
    DEFAULT_CRITERIA,
    MIN_COHORT_CUT,
    DimensionScore,
    GradationCriteria,
    exposure_level,
    exposure_position,
)


# Standardised mean difference bands. Cohen's conventions, used here as the
# documented threshold for calling a change real — it belongs in the
# organization's critérios do GRO alongside the gradation scales.
EFFECT_TRIVIAL = 0.20
EFFECT_MODERATE = 0.50
EFFECT_LARGE = 0.80

# Um efeito só recebe direção depois de sobreviver ao ruído da própria coorte.
# 1.96 é o valor crítico de 95%.
CONFIDENCE_Z = 1.96

# Abaixo deste nível de exigência não havia medida a corrigir: o subitem
# 1.5.5.3.2.1 manda corrigir a medida cujo acompanhamento mostrou ineficácia,
# e isso pressupõe que uma medida existia. Dimensão que já estava baixa e
# continua baixa não gera obrigação nenhuma.
#
# O valor é o nível 3 da escala de cinco bandas do FROID. Numa organização que
# publicou uma matriz 3x3, o nível 3 é o TETO — e exigir o teto faria a
# obrigação de correção praticamente desaparecer para esse cliente. O piso
# passa a ser proporcional à escala em uso.
CORRECTION_EXPOSURE_FLOOR = 3
_CORRECTION_FLOOR_RATIO = CORRECTION_EXPOSURE_FLOOR / 5


def correction_floor(criteria: GradationCriteria = DEFAULT_CRITERIA) -> int:
    """Nível de exigência a partir do qual havia medida a corrigir.

    Preserva o comportamento da escala de cinco bandas e o traduz para a escala
    que a organização documentou (1.5.4.4.2.2), em vez de aplicar um número
    absoluto a uma régua diferente.
    """
    return max(1, min(criteria.probability_max, ceil(criteria.probability_max * _CORRECTION_FLOOR_RATIO)))

VERDICT_TO_EFFICACY = {
    "eliminated": "eliminated",
    "effective": "effective",
    "partial": "partial",
    "no_change": "insufficient",
    "worsened": "none",
    "inconclusive": "none",
}


@dataclass(frozen=True)
class EffectivenessVerdict:
    unit_id: Optional[str]
    dimension_id: str
    baseline_cohort: int
    followup_cohort: int
    baseline_mean: float
    followup_mean: float
    baseline_position: float
    followup_position: float
    effect_size: float
    # Margem de erro do próprio efeito, dada o tamanho das duas coortes. Um
    # efeito menor que ela não se distingue de zero.
    effect_margin: float
    significant: bool
    verdict: str
    measure_efficacy: str
    requires_correction: bool
    triggers_review: bool
    rationale: str


def pooled_stddev(
    baseline: DimensionScore, followup: DimensionScore
) -> float:
    """Pooled dispersion of the two cohorts, for a standardised difference."""
    n1 = int(baseline.cohort_size)
    n2 = int(followup.cohort_size)
    s1 = float(baseline.score_stddev)
    s2 = float(followup.score_stddev)
    if n1 + n2 - 2 <= 0:
        return 0.0
    numerator = ((n1 - 1) * (s1 ** 2)) + ((n2 - 1) * (s2 ** 2))
    return sqrt(max(0.0, numerator / (n1 + n2 - 2)))


def improvement_delta(
    baseline: DimensionScore, followup: DimensionScore
) -> float:
    """Raw change in the direction of improvement, honouring polarity.

    On a demand dimension a lower mean is better; on a resource dimension a
    higher mean is better. Positive means the work got less demanding.
    """
    if baseline.polarity == "protective":
        return float(followup.mean_score) - float(baseline.mean_score)
    return float(baseline.mean_score) - float(followup.mean_score)


def effect_size(baseline: DimensionScore, followup: DimensionScore) -> Optional[float]:
    """Standardised improvement. Positive is better, negative is worse.

    Devolve None quando não há dispersão para padronizar por.

    A versão anterior caía numa diferença de posições normalizadas, o que
    parecia prudente e não era: aquele número vive em [-1, 1] e o d de Cohen
    não, mas os dois eram comparados contra as MESMAS bandas de 0,20, 0,50 e
    0,80. Pior, `effect_margin` aplicava a ele o erro padrão do d, que só vale
    para uma diferença padronizada. O veredito passava a depender de o
    `score_stddev` ter sido gravado — um acidente de disponibilidade de dado,
    e não uma propriedade da medida adotada.

    Sem dispersão não existe efeito padronizado. O honesto é dizer isso.
    """
    spread = pooled_stddev(baseline, followup)
    if spread == 0.0:
        return None
    return improvement_delta(baseline, followup) / spread


def effect_margin(effect: float, n1: int, n2: int) -> float:
    """Margem de erro do efeito padronizado, a 95%.

    Erro padrão aproximado do d de Cohen. Sem isto, um efeito de 0,22 medido em
    22 pessoas seria anunciado como melhora — quando o ruído da própria coorte
    é maior que ele. É a diferença entre medir e adivinhar, e é exatamente o
    ponto onde uma perícia adversária desmonta um laudo.
    """
    if n1 < 2 or n2 < 2:
        return float("inf")
    variancia = ((n1 + n2) / (n1 * n2)) + ((effect ** 2) / (2 * (n1 + n2)))
    return CONFIDENCE_Z * sqrt(max(0.0, variancia))


def compare(
    baseline: DimensionScore,
    followup: DimensionScore,
    criteria: GradationCriteria = DEFAULT_CRITERIA,
) -> EffectivenessVerdict:
    """Judge one dimension of one unit across two cycles.

    `criteria` são os critérios documentados pela organização (1.5.4.4.2.2).
    Eles decidem em que escala a exigência da atividade é lida, e portanto a
    partir de que nível existia medida a corrigir.
    """
    if baseline.dimension_id != followup.dimension_id:
        raise ValueError("effectiveness compares the same dimension over time")
    if baseline.unit_id != followup.unit_id:
        raise ValueError("effectiveness compares the same unit over time")

    position_before = exposure_position(baseline)
    position_after = exposure_position(followup)

    def inconclusivo(motivo: str) -> EffectivenessVerdict:
        return EffectivenessVerdict(
            unit_id=baseline.unit_id,
            dimension_id=baseline.dimension_id,
            baseline_cohort=int(baseline.cohort_size),
            followup_cohort=int(followup.cohort_size),
            baseline_mean=float(baseline.mean_score),
            followup_mean=float(followup.mean_score),
            baseline_position=position_before,
            followup_position=position_after,
            effect_size=0.0,
            effect_margin=float("inf"),
            significant=False,
            verdict="inconclusive",
            measure_efficacy=VERDICT_TO_EFFICACY["inconclusive"],
            requires_correction=False,
            triggers_review=False,
            rationale=motivo,
        )

    # Both ends must clear the k floor. A follow-up with fewer respondents than
    # the floor is not a smaller sample, it is a suppressed one.
    if min(baseline.cohort_size, followup.cohort_size) < MIN_COHORT_CUT:
        return inconclusivo(
            "Comparacao nao realizada: uma das coortes ficou abaixo do piso "
            f"de {MIN_COHORT_CUT} respostas. Sem coorte suficiente nao se "
            "afirma eficacia."
        )

    efeito = effect_size(baseline, followup)
    if efeito is None:
        # Sem dispersao registrada nao ha como padronizar a diferenca. Inventar
        # um numero em outra escala e compara-lo com as bandas de Cohen seria
        # produzir um veredito que depende de o desvio-padrao ter sido gravado.
        return inconclusivo(
            "Comparacao nao realizada: nao ha dispersao registrada nas duas "
            "coortes, entao a diferenca nao pode ser padronizada. Sem isso nao "
            "se distingue mudanca de ruido, e nao se afirma eficacia."
        )

    effect = efeito
    margem = effect_margin(effect, baseline.cohort_size, followup.cohort_size)

    # Classifica-se pelo limite CONSERVADOR do intervalo, não pelo ponto.
    #
    # Um efeito de +0,60 com margem de 0,60 tem intervalo [0,00; 1,20]: ele
    # encosta no zero, e anunciar "medida eficaz" a partir dele é afirmar mais
    # do que o dado sustenta. O piloto produziu exatamente esse caso — uma
    # melhora de assédio que eu nunca plantei, surgida do ruído de uma coorte
    # de 22 e promovida a resultado. Só se afirma a magnitude que o intervalo
    # inteiro sustenta.
    magnitude_sustentada = abs(effect) - margem
    significativo = magnitude_sustentada >= EFFECT_TRIVIAL

    if not significativo:
        verdict = "no_change"
    elif effect < 0:
        verdict = "worsened"
    elif magnitude_sustentada >= EFFECT_LARGE and position_after == 0.0:
        verdict = "eliminated"
    elif magnitude_sustentada >= EFFECT_MODERATE:
        verdict = "effective"
    else:
        verdict = "partial"

    # Só se exige correção onde ainda há exposição a corrigir. Dimensão que já
    # estava baixa e continua baixa nunca teve medida associada, e apontá-la
    # como falha enche o plano de ação de ruído — escondendo o que importa.
    exposicao_atual = exposure_level(followup, criteria)
    piso = correction_floor(criteria)
    havia_medida = exposicao_atual >= piso
    requires_correction = verdict in ("no_change", "worsened") and havia_medida

    # A eficácia registrada precisa concordar com o parecer.
    #
    # Antes, "no_change" virava sempre "insufficient" — inclusive na dimensão
    # que nunca teve medida, cuja própria justificativa diz que não havia
    # medida associada. O inventário do ciclo seguinte lia "medida
    # insuficiente" onde o texto ao lado dizia que medida nenhuma existia.
    eficacia = VERDICT_TO_EFFICACY[verdict]
    if verdict == "no_change" and not havia_medida:
        eficacia = "none"

    rationale = (
        f"Linha de base n={baseline.cohort_size}, media {baseline.mean_score:.2f} "
        f"({position_before * 100:.0f}% de exposicao). Reavaliacao "
        f"n={followup.cohort_size}, media {followup.mean_score:.2f} "
        f"({position_after * 100:.0f}%). Diferenca padronizada d={effect:+.2f}, "
        f"margem de erro +/-{margem:.2f}, intervalo "
        f"[{effect - margem:+.2f}; {effect + margem:+.2f}]. "
        f"Exigencia da atividade na reavaliacao: nivel {exposicao_atual}. "
        f"Veredito: {verdict}."
    )
    if not significativo and abs(effect) >= EFFECT_TRIVIAL:
        rationale += (
            " O intervalo alcanca o zero: com este numero de respostas a "
            "variacao observada nao se distingue de ruido, em nenhum sentido."
        )
    if requires_correction:
        rationale += (
            " A medida nao demonstrou eficacia e deve ser corrigida "
            "(NR-1 1.5.5.3.2.1); a avaliacao de riscos deve ser revista "
            "(1.5.4.4.6 'c')."
        )
    elif verdict in ("no_change", "worsened"):
        rationale += (
            " Sem obrigacao de correcao: a exigencia da atividade permanece "
            "baixa, entao nao havia medida associada a esta dimensao."
        )

    return EffectivenessVerdict(
        unit_id=baseline.unit_id,
        dimension_id=baseline.dimension_id,
        baseline_cohort=int(baseline.cohort_size),
        followup_cohort=int(followup.cohort_size),
        baseline_mean=float(baseline.mean_score),
        followup_mean=float(followup.mean_score),
        baseline_position=position_before,
        followup_position=position_after,
        effect_size=round(effect, 3),
        effect_margin=round(margem, 3),
        significant=significativo,
        verdict=verdict,
        measure_efficacy=eficacia,
        requires_correction=requires_correction,
        triggers_review=requires_correction,
        rationale=rationale,
    )


def _key(score: DimensionScore) -> Tuple[Optional[str], str]:
    return (score.unit_id, score.dimension_id)


def compare_campaigns(
    baseline_scores: Iterable[DimensionScore],
    followup_scores: Iterable[DimensionScore],
    criteria: GradationCriteria = DEFAULT_CRITERIA,
) -> List[EffectivenessVerdict]:
    """Compare two cycles, pairing on unit and dimension.

    Pairs that exist on only one side are skipped rather than guessed: a unit
    that was not measured before has no baseline, and inventing one would be the
    opposite of what this module is for.
    """
    baseline_index: Dict[Tuple[Optional[str], str], DimensionScore] = {
        _key(score): score for score in baseline_scores
    }
    verdicts: List[EffectivenessVerdict] = []
    for followup in followup_scores:
        baseline = baseline_index.get(_key(followup))
        if baseline is None:
            continue
        verdicts.append(compare(baseline, followup, criteria))
    verdicts.sort(key=lambda item: item.effect_size)
    return verdicts


def efficacy_index(
    verdicts: Iterable[EffectivenessVerdict],
) -> Dict[Tuple[Optional[str], str], str]:
    """Lookup of measured efficacy, to feed the next cycle's probability."""
    return {
        (verdict.unit_id, verdict.dimension_id): verdict.measure_efficacy
        for verdict in verdicts
    }


def measures_requiring_correction(
    verdicts: Iterable[EffectivenessVerdict],
) -> List[EffectivenessVerdict]:
    """Measures the organization is obliged to revisit, worst first."""
    return [verdict for verdict in verdicts if verdict.requires_correction]
