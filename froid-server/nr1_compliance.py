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

import math
from dataclasses import dataclass, replace
from statistics import NormalDist
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple


# Mirrors froid_nr1_min_cohort_total() / froid_nr1_min_cohort_cut(). SQL is the
# authority — these exist so the API can explain a suppression without a round
# trip, not to decide it. O piso de recorte vem de migrations/010; o de campanha
# foi redefinido em migrations/027 e a definicao que vale e a ultima.
#
# Os dois protegem coisas diferentes, e confundi-los foi o erro que 027 desfez.
# MIN_COHORT_CUT protege PESSOA: e ele que decide o tamanho minimo de cada
# coorte publicada, e por isso nao se move. MIN_COHORT_TOTAL diz quanta resposta
# a campanha precisa somar antes de qualquer coisa ser liberada — e desde que a
# migration 025 acrescentou o portao de representatividade, era ele, e nao este
# piso, que barrava campanha rala em empresa grande.
#
# Em 50, este piso tinha uma unica faixa de efeito restante: empresas de 10 a 49
# trabalhadores, onde a amostra exigida ja e o censo. Ali ele nao acrescentava
# protecao, acrescentava impossibilidade — uma empresa de 30 pessoas nunca reune
# 50 respostas, ainda que todas respondam.
MIN_COHORT_TOTAL = 15
MIN_COHORT_CUT = 10

# Mirrors froid_nr1_sampling_* in migrations/025, same arrangement: SQL decides,
# these explain. z for 95% confidence, ±5 percentage points, and the share of
# the population above which sampling stops making sense and becomes a census.
CONFIDENCE_Z = 1.96
MARGIN_OF_ERROR = 0.05
CENSUS_THRESHOLD = 0.80

VALID_POLARITIES = frozenset({"risk", "protective"})


# ---------------------------------------------------------------------------
# Controle de divulgação: a proporção sai em faixa, nunca em número exato.
#
# O painel publica o tamanho da coorte exato. Publicando junto a proporção com
# três casas, quem lê multiplica uma pela outra e recupera a CONTAGEM DE
# PESSOAS: numa coorte de 15, uma proporção de 0,067 significa exatamente uma
# pessoa na faixa crítica — e numa empresa desse tamanho, onde a chefia conhece
# todo mundo, "exatamente uma pessoa" está a um passo de um nome.
#
# A faixa quebra essa inversão. As bandas são de 20 pontos e a primeira começa
# em zero de propósito: assim ela contém 0 e 1 pessoa em qualquer coorte a
# partir do piso de 10 (1/10 = 0,10, que cai dentro da primeira faixa). Sem essa
# propriedade a faixa não protege nada — ainda seria possível CONFIRMAR que
# existe alguém na faixa crítica, que é a informação que aponta.
#
# São fixas, e não parâmetro de gro_risk_criteria. Controle de privacidade que o
# cliente pode afrouxar não é controle: um cliente com matriz fina afrouxaria a
# própria proteção sem perceber que era isso que estava fazendo.
CRITICAL_RATIO_BANDS: Tuple[Tuple[float, float, str], ...] = (
    (0.00, 0.20, "até 20% da coorte"),
    (0.20, 0.40, "de 20% a 40% da coorte"),
    (0.40, 0.60, "de 40% a 60% da coorte"),
    (0.60, 0.80, "de 60% a 80% da coorte"),
    (0.80, 1.01, "80% ou mais da coorte"),
)


