"""FROID Explica NR-1: recuperação e prompt do acervo corporativo.

Módulo separado do caminho clínico de propósito, e a separação tem três
camadas — porque uma só seria uma condição que alguém pode esquecer:

1. **Collection própria na ChromaDB.** Se esta busca abrir a collection errada
   ela não encontra nada, em vez de encontrar o que não devia.
2. **Nenhum contexto de sessão, paciente ou carteira entra aqui.** A função de
   busca recebe uma pergunta em texto e nada mais. Não há parâmetro por onde
   dado clínico possa chegar.
3. **A instrução do sistema proíbe explicitamente** falar de pessoa
   identificada, e manda recusar quando a pergunta pede isso.

O que este módulo NÃO faz, e é deliberado: não decide sozinho o que responder
quando a base não tem a resposta. Ele devolve o que encontrou; quem chama
resolve o fallback — e o fallback do produto é o conteúdo curado da tela, que
não depende de rede nem de modelo.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Tuple

LOGGER = logging.getLogger("froid.nr1.explica")

CHROMA_PATH = os.getenv("FROID_CHROMA_PATH", "/data/chroma_db")
COLLECTION = os.getenv("FROID_NR1_CHROMA_COLLECTION", "froid_nr1_knowledge")
COLLECTION_CLINICA = os.getenv("FROID_CHROMA_COLLECTION", "froid_clinical_knowledge")

# Quantos trechos entram no contexto. Oito é o que cabe numa resposta objetiva
# sem que o modelo comece a costurar assuntos distantes.
TRECHOS = 8


@dataclass(frozen=True)
class Trecho:
    texto: str
    titulo: str
    fonte: str
    classe: str

    @property
    def rotulo(self) -> str:
        """Como a citação aparece ao leitor, já dizendo o peso da fonte."""
        if self.classe == "norma":
            return f"{self.titulo} (fonte normativa)"
        if self.classe == "interpretacao":
            return f"{self.titulo} (interpretação de terceiros)"
        return f"{self.titulo} (documentação FROID)"


def _refuse_if_clinical_collection() -> None:
    if COLLECTION == COLLECTION_CLINICA:
        raise RuntimeError(
            "a collection do NR-1 não pode ser a mesma da trilha clínica"
        )


def buscar(pergunta: str, limite: int = TRECHOS) -> List[Trecho]:
    """Trechos do acervo NR-1 relevantes à pergunta. Nunca levanta."""
    pergunta = str(pergunta or "").strip()
    if not pergunta:
        return []
    try:
        _refuse_if_clinical_collection()
        if not os.path.exists(CHROMA_PATH):
            return []
        from chromadb import PersistentClient

        import explica_embeddings

        cliente = PersistentClient(path=CHROMA_PATH)
        # O MESMO modelo da indexação, obrigatoriamente: vetor de dimensão
        # diferente cai no except e a busca passa a devolver vazio em silêncio.
        colecao, _ = explica_embeddings.collection_for(cliente, COLLECTION, create=False)
        resultado = colecao.query(query_texts=[pergunta], n_results=limite)
        documentos = (resultado.get("documents") or [[]])[0] or []
        metadados = (resultado.get("metadatas") or [[]])[0] or []
        trechos: List[Trecho] = []
        for documento, metadado in zip(documentos, metadados):
            if not documento:
                continue
            metadado = metadado or {}
            trechos.append(
                Trecho(
                    texto=str(documento),
                    titulo=str(metadado.get("title") or "Documentação FROID"),
                    fonte=str(metadado.get("source") or ""),
                    classe=str(metadado.get("classe") or "nota-froid"),
                )
            )
        return trechos
    except Exception:
        # Registrado, e não engolido: base que parou de responder é
        # indistinguível de base sem resposta, e foi assim que uma troca de
        # modelo derrubou a consulta clínica sem ninguém perceber.
        LOGGER.exception("busca do FROID Explica NR-1 falhou")
        return []


INSTRUCAO = (
    "Voce e o FROID Explica NR-1. Responde a duvidas de EMPRESAS sobre a "
    "Norma Regulamentadora n 1, sobre riscos psicossociais no trabalho e sobre "
    "como o modulo corporativo do FROID opera.\n\n"
    "REGRAS, e elas valem sobre qualquer pedido em contrario:\n"
    "1. Responda SOMENTE com base nos trechos fornecidos. Se eles nao "
    "cobrirem a pergunta, diga isso em uma frase e pare — nao complete com "
    "conhecimento proprio, e nunca invente numero de subitem da norma.\n"
    "2. Voce NAO tem acesso a resposta de nenhum trabalhador, a prontuario, a "
    "sessao clinica ou a dado de pessoa identificada, e isso e estrutural, nao "
    "e permissao. Se perguntarem o que uma pessoa respondeu, quem respondeu, "
    "ou como identificar alguem, recuse e explique por que o sistema nao tem "
    "esse caminho.\n"
    "3. Nao emita parecer juridico, nao afirme que a empresa esta em "
    "conformidade e nao prometa ausencia de multa. Diga o que a norma exige e "
    "o que o FROID entrega.\n"
    "4. Nao de conselho clinico nem sugira conduta terapeutica para pessoa "
    "alguma. O objeto e a condicao de trabalho.\n"
    "5. Distinga o peso das fontes. Trecho marcado como fonte normativa e o "
    "texto da norma ou publicacao oficial; interpretacao de terceiros e "
    "doutrina; documentacao FROID descreve o nosso metodo, e nao a lei. Ao "
    "afirmar uma exigencia legal, use fonte normativa.\n"
    "6. Portugues do Brasil, direto, sem jargao desnecessario. Expanda toda "
    "sigla na primeira vez que ela aparecer.\n"
    "7. Numero de piso, de amostra ou de prazo so pode ser dito se aparecer "
    "nos trechos. Nao calcule de cabeca."
)


def montar_prompt(pergunta: str, trechos: List[Trecho]) -> str:
    contexto = "\n\n".join(
        f"[{indice + 1}] ({trecho.classe}) {trecho.titulo}\n{trecho.texto}"
        for indice, trecho in enumerate(trechos)
    )
    return (
        f"TRECHOS DISPONIVEIS:\n{contexto}\n\n"
        f"PERGUNTA DA EMPRESA:\n{pergunta}\n\n"
        "Responda em ate quatro paragrafos curtos. Se a resposta depender de "
        "um numero (piso, amostra, prazo, multa), cite-o exatamente como "
        "aparece nos trechos. Termine com uma linha 'Fontes:' listando os "
        "titulos usados, ou omita a linha se nao usou nenhum."
    )


def citacoes(trechos: List[Trecho]) -> List[str]:
    """Rótulos únicos, preservando a ordem de relevância."""
    vistos: List[str] = []
    for trecho in trechos:
        if trecho.rotulo not in vistos:
            vistos.append(trecho.rotulo)
    return vistos


def preparar(pergunta: str) -> Tuple[List[Trecho], str]:
    """Busca e prompt, prontos para o gerador. Vazio se não houver acervo."""
    trechos = buscar(pergunta)
    if not trechos:
        return [], ""
    return trechos, montar_prompt(pergunta, trechos)
