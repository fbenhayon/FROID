"""Mede se o FROID Explica encontra o documento certo para cada pergunta.

Ate agora a qualidade da recuperacao era avaliada no olho, uma consulta por
vez. Isso escondeu por semanas um defeito grave: os trechos eram cortados em
700 palavras, o modelo de embedding trunca em 256 tokens, e tres quartos de
cada trecho nunca eram vetorizados. A busca so enxergava o comeco de cada
pedaco — e um documento com 137 pedacos dominava tudo, nao por responder
melhor, mas por ter 137 comecos.

Este script transforma "parece bom" em um numero. Roda um conjunto de
perguntas reais, cada uma com o documento que deveria responde-la, e reporta
em quantas o documento certo aparece entre os primeiros resultados.

Nao imprime conteudo de documento, apenas nomes de arquivo e posicoes.

Uso:
    python tools/verify_explica_retrieval.py
    python tools/verify_explica_retrieval.py --top 5
"""

from __future__ import annotations

import argparse
import os
import sys

# Pergunta -> trecho do nome do arquivo que deveria responde-la.
#
# Sao perguntas que uma pessoa faz de verdade, na linguagem dela, nao termos
# tecnicos que ja combinam com o texto do documento. A primeira e a mais
# importante do modulo NR-1: e a que decide se o trabalhador responde o
# questionario, e adesao baixa derruba o piso de coorte, que derruba o
# inventario inteiro.
CASOS: list[tuple[str, str]] = [
    ("meu chefe vai ver o que eu respondi no questionario", "NR1"),
    ("a empresa consegue saber quem respondeu o que", "NR1"),
    ("por que o painel nao mostra resultado enquanto a coleta esta aberta", "NR1"),
    ("o que a NR-1 passou a exigir sobre riscos psicossociais", "NR1"),
    ("por que o sistema diz sem mudanca em vez de dizer que melhorou", "NR1"),
    ("quantas respostas sao necessarias para liberar o resultado", "NR1"),
    ("o questionario pergunta sobre a minha saude mental", "NR1"),
    ("o que e a AEP e por que ela e obrigatoria", "NR1"),
    ("como funciona a janela clinica de cinco minutos", "Estabilizacao"),
    ("por que a tela nao atualiza a cada segundo", "Estabilizacao"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=3, help="posicoes consideradas acerto")
    parser.add_argument(
        "--chroma-path", default=os.getenv("FROID_CHROMA_PATH", "/data/chroma_db")
    )
    parser.add_argument(
        "--collection", default=os.getenv("FROID_CHROMA_COLLECTION", "froid_clinical_knowledge")
    )
    args = parser.parse_args()

    import chromadb

    collection = chromadb.PersistentClient(path=args.chroma_path).get_collection(
        args.collection
    )
    total = collection.count()
    print(f"Collection: {args.collection} ({total} trechos)")
    print(f"Acerto = documento esperado entre os {args.top} primeiros.\n")

    acertos = 0
    for pergunta, esperado in CASOS:
        resultado = collection.query(query_texts=[pergunta], n_results=args.top)
        fontes = [m.get("source", "?") for m in resultado["metadatas"][0]]
        posicao = next(
            (i + 1 for i, fonte in enumerate(fontes) if esperado.lower() in fonte.lower()),
            None,
        )
        if posicao:
            acertos += 1
            marca = f"OK  #{posicao}"
        else:
            marca = "FALHA "
        print(f"  {marca}  {pergunta}")
        if not posicao:
            print(f"           veio: {', '.join(f[:44] for f in fontes)}")

    taxa = acertos / len(CASOS)
    print(f"\nAcerto: {acertos}/{len(CASOS)} ({taxa * 100:.0f}%)")

    # Um documento que ocupa fatia grande do indice aparece em qualquer busca
    # por massa, e nao por pertinencia.
    todos = collection.get(include=["metadatas"])
    contagem: dict[str, int] = {}
    for metadado in todos["metadatas"]:
        fonte = metadado.get("source", "?")
        contagem[fonte] = contagem.get(fonte, 0) + 1
    print("\nDocumentos com maior fatia do indice:")
    for fonte, quantos in sorted(contagem.items(), key=lambda x: -x[1])[:5]:
        fatia = quantos / max(1, total)
        alerta = "  <-- domina o indice" if fatia > 0.05 else ""
        print(f"  {quantos:5d} trechos ({fatia * 100:4.1f}%)  {fonte[:60]}{alerta}")

    return 0 if taxa >= 0.7 else 1


if __name__ == "__main__":
    raise SystemExit(main())
