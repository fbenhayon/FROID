"""Exporta os contatos deixados no site (marketing_leads) em CSV.

A tabela gravava e nada a lia (skill-froid-master 2.1). Esta é a leitura do
comercial. Quem pediu oposição ao contato sai com a coluna `opt_out_at`
preenchida: é para NÃO ligar, e por isso aparece em vez de sumir.

Uso, de dentro do contêiner do backend (o CSV sai no terminal):

    python tools/exportar_leads.py > leads.csv
    python tools/exportar_leads.py --origem kit-demonstracao-nr1
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_store import TenantStore  # noqa: E402

COLUNAS = (
    "created_at", "nome", "email", "telefone", "empresa", "cargo",
    "origem", "contexto", "opt_out_at",
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origem", default="", help="Filtra por origem (ex.: kit-demonstracao-nr1).")
    args = ap.parse_args()

    store = TenantStore.from_env()
    if not store.enabled:
        raise SystemExit("FROID_PERSISTENCE_MODE não está em 'dual': não há base de leads para ler.")
    leads = store.list_marketing_leads()
    if args.origem:
        leads = [lead for lead in leads if lead["origem"] == args.origem]

    escritor = csv.writer(sys.stdout)
    escritor.writerow(COLUNAS)
    for lead in leads:
        escritor.writerow(
            "" if lead[c] is None else (lead[c].isoformat() if hasattr(lead[c], "isoformat") else lead[c])
            for c in COLUNAS
        )
    print(f"{len(leads)} contato(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
