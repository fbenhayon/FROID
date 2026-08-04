"""NR-1 psychosocial risk gradation for enterprise organizations.

Implements the grading the revised chapter 1.5 of NR-1 requires, following the
norm's own definition of each axis rather than a generic survey score:

  Severidade   (1.5.4.4.4)   magnitude of the possible lesão ou agravo. When a
                             perigo has more than one possible consequence, the
                             one of greatest magnitude is selected
                             (1.5.4.4.4.1). It does NOT come from how badly the
                             cohort answered.

  Probabilidade (1.5.4.4.5.3) for ergonomic factors, psychosocial included, the
                             assessment must consider *as exigências da
                             atividade de trabalho* and *a eficácia das medidas
                             de prevenção implementadas*.

The Guia MTE 2025 is explicit that the object is the work, not the person: "Não
se trata de verificar sintomas individuais ou sensação do que está ocorrendo no
trabalhador (...) mas de se verificar as condições de trabalho a que ele está
submetido." A questionnaire therefore characterises the exposure; it is never on
its own the evidence of risk management, and its results must be technically
analysed and integrated into the AEP.

Every threshold below is DATA, not code. Subitem 1.5.4.4.2.2 obliges the
organization to detail its own gradations of severity and probability, its risk
levels and its classification and decision rules in a document — and the Manual
requires the same gradations to be used across every risk type so the PGR can be
managed as one. A client whose SST consultancy works on a 3x3 matrix must be
able to keep it. DEFAULT_CRITERIA is only what a new organization starts from.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple


# Mirrors froid_nr1_min_cohort_total() / froid_nr1_min_cohort_cut() in
# migrations/010. SQL is the authority — these exist so the API can explain a
# suppression without a round trip, not to decide it.
MIN_COHORT_TOTAL = 50
MIN_COHORT_CUT = 10

VALID_POLARITIES = frozenset({"risk", "protective"})

NR1_FACTORS = (
    "work_organization",
    "workload_demand",
    "harassment_violence",
    "environment_modality",
)

RISK_LEVELS = ("low", "moderate", "high", "critical")

VALID_EFFICACY = frozenset(
    {"none", "insufficient", "partial", "effective", "eliminated"}
)


@dataclass(frozen=True)
class GradationCriteria:
    """The organization's documented criteria (1.5.4.4.2.2).

    Loaded from gro_risk_criteria. Immutable once published, so a campaign is
    always explainable by the criteria in force when it ran.
    """

    # Magnitude of each possible lesão ou agravo, on the severity scale.
    consequence_magnitudes: Mapping[str, int]
    # Thresholds that turn the 0..1 exposure into the probability scale,
    # descending, one fewer than the number of bands.
    exposure_bands: Tuple[float, ...]
    # How many probability bands each level of measure efficacy discounts.
    efficacy_reductions: Mapping[str, int]
    # Ascending product thresholds separating low/moderate/high/critical.
    risk_bands: Tuple[int, ...]
    # Weight of the depth of exposure against how widely it is reported.
    demand_weight: float = 0.60
    severity_max: int = 5
    probability_max: int = 5
    version: int = 0
    source: str = "froid-default"

    def __post_init__(self) -> None:
        if self.severity_max < 1 or self.probability_max < 1:
            raise ValueError("severity and probability scales must have at least one band")
        if len(self.exposure_bands) != self.probability_max - 1:
            raise ValueError(
                f"exposure_bands must hold {self.probability_max - 1} thresholds "
                f"for a scale of {self.probability_max}"
            )
        if list(self.exposure_bands) != sorted(self.exposure_bands, reverse=True):
            raise ValueError("exposure_bands must be listed from highest to lowest")
        if len(self.risk_bands) != len(RISK_LEVELS) - 1:
            raise ValueError(
                f"risk_bands must hold {len(RISK_LEVELS) - 1} thresholds"
            )
        if list(self.risk_bands) != sorted(self.risk_bands):
            raise ValueError("risk_bands must be listed from lowest to highest")
        if not 0.0 <= self.demand_weight <= 1.0:
            raise ValueError("demand_weight must sit between 0 and 1")
        for name, magnitude in self.consequence_magnitudes.items():
            if not 1 <= int(magnitude) <= self.severity_max:
                raise ValueError(
                    f"Magnitude of {name!r} falls outside the 1..{self.severity_max} scale"
                )
        missing = VALID_EFFICACY - set(self.efficacy_reductions)
        if missing:
            raise ValueError(f"efficacy_reductions is missing {sorted(missing)}")

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "GradationCriteria":
        """Build from a gro_risk_criteria row."""
        severity_scale = document.get("severity_scale") or {}
        probability_scale = document.get("probability_scale") or {}
        matrix = document.get("risk_matrix") or {}
        base = DEFAULT_CRITERIA
        return cls(
            consequence_magnitudes=dict(
                document.get("consequence_magnitudes")
                or base.consequence_magnitudes
            ),
            exposure_bands=tuple(
                float(value)
                for value in (
                    probability_scale.get("exposure_bands") or base.exposure_bands
                )
            ),
            efficacy_reductions=dict(
                probability_scale.get("efficacy_reductions")
                or base.efficacy_reductions
            ),
            risk_bands=tuple(
                int(value) for value in (matrix.get("bands") or base.risk_bands)
            ),
            demand_weight=float(
                probability_scale.get("demand_weight", base.demand_weight)
            ),
            severity_max=int(severity_scale.get("levels", base.severity_max)),
            probability_max=int(probability_scale.get("levels", base.probability_max)),
            version=int(document.get("version") or 0),
            source=str(document.get("source") or "organization"),
        )

    def as_document(self) -> dict:
        """Render back into the shape gro_risk_criteria stores."""
        return {
            "severity_scale": {
                "levels": self.severity_max,
                "basis": "magnitude da possivel lesao ou agravo (NR-1 1.5.4.4.4)",
            },
            "probability_scale": {
                "levels": self.probability_max,
                "basis": (
                    "exigencias da atividade de trabalho e eficacia das medidas "
                    "de prevencao implementadas (NR-1 1.5.4.4.5.3)"
                ),
                "exposure_bands": list(self.exposure_bands),
                "efficacy_reductions": dict(self.efficacy_reductions),
                "demand_weight": self.demand_weight,
            },
            "risk_matrix": {
                "type": f"{self.severity_max}x{self.probability_max}",
                "operation": "severidade x probabilidade",
                "bands": list(self.risk_bands),
                "levels": list(RISK_LEVELS),
            },
            "consequence_magnitudes": dict(self.consequence_magnitudes),
        }


# What a new organization starts from. These magnitudes and cuts are FROID's
# proposal, not the norm's — the norm requires them to be documented, and this
# is what gets written into the organization's criteria document on day one so
# it can be reviewed and changed with its SST team.
DEFAULT_CRITERIA = GradationCriteria(
    consequence_magnitudes={
        "transtorno_mental": 4,
        "dort": 3,
        "fadiga": 2,
        "doenca_cardiovascular": 5,
        "afastamento_prolongado": 4,
        "obito": 5,
    },
    exposure_bands=(0.80, 0.60, 0.40, 0.20),
    efficacy_reductions={
        "none": 0,          # nothing implemented
        "insufficient": 0,  # implemented but measured ineffective (1.5.5.3.2.1)
        "partial": 1,
        "effective": 2,
        "eliminated": 3,    # perigo evitado/eliminado at source
    },
    risk_bands=(4, 8, 15),
)


def criteria_for_scale(severity_max: int, probability_max: int) -> GradationCriteria:
    """Rescale the default onto a client's existing matrix (3x3, 4x4, ...).

    The Manual requires every risk type in a PGR to share the same gradations,
    so a client already running a 3x3 matrix for physical risks must be able to
    receive the psychosocial section on that same scale.
    """
    if severity_max < 2 or probability_max < 2:
        raise ValueError("a gradation scale needs at least two bands")
    span = 1.0 / probability_max
    bands = tuple(
        round(1.0 - (index * span), 3) for index in range(1, probability_max)
    )
    top = severity_max * probability_max
    rescaled_magnitudes = {
        name: max(1, min(severity_max, round(value * severity_max / 5)))
        for name, value in DEFAULT_CRITERIA.consequence_magnitudes.items()
    }
    return replace(
        DEFAULT_CRITERIA,
        consequence_magnitudes=rescaled_magnitudes,
        exposure_bands=bands,
        risk_bands=(
            max(2, round(top * 0.16)),
            max(3, round(top * 0.32)),
            max(4, round(top * 0.60)),
        ),
        severity_max=severity_max,
        probability_max=probability_max,
        source=f"froid-default-{severity_max}x{probability_max}",
    )


@dataclass(frozen=True)
class DimensionScore:
    """One row of froid_nr1_dimension_scores(), plus its hazard metadata.

    `mean_score` and `critical_ratio` characterise the *exposure* — how
    demanding the work is reported to be — not the health of any person.
    """

    dimension_id: str
    nr1_factor: str
    polarity: str
    cut_favorable: float
    cut_critical: float
    cohort_size: int
    mean_score: float
    critical_ratio: float
    unit_id: Optional[str] = None
    # 1.5.4.3.1 "a": the possible lesões ou agravos for this perigo.
    consequences: Tuple[str, ...] = ("transtorno_mental",)
    # 1.5.4.4.5.3: efficacy of what the organization already implemented.
    measure_efficacy: str = "none"
    # 1.5.5.2.1.1: workers possibly affected, used to raise action priority.
    exposed_workers: int = 0
    # Dispersion of the per-respondent dimension scores, needed to tell a real
    # change from noise when the next cycle is compared against this one.
    score_stddev: float = 0.0


@dataclass(frozen=True)
class GradedRisk:
    dimension_id: str
    nr1_factor: str
    unit_id: Optional[str]
    cohort_size: int
    mean_score: float
    critical_ratio: float
    exposure_level: int
    severity: int
    probability: int
    risk_level: str
    consequence: str
    consequences_considered: Tuple[str, ...]
    measure_efficacy: str
    exposed_workers: int
    criteria_version: int
    rationale: str


def exposure_position(score: DimensionScore) -> float:
    """Where the cohort sits between the favourable and the critical cut.

    Returns 0.0 at (or better than) the favourable cut and 1.0 at (or worse
    than) the critical cut, regardless of whether the dimension is worded as a
    demand or as a resource.
    """
    favorable = float(score.cut_favorable)
    critical = float(score.cut_critical)
    mean = float(score.mean_score)
    span = critical - favorable
    if span == 0:
        # Degenerate instrument definition: treat anything at or past the cut
        # as fully exposed rather than dividing by zero.
        if score.polarity == "protective":
            return 1.0 if mean <= critical else 0.0
        return 1.0 if mean >= critical else 0.0
    position = (mean - favorable) / span
    return max(0.0, min(1.0, position))


def worst_consequence(
    consequences: Sequence[str], criteria: GradationCriteria = DEFAULT_CRITERIA
) -> Tuple[str, int]:
    """Select the consequence of greatest magnitude, per 1.5.4.4.4.1."""
    known = [
        (name, int(criteria.consequence_magnitudes[name]))
        for name in consequences
        if name in criteria.consequence_magnitudes
    ]
    if not known:
        raise ValueError(
            f"No known consequence among {list(consequences)!r}; declare its "
            "magnitude in the organization's critérios do GRO first"
        )
    return max(known, key=lambda item: item[1])


def severity_from_consequences(
    consequences: Sequence[str], criteria: GradationCriteria = DEFAULT_CRITERIA
) -> int:
    """Severity is the magnitude of the worst possible agravo (1.5.4.4.4)."""
    return worst_consequence(consequences, criteria)[1]


def exposure_level(
    score: DimensionScore, criteria: GradationCriteria = DEFAULT_CRITERIA
) -> int:
    """The 'exigências da atividade de trabalho' term of 1.5.4.4.5.3.

    Combines how far the cohort sits past the favourable cut with how widely the
    demand is reported across the group. Both are properties of the work, not of
    anyone's diagnosis.
    """
    position = exposure_position(score)
    spread = max(0.0, min(1.0, float(score.critical_ratio)))
    weight = criteria.demand_weight
    combined = (position * weight) + (spread * (1.0 - weight))
    for index, threshold in enumerate(criteria.exposure_bands):
        if combined >= threshold:
            return criteria.probability_max - index
    return 1


def probability_from_exposure(
    demand_level: int,
    measure_efficacy: str,
    criteria: GradationCriteria = DEFAULT_CRITERIA,
) -> int:
    """Probability per 1.5.4.4.5.3: work demands, discounted by measure efficacy.

    'insufficient' grants no reduction by default: 1.5.5.3.2.1 requires measures
    shown to be ineffective to be corrected, so they must not lower the risk on
    paper while failing in practice.
    """
    if measure_efficacy not in criteria.efficacy_reductions:
        raise ValueError(f"Invalid measure efficacy: {measure_efficacy!r}")
    reduction = int(criteria.efficacy_reductions[measure_efficacy])
    return max(1, min(criteria.probability_max, int(demand_level) - reduction))


def risk_level(
    severity: int, probability: int, criteria: GradationCriteria = DEFAULT_CRITERIA
) -> str:
    """Severity x probability, read against the organization's own bands."""
    product = int(severity) * int(probability)
    for index in range(len(criteria.risk_bands) - 1, -1, -1):
        if product >= criteria.risk_bands[index]:
            return RISK_LEVELS[index + 1]
    return RISK_LEVELS[0]


