#!/usr/bin/env python3
"""
Curadoria automatica das fontes FROID em Markdown.

O script nunca apaga as fontes brutas. Ele copia cada arquivo para uma das
pastas de curadoria, calcula hashes, classifica por assunto, detecta duplicatas
exatas/proximas e sinaliza possivel obsolescencia ou conflito.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


DEFAULT_SOURCE_DIR = Path("/data/froid_sources/raw_md")
DEFAULT_OUTPUT_DIR = Path("/data/froid_sources/curated")

AREA_KEYWORDS: dict[str, list[str]] = {
    "LGPD": [
        "lgpd",
        "lei geral de protecao de dados",
        "lei 13.709",
        "anpd",
        "consentimento",
        "dados sensiveis",
        "titular dos dados",
        "ripd",
        "dpo",
    ],
    "FACS_AUS": [
        "facs",
        "action unit",
        "unidade de acao",
        "au12",
        "au15",
        "au20",
        "duchenne",
        "landmarks",
        "microexpressao",
    ],
    "Bioacustica": [
        "bioacustica",
        "voz",
        "mfcc",
        "mfcc7",
        "mfcc9",
        "f0",
        "jitter",
        "shimmer",
        "zcr",
        "pitch",
    ],
    "Sub_harmonicos": [
        "sub-harmonico",
        "sub harmonico",
        "infrassom",
        "5-12",
        "12-20",
        "85-165",
        "tremor sna",
        "flooding",
        "shutdown",
    ],
    "IPM_IDM": [
        "ipm",
        "idm",
        "indice de potencia motivacional",
        "indice de desvio multimodal",
        "linha de base",
        "baseline",
        "m_fac",
    ],
    "Riscos_clinicos": [
        "phq-9",
        "hamd",
        "ymrs",
        "depressao",
        "ansiedade",
        "mania",
        "estresse cognitivo",
        "dissociacao",
        "trauma",
    ],
    "Zonas_FROID": [
        "zona",
        "zonas froid",
        "mapa zonal",
        "evox",
        "perception index",
        "crencas",
        "raiva",
        "tristeza",
    ],
    "STT_IA": [
        "stt",
        "speech to text",
        "transcricao",
        "gpt-4o-transcribe",
        "gemini",
        "rag",
        "chroma",
        "llm",
    ],
    "Notas_tecnicas_FROID": [
        "froid",
        "frequency recognition",
        "nota tecnica",
        "arquitetura",
        "dashboard",
        "pipeline",
        "algoritmo",
    ],
}

OBSOLETE_PATTERNS = [
    r"\bobsoleto\b",
    r"\bdeprecated\b",
    r"\bsubstitu[ií]d[oa]\b",
    r"\bvers[aã]o antiga\b",
    r"\bnao utilizar\b",
    r"\bdescontinuad[oa]\b",
    r"\brascunho\b",
    r"\bdraft\b",
    r"\bv0\b",
    r"\bv1\b",
]

PRIMARY_SOURCE_PATTERNS = [
    r"\bfonte prim[aá]ria\b",
    r"\bartigo cient[ií]fico\b",
    r"\bpublica[cç][aã]o\b",
    r"\bdoi\b",
    r"\bpubmed\b",
    r"\bpeer[- ]reviewed\b",
    r"\blei\b",
]

ASSERTIVE_PATTERNS = [
    r"\bobrigat[oó]rio\b",
    r"\bdeve\b",
    r"\bn[aã]o deve\b",
    r"\blimiar\b",
    r"\bthreshold\b",
    r"\bf[oó]rmula\b",
    r"\bequa[cç][aã]o\b",
    r"\bprotocolo\b",
]


@dataclass
class SourceRecord:
    source_path: str
    output_path: str
    title: str
    area: str
    status: str
    confidence: int
    exact_hash: str
    normalized_hash: str
    simhash: str
    word_count: int
    duplicate_of: str
    similarity: float
    reasons: str


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\u00c0-\u017f\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9\u00c0-\u017f]{3,}", normalize_text(text))


def title_from_markdown(path: Path, text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()[:180]
    return path.stem.replace("_", " ").replace("-", " ").strip()[:180]


def classify_area(text: str, filename: str) -> tuple[str, dict[str, int]]:
    haystack = f"{filename}\n{text}".lower()
    scores: dict[str, int] = {}
    for area, keywords in AREA_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in haystack:
                score += 2 if keyword.lower() in filename.lower() else 1
        scores[area] = score
    best_area, best_score = max(scores.items(), key=lambda item: item[1])
    return (best_area if best_score > 0 else "Geral"), scores


def suspicious_obsolete(text: str, filename: str) -> list[str]:
    haystack = f"{filename}\n{text}".lower()
    reasons = []
    for pattern in OBSOLETE_PATTERNS:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            reasons.append(f"obsolete_pattern:{pattern}")
    return reasons


def confidence_score(text: str, area: str, area_scores: dict[str, int]) -> tuple[int, list[str]]:
    tokens = word_tokens(text)
    score = 45
    reasons = [f"area:{area}"]
    if len(tokens) >= 250:
        score += 10
        reasons.append("conteudo_suficiente")
    elif len(tokens) < 80:
        score -= 20
        reasons.append("conteudo_curto")
    if area != "Geral":
        score += min(20, area_scores.get(area, 0) * 2)
    primary_hits = sum(1 for pattern in PRIMARY_SOURCE_PATTERNS if re.search(pattern, text, re.I))
    if primary_hits:
        score += min(20, primary_hits * 5)
        reasons.append("fonte_primaria_ou_cientifica")
    obsolete_hits = suspicious_obsolete(text, "")
    if obsolete_hits:
        score -= min(35, len(obsolete_hits) * 12)
        reasons.extend(obsolete_hits)
    return max(0, min(100, score)), reasons


def fingerprint(tokens: Iterable[str], size: int = 80) -> str:
    counter = Counter(tokens)
    common = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:size]
    return " ".join(word for word, _ in common)


def copy_to_bucket(source: Path, output_dir: Path, status: str, area: str) -> Path:
    safe_area = re.sub(r"[^A-Za-z0-9_.-]+", "_", area) or "Geral"
    target_dir = output_dir / status / safe_area
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        counter = 2
        while target.exists():
            target = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.copy2(source, target)
    return target


def likely_conflict(current: dict, previous: dict, similarity: float) -> bool:
    if current["area"] != previous["area"]:
        return False
    if similarity < 0.68 or similarity >= 0.92:
        return False
    current_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?%?\b", current["normalized"]))
    previous_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?%?\b", previous["normalized"]))
    numeric_conflict = bool(current_numbers and previous_numbers and current_numbers != previous_numbers)
    current_assertive = any(re.search(pattern, current["normalized"], re.I) for pattern in ASSERTIVE_PATTERNS)
    previous_assertive = any(re.search(pattern, previous["normalized"], re.I) for pattern in ASSERTIVE_PATTERNS)
    return numeric_conflict and current_assertive and previous_assertive


def curate_sources(source_dir: Path, output_dir: Path, similarity_threshold: float) -> list[SourceRecord]:
    if not source_dir.exists():
        raise SystemExit(f"Fonte inexistente: {source_dir}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    for bucket in [
        "approved",
        "quarantine_duplicates",
        "quarantine_obsolete",
        "quarantine_conflicts",
        "quarantine_low_confidence",
    ]:
        (output_dir / bucket).mkdir(parents=True, exist_ok=True)

    md_files = sorted(source_dir.rglob("*.md"))
    seen_hash: dict[str, dict] = {}
    seen_any_hash: dict[str, dict] = {}
    candidates_by_area: dict[str, list[dict]] = defaultdict(list)
    records: list[SourceRecord] = []

    for path in md_files:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        normalized = normalize_text(raw)
        tokens = word_tokens(raw)
        area, area_scores = classify_area(raw, path.name)
        title = title_from_markdown(path, raw)
        exact_hash = content_hash(raw)
        normalized_hash = content_hash(normalized)
        simhash = content_hash(fingerprint(tokens))
        confidence, reasons = confidence_score(raw, area, area_scores)
        status = "approved"
        duplicate_of = ""
        similarity = 0.0

        current = {
            "path": path,
            "title": title,
            "area": area,
            "normalized": normalized,
            "normalized_hash": normalized_hash,
            "confidence": confidence,
        }

        if normalized_hash in seen_any_hash:
            status = "quarantine_duplicates"
            duplicate_of = str(seen_any_hash[normalized_hash]["path"])
            similarity = 1.0
            reasons.append("duplicata_exata_normalizada")
        else:
            best_match = None
            best_similarity = 0.0
            for candidate in candidates_by_area[area]:
                if not normalized or not candidate["normalized"]:
                    continue
                ratio = SequenceMatcher(None, normalized[:12000], candidate["normalized"][:12000]).ratio()
                if ratio > best_similarity:
                    best_similarity = ratio
                    best_match = candidate
            if best_match and best_similarity >= similarity_threshold:
                status = "quarantine_duplicates"
                duplicate_of = str(best_match["path"])
                similarity = round(best_similarity, 4)
                reasons.append("duplicata_proxima")
            elif best_match and likely_conflict(current, best_match, best_similarity):
                status = "quarantine_conflicts"
                duplicate_of = str(best_match["path"])
                similarity = round(best_similarity, 4)
                reasons.append("possivel_conflito_numerico_normativo")
            elif suspicious_obsolete(raw, path.name):
                status = "quarantine_obsolete"
            elif confidence < 45:
                status = "quarantine_low_confidence"

        target = copy_to_bucket(path, output_dir, status, area)
        records.append(
            SourceRecord(
                source_path=str(path),
                output_path=str(target),
                title=title,
                area=area,
                status=status,
                confidence=confidence,
                exact_hash=exact_hash,
                normalized_hash=normalized_hash,
                simhash=simhash,
                word_count=len(tokens),
                duplicate_of=duplicate_of,
                similarity=similarity,
                reasons="; ".join(reasons),
            )
        )
        if status == "approved":
            seen_hash[normalized_hash] = current
            candidates_by_area[area].append(current)
        seen_any_hash.setdefault(normalized_hash, current)

    write_reports(output_dir, records)
    return records


def write_reports(output_dir: Path, records: list[SourceRecord]) -> None:
    csv_path = output_dir / "curation_report.csv"
    json_path = output_dir / "curation_report.json"
    md_path = output_dir / "curation_report.md"

    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(asdict(records[0]).keys()) if records else [])
        if records:
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))

    json_path.write_text(
        json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_status = Counter(record.status for record in records)
    by_area = Counter(record.area for record in records)
    lines = [
        "# Relatorio de curadoria FROID",
        "",
        f"Total de arquivos analisados: {len(records)}",
        "",
        "## Por status",
    ]
    for status, count in sorted(by_status.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Por area"])
    for area, count in sorted(by_area.items()):
        lines.append(f"- {area}: {count}")
    lines.extend(["", "## Itens que exigem revisao"])
    review = [record for record in records if record.status != "approved"]
    if not review:
        lines.append("- Nenhum item em quarentena.")
    else:
        for record in review[:200]:
            lines.append(
                f"- {record.status} | {record.area} | {record.title} | "
                f"conf={record.confidence} | {Path(record.source_path).name} | {record.reasons}"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Curadoria automatica das fontes FROID em Markdown.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--similarity-threshold", type=float, default=0.92)
    args = parser.parse_args()

    records = curate_sources(args.source, args.output, args.similarity_threshold)
    counts = Counter(record.status for record in records)
    print(f"Fontes analisadas: {len(records)}")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    print(f"Relatorios: {args.output / 'curation_report.md'}")


if __name__ == "__main__":
    main()
