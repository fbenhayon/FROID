"""
Motor FACS (Facial Action Coding System) REAL do FROID.

Substitui as marcações faciais simuladas por marcações REAIS derivadas da
face do paciente. O navegador computa, quadro a quadro, os coeficientes de
blendshape faciais (MediaPipe FaceLandmarker / ARKit, 52 formas) e os envia ao
servidor; aqui eles são convertidos em INTENSIDADES de Unidades de Ação (AUs)
do FACS e, a partir das AUs, em DISSONÂNCIAS FACIAIS por Zona de Percepção.

Só marcações reais: se não há blendshapes medidos, nada é inventado — o motor
não emite AU alguma (o motor de tick então recai no comportamento simulado
explícito, sinalizado como tal). Quando há blendshapes reais, as AUs e as
dissonâncias faciais passam a refletir o rosto de fato.

MAPA BLENDSHAPE -> AU
---------------------
O padrão ARKit/MediaPipe expõe 52 blendshapes cujos nomes têm correspondência
consolidada na literatura com as Unidades de Ação do FACS de Ekman. Left/Right
são combinados (média) para a intensidade bilateral da AU; a assimetria é
preservada à parte para AUs de desprezo (unilaterais).

Somente aritmética simples e determinística — sem dependências externas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Intensidade mínima de blendshape para considerar uma AU "ativa" (presente).
# Blendshapes ARKit são escalas 0..1; 0,30 é um limiar de presença conservador
# que evita ruído de micro-movimentos involuntários.
AU_ACTIVE_THRESHOLD = 0.30

# Assimetria mínima (|esq - dir|) para caracterizar uma AU unilateral (desprezo).
AU_ASYMMETRY_THRESHOLD = 0.25

# Mapa AU -> lista de blendshapes que a compõem (média das intensidades).
# Nomes conforme MediaPipe FaceLandmarker (categorias ARKit).
AU_BLENDSHAPES: Dict[str, List[str]] = {
    "AU1": ["browInnerUp"],                              # Inner brow raiser
    "AU2": ["browOuterUpLeft", "browOuterUpRight"],      # Outer brow raiser
    "AU4": ["browDownLeft", "browDownRight"],            # Brow lowerer
    "AU5": ["eyeWideLeft", "eyeWideRight"],              # Upper lid raiser
    "AU6": ["cheekSquintLeft", "cheekSquintRight"],      # Cheek raiser
    "AU7": ["eyeSquintLeft", "eyeSquintRight"],          # Lid tightener
    "AU9": ["noseSneerLeft", "noseSneerRight"],          # Nose wrinkler
    "AU10": ["mouthUpperUpLeft", "mouthUpperUpRight"],   # Upper lip raiser
    "AU12": ["mouthSmileLeft", "mouthSmileRight"],       # Lip corner puller
    "AU14": ["mouthDimpleLeft", "mouthDimpleRight"],     # Dimpler (desprezo)
    "AU15": ["mouthFrownLeft", "mouthFrownRight"],       # Lip corner depressor
    "AU17": ["mouthShrugLower", "mouthShrugUpper"],      # Chin raiser
    "AU20": ["mouthStretchLeft", "mouthStretchRight"],   # Lip stretcher
    "AU23": ["mouthRollLower", "mouthRollUpper"],        # Lip tightener
    "AU24": ["mouthPressLeft", "mouthPressRight"],       # Lip pressor
    "AU26": ["jawOpen"],                                 # Jaw drop
}

# AUs unilaterais laterais (para detectar desprezo por assimetria).
AU_LATERAL: Dict[str, Tuple[str, str]] = {
    "AU12": ("mouthSmileLeft", "mouthSmileRight"),
    "AU14": ("mouthDimpleLeft", "mouthDimpleRight"),
}


def _bs(blendshapes: Dict[str, float], name: str) -> float:
    try:
        return float(blendshapes.get(name, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def compute_action_units(blendshapes: Dict[str, float]) -> Dict[str, float]:
    """Converte blendshapes ARKit/MediaPipe em intensidades de AU (0..1)."""
    aus: Dict[str, float] = {}
    if not blendshapes:
        return aus
    for au, names in AU_BLENDSHAPES.items():
        vals = [_bs(blendshapes, n) for n in names]
        if not vals:
            continue
        aus[au] = round(float(sum(vals) / len(vals)), 4)
    return aus


def _asymmetry(blendshapes: Dict[str, float], au: str) -> float:
    pair = AU_LATERAL.get(au)
    if not pair:
        return 0.0
    return abs(_bs(blendshapes, pair[0]) - _bs(blendshapes, pair[1]))


def _active(aus: Dict[str, float], au: str) -> bool:
    return aus.get(au, 0.0) >= AU_ACTIVE_THRESHOLD


# --------------------------------------------------------------------------
# Regras de DISSONÂNCIA FACIAL por Zona de Percepção.
#
# A dissonância facial no FROID é o rosto CONTRADIZENDO/MASCARANDO o afeto:
# co-ocorrência de AUs incompatíveis (ex.: sorriso social sobre lábios
# comprimidos = aversão suprimida). Cada regra mapeia um padrão facial validado
# a uma zona. Só dispara com AUs reais acima do limiar de presença.
# --------------------------------------------------------------------------

def detect_facial_dissonance(
    aus: Dict[str, float], blendshapes: Optional[Dict[str, float]] = None
) -> Tuple[Dict[int, bool], Dict[int, Optional[dict]]]:
    """Deriva flags e detalhes de dissonância facial por zona (1..12)."""
    flags: Dict[int, bool] = {z: False for z in range(1, 13)}
    details: Dict[int, Optional[dict]] = {z: None for z in range(1, 13)}
    blendshapes = blendshapes or {}

    def set_zone(zone: int, active_aus: List[str], report: str, intensity: float):
        # Preserva a dissonância de maior intensidade quando a mesma zona é
        # candidata por mais de uma regra.
        prev = details[zone]
        if prev is not None and float(prev.get("intensity", 0.0)) >= intensity:
            return
        flags[zone] = True
        details[zone] = {
            "active_aus": active_aus,
            "report": report,
            "intensity": round(float(intensity), 3),
            "source": "real_facs",
        }

    # Zona 7 — Raiva vs. Aceitação da Mudança: sorriso social (AU12) sobre
    # compressão/aperto labial (AU23/AU24) = supressão de aversão.
    if _active(aus, "AU12") and (_active(aus, "AU23") or _active(aus, "AU24")):
        press = max(aus.get("AU23", 0.0), aus.get("AU24", 0.0))
        used = ["AU12"] + (["AU23"] if _active(aus, "AU23") else []) + (
            ["AU24"] if _active(aus, "AU24") else []
        )
        set_zone(
            7, used,
            "Supressão de Aversão: sorriso social sobreposto a compressão labial "
            "involuntária — o rosto mascara a hostilidade.",
            min(aus["AU12"], press),
        )

    # Zona 12 — Crenças e Ações Conflitantes: franzir de sobrancelhas (AU4) com
    # olhos semicerrados (AU7) durante fala neutra = conflito interno.
    if _active(aus, "AU4") and _active(aus, "AU7"):
        set_zone(
            12, ["AU4", "AU7"],
            "Conflito interno: sobrancelhas contraídas com pálpebras tensionadas "
            "— incongruência entre discurso e estado.",
            min(aus["AU4"], aus["AU7"]),
        )

    # Zona 3 — Tristeza vs. Paz Interior: cantos da boca em queda (AU15) sob
    # tentativa de sorriso (AU12) = tristeza mascarada.
    if _active(aus, "AU15") and _active(aus, "AU12"):
        set_zone(
            3, ["AU15", "AU12"],
            "Tristeza mascarada: depressão dos cantos labiais sob esforço de "
            "sorriso — afeto negativo encoberto.",
            min(aus["AU15"], aus["AU12"]),
        )

    # Zona 8 — Medo e Sobrecarga: elevação interna+externa de sobrancelhas
    # (AU1+AU2) com pálpebra superior elevada (AU5) = medo contido.
    if _active(aus, "AU1") and _active(aus, "AU2") and _active(aus, "AU5"):
        set_zone(
            8, ["AU1", "AU2", "AU5"],
            "Medo contido: assinatura de sobrancelhas e pálpebras de sobressalto "
            "durante fala controlada.",
            min(aus["AU1"], aus["AU2"], aus["AU5"]),
        )

    # Zona 6 — Amor Condicional vs. Incondicional: covinha/canto unilateral
    # (AU14 assimétrico) ou elevação de lábio superior (AU10) = desprezo.
    asym14 = _asymmetry(blendshapes, "AU14")
    asym12 = _asymmetry(blendshapes, "AU12")
    if (_active(aus, "AU14") and asym14 >= AU_ASYMMETRY_THRESHOLD) or (
        _active(aus, "AU10") and asym12 >= AU_ASYMMETRY_THRESHOLD
    ):
        set_zone(
            6, ["AU14"] if _active(aus, "AU14") else ["AU10"],
            "Desprezo: expressão facial unilateral (assimetria) — distanciamento "
            "afetivo mascarado.",
            max(aus.get("AU14", 0.0), aus.get("AU10", 0.0)),
        )

    # Zona 9 — Expressão Emocional Suprimida: aperto+compressão labial
    # (AU23+AU24) com rosto globalmente inexpressivo = contenção expressiva.
    expressivity = _global_expressivity(aus)
    if _active(aus, "AU23") and _active(aus, "AU24") and expressivity < 0.20:
        set_zone(
            9, ["AU23", "AU24"],
            "Supressão expressiva: lábios pressionados e tensos com face "
            "aplainada — retenção do que seria dito.",
            min(aus["AU23"], aus["AU24"]),
        )

    # Remove o campo interno "intensity" do payload público (uso apenas de
    # priorização), mantendo o contrato existente (active_aus, report, source).
    for z, d in details.items():
        if d is not None:
            d.pop("intensity", None)
    return flags, details


def _global_expressivity(aus: Dict[str, float]) -> float:
    """Média de intensidade das AUs EMOCIONAIS — proxy de quão animado está o
    rosto. Baixa expressividade + AUs de contenção indica supressão. AU26
    (abertura de mandíbula) é excluída por ser dirigida pela FALA, não pela
    emoção — incluí-la inflava a expressividade durante o discurso e mascarava
    a contenção justamente quando ela é mais relevante."""
    expressive = ["AU1", "AU2", "AU5", "AU6", "AU12", "AU15"]
    vals = [aus.get(a, 0.0) for a in expressive]
    return float(sum(vals) / len(vals)) if vals else 0.0


def process_facial_frame(
    blendshapes: Dict[str, float]
) -> Dict[str, Any]:
    """Pipeline completo: blendshapes reais -> AUs -> dissonâncias faciais."""
    aus = compute_action_units(blendshapes)
    flags, details = detect_facial_dissonance(aus, blendshapes)
    active_zones = [z for z, f in flags.items() if f]
    return {
        "action_units": aus,
        "flags": flags,
        "details": details,
        "active_zones": active_zones,
        "facs_source": "real_facs" if aus else "none",
    }
