"""
Motor de DISSONÂNCIAS EVIDENTES do FROID.

A habilidade central e o objetivo do FROID é apontar dissonâncias — os
instantes em que a expressão humana (voz, face) se descola do estado interno —
e alertar o profissional. Este módulo formaliza essa detecção.

CONCEITO
--------
Para CADA marcador real define-se uma MÉTRICA BASE: uma banda [mínimo, máximo]
de normalidade. Sempre que o valor medido ultrapassa a banda (fica abaixo do
mínimo OU acima do máximo), aquele marcador constitui uma "dissonância
evidente" naquele tick.

Uma dissonância evidente isolada é ruído clínico — variação natural. O ALERTA
só é emitido quando DUAS OU MAIS dissonâncias evidentes ocorrem
SIMULTANEAMENTE no mesmo tick: a co-ocorrência é o que caracteriza uma
dissonância real, digna de registro na listagem detalhada apresentada ao
profissional (com scroll). É exatamente a regra pedida: "apenas aquelas
situações em que forem apontados dois ou mais itens que ultrapassarem a
métrica base pré-definida".

TIPOS DE BANDA
--------------
- ABSOLUTA: marcadores já normalizados ou com referência de literatura
  (jitter, shimmer, índices DNA em [0,1], aceleração cepstral ΔΔMFCC).
- RELATIVA À BASELINE: marcadores cuja normalidade é o próprio repouso do
  paciente (F0, loudness, ZCR). A banda é derivada da baseline travada nos
  primeiros ~60s da sessão; enquanto não há baseline, o marcador é ignorado
  (não se pode afirmar desvio sem referência).

Cada limiar abaixo está documentado com sua justificativa. O módulo é puro
(sem estado): recebe um snapshot de marcadores por tick e devolve a avaliação.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

EPS = 1e-9


@dataclass
class Breach:
    """Uma dissonância evidente: um marcador fora de sua métrica base."""

    key: str
    label: str
    category: str
    value: float
    low: Optional[float]
    high: Optional[float]
    direction: str  # "acima" | "abaixo"
    severity: float  # 0..1, quão longe da banda (normalizado)
    unit: str
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "value": round(float(self.value), 4),
            "band": [self.low, self.high],
            "direction": self.direction,
            "severity": round(float(self.severity), 3),
            "unit": self.unit,
            "interpretation": self.interpretation,
        }


@dataclass
class MarkerSpec:
    """Definição de um marcador e sua métrica base (banda de normalidade)."""

    key: str
    label: str
    category: str
    unit: str
    interpret_low: str
    interpret_high: str
    # Extrai (valor, low, high) do snapshot, ou None se não avaliável neste tick
    # (ex.: voz real ausente, baseline ainda não travada).
    resolver: Callable[[Dict[str, Any]], Optional[tuple]]

    def evaluate(self, snap: Dict[str, Any]) -> Optional[Breach]:
        resolved = self.resolver(snap)
        if resolved is None:
            return None
        value, low, high = resolved
        if value is None:
            return None
        value = float(value)
        direction: Optional[str] = None
        if high is not None and value > high:
            direction = "acima"
            span = abs(high) if abs(high) > EPS else 1.0
            severity = min(1.0, (value - high) / span)
        elif low is not None and value < low:
            direction = "abaixo"
            span = abs(low) if abs(low) > EPS else 1.0
            severity = min(1.0, (low - value) / span)
        if direction is None:
            return None
        return Breach(
            key=self.key,
            label=self.label,
            category=self.category,
            value=value,
            low=low,
            high=high,
            direction=direction,
            severity=max(0.0, severity),
            unit=self.unit,
            interpretation=self.interpret_high if direction == "acima" else self.interpret_low,
        )

    def read(self, snap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Leitura SEMPRE presente (marcador dentro ou fora da banda) — usada
        para exibir o valor atual de cada índice, independente de ter
        rompido ou não a métrica base. Retorna None só quando o marcador não
        é avaliável neste tick (ex.: voz real ausente, baseline não travada)."""
        resolved = self.resolver(snap)
        if resolved is None:
            return None
        value, low, high = resolved
        if value is None:
            return None
        value = float(value)
        breached = False
        direction = "dentro"
        severity = 0.0
        interpretation = "—"
        if high is not None and value > high:
            breached, direction = True, "acima"
            span = abs(high) if abs(high) > EPS else 1.0
            severity = max(0.0, min(1.0, (value - high) / span))
            interpretation = self.interpret_high
        elif low is not None and value < low:
            breached, direction = True, "abaixo"
            span = abs(low) if abs(low) > EPS else 1.0
            severity = max(0.0, min(1.0, (low - value) / span))
            interpretation = self.interpret_low
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "value": round(value, 4),
            "band": [low, high],
            "unit": self.unit,
            "breached": breached,
            "direction": direction,
            "severity": round(severity, 3),
            "interpretation": interpretation,
        }


