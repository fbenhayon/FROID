#!/usr/bin/env python3
"""Registra no manifesto de ingestao as notas liberadas que ainda nao constam nele.

POR QUE EXISTE. O manifesto (`manifesto_explica.json`) e gerado pela curadoria
a partir das fontes que existiam naquele momento; `liberar_notas_froid.py` so
vira `indexar=true` em entradas que ja existem. Uma nota escrita depois da
curadoria fica fora do manifesto, e `ingest_approved_sources.py --manifesto`
nao a indexa — sem erro: ela simplesmente nao aparece nas respostas. Foi o
caso de FROID_Dois_Produtos_Clinico_e_NR1.md, liberada em git e ausente do
manifesto de producao em 19/10/2026; o FROID Explica so a alcancava pela busca
local por palavra.

O que faz: para cada nota em LIBERADAS que existe na pasta approved do
repositorio e NAO tem entrada no manifesto, cria a entrada com
`indexar=true`, o caminho real e o motivo da liberacao. Nao toca em entrada
existente (a decisao de curadoria e `liberar_notas_froid.py`).

Uso:
    python tools/registrar_notas_no_manifesto.py --manifesto /data/froid_sources/manifesto_explica.json
    python tools/registrar_notas_no_manifesto.py --manifesto ... --conferir   # so lista
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from liberar_notas_froid import LIBERADAS  # noqa: E402

APPROVED = Path(__file__).resolve().parents[1] / "knowledge" / "approved"


def faltantes(manifesto: dict, approved: Path = APPROVED) -> dict[str, dict]:
    """As entradas a criar: nome -> entrada, so para notas liberadas que existem
    em disco e nao estao no manifesto."""
    novas: dict[str, dict] = {}
    for nome, motivo in LIBERADAS.items():
        if nome in manifesto:
            continue
        caminhos = list(approved.rglob(nome))
        if not caminhos:
            continue
        novas[nome] = {
            "caminho": str(caminhos[0]),
            "categorias": ["nota_froid_liberada"],
            "indexar": True,
            "motivo": motivo,
        }
    return novas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifesto", type=Path, required=True)
    parser.add_argument("--conferir", action="store_true", help="So lista o que faltaria; nao grava.")
    args = parser.parse_args()
    manifesto = json.loads(args.manifesto.read_text(encoding="utf-8"))
    novas = faltantes(manifesto)
    if not novas:
        print("Nenhuma nota liberada falta no manifesto.")
        return 0
    for nome, entrada in novas.items():
        print(f"{'faltaria' if args.conferir else 'registrada'}: {nome} -> {entrada['caminho']}")
    if args.conferir:
        return 0
    manifesto.update(novas)
    args.manifesto.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifesto gravado com {len(novas)} entrada(s) nova(s); total {len(manifesto)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
