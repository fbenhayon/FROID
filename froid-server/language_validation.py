"""Deterministic metrics for FROID Phase 1 language-validation batches."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable

from localization import normalize_session_locale


def _normalized_words(value: object) -> list[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*", text, flags=re.UNICODE)


def _normalized_characters(value: object) -> list[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return [character for character in text if not character.isspace()]


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for reference_index, reference_item in enumerate(reference, start=1):
        current = [reference_index]
        for hypothesis_index, hypothesis_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[hypothesis_index] + 1,
                    previous[hypothesis_index - 1]
                    + (0 if reference_item == hypothesis_item else 1),
                )
            )
        previous = current
    return previous[-1]


def word_error_rate(reference: object, hypothesis: object) -> float | None:
    reference_words = _normalized_words(reference)
    if not reference_words:
        return None
    return edit_distance(reference_words, _normalized_words(hypothesis)) / len(reference_words)


def character_error_rate(reference: object, hypothesis: object) -> float | None:
    reference_characters = _normalized_characters(reference)
    if not reference_characters:
        return None
    return edit_distance(reference_characters, _normalized_characters(hypothesis)) / len(
        reference_characters
    )


def critical_term_recall(
    reference: object,
    hypothesis: object,
    critical_terms: Iterable[object],
) -> tuple[int, int]:
    reference_text = " ".join(_normalized_words(reference))
    hypothesis_text = " ".join(_normalized_words(hypothesis))
    expected = []
    for term in critical_terms or []:
        normalized = " ".join(_normalized_words(term))
        if normalized and normalized in reference_text:
            expected.append(normalized)
    matched = sum(1 for term in expected if term in hypothesis_text)
    return matched, len(expected)


def percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    position = (len(ordered) - 1) * min(1.0, max(0.0, quantile))
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _rate(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def evaluate_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        groups[normalize_session_locale(record.get("locale"))].append(record)

    locale_results: dict[str, dict[str, Any]] = {}
    for locale, items in sorted(groups.items()):
        word_errors: list[float] = []
        character_errors: list[float] = []
        latencies: list[float] = []
        term_matches = 0
        term_expected = 0
        status_counts: dict[str, int] = defaultdict(int)
        subgroup_word_errors: dict[str, list[float]] = defaultdict(list)

        for item in items:
            reference = item.get("reference") or ""
            hypothesis = item.get("hypothesis") or ""
            wer = word_error_rate(reference, hypothesis)
            cer = character_error_rate(reference, hypothesis)
            if wer is not None:
                word_errors.append(wer)
            if cer is not None:
                character_errors.append(cer)
            matched, expected = critical_term_recall(
                reference,
                hypothesis,
                item.get("critical_terms") or [],
            )
            term_matches += matched
            term_expected += expected
            status = str(item.get("status") or "ok").strip().lower()
            status_counts[status] += 1
            try:
                latency = float(item.get("latency_ms"))
                if math.isfinite(latency) and latency >= 0:
                    latencies.append(latency)
            except (TypeError, ValueError):
                pass
            for key, value in sorted((item.get("subgroups") or {}).items()):
                if wer is not None and str(value or "").strip():
                    subgroup_word_errors[f"{key}:{value}"].append(wer)

        mean_wer = sum(word_errors) / len(word_errors) if word_errors else None
        subgroup_means = {
            name: round(sum(values) / len(values), 6)
            for name, values in sorted(subgroup_word_errors.items())
            if values
        }
        subgroup_gap = (
            max(subgroup_means.values()) - min(subgroup_means.values())
            if len(subgroup_means) > 1
            else 0.0
        )
        total = len(items)
        locale_results[locale] = {
            "records": total,
            "wer": round(mean_wer, 6) if mean_wer is not None else None,
            "cer": round(sum(character_errors) / len(character_errors), 6)
            if character_errors
            else None,
            "critical_term_recall": round(term_matches / term_expected, 6)
            if term_expected
            else None,
            "critical_terms_matched": term_matches,
            "critical_terms_expected": term_expected,
            "empty_rate": _rate(status_counts.get("empty", 0), total),
            "truncated_rate": _rate(status_counts.get("truncated", 0), total),
            "duplicated_rate": _rate(status_counts.get("duplicated", 0), total),
            "delayed_rate": _rate(status_counts.get("delayed", 0), total),
            "latency_ms_p50": round(percentile(latencies, 0.50), 3)
            if latencies
            else None,
            "latency_ms_p95": round(percentile(latencies, 0.95), 3)
            if latencies
            else None,
            "subgroup_wer": subgroup_means,
            "subgroup_wer_absolute_gap": round(subgroup_gap, 6),
        }

    return {
        "schema": "froid_language_validation_v1",
        "locales": locale_results,
        "records": sum(result["records"] for result in locale_results.values()),
    }
