#!/usr/bin/env python3
"""
Ingestao das fontes aprovadas na ChromaDB do FROID Explica.

Execute somente depois de revisar a curadoria gerada por
curate_knowledge_base.py. O script le apenas a pasta approved/.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path


DEFAULT_APPROVED_DIR = Path("/data/froid_sources/curated/approved")
DEFAULT_CHROMA_PATH = Path(os.getenv("FROID_CHROMA_PATH", "/data/chroma_db"))
DEFAULT_COLLECTION = os.getenv("FROID_CHROMA_COLLECTION", "froid_clinical_knowledge")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def title_from_markdown(path: Path, text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()[:180]
    return path.stem.replace("_", " ").replace("-", " ").strip()[:180]


def chunk_markdown(text: str, words_per_chunk: int, overlap: int) -> list[str]:
    clean = normalize_space(
        re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    )
    words = clean.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, words_per_chunk - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + words_per_chunk]).strip()
        if len(chunk) >= 80:
            chunks.append(chunk)
        if start + words_per_chunk >= len(words):
            break
    return chunks


def stable_id(source_path: Path, chunk_index: int, chunk: str) -> str:
    raw = f"{source_path.as_posix()}:{chunk_index}:{chunk[:240]}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def infer_area(path: Path) -> str:
    try:
      return path.parent.name
    except Exception:
      return "Geral"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestao das fontes aprovadas na ChromaDB.")
    parser.add_argument("--approved", type=Path, default=DEFAULT_APPROVED_DIR)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--words-per-chunk", type=int, default=700)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--reset", action="store_true", help="Apaga a collection antes de reindexar.")
    args = parser.parse_args()

    if not args.approved.exists():
        raise SystemExit(f"Pasta approved inexistente: {args.approved}")

    from chromadb import PersistentClient

    args.chroma_path.mkdir(parents=True, exist_ok=True)
    client = PersistentClient(path=str(args.chroma_path))
    if args.reset:
        try:
            client.delete_collection(args.collection)
        except Exception:
            pass
    collection = client.get_or_create_collection(name=args.collection)

    md_files = sorted(args.approved.rglob("*.md"))
    total_chunks = 0
    total_files = 0

    for path in md_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_markdown(text, args.words_per_chunk, args.overlap)
        if not chunks:
            continue
        title = title_from_markdown(path, text)
        area = infer_area(path)
        ids = [stable_id(path.relative_to(args.approved), index, chunk) for index, chunk in enumerate(chunks)]
        metadatas = [
            {
                "title": title,
                "source": path.name,
                "source_path": str(path),
                "area": area,
                "chunk_index": index,
                "curation_status": "approved",
            }
            for index, _ in enumerate(chunks)
        ]
        collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        total_files += 1
        total_chunks += len(chunks)

    print(f"Arquivos aprovados indexados: {total_files}")
    print(f"Chunks gravados na ChromaDB: {total_chunks}")
    print(f"Chroma path: {args.chroma_path}")
    print(f"Collection: {args.collection}")


if __name__ == "__main__":
    main()
