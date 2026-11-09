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
    "Referência facial individual (60 s iniciais) em modo de medição: ainda não filtra nem classifica padrões; sem controle validado de pose, oclusão, iluminação e movimentos de fala.",
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


# REFERÊNCIA FACIAL INDIVIDUAL — MODO DE MEDIÇÃO (decisão do dono, 08/11/2026).
#
# Os limiares absolutos 0,30/0,25 tratam todo rosto igual: um paciente com
# AU4 em 0,37 em repouso (sobrancelha baixa, óculos, luz) fica sempre "ativo",
# e movimentos sutis de outro nunca chegam a 0,30. A régua certa é a do próprio
# paciente, com a mesma disciplina da voz (`_update_activation_reference` em
# froid_core.py): mediana e MAD dos 60 s iniciais, imunes a um evento isolado.
#
# Esta fase NÃO filtra nem reclassifica nada. Ela só mede quanto cada AU se
# afasta da referência, para que o limiar seja escolhido a partir de sessões
# reais, e não chutado (skill mestre, §1.1). Quando o limiar existir, ele vira
# uma constante com a origem documentada, e só então o relatório passa a omitir
# o que ficar abaixo dele.
FACE_BASELINE_WINDOW_S = 60.0  # a mesma janela de calibração da voz
# Mínimo OPERACIONAL, não clínico: 10 s de rosto medido à cadência de 3 Hz.
# Abaixo disso a mediana é de poucos quadros e a referência se declara
# insuficiente. O número de quadros sai publicado, para que a análise do
# limiar possa descartar calibrações curtas com o critério que os dados pedirem.
FACE_BASELINE_MIN_FRAMES = 30
# Histograma do afastamento (valor - mediana), que vai de -1 a +1 porque os
# coeficientes vivem em [0, 1]. Passo de 0,01: memória constante numa sessão
# longa e percentis com resolução de um centésimo.
_HIST_STEP = 0.01
_HIST_BINS = 201
_PERCENTILES = (50, 90, 95, 99)


class FacialBaseline:
    def __init__(self):
        self.started_at: Optional[float] = None
        self.samples: Dict[str, List[float]] = {au: [] for au in AU_BLENDSHAPES}
        self.frames = 0
        self.status = "waiting"  # waiting | calibrating | ready | insufficient
        self.reference: Dict[str, Optional[dict]] = {}
        self.histograms: Dict[str, List[int]] = {}
        self.max_delta: Dict[str, Optional[float]] = {}
        self.measured_frames = 0

    def _close(self) -> None:
        if self.frames < FACE_BASELINE_MIN_FRAMES:
            self.status = "insufficient"
        else:
            self.status = "ready"
            for au, values in self.samples.items():
                if not values:
                    self.reference[au] = None
                    continue
                arr = sorted(values)
                n = len(arr)
                median = (arr[n // 2] if n % 2 else (arr[n // 2 - 1] + arr[n // 2]) / 2)
                deviations = sorted(abs(v - median) for v in arr)
                mad = (deviations[n // 2] if n % 2 else (deviations[n // 2 - 1] + deviations[n // 2]) / 2)
                self.reference[au] = {"median": round(median, 4), "scale": round(mad * 1.4826, 4), "frames": n}
                self.histograms[au] = [0] * _HIST_BINS
                self.max_delta[au] = None
        self.samples = {au: [] for au in AU_BLENDSHAPES}

    def observe(self, aus: dict, now: float) -> Dict[str, Optional[float]]:
        """Recebe um quadro MEDIDO. Devolve o afastamento de cada AU em relação
        à referência (None enquanto ela não existe ou quando a AU não foi
        medida — nunca zero por ausência)."""
        if self.started_at is None:
            self.started_at = now
            self.status = "calibrating"
        if self.status == "calibrating":
            if now - self.started_at <= FACE_BASELINE_WINDOW_S:
                self.frames += 1
                for au, value in aus.items():
                    if value is not None and au in self.samples:
                        self.samples[au].append(float(value))
                return {au: None for au in aus}
            self._close()
        if self.status != "ready":
            return {au: None for au in aus}
        self.measured_frames += 1
        deltas: Dict[str, Optional[float]] = {}
        for au, value in aus.items():
            ref = self.reference.get(au)
            if value is None or ref is None:
                deltas[au] = None
                continue
            delta = float(value) - ref["median"]
            deltas[au] = round(delta, 4)
            index = min(_HIST_BINS - 1, max(0, int(round((delta + 1.0) / _HIST_STEP))))
            self.histograms[au][index] += 1
            prev = self.max_delta[au]
            self.max_delta[au] = delta if prev is None else max(prev, delta)
        return deltas

    def summary(self) -> dict:
        # Todas as 16 AUs constam: a que não tem referência aparece como None,
        # declarada, em vez de sumir do resumo.
        deviation = {}
        for au in AU_BLENDSHAPES:
            hist = self.histograms.get(au)
            total = sum(hist) if hist else 0
            if not total:
                deviation[au] = None
                continue
            out = {"frames": total}
            for p in _PERCENTILES:
                target, acc = total * p / 100.0, 0
                for i, count in enumerate(hist):
                    acc += count
                    if acc >= target:
                        out[f"p{p}"] = round(i * _HIST_STEP - 1.0, 2)
                        break
            out["max"] = round(self.max_delta[au], 4) if self.max_delta[au] is not None else None
            deviation[au] = out
        return {
            "schema_version": "facial_baseline_v1",
            "mode": "measurement_only",
            "status": self.status,
            "window_s": FACE_BASELINE_WINDOW_S,
            "min_frames": FACE_BASELINE_MIN_FRAMES,
            "calibration_frames": self.frames,
            "frames_after_calibration": self.measured_frames,
            "reference": self.reference if self.status == "ready" else None,
            "deviation": deviation if self.status == "ready" else None,
            "threshold": None,
            "threshold_reason": "Limiar ainda não definido: em medição para ser escolhido a partir de sessões reais.",
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
        self.baseline = FacialBaseline()

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
        deltas = self.baseline.observe(result["action_units"], now)
        result["baseline_delta"] = deltas
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
                # Afastamento da referência individual. Variante unilateral
                # mede um lado só, e a referência é da média dos dois lados:
                # comparar os dois seria inventar uma régua, então fica None.
                variant_deltas = {au: deltas.get(au) for au in variant["aus"]}
                if variant["side"] in ("left", "right") or any(v is None for v in variant_deltas.values()):
                    delta_strength = None
                else:
                    delta_strength = min(variant_deltas.values())
                previous_peak = previous.get("peak_baseline_delta") if previous else None
                if delta_strength is None:
                    peak_delta = previous_peak
                elif previous_peak is None:
                    peak_delta = delta_strength
                else:
                    peak_delta = max(previous_peak, delta_strength)
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
                    "baseline_delta": variant_deltas, "baseline_delta_strength": delta_strength,
                    "peak_baseline_delta": peak_delta,
                    "baseline_status": self.baseline.status,
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
        return {**self.current, "facial_baseline": self.baseline.summary()}

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
