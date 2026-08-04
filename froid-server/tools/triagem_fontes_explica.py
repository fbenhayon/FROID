"""Triagem das fontes do FROID Explica, com postura de negar por padrao.

Ate agora a base era montada por exclusao: indexa tudo, tira o que parecer
ruim. Uma auditoria mostrou onde isso da: o FROID Explica podia responder
"quanto custa uma sessao" com o CUSTO interno, e a base guardava plano de
captacao, EBITDA e margem — consultaveis por qualquer cliente.

Exclusao por lista falha sempre do mesmo jeito: o documento novo entra por
padrao, e o proximo vazamento e questao de tempo.

Aqui a logica se inverte. O script le cada arquivo, procura indicios, e propoe
um manifesto onde NADA e indexado sem decisao explicita. O manifesto e um
arquivo de texto que voce revisa, corrige e versiona; a indexacao passa a ler
dele.

O script nao decide sozinho o que e segredo. Ele encontra e mostra a evidencia
— a frase exata, com a linha — para que a decisao seja de quem conhece o
negocio. Na duvida, ele propoe NAO indexar.

Uso:
    python tools/triagem_fontes_explica.py                     # relatorio
    python tools/triagem_fontes_explica.py --manifesto m.json  # grava proposta
    python tools/triagem_fontes_explica.py --detalhe "FIN.pdf" # evidencia de um
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.ingest_approved_sources as ingest  # noqa: E402


# Cada categoria e um risco distinto, e a gravidade nao e a mesma. Dinheiro e
# rota de produto sao segredo comercial; credencial e incidente de seguranca;
# literatura cientifica publicada nao e segredo de ninguem.
INDICIOS = {
    "financeiro": [
        r"\bebitda\b", r"\bvaluation\b", r"\bcusto total\b",
        # "margem" sozinho pega "margem de erro", que e estatistica e nao
        # dinheiro. Exige o qualificador financeiro.
        r"margem (de lucro|bruta|l[ií]quida|de contribui[cç][aã]o|operacional)",
        r"\bbreak-?even\b", r"\bcac\b", r"\bltv\b", r"\brunway\b",
        r"investimento seed", r"pr[eé]-?series", r"\bseries [ab]\b",
        r"rodada de (investimento|capta)", r"faturamento projetado",
        r"proje[cç][aã]o de receita", r"custo (por|/) sess[aã]o",
        r"early adopter", r"payback",
    ],
    "rota_de_produto": [
        r"pr[oó]ximas a[cç][oõ]es", r"\broadmap\b", r"\bbacklog\b",
        r"fase [2-9] \(", r"lan[cç]amento previsto", r"ainda n[aã]o implementad",
        r"em desenvolvimento", r"planejado para", r"vantagem competitiva",
        r"\bconcorrente[s]?\b",
    ],
    "credencial": [
        # Exige atribuicao de valor: a palavra solta aparece em qualquer texto
        # que explique como o convite anonimo funciona.
        r"(api[_ -]?key|secret|token|senha|password)\s*[:=]\s*\S",
        r"\.env\b", r"chave privada", r"bearer\s+[A-Za-z0-9._-]{12,}",
        r"sk-[A-Za-z0-9]{16,}",
    ],
    "juridico_interno": [
        r"estrat[eé]gia de defesa", r"parecer interno", r"risco jur[ií]dico",
        r"conting[eê]ncia", r"provis[aã]o para", r"litig",
    ],
    "infra_interna": [
        # Endereco IP de verdade: quatro octetos validos, e nao pode fazer
        # parte de uma sequencia pontuada maior. Sem isso, "1.5.4.4.5.3" — a
        # numeracao de subitem da NR-1 — era lida como endereco de servidor.
        r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])",
        r"postgres://", r"root@", r"ssh root",
    ],
}

# Sinais de que o documento e literatura publicada, e nao material do FROID.
# Nao tornam nada seguro por si so — apenas ajudam a separar as pilhas.
SINAIS_LITERATURA = [
    r"\bdoi\b", r"\babstract\b", r"\breferences\b", r"\bet al\.",
    r"\bpubmed\b", r"\bfrontiers in\b", r"\buniversity\b", r"\bjournal\b",
]


def classificar(texto: str) -> dict:
    baixo = texto.lower()
    achados: dict[str, list[str]] = {}
    for categoria, padroes in INDICIOS.items():
        for padrao in padroes:
            for m in re.finditer(padrao, baixo):
                inicio = max(0, m.start() - 70)
                trecho = " ".join(texto[inicio : m.end() + 70].split())
                achados.setdefault(categoria, [])
                if len(achados[categoria]) < 3:
                    achados[categoria].append(trecho)
    literatura = sum(1 for p in SINAIS_LITERATURA if re.search(p, baixo))
    return {"achados": achados, "sinais_literatura": literatura}


def propor(nome: str, analise: dict) -> tuple[bool, str]:
    """Proposta de indexacao. Na duvida, nao indexa."""
    achados = analise["achados"]
    if "credencial" in achados:
        return False, "credencial exposta"
    if "financeiro" in achados:
        return False, "material financeiro interno"
    if "rota_de_produto" in achados:
        return False, "rota de produto / posicao competitiva"
    if "juridico_interno" in achados:
        return False, "estrategia juridica interna"
    if "infra_interna" in achados:
        return False, "detalhe de infraestrutura"
    if analise["sinais_literatura"] >= 3:
        return True, "literatura publicada"
    if nome.lower().startswith("froid") or "froid" in nome.lower():
        # Documento do FROID sem indicio de segredo: provavelmente nota
        # tecnica citavel, mas quem confirma e uma pessoa.
        return False, "documento FROID — revisar antes de liberar"
    return False, "sem sinal claro — revisar"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifesto", type=Path, help="grava a proposta em JSON")
    parser.add_argument("--detalhe", help="mostra a evidencia de uma fonte")
    parser.add_argument("--aprovado", type=Path, action="append", default=None)
    args = parser.parse_args()

    fontes = [Path(p) for p in (args.aprovado or [])] or ingest.default_sources()
    arquivos: list[Path] = []
    for raiz in fontes:
        arquivos.extend(sorted(raiz.rglob("*.md")))
    print(f"Fontes analisadas: {len(arquivos)} arquivos\n")

    manifesto: dict[str, dict] = {}
    for path in arquivos:
        texto = path.read_text(encoding="utf-8", errors="ignore")
        analise = classificar(texto)
        indexar, motivo = propor(path.name, analise)
        manifesto[path.name] = {
            "indexar": indexar,
            "motivo": motivo,
            "categorias": sorted(analise["achados"]),
            "caminho": str(path),
        }
        if args.detalhe and args.detalhe.lower() in path.name.lower():
            print(f"=== {path.name}")
            print(f"    proposta: {'INDEXAR' if indexar else 'NAO INDEXAR'} ({motivo})")
            for categoria, trechos in analise["achados"].items():
                print(f"    [{categoria}]")
                for trecho in trechos:
                    print(f"        ...{trecho[:150]}...")
            print()

    if args.detalhe:
        return 0

    bloqueados: dict[str, list[str]] = {}
    liberados: list[str] = []
    for nome, item in manifesto.items():
        if item["indexar"]:
            liberados.append(nome)
        else:
            bloqueados.setdefault(item["motivo"], []).append(nome)

    print("PROPOSTA DE NAO INDEXAR")
    for motivo in sorted(bloqueados, key=lambda m: -len(bloqueados[m])):
        nomes = bloqueados[motivo]
        print(f"\n  {motivo} ({len(nomes)})")
        for nome in sorted(nomes)[:12]:
            categorias = manifesto[nome]["categorias"]
            extra = f"  [{', '.join(categorias)}]" if categorias else ""
            print(f"    - {nome[:62]}{extra}")
        if len(nomes) > 12:
            print(f"    ... e mais {len(nomes) - 12}")

    print(f"\n\nPROPOSTA DE INDEXAR ({len(liberados)})")
    for nome in sorted(liberados)[:20]:
        print(f"    + {nome[:70]}")
    if len(liberados) > 20:
        print(f"    ... e mais {len(liberados) - 20}")

    if args.manifesto:
        args.manifesto.write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nManifesto gravado em {args.manifesto}")
        print("Revise, ajuste 'indexar' onde discordar, e passe o arquivo para")
        print("ingest_approved_sources.py --manifesto.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
