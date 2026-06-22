from __future__ import annotations

import hashlib
import math
import statistics
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Mapping, MutableMapping, Sequence


METRICS: tuple[dict[str, str], ...] = (
    {"key": "ipm", "label": "IPM", "unit": "indice", "category": "Indices FROID"},
    {"key": "idm", "label": "IDM", "unit": "indice", "category": "Indices FROID"},
    {"key": "subharmonics", "label": "Sub-harmonicos", "unit": "energia", "category": "Bioacustica"},
    {"key": "mfcc7", "label": "MFCC7", "unit": "coef.", "category": "Acustica"},
    {"key": "mfcc9", "label": "MFCC9", "unit": "coef.", "category": "Acustica"},
    {"key": "f0", "label": "F0", "unit": "Hz", "category": "Bioacustica"},
    {"key": "jitter", "label": "Jitter", "unit": "%", "category": "Bioacustica"},
    {"key": "shimmer", "label": "Shimmer", "unit": "%", "category": "Bioacustica"},
    {"key": "zcr", "label": "ZCR", "unit": "taxa", "category": "Bioacustica"},
    {"key": "pauses", "label": "Pausas", "unit": "s/min", "category": "Fluencia"},
    {"key": "loudness", "label": "Loudness", "unit": "LUFS", "category": "Bioacustica"},
    {"key": "words_per_minute", "label": "Palavras/min", "unit": "ppm", "category": "Fluencia"},
    {
        "key": "facial_vocal_dissonance",
        "label": "Dissonancia facial-vocal",
        "unit": "eventos",
        "category": "Indices FROID",
    },
    {"key": "clinical_risk", "label": "Risco clinico", "unit": "0-100", "category": "Triagem"},
)

METRIC_KEYS = tuple(metric["key"] for metric in METRICS)

DEFAULT_GLOBAL_PARAMETERS: dict[str, float] = {
    "coverage_min": 0.80,
    "confidence_min": 0.70,
    "z_alert": 2.0,
    "z_critical": 3.0,
    "trend_stable_pct": 0.05,
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _numbers(values: Iterable[Any] | None) -> list[float]:
    if values is None:
        return []
    result: list[float] = []
    for value in values:
        parsed = _number(value)
        if parsed is not None:
            result.append(parsed)
    return result


def percentile(values: Sequence[float], probability: float) -> float | None:
    clean = sorted(_numbers(values))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    probability = min(1.0, max(0.0, probability))
    position = (len(clean) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[lower]
    weight = position - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def safe_mean(values: Iterable[Any]) -> float | None:
    clean = _numbers(values)
    return statistics.fmean(clean) if clean else None


def safe_pct_change(current: Any, baseline: Any) -> float | None:
    current_n, baseline_n = _number(current), _number(baseline)
    if current_n is None or baseline_n in (None, 0.0):
        return None
    return (current_n - baseline_n) / baseline_n


def safe_zscore(current: Any, baseline: Any, baseline_std: Any) -> float | None:
    current_n = _number(current)
    baseline_n = _number(baseline)
    std_n = _number(baseline_std)
    if current_n is None or baseline_n is None or std_n in (None, 0.0):
        return None
    return (current_n - baseline_n) / std_n


def trend_from_delta(delta: Any, stable_pct: float = 0.05) -> str:
    value = _number(delta)
    if value is None:
        return "Sem dados"
    if abs(value) <= stable_pct:
        return "Estavel"
    return "Alta" if value > 0 else "Queda"


def _metric_stats_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})
    samples = _numbers(payload.get("samples"))
    explicit_mean = _number(payload.get("mean", payload.get("value")))
    mean = statistics.fmean(samples) if samples else explicit_mean
    median_value = statistics.median(samples) if samples else _number(payload.get("median"))
    std = statistics.pstdev(samples) if len(samples) > 1 else _number(payload.get("std"))
    minimum = min(samples) if samples else _number(payload.get("min", payload.get("minimum")))
    maximum = max(samples) if samples else _number(payload.get("max", payload.get("peak")))
    p5 = percentile(samples, 0.05) if samples else _number(payload.get("p5"))
    p95 = percentile(samples, 0.95) if samples else _number(payload.get("p95"))
    n_valid = len(samples) if samples else int(_number(payload.get("n_valid")) or 0)
    expected = int(_number(payload.get("expected_samples")) or 0)
    coverage = _number(payload.get("coverage"))
    if coverage is None and expected > 0:
        coverage = min(1.0, n_valid / expected)
    confidence = _number(payload.get("confidence"))
    return {
        "mean": mean,
        "median": median_value,
        "std": std,
        "min": minimum,
        "max": maximum,
        "p5": p5,
        "p95": p95,
        "n_valid": n_valid if n_valid > 0 else None,
        "coverage": coverage,
        "confidence": confidence,
        "source_model": payload.get("source_model"),
        "professional_validation": payload.get("professional_validation", "Pendente"),
    }