def _voice_real(snap: Dict[str, Any]) -> bool:
    return bool(snap.get("voice_real"))


def _baseline_ready(snap: Dict[str, Any]) -> bool:
    # A baseline de VOZ REAL do paciente (F0/loudness/ZCR) precisa estar
    # concluída para que os marcadores relativos tenham referência confiável;
    # recai na trava espectral em payloads sem o campo dedicado.
    if "voice_baseline_ready" in snap:
        return bool(snap.get("voice_baseline_ready"))
    return bool(snap.get("baseline_locked"))


# --------------------------------------------------------------------------
# Registro de marcadores e suas métricas base.
#
# Cada limiar é justificado. Os marcadores dependentes da forma de onda só são
# avaliados quando há voz REAL (voice_real), evitando alarme sobre o modo
# simulado. Os índices estruturais (DNA, zonas, IPM, embotamento) derivam do
# vetor espectral e são sempre avaliados.
# --------------------------------------------------------------------------

def _jitter(snap):
    # Jitter local (perturbação relativa do período). Voz saudável ~<1%
    # (limiar Praat 1,04%); a estimativa por quadros do FROID é mais grosseira,
    # portanto max=0,02 (2%) para tensão/instabilidade glótica evidente.
    if not _voice_real(snap):
        return None
    return (snap.get("jitter"), None, 0.02)


def _shimmer(snap):
    # Shimmer local (perturbação relativa da amplitude). Limiar Praat ~3,81%;
    # com margem para o estimador do FROID, max=0,08 (8%).
    if not _voice_real(snap):
        return None
    return (snap.get("shimmer"), None, 0.08)


def _f0_cv(snap):
    # Prosódia: coeficiente de variação da F0 na janela (f0_var/f0_mean).
    # A fala expressiva natural mantém CV ~0,08-0,35. Abaixo de 0,04 =
    # monotonia (achatamento afetivo); acima de 0,45 = instabilidade/agitação.
    # Exige F0 vozeada suficiente (voiced_ratio >= 0,30); com poucos quadros
    # vozeados o desvio-padrão é ruidoso e o CV não é confiável.
    if not _voice_real(snap):
        return None
    if float(snap.get("f0_voiced_ratio") or 0.0) < 0.30:
        return None
    f0 = float(snap.get("f0_mean") or 0.0)
    if f0 <= 0.0:
        return None
    cv = float(snap.get("f0_var") or 0.0) / (f0 + EPS)
    return (cv, 0.04, 0.45)


def _f0_baseline_dev(snap):
    # Desvio da F0 média em relação à baseline do paciente. Uma elevação
    # sustentada >20% sugere tensão/hiperativação; queda >20% sugere
    # retração/hipofonação.
    if not _voice_real(snap) or not _baseline_ready(snap):
        return None
    base = float(snap.get("baseline_f0") or 0.0)
    f0 = float(snap.get("f0_mean") or 0.0)
    if base <= 0.0 or f0 <= 0.0:
        return None
    rel = (f0 - base) / (base + EPS)
    return (rel, -0.20, 0.20)


