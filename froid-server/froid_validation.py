"""Evidence of convergent validity for the FROID signal patterns.

The question clinicians keep asking — "who validated this index?" — has only
one honest answer, and it is not a better argument. It is a number, produced
the same way every other instrument produces it: correlate the pattern against
an already validated instrument, in real patients, and publish what comes out.

Two design decisions keep this on the right side of the line.

**FROID does not administer the instrument.** The professional applies the
PHQ-9, the GAD-7 or whatever their practice already uses, and records the
score. FROID stores the score and pairs it with what it measured in the same
window. This is deliberate: a system that administered and scored a
psychometric instrument would be a psychometric instrument, which is precisely
what the product must not become. It also sidesteps reproducing copyrighted
item text.

**The expected direction is declared before the data is seen.** A study that
decides afterwards which way the correlation should point is not a study, it
is a story. Each pairing states, up front, that psychomotor slowing should rise
with depression severity — and if the data says the opposite, this module
reports evidence *against* convergence rather than quietly reframing it.

The output is never "validated". Convergent validity is accumulated, not
granted, and one correlation in one sample is one piece of evidence. What this
produces is the piece — with its sample size, its interval and its direction —
so that the claim made outside is exactly the claim the data supports.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atanh, isfinite, sqrt, tanh
from typing import Iterable, List, Optional, Sequence, Tuple


CONFIDENCE_Z = 1.96


def ethics_approval() -> str:
    """O CAAE do parecer do CEP, ou vazio enquanto nao houver.

    Pesquisa com seres humanos no Brasil exige aprovacao de Comite de Etica em
    Pesquisa antes da coleta, e dado coletado antes do parecer nao pode ser
    usado — nem no estudo, nem para publicar. O prejuizo de esquecer isso nao
    e uma multa: e descobrir, seis meses depois, que os 70 pares nao valem.

    Por isso a checagem e uma trava e nao um aviso. O modulo inteiro fica
    dormente ate que FROID_RESEARCH_CAAE exista, e a tela nao oferece o que o
    backend vai recusar.
    """
    import os

    return os.getenv("FROID_RESEARCH_CAAE", "").strip()


def collection_allowed() -> bool:
    return bool(ethics_approval())

# Below this, a correlation coefficient is an anecdote with decimals. Thirty
# pairs is the conventional floor for reporting a validity coefficient at all;
# the interval at n=30 is still wide, and the report says so rather than
# rounding the doubt away.
MIN_PAIRS = 30

# Two stages, both declared before collecting anything.
#
# Declaring them up front is not bureaucracy: it is what stops optional
# stopping. A team that checks the correlation every week and stops the day it
# looks good has not measured the pattern, it has measured its own patience.
# A *planned* interim look is a different thing entirely, and it is legitimate
# — which is why the pilot exists as a stage rather than as a temptation.
#
# The arithmetic decides what each stage can buy. With a true correlation of
# 0.50:
#
#   at n = 30 the 95% interval runs from about 0.17 to 0.73
#   at n = 70 the 95% interval runs from about 0.30 to 0.66
#
# Because the verdict is taken from the conservative end, a genuinely good
# r = 0.50 reports as "weak" at 30 and reaches "moderate" only at 70. Thirty
# pairs therefore buy a pilot: enough to see whether the direction holds and
# whether the effect is plausibly large enough to justify finishing. They do
# not buy a validity claim, and the module says so rather than letting the
# number be quoted as if they did.
PILOT_PAIRS = 30
TARGET_PAIRS = 70

# Cohen's conventions for correlation magnitude. Convergent validity is
# customarily argued from the moderate band upwards.
R_SMALL = 0.10
R_MODERATE = 0.30
R_STRONG = 0.50


@dataclass(frozen=True)
class Pairing:
    """A pattern and the instrument it is expected to converge with.

    `expected_direction` is +1 when the pattern should rise with the
    instrument score and -1 when it should fall. It is part of the hypothesis,
    not of the result, and must be set before looking at the data.
    """

    pattern_key: str
    instrument: str
    expected_direction: int

    def __post_init__(self) -> None:
        if self.expected_direction not in (1, -1):
            raise ValueError("expected_direction must be +1 or -1")


# The hypotheses, stated once and in the open. Each one is falsifiable: if the
# observed correlation contradicts the declared direction, the report says the
# evidence points against convergence.
#
# One instrument, on purpose. Two questionnaires per session is where adherence
# dies, and the way it dies is worse than the burden: the professional skips
# when the session ran long or the patient was in distress. Those sessions are
# not a random subset — they are precisely the ones with the signal — so the
# missingness biases the coefficient rather than merely shrinking the sample.
#
# The PHQ-9 also earns its place clinically and not only for the study: its
# severity bands map onto treatment decisions in every major guideline, so the
# professional gets something usable from each administration whether or not
# the research ever concludes. An instrument that only serves the study is an
# instrument that stops being applied by the third month.
DECLARED_PAIRINGS: Tuple[Pairing, ...] = (
    # Vocal psychomotor slowing should rise with depressive severity.
    Pairing("psychomotor_slowing", "PHQ-9", +1),
    # Prosodic activation should fall as depressive severity rises.
    Pairing("prosodic_activation", "PHQ-9", -1),
)

# Deferred to a second study, with its own instrument and its own sample.
#
# Moved out before any data existed, which is the only time hypotheses may be
# changed without contaminating them. Recorded here rather than deleted so the
# protocol shows what was set aside and when.
STAGE_TWO_PAIRINGS: Tuple[Pairing, ...] = (
    # Sustained laryngeal tension should rise with anxiety severity.
    Pairing("laryngeal_tension", "GAD-7", +1),
)


def _clean_pairs(
    xs: Sequence[float], ys: Sequence[float]
) -> Tuple[List[float], List[float]]:
    """Keep only pairs where both sides are usable numbers."""
    limpo_x: List[float] = []
    limpo_y: List[float] = []
    for x, y in zip(xs, ys):
        try:
            fx, fy = float(x), float(y)
        except (TypeError, ValueError):
            continue
        if isfinite(fx) and isfinite(fy):
            limpo_x.append(fx)
            limpo_y.append(fy)
    return limpo_x, limpo_y


def pearson_r(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    x, y = _clean_pairs(xs, ys)
    n = len(x)
    if n < 3:
        return None
    media_x = sum(x) / n
    media_y = sum(y) / n
    dx = [v - media_x for v in x]
    dy = [v - media_y for v in y]
    num = sum(a * b for a, b in zip(dx, dy))
    den = sqrt(sum(a * a for a in dx) * sum(b * b for b in dy))
    if den == 0:
        # No variance on one side: a flat pattern or a flat instrument score
        # cannot correlate with anything, and reporting 0 would suggest a
        # measured absence of relationship rather than an unusable sample.
        return None
    return max(-1.0, min(1.0, num / den))


def fisher_interval(r: float, n: int) -> Optional[Tuple[float, float]]:
    """Confidence interval for r via the Fisher z transform.

    The interval is the whole point. A coefficient of 0.42 from 31 patients and
    one from 400 are different claims, and only the interval shows it.
    """
    if n < 4 or abs(r) >= 1.0:
        return None
    z = atanh(r)
    erro = 1.0 / sqrt(n - 3)
    return tanh(z - CONFIDENCE_Z * erro), tanh(z + CONFIDENCE_Z * erro)


@dataclass(frozen=True)
class ConvergenceResult:
    pattern_key: str
    instrument: str
    n: int
    r: Optional[float]
    interval: Optional[Tuple[float, float]]
    verdict: str
    detail: str

    @property
    def reportable(self) -> bool:
        return self.verdict not in ("insufficient_sample", "unusable_sample")

    @property
    def is_pilot(self) -> bool:
        """O piloto fechou? Leitura planejada, nao resultado."""
        return self.n >= PILOT_PAIRS

    @property
    def is_final(self) -> bool:
        """A amostra confirmatoria foi atingida?

        Antes disso, todo coeficiente e leitura provisoria. Sustentar conclusao
        em leitura provisoria e parar de coletar quando o numero agrada — a
        forma mais comum de produzir um resultado que nao se reproduz.
        """
        return self.n >= TARGET_PAIRS

    @property
    def stage(self) -> str:
        if self.n >= TARGET_PAIRS:
            return "confirmatorio"
        if self.n >= PILOT_PAIRS:
            return "piloto"
        return "coleta"

    @property
    def progress(self) -> str:
        alvo = TARGET_PAIRS if self.n >= PILOT_PAIRS else PILOT_PAIRS
        return f"{self.n}/{alvo}"


def evaluate(
    pairing: Pairing,
    pattern_values: Sequence[float],
    instrument_scores: Sequence[float],
) -> ConvergenceResult:
    """Weigh one hypothesis against one sample.

    The verdict is decided by the end of the interval nearest zero, never by
    the point estimate — the same posture the effectiveness module takes. An
    r of 0.55 whose interval runs from 0.04 to 0.82 is not evidence of
    convergence; it is a sample too small to tell, and saying otherwise is what
    an opposing expert takes apart.
    """
    x, y = _clean_pairs(pattern_values, instrument_scores)
    n = len(x)

    if n < MIN_PAIRS:
        return ConvergenceResult(
            pairing.pattern_key, pairing.instrument, n, None, None,
            "insufficient_sample",
            f"{n} pares validos; sao necessarios ao menos {MIN_PAIRS} para "
            f"reportar coeficiente de validade.",
        )

    r = pearson_r(x, y)
    if r is None:
        return ConvergenceResult(
            pairing.pattern_key, pairing.instrument, n, None, None,
            "unusable_sample",
            "Sem variancia em um dos lados: a amostra nao permite correlacao.",
        )

    intervalo = fisher_interval(r, n)
    if intervalo is None:
        return ConvergenceResult(
            pairing.pattern_key, pairing.instrument, n, r, None,
            "unusable_sample", "Correlacao degenerada; intervalo indefinido.",
        )

    baixo, alto = intervalo
    orientado = r * pairing.expected_direction
    # A extremidade conservadora, na direcao declarada.
    limite = (baixo if pairing.expected_direction > 0 else -alto)

    if baixo <= 0.0 <= alto:
        verdict = "inconclusive"
        detalhe = (
            "O intervalo atravessa o zero: a amostra nao distingue a relacao "
            "de ausencia de relacao."
        )
    elif orientado < 0:
        verdict = "contradicted"
        detalhe = (
            "A correlacao aponta no sentido oposto ao declarado antes da "
            "coleta. Isto e evidencia contra a convergencia, e nao um "
            "resultado a reinterpretar."
        )
    elif limite >= R_STRONG:
        verdict = "strong"
        detalhe = "Convergencia sustentada mesmo na extremidade conservadora."
    elif limite >= R_MODERATE:
        verdict = "moderate"
        detalhe = "Convergencia moderada sustentada pelo limite do intervalo."
    elif limite >= R_SMALL:
        verdict = "weak"
        detalhe = (
            "Relacao pequena e sustentada. Insuficiente para afirmar "
            "convergencia; util para acompanhar com amostra maior."
        )
    else:
        verdict = "negligible"
        detalhe = "Relacao presente porem desprezivel em magnitude."

    return ConvergenceResult(
        pairing.pattern_key, pairing.instrument, n, r, intervalo, verdict, detalhe,
    )


def evidence_statement(result: ConvergenceResult) -> str:
    """The sentence that may be said outside, and nothing beyond it.

    Written here rather than left to whoever builds a slide, because the gap
    between what a coefficient supports and what a deck claims is exactly where
    products of this kind get into trouble.
    """
    if result.verdict == "insufficient_sample":
        return (
            f"Ainda nao ha evidencia de validade convergente entre "
            f"{result.pattern_key} e {result.instrument}: {result.n} pares "
            f"coletados, minimo de {MIN_PAIRS}."
        )
    if result.verdict == "unusable_sample":
        return (
            f"Amostra inutilizavel para {result.pattern_key} x "
            f"{result.instrument}."
        )
    baixo, alto = result.interval or (0.0, 0.0)
    base = (
        f"Em {result.n} pares, {result.pattern_key} correlaciona-se com "
        f"{result.instrument} a r = {result.r:.2f} "
        f"(IC 95%: {baixo:.2f} a {alto:.2f})."
    )
    if not result.is_final:
        # Leitura provisoria nunca sai como resultado, por melhor que esteja.
        # E justamente quando esta boa que a tentacao de parar aparece.
        if result.is_pilot:
            return (
                base + f" PILOTO ({result.progress}): leitura planejada, nao "
                f"resultado. Em {PILOT_PAIRS} pares o intervalo e largo demais "
                f"para sustentar afirmacao de validade — serve para decidir se "
                f"vale concluir o estudo em {TARGET_PAIRS}. Nao divulgar."
            )
        return (
            base + f" LEITURA PARCIAL: o piloto deste estudo fecha em "
            f"{PILOT_PAIRS} pares e ha {result.progress} coletados. "
            f"Nao divulgar como resultado."
        )
    if result.verdict in ("strong", "moderate"):
        return (
            base + " O resultado e compativel com validade convergente nesta "
            "amostra. Nao substitui o instrumento nem autoriza uso "
            "diagnostico."
        )
    if result.verdict == "contradicted":
        return base + " A direcao contradiz a hipotese declarada."
    return base + " Nao sustenta afirmacao de validade convergente."


def run_declared(
    amostras: Iterable[Tuple[str, Sequence[float], Sequence[float]]],
) -> List[ConvergenceResult]:
    """Evaluate every declared pairing for which a sample was supplied."""
    por_chave = {chave: (p, i) for chave, p, i in amostras}
    resultados: List[ConvergenceResult] = []
    for pairing in DECLARED_PAIRINGS:
        chave = f"{pairing.pattern_key}:{pairing.instrument}"
        amostra = por_chave.get(chave)
        if amostra is None:
            continue
        resultados.append(evaluate(pairing, amostra[0], amostra[1]))
    return resultados
