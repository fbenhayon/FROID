"""Escolha do modelo de embedding do FROID Explica.

Centralizado porque indexacao e consulta PRECISAM usar o mesmo modelo. Vetores
gerados por modelos diferentes nao sao comparaveis, e o erro nao aparece como
falha: aparece como busca que devolve qualquer coisa.

Por que sair do modelo padrao da ChromaDB:

  all-MiniLM-L6-v2 e treinado essencialmente em ingles e trunca em 256 tokens.
  Todas as perguntas reais do FROID chegam em portugues, muitas vezes em
  linguagem coloquial — "meu chefe vai ver o que eu respondi", "o questionario
  pergunta sobre a minha saude mental". Medindo com
  tools/verify_explica_retrieval.py, o acerto ficou em 50%: as perguntas
  redigidas como documento acertavam, as redigidas como gente falhavam.

  text-embedding-3-small e multilingue, aceita 8191 tokens e ja esta ao alcance
  porque a chave da OpenAI existe no ambiente. O custo e desprezivel para um
  corpus deste tamanho, e a indexacao roda uma vez por atualizacao de fonte.

Trocar o modelo muda a dimensao do vetor. A collection precisa ser recriada
com --reset; sem isso a ChromaDB recusa ou, pior, mistura espacos.
"""

from __future__ import annotations

import os


LOCAL_MODEL = "all-MiniLM-L6-v2"
OPENAI_MODEL = "text-embedding-3-small"


def resolve_mode(requested: str = "auto") -> str:
    """Decide entre 'openai' e 'local'.

    'auto' prefere a OpenAI quando ha chave, porque e a unica das duas que
    entende portugues coloquial. Sem chave, cai no modelo local para que a
    indexacao nunca fique impossivel — mas o chamador deve avisar que a
    qualidade sera menor.
    """
    requested = (requested or "auto").strip().lower()
    if requested not in {"auto", "openai", "local"}:
        raise ValueError(f"Modo de embedding invalido: {requested!r}")
    if requested == "auto":
        return "openai" if os.getenv("OPENAI_API_KEY", "").strip() else "local"
    if requested == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
        raise SystemExit(
            "OPENAI_API_KEY nao esta definido; use --embedding local ou "
            "configure a chave."
        )
    return requested


def embedding_function(mode: str = "auto"):
    """Funcao de embedding pronta para a ChromaDB, e o rotulo do modelo."""
    from chromadb.utils import embedding_functions

    resolved = resolve_mode(mode)
    if resolved == "openai":
        return (
            embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ["OPENAI_API_KEY"],
                model_name=OPENAI_MODEL,
            ),
            f"openai/{OPENAI_MODEL}",
        )
    return (
        embedding_functions.ONNXMiniLM_L6_V2(),
        f"local/{LOCAL_MODEL}",
    )


def collection_for(client, name: str, mode: str = "auto", create: bool = True):
    """Abre a collection ja amarrada ao modelo escolhido."""
    função, rotulo = embedding_function(mode)
    if create:
        return client.get_or_create_collection(name=name, embedding_function=função), rotulo
    return client.get_collection(name=name, embedding_function=função), rotulo