def critical_ratio_band(ratio: float) -> dict:
    """A faixa publicável de uma proporção, sem a proporção.

    Devolve os limites e o rótulo. Os limites vão junto porque a tela precisa
    ordenar e colorir, e o rótulo porque é o que a pessoa lê — mas nenhum dos
    dois permite recuperar quantas pessoas estão ali.
    """
    valor = max(0.0, min(1.0, float(ratio or 0.0)))
    for lower, upper, label in CRITICAL_RATIO_BANDS:
        if valor < upper:
            return {"lower": lower, "upper": min(1.0, upper), "label": label}
    lower, upper, label = CRITICAL_RATIO_BANDS[-1]
    return {"lower": lower, "upper": 1.0, "label": label}

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
            # 1.5.4.4.2.2 exige QUATRO coisas no documento: gradacoes de
            # severidade, gradacoes de probabilidade, niveis de risco e os
            # criterios de classificacao e de tomada de decisao. As duas
            # ultimas tinham coluna NOT NULL em gro_risk_criteria e eram
            # gravadas vazias — o documento que a fiscalizacao le chegava pela
            # metade.
            "classification_rules": {
                "basis": (
                    "classificacao dos riscos para identificar a necessidade de "
                    "adocao ou manutencao de medidas de prevencao e elaboracao "
                    "do plano de acao (NR-1 1.5.4.4.3)"
                ),
                "levels": {
                    "low": "risco tolerado; manter as medidas existentes e o monitoramento",
                    "moderate": "exige medida; entra no plano de acao",
                    "high": "exige medida; prioridade sobre os moderados",
                    "critical": "exige medida; prioridade maxima",
                },
                "priority_tiebreaker": (
                    "entre riscos de mesma classificacao, o numero de "
                    "trabalhadores possivelmente atingidos aumenta a prioridade "
                    "de acao (NR-1 1.5.5.2.1.1)"
                ),
                "cohort_floors": {
                    "campaign_min_responses": MIN_COHORT_TOTAL,
                    "cut_min_responses": MIN_COHORT_CUT,
                    "representativeness": (
                        "amostra para proporcao com correcao de populacao finita, "
                        f"a {round((2 * NormalDist().cdf(CONFIDENCE_Z) - 1) * 100)}% de confianca e margem de "
                        f"{round(MARGIN_OF_ERROR * 100)} pontos, em p=0,5; acima de "
                        f"{round(CENSUS_THRESHOLD * 100)}% da populacao a amostra vira censo"
                    ),
                    "disclosure_control": (
                        "A proporcao da coorte na faixa critica e publicada em "
                        "faixas de 20 pontos, nunca como valor exato. O tamanho "
                        "da coorte e publicado exato, e sem essa medida a "
                        "multiplicacao de um pelo outro devolveria a contagem de "
                        "pessoas: numa coorte de 15, a proporcao 0,067 seria "
                        "exatamente uma pessoa. A primeira faixa comeca em zero "
                        "para conter tanto nenhuma quanto uma pessoa em qualquer "
                        "coorte a partir do piso, de modo que nao se possa "
                        "sequer confirmar que existe alguem na faixa critica. As "
                        "faixas sao fixas e nao configuraveis: controle de "
                        "privacidade que o cliente pode afrouxar nao e controle. "
                        "A gradacao do risco continua sendo calculada sobre o "
                        "valor exato, que nao sai do banco."
                    ),
                    "origin": (
                        "ESCOLHA METODOLOGICA DESTA ORGANIZACAO, NAO EXIGENCIA "
                        "NORMATIVA. A NR-1 nao prescreve taxa de resposta nem "
                        "piso de coorte. Os pisos existem para sustentar a "
                        "suficiencia tecnica que 1.5.4.4.2.1 cobra (ferramenta "
                        "adequada ao risco em avaliacao) e para impedir "
                        "reidentificacao do trabalhador, e por isso ficam "
                        "declarados aqui em vez de apresentados como obrigacao legal."
                    ),
                },
            },
            "decision_rules": {
                "measure_hierarchy": {
                    "order": list(MEASURE_HIERARCHY),
                    "basis": "NR-1 1.5.3.2 'a', 1.4.1 'g' e 1.5.5.1.2",
                    "declared_divergence": (
                        "A hierarquia de 1.5.5.1.2 termina em equipamento de "
                        "protecao individual. Esta organizacao NAO adota o degrau "
                        "de EPI para fatores de risco psicossociais, por dois "
                        "motivos declarados: nao existe equipamento de protecao "
                        "individual contra a forma como o trabalho e organizado, "
                        "e o Guia MTE 2025 orienta preferir intervencoes que "
                        "modifiquem as condicoes da organizacao do trabalho as "
                        "intervencoes pessoais ou comportamentais. No lugar do "
                        "EPI, o ultimo degrau e o acompanhamento planejado do "
                        "desempenho da medida, previsto em 1.5.5.3.2. A "
                        "'substituicao' listada acima consta do Manual do GRO "
                        "como parte da eliminacao do perigo, e nao do texto do "
                        "subitem. A divergencia esta escrita aqui de proposito: "
                        "quem comparar este documento com 1.5.5.1.2 encontra a "
                        "justificativa no mesmo lugar em que encontra a diferenca."
                    ),
                },
                "measure_by_level": {
                    level: suggested_measure_type_for_level(level)
                    for level in RISK_LEVELS
                },
                "action_deadline": (
                    "A NR-1 nao fixa prazo para implementar a medida: 1.5.5.2.2 "
                    "exige cronograma com responsaveis, formas de acompanhamento "
                    "e afericao de resultados. O prazo de cada nivel de risco e "
                    "definido por esta organizacao no plano de acao e passa a ser "
                    "o criterio contra o qual o proprio desempenho e medido."
                ),
                "review": {
                    "interval_months_default": 24,
                    "interval_months_with_certified_sst_system": 36,
                    "basis": "NR-1 1.5.4.4.6 e 1.5.4.4.6.1",
                    "immediate_triggers": [
                        "a) apos implementacao das medidas, para avaliacao de riscos residuais",
                        "b) apos inovacoes e modificacoes que impliquem novos riscos",
                        "c) quando identificadas inadequacoes, insuficiencia ou ineficacia das medidas",
                        "d) na ocorrencia de acidentes ou doencas relacionadas ao trabalho",
                        "e) quando houver mudanca nos requisitos legais aplicaveis",
                        "f) apos solicitacao justificada dos trabalhadores ou da CIPA",
                    ],
                    "note": (
                        "O prazo de dois anos e teto, nao cadencia. A alinea 'a' "
                        "dispara pela implementacao da medida, e nao por data: "
                        "assim que a organizacao age, nasce a obrigacao de "
                        "reavaliar o risco residual."
                    ),
                },
                "ineffective_measure": (
                    "Medida cujo acompanhamento indique ineficacia deve ser "
                    "corrigida (NR-1 1.5.5.3.2.1). Nesta organizacao a ineficacia "
                    "e apurada comparando cada recorte contra a propria linha de "
                    "base, pelo limite conservador do intervalo de confianca do "
                    "tamanho de efeito — nunca pelo valor central."
                ),
            },
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


