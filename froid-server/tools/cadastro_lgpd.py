"""Imprime o cadastro de operacoes de tratamento, para anexar ao RIPD.

O cadastro existia em lgpd_registry.py e nao tinha nenhuma forma de sair de la
— so os testes o liam. Um cadastro que ninguem consegue imprimir nao serve ao
RIPD, que e a unica razao de ele existir.

Uso:
    python tools/cadastro_lgpd.py
    python tools/cadastro_lgpd.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lgpd_registry as R  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="saida em JSON")
    args = parser.parse_args()

    documento = R.registry_as_document()
    if args.json:
        print(json.dumps(documento, ensure_ascii=False, indent=2))
        return 0

    print(f"CADASTRO DE OPERACOES DE TRATAMENTO — versao {documento['versao']}")
    print("Anexo do Relatorio de Impacto (LGPD art. 38).\n")

    for operacao in documento["operacoes"]:
        print(f"  {operacao['chave']}")
        print(f"    {operacao['descricao']}")
        print(f"    base legal  : {operacao['base_legal']}")
        print(f"    controlador : {operacao['controlador']}")
        print(f"    operador    : {operacao['operador']}")
        print(f"    classe      : {operacao['classe_dado']}")
        print(f"    retencao    : {operacao['retencao']}")
        if operacao["observacao"]:
            print(f"    nota        : {operacao['observacao']}")
        print()

    sensiveis = [o for o in documento["operacoes"] if o["classe_dado"] == "sensivel"]
    print(f"Operacoes com dado sensivel: {len(sensiveis)} de "
          f"{len(documento['operacoes'])}.")
    print("Sao estas que sustentam a necessidade do RIPD (art. 38).\n")
    print("AVISO AO COLABORADOR, texto vigente:")
    print(f"  {R.AVISO_BASE_LEGAL_NR1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
