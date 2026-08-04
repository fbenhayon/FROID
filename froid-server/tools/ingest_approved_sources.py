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
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import explica_embeddings  # noqa: E402

REPO_APPROVED_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "approved"
VOLUME_APPROVED_DIR = Path("/data/froid_sources/curated/approved")
DEFAULT_APPROVED_DIR = Path(
    os.getenv(
        "FROID_APPROVED_KNOWLEDGE_DIR",
        str(VOLUME_APPROVED_DIR if VOLUME_APPROVED_DIR.exists() else REPO_APPROVED_DIR),
    )
)


def default_sources() -> list[Path]:
    """Pastas a indexar quando nenhuma e informada explicitamente.

    Antes o script escolhia UMA: o volume, se existisse, senao o repositorio.
    Na pratica isso descartava em silencio toda nota versionada em git, porque
    em producao o volume existe. Uma nota podia ser escrita, revisada,
    publicada e nunca chegar ao FROID Explica, sem erro nenhum — so nao
    aparecia nas respostas.

    Agora as duas sao indexadas. O volume guarda o material curado que nao
    cabe no repositorio; o repositorio guarda as notas tecnicas revisadas em
    code review. Ambas sao fonte legitima e nenhuma deve sumir por acidente.
    """
    override = os.getenv("FROID_APPROVED_KNOWLEDGE_DIR", "").strip()
    if override:
        return [Path(override)]
    fontes = [REPO_APPROVED_DIR]
    if VOLUME_APPROVED_DIR.exists():
        fontes.append(VOLUME_APPROVED_DIR)
    return [path for path in fontes if path.exists()]
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


# O modelo de embedding padrao da ChromaDB (all-MiniLM-L6-v2) trunca a entrada
# em 256 tokens. Um trecho de 700 palavras vira cerca de mil tokens: tres
# quartos dele nunca chegam a ser vetorizados, e a busca so enxerga o comeco.
#
# Foi por isso que uma nota indexada corretamente nao aparecia nem quando
# consultada com uma frase literal sua: a frase estava depois do corte. E foi
# por isso que um documento de 137 trechos dominava qualquer busca — ele nao
# respondia melhor, apenas tinha 137 comecos.
#
# 150 palavras em portugues ficam com folga dentro do limite.
MODEL_TOKEN_LIMIT = 256
DEFAULT_WORDS_PER_CHUNK = 150
DEFAULT_OVERLAP = 40


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
    parser.add_argument(
        "--approved", type=Path, action="append", default=None,
        help="Pasta approved a indexar. Pode repetir. Sem isto, indexa o "
             "repositorio e o volume curado.",
    )
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--words-per-chunk", type=int, default=DEFAULT_WORDS_PER_CHUNK)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    parser.add_argument("--reset", action="store_true", help="Apaga a collection antes de reindexar.")
    parser.add_argument("--embedding", default="auto", choices=["auto", "openai", "local"],
                        help="Modelo de embedding. Trocar exige --reset.")
    parser.add_argument("--exclude", action="append", default=[],
                        help="Ignora arquivos cujo nome contenha este texto. Pode repetir.")
    args = parser.parse_args()

    fontes = [Path(p) for p in (args.approved or [])] or default_sources()
    if not fontes:
        raise SystemExit("Nenhuma pasta approved encontrada.")
    for fonte in fontes:
        if not fonte.exists():
            raise SystemExit(f"Pasta approved inexistente: {fonte}")
    print("Fontes:")
    for fonte in fontes:
        print(f"  {fonte} ({len(list(fonte.rglob('*.md')))} arquivos)")

    from chromadb import PersistentClient

    args.chroma_path.mkdir(parents=True, exist_ok=True)
    client = PersistentClient(path=str(args.chroma_path))
    if args.reset:
        try:
            client.delete_collection(args.collection)
        except Exception:
            pass
    collection, modelo = explica_embeddings.collection_for(
        client, args.collection, args.embedding
    )
    print(f"Embedding: {modelo}")

    # (raiz, arquivo) para que o identificador estavel continue derivando do
    # caminho relativo a sua propria pasta approved.
    md_files: list[tuple[Path, Path]] = []
    vistos: set[str] = set()
    duplicados = 0
    ignorados_por_filtro = 0
    for raiz in fontes:
        for path in sorted(raiz.rglob("*.md")):
            if any(termo.lower() in path.name.lower() for termo in args.exclude):
                ignorados_por_filtro += 1
                continue
            if path.name in vistos:
                # Mesmo nome nas duas fontes: vale a primeira, que e o
                # repositorio — a versao revisada em code review.
                duplicados += 1
                continue
            vistos.add(path.name)
            md_files.append((raiz, path))
    if duplicados:
        print(f"Ignorados por nome repetido entre as fontes: {duplicados}")
    if ignorados_por_filtro:
        print(f"Ignorados por --exclude: {ignorados_por_filtro}")

    total_chunks = 0
    total_files = 0

    for raiz, path in md_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_markdown(text, args.words_per_chunk, args.overlap)
        if not chunks:
            continue
        title = title_from_markdown(path, text)
        area = infer_area(path)
        # O titulo entra no texto vetorizado. Sem isso, um trecho do meio do
        # documento perde a identidade dele: fica um paragrafo solto, sem sinal
        # de a que assunto pertence.
        chunks = [f"{title}. {area}. {chunk}" for chunk in chunks]
        ids = [
            stable_id(path.relative_to(raiz), index, chunk)
            for index, chunk in enumerate(chunks)
        ]
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
