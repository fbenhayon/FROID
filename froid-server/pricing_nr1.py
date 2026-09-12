"""Motor de precificacao do FROID NR-1: faixas progressivas, centavos, hash.

PORTADO de `froid-pricing-engine` (TypeScript), escrito pelo dono em
11/09/2026. As estruturas e os nomes de campo foram preservados de proposito:
um port com outro vocabulario nao se confere contra a origem, e a origem e o
unico outro lugar onde esta conta existe.

POR QUE ELE EXISTE
------------------
Ate hoje o preco do NR-1 nao tinha fonte de execucao. Ele vivia em DUAS copias
declaradas — uma constante num arquivo de TESTE e um gerador de planilha — e em
mais dez copias publicadas: oito paginas do site em quatro idiomas, o modelo de
proposta e o anexo de consulta por porte. Nenhuma delas calculava nada: todas
eram numeros digitados a mao.

O sintoma apareceu em 11/09/2026 com tres bases diferentes em circulacao para o
MESMO componente — R$ 1.200 na proposta enviada a um cliente, R$ 500 no site e
no simulador, R$ 200 no motor novo. Para 263 trabalhadores em 11 estabelecimentos
isso da R$ 16.737,50, R$ 9.037,50 ou R$ 5.737,50 por mes. Tres numeros, o mesmo
cliente, a mesma tabela de faixas.

Este modulo e a fonte. Toda copia publicada passa a ser conferida contra ele.

DINHEIRO E INTEIRO
------------------
Tudo em centavos, sempre `int`. Preco em ponto flutuante acumula erro que so
aparece na soma de um efetivo grande, e o lugar onde ele aparece e a fatura.

O HASH
------
`pricing_hash` reproduz byte a byte o `JSON.stringify` do payload canonico da
origem em TypeScript, entao as duas implementacoes produzem o MESMO sha256 para
a mesma tabela. Nao e enfeite: e como se confere que o port nao mudou a regra —
e e o que permite uma proposta gravada em 2026 provar, em 2030, qual tabela a
produziu.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


# ---------------------------------------------------------------- a tabela ---
# A FONTE. Preco novo NAO se edita aqui em cima de uma versao ja usada: cria-se
# uma versao nova, com `valid_from` proprio. Sobrescrever uma tabela historica
# apaga a explicacao de uma proposta que ja foi assinada.
TABELA_VIGENTE: dict[str, Any] = {
    "code": "FROID-PRICING-2026-V01",
    "name": "Tabela Comercial FROID NR-1",
    "version": "1.0",
    "validFrom": "2026-01-01",
    "validTo": None,
    "status": "active",
    # R$ 200,00 por estabelecimento/mes. Decisao do dono em 11/09/2026, que
    # substituiu os R$ 500 publicados ate entao. A proposta enviada a TATICCA em
    # 28/08/2026 carrega R$ 1.200 e NAO se reescreve: preco novo vale para
    # proposta nova, e documento comercial ja enviado e registro, nao rascunho.
    "baseEstablishmentCents": 20_000,
    "tiers": [
        {"order": 1, "lowerBound": 1, "upperBound": 100, "workerPriceCents": 1_500},
        {"order": 2, "lowerBound": 101, "upperBound": 300, "workerPriceCents": 1_250},
        {"order": 3, "lowerBound": 301, "upperBound": 1_000, "workerPriceCents": 930},
        {"order": 4, "lowerBound": 1_001, "upperBound": None, "workerPriceCents": 655},
    ],
}


class TabelaInvalida(ValueError):
    """Tabela que nao pode precificar. Recusar e a saida certa: faixa com buraco
    nao produz erro, produz cobranca a menos que ninguem confere."""


# ------------------------------------------------------------- validacao ---
def validate_pricing_table(table: dict[str, Any]) -> None:
    """As faixas cobrem a reta inteira a partir de 1, sem buraco nem sobreposicao.

    A verificacao nao e formalidade. Uma faixa que comeca em 102 quando a
    anterior termina em 100 deixa o centesimo primeiro trabalhador sem preco: a
    conta fecha, o total sai menor, e nada acusa.
    """
    base = table.get("baseEstablishmentCents")
    if not isinstance(base, int) or isinstance(base, bool) or base < 0:
        raise TabelaInvalida("baseEstablishmentCents deve ser inteiro em centavos.")

    tiers = sorted(table.get("tiers") or [], key=lambda t: t["order"])
    if not tiers:
        raise TabelaInvalida("A tabela deve possuir ao menos uma faixa.")

    esperado = 1
    for indice, tier in enumerate(tiers):
        if tier["lowerBound"] != esperado:
            raise TabelaInvalida(
                f"Faixa {tier['order']}: lowerBound esperado {esperado}."
            )
        preco = tier.get("workerPriceCents")
        if not isinstance(preco, int) or isinstance(preco, bool) or preco < 0:
            raise TabelaInvalida(
                f"Faixa {tier['order']}: preco deve ser inteiro em centavos."
            )
        superior = tier.get("upperBound")
        if superior is not None:
            if not isinstance(superior, int) or superior < tier["lowerBound"]:
                raise TabelaInvalida(f"Faixa {tier['order']}: upperBound invalido.")
            esperado = superior + 1
        elif indice != len(tiers) - 1:
            raise TabelaInvalida("Somente a ultima faixa pode ter limite superior nulo.")


# ---------------------------------------------------------------- calculo ---
def calculate_pricing(
    table: dict[str, Any], workers: int, establishments: int
) -> dict[str, Any]:
    """O valor mensal, em centavos, com a memoria de calculo por faixa.

    A memoria acompanha o resultado porque proposta sem memoria de calculo
    obriga o cliente a confiar no total — e a primeira pergunta de qualquer
    comprador e "de onde saiu esse numero".
    """
    for valor, nome in ((workers, "workers"), (establishments, "establishments")):
        if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
            raise TabelaInvalida(f"{nome} deve ser um inteiro maior que zero.")
    validate_pricing_table(table)

    base_subtotal = establishments * table["baseEstablishmentCents"]

    workers_subtotal = 0
    memoria: list[dict[str, int]] = []
    for tier in sorted(table["tiers"], key=lambda t: t["order"]):
        superior = tier["upperBound"] if tier["upperBound"] is not None else workers
        na_faixa = max(0, min(workers, superior) - tier["lowerBound"] + 1)
        subtotal = na_faixa * tier["workerPriceCents"]
        workers_subtotal += subtotal
        memoria.append(
            {
                "order": tier["order"],
                "workersInTier": na_faixa,
                "workerPriceCents": tier["workerPriceCents"],
                "subtotalCents": subtotal,
            }
        )

    total = base_subtotal + workers_subtotal
    return {
        "workers": workers,
        "establishments": establishments,
        "baseSubtotalCents": base_subtotal,
        "workersSubtotalCents": workers_subtotal,
        "monthlyTotalCents": total,
        # Arredondamento comercial, e SO para exibicao: o total cobravel e
        # `monthlyTotalCents`. Multiplicar este valor pelo efetivo de volta nao
        # devolve o total, e nenhuma fatura deve ser montada a partir dele.
        #
        # ARITMETICA INTEIRA, E NAO `round(total / workers)`.
        #
        # `round()` do Python e BANCARIO — empate vai para o par: round(2.5)==2.
        # `Math.round` do JavaScript, que a origem usa, e metade para CIMA: 3.
        # Numa varredura de 12 estabelecimentos por 4.000 trabalhadores os dois
        # divergem em 33 combinacoes, e a mais banal delas e 64 trabalhadores num
        # estabelecimento: a origem diz 1813 e o `round()` dizia 1812.
        #
        # Os sete casos do oraculo nao continham nenhum empate, entao a bateria
        # passava verde sobre uma divergencia real — publicada no simulador do
        # site e na etapa do cadastro. `(2*a + b) // (2*b)` e metade para cima
        # sem passar por float, entao tambem nao depende da precisao do double
        # num efetivo grande.
        "perWorkerMonthCents": (2 * total + workers) // (2 * workers),
        "tierBreakdown": memoria,
    }


# ------------------------------------------------------------------ hash ---
def canonical_pricing_payload(table: dict[str, Any]) -> dict[str, Any]:
    """So o que DECIDE preco entra no hash.

    Nome e status ficam de fora de proposito: renomear a tabela nao muda a
    conta, e se entrassem, uma correcao de rotulo invalidaria a digital de toda
    proposta ja emitida sob ela.
    """
    return {
        "code": table["code"],
        "version": table["version"],
        "validFrom": table["validFrom"],
        "validTo": table["validTo"],
        "baseEstablishmentCents": table["baseEstablishmentCents"],
        "tiers": [
            {
                "order": t["order"],
                "lowerBound": t["lowerBound"],
                "upperBound": t["upperBound"],
                "workerPriceCents": t["workerPriceCents"],
            }
            for t in sorted(table["tiers"], key=lambda t: t["order"])
        ],
    }


def pricing_hash(table: dict[str, Any]) -> str:
    """sha256 do payload canonico, igual ao da origem em TypeScript.

    `separators=(",", ":")` reproduz o `JSON.stringify` sem espacos, e a ordem
    das chaves e a de insercao em `canonical_pricing_payload` — a mesma da
    origem. Um espaco a mais aqui produziria uma digital diferente para a mesma
    tabela, e a conferencia entre as duas implementacoes deixaria de valer.
    """
    canonico = json.dumps(
        canonical_pricing_payload(table), ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


# ------------------------------------------------------------- conversao ---
def reais(centavos: int) -> float:
    """Centavos para reais, para comparar com texto publicado. Nunca para somar."""
    return centavos / 100


def formatar_brl(centavos: int, casas: int = 2) -> str:
    """R$ 5.737,50 — escrito aqui, e nao em cada tela que exibe preco.

    Sem `locale`: a formatacao pt-BR de um servidor depende de o sistema ter a
    localidade instalada, e no contentor ela nao esta. Formatar a mao e feio e
    e deterministico; depender de locale produz "5737.50" em producao e
    "5.737,50" na maquina de quem testou.
    """
    inteiro, resto = divmod(int(centavos), 100)
    corpo = f"{inteiro:,}".replace(",", ".")
    return f"R$ {corpo}" + (f",{resto:02d}" if casas else "")


def simular(
    workers: int, establishments: int, table: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """A simulacao com a digital da tabela junto.

    Devolver o valor sem a tabela que o produziu torna a proposta
    irreproduzivel: seis meses depois ninguem sabe se aquele numero saiu da
    tabela vigente ou de uma que ja foi substituida.
    """
    tabela = table or TABELA_VIGENTE
    calculo = calculate_pricing(tabela, workers, establishments)
    calculo["pricingTable"] = {
        "code": tabela["code"],
        "version": tabela["version"],
        "validFrom": tabela["validFrom"],
        "sha256": pricing_hash(tabela),
    }
    return calculo
