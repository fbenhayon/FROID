"""Relatorio de validade convergente dos padroes do FROID.

Roda as hipoteses declaradas em froid_validation contra os pares coletados e
imprime o que a amostra sustenta — incluindo, e principalmente, quando ela nao
sustenta nada.

Nao imprime dado de paciente: a funcao froid_validation_pairs devolve apenas
os pares, sem identificador.

Uso:
    python tools/validation_report.py
    python tools/validation_report.py --organizacao <uuid>
    python tools/validation_report.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import froid_validation as V  # noqa: E402


def carregar_pares(conn, pattern_key: str, instrument: str):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pattern_value, instrument_score "
            "FROM froid_validation_pairs(%s, %s)",
            (pattern_key, instrument),
        )
        linhas = cur.fetchall()
    return [float(a) for a, _ in linhas], [float(b) for _, b in linhas]


def imprimir(resultado: V.ConvergenceResult) -> None:
    cabecalho = f"{resultado.pattern_key} x {resultado.instrument}"
    print(f"\n{cabecalho}")
    print("-" * len(cabecalho))
    print(f"  pares utilizaveis : {resultado.n}")
    if resultado.r is not None:
        print(f"  coeficiente r     : {resultado.r:+.3f}")
    if resultado.interval:
        baixo, alto = resultado.interval
        print(f"  IC 95%            : {baixo:+.3f} a {alto:+.3f}")
    print(f"  veredito          : {resultado.verdict}")
    print(f"  {resultado.detail}")
    print(f"\n  Frase divulgavel:\n    {V.evidence_statement(resultado)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organizacao", help="UUID da organizacao (RLS)")
    parser.add_argument("--json", action="store_true", help="saida em JSON")
    args = parser.parse_args()

    import tenant_store

    conn = tenant_store.TENANT_STORE.connect()  # type: ignore[attr-defined]
    if args.organizacao:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('froid.organization_id', %s, false)",
                (args.organizacao,),
            )

    resultados = []
    for pairing in V.DECLARED_PAIRINGS:
        xs, ys = carregar_pares(conn, pairing.pattern_key, pairing.instrument)
        resultados.append(V.evaluate(pairing, xs, ys))

    if args.json:
        print(json.dumps([
            {
                "pattern": r.pattern_key, "instrument": r.instrument, "n": r.n,
                "r": r.r, "interval": r.interval, "verdict": r.verdict,
                "statement": V.evidence_statement(r),
            }
            for r in resultados
        ], ensure_ascii=False, indent=2))
        return 0

    print("VALIDADE CONVERGENTE — HIPOTESES DECLARADAS")
    print("As direcoes esperadas foram fixadas antes da coleta. Um resultado")
    print("no sentido contrario e evidencia contra, nao achado a reinterpretar.")
    for resultado in resultados:
        imprimir(resultado)

    prontos = [r for r in resultados if r.reportable]
    print(f"\n\n{len(prontos)} de {len(resultados)} hipoteses com amostra suficiente.")
    if not prontos:
        print(f"Nenhuma ainda atinge {V.MIN_PAIRS} pares. Ate la, a resposta")
        print("honesta a 'quem validou isso' continua sendo 'ainda ninguem'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
