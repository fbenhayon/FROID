"""Libera no manifesto as notas do FROID que existem para ser lidas.

A triagem nega por padrao, e isso esta certo: documento do FROID sem revisao
humana nao entra. Mas o passo da revisao humana precisava existir, e nao
existia — o manifesto saiu com `indexar: false` em tudo que fala do FROID, a
reindexacao rodou assim, e o FROID Explica ficou sem uma unica nota propria.

O efeito nao foi busca vazia: foi busca ruim. Sobraram artigos de FACS, e o
modelo, sem fonte para o que lhe perguntavam, inventou. "Indice de Performance
Vocal" e "Indice de Dissonancia Vocal" nao existem — sao confabulacao de um
sistema sem base. Uma base incompleta mente com mais confianca que uma base
vazia.

Entao a revisao humana vira esta lista: explicita, versionada em git, revisada
em code review. Cada entrada diz por que aquela nota pode ser lida por
qualquer usuario, e o que NAO esta aqui continua negado.

Uso:
    python tools/liberar_notas_froid.py --manifesto /caminho/manifesto.json
    python tools/liberar_notas_froid.py --manifesto ... --conferir
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


# Nota -> por que ela e publica.
#
# O criterio e o mesmo da nota FROID_Fronteira_Medida_Interpretacao: entra o
# que o clinico precisa para INTERPRETAR a leitura; fica fora como o sistema
# CALCULA a leitura.
LIBERADAS: dict[str, str] = {
    "FROID_Ficha_Tecnica_IPM.md":
        "O que o IPM mede e o que nao afirma. Sem pesos, sem composicao.",
    "FROID_Ficha_Tecnica_IDM_e_Zonas.md":
        "O que o IDM mede e o que as zonas sao. Sem a matriz de projecao.",
    "FROID_Ficha_Tecnica_Dissonancia.md":
        "Como um evento e registrado e o que a contagem nao significa.",
    "FROID_Ficha_Tecnica_Sinais_Bioacusticos.md":
        "F0, jitter, shimmer, ZCR e loudness, com as referencias do Praat.",
    "FROID_Ficha_Tecnica_Espectral_Cepstral.md":
        "MFCC e bandas de modulacao, com a ressalva de que nao sao EEG.",
    "FROID_Ficha_Tecnica_Fluencia_e_Face.md":
        "Fluencia verbal e FACS, com os limites de captacao.",
    "FROID_NR1_Riscos_Psicossociais.md":
        "Responde a pergunta do trabalhador: meu chefe ve o que eu respondi?",
    "FROID_Estabilizacao_Clinica_Da_Tela.md":
        "Por que a tela nao oscila a cada segundo. Sem o vetor de pesos.",
    "FROID_Bibliografia_Cientifica_Verificada.md":
        "As fontes que sustentam cada afirmacao. Ja liberada pela triagem.",
}

# Deliberadamente FORA, para que a ausencia seja decisao e nao esquecimento.
FORA: dict[str, str] = {
    "FROID_Fronteira_Medida_Interpretacao.md":
        "Cita as frases proibidas para proibi-las. Um corte de 150 palavras "
        "entregaria a frase sem a coluna que a nega. Doutrina interna.",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifesto", type=Path, required=True)
    parser.add_argument("--conferir", action="store_true",
                        help="mostra o que mudaria, sem gravar")
    args = parser.parse_args()

    dados = json.loads(args.manifesto.read_text(encoding="utf-8"))
    alterados, ausentes, ja_liberados = [], [], []

    for nome, motivo in LIBERADAS.items():
        item = dados.get(nome)
        if item is None:
            ausentes.append(nome)
            continue
        if item.get("indexar") is True:
            ja_liberados.append(nome)
            continue
        item["indexar"] = True
        item["motivo"] = f"liberada por revisao: {motivo}"
        alterados.append(nome)

    for nome, motivo in FORA.items():
        item = dados.get(nome)
        if item is not None and item.get("indexar") is True:
            item["indexar"] = False
            item["motivo"] = f"mantida fora: {motivo}"
            alterados.append(f"{nome} (RETIRADA)")

    print(f"Manifesto: {args.manifesto}")
    print(f"  liberadas agora : {len(alterados)}")
    for nome in alterados:
        print(f"    + {nome}")
    if ja_liberados:
        print(f"  ja estavam liberadas: {len(ja_liberados)}")
    if ausentes:
        print(f"  NAO ENCONTRADAS no manifesto: {len(ausentes)}")
        for nome in ausentes:
            print(f"    ? {nome}")
        print("    (a triagem nao viu estes arquivos — confira as pastas)")

    total = sum(1 for i in dados.values() if i.get("indexar") is True)
    print(f"\n  total liberado no manifesto: {total} de {len(dados)}")

    if args.conferir:
        print("\n  --conferir: nada foi gravado.")
        return 0

    args.manifesto.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  Manifesto atualizado. Reindexe com --manifesto {args.manifesto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