def _loudness_dev(snap):
    # Desvio de loudness (RMS dBFS) em relação à baseline. Uma variação >6 dB
    # (dobro/metade da pressão sonora) marca surto de intensidade (agitação) ou
    # colapso de volume (retração/embotamento).
    if not _voice_real(snap) or not _baseline_ready(snap):
        return None
    base = snap.get("baseline_loudness")
    val = snap.get("loudness_dbfs")
    if base is None or val is None:
        return None
    return (float(val) - float(base), -6.0, 6.0)


def _zcr_dev(snap):
    # Desvio de ZCR em relação à baseline. Aumento >60% sugere voz soprosa/
    # fricativa por tensão; a banda relativa evita depender do valor absoluto.
    if not _voice_real(snap) or not _baseline_ready(snap):
        return None
    base = float(snap.get("baseline_zcr") or 0.0)
    val = snap.get("zcr")
    if base <= 0.0 or val is None:
        return None
    rel = (float(val) - base) / (base + EPS)
    return (rel, -0.60, 0.60)


def _mfcc9_spastic(snap):
    # Aceleração cepstral |ΔΔMFCC9| > 1,8 (memória de cálculo): contração
    # espástica involuntária das cordas vocais por ativação simpática.
    if not _voice_real(snap):
        return None
    return (abs(float(snap.get("mfcc9_delta_delta") or 0.0)), None, 1.8)


def _mfcc7_spastic(snap):
    # Instabilidade cepstral análoga no coeficiente 7 (formante/timbre).
    if not _voice_real(snap):
        return None
    return (abs(float(snap.get("mfcc7_delta_delta") or 0.0)), None, 1.8)


def _dna_flooding(snap):
    # Inundação autonômica (índice DNA em [0,1]). Acima de 0,60 = ativação
    # simpática intensa (energia infrassônica + basal elevadas).
    return (snap.get("dna_autonomic_flooding"), None, 0.60)


def _dna_shutdown(snap):
    # Shutdown dissociativo (índice DNA em [0,1]). Acima de 0,60 = colapso
    # parassimpático (energia nuclear alta com IPM e ZCR deprimidos).
    return (snap.get("dna_dissociative_shutdown"), None, 0.60)


def _dna_somato(snap):
    # Dissonância somatoafetiva (índice DNA em [0,1]). Acima de 0,60 =
    # descolamento entre carga somática e supressão expressiva facial.
    return (snap.get("dna_somatoaffective_dissonance"), None, 0.60)


def _zone_extreme(snap):
    # Desequilíbrio EXTREMO de zona: maior |desvio| entre as 12 zonas acima de
    # 3,0 (faixa VERMELHA do colorímetro).
    zones = snap.get("zone_deviations") or []
    if not zones:
        return None
    peak = max((abs(float(z)) for z in zones), default=0.0)
    return (peak, None, 3.0)


def _ipm_hyper(snap):
    # Hiperativação multimodal: IPM (0-100) acima de 80 satura a sigmoide de
    # potência — ativação difusa por todas as zonas.
    return (snap.get("ipm_score"), None, 80.0)


def _facial_contradiction(snap):
    # Contradição facial-vocal REAL (FACS): a assinatura de dissonância do
    # FROID — o rosto mascarando/contradizendo o afeto. Só conta com face real
    # (blendshapes medidos). Qualquer dissonância facial real (>= 1) é evidente.
    if not snap.get("facial_real"):
        return None
    return (float(snap.get("facial_dissonance_count") or 0), None, 0.0)