# ---------------------------------------------------------------------------
# Portão A — representatividade.
#
# Separado do piso de anonimato de propósito. Os dois contam respostas e recusam
# o resultado, mas respondem a perguntas diferentes: MIN_COHORT_* impede que a
# coorte seja pequena o bastante para reidentificar quem respondeu; o piso
# abaixo impede que ela seja pequena demais para *falar pelo efetivo*. Uma
# empresa de 3.000 pessoas com 50 respostas passava no primeiro e gerava
# inventário sobre 1,7% do quadro.
#
# O número não é nosso, e é o ponto: é o tamanho de amostra com correção para
# população finita. Isso o torna citável no documento de critérios que
# 1.5.4.4.2.2 exige e afasta a alegação de amostragem por conveniência. E ele
# escala sozinho na direção que o Guia MTE indica — questionário serve empresa
# grande; em grupo pequeno a fórmula converge para censo, que é justamente onde
# o Guia manda usar diálogo e observação da atividade em vez de formulário.
#
# A norma não fixa taxa nenhuma: a escolha do método é da organização. O que a
# fiscalização cobra é suficiência técnica e coerência — por isso os parâmetros
# abaixo são dado em gro_risk_criteria, versionado junto com o resto dos
# critérios, e não constante de código.
# ---------------------------------------------------------------------------


