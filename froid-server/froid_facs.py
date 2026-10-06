"""Uma interpretação facial descritiva; AUs são proxies, não FACS certificado."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

# Limiares legados, não calibração clínica.
AU_ACTIVE_THRESHOLD = 0.30
AU_ASYMMETRY_THRESHOLD = 0.25
FACIAL_SCHEMA = "facial_families_v1"
AU_BLENDSHAPES: Dict[str, List[str]] = {
    "AU1": ["browInnerUp"],
    "AU2": ["browOuterUpLeft", "browOuterUpRight"],
    "AU4": ["browDownLeft", "browDownRight"],
    "AU5": ["eyeWideLeft", "eyeWideRight"],
    "AU6": ["cheekSquintLeft", "cheekSquintRight"],
    "AU7": ["eyeSquintLeft", "eyeSquintRight"],
    "AU9": ["noseSneerLeft", "noseSneerRight"],
    "AU10": ["mouthUpperUpLeft", "mouthUpperUpRight"],
    "AU12": ["mouthSmileLeft", "mouthSmileRight"],
    "AU14": ["mouthDimpleLeft", "mouthDimpleRight"],
    "AU15": ["mouthFrownLeft", "mouthFrownRight"],
    "AU17": ["mouthShrugLower"],
    "AU20": ["mouthStretchLeft", "mouthStretchRight"],
    # mouthRoll (rolamento labial) não equivale a apertamento AU23.
    "AU23": [],
    "AU24": ["mouthPressLeft", "mouthPressRight"],
    "AU26": ["jawOpen"],
}
AU_LATERAL = {au: tuple(names) for au, names in AU_BLENDSHAPES.items()
              if len(names) == 2 and names[0].endswith("Left")}
LEGACY_MAPPING = {**AU_BLENDSHAPES,
                  "AU17": ["mouthShrugLower", "mouthShrugUpper"],
                  "AU23": ["mouthRollLower", "mouthRollUpper"]}

# Uma fonte para regras, nomes e textos. AU25/AU27 não são inventadas.
FACIAL_FAMILIES = (
    {"id": "sorriso", "title": "Sorriso", "patterns": (("AU12",),),
     "description": "Elevação dos cantos labiais; AU6 distingue variantes observadas, não autenticidade."},
    {"id": "tristeza", "title": "Padrão compatível com tristeza",
     "patterns": (("AU1", "AU4", "AU15"), ("AU1", "AU4", "AU15", "AU17"), ("AU6", "AU15")),
     "description": "Configuração de sobrancelhas e/ou cantos labiais rebaixados."},
    {"id": "raiva", "title": "Padrão compatível com raiva",
     "patterns": (("AU4", "AU5", "AU7", "AU24"), ("AU4", "AU5", "AU7", "AU23"), ("AU4", "AU5", "AU7", "AU10", "AU23")),
     "description": "Contração de sobrancelhas, tensão palpebral e pressão labial."},
    {"id": "medo", "title": "Padrão compatível com medo",
     "patterns": (("AU1", "AU2", "AU4", "AU5", "AU20", "AU26"), ("AU5", "AU20")),
     "description": "Abertura palpebral com estiramento horizontal dos lábios."},
    {"id": "surpresa", "title": "Padrão compatível com surpresa",
     "patterns": (("AU1", "AU2", "AU5", "AU26"),),
     "description": "Elevação de sobrancelhas e pálpebras com abertura mandibular."},
    {"id": "nojo", "title": "Padrão compatível com nojo",
     "patterns": (("AU9", "AU15", "AU17"), ("AU10", "AU17")),
     "description": "Elevação nasal/labial combinada ao proxy de movimento do queixo."},
    {"id": "desprezo", "title": "Assimetria compatível com desprezo",
     "patterns": (("AU12",), ("AU14",)),
     "description": "Tração ou covinha estritamente unilateral; assimetria não comprova desprezo."},
)
LIMITATIONS = [
    "Padrões morfológicos não comprovam emoção, mentira, mascaramento ou conflito subconsciente.",
    "AUs são proxies não validados contra codificação FACS; limiares 0,30/0,25 são legados.",
    "AU23 sem mapeamento; AU25/AU27 não instrumentadas; AU17 usa mouthShrugLower como proxy.",
    "Sem confiança clínica, escala FACS A–E ou detecção certificada de ápice/microexpressão.",
    "Sem baseline neutra individual nem controle validado de pose, oclusão, iluminação e movimentos de fala.",
    "Dissonância facial-vocal não apurada: falta relação validada entre canais.",
]
PATIENT_FACIAL_TITLE = "Movimento facial observado"
PATIENT_FACIAL_DESCRIPTION = (
    "Foi observado um movimento do rosto em mais de um quadro. Esse registro "
    "não determina o que você sentiu; seu significado depende do contexto "
    "e da conversa com seu profissional."
)


def _coefficient(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and 0.0 <= number <= 1.0 else None


def _mean(blendshapes: dict, names: list) -> Optional[float]:
    values = [_coefficient(blendshapes.get(name)) for name in names]
    if not values or any(value is None for value in values):
        return None
    return round(sum(values) / len(values), 4)


def _valid_time(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def compute_action_units(blendshapes: dict) -> Dict[str, Optional[float]]:
    if not blendshapes:
        return {}
    return {au: _mean(blendshapes, names) for au, names in AU_BLENDSHAPES.items()}


def _active(aus: dict, au: str) -> bool:
    value = aus.get(au)
    return value is not None and value >= AU_ACTIVE_THRESHOLD


def _unilateral(blendshapes: dict, au: str) -> Optional[str]:
    left, right = (_coefficient(blendshapes.get(name)) for name in AU_LATERAL[au])
    if left is None or right is None or abs(left - right) < AU_ASYMMETRY_THRESHOLD:
        return None
    if left >= AU_ACTIVE_THRESHOLD and right < AU_ACTIVE_THRESHOLD:
        return "left"
    if right >= AU_ACTIVE_THRESHOLD and left < AU_ACTIVE_THRESHOLD:
        return "right"
    return None


def interpret_families(aus: dict, blendshapes: dict) -> list:
    families = []
    for spec in FACIAL_FAMILIES:
        variants = []
        measurable = False
        for pattern in spec["patterns"]:
            if all(aus.get(au) is not None for au in pattern):
                measurable = True
            if spec["id"] == "desprezo":
                side = _unilateral(blendshapes, pattern[0])
                if side:
                    variants.append({"id": f"{pattern[0]}_{side}", "aus": list(pattern), "side": side})
            elif all(_active(aus, au) for au in pattern):
                if spec["id"] == "sorriso":
                    left, right = (_coefficient(blendshapes.get(n)) for n in AU_LATERAL["AU12"])
                    if left is None or right is None or min(left, right) < AU_ACTIVE_THRESHOLD:
                        continue
                    suffix = "AU6_nao_apurada" if aus.get("AU6") is None else "com_AU6" if _active(aus, "AU6") else "sem_AU6"
                    variants.append({"id": f"sorriso_{suffix}", "aus": ["AU12", "AU6"] if _active(aus, "AU6") else ["AU12"], "side": "bilateral"})
                else:
                    variants.append({"id": "+".join(pattern), "aus": list(pattern), "side": None})
        # Variante mais completa contém a reduzida: não duplicar o mesmo padrão.
        variants = [v for v in variants if not any(
            set(v["aus"]) < set(other["aus"]) for other in variants
        )]
        families.append({"id": spec["id"], "title": spec["title"],
                         "description": spec["description"], "variants": variants,
                         "status": "candidate" if variants else "not_detected" if measurable else "unavailable",
                         "confirmed": False})
    return families


def detect_facial_dissonance(aus: dict, blendshapes: Optional[dict] = None) -> Tuple[dict, dict]:
    """Contrato legado: expressão NÃO comprova dissonância por zona."""
    return {z: False for z in range(1, 13)}, {z: None for z in range(1, 13)}


def process_facial_frame(blendshapes: Dict[str, float]) -> Dict[str, Any]:
    clean = {str(name): value for name, raw in blendshapes.items()
             if (value := _coefficient(raw)) is not None}
    aus = compute_action_units(clean)
    measured = any(value is not None for value in aus.values())
    flags, details = detect_facial_dissonance(aus)
    families = interpret_families(aus, clean)
    return {
        "schema_version": FACIAL_SCHEMA,
        "status": "measured" if measured else "unavailable",
        "reason": None if measured else "Sem capacidade de apuração: coeficientes reconhecidos ausentes ou inválidos.",
        "action_units": aus if measured else None,
        "raw_blendshapes": clean,
        "legacy_estimates": {au: _mean(clean, names) for au, names in LEGACY_MAPPING.items()},
        "lateral": {au: {"left": _coefficient(clean.get(names[0])), "right": _coefficient(clean.get(names[1]))}
                    for au, names in AU_LATERAL.items()},
        "families": families,
        "ambiguous": sum(bool(f["variants"]) for f in families) > 1,
        "limitations": list(LIMITATIONS),
        "dissonance": {"status": "unavailable", "reason": LIMITATIONS[-1]},
        "flags": flags, "details": details, "active_zones": [],
        "facs_source": "real_facs" if measured else "sem_apuracao",
    }


class FacialTracker:
    """Repetição por quadros distintos, nunca por tick/releitura de cache.

    Eventos confirmados ficam no acervo da sessão, atualizados por ID. Não se
    perde um padrão que iniciou e terminou entre dois ticks acústicos.
    """
    def __init__(self, validity_s: float, minimum_observations: int):
        self.validity_s = validity_s
        self.minimum_observations = minimum_observations
        self.current = process_facial_frame({})
        self.stream_id = None
        self.stream_started_at = None
        self.retired_streams = set()
        self.last_identity = None
        self.updated_at = None
        self.active = {}
        self.events = {}

    def _end(self, reason: str) -> None:
        for event in self.active.values():
            if event["confirmed"]:
                event["ended_at_ms"] = event["last_observed_at_ms"]
                event["end_reason"] = reason
                self.events[event["id"]] = dict(event)
        self.active = {}

    def unavailable(self, now: float, reason: str) -> None:
        self._end(reason)
        self.current = process_facial_frame({})
        self.current["reason"] = reason
        self.updated_at = None

    def expire(self, now: float) -> None:
        if self.updated_at is not None and now - self.updated_at > self.validity_s:
            self.unavailable(now, "Leitura facial vencida: nenhum quadro novo no prazo de validade.")

    def ingest(self, blendshapes: dict, frame: Optional[dict], now: float, reason: Optional[str] = None) -> bool:
        self.expire(now)
        identified = False
        if isinstance(frame, dict):
            stream = frame.get("stream_id")
            sequence = frame.get("sequence")
            captured = frame.get("captured_at_ms")
            video_time = frame.get("video_time_ms")
            stream_started = frame.get("stream_started_at_ms")
            if not (isinstance(stream, str) and 0 < len(stream) <= 128
                    and isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0
                    and all(_valid_time(v) for v in (captured, video_time, stream_started))):
                return False
            if stream in self.retired_streams:
                return False
            if stream != self.stream_id:
                if self.stream_started_at is not None and stream_started <= self.stream_started_at:
                    return False
                self._end("capture_restarted")
                if self.stream_id is not None:
                    self.retired_streams.add(self.stream_id)
                self.stream_id, self.last_identity = stream, None
                self.stream_started_at = stream_started
            elif stream_started != self.stream_started_at:
                return False
            identity = (sequence, captured, video_time)
            if self.last_identity and any(new <= old for new, old in zip(identity, self.last_identity)):
                return False
            if self.last_identity and (captured - self.last_identity[1]) / 1000 > self.validity_s:
                self._end("capture_gap")
            self.last_identity = identity
            identified = True
        elif frame is not None:
            return False
        if reason:
            self.unavailable(now, reason)
            return True
        result = process_facial_frame(blendshapes)
        if result["status"] != "measured":
            self.unavailable(now, result["reason"])
            self.current = result
            return True
        if not identified:
            self._end("frame_identity_unavailable")
            result["limitations"].append("Quadro sem identidade temporal: padrões não podem ser confirmados.")
        matching = [family for family in result["families"] if family["variants"]]
        next_active = {}
        for family in matching:
            for variant in family["variants"]:
                key = (family["id"], variant["id"])
                previous = self.active.get(key) if identified else None
                count = previous["observations"] + 1 if previous else 1
                strength = min(result["action_units"][au] for au in variant["aus"])
                if variant["side"] in ("left", "right"):
                    strength = result["lateral"][variant["aus"][0]][variant["side"]]
                event = {
                    "id": previous["id"] if previous else f"{self.stream_id}:{self.last_identity[0] if identified else 'unidentified'}:{family['id']}:{variant['id']}",
                    "schema_version": FACIAL_SCHEMA, "family": family["id"], "title": family["title"],
                    "report": family["description"] + " Padrão facial observado; não comprova estado emocional ou dissonância.",
                    "patient_title": PATIENT_FACIAL_TITLE,
                    "patient_description": PATIENT_FACIAL_DESCRIPTION,
                    "variant": variant["id"], "active_aus": variant["aus"], "side": variant["side"],
                    "started_at_ms": previous["started_at_ms"] if previous else int(now * 1000),
                    "last_observed_at_ms": int(now * 1000), "ended_at_ms": None,
                    "observations": count, "confirmed": identified and count >= self.minimum_observations,
                    "ambiguous": result["ambiguous"], "strength": strength,
                    "peak_strength": max(previous["peak_strength"], strength) if previous else strength,
                    "action_units": result["action_units"], "lateral": result["lateral"],
                    "raw_blendshapes": result["raw_blendshapes"],
                    "legacy_estimates": result["legacy_estimates"],
                    "source": "real_facs", "clinical_confidence": None,
                }
                next_active[key] = event
                if event["confirmed"]:
                    self.events[event["id"]] = dict(event)
                    family["confirmed"], family["status"] = True, "observed"
        for key, event in self.active.items():
            if key not in next_active and event["confirmed"]:
                event["ended_at_ms"] = event["last_observed_at_ms"]
                event["end_reason"] = "pattern_ended"
                self.events[event["id"]] = dict(event)
        self.active = next_active if identified else {}
        result["frame"] = frame
        result["observed_at_ms"] = int(now * 1000)
        result["expires_at_ms"] = int((now + self.validity_s) * 1000)
        self.current, self.updated_at = result, now
        return True

    def snapshot(self, now: float) -> dict:
        self.expire(now)
        return self.current

    def archive(self) -> list:
        return list(self.events.values())


def facial_event_updates(events: list, versions: dict) -> Tuple[list, dict]:
    """Delta por conexão. Reconexão com cursor vazio recebe o acervo completo."""
    updated = dict(versions)
    changes = []
    for event in events:
        version = (event["last_observed_at_ms"], event["observations"],
                   event["ended_at_ms"], event.get("end_reason"))
        if versions.get(event["id"]) != version:
            changes.append(event)
            updated[event["id"]] = version
    return changes, updated
