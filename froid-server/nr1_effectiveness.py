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
from math import sqrt
from typing import Dict, Iterable, List, Optional, Tuple

from nr1_compliance import MIN_COHORT_CUT, DimensionScore, exposure_position


# Standardised mean difference bands. Cohen's conventions, used here as the
# documented threshold for calling a change real — it belongs in the
# organization's critérios do GRO alongside the gradation scales.
EFFECT_TRIVIAL = 0.20
EFFECT_MODERATE = 0.50
EFFECT_LARGE = 0.80

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


def effect_size(baseline: DimensionScore, followup: DimensionScore) -> float:
    """Standardised improvement. Positive is better, negative is worse."""
    spread = pooled_stddev(baseline, followup)
    delta = improvement_delta(baseline, followup)
    if spread == 0.0:
        # No dispersion recorded: fall back on the normalised exposure, which is
        # always available, rather than claiming an infinite effect.
        return exposure_position(baseline) - exposure_position(followup)
    return delta / spread


def compare(
    baseline: DimensionScore, followup: DimensionScore
) -> EffectivenessVerdict:
    """Judge one dimension of one unit across two cycles."""
    if baseline.dimension_id != followup.dimension_id:
        raise ValueError("effectiveness compares the same dimension over time")
    if baseline.unit_id != followup.unit_id:
        raise ValueError("effectiveness compares the same unit over time")

    position_before = exposure_position(baseline)
    position_after = exposure_position(followup)

    # Both ends must clear the k floor. A follow-up with fewer respondents than
    # the floor is not a smaller sample, it is a suppressed one.
    if min(baseline.cohort_size, followup.cohort_size) < MIN_COHORT_CUT:
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
            verdict="inconclusive",
            measure_efficacy=VERDICT_TO_EFFICACY["inconclusive"],
            requires_correction=False,
            triggers_review=False,
            rationale=(
                "Comparacao nao realizada: uma das coortes ficou abaixo do piso "
                f"de {MIN_COHORT_CUT} respostas. Sem coorte suficiente nao se "
                "afirma eficacia."
            ),
        )

    effect = effect_size(baseline, followup)

    if effect >= EFFECT_LARGE and position_after == 0.0:
        verdict = "eliminated"
    elif effect >= EFFECT_MODERATE:
        verdict = "effective"
    elif effect >= EFFECT_TRIVIAL:
        verdict = "partial"
    elif effect > -EFFECT_TRIVIAL:
        verdict = "no_change"
    else:
        verdict = "worsened"

    requires_correction = verdict in ("no_change", "worsened")
    rationale = (
        f"Linha de base n={baseline.cohort_size}, media {baseline.mean_score:.2f} "
        f"({position_before * 100:.0f}% de exposicao). Reavaliacao "
        f"n={followup.cohort_size}, media {followup.mean_score:.2f} "
        f"({position_after * 100:.0f}%). Diferenca padronizada d={effect:+.2f}. "
        f"Veredito: {verdict}."
    )
    if requires_correction:
        rationale += (
            " A medida nao demonstrou eficacia e deve ser corrigida "
            "(NR-1 1.5.5.3.2.1); a avaliacao de riscos deve ser revista "
            "(1.5.4.4.6 'c')."
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
        verdict=verdict,
        measure_efficacy=VERDICT_TO_EFFICACY[verdict],
        requires_correction=requires_correction,
        triggers_review=requires_correction,
        rationale=rationale,
    )


def _key(score: DimensionScore) -> Tuple[Optional[str], str]:
    return (score.unit_id, score.dimension_id)


def compare_campaigns(
    baseline_scores: Iterable[DimensionScore],
    followup_scores: Iterable[DimensionScore],
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
        verdicts.append(compare(baseline, followup))
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