def required_sample(
    population: int,
    *,
    margin_of_error: float = MARGIN_OF_ERROR,
    confidence_z: float = CONFIDENCE_Z,
    census_threshold: float = CENSUS_THRESHOLD,
) -> Optional[int]:
    """Respostas substantivas necessárias para uma coorte falar por `population`.

    Amostra para proporção com correção de população finita, em p=0,5 — a
    proporção de maior variância, e portanto a exigência conservadora qualquer
    que seja o resultado que o questionário venha a medir.

    Devolve None quando o efetivo não foi declarado. Sem denominador não existe
    "amostra suficiente", e devolver zero faria do efetivo não declarado o
    caminho mais curto para desligar o portão.
    """
    if population is None or population <= 0:
        return None
    if not 0.0 < margin_of_error < 1.0:
        raise ValueError("margin_of_error must sit between 0 and 1")
    if confidence_z <= 0:
        raise ValueError("confidence_z must be positive")
    if not 0.0 < census_threshold <= 1.0:
        raise ValueError("census_threshold must sit between 0 and 1")
    unlimited = (confidence_z ** 2) * 0.25 / (margin_of_error ** 2)
    corrected = unlimited / (1.0 + (unlimited - 1.0) / population)
    # A transição para censo é decidida sobre o valor contínuo, antes do teto.
    # Comparando o inteiro já arredondado, o arredondamento empurra populações
    # logo acima do corte para o outro lado e a exigência oscila: 100 pessoas
    # pedindo amostra de 80, 101 pedindo censo de 101, 102 pedindo amostra de
    # novo. Quem tivesse 101 no quadro pagaria por declarar uma pessoa a mais.
    if corrected > census_threshold * population:
        return population
    # O arredondamento antes do teto existe para que 80.0000000001, que é ruído
    # de ponto flutuante e não exigência, não vire 81 respostas.
    return min(population, math.ceil(round(corrected, 9)))


@dataclass(frozen=True)
class Representativeness:
    """Por que uma campanha fechada ainda não vira inventário."""

    population: int
    achieved: int
    required: Optional[int]
    # "sample" | "census" | "undeclared"
    mode: str
    met: bool
    # Carregados junto porque o aviso ao gestor cita a tolerância, e citar 95%
    # quando a organização configurou outra coisa seria informação errada num
    # texto que acompanha documento de fiscalização.
    margin_of_error: float = MARGIN_OF_ERROR
    confidence_z: float = CONFIDENCE_Z

    @property
    def confidence(self) -> float:
        """Confiança bilateral correspondente a `confidence_z`, em 0..1."""
        return max(0.0, min(1.0, 2.0 * NormalDist().cdf(self.confidence_z) - 1.0))


def representativeness(
    population: int,
    achieved: int,
    *,
    margin_of_error: float = MARGIN_OF_ERROR,
    confidence_z: float = CONFIDENCE_Z,
    census_threshold: float = CENSUS_THRESHOLD,
) -> Representativeness:
    """Espelha o veredito do Portão A para que a tela possa explicá-lo.

    A decisão continua sendo do SQL: esta função existe para dizer ao gestor
    quantas respostas ainda faltam, não para liberar resultado.
    """
    declared = max(0, int(population or 0))
    required = required_sample(
        declared,
        margin_of_error=margin_of_error,
        confidence_z=confidence_z,
        census_threshold=census_threshold,
    )
    if required is None:
        mode = "undeclared"
    elif required >= declared:
        mode = "census"
    else:
        mode = "sample"
    return Representativeness(
        population=declared,
        achieved=max(0, int(achieved or 0)),
        required=required,
        mode=mode,
        met=required is not None and int(achieved or 0) >= required,
        margin_of_error=margin_of_error,
        confidence_z=confidence_z,
    )