MARKER_SPECS: List[MarkerSpec] = [
    MarkerSpec("jitter", "Jitter (perturbação de período)", "Perturbação vocal", "proxy",
               "—", "instabilidade glótica / tensão laríngea", _jitter),
    MarkerSpec("shimmer", "Shimmer (perturbação de amplitude)", "Perturbação vocal", "proxy",
               "—", "irregularidade de amplitude / esforço vocal", _shimmer),
    MarkerSpec("f0_cv", "Variabilidade da F0 (prosódia)", "Prosódia", "CV",
               "monotonia / achatamento afetivo", "instabilidade prosódica / agitação", _f0_cv),
    MarkerSpec("f0_baseline_dev", "Desvio de F0 vs. baseline", "Prosódia", "ratio",
               "hipofonação / retração", "tensão / hiperativação tonal", _f0_baseline_dev),
    MarkerSpec("loudness_dev", "Desvio de loudness vs. baseline", "Energia vocal", "dB",
               "colapso de volume / embotamento", "surto de intensidade / agitação", _loudness_dev),
    MarkerSpec("zcr_dev", "Desvio de ZCR vs. baseline", "Timbre", "ratio",
               "voz opaca / abafada", "voz soprosa-fricativa / tensão", _zcr_dev),
    MarkerSpec("mfcc9_spastic", "Aceleração cepstral ΔΔMFCC9", "Contração espástica (SNS)", "|ΔΔ|",
               "—", "contração espástica involuntária das cordas vocais", _mfcc9_spastic),
    MarkerSpec("mfcc7_spastic", "Aceleração cepstral ΔΔMFCC7", "Instabilidade cepstral", "|ΔΔ|",
               "—", "instabilidade de timbre / formante", _mfcc7_spastic),
    MarkerSpec("dna_flooding", "Inundação autonômica", "Sistema nervoso autônomo", "índice",
               "—", "ativação simpática intensa (flooding)", _dna_flooding),
    MarkerSpec("dna_shutdown", "Shutdown dissociativo", "Sistema nervoso autônomo", "índice",
               "—", "colapso parassimpático / dissociação", _dna_shutdown),
    MarkerSpec("dna_somato", "Dissonância somatoafetiva", "Integração somatoafetiva", "índice",
               "—", "carga somática descolada da expressão", _dna_somato),
    MarkerSpec("zone_extreme", "Desequilíbrio extremo de zona", "Colorimetria", "score",
               "—", "zona em faixa vermelha (desvio extremo)", _zone_extreme),
    MarkerSpec("ipm_hyper", "Hiperativação multimodal (IPM)", "Potência multimodal", "0-100",
               "—", "ativação difusa por todas as zonas", _ipm_hyper),
    MarkerSpec("facial_contradiction", "Contradição facial-vocal (FACS)", "Dissonância facial", "AUs",
               "—", "o rosto mascara/contradiz o afeto (Unidades de Ação reais)", _facial_contradiction),
]

# TODA dissonância evidente é registrada (>= 1 marcador fora da métrica base)
# — é a decisão do produto: o profissional deve ver cada apontamento, com
# scroll e detalhamento completo, não apenas co-ocorrências.
MIN_EVIDENT = 1
# Quando >= MIN_SIMULTANEOUS marcadores em >= MIN_DISTINCT_CATEGORIES
# categorias clínicas DISTINTAS ocorrem juntos, o evento é adicionalmente
# marcado como "dissonância múltipla" — um sinal de maior confiança (a
# co-ocorrência entre sistemas diferentes é mais específica do que um único
# marcador). Categorias distintas evitam contar como "múltiplo" dois
# marcadores fortemente correlacionados da mesma categoria (ex.: jitter e
# shimmer, ambos "Perturbação vocal").
MIN_SIMULTANEOUS = 2
MIN_DISTINCT_CATEGORIES = 2
# Confirmação TEMPORAL: um evento só é "confirmado" quando a condição (haver
# ao menos uma dissonância evidente) se sustenta em CONFIRM_MIN dos últimos
# CONFIRM_WINDOW ticks (janela de 1s). Um pico de um único tick é tratado como
# transitório (não confirmado), evitando alertar sobre flutuação instantânea.
CONFIRM_WINDOW = 3
CONFIRM_MIN = 2


