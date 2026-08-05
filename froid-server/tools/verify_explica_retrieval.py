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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import explica_embeddings  # noqa: E402

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
    # Os dois casos abaixo nasceram de respostas erradas em producao: o
    # Explica confundiu o produto clinico com o modulo NR-1, e descreveu o
    # FROID inteiro pela metade corporativa.
    ("o froid substitui o phq-9", "Dois_Produtos"),
    ("qual a diferenca entre o froid da clinica e o da empresa", "Dois_Produtos"),
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
    parser.add_argument(
        "--embedding", default="auto", choices=["auto", "openai", "local"],
        help="Precisa ser o mesmo usado na indexacao.",
    )
    parser.add_argument(
        "--simulate-exclude", action="append", default=[],
        help="Descarta resultados destas fontes na hora de pontuar, sem "
             "reindexar. Serve para medir o efeito de tirar um documento da "
             "base antes de decidir tira-lo de verdade.",
    )
    args = parser.parse_args()

    import chromadb

    # O mesmo modelo da indexacao, obrigatoriamente: vetores de modelos
    # diferentes nao sao comparaveis, e o erro nao aparece como falha — aparece
    # como busca que devolve qualquer coisa.
    collection, modelo = explica_embeddings.collection_for(
        chromadb.PersistentClient(path=args.chroma_path),
        args.collection,
        args.embedding,
        create=False,
    )
    total = collection.count()
    print(f"Collection: {args.collection} ({total} trechos)")
    print(f"Embedding: {modelo}")
    print(f"Acerto = documento esperado entre os {args.top} primeiros.\n")

    if args.simulate_exclude:
        print(f"Simulando remocao de: {', '.join(args.simulate_exclude)}\n")

    def descartada(fonte: str) -> bool:
        return any(
            termo.lower() in fonte.lower() for termo in args.simulate_exclude
        )

    acertos = 0
    for pergunta, esperado in CASOS:
        # Busca mais fundo quando ha simulacao, para que sobrem candidatos
        # depois do descarte e a comparacao continue sendo sobre as mesmas
        # primeiras posicoes.
        profundidade = args.top * 6 if args.simulate_exclude else args.top
        resultado = collection.query(query_texts=[pergunta], n_results=profundidade)
        fontes = [m.get("source", "?") for m in resultado["metadatas"][0]]
        fontes = [f for f in fontes if not descartada(f)][: args.top]
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
