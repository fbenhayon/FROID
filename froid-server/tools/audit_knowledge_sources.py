"""Levanta quem responde o que na base do FROID Explica.

Serve para uma pergunta que so um humano com contexto responde: quais fontes
estao desatualizadas em relacao ao FROID de hoje.

O script nao decide isso. Ele torna a decisao possivel: para cada afirmacao
corrente do produto, mostra quais documentos a base devolveria e um trecho do
que cada um diz. Onde dois documentos discordarem sobre o mesmo assunto, um
deles esta velho — e quem sabe qual e voce, nao o script.

Tambem lista o peso de cada fonte no indice, porque documento grande aparece
em qualquer busca por massa e nao por pertinencia.

Nao imprime dado de paciente: le apenas a base de conhecimento curada.

Uso:
    python tools/audit_knowledge_sources.py
    python tools/audit_knowledge_sources.py --tema precos
    python tools/audit_knowledge_sources.py --pergunta "quantos creditos por sessao"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import explica_embeddings  # noqa: E402


# Afirmacoes correntes do FROID. Se a base devolver documentos que digam coisa
# diferente destas, o documento e candidato a remocao — ou a afirmacao mudou e
# a nota tecnica e que precisa ser atualizada. Os dois casos sao achados.
TEMAS: dict[str, list[str]] = {
    "planos": [
        "quais sao os planos do FROID e o que cada um inclui",
        "quantos usuarios cada plano permite",
        "como funciona o consumo de creditos por sessao",
    ],
    "precos": [
        "quanto custa uma sessao no FROID",
        "quais pacotes de credito existem",
    ],
    "clinica": [
        "como funciona a gestao de clinica com varios profissionais",
        "carteira compartilhada de creditos entre profissionais",
        "quem pode ver o relatorio de qual paciente",
    ],
    "metricas": [
        "o que e o IPM e como ele e calculado",
        "o que e o IDM",
        "quantas zonas emocionais o FROID usa",
        "como funciona a calibracao de linha de base",
    ],
    "privacidade": [
        "o que e o k-anonimato no Data-FROID",
        "quantos registros minimos uma consulta analitica exige",
        "quem tem acesso ao relatorio clinico de um paciente",
    ],
    "sessao": [
        "como o paciente entra na sessao",
        "o que acontece quando acabam os creditos durante a sessao",
        "como funciona a sessao pelo celular",
    ],
    "nr1": [
        "o que a NR-1 exige sobre riscos psicossociais",
        "o empregador ve a resposta individual do colaborador",
    ],
}


# Termos que nao deveriam existir numa base consultada por cliente. Nao sao
# palavras proibidas: sao indicios de documento interno — plano financeiro,
# material de captacao, estrutura de custo — que entrou na curadoria por
# engano.
#
# Encontrado em auditoria: a base respondia "quanto custa uma sessao" com o
# CUSTO interno por sessao, e nao com o preco. O produto entregava a propria
# margem ao cliente que perguntasse.
INDICIOS_CONFIDENCIAIS = [
    "custo total", "custo por sessao", "custo / sessao", "custo/sessao",
    "margem", "valuation", "investimento seed", "series a", "pre-series",
    "captacao", "rodada", "burn", "runway", "cac", "ltv", "payback",
    "early adopter", "break-even", "breakeven", "projecao de receita",
    "faturamento projetado", "ebitda",
]


def escanear_confidencial(collection, limite: int) -> None:
    """Procura na base indicios de material interno exposto ao cliente."""
    print("\n\nINDICIOS DE MATERIAL INTERNO NA BASE")
    print("Documento interno numa base consultada por cliente e vazamento,")
    print("nao desatualizacao. Confira cada achado antes de decidir.\n")
    achados: dict[str, set] = {}
    for termo in INDICIOS_CONFIDENCIAIS:
        resultado = collection.query(query_texts=[termo], n_results=limite)
        for metadado, documento in zip(
            resultado["metadatas"][0], resultado["documents"][0]
        ):
            texto = " ".join(str(documento).split()).lower()
            if termo not in texto:
                continue
            fonte = metadado.get("source", "?")
            achados.setdefault(fonte, set()).add(termo)
    if not achados:
        print("  Nenhum indicio encontrado.")
        return
    for fonte, termos in sorted(achados.items(), key=lambda x: -len(x[1])):
        print(f"  {fonte[:62]}")
        print(f"      termos: {', '.join(sorted(termos))}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tema", choices=sorted(TEMAS), action="append", default=[])
    parser.add_argument("--pergunta", action="append", default=[])
    parser.add_argument("--top", type=int, default=4)
    parser.add_argument("--trecho", type=int, default=150, help="caracteres por excerto")
    parser.add_argument(
        "--chroma-path", default=os.getenv("FROID_CHROMA_PATH", "/data/chroma_db")
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("FROID_CHROMA_COLLECTION", "froid_clinical_knowledge"),
    )
    parser.add_argument("--embedding", default="auto", choices=["auto", "openai", "local"])
    parser.add_argument(
        "--so-peso", action="store_true", help="mostra apenas o peso das fontes"
    )
    parser.add_argument(
        "--confidencial", action="store_true",
        help="procura indicios de material interno exposto na base",
    )
    args = parser.parse_args()

    import chromadb

    collection, modelo = explica_embeddings.collection_for(
        chromadb.PersistentClient(path=args.chroma_path),
        args.collection,
        args.embedding,
        create=False,
    )
    total = collection.count()
    print(f"Collection: {args.collection} ({total} trechos) | Embedding: {modelo}\n")

    todos = collection.get(include=["metadatas"])
    contagem: dict[str, int] = {}
    for metadado in todos["metadatas"]:
        fonte = metadado.get("source", "?")
        contagem[fonte] = contagem.get(fonte, 0) + 1

    print("PESO DE CADA FONTE NO INDICE")
    for fonte, quantos in sorted(contagem.items(), key=lambda x: -x[1]):
        fatia = quantos / max(1, total)
        if fatia < 0.01 and quantos < 20:
            continue
        alerta = "  <-- pesa demais" if fatia > 0.05 else ""
        print(f"  {quantos:5d} ({fatia * 100:4.1f}%)  {fonte[:66]}{alerta}")
    print(f"\n  ... e mais {sum(1 for q in contagem.values() if q < 20)} fontes menores")

    if args.confidencial:
        escanear_confidencial(collection, max(args.top, 8))
        return 0

    if args.so_peso:
        return 0

    perguntas: list[str] = list(args.pergunta)
    for tema in args.tema or sorted(TEMAS):
        perguntas.extend(TEMAS[tema])

    print("\n\nQUEM RESPONDE O QUE")
    print("Onde dois documentos discordarem sobre o mesmo assunto, um esta velho.\n")
    for pergunta in perguntas:
        print(f"? {pergunta}")
        resultado = collection.query(query_texts=[pergunta], n_results=args.top)
        for metadado, documento in zip(
            resultado["metadatas"][0], resultado["documents"][0]
        ):
            fonte = metadado.get("source", "?")
            excerto = " ".join(str(documento).split())[: args.trecho]
            print(f"    {fonte[:52]}")
            print(f"      {excerto}...")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
