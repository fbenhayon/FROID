#!/usr/bin/env python3
"""Indexa o acervo do FROID Explica NR-1 numa collection SEPARADA.

Por que separada, e nao um filtro sobre a collection clinica:

  O produto inteiro se sustenta numa fronteira — o empregador nunca alcanca o
  material clinico, e o profissional de saude nunca precisa do corporativo.
  Filtro e uma condicao que alguem pode esquecer de aplicar numa consulta nova;
  collection separada e uma condicao que nao existe para ser esquecida. Se a
  busca do NR-1 abrir a collection errada, ela nao encontra nada — em vez de
  encontrar o que nao devia.

O que entra:

  * as notas tecnicas do FROID sobre NR-1 (knowledge/approved/.../FROID_NR1_*)
  * as fontes primarias em docs/normas/primarias — texto da norma e publicacoes
    oficiais do MTE, que sao citaveis ao cliente e ao auditor
  * as secundarias — doutrina e material de entidade, citaveis com atribuicao,
    como interpretacao. Sai com --sem-secundarias
  * os DOCUMENTOS CONTRATUAIS vigentes: Termos de Uso NR-1, Contrato de
    Prestacao de Servico NR-1 e Politica de Privacidade

    Eles nao sao lidos de arquivo: sao renderizados de `legal_documents`, a
    mesma fonte que a tela do contrato e o comprovante de aceite usam. Indexar
    uma copia deles seria criar um texto paralelo que envelhece sozinho — e o
    comprovante prova um sha256, entao divergencia entre a copia e o vigente
    nao seria detalhe. Cada trecho carrega a versao e a digital do documento
    de onde saiu.

O que NUNCA entra, e o script recusa:

  * docs/normas/pareceres — parecer da nossa assessoria juridica sobre os
    NOSSOS contratos. E opiniao sobre documento nosso, nao norma, e citar isso
    a um cliente seria apresentar como fonte externa aquilo que nos encomendamos
  * qualquer nota clinica do FROID

Uso, de dentro do conteiner do backend:

    python tools/indexar_nr1_explica.py --reset
    python tools/indexar_nr1_explica.py --conferir
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
SERVER_DIR = TOOLS_DIR.parent
REPO_DIR = SERVER_DIR.parent
for caminho in (str(SERVER_DIR), str(TOOLS_DIR)):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

import explica_embeddings  # noqa: E402

# A parte trabalhosa — dividir o markdown em trechos que caibam no modelo,
# derivar titulo e gerar identificador estavel — ja existe e ja foi ajustada
# depois de um defeito real de truncamento. Reimplementar aqui produziria uma
# segunda versao para divergir da primeira.
from ingest_approved_sources import (  # noqa: E402
    chunk_markdown,
    stable_id,
    title_from_markdown,
)

COLLECTION_NR1 = os.getenv("FROID_NR1_CHROMA_COLLECTION", "froid_nr1_knowledge")
COLLECTION_CLINICA = os.getenv(
    "FROID_CHROMA_COLLECTION", "froid_clinical_knowledge"
)
CHROMA_PATH = Path(os.getenv("FROID_CHROMA_PATH", "/data/chroma_db"))

NOTAS_FROID = SERVER_DIR / "knowledge" / "approved" / "Notas_tecnicas_FROID"


def _pasta_das_normas() -> Path:
    """Onde esta o texto das normas, no conteiner ou no repositorio.

    No conteiner o backend e construido com contexto ./froid-server e nao
    alcanca a raiz do repositorio: docs/normas so existe ali por ponto de
    montagem (/normas, definido no docker-compose). Fora do conteiner, vale o
    caminho do repositorio.
    """
    candidatos = [
        Path(os.getenv("FROID_NORMAS_DIR", "").strip() or "/normas"),
        REPO_DIR / "docs" / "normas",
    ]
    for caminho in candidatos:
        if (caminho / "primarias").is_dir():
            return caminho
    return candidatos[-1]


NORMAS = _pasta_das_normas()

PALAVRAS_POR_TRECHO = 150
SOBREPOSICAO = 40


def fontes(incluir_secundarias: bool) -> list[tuple[Path, str]]:
    """(arquivo, classe de citabilidade), na ordem de confianca.

    A classe viaja com o trecho ate a resposta. Sem ela o modelo trata "o que a
    norma diz" e "o que uma consultoria escreveu sobre a norma" como a mesma
    coisa — e a diferenca entre as duas e exatamente o que um auditor cobra.
    """
    encontrados: list[tuple[Path, str]] = []

    for arquivo in sorted(NOTAS_FROID.glob("FROID_NR1_*.md")):
        encontrados.append((arquivo, "nota-froid"))

    primarias = NORMAS / "primarias"
    if primarias.exists():
        for arquivo in sorted(primarias.glob("*.md")):
            encontrados.append((arquivo, "norma"))

    if incluir_secundarias:
        secundarias = NORMAS / "secundarias"
        if secundarias.exists():
            for arquivo in sorted(secundarias.glob("*.md")):
                encontrados.append((arquivo, "interpretacao"))

    return encontrados


# Documentos contratuais que o acervo do NR-1 pode conhecer. A politica de
# privacidade entra porque metade das perguntas de compliance e sobre
# tratamento de dado; os contratos de profissional e de clinica NAO entram,
# porque sao do outro produto.
CHAVES_CONTRATUAIS = ("terms_nr1", "nr1_company_contract", "privacy")


def trechos_contratuais() -> list[dict]:
    """Secoes dos documentos vigentes, prontas para indexar.

    Uma secao por trecho, e nao o documento inteiro fatiado por contagem de
    palavras: clausula tem comeco e fim, e cortar no meio produziria um trecho
    que afirma metade de uma condicao. O titulo carrega o nome da secao para
    que a resposta possa dizer ONDE esta, que e o que o leitor precisa para
    conferir.
    """
    import legal_documents

    catalogo = legal_documents.public_legal_catalog()
    documentos = catalogo.get("documents") or {}
    encontrados: list[dict] = []
    for chave in CHAVES_CONTRATUAIS:
        documento = documentos.get(chave)
        if not documento:
            print(f"  aviso: documento {chave} ausente do catalogo")
            continue
        for secao in documento.get("sections") or []:
            corpo = str(secao.get("body") or "").strip()
            if len(corpo) < 80:
                continue
            encontrados.append(
                {
                    "texto": corpo,
                    "titulo": f"{documento['title']} — {secao.get('heading')}",
                    "fonte": chave,
                    "versao": str(documento.get("version") or ""),
                    "sha256": str(documento.get("sha256") or "")[:16],
                }
            )
    return encontrados


def recusar_o_que_nao_pode_entrar(arquivos: list[tuple[Path, str]]) -> None:
    """Trava explicita, e nao confianca no glob acima.

    O glob pode ser afrouxado por alguem que queira "indexar tudo de normas".
    Esta funcao existe para que essa mudanca falhe em vez de passar.
    """
    for arquivo, _ in arquivos:
        partes = {parte.lower() for parte in arquivo.parts}
        if "pareceres" in partes:
            raise SystemExit(
                f"RECUSADO: {arquivo} esta em pareceres/. Parecer da nossa "
                "assessoria sobre os nossos contratos nao e fonte citavel ao "
                "cliente."
            )
        if arquivo.parent == NOTAS_FROID and not arquivo.name.startswith(
            "FROID_NR1_"
        ):
            raise SystemExit(
                f"RECUSADO: {arquivo} e nota clinica. O acervo do NR-1 nao "
                "mistura os dois produtos."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chroma-path", type=Path, default=CHROMA_PATH)
    parser.add_argument("--collection", default=COLLECTION_NR1)
    parser.add_argument(
        "--reset", action="store_true",
        help="Apaga a collection antes de reindexar. Necessario ao trocar o "
             "modelo de embedding.",
    )
    parser.add_argument(
        "--sem-secundarias", dest="secundarias", action="store_false",
        default=True,
        help="Deixa de fora doutrina e material de entidade. O padrao e "
             "inclui-los, marcados como interpretacao.",
    )
    parser.add_argument(
        "--sem-contratos", dest="contratos", action="store_false",
        default=True,
        help="Deixa de fora os documentos contratuais vigentes.",
    )
    parser.add_argument(
        "--sem-normas", action="store_true",
        help="Indexa mesmo sem o texto das normas. Use apenas sabendo que o "
             "acervo respondera sobre a lei citando a nossa documentacao.",
    )
    parser.add_argument(
        "--embedding", default="auto", choices=["auto", "openai", "local"],
    )
    parser.add_argument(
        "--conferir", action="store_true",
        help="So relata o que ha na collection, sem escrever nada.",
    )
    args = parser.parse_args()

    if args.collection == COLLECTION_CLINICA:
        raise SystemExit(
            "RECUSADO: a collection do NR-1 nao pode ser a mesma da trilha "
            f"clinica ({COLLECTION_CLINICA}). A separacao e a fronteira."
        )

    from chromadb import PersistentClient

    args.chroma_path.mkdir(parents=True, exist_ok=True)
    client = PersistentClient(path=str(args.chroma_path))

    if args.conferir:
        try:
            colecao, modelo = explica_embeddings.collection_for(
                client, args.collection, args.embedding, create=False
            )
        except Exception as erro:
            print(f"Collection {args.collection} ainda nao existe: {erro}")
            return 1
        print(f"Collection: {args.collection}")
        print(f"Embedding:  {modelo}")
        print(f"Trechos:    {colecao.count()}")

        # Histograma por classe, e nao uma amostra de cinco linhas.
        #
        # A amostra saiu cinco vezes do mesmo arquivo e nao respondia a unica
        # pergunta que importa — "esta tudo la?". Uma indexacao sem o texto da
        # lei passou despercebida exatamente assim: o total parecia razoavel e
        # ninguem tinha como ver o que faltava.
        tudo = colecao.get(include=["metadatas"])
        contagem: dict[str, int] = {}
        arquivos: dict[str, set] = {}
        for metadado in tudo.get("metadatas") or []:
            classe = str((metadado or {}).get("classe") or "?")
            contagem[classe] = contagem.get(classe, 0) + 1
            arquivos.setdefault(classe, set()).add(
                str((metadado or {}).get("source") or "?")
            )
        print()
        print("Por classe de fonte:")
        for classe in ("norma", "interpretacao", "contrato", "nota-froid"):
            quantos = contagem.get(classe, 0)
            marca = "  " if quantos else "!!"
            print(
                f"{marca} {classe:14} {quantos:4} trechos, "
                f"{len(arquivos.get(classe, ()))} fonte(s)"
            )
        for classe, quantos in sorted(contagem.items()):
            if classe not in ("norma", "interpretacao", "contrato", "nota-froid"):
                print(f"   {classe:14} {quantos:4} trechos")

        if not contagem.get("norma"):
            for linha in (
                "",
                "!! SEM TEXTO DE NORMA no indice.",
                "   O acervo respondera sobre a lei citando a nossa",
                "   documentacao, e nao o texto dela.",
                "   Rode: docker compose up -d --force-recreate froid-backend",
                "   e reindexe com --reset.",
            ):
                print(linha)
            return 1
        print()
        print("Acervo completo.")
        return 0

    arquivos = fontes(args.secundarias)
    if not arquivos:
        raise SystemExit("Nenhuma fonte encontrada para indexar.")
    recusar_o_que_nao_pode_entrar(arquivos)

    # A ausencia do texto da norma NAO pode passar como sucesso.
    #
    # Na primeira indexacao em producao o script rodou, imprimiu "Pronto: 163
    # trechos" e indexou tudo MENOS as normas — porque o conteiner nao
    # enxergava docs/normas. Um acervo de NR-1 sem o texto da NR-1 responde a
    # tudo citando a nossa propria documentacao, que e exatamente a fonte que
    # um auditor nao aceita. Falha em silencio de novo, nao.
    normativas = [par for par in arquivos if par[1] == "norma"]
    if not normativas and not args.sem_normas:
        raise SystemExit(
            "\n".join(
                [
                    f"RECUSADO: nenhuma fonte normativa encontrada em {NORMAS}.",
                    "  Dentro do conteiner, docs/normas precisa estar montado",
                    "  em /normas (ver docker-compose.yml). Depois de atualizar",
                    "  o compose, rode: docker compose up -d froid-backend",
                    "  Para indexar mesmo assim, use --sem-normas — mas entenda",
                    "  o que isso significa: o acervo respondera sobre a lei",
                    "  citando a nossa documentacao, e nao o texto dela.",
                ]
            )
        )

    print(f"ChromaDB:   {args.chroma_path}")
    print(f"Collection: {args.collection}")
    print(f"Normas em:  {NORMAS} ({'encontrada' if (NORMAS / 'primarias').is_dir() else 'AUSENTE'})")
    print("Fontes:")
    for arquivo, classe in arquivos:
        print(f"  [{classe:14}] {arquivo.name}")

    if args.reset:
        try:
            client.delete_collection(args.collection)
            print("Collection anterior apagada.")
        except Exception:
            pass

    colecao, modelo = explica_embeddings.collection_for(
        client, args.collection, args.embedding
    )
    print(f"Embedding:  {modelo}")

    ids: list[str] = []
    documentos: list[str] = []
    metadados: list[dict] = []

    for arquivo, classe in arquivos:
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        titulo = title_from_markdown(arquivo, texto)
        trechos = chunk_markdown(texto, PALAVRAS_POR_TRECHO, SOBREPOSICAO)
        for indice, trecho in enumerate(trechos):
            ids.append(stable_id(arquivo, indice, trecho))
            documentos.append(trecho)
            metadados.append(
                {
                    "title": titulo,
                    "source": arquivo.name,
                    "classe": classe,
                    "modulo": "nr1",
                }
            )
        print(f"  {arquivo.name}: {len(trechos)} trechos")

    if args.contratos:
        contratuais = trechos_contratuais()
        print(f"  [contrato      ] {len(contratuais)} secoes dos documentos vigentes")
        for indice, secao in enumerate(contratuais):
            # O id deriva do titulo da secao e da digital do documento: quando o
            # documento muda de versao, o id muda e o trecho antigo nao fica
            # convivendo com o novo dentro do indice.
            bruto = f"contrato:{secao['fonte']}:{secao['sha256']}:{indice}"
            ids.append(hashlib.sha256(bruto.encode("utf-8")).hexdigest())
            documentos.append(secao["texto"])
            metadados.append(
                {
                    "title": secao["titulo"],
                    "source": secao["fonte"],
                    "classe": "contrato",
                    "modulo": "nr1",
                    "versao": secao["versao"],
                    "sha256": secao["sha256"],
                }
            )

    if not documentos:
        raise SystemExit("Nada a indexar.")

    # Em lotes: a API de embedding tem limite de tamanho de requisicao, e uma
    # falha no meio de um upsert unico deixaria a collection pela metade sem
    # dizer onde parou.
    LOTE = 100
    for inicio in range(0, len(documentos), LOTE):
        colecao.upsert(
            ids=ids[inicio : inicio + LOTE],
            documents=documentos[inicio : inicio + LOTE],
            metadatas=metadados[inicio : inicio + LOTE],
        )
        print(f"  indexados {min(inicio + LOTE, len(documentos))}/{len(documentos)}")

    print(f"\nPronto: {colecao.count()} trechos em {args.collection}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