def read_all(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Leitura de TODOS os marcadores avaliáveis neste tick (dentro ou fora da
    banda) — usada para exibir o valor atual de cada índice com destaque
    visual quando ultrapassa a métrica base, independente de contar para o
    campo de dissonâncias (que exige o registro de fato de uma ocorrência)."""
    readings: List[Dict[str, Any]] = []
    for spec in MARKER_SPECS:
        try:
            r = spec.read(snapshot)
        except Exception:
            r = None
        if r is not None:
            readings.append(r)
    return readings


def evaluate(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Avalia todos os marcadores contra suas métricas base num tick.

    Retorna um evento com:
      - evident_markers: lista de dissonâncias evidentes (marcadores fora da banda)
      - evident_count: quantas
      - distinct_categories: nº de categorias clínicas distintas atingidas
      - has_dissonance: True se houver >= MIN_EVIDENT (1) marcador fora da
        banda — é o critério de registro no campo de dissonâncias
      - is_multi_dissonance: True se >= MIN_SIMULTANEOUS marcadores em
        >= MIN_DISTINCT_CATEGORIES categorias ocorreram juntos — destaque de
        maior confiança, não é mais o critério de registro
      - severity / mean_severity: intensidade agregada do evento (0..1)
      - categories: categorias clínicas envolvidas (distintas)
      - summary: resumo textual (preenchido sempre que has_dissonance)
    """
    breaches: List[Breach] = []
    for spec in MARKER_SPECS:
        try:
            b = spec.evaluate(snapshot)
        except Exception:
            b = None
        if b is not None:
            breaches.append(b)

    breaches.sort(key=lambda b: b.severity, reverse=True)
    categories = sorted({b.category for b in breaches})
    has_dissonance = len(breaches) >= MIN_EVIDENT
    is_multi = (
        len(breaches) >= MIN_SIMULTANEOUS
        and len(categories) >= MIN_DISTINCT_CATEGORIES
    )

    severities = [b.severity for b in breaches]
    severity = round(max(severities), 3) if severities else 0.0
    mean_severity = round(sum(severities) / len(severities), 3) if severities else 0.0

    summary = ""
    if is_multi:
        parts = [f"{b.label} ({b.direction} do limiar)" for b in breaches]
        summary = (
            f"Dissonância evidente múltipla: {len(breaches)} marcadores em "
            f"{len(categories)} categorias ultrapassaram simultaneamente a "
            f"métrica base — " + "; ".join(parts) + "."
        )
    elif has_dissonance:
        b0 = breaches[0]
        summary = (
            f"Dissonância evidente: {b0.label} {b0.direction} do limiar da "
            f"métrica base (valor {b0.value:.3f}) — {b0.interpretation}."
        )

    return {
        "evident_count": len(breaches),
        "distinct_categories": len(categories),
        "has_dissonance": has_dissonance,
        "is_multi_dissonance": is_multi,
        "min_evident": MIN_EVIDENT,
        "min_simultaneous": MIN_SIMULTANEOUS,
        "min_distinct_categories": MIN_DISTINCT_CATEGORIES,
        "severity": severity,
        "mean_severity": mean_severity,
        "categories": categories,
        "evident_markers": [b.to_dict() for b in breaches],
        # TODOS os marcadores avaliáveis neste tick (dentro ou fora da banda) —
        # alimenta painéis que exibem o valor atual de cada índice com destaque
        # visual ao ultrapassar o limiar, sem exigir uma "ocorrência" registrada.
        "all_markers": read_all(snapshot),
        "summary": summary,
        "voice_features_source": "real_pcm" if _voice_real(snapshot) else "mock",
    }


def confirm(history: List[bool]) -> bool:
    """Confirmação temporal: True se a condição (ex.: has_dissonance) se
    sustentou em CONFIRM_MIN dos últimos CONFIRM_WINDOW ticks."""
    window = history[-CONFIRM_WINDOW:]
    return sum(1 for h in window if h) >= CONFIRM_MIN
