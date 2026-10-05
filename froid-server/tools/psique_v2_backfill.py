"""Fase 7.4, etapa 1: converte as carteiras V1 da frota para a carteira unica V2.

Le o identity_state.json (fonte autoritativa do saldo V1 em producao), agrupa os
profissionais por organizacao com a MESMA regra do espelho dual
(organization_id_for_profile), e para cada organizacao calcula:

- net: soma de remaining_sessions dos profissionais (o saldo vivo do V1);
- ever_purchased: alguem da organizacao ja comprou (session_credit_purchases);
- pendencias: sessoes ja entregues sem credito (pending_settlement_session_ids).

Depois chama PsiqueCredits.backfill_from_v1 (migration 048), que e nao destrutivo
e idempotente: org ja psique_v2 vira no-op. O pool Postgres NAO e usado como
verdade do saldo: em FROID_SHARED_CREDITS_MODE=off ele guarda so a abertura do
espelho e fica velho; o numero vem do JSON e o pool aparece no plano so para
conferencia.

Ensaio por padrao. --aplicar exige --organizacao (uma por vez) ou --todas.
A ordem da 7.4 importa: converter uma org antes de o checkout dela apontar para
o V2 faz o cliente pagar e nao receber credito (WALLET_CREDIT_MODEL_MISMATCH).

    FROID_PSIQUE_OPERACAO_DATABASE_URL=... python tools/psique_v2_backfill.py \
        --estado /data/identity_state.json --confirm-database froid_homologacao \
        [--organizacao <uuid> | --todas] [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tenant_store import normalize_email, organization_id_for_profile, safe_int

ENV_DSN = "FROID_PSIQUE_OPERACAO_DATABASE_URL"
NOTA = "Fase 7.4: saldo V1 do identity_state.json"


def planejar(state: dict) -> dict[str, dict[str, Any]]:
    """Agrega o saldo V1 por organizacao. Puro: so le o JSON."""
    perfis = state.get("professional_profiles") or {}
    orgs: dict[str, dict[str, Any]] = {}
    for email, perfil in perfis.items():
        if not isinstance(perfil, dict):
            continue
        dono = normalize_email(email)
        if not dono:
            continue
        org_id = str(organization_id_for_profile(
            dono, str(perfil.get("account_type") or "individual").lower(),
            perfil.get("organization_document")))
        item = orgs.setdefault(org_id, {"net": 0, "ever_purchased": False,
                                        "pendencias": [], "profissionais": []})
        item["net"] += max(0, safe_int(perfil.get("remaining_sessions")))
        if perfil.get("session_credit_purchases"):
            item["ever_purchased"] = True
        for sid in perfil.get("pending_settlement_session_ids") or []:
            sid = str(sid or "").strip()
            if sid and sid not in item["pendencias"]:
                item["pendencias"].append(sid)
        item["profissionais"].append(dono)
    return orgs


def localizar_membro(conn: Any, organizacao: str) -> dict[str, str] | None:
    """Dono (ou administrador) ativo: o 048 exige membership ativo da propria org."""
    conn.execute("SELECT set_config('app.organization_id',%s,false)", (organizacao,))
    row = conn.execute(
        """
        SELECT m.id, u.id, o.organization_type, o.display_name
        FROM organization_memberships m
        JOIN users u ON u.id = m.user_id
        JOIN membership_roles r ON r.membership_id = m.id
        JOIN organizations o ON o.id = m.organization_id
        WHERE m.organization_id = %s AND m.status = 'active' AND u.status = 'active'
          AND r.role IN ('owner', 'administrator')
        ORDER BY (r.role = 'owner') DESC, m.created_at
        LIMIT 1
        """, (organizacao,)).fetchone()
    if row is None:
        return None
    return {"membership_id": str(row[0]), "user_id": str(row[1]),
            "organization_type": str(row[2]), "display_name": str(row[3] or "")}


def estado_da_carteira(conn: Any, organizacao: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT credit_model, balance, authority FROM organization_wallets "
        "WHERE organization_id = %s", (organizacao,)).fetchone()
    if row is None:
        return None
    return {"credit_model": row[0], "pool": row[1], "authority": row[2]}


def classificar(carteira: dict | None, membro: dict | None) -> str:
    if carteira is None:
        return "PULAR_SEM_CARTEIRA"
    if carteira["credit_model"] == "psique_v2":
        return "JA_V2"
    # Empresa do NR-1 nao atende sessao: a carteira unica V2 so existe para
    # profissional (solo) e clinica. O comando 048 recusaria; aqui so se pula.
    if membro is not None and membro["organization_type"] not in {"solo", "clinic"}:
        return "PULAR_EMPRESA_NR1"
    if membro is None:
        return "PULAR_SEM_DONO_ATIVO"
    return "CONVERTER"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--estado", required=True, help="caminho do identity_state.json")
    parser.add_argument("--confirm-database", required=True, help="nome exato do banco do DSN")
    alvo = parser.add_mutually_exclusive_group()
    alvo.add_argument("--organizacao", help="converte so esta organizacao (uuid)")
    alvo.add_argument("--todas", action="store_true", help="converte todas as elegiveis")
    parser.add_argument("--aplicar", action="store_true", help="sem isto, so ensaia")
    args = parser.parse_args(argv)
    if args.aplicar and not (args.organizacao or args.todas):
        raise SystemExit("ALVO_OBRIGATORIO: --aplicar exige --organizacao <uuid> ou --todas")

    dsn = os.environ.get(ENV_DSN, "")
    if not dsn:
        raise SystemExit(f"{ENV_DSN} ausente: exporte o DSN administrativo")
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    if conninfo_to_dict(dsn).get("dbname", "") != args.confirm_database:
        raise SystemExit("CONFIRMACAO_DIVERGE: o DSN nao aponta para --confirm-database")

    with open(args.estado, encoding="utf-8") as fh:
        planos = planejar(json.load(fh))
    if args.organizacao:
        if args.organizacao not in planos:
            raise SystemExit("ORGANIZACAO_FORA_DO_ESTADO: nenhum profissional do JSON cai nela")
        planos = {args.organizacao: planos[args.organizacao]}

    def conectar() -> Any:
        return psycopg.connect(dsn, autocommit=True)

    relatorio = []
    with conectar() as conn:
        for org_id, plano in sorted(planos.items()):
            carteira = estado_da_carteira(conn, org_id)
            membro = localizar_membro(conn, org_id)
            relatorio.append({"organizacao": org_id,
                              "nome": (membro or {}).get("display_name", ""),
                              "acao": classificar(carteira, membro),
                              "net_json": plano["net"],
                              "pool_pg": (carteira or {}).get("pool"),
                              "ever_purchased": plano["ever_purchased"],
                              "pendencias": len(plano["pendencias"]),
                              "profissionais": len(plano["profissionais"]),
                              "_membro": membro})

    resumo: dict[str, int] = {}
    for linha in relatorio:
        resumo[linha["acao"]] = resumo.get(linha["acao"], 0) + 1
    publico = [{k: v for k, v in linha.items() if not k.startswith("_")} for linha in relatorio]
    print(json.dumps({"resumo": resumo, "organizacoes": publico}, ensure_ascii=False, indent=2))
    if not args.aplicar:
        print("ENSAIO: nada foi escrito.")
        return 0

    from psique_credits import CreditError, PsiqueCredits
    from tenant_access import AccessContext

    def _nunca(*_a: Any) -> Any:
        raise CreditError("BACKFILL_NAO_USA_IDENTIDADE_NEM_MATERIAL")

    servico = PsiqueCredits(conectar, identity_loader=_nunca,
                            material_loader=_nunca, keyring=None)  # type: ignore[arg-type]
    falhas = 0
    for linha in relatorio:
        if linha["acao"] != "CONVERTER":
            continue
        m = linha["_membro"]
        ctx = AccessContext.create(organization_id=linha["organizacao"],
                                   membership_id=m["membership_id"], user_id=m["user_id"],
                                   roles=["owner"], organization_type=m["organization_type"])
        try:
            res = servico.backfill_from_v1(
                ctx, int(linha["net_json"]), ever_purchased=bool(linha["ever_purchased"]),
                pending_ids=planos[linha["organizacao"]]["pendencias"], note=NOTA)
            print(json.dumps({"organizacao": linha["organizacao"], "resultado": res},
                             ensure_ascii=False, default=str))
        except CreditError as erro:
            falhas += 1
            print(json.dumps({"organizacao": linha["organizacao"], "recusado": erro.code},
                             ensure_ascii=False))
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
