# -*- coding: utf-8 -*-
"""Une, sob um mesmo `patient.id`, os registros do MESMO paciente que ficaram
com ids diferentes. Nao apaga nada.

    python3 tools/unir-pacientes-mesmo-nome.py                  # so mostra
    python3 tools/unir-pacientes-mesmo-nome.py --aplicar        # escreve

POR QUE O PAINEL DUPLICA

A linha de paciente vem de `patientGroupKey`, que agrupa por
`id || email || phone || document || name || sessionId`. Quando a mesma pessoa
foi cadastrada duas vezes, ou foi atendida uma vez com cadastro e outra sem, os
relatorios carregam ids diferentes e viram DUAS linhas com o mesmo nome. O
painel esta exibindo o dado com fidelidade; o duplicado esta no acervo.

O QUE ELE UNE, E O QUE NAO UNE

Une apenas nomes IDENTICOS depois de normalizar caixa, acento e espaco, e
apenas DENTRO do mesmo profissional — nunca atravessa contas. Nomes parecidos
mas diferentes ("Sarracchi" e "Saracchi") NAO sao unidos: sao listados no fim
para voce decidir, porque adivinhar parentesco entre grafias e como se cria
prontuario de uma pessoa que nao existe.

Paciente sem nome fica de fora por padrao. Sao 28 sessoes num unico balde e
juntar estranhos sob um id so e o oposto do que se quer. `--incluir-sem-nome`
existe, e nao deveria ser usado sem saber exatamente por que.

O BACKEND PRECISA ESTAR PARADO, pela mesma razao do outro utilitario:
_save_identity_state() serializa a memoria do processo e regravaria por cima.

    docker compose stop froid-backend
    python3 tools/unir-pacientes-mesmo-nome.py
    python3 tools/unir-pacientes-mesmo-nome.py --aplicar
    docker compose start froid-backend
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
import time
import unicodedata

SEM_NOME = {"", "paciente sem nome", "sem nome", "(sem nome)"}


def normalizar_nome(valor) -> str:
    bruto = unicodedata.normalize("NFD", str(valor or ""))
    sem_marca = "".join(c for c in bruto if unicodedata.category(c) != "Mn")
    return " ".join(sem_marca.strip().lower().split())


def normalizar_email(valor) -> str:
    return str(valor or "").strip().lower()


def carregar(caminho: str) -> dict:
    if not os.path.exists(caminho):
        raise SystemExit("arquivo nao encontrado: " + caminho)
    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if not isinstance(dados, dict):
        raise SystemExit("conteudo inesperado (nao e objeto JSON): " + caminho)
    return dados


def gravar_preservando(caminho: str, dados: dict) -> None:
    anterior = os.stat(caminho)
    temporario = caminho + ".unir.tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)
    os.chmod(caminho, anterior.st_mode & 0o7777)
    if hasattr(os, "chown") and os.geteuid() == 0:
        os.chown(caminho, anterior.st_uid, anterior.st_gid)


def paciente_do_relatorio(relatorio: dict) -> dict:
    paciente = relatorio.get("patient")
    return paciente if isinstance(paciente, dict) else {}


def dono_do_relatorio(relatorio: dict) -> str:
    profissional = relatorio.get("professional")
    profissional = profissional if isinstance(profissional, dict) else {}
    return normalizar_email(
        relatorio.get("professionalEmail")
        or relatorio.get("professional_email")
        or profissional.get("email")
        or ""
    )


def escolher_canonico(ids_com_peso: dict, cadastrados: set) -> str:
    """Id que fica. Prefere um que exista no cadastro; depois o mais usado."""
    def chave(item):
        identificador, peso = item
        return (0 if identificador in cadastrados else 1, -peso, identificador)

    return sorted(ids_com_peso.items(), key=chave)[0][0]


def main() -> int:
    interpretador = argparse.ArgumentParser(
        description="Une sob um mesmo id os registros de pacientes homonimos."
    )
    interpretador.add_argument("--dados", default="/root/froid-project/data")
    interpretador.add_argument("--incluir-sem-nome", action="store_true")
    interpretador.add_argument("--aplicar", action="store_true")
    opcoes = interpretador.parse_args()

    caminho_relatorios = os.path.join(opcoes.dados, "session_reports.json")
    caminho_identidade = os.path.join(opcoes.dados, "identity_state.json")
    relatorios = carregar(caminho_relatorios)
    identidade = carregar(caminho_identidade)
    cadastrados = set(map(str, (identidade.get("patients") or {}).keys()))
    convites = identidade.get("session_invites") or {}

    # (dono, nome normalizado) -> {id ou "": quantidade de relatorios}
    grupos: dict = {}
    exibicao: dict = {}
    for relatorio in relatorios.values():
        if not isinstance(relatorio, dict):
            continue
        paciente = paciente_do_relatorio(relatorio)
        nome = normalizar_nome(paciente.get("name") or relatorio.get("patientName"))
        if nome in SEM_NOME and not opcoes.incluir_sem_nome:
            continue
        if not nome:
            continue
        chave = (dono_do_relatorio(relatorio), nome)
        identificador = str(paciente.get("id") or relatorio.get("patientId") or "")
        grupos.setdefault(chave, {})
        grupos[chave][identificador] = grupos[chave].get(identificador, 0) + 1
        exibicao.setdefault(chave, paciente.get("name") or "(sem nome)")

    # So interessa quem tem mais de uma identidade sob o mesmo nome.
    a_unir = {
        chave: ids for chave, ids in grupos.items() if len([i for i in ids]) > 1
    }

    print("MODO:", "APLICAR (escreve)" if opcoes.aplicar else "CONFERENCIA (nao escreve)")
    print("pacientes distintos por (profissional, nome):", len(grupos))
    print("nomes com mais de um id:", len(a_unir))
    print()

    plano = {}
    for chave in sorted(a_unir, key=lambda c: (c[0], c[1])):
        dono, nome = chave
        ids = a_unir[chave]
        com_id = {i: n for i, n in ids.items() if i}
        canonico = escolher_canonico(com_id, cadastrados) if com_id else ""
        if not canonico:
            continue
        plano[chave] = canonico
        print("  " + exibicao[chave] + "   (" + (dono or "sem dono") + ")")
        for identificador in sorted(ids, key=lambda i: (i != canonico, i)):
            marca = "  <= FICA" if identificador == canonico else ""
            rotulo = identificador if identificador else "(sem id)"
            no_cadastro = " [no cadastro]" if identificador in cadastrados else ""
            print("     %-40s %2d sessoes%s%s" % (rotulo, ids[identificador], no_cadastro, marca))
        print()

    # Nomes parecidos, deliberadamente NAO unidos.
    nomes = sorted({nome for _dono, nome in grupos})
    parecidos = []
    for indice, nome in enumerate(nomes):
        for outro in nomes[indice + 1:]:
            if nome == outro:
                continue
            if difflib.SequenceMatcher(None, nome, outro).ratio() >= 0.86:
                parecidos.append((nome, outro))
    if parecidos:
        print("PARECIDOS, NAO UNIDOS (decida voce)")
        for nome, outro in parecidos:
            print("  -", nome, "<->", outro)
        print()

    if not plano:
        print("Nada a unir.")
        return 0
    if not opcoes.aplicar:
        print("Nada foi escrito. Para aplicar, repita com --aplicar.")
        return 0

    marca_tempo = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for caminho in (caminho_relatorios, caminho_identidade):
        copia = caminho + ".antes-de-unir-" + marca_tempo
        shutil.copy2(caminho, copia)
        print("copia de seguranca:", copia)

    sessoes_tocadas = set()
    tocados = 0
    for sessao, relatorio in relatorios.items():
        if not isinstance(relatorio, dict):
            continue
        paciente = paciente_do_relatorio(relatorio)
        nome = normalizar_nome(paciente.get("name") or relatorio.get("patientName"))
        chave = (dono_do_relatorio(relatorio), nome)
        canonico = plano.get(chave)
        if not canonico:
            continue
        atual = str(paciente.get("id") or relatorio.get("patientId") or "")
        if atual == canonico:
            continue
        novo_paciente = dict(paciente)
        novo_paciente["id"] = canonico
        relatorio["patient"] = novo_paciente
        relatorio["patientId"] = canonico
        sessoes_tocadas.add(str(relatorio.get("sessionId") or sessao))
        tocados += 1

    convites_tocados = 0
    for convite in convites.values():
        if not isinstance(convite, dict):
            continue
        sessao = str(convite.get("session_id") or "")
        if sessao not in sessoes_tocadas:
            continue
        nome = normalizar_nome(convite.get("patient_name"))
        chave = (normalizar_email(convite.get("professional_email")), nome)
        canonico = plano.get(chave)
        if canonico and str(convite.get("patient_id") or "") != canonico:
            convite["patient_id"] = canonico
            convites_tocados += 1

    identidade["session_invites"] = convites
    gravar_preservando(caminho_relatorios, relatorios)
    gravar_preservando(caminho_identidade, identidade)
    print()
    print("relatorios reapontados:", tocados)
    print("convites reapontados:", convites_tocados)
    print("Os registros antigos de paciente continuam no cadastro; nada foi apagado.")
    print("Suba o backend: docker compose start froid-backend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
