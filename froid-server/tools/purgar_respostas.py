"""Purga as respostas individuais de campanhas ja consolidadas no inventario.

A NR-1 exige vinte anos de historico do INVENTARIO. Nao das respostas cruas
que o produziram. Guardar resposta individual de saude mental por vinte anos
porque o inventario dura vinte anos confunde as duas coisas — e depois de
consolidado, a resposta crua nao responde nenhuma pergunta que o agregado nao
responda.

O padrao e --dry-run. Apagar dado sensivel precisa de um passo deliberado a
mais que nao apagar.

Uso:
    python tools/purgar_respostas.py --organizacao <uuid>
    python tools/purgar_respostas.py --organizacao <uuid> --executar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organizacao", required=True)
    parser.add_argument("--membership", default="", help="membership_id da sessao")
    parser.add_argument("--carencia", type=int, default=90,
                        help="dias apos o fechamento antes de poder purgar")
    parser.add_argument("--executar", action="store_true",
                        help="sem isto, nada e apagado")
    parser.add_argument("--campanha", help="purga apenas esta campanha")
    args = parser.parse_args()

    import tenant_store

    loja = tenant_store.TENANT_STORE
    with loja._connect(runtime=True) as conexao:
        with conexao.transaction():
            loja._nr1_session(conexao, args.organizacao, args.membership)
            linhas = conexao.execute(
                "SELECT campaign_id, title, closes_at, responses, has_aggregate, "
                "       eligible, reason FROM froid_purge_candidates(%s)",
                (args.carencia,),
            ).fetchall()

    if not linhas:
        print("Nenhuma campanha encontrada.")
        return 0

    elegiveis = [l for l in linhas if l[5]]
    print(f"Campanhas: {len(linhas)}  |  elegiveis: {len(elegiveis)}")
    print(f"Carencia: {args.carencia} dias apos o fechamento\n")

    for cid, titulo, fecha, respostas, agregado, elegivel, motivo in linhas:
        marca = "PURGAR" if elegivel else "manter"
        print(f"  [{marca}] {str(titulo)[:44]:44} {respostas:>5} respostas")
        print(f"           fecha em {fecha:%Y-%m-%d} | inventario: "
              f"{'sim' if agregado else 'NAO'} | {motivo}")

    if not args.executar:
        total = sum(l[3] for l in elegiveis)
        print(f"\n--dry-run: nada foi apagado. Seriam {total} respostas em "
              f"{len(elegiveis)} campanha(s).")
        print("Para executar de verdade, repita com --executar.")
        return 0

    if not elegiveis:
        print("\nNada elegivel. Nada a fazer.")
        return 0

    apagadas = 0
    with loja._connect(runtime=True) as conexao:
        with conexao.transaction():
            loja._nr1_session(conexao, args.organizacao, args.membership)
            for cid, titulo, *_ in elegiveis:
                if args.campanha and str(cid) != args.campanha:
                    continue
                linha = conexao.execute(
                    "SELECT froid_purge_campaign_responses(%s, %s)",
                    (cid, args.carencia),
                ).fetchone()
                n = int(linha[0] or 0)
                apagadas += n
                print(f"  purgada: {str(titulo)[:44]:44} {n} respostas")

    print(f"\nTotal apagado: {apagadas} respostas.")
    print("O inventario, o agregado por dimensao e a trilha de auditoria "
          "permanecem intactos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
