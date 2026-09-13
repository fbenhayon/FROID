# -*- coding: utf-8 -*-
"""Transfere para UMA conta os pacientes das contas profissionais de um mesmo
primeiro nome. Nao apaga nada.

    python3 tools/unificar-pacientes-fabio.py                  # so mostra
    python3 tools/unificar-pacientes-fabio.py --aplicar        # escreve

O QUE ELE FAZ

Reescreve o dono em tres lugares, e nada alem disso:

    session_reports.json   professionalEmail, professional.email/.name
    identity_state.json    session_invites[*].professional_email
    identity_state.json    session_owners[session_id]

Relatorio sem `professionalEmail` tambem passa a apontar para o destino. Hoje
esses aparecem como seus por causa do padrao FROID_LEGACY_REPORT_OWNER no
codigo: se alguem mudar essa variavel de ambiente, eles trocam de dono sozinhos,
sem erro e sem log. Carimbar encerra a dependencia.

O QUE ELE NAO FAZ, DE PROPOSITO

Nao apaga conta, relatorio, paciente nem convite. Nao encosta em contas cujo
primeiro nome nao seja o procurado. Nao reescreve `organization_id` — a posse
e do profissional, e mexer na organizacao move pool de credito. Nao encosta em
`consent_ledger`: consentimento e historico juridico, nao cadastro.

O BACKEND PRECISA ESTAR PARADO

`_save_identity_state()` serializa os dicionarios que o processo mantem em
MEMORIA. Com o backend no ar, a proxima operacao qualquer regrava
identity_state.json inteiro por cima — e a transferencia some sem deixar
vestigio. Pare o contentor antes:

    docker compose stop froid-backend
    python3 tools/unificar-pacientes-fabio.py            # confira
    python3 tools/unificar-pacientes-fabio.py --aplicar
    docker compose start froid-backend
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import unicodedata


def sem_acento(texto) -> str:
    bruto = str(texto or "")
    decomposto = unicodedata.normalize("NFD", bruto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def primeiro_nome(nome) -> str:
    partes = sem_acento(nome).strip().lower().split()
    return partes[0] if partes else ""


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
    """Grava mantendo dono e permissao do arquivo original.

    O backend roda como UID 10001 e /data e bind mount. Um arquivo recriado
    por root deixaria de ser gravavel pelo processo, e o sintoma apareceria
    so na proxima sessao arquivada.
    """
    anterior = os.stat(caminho)
    temporario = caminho + ".unificar.tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)
    os.chmod(caminho, anterior.st_mode & 0o7777)
    if hasattr(os, "chown") and os.geteuid() == 0:
        os.chown(caminho, anterior.st_uid, anterior.st_gid)


def dono_do_relatorio(relatorio: dict) -> str:
    profissional = relatorio.get("professional")
    profissional = profissional if isinstance(profissional, dict) else {}
    return normalizar_email(
        relatorio.get("professionalEmail")
        or relatorio.get("professional_email")
        or profissional.get("email")
        or ""
    )


def contas_alvo(perfis: dict, alvo_nome: str, destino: str) -> dict:
    """Contas cujo primeiro nome bate. O destino entra sempre."""
    encontradas = {}
    for email, perfil in (perfis or {}).items():
        email = normalizar_email(email)
        if not email:
            continue
        perfil = perfil if isinstance(perfil, dict) else {}
        nome = perfil.get("owner_name") or perfil.get("name") or ""
        if primeiro_nome(nome) == alvo_nome or email == destino:
            encontradas[email] = str(nome or "(sem nome)")
    return encontradas


def main() -> int:
    interpretador = argparse.ArgumentParser(
        description="Transfere pacientes de contas de mesmo primeiro nome para uma so."
    )
    interpretador.add_argument("--dados", default="/root/froid-project/data")
    interpretador.add_argument("--destino", default="fbenhayon@gmail.com")
    interpretador.add_argument("--primeiro-nome", default="fabio")
    interpretador.add_argument(
        "--aplicar", action="store_true", help="escreve; sem isto so mostra"
    )
    opcoes = interpretador.parse_args()

    destino = normalizar_email(opcoes.destino)
    alvo_nome = primeiro_nome(opcoes.primeiro_nome)
    caminho_relatorios = os.path.join(opcoes.dados, "session_reports.json")
    caminho_identidade = os.path.join(opcoes.dados, "identity_state.json")

    relatorios = carregar(caminho_relatorios)
    identidade = carregar(caminho_identidade)
    perfis = identidade.get("professional_profiles") or {}
    convites = identidade.get("session_invites") or {}
    donos_de_sessao = identidade.get("session_owners") or {}

    alvos = contas_alvo(perfis, alvo_nome, destino)
    if destino not in alvos:
        alvos[destino] = "(conta de destino, sem perfil cadastrado)"
    nome_destino = (
        (perfis.get(destino) or {}).get("owner_name")
        or (perfis.get(destino) or {}).get("name")
        or destino
    )

    print("MODO:", "APLICAR (escreve)" if opcoes.aplicar else "CONFERENCIA (nao escreve)")
    print("destino:", destino, "|", nome_destino)
    print("primeiro nome procurado:", alvo_nome or "(vazio)")
    print()
    print("CONTAS QUE ENTRAM NA UNIFICACAO")
    for email in sorted(alvos):
        print("  -", email, "|", alvos[email])
    intocadas = sorted(set(map(normalizar_email, perfis)) - set(alvos))
    print()
    print("CONTAS INTOCADAS")
    for email in intocadas:
        perfil = perfis.get(email) or {}
        print("  -", email, "|", perfil.get("owner_name") or perfil.get("name") or "(sem nome)")
    if not intocadas:
        print("  (nenhuma)")

    movidos_relatorio = {}
    sem_dono = 0
    for _sessao, relatorio in relatorios.items():
        if not isinstance(relatorio, dict):
            continue
        dono = dono_do_relatorio(relatorio)
        if not dono:
            sem_dono += 1
        elif dono in alvos and dono != destino:
            movidos_relatorio[dono] = movidos_relatorio.get(dono, 0) + 1

    movidos_convite = {}
    convites_sem_dono = 0
    for _token, convite in convites.items():
        if not isinstance(convite, dict):
            continue
        dono = normalizar_email(convite.get("professional_email"))
        if not dono:
            convites_sem_dono += 1
        elif dono in alvos and dono != destino:
            movidos_convite[dono] = movidos_convite.get(dono, 0) + 1

    movidas_sessoes = sum(
        1
        for _sessao, dono in donos_de_sessao.items()
        if normalizar_email(dono) in alvos and normalizar_email(dono) != destino
    )

    print()
    print("O QUE MUDA")
    print("  relatorios movidos de outra conta 'fabio':", sum(movidos_relatorio.values()))
    for email in sorted(movidos_relatorio):
        print("     ", email, "->", movidos_relatorio[email])
    print("  relatorios SEM dono que passam a ser do destino:", sem_dono)
    print("  convites movidos de outra conta 'fabio':", sum(movidos_convite.values()))
    for email in sorted(movidos_convite):
        print("     ", email, "->", movidos_convite[email])
    print("  convites SEM dono (NAO sao tocados):", convites_sem_dono)
    print("  session_owners reapontados:", movidas_sessoes)

    total = (
        sum(movidos_relatorio.values())
        + sem_dono
        + sum(movidos_convite.values())
        + movidas_sessoes
    )
    if not opcoes.aplicar:
        print()
        print("Nada foi escrito. Para aplicar, repita com --aplicar.")
        return 0
    if not total:
        print()
        print("Nada a fazer.")
        return 0

    marca = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for caminho in (caminho_relatorios, caminho_identidade):
        copia = caminho + ".antes-de-unificar-" + marca
        shutil.copy2(caminho, copia)
        print("copia de seguranca:", copia)

    for _sessao, relatorio in relatorios.items():
        if not isinstance(relatorio, dict):
            continue
        dono = dono_do_relatorio(relatorio)
        if dono and (dono not in alvos or dono == destino):
            continue
        relatorio["professionalEmail"] = destino
        relatorio.pop("professional_email", None)
        profissional = relatorio.get("professional")
        profissional = dict(profissional) if isinstance(profissional, dict) else {}
        profissional["email"] = destino
        profissional["name"] = nome_destino
        relatorio["professional"] = profissional

    for _token, convite in convites.items():
        if not isinstance(convite, dict):
            continue
        dono = normalizar_email(convite.get("professional_email"))
        if not dono or dono not in alvos or dono == destino:
            continue
        convite["professional_email"] = destino

    for sessao, dono in list(donos_de_sessao.items()):
        if normalizar_email(dono) in alvos:
            donos_de_sessao[sessao] = destino

    identidade["session_invites"] = convites
    identidade["session_owners"] = donos_de_sessao

    gravar_preservando(caminho_relatorios, relatorios)
    gravar_preservando(caminho_identidade, identidade)
    print()
    print("Feito. Suba o backend: docker compose start froid-backend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