def grade(
    score: DimensionScore, criteria: GradationCriteria = DEFAULT_CRITERIA
) -> GradedRisk:
    if score.polarity not in VALID_POLARITIES:
        raise ValueError(f"Invalid dimension polarity: {score.polarity!r}")
    if score.nr1_factor not in NR1_FACTORS:
        raise ValueError(f"Invalid NR-1 factor: {score.nr1_factor!r}")
    if score.cohort_size < MIN_COHORT_CUT:
        # Defence in depth. The SQL aggregate already suppresses this row; if a
        # caller ever hands one over anyway, refuse to grade it rather than
        # publish a cut that identifies people.
        raise ValueError(
            f"Cohort of {score.cohort_size} is below the k floor of {MIN_COHORT_CUT}"
        )

    consequence, severity = worst_consequence(score.consequences, criteria)
    demand_level = exposure_level(score, criteria)
    probability = probability_from_exposure(
        demand_level, score.measure_efficacy, criteria
    )
    level = risk_level(severity, probability, criteria)
    position = exposure_position(score)

    rationale = (
        f"Criterios v{criteria.version} ({criteria.source}), matriz "
        f"{criteria.severity_max}x{criteria.probability_max}. Coorte n={score.cohort_size}. "
        f"Exigencia da atividade nivel {demand_level} (media {score.mean_score:.2f}, "
        f"{position * 100:.0f}% do intervalo entre o corte favoravel "
        f"{score.cut_favorable:.2f} e o critico {score.cut_critical:.2f}; "
        f"{score.critical_ratio * 100:.0f}% da coorte na faixa critica). "
        f"Eficacia das medidas implementadas: {score.measure_efficacy} -> "
        f"probabilidade {probability}. Consequencia de maior magnitude: "
        f"{consequence} -> severidade {severity}. Nivel de risco: {level}."
    )
    return GradedRisk(
        dimension_id=score.dimension_id,
        nr1_factor=score.nr1_factor,
        unit_id=score.unit_id,
        cohort_size=score.cohort_size,
        mean_score=float(score.mean_score),
        critical_ratio=float(score.critical_ratio),
        exposure_level=demand_level,
        severity=severity,
        probability=probability,
        risk_level=level,
        consequence=consequence,
        consequences_considered=tuple(score.consequences),
        measure_efficacy=score.measure_efficacy,
        exposed_workers=max(0, int(score.exposed_workers)),
        criteria_version=criteria.version,
        rationale=rationale,
    )


