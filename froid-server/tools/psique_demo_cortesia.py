"""Cortesia de demonstracao do Psique V2: ENROLL + ADJUST auditado, sem Stripe.

Concede creditos de demonstracao a uma organizacao pelo MESMO comando
SECURITY DEFINER que o produto usa (psique_v2_credit_command), como o dono
real da organizacao: nada de INSERT direto em carteira ou ledger. O ADJUST
exige motivo e chave de idempotencia, entao a trilha de auditoria registra
que foi cortesia e reexecutar nao concede duas vezes.

Uso (sempre comeca em ensaio; nada escreve sem --aplicar):

    FROID_PSIQUE_OPERACAO_DATABASE_URL=... python tools/psique_demo_cortesia.py \
        --organizacao <uuid> --owner-email dono@exemplo.com \
        --creditos 500 --motivo "Cortesia de demonstracao PRO 500" \
        --confirm-database <dbname>

O DSN e o administrativo (mesma familia do runner de migrations): a RLS de
organization_memberships exige membership ja declarado, o que uma ferramenta
de localizacao nao tem como saber antes. A autoridade de escrita nao vem do
DSN: o comando SECURITY DEFINER revalida dono ativo, organizacao e papel.
--confirm-database obriga a dizer em voz alta contra qual banco.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from psique_credits import CreditError, PsiqueCredits
from tenant_access import AccessContext

ENV_DSN = "FROID_PSIQUE_OPERACAO_DATABASE_URL"


def _nunca(*_args: Any) -> Any:
    raise CreditError("CORTESIA_NAO_USA_IDENTIDADE_NEM_MATERIAL")


def localizar_dono(conn: Any, organizacao: str, owner_email: str) -> dict[str, str]:
    """Resolve o dono ativo; falha nomeada se a organizacao nao confere."""
    row = conn.execute(
        """
        SELECT m.id, u.id, o.organization_type, o.display_name
        FROM users u
        JOIN organization_memberships m ON m.user_id = u.id
        JOIN membership_roles r ON r.membership_id = m.id AND r.role = 'owner'
        JOIN organizations o ON o.id = m.organization_id
        WHERE o.id = %s AND lower(u.email) = lower(%s)
            AND m.status = 'active' AND u.status = 'active' AND o.status = 'active'
            AND o.organization_type IN ('solo','clinic')
        """,
        (organizacao, owner_email),
    ).fetchone()
    if row is None:
        raise SystemExit("DONO_ATIVO_NAO_ENCONTRADO: confira organizacao, e-mail e papel owner")
    return {"membership_id": str(row[0]), "user_id": str(row[1]),
            "organization_type": row[2], "display_name": row[3]}


def estado_da_carteira(conn: Any, organizacao: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT credit_model, balance, reserved_balance FROM organization_wallets "
        "WHERE organization_id = %s", (organizacao,)).fetchone()
    if row is None:
        return {"carteira": "ausente (ENROLL cria vazia)"}
    return {"credit_model": row[0], "balance": row[1], "reserved_balance": row[2]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--organizacao", required=True, help="UUID da organizacao")
    parser.add_argument("--owner-email", required=True, help="e-mail do dono da organizacao")
    parser.add_argument("--creditos", required=True, type=int, help="creditos de cortesia (>0)")
    parser.add_argument("--motivo", required=True, help="motivo gravado no ledger de auditoria")
    parser.add_argument("--chave", default=None,
                        help="chave de idempotencia; padrao demo-cortesia-<org>-<creditos>")
    parser.add_argument("--confirm-database", required=True,
                        help="nome exato do banco do DSN, dito em voz alta")
    parser.add_argument("--aplicar", action="store_true",
                        help="sem esta flag o comando apenas ensaia e nada escreve")
    args = parser.parse_args(argv)

    if args.creditos <= 0:
        raise SystemExit("CREDITOS_POSITIVOS_OBRIGATORIOS: cortesia nunca debita")
    if not args.motivo.strip():
        raise SystemExit("MOTIVO_OBRIGATORIO")

    dsn = os.environ.get(ENV_DSN, "")
    if not dsn:
        raise SystemExit(f"{ENV_DSN} ausente: exporte o DSN administrativo")

    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    dbname = conninfo_to_dict(dsn).get("dbname", "")
    if dbname != args.confirm_database:
        raise SystemExit(f"CONFIRMACAO_DIVERGE: o DSN aponta para '{dbname}'")

    def conectar() -> Any:
        return psycopg.connect(dsn, autocommit=True)

    chave = args.chave or f"demo-cortesia-{args.organizacao}-{args.creditos}"
    with conectar() as conn:
        # A RLS das tabelas de identidade e chaveada por app.organization_id;
        # declarar o GUC aqui so abre a leitura do proprio tenant. A autoridade
        # de escrita e revalidada dentro do comando SECURITY DEFINER.
        conn.execute("SELECT set_config('app.organization_id',%s,false)",
                     (args.organizacao,))
        dono = localizar_dono(conn, args.organizacao, args.owner_email)
        antes = estado_da_carteira(conn, args.organizacao)

    plano = {"organizacao": args.organizacao, "display_name": dono["display_name"],
             "dono": args.owner_email, "carteira_antes": antes,
             "acoes": ["ENROLL (idempotente)",
                       f"ADJUST +{args.creditos} motivo='{args.motivo}' chave='{chave}'"]}
    print(json.dumps(plano, ensure_ascii=False, indent=2))
    if not args.aplicar:
        print("ENSAIO: nada foi escrito. Repita com --aplicar para executar.")
        return 0

    contexto = AccessContext.create(
        organization_id=args.organizacao, membership_id=dono["membership_id"],
        user_id=dono["user_id"], roles=["owner"],
        organization_type=dono["organization_type"])
    servico = PsiqueCredits(conectar, identity_loader=_nunca,
                            material_loader=_nunca, keyring=None)  # type: ignore[arg-type]
    try:
        inscricao = servico.enroll_empty_wallet(contexto)
        ajuste = servico.manual_adjustment(contexto, args.creditos,
                                           reason=args.motivo, idempotency_key=chave)
        saldo = servico.balance(contexto)
    except CreditError as erro:
        raise SystemExit(f"COMANDO_RECUSADO: {erro.code}") from erro

    print(json.dumps({"enroll": inscricao, "ajuste": ajuste, "saldo": saldo},
                     ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
