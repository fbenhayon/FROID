#!/usr/bin/env python3
"""Ativa a carteira compartilhada de uma clinica, com conferencia obrigatoria.

A ativacao e o unico passo irreversivel da migracao multiprofissional: a partir
dela o pool compartilhado passa a ser a autoridade do saldo. A funcao no banco
exige que o saldo esperado bata EXATAMENTE com o consolidado - essa e a trava
contra migrar errado. Calcular esse numero a mao, somando o saldo de varios
profissionais, e justamente onde um erro custa credito de cliente.

Este utilitario faz a conta e mostra tudo ANTES de qualquer escrita.

  # 1. Conferencia (nao escreve nada)
  python3 ops/clinic_activation.py --cnpj 12.345.678/0001-99

  # 2. Ativacao, so depois de conferir o numero mostrado acima
  python3 ops/clinic_activation.py --cnpj 12.345.678/0001-99 --activate --expect 500

A URL do banco vem de --database-url ou de FROID_DATABASE_URL (ja definida no
ambiente do backend em modo dual, entao normalmente basta omitir).

Rode de DENTRO do container do backend - e o unico lugar que tem psycopg e
alcanca o Postgres, que nao expoe porta ao host:

  docker compose exec froid-backend python3 ops/clinic_activation.py --cnpj ...
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# O script vive em <backend>/ops/, entao a raiz do backend (onde estao
# tenant_store.py e main.py) e o diretorio pai.
SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

try:
    import psycopg
except ImportError:  # pragma: no cover
    sys.exit("psycopg nao encontrado. Rode dentro do container do backend.")

from tenant_store import stable_uuid  # noqa: E402


def organization_id_for_cnpj(cnpj: str) -> str:
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14:
        sys.exit(f"CNPJ invalido: '{cnpj}' (esperado 14 digitos, veio {len(digits)})")
    return str(stable_uuid("organization", "cnpj", digits))


def describe(connection, organization_id: str) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT display_name, document, report_visibility FROM organizations WHERE id=%s",
            (organization_id,),
        )
        organization = cursor.fetchone()
        if not organization:
            sys.exit(
                "Organizacao nao encontrada para este CNPJ.\n"
                "Rode o backfill (persistencia dual) antes de ativar."
            )
        cursor.execute(
            "SELECT balance, authority, version FROM organization_wallets "
            "WHERE organization_id=%s",
            (organization_id,),
        )
        wallet = cursor.fetchone()
        cursor.execute(
            """
            SELECT user_account.email,
                   coalesce(string_agg(DISTINCT role.role, ',' ORDER BY role.role), ''),
                   membership.id,
                   coalesce((
                       SELECT ledger.delta FROM credit_ledger ledger
                        WHERE ledger.organization_id = membership.organization_id
                          AND ledger.event_type = 'migration_opening'
                          AND ledger.actor_user_id = membership.user_id
                        LIMIT 1
                   ), 0)
              FROM organization_memberships membership
              JOIN users user_account ON user_account.id = membership.user_id
              LEFT JOIN membership_roles role ON role.membership_id = membership.id
             WHERE membership.organization_id=%s AND membership.status='active'
             GROUP BY membership.id, membership.organization_id, membership.user_id,
                      user_account.email
             ORDER BY user_account.email
            """,
            (organization_id,),
        )
        members = cursor.fetchall()
    return {"organization": organization, "wallet": wallet, "members": members}


def owner_reference(connection, organization_id: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT membership.id, membership.user_id, user_account.email
              FROM organization_memberships membership
              JOIN membership_roles role ON role.membership_id = membership.id
              JOIN users user_account ON user_account.id = membership.user_id
             WHERE membership.organization_id=%s AND membership.status='active'
               AND role.role IN ('owner','administrator')
             ORDER BY CASE role.role WHEN 'owner' THEN 0 ELSE 1 END
             LIMIT 1
            """,
            (organization_id,),
        )
        row = cursor.fetchone()
    if not row:
        sys.exit("Nenhum owner/administrator ativo nesta organizacao; ative por outro caminho.")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cnpj", required=True, help="CNPJ da clinica")
    parser.add_argument("--database-url", default=os.getenv("FROID_DATABASE_URL", ""))
    parser.add_argument("--activate", action="store_true", help="executa a ativacao")
    parser.add_argument("--expect", type=int, help="saldo consolidado esperado")
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("Informe --database-url ou defina FROID_DATABASE_URL.")
    if args.activate and args.expect is None:
        sys.exit("--activate exige --expect com o saldo conferido na etapa 1.")

    organization_id = organization_id_for_cnpj(args.cnpj)

    with psycopg.connect(args.database_url, autocommit=True) as connection:
        info = describe(connection, organization_id)
        name, document, visibility = info["organization"]
        wallet = info["wallet"]

        print(f"\nClinica ......... {name}")
        print(f"Documento ....... {document}")
        print(f"Organizacao ..... {organization_id}")
        print(f"Visibilidade .... {visibility}")

        if not wallet:
            sys.exit("\nCarteira ainda nao criada. Rode o backfill antes de ativar.")
        balance, authority, version = wallet
        print(f"Carteira ........ saldo={balance} autoridade={authority} versao={version}\n")

        print("Profissionais ativos e aporte de abertura:")
        aportes = 0
        for email, roles, _membership, opening in info["members"]:
            aportes += int(opening)
            print(f"  {email:<40} {roles or '--':<28} aporte={opening}")
        print(f"\n  Soma dos aportes registrados ... {aportes}")
        print(f"  Saldo atual da carteira ........ {balance}")

        if authority == "shared":
            print("\nCarteira JA ATIVADA. Nada a fazer.")
            return

        if not args.activate:
            print(
                "\nConferencia apenas. Se o saldo acima estiver correto, ative com:\n"
                f"  python3 ops/clinic_activation.py --cnpj {args.cnpj} "
                f"--activate --expect {balance}\n"
            )
            return

        if args.expect != balance:
            sys.exit(
                f"\nABORTADO: --expect {args.expect} difere do saldo consolidado {balance}.\n"
                "Confira a origem da divergencia antes de ativar."
            )

        membership_id, user_id, owner_email = owner_reference(connection, organization_id)
        print(f"Ativando como {owner_email} ...")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.organization_id', %s, false)", (organization_id,)
            )
            cursor.execute(
                "SELECT set_config('app.membership_id', %s, false)", (str(membership_id),)
            )
            cursor.execute(
                "SELECT resulting_balance, activated "
                "FROM froid_activate_shared_wallet(%s,%s,%s,%s)",
                (organization_id, membership_id, user_id, args.expect),
            )
            resulting, activated = cursor.fetchone()
        print(
            f"\nCarteira compartilhada ATIVADA. Saldo={resulting} (mudou={activated}).\n"
            "A partir de agora todo consumo desta clinica debita deste pool unico."
        )


if __name__ == "__main__":
    main()