def action_priority(risk: GradedRisk) -> Tuple[int, int, int]:
    """Ordering key for the plano de ação, worst first.

    Subitem 1.5.5.2.1.1 is explicit that the number of workers possibly affected
    must be used to raise the priority of action, so it is a ranking term and
    not merely a reported figure.
    """
    return (
        RISK_LEVELS.index(risk.risk_level),
        risk.severity * risk.probability,
        risk.exposed_workers,
    )


def grade_all(
    scores: Iterable[DimensionScore], criteria: GradationCriteria = DEFAULT_CRITERIA
) -> List[GradedRisk]:
    """Grade a campaign's aggregate, highest priority first."""
    graded = [grade(score, criteria) for score in scores]
    graded.sort(key=action_priority, reverse=True)
    return graded


def campaign_is_reportable(total_completed_responses: int) -> bool:
    """Whether a campaign has cleared the total k floor."""
    return int(total_completed_responses) >= MIN_COHORT_TOTAL


def suppression_notice(total_completed_responses: int) -> str:
    """Explain a withheld panel without leaking how close the cohort is."""
    if campaign_is_reportable(total_completed_responses):
        return ""
    return (
        "O painel agregado exige no minimo "
        f"{MIN_COHORT_TOTAL} respostas concluidas na campanha e cada recorte "
        f"por unidade exige {MIN_COHORT_CUT}. Enquanto o piso nao for atingido "
        "nenhum resultado e liberado, para que nenhum colaborador seja "
        "identificavel por eliminacao."
    )