def metric_alert(
    *,
    delta_pct: Any,
    zscore: Any,
    coverage: Any,
    confidence: Any,
    config: Mapping[str, Any],
) -> str:
    coverage_n = _number(coverage)
    confidence_n = _number(confidence)
    if coverage_n is not None and coverage_n < float(config.get("coverage_min", 0.80)):
        return "Revisar qualidade"
    if confidence_n is not None and confidence_n < float(config.get("confidence_min", 0.70)):
        return "Revisar confianca"

    z = abs(_number(zscore) or 0.0)
    if z >= float(config.get("z_critical", 3.0)):
        return "Critico"
    if z >= float(config.get("z_alert", 2.0)):
        return "Alerta"
    return "Sem alerta" if (delta_pct is not None or zscore is not None) else "Sem dados"


def _merge_dict(base: MutableMapping[str, Any], incoming: Mapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in incoming.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), MutableMapping):
            _merge_dict(base[key], value)  # type: ignore[index]
        else:
            base[key] = deepcopy(value)
    return base


def empty_session(max_windows: int = 12) -> dict[str, Any]:
    return {
        "metadata": {
            "session_id": "",
            "date": "",
            "start_time": "",
            "end_time": "",
            "duration_min": None,
            "consent": "Pendente",
        },
        "baseline": {
            "metrics": {},
            "theme": "",
            "emotional_tone": "",
            "dominant_zones": "",
            "initial_risks": "",
            "initial_dissonances": "",
        },
        "windows": [
            {
                "label": f"{i * 10}-{(i + 1) * 10} min",
                "start_min": i * 10,
                "end_min": (i + 1) * 10,
                "metrics": {},
                "clinical": {},
                "quality": {},
            }
            for i in range(max_windows)
        ],
        "closure": {},
        "report": {"status": "Pendente", "version": 1, "sections": {}},
        "parameters": {"global": deepcopy(DEFAULT_GLOBAL_PARAMETERS), "metrics": {}},
        "audit": [],
    }


def normalize_session(payload: Mapping[str, Any] | None, max_windows: int = 12) -> dict[str, Any]:
    session = empty_session(max_windows)
    if payload:
        _merge_dict(session, payload)
    windows = list(session.get("windows") or [])
    normalized_windows: list[dict[str, Any]] = []
    for i in range(max_windows):
        provided = windows[i] if i < len(windows) and isinstance(windows[i], Mapping) else {}
        default_window = empty_session(max_windows)["windows"][i]
        _merge_dict(default_window, provided)
        normalized_windows.append(default_window)
    session["windows"] = normalized_windows
    globals_cfg = deepcopy(DEFAULT_GLOBAL_PARAMETERS)
    globals_cfg.update(session.get("parameters", {}).get("global") or {})
    session["parameters"]["global"] = globals_cfg
    return session


def _duration_minutes(metadata: Mapping[str, Any]) -> float | None:
    explicit = _number(metadata.get("duration_min"))
    if explicit is not None:
        return explicit
    start = metadata.get("start_time")
    end = metadata.get("end_time")
    if not start or not end:
        return None
    try:
        start_dt = datetime.fromisoformat(str(start))
        end_dt = datetime.fromisoformat(str(end))
        delta = (end_dt - start_dt).total_seconds() / 60.0
        return delta if delta >= 0 else delta + 24 * 60
    except ValueError:
        return None


