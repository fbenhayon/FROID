# -*- coding: utf-8 -*-
"""As ferramentas do FROID Explica: o que o modelo pode pedir ao servidor.

Fase 4 (18/10/2026). Ate aqui o navegador montava o contexto de UMA sessao e
o mandava inteiro; perguntas sobre varias sessoes, varios pacientes ou a
clinica dependiam de uma palavra-gatilho e de um resumo fixo. Agora o modelo
pede o que a pergunta precisa, e cada ferramenta le de um unico lugar: o
acervo que o solicitante JA pode ver, decidido por `_accessible_session_reports`
em `main.py` — posse, atribuicao e visibilidade de clinica. O Explica nao ve
mais que a tela.

Este modulo nao sabe de HTTP nem de autorizacao: recebe o `Acervo` pronto e
responde. E assim que se testa sem servidor, e e assim que nenhuma ferramenta
consegue abrir caminho novo de acesso.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import data_froid_referencia
import explica_clinico

LOGGER = logging.getLogger("froid.persistence")

# ---------------------------------------------------------------------------
# O snapshot arquivado, nos rotulos do glossario
# ---------------------------------------------------------------------------

# ESPELHO de `metricasParaOExplica` em froid-dashboard/src/lib/painel-para-o-explica.ts:
# (rotulo na tela, campo do snapshot arquivado, casas decimais). O painel
# produz esta tabela para a sessao aberta na tela; o servidor a produz para
# qualquer sessao acessivel. `test_explica_ferramentas` le o arquivo
# TypeScript e confronta as duas listas — rotulo novo num lado sem o outro
# quebra o teste (padrao 2.9: espelho de nome tem UMA fonte e um teste).
ROTULOS_DO_SNAPSHOT: Tuple[Tuple[str, str, int], ...] = (
    ("IPM", "ipmAvg", 1),
    ("IDM", "idmAvg", 2),
    ("ZONAS", "dominantZone", -1),
    ("TOM", "emotionalTone", -1),
    ("P/MIN", "wordsPerMinute", 1),
    ("DISSO.", "dissonanceCount", 0),
    ("MFCC7", "mfcc7", 3),
    ("MFCC9", "mfcc9", 3),
    ("DMFCC7", "mfcc7Delta", 4),
    ("DMFCC9", "mfcc9Delta", 4),
    ("DDMFCC7", "mfcc7DeltaDelta", 4),
    ("DDMFCC9", "mfcc9DeltaDelta", 4),
    ("F0 MED.", "f0Mean", 2),
    ("ZCR", "zcr", 3),
    ("JITTER", "jitter", 3),
    ("SHIMMER", "shimmer", 3),
    ("DELTA", "spectralDelta0_4", 3),
    ("THETA", "spectralTheta4_8", 3),
    ("ALPHA", "spectralAlpha8_12", 3),
    ("BETA", "spectralBeta12_30", 3),
    ("GAMA", "spectralGamma30_80", 3),
    ("IND. ESPECTRAL", "spectralBandIndex", 3),
    ("SUB-H 5-12", "subharmonic5_12", 3),
    ("SUB-H 12-20", "subharmonic12_20", 3),
    ("SUB-H 20-40", "subharmonic20_40", 3),
    ("VOCAL 85-165", "vocalBasal85_165", 3),
    ("DNA INFRA", "dnaInfrasoundNuclear", 3),
    ("DNA LIMBICO", "dnaLimbicModulation", 3),
    ("DNA VOCAL", "dnaVocalBasalTension", 3),
    ("DNA FLOOD", "dnaAutonomicFlooding", 3),
    ("DNA SHUTDOWN", "dnaDissociativeShutdown", 3),
    ("DNA NEURO", "dnaNeurogenicResonance", 3),
    ("DNA SOMATO", "dnaSomatoaffectiveDissonance", 3),
)


def _numero(valor: Any) -> Optional[float]:
    """Numero quando houve medida; None quando nao houve. Nunca zero por ausencia."""
    if valor is None or valor == "":
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _fmt(valor: Any, casas: int) -> str:
    """Mesma regra do painel: ausencia vira "--", nunca zero."""
    if casas < 0:
        return str(valor).strip() if valor not in (None, "") else "--"
    numero = _numero(valor)
    return "--" if numero is None else f"{numero:.{casas}f}"


def metricas_do_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, str]:
    saida: Dict[str, str] = {}
    for rotulo, campo, casas in ROTULOS_DO_SNAPSHOT:
        valor = snapshot.get(campo)
        if rotulo == "ZONAS":
            saida[rotulo] = f"Zona {valor}" if valor not in (None, "") else "--"
        else:
            saida[rotulo] = _fmt(valor, casas)
    return saida


def _segundos_do_resumo(resumo: Mapping[str, Any]) -> Optional[Tuple[int, int]]:
    """A janela do resumo em segundos, ou None quando ele nao tem instante.

    Ate 20/10/2026 um resumo sem instante virava a janela 0-1 s (`or 0`), e
    podia casar com o primeiro corte por engano. Ausencia nao vira zero.
    """
    inicio = resumo.get("startSecond")
    if inicio is None and resumo.get("startMinute") is not None:
        inicio = float(resumo["startMinute"]) * 60
    fim = resumo.get("endSecond")
    if fim is None and resumo.get("endMinute") is not None:
        fim = float(resumo["endMinute"]) * 60
    if _numero(inicio) is None or _numero(fim) is None:
        return None
    inicio_s = max(0, int(math.floor(float(inicio))))
    fim_s = max(inicio_s + 1, int(math.ceil(float(fim))))
    return inicio_s, fim_s


def _resumo_do_corte(corte: Mapping[str, Any], resumos: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """O resumo que mais se sobrepoe ao corte — a mesma regra de resumo-do-corte.ts.
    Corte ou resumo sem instante nao casa com nada."""
    inicio = _numero(corte.get("startSecond"))
    fim = _numero(corte.get("endSecond"))
    if inicio is None or fim is None:
        return None
    melhor, maior = None, 0
    for resumo in resumos:
        if not isinstance(resumo, Mapping):
            continue
        janela = _segundos_do_resumo(resumo)
        if janela is None:
            continue
        r_inicio, r_fim = janela
        sobreposicao = max(0.0, min(fim, r_fim) - max(inicio, r_inicio))
        if sobreposicao > maior:
            melhor, maior = resumo, sobreposicao
    return melhor


def corte_compacto(corte: Mapping[str, Any], resumo: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    inicio = _numero(corte.get("startSecond"))
    fim = _numero(corte.get("endSecond"))
    # Instante ausente fica ausente (None); a linha do corte declara. Ate
    # 20/10/2026 virava "0-0 s (duracao 0 s)", um numero com cara de medida.
    inicio_s = int(inicio) if inicio is not None else None
    fim_s = int(fim) if fim is not None else None
    amostras = _numero(corte.get("sampleCount"))
    tema = str((resumo or {}).get("theme") or "").strip()
    texto = str((resumo or {}).get("summary") or "").strip()
    rotulo = str(corte.get("label") or "").strip()
    if not rotulo:
        rotulo = f"{inicio_s // 60}-{-(-fim_s // 60)}min" if inicio_s is not None and fim_s is not None else "corte sem instante"
    return {
        "corte": rotulo,
        "inicio_s": inicio_s,
        "fim_s": fim_s,
        "duracao_s": max(0, fim_s - inicio_s) if inicio_s is not None and fim_s is not None else None,
        "amostras": int(amostras) if amostras is not None else None,
        "tema": tema or None,
        "resumo": texto or None,
        "metricas": metricas_do_snapshot(corte),
    }


def contexto_dos_cortes(relatorio: Mapping[str, Any], janela: str) -> Dict[str, Any]:
    """`panel_baseline` + `panel_cuts` de um relatorio arquivado — a mesma forma
    que o painel manda, para o mesmo `explica_clinico.bloco_dos_cortes`."""
    saida: Dict[str, Any] = {}
    base = relatorio.get("baseline")
    if isinstance(base, Mapping):
        amostras = _numero(base.get("sampleCount"))
        saida["panel_baseline"] = {
            "janela": f"{base.get('startSecond')}-{base.get('endSecond')} s",
            "amostras": int(amostras) if amostras is not None else None,
            "metricas": metricas_do_snapshot(base),
        }
    cortes = relatorio.get("tenMinuteCuts")
    resumos = relatorio.get("conversationSummaries")
    resumos = [r for r in resumos if isinstance(r, Mapping)] if isinstance(resumos, list) else []
    if isinstance(cortes, list) and cortes:
        saida["panel_cuts"] = [
            corte_compacto(corte, _resumo_do_corte(corte, resumos))
            for corte in cortes
            if isinstance(corte, Mapping)
        ]
        saida["panel_cuts_window"] = janela
    return saida


# ---------------------------------------------------------------------------
# A carteira: uma linha por sessao
# ---------------------------------------------------------------------------


def resumo_da_sessao(relatorio: Mapping[str, Any]) -> Dict[str, Any]:
    """Resumo minimo de uma sessao para comparacao, nos nomes DO ARQUIVO.

    Ate 15/10/2026 esta funcao (entao em main.py) lia `ipm`, `coherence` e
    `dominant_zone` de um snapshot que grava `ipmAvg`, `coherenceStatus` e
    `dominantZone`: 20 de 20 resumos saiam nulos em producao. Espelho de nome
    (padrao 2.9) entre o painel que grava e o servidor que le.
    """
    if not isinstance(relatorio, Mapping):
        relatorio = {}
    average = relatorio.get("sessionAverage")
    baseline = relatorio.get("baseline")
    average = average if isinstance(average, Mapping) else {}
    baseline = baseline if isinstance(baseline, Mapping) else {}
    resumo = relatorio.get("sessionSummary")
    if isinstance(resumo, Mapping):
        tema = str(resumo.get("theme") or "").strip()
        texto = str(resumo.get("summary") or "").strip()
    else:
        tema, texto = "", str(resumo or "").strip()
    cortes = relatorio.get("tenMinuteCuts")
    zona = average.get("dominantZone")
    return {
        "session_id": str(relatorio.get("sessionId") or relatorio.get("session_id") or ""),
        "date": str(relatorio.get("createdAt") or relatorio.get("created_at") or "")[:10],
        "patient_id": str(relatorio.get("patientId") or ""),
        "duration_seconds": _numero(relatorio.get("durationSeconds")),
        "cuts_count": len(cortes) if isinstance(cortes, list) else None,
        "ipm_average": _numero(average.get("ipmAvg")),
        "ipm_baseline": _numero(baseline.get("ipmAvg")),
        "idm_average": _numero(average.get("idmAvg")),
        "words_per_minute_average": _numero(average.get("wordsPerMinute")),
        "words_per_minute_baseline": _numero(baseline.get("wordsPerMinute")),
        "f0_mean_average": _numero(average.get("f0Mean")),
        "f0_mean_baseline": _numero(baseline.get("f0Mean")),
        "dominant_zone": zona if zona not in (None, "") else None,
        "coherence": str(average.get("coherenceStatus") or "").strip() or None,
        "theme": tema[:120],
        "session_summary": texto[:300],
    }


def linha_da_carteira(item: Mapping[str, Any]) -> str:
    duracao = item.get("duration_seconds")
    minutos = f"{duracao / 60:.0f} min" if duracao is not None else "duracao --"
    cortes = item.get("cuts_count")
    zona = item.get("dominant_zone")
    marca = " (ESTE PACIENTE)" if item.get("current_patient") else ""
    linha = (
        f"- {item.get('date') or 'data --'} | sessao {item.get('session_id') or '--'} | "
        f"paciente {item.get('patient_id') or '--'}{marca} | {minutos} | "
        f"{cortes if cortes is not None else '--'} cortes | "
        f"IPM {_fmt(item.get('ipm_average'), 1)} (base {_fmt(item.get('ipm_baseline'), 1)}) | "
        f"IDM {_fmt(item.get('idm_average'), 2)} | "
        f"P/MIN {_fmt(item.get('words_per_minute_average'), 1)} "
        f"(base {_fmt(item.get('words_per_minute_baseline'), 1)}) | "
        f"F0 MED. {_fmt(item.get('f0_mean_average'), 1)} "
        f"(base {_fmt(item.get('f0_mean_baseline'), 1)}) | "
        f"zona {zona if zona is not None else '--'} | "
        f"coerencia {item.get('coherence') or '--'} | tema: {item.get('theme') or '--'}"
    )
    resumo = str(item.get("session_summary") or "").strip()
    if resumo:
        linha += f"\n  resumo: {resumo}"
    return linha


# ---------------------------------------------------------------------------
# O acervo e as ferramentas
# ---------------------------------------------------------------------------

# Teto do trecho de transcricao devolvido por chamada. O modelo pode pedir de
# novo com outra janela; o que nao coube e DECLARADO.
LIMITE_DO_TRECHO = 6_000
# Teto de linhas de carteira por chamada, declarado quando atua.
LIMITE_DE_SESSOES_POR_CHAMADA = 40


@dataclass
class Acervo:
    """O que o solicitante pode ver, ja decidido pelo RLS em main.py.

    `relatorios`: os relatorios acessiveis, sem transcricao decifrada.
    `transcricao_de`: carrega UM relatorio com a transcricao decifrada, so
    quando uma ferramenta pede — decifrar o acervo inteiro a cada pergunta
    seria caro e desnecessario. Devolve None quando a sessao nao esta entre
    as acessiveis.
    """

    relatorios: List[Dict[str, Any]]
    sessao_atual: str = ""
    paciente_atual: str = ""
    transcricao_de: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None
    # Fase 5: a referencia populacional do Data-FROID anonimo. Quem a injeta
    # (main) e quem conhece o acervo, o piso de coorte e as versoes sem zero
    # falso; esta camada so repassa a entrada e devolve o texto ou o erro.
    # None = Data-FROID indisponivel neste servidor, e a ferramenta diz isso.
    referencia_populacional: Optional[Callable[[Mapping[str, Any]], str]] = None
    chamadas: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)

    def relatorio(self, session_id: str) -> Optional[Dict[str, Any]]:
        alvo = str(session_id or "").strip()
        for relatorio in self.relatorios:
            if str(relatorio.get("sessionId") or relatorio.get("session_id") or "") == alvo:
                return relatorio
        return None


class ErroDeFerramenta(Exception):
    """Volta ao modelo como tool_result com is_error, nunca como dado."""


def _mmss(segundos: float) -> str:
    total = max(0, int(math.floor(segundos)))
    return f"{total // 60:02d}:{total % 60:02d}"


def _ordenados_por_data(relatorios: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return sorted(relatorios, key=lambda r: str(r.get("createdAt") or r.get("created_at") or ""))


def _media_com_n(valores: Sequence[Optional[float]]) -> Tuple[Optional[float], int]:
    medidos = [v for v in valores if v is not None]
    if not medidos:
        return None, 0
    return sum(medidos) / len(medidos), len(medidos)


def _cortes_da_sessao(acervo: Acervo, entrada: Mapping[str, Any]) -> str:
    session_id = str(entrada.get("session_id") or "").strip()
    relatorio = acervo.relatorio(session_id)
    if relatorio is None:
        raise ErroDeFerramenta(
            f"a sessao '{session_id}' nao esta entre as sessoes que voce pode ver; "
            "use sessoes_do_paciente ou pacientes_do_profissional para listar as acessiveis"
        )
    contexto = contexto_dos_cortes(relatorio, f"cortes da sessao {session_id}")
    if "panel_cuts" not in contexto:
        return (
            f"A sessao {session_id} esta acessivel mas nao tem cortes arquivados "
            "(sem capacidade de apuracao por corte)."
        )
    return explica_clinico.bloco_dos_cortes(contexto)


def _sessoes_do_paciente(acervo: Acervo, entrada: Mapping[str, Any]) -> str:
    patient_id = str(entrada.get("patient_id") or "").strip() or acervo.paciente_atual
    if not patient_id:
        raise ErroDeFerramenta("informe patient_id; nao ha paciente em contexto nesta pergunta")
    do_paciente = _ordenados_por_data(
        [r for r in acervo.relatorios if str(r.get("patientId") or "") == patient_id]
    )
    if not do_paciente:
        return f"Nenhuma sessao acessivel para o paciente {patient_id}."
    linhas = [f"SESSOES DO PACIENTE {patient_id} ({len(do_paciente)} acessiveis, em ordem cronologica; '--' e sem apuracao, nunca zero):"]
    for relatorio in do_paciente[:LIMITE_DE_SESSOES_POR_CHAMADA]:
        item = resumo_da_sessao(relatorio)
        item["current_patient"] = patient_id == acervo.paciente_atual
        linhas.append(linha_da_carteira(item))
    if len(do_paciente) > LIMITE_DE_SESSOES_POR_CHAMADA:
        linhas.append(f"[{len(do_paciente) - LIMITE_DE_SESSOES_POR_CHAMADA} sessao(oes) omitida(s) por limite; as mais antigas]")
    return "\n".join(linhas)


def _pacientes_do_profissional(acervo: Acervo, entrada: Mapping[str, Any]) -> str:
    por_paciente: Dict[str, List[Mapping[str, Any]]] = {}
    sem_id = 0
    for relatorio in acervo.relatorios:
        chave = str(relatorio.get("patientId") or "")
        if not chave:
            # Sessao sem paciente registrado nao e um paciente: ate 20/10/2026
            # entrava na contagem como "(sem id de paciente)" (item 26).
            sem_id += 1
            continue
        por_paciente.setdefault(chave, []).append(relatorio)
    if not por_paciente and not sem_id:
        return "Nenhuma sessao acessivel: a carteira que voce pode ver esta vazia."
    linhas = [
        f"PACIENTES COM SESSAO ACESSIVEL: {len(por_paciente)} (identificados por id; "
        "medias sao medias das medias de sessao, sobre n sessoes com apuracao):"
    ]
    if sem_id:
        linhas.append(f"- {sem_id} sessao(oes) sem id de paciente, fora da contagem de pacientes")
    for paciente, relatorios in sorted(por_paciente.items(), key=lambda par: -len(par[1])):
        ordenados = _ordenados_por_data(relatorios)
        resumos = [resumo_da_sessao(r) for r in ordenados]
        ipm, n_ipm = _media_com_n([r["ipm_average"] for r in resumos])
        pmin, n_pmin = _media_com_n([r["words_per_minute_average"] for r in resumos])
        marca = " (ESTE PACIENTE)" if paciente == acervo.paciente_atual else ""
        linhas.append(
            f"- paciente {paciente}{marca} | {len(ordenados)} sessoes | "
            f"de {resumos[0]['date'] or '--'} a {resumos[-1]['date'] or '--'} | "
            f"IPM medio {_fmt(ipm, 1)} (n={n_ipm}) | P/MIN medio {_fmt(pmin, 1)} (n={n_pmin}) | "
            f"ultima zona {resumos[-1]['dominant_zone'] if resumos[-1]['dominant_zone'] is not None else '--'}"
        )
    return "\n".join(linhas)


def _agregado_da_clinica(acervo: Acervo, entrada: Mapping[str, Any]) -> str:
    por = str(entrada.get("por") or "clinica").strip().lower()
    if por not in ("profissional", "clinica"):
        raise ErroDeFerramenta("por deve ser 'profissional' ou 'clinica'")
    if not acervo.relatorios:
        return "Nenhuma sessao acessivel para agregar."
    grupos: Dict[str, List[Mapping[str, Any]]] = {}
    for relatorio in acervo.relatorios:
        if por == "profissional":
            profissional = relatorio.get("professional") if isinstance(relatorio.get("professional"), Mapping) else {}
            chave = str(relatorio.get("professionalEmail") or profissional.get("email") or "").strip() or "(profissional nao registrado)"
        else:
            chave = "clinica"
        grupos.setdefault(chave, []).append(relatorio)
    linhas = [
        f"AGREGADO POR {por.upper()} sobre as {len(acervo.relatorios)} sessoes que voce pode ver "
        "(se a politica da clinica for restrita, isto cobre so as suas sessoes e as atribuidas a voce; "
        "medias sao medias das medias de sessao, com n):"
    ]
    for chave, relatorios in sorted(grupos.items(), key=lambda par: -len(par[1])):
        resumos = [resumo_da_sessao(r) for r in relatorios]
        pacientes = {r["patient_id"] for r in resumos if r["patient_id"]}
        ipm, n_ipm = _media_com_n([r["ipm_average"] for r in resumos])
        pmin, n_pmin = _media_com_n([r["words_per_minute_average"] for r in resumos])
        datas = sorted(r["date"] for r in resumos if r["date"])
        linhas.append(
            f"- {chave} | {len(pacientes)} pacientes | {len(relatorios)} sessoes | "
            f"de {datas[0] if datas else '--'} a {datas[-1] if datas else '--'} | "
            f"IPM medio {_fmt(ipm, 1)} (n={n_ipm}) | P/MIN medio {_fmt(pmin, 1)} (n={n_pmin})"
        )
    return "\n".join(linhas)


def _trecho_da_transcricao(acervo: Acervo, entrada: Mapping[str, Any]) -> str:
    session_id = str(entrada.get("session_id") or "").strip() or acervo.sessao_atual
    inicio = _numero(entrada.get("inicio_s"))
    fim = _numero(entrada.get("fim_s"))
    if not session_id:
        raise ErroDeFerramenta("informe session_id; nao ha sessao em contexto nesta pergunta")
    if inicio is None or fim is None or fim <= inicio:
        raise ErroDeFerramenta("informe inicio_s e fim_s em segundos, com fim_s maior que inicio_s")
    if acervo.relatorio(session_id) is None:
        raise ErroDeFerramenta(f"a sessao '{session_id}' nao esta entre as sessoes que voce pode ver")
    if acervo.transcricao_de is None:
        raise ErroDeFerramenta("a transcricao nao esta disponivel nesta pergunta")
    relatorio = acervo.transcricao_de(session_id)
    if relatorio is None:
        raise ErroDeFerramenta(f"a transcricao da sessao '{session_id}' nao pode ser lida")
    texto = str(relatorio.get("transcript") or "")
    linhas = texto.split("\n")
    if linhas and linhas[-1] == "":
        linhas = linhas[:-1]
    segundos = relatorio.get("transcriptLineSeconds")
    if not isinstance(segundos, list) or len(segundos) != len(linhas):
        return (
            f"A sessao {session_id} nao tem o instante de cada linha registrado (relatorio "
            "anterior a esse registro): nao e possivel recortar por tempo. Ha "
            f"{len(linhas)} linhas transcritas; peca pelo conteudo, nao por minuto."
        )
    selecionadas = [
        f"[{_mmss(float(s))}] {linha}"
        for s, linha in zip(segundos, linhas)
        if _numero(s) is not None and inicio <= float(s) < fim
    ]
    if not selecionadas:
        return f"Nenhuma linha transcrita entre {_mmss(inicio)} e {_mmss(fim)} na sessao {session_id}."
    cabecalho = f"TRANSCRICAO DA SESSAO {session_id} DE {_mmss(inicio)} A {_mmss(fim)} ({len(selecionadas)} linhas):"
    # Em linhas inteiras, do inicio da janela: cada linha entregue conserva o
    # seu [mm:ss]. Ate 20/10/2026 o corte era por caractere e a ultima linha
    # saia pela metade, com cara de fala interrompida.
    mantidas, tamanho = [], 0
    for linha in selecionadas:
        custo = len(linha) + (1 if mantidas else 0)
        if mantidas and tamanho + custo > LIMITE_DO_TRECHO:
            break
        mantidas.append(linha)
        tamanho += custo
    corpo = "\n".join(mantidas)
    omitidas = len(selecionadas) - len(mantidas)
    if omitidas:
        ultima = mantidas[-1][1:6]
        corpo += f"\n[trecho truncado: {omitidas} linhas omitidas depois de {ultima}; peca uma janela menor]"
    return cabecalho + "\n" + corpo


def _referencia_populacional(acervo: Acervo, entrada: Mapping[str, Any]) -> str:
    if acervo.referencia_populacional is None:
        raise ErroDeFerramenta("a referencia populacional do Data-FROID nao esta disponivel neste servidor")
    return acervo.referencia_populacional(entrada)


FERRAMENTAS: Tuple[Dict[str, Any], ...] = (
    {
        "name": "cortes_da_sessao",
        "description": (
            "Os cortes de uma sessao arquivada, um por linha, nos rotulos do painel, com o "
            "desvio de cada metrica contra a linha de base calculado pelo servidor, mais tema "
            "e resumo de cada corte. Use quando a pergunta comparar cortes ou pedir valores por "
            "corte de uma sessao que nao e a aberta na tela (a da tela ja vem no prompt)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "string", "description": "identificador da sessao, como froid-xxxx"}},
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "sessoes_do_paciente",
        "description": (
            "Todas as sessoes acessiveis de um paciente, uma linha por sessao, em ordem "
            "cronologica, com IPM, IDM, P/MIN e F0 medios e a linha de base de cada uma. Use "
            "para evolucao entre sessoes do mesmo paciente. Sem patient_id, usa o paciente da "
            "sessao em contexto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"patient_id": {"type": "string", "description": "identificador do paciente; vazio = paciente em contexto"}},
            "required": ["patient_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pacientes_do_profissional",
        "description": (
            "Os pacientes com sessao acessivel a quem pergunta: por paciente, numero de "
            "sessoes, primeira e ultima data, IPM e P/MIN medios. Use para 'meus pacientes', "
            "'quantos pacientes', comparacao entre pacientes."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "agregado_da_clinica",
        "description": (
            "Contagens e medias sobre as sessoes que quem pergunta pode ver, por profissional "
            "ou para a clinica inteira: pacientes, sessoes, periodo, IPM e P/MIN medios com n. "
            "Cobre so o que a politica de visibilidade da clinica permite a essa pessoa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"por": {"type": "string", "enum": ["profissional", "clinica"]}},
            "required": ["por"],
            "additionalProperties": False,
        },
    },
    {
        "name": "trecho_da_transcricao",
        "description": (
            "As linhas transcritas de uma sessao acessivel entre dois instantes, em segundos, "
            "cada uma com [mm:ss]. Use para reler o trecho de um corte ou confirmar o que foi "
            "dito num momento. Sem session_id, usa a sessao em contexto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "vazio = sessao em contexto"},
                "inicio_s": {"type": "number"},
                "fim_s": {"type": "number"},
            },
            "required": ["session_id", "inicio_s", "fim_s"],
            "additionalProperties": False,
        },
    },
    {
        "name": "referencia_populacional",
        "description": (
            "A distribuicao de UMA medida no acervo anonimo do Data-FROID (sessoes do FROID, "
            "nao uma norma clinica): sessoes distintas, registros apurados, media, mediana e "
            "quartis, com piso de coorte; abaixo do piso nada e devolvido. Com valor_do_paciente, "
            "o servidor calcula em que ponto da distribuicao esse valor cai. Use quando a "
            "pergunta situar o paciente ou a sessao frente ao conjunto de sessoes do FROID "
            "('e alto?', 'e comum?', 'como se compara'). Filtros opcionais de coorte: "
            "age_bucket, gender, session_modality; vazio = sem filtro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "medida": {"type": "string", "enum": list(data_froid_referencia.NOMES_DAS_MEDIDAS)},
                "valor_do_paciente": {"type": "string", "description": "valor numerico como texto; vazio = sem valor"},
                "age_bucket": {"type": "string", "description": "faixa etaria do acervo, ex. 30-39; vazio = sem filtro"},
                "gender": {"type": "string", "description": "vazio = sem filtro"},
                "session_modality": {"type": "string", "description": "vazio = sem filtro"},
            },
            "required": ["medida", "valor_do_paciente", "age_bucket", "gender", "session_modality"],
            "additionalProperties": False,
        },
    },
)

_EXECUTORES: Dict[str, Callable[[Acervo, Mapping[str, Any]], str]] = {
    "cortes_da_sessao": _cortes_da_sessao,
    "sessoes_do_paciente": _sessoes_do_paciente,
    "pacientes_do_profissional": _pacientes_do_profissional,
    "agregado_da_clinica": _agregado_da_clinica,
    "trecho_da_transcricao": _trecho_da_transcricao,
    "referencia_populacional": _referencia_populacional,
}


def definicoes() -> List[Dict[str, Any]]:
    """As ferramentas como a API as recebe: esquema estrito, sem campo extra."""
    return [{**ferramenta, "strict": True} for ferramenta in FERRAMENTAS]


def executar(acervo: Acervo, nome: str, entrada: Any) -> Tuple[str, bool]:
    """(conteudo, e_erro). Erro vai ao modelo como tal, nunca como dado."""
    entrada = entrada if isinstance(entrada, Mapping) else {}
    acervo.chamadas.append((nome, {chave: entrada[chave] for chave in entrada}))
    LOGGER.info("FROID Explica: ferramenta %s(%s)", nome, ", ".join(sorted(str(k) for k in entrada)))
    executor = _EXECUTORES.get(nome)
    if executor is None:
        return f"Error: ferramenta '{nome}' nao existe", True
    try:
        return executor(acervo, entrada), False
    except ErroDeFerramenta as erro:
        return f"Error: {erro}", True
    except Exception as erro:  # a falha interna tambem e declarada, nao engolida
        LOGGER.exception("FROID Explica: ferramenta %s falhou", nome)
        return f"Error: falha interna em {nome} ({type(erro).__name__})", True