# Order of priority for prevention measures, following item 1.4.1 "g" and
# subitem 1.5.5.1.2. EPI is absent on purpose: there is no personal protective
# equipment against how work is organized, and the Guia MTE is explicit that
# measures changing the organization of work are preferred over individual or
# behavioural ones.
MEASURE_HIERARCHY = (
    "elimination",      # evitar ou eliminar o perigo na origem
    "substitution",     # substituir a condição geradora
    "collective",       # medida de proteção coletiva / reprojeto do trabalho
    "administrative",   # medida administrativa ou de organização do trabalho
    "monitoring",       # acompanhamento planejado do desempenho
)


def suggested_measure_type(risk: GradedRisk) -> str:
    """A starting point for the action plan, never a substitute for it."""
    if risk.risk_level == "critical":
        return "elimination"
    if risk.risk_level == "high":
        return "collective"
    if risk.risk_level == "moderate":
        return "administrative"
    return "monitoring"


def action_plan_seed(graded: Sequence[GradedRisk]) -> List[dict]:
    """Draft plano de ação rows for every risk that NR-1 obliges acting on.

    Only a skeleton: 1.5.5.2.2 requires cronograma, responsáveis and formas de
    acompanhamento e aferição de resultados, and those are the organization's to
    fill in — a measure nobody owns is what an auditor treats as no measure.
    """
    seeds: List[dict] = []
    for risk in graded:
        if risk.risk_level == "low":
            continue
        seeds.append(
            {
                "dimension_id": risk.dimension_id,
                "nr1_factor": risk.nr1_factor,
                "unit_id": risk.unit_id,
                "risk_level": risk.risk_level,
                "severity": risk.severity,
                "probability": risk.probability,
                "exposed_workers": risk.exposed_workers,
                "measure_type": suggested_measure_type(risk),
                "measure": "",
                "responsible_membership_id": None,
                "due_date": None,
                "monitoring_method": "",
                "status": "planned",
            }
        )
    return seeds