def _metric_config(session: Mapping[str, Any], key: str) -> dict[str, Any]:
    cfg = dict(session["parameters"]["global"])
    metric_cfg = (session.get("parameters", {}).get("metrics") or {}).get(key) or {}
    cfg.update(metric_cfg)
    return cfg


def calculate_session(payload: Mapping[str, Any] | None, max_windows: int = 12) -> dict[str, Any]:
    session = normalize_session(payload, max_windows)
    session["metadata"]["duration_min"] = _duration_minutes(session["metadata"])
    globals_cfg = session["parameters"]["global"]

    baseline_metrics: dict[str, dict[str, Any]] = {}
    raw_baseline = session["baseline"].get("metrics") or {}
    for key in METRIC_KEYS:
        baseline_metrics[key] = _metric_stats_from_payload(raw_baseline.get(key, {}))
    session["baseline"]["metrics"] = baseline_metrics

    for window in session["windows"]:
        normalized_metrics: dict[str, dict[str, Any]] = {}
        raw_metrics = window.get("metrics") or {}
        for key in METRIC_KEYS:
            stats = _metric_stats_from_payload(raw_metrics.get(key, {}))
            baseline = baseline_metrics[key]
            stats["delta_pct"] = safe_pct_change(stats["mean"], baseline["mean"])
            stats["trend"] = trend_from_delta(stats["delta_pct"], globals_cfg["trend_stable_pct"])
            stats["zscore"] = safe_zscore(stats["mean"], baseline["mean"], baseline["std"])
            stats["alert"] = metric_alert(
                delta_pct=stats["delta_pct"],
                zscore=stats["zscore"],
                coverage=stats["coverage"],
                confidence=stats["confidence"],
                config=_metric_config(session, key),
            )
            stats["quality"] = (
                "Sem dados"
                if stats["mean"] is None
                else "Revisar"
                if stats["coverage"] is not None and stats["coverage"] < globals_cfg["coverage_min"]
                else "Revisar"
                if stats["confidence"] is not None and stats["confidence"] < globals_cfg["confidence_min"]
                else "Adequado"
            )
            normalized_metrics[key] = stats
        window["metrics"] = normalized_metrics

    session["summary"] = _summary(session)
    session["dashboard"] = _dashboard(session)
    session["evolution"] = _evolution(session)
    session["report_rendered"] = compose_report(session)
    return session