def representativeness_notice(verdict: Representativeness) -> str:
    """Explica um painel retido por representatividade, não por anonimato.

    São dois avisos porque são duas causas, e confundi-las manda o gestor
    perseguir o número errado: quem lê "faltam respostas para o piso de 50"
    numa campanha que já tem 200 e precisa de 341 conclui que o sistema está
    quebrado.
    """
    if verdict.met:
        return ""
    if verdict.mode == "undeclared":
        return (
            "O efetivo de trabalhadores desta campanha não foi declarado. Sem "
            "ele não há como afirmar que as respostas representam o quadro, e "
            "inventário sobre população desconhecida não se sustenta diante da "
            "fiscalização. Informe o efetivo do período de referência."
        )
    confianca = round(verdict.confidence * 100)
    margem = round(verdict.margin_of_error * 100)
    if verdict.mode == "census":
        return (
            f"Para um efetivo de {verdict.population} trabalhadores, a amostra "
            f"necessária a {confianca}% de confiança alcança praticamente todo "
            "o quadro — esta campanha exige censo, ou seja, as "
            f"{verdict.population} respostas. Há {verdict.achieved}. Em grupos "
            "deste tamanho o Guia MTE indica diálogo e observação da atividade "
            "como caminho mais adequado que o questionário."
        )
    return (
        f"Esta campanha reuniu {verdict.achieved} respostas substantivas e "
        f"precisa de {verdict.required} para representar um efetivo de "
        f"{verdict.population} trabalhadores a {confianca}% de confiança, com "
        f"margem de {margem} pontos. Abaixo disso o resultado descreve quem "
        "respondeu, e não o trabalho da organização."
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
        # A justificativa e GRAVADA no inventario e e o texto que o auditor le.
        # Citar aqui a proporcao exata anularia a faixa do painel: bastaria abrir
        # o documento para recuperar a contagem de pessoas.
        f"{critical_ratio_band(score.critical_ratio)['label']} na faixa critica). "
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


# ---------------------------------------------------------------------------
# Recorte que nao pode ser classificado: declarado, e nao omitido.
#
# Suprimir e ocultar; declarar insuficiente e documentar. Ate 25/08/2026 o
# produto so fazia a primeira, e painel vazio nao e neutro — o cliente le
# "nao ha risco aqui", que e exatamente a conclusao que a ausencia de dado nao
# autoriza. O contrato passou a proibir isso em duas clausulas, e a norma diz o
# mesmo por outro caminho: 1.5.7.3.1 manda consolidar no inventario os dados da
# identificacao de perigos, e nao apenas os riscos que couberam numa
# classificacao.
#
# Cada portao tem remedio diferente, e por isso cada um tem texto proprio. Dizer
# so "insuficiente" faria a empresa perseguir adesao onde adesao nao resolve.
UNCLASSIFIABLE_LEVEL = "insuficiente"

SUPPRESSION_GATES: Tuple[str, ...] = (
    "anonimato",
    "representatividade",
    "efetivo_nao_declarado",
    "campanha_abaixo_do_piso",
)

_NAO_E_AUSENCIA_DE_RISCO = (
    "Este resultado NAO significa ausencia de risco: significa que as evidencias "
    "reunidas nao bastam para classificar este recorte. A obrigacao de gerenciar "
    "o risco psicossocial permanece integral."
)


def escalation_note(
    gate: str,
    *,
    required_responses: Optional[int] = None,
    declared_headcount: Optional[int] = None,
) -> str:
    """O que a organizacao deve fazer com um recorte que nao classificou.

    Texto destinado ao documento que a fiscalizacao le, entao nomeia o subitem
    que sustenta cada caminho. Nao cita contagem de respostas do recorte — o
    numero esta abaixo do piso por definicao, e publica-lo aqui devolveria pela
    porta dos fundos a coorte que o piso recusou mostrar no painel.
    """
    if gate == "anonimato":
        return (
            "Recorte abaixo do piso de coorte que protege o anonimato. Nenhuma "
            "adesao adicional o publica enquanto o grupo for menor que esse piso, "
            "porque o piso olha o tamanho do grupo e nao a taxa de resposta. "
            "Caminho indicado: avaliar este grupo pela Avaliacao Ergonomica "
            "Preliminar, com dialogo com os trabalhadores e observacao da "
            "atividade — metodos que o Guia MTE indica justamente para grupo "
            "pequeno e que nao dependem de piso de respondentes. "
            + _NAO_E_AUSENCIA_DE_RISCO
        )
    if gate == "representatividade":
        exigencia = ""
        if required_responses and declared_headcount:
            exigencia = (
                f" Para o efetivo declarado de {declared_headcount} trabalhadores, "
                f"a amostra necessaria e de {required_responses} respostas "
                "substantivas."
            )
        return (
            "A coorte reunida atingiu o piso de anonimato, mas ainda nao fala "
            "pelo efetivo declarado deste recorte." + exigencia + " Diferente do "
            "caso anterior, este recorte publica se a adesao subir: cabe reforcar "
            "a participacao, nos termos de 1.5.3.3, e reabrir a coleta. "
            + _NAO_E_AUSENCIA_DE_RISCO
        )
    if gate == "efetivo_nao_declarado":
        return (
            "Recorte sem efetivo declarado para o periodo de referencia. Sem "
            "denominador nao ha o que representar, e qualquer resultado seria "
            "sobre uma populacao desconhecida. Caminho indicado: declarar o "
            "efetivo deste recorte, o que publica o resultado ou o reprova com "
            "fundamento verificavel. " + _NAO_E_AUSENCIA_DE_RISCO
        )
    if gate == "campanha_abaixo_do_piso":
        return (
            "A campanha inteira nao atingiu os pisos exigidos, entao nenhum "
            "recorte dela e publicavel e nao ha quebra por unidade a apresentar. "
            "Caminho indicado: reforcar a participacao e reabrir a coleta, ou "
            "avaliar por Avaliacao Ergonomica Preliminar quando o porte da "
            "organizacao nao sustentar coorte. " + _NAO_E_AUSENCIA_DE_RISCO
        )
    raise ValueError(f"portao de supressao desconhecido: {gate!r}")


@dataclass(frozen=True)
class UnclassifiableFinding:
    """Um recorte que foi avaliado, nao pode ser classificado, e fica registrado.

    Espelha GradedRisk no que o inventario precisa, e deliberadamente NAO tem
    cohort_size, mean_score, severity nem probability: a restricao
    psychosocial_risk_inventory_classificada_ou_declarada exige que esses quatro
    sejam nulos aqui. Linha pela metade e a que um auditor le como risco baixo.
    """

    unit_id: Optional[str]
    dimension_id: str
    nr1_factor: str
    gate: str
    required_responses: Optional[int]
    declared_headcount: Optional[int]
    criteria_version: str
    risk_level: str = UNCLASSIFIABLE_LEVEL

    @property
    def escalation(self) -> str:
        return escalation_note(
            self.gate,
            required_responses=self.required_responses,
            declared_headcount=self.declared_headcount,
        )


def unclassifiable_findings(
    rows: Iterable[Mapping[str, Any]], criteria: "GradationCriteria"
) -> List[UnclassifiableFinding]:
    """Converte o veredito do banco em achado declaravel, na ordem estavel."""
    achados = [
        UnclassifiableFinding(
            unit_id=row.get("unit_id"),
            dimension_id=str(row["dimension_id"]),
            nr1_factor=str(row.get("nr1_factor") or ""),
            gate=str(row["gate"]),
            required_responses=row.get("required_responses"),
            declared_headcount=row.get("declared_headcount"),
            criteria_version=criteria.version,
        )
        for row in rows
    ]
    # Ordem estavel para que o documento nao mude de ordem entre duas geracoes
    # do mesmo ciclo, o que numa pericia parece adulteracao.
    return sorted(achados, key=lambda a: (a.unit_id or "", a.nr1_factor, a.dimension_id))


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


def suggested_measure_type_for_level(risk_level: str) -> str:
    """Degrau da hierarquia que cada nivel de risco puxa como ponto de partida.

    Separado de suggested_measure_type() porque o documento de criterios de
    1.5.4.4.2.2 precisa DECLARAR esta regra, e uma regra declarada num lugar e
    aplicada noutro e a forma mais confiavel de as duas divergirem.
    """
    if risk_level == "critical":
        return "elimination"
    if risk_level == "high":
        return "collective"
    if risk_level == "moderate":
        return "administrative"
    return "monitoring"


def suggested_measure_type(risk: GradedRisk) -> str:
    """A starting point for the action plan, never a substitute for it."""
    return suggested_measure_type_for_level(risk.risk_level)


# 1.5.5.2.1 nomeia TRÊS destinos possíveis para uma medida no plano de ação:
# introduzida, aprimorada ou mantida. Guardar só o texto da medida perde a
# informação de qual dos três o inventário determinou — e é justamente essa
# informação que distingue "não fizemos nada" de "já havia medida e ela segue".
PLAN_ACTIONS = ("introduce", "improve", "maintain")


def plan_action_for(risk: GradedRisk) -> Optional[str]:
    """Qual dos três verbos de 1.5.5.2.1 este risco determina, ou nenhum.

    A regra sai da combinação entre o nível de risco e a eficácia da medida já
    implementada, que são exatamente os dois eixos que 1.5.4.4.5.3 manda
    considerar:

    - Sem medida implementada e risco acima de baixo -> **introduzir**.
    - Sem medida implementada e risco baixo -> nada. Não há o que introduzir
      (o nível é tolerável) nem o que manter (não existe medida).
    - Medida implementada cujo acompanhamento indicou ineficácia -> **aprimorar**,
      qualquer que seja o nível resultante. 1.5.5.3.2.1 é categórico: medida que
      se mostrou ineficaz *deve* ser corrigida. Deixá-la de pé porque o risco
      ficou baixo é o caso em que uma medida que não funciona envelhece como se
      fosse prova de diligência.
    - Medida implementada e risco baixo -> **manter**, com acompanhamento. O
      Quadro 5 do Manual do GRO: "nenhum controle adicional necessário; manter o
      monitoramento para assegurar que os controles sejam mantidos".
    - Medida implementada e risco ainda acima de baixo -> **aprimorar**. A medida
      existe e não bastou.
    """
    if risk.measure_efficacy == "none":
        return None if risk.risk_level == "low" else "introduce"
    if risk.measure_efficacy == "insufficient":
        return "improve"
    if risk.risk_level == "low":
        return "maintain"
    return "improve"


def action_plan_seed(graded: Sequence[GradedRisk]) -> List[dict]:
    """Draft plano de ação rows for every risk that NR-1 obliges acting on.

    Only a skeleton: 1.5.5.2.2 requires cronograma, responsáveis and formas de
    acompanhamento e aferição de resultados, and those are the organization's to
    fill in — a measure nobody owns is what an auditor treats as no measure.

    `graded` chega já ordenado por action_priority(), então a posição na lista é
    a prioridade — e 1.5.5.2.1.1 manda que o número de trabalhadores atingidos
    entre nessa conta, o que action_priority() faz. O rank é gravado para que a
    ordem do documento não dependa de quem o abre.
    """
    seeds: List[dict] = []
    for risk in graded:
        plan_action = plan_action_for(risk)
        if plan_action is None:
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
                "plan_action": plan_action,
                "measure_type": suggested_measure_type(risk),
                "measure": "",
                "responsible_membership_id": None,
                "due_date": None,
                "monitoring_method": "",
                "result_measurement": "",
                "status": "planned",
                "priority_rank": len(seeds) + 1,
            }
        )
    return seeds