def _summary(session: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in METRIC_KEYS:
        baseline = session["baseline"]["metrics"][key]
        means = [
            window["metrics"][key]["mean"]
            for window in session["windows"]
            if _number(window["metrics"][key]["mean"]) is not None
        ]
        last = means[-1] if means else None
        result[key] = {
            "baseline": baseline.get("mean"),
            "baseline_std": baseline.get("std"),
            "session_mean": safe_mean(means),
            "last": last,
            "min": min(means) if means else None,
            "max": max(means) if means else None,
            "delta_mean": safe_pct_change(safe_mean(means), baseline.get("mean")),
            "delta_last": safe_pct_change(last, baseline.get("mean")),
            "z_last": safe_zscore(last, baseline.get("mean"), baseline.get("std")),
            "alerts": [
                window["metrics"][key]["alert"]
                for window in session["windows"]
                if window["metrics"][key]["alert"] not in ("Sem alerta", "Sem dados")
            ],
        }
    return result


def _dashboard(session: Mapping[str, Any]) -> dict[str, Any]:
    populated_windows = [
        window
        for window in session["windows"]
        if any(_number(window["metrics"][key]["mean"]) is not None for key in METRIC_KEYS)
    ]
    coverages = [
        metric.get("coverage")
        for window in populated_windows
        for metric in window["metrics"].values()
        if _number(metric.get("coverage")) is not None
    ]
    confidences = [
        metric.get("confidence")
        for window in populated_windows
        for metric in window["metrics"].values()
        if _number(metric.get("confidence")) is not None
    ]
    alerts = [
        metric.get("alert")
        for window in populated_windows
        for metric in window["metrics"].values()
        if metric.get("alert") in ("Alerta", "Critico", "Revisar qualidade", "Revisar confianca")
    ]
    clinical_risk = session["summary"]["clinical_risk"]
    dissonance = session["summary"]["facial_vocal_dissonance"]
    return {
        "populated_windows": len(populated_windows),
        "mean_coverage": safe_mean(coverages),
        "mean_confidence": safe_mean(confidences),
        "last_risk": clinical_risk.get("last"),
        "max_risk": clinical_risk.get("max"),
        "last_dissonance": dissonance.get("last"),
        "max_dissonance": dissonance.get("max"),
        "data_status": "Revisar" if any(str(a).startswith("Revisar") for a in alerts) else "Adequado",
        "critical_alerts": sum(1 for alert in alerts if alert == "Critico"),
        "alerts_count": len(alerts),
    }


def _evolution(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for window in session["windows"]:
        if not any(_number(window["metrics"][key]["mean"]) is not None for key in METRIC_KEYS):
            continue
        rows.append(
            {
                "label": window.get("label"),
                "start_min": window.get("start_min"),
                "end_min": window.get("end_min"),
                "ipm": window["metrics"]["ipm"]["mean"],
                "idm": window["metrics"]["idm"]["mean"],
                "words_per_minute": window["metrics"]["words_per_minute"]["mean"],
                "clinical_risk": window["metrics"]["clinical_risk"]["mean"],
                "facial_vocal_dissonance": window["metrics"]["facial_vocal_dissonance"]["mean"],
                "quality": _window_quality(window),
            }
        )
    return rows


def _window_quality(window: Mapping[str, Any]) -> str:
    qualities = [metric.get("quality") for metric in (window.get("metrics") or {}).values()]
    if any(item == "Revisar" for item in qualities):
        return "Revisar"
    if any(item == "Adequado" for item in qualities):
        return "Adequado"
    return "Sem dados"


def compose_report(session: Mapping[str, Any]) -> str:
    metadata = session["metadata"]
    dashboard = session["dashboard"]
    lines = [
        "RELATORIO DA CONSULTA FROID",
        f"Sessao: {metadata.get('session_id') or '--'}",
        f"Duracao: {metadata.get('duration_min') or '--'} min",
        f"Cortes com dados: {dashboard['populated_windows']}",
        f"Status dos dados: {dashboard['data_status']}",
        "",
        "Leitura evolutiva:",
    ]
    for key in ("ipm", "idm", "words_per_minute", "facial_vocal_dissonance", "clinical_risk"):
        metric = next(item for item in METRICS if item["key"] == key)
        summary = session["summary"][key]
        lines.append(
            f"- {metric['label']}: baseline={_fmt(summary['baseline'])}; "
            f"media={_fmt(summary['session_mean'])}; ultimo={_fmt(summary['last'])}; "
            f"delta={_fmt_pct(summary['delta_last'])}; z={_fmt(summary['z_last'])}."
        )
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    parsed = _number(value)
    return "--" if parsed is None else f"{parsed:.2f}"


def _fmt_pct(value: Any) -> str:
    parsed = _number(value)
    return "--" if parsed is None else f"{parsed * 100:.1f}%"


def _metric_value(value: Any, *, confidence: float | None = None, samples: list[float] | None = None) -> dict[str, Any]:
    parsed = _number(value)
    result: dict[str, Any] = {
        "mean": parsed,
        "value": parsed,
        "n_valid": len(samples or []) or (1 if parsed is not None else 0),
        "expected_samples": len(samples or []) or (1 if parsed is not None else 0),
        "coverage": 1.0 if parsed is not None else None,
        "confidence": confidence if confidence is not None else (0.90 if parsed is not None else None),
    }
    if samples:
        result["samples"] = samples
    return result


def _snapshot_metrics(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    subharmonics = safe_mean(
        [snapshot.get("subharmonic5_12"), snapshot.get("subharmonic12_20")]
    )
    return {
        "ipm": _metric_value(snapshot.get("ipmAvg")),
        "idm": _metric_value(snapshot.get("idmAvg")),
        "subharmonics": _metric_value(subharmonics),
        "mfcc7": _metric_value(snapshot.get("mfcc7")),
        "mfcc9": _metric_value(snapshot.get("mfcc9")),
        "f0": _metric_value(snapshot.get("f0Mean")),
        "jitter": _metric_value(snapshot.get("jitter")),
        "shimmer": _metric_value(snapshot.get("shimmer")),
        "zcr": _metric_value(snapshot.get("zcr")),
        "pauses": _metric_value(None),
        "loudness": _metric_value(None),
        "words_per_minute": _metric_value(snapshot.get("wordsPerMinute")),
        "facial_vocal_dissonance": _metric_value(snapshot.get("dissonanceCount")),
        "clinical_risk": _metric_value(snapshot.get("clinicalRisk")),
    }


def build_payload_from_report(report: Mapping[str, Any], max_windows: int = 12) -> dict[str, Any]:
    baseline = report.get("baseline") or {}
    cuts = list(report.get("tenMinuteCuts") or [])[:max_windows]
    created_at = str(report.get("createdAt") or "")
    duration_seconds = _number(report.get("durationSeconds")) or 0
    end_time = created_at
    start_time = ""
    try:
        if created_at:
            end_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            start_time = (end_dt.timestamp() - duration_seconds)
            start_time = datetime.fromtimestamp(start_time, tz=end_dt.tzinfo).isoformat()
    except Exception:
        start_time = ""
    return {
        "metadata": {
            "session_id": report.get("sessionId") or report.get("session_id") or "",
            "date": created_at[:10],
            "start_time": start_time,
            "end_time": end_time,
            "duration_min": duration_seconds / 60.0 if duration_seconds else None,
            "consent": "Registrado",
        },
        "baseline": {
            "metrics": _snapshot_metrics(baseline),
            "theme": baseline.get("theme") or "",
            "emotional_tone": baseline.get("emotionalTone") or "",
            "dominant_zones": baseline.get("dominantZone"),
            "initial_dissonances": baseline.get("dissonanceCount"),
        },
        "windows": [
            {
                "label": cut.get("label") or f"{index * 10}-{(index + 1) * 10} min",
                "start_min": (cut.get("startSecond") or index * 600) / 60,
                "end_min": (cut.get("endSecond") or (index + 1) * 600) / 60,
                "metrics": _snapshot_metrics(cut),
                "clinical": {
                    "theme": cut.get("theme") or "",
                    "dominant_zone": cut.get("dominantZone"),
                    "dominant_theme": cut.get("dominantTheme") or "",
                    "emotional_tone": cut.get("emotionalTone") or "",
                },
                "quality": {"metrics_coverage_pct": 1.0 if cut.get("sampleCount") else None},
            }
            for index, cut in enumerate(cuts)
        ],
        "closure": {
            "clinical_notes_count": len(report.get("clinicalNotes") or []),
            "summaries_count": len(report.get("conversationSummaries") or []),
            "relevant_dissonances_count": len(report.get("dissonances") or []),
        },
        "report": {"status": "Gerado", "version": 1},
    }


def calculate_report_metrics(report: Mapping[str, Any], max_windows: int = 12) -> dict[str, Any]:
    payload = build_payload_from_report(report, max_windows=max_windows)
    calculated = calculate_session(payload, max_windows=max_windows)
    return {
        "schema": "froid_metrics_analysis_v1",
        "metrics": METRICS,
        "payload": payload,
        "summary": calculated["summary"],
        "dashboard": calculated["dashboard"],
        "evolution": calculated["evolution"],
        "report_rendered": calculated["report_rendered"],
    }


def build_anonymous_datamart_record(report: Mapping[str, Any], salt: str) -> dict[str, Any]:
    analysis = calculate_report_metrics(report)
    session_id = str(report.get("sessionId") or report.get("session_id") or "")
    created_at = str(report.get("createdAt") or "")
    anonymous_id = hashlib.sha256(f"{salt}:{session_id}:{created_at}".encode("utf-8")).hexdigest()
    return {
        "anonymous_session_id": anonymous_id,
        "schema": "froid_anonymous_metrics_v1",
        "duration_seconds": report.get("durationSeconds"),
        "dashboard": analysis["dashboard"],
        "summary": analysis["summary"],
        "evolution": analysis["evolution"],
    }
