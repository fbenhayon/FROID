"""Gera o kit de demonstração NR-1 (PDF) a partir do dossiê selado do piloto.

O kit é o que o visitante do site recebe depois de deixar o contato: os
documentos que o FROID produz para o GRO/PGR — critérios do GRO, AEP,
classificação dos fatores, inventário de riscos e plano de ação — preenchidos
com a empresa piloto "FROID NR-1 Piloto 01 — DADOS SIMULADOS".

Regras que este gerador NÃO negocia (skill-froid-master 1.1):

  * Nenhum número, nome ou texto é escrito aqui. Tudo sai do JSON do dossiê
    selado, que é o mesmo conteúdo que o produto exporta. Campo vazio no
    dossiê aparece como "—", nunca é completado.
  * Os rótulos em português são os mesmos das telas do painel
    (Nr1ActionPlan.tsx, Nr1Aep.tsx, Nr1Effectiveness.tsx). Rótulo que não
    existir no mapa sai com o código cru, para que a falta apareça.
  * A cor de cada célula da matriz 5x5 é calculada por
    `nr1_compliance.risk_level` com os critérios do próprio dossiê — a mesma
    função que classifica no servidor (regra 2.7: número com uma fonte).
  * Toda página leva o aviso "DADOS SIMULADOS — sem validade documental".

Como produzir o dossiê de entrada (banco DESCARTÁVEL, nunca o de produção):

    1. PostgreSQL 16 local, papel froid_runtime, migrações aplicadas;
    2. python froid-server/tools/nr1_pilot_dryrun.py --create
    3. exportar a última linha de psychosocial_compliance_dossiers como
       {"version", "sha", "sealed_at", "payload"}.

Uso:

    python tools/gerar-kit-demonstracao-nr1.py DOSSIE.json SAIDA.pdf \
        [--responsavel "Nome exibido do responsável pelo plano"]

O kit publicado fica em froid-server/assets/froid-kit-demonstracao-nr1.pdf
(dentro do backend, fora do site público: só sai pelo link individual que vai
por e-mail). Para atualizá-lo, gere direto nesse caminho e reconstrua o backend.
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "froid-server"))

import nr1_compliance  # noqa: E402

FONTES = REPO / "froid-site-dev" / "site-assets" / "fonts" / "fontes.css"
LOGO = REPO / "froid-site-dev" / "site-assets" / "img" / "froid-logo.png"
# Onde o leitor do kit pede a proposta: a janela do formulário na Apresentação
# NR-1. O caminho é o mesmo de main.KIT_NR1_PAGINA_DO_FORMULARIO, e
# test_kit_demonstracao_nr1 confere os dois.
URL_DO_PEDIDO = "https://www.froid.com.br/nr1/apresentacao-nr1.html#pedir-kit"

NAVEGADORES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/google-chrome"),
)

# --- Rótulos: cópia literal dos mapas das telas do painel ------------------
RISCO = {"critical": "Crítico", "high": "Alto", "moderate": "Moderado", "low": "Baixo"}
FATOR = {
    "work_organization": "Gestão e organização do trabalho",
    "workload_demand": "Carga e demanda",
    "harassment_violence": "Assédio e violência",
    "environment_modality": "Ambiente e modalidade",
}
STATUS = {"planned": "Planejada", "in_progress": "Em andamento", "done": "Concluída", "cancelled": "Cancelada"}
EFICACIA = {
    "none": "Sem efeito medido", "insufficient": "Insuficiente", "partial": "Parcial",
    "effective": "Eficaz", "eliminated": "Perigo eliminado",
}
TIPO_MEDIDA = {
    "elimination": "Eliminação", "substitution": "Substituição", "collective": "Coletiva",
    "administrative": "Administrativa", "monitoring": "Acompanhamento",
}
ACAO = {"introduce": "Introduzir", "improve": "Aprimorar", "maintain": "Manter"}
VEREDITO = {
    "eliminated": "Perigo eliminado", "effective": "Medida eficaz", "partial": "Eficácia parcial",
    "no_change": "Sem mudança", "worsened": "Piorou", "inconclusive": "Inconclusivo",
}
METODO = {
    "activity_observation": "Observação da atividade",
    "worker_dialogue": "Diálogo com o trabalhador",
    "questionnaire": "Pesquisa padronizada",
    "workshop": "Oficina",
    "focus_group": "Grupo focal",
    "document_analysis": "Análise documental",
    "cipa_manifestation": "Manifestação da CIPA",
}
PARTICIPACAO = {
    "cipa_minutes": "Ata da CIPA",
    "focus_group": "Grupo focal",
    "risk_communication": "Comunicação de risco",
}
AGRAVO = {
    "transtorno_mental": "transtorno mental", "dort": "DORT", "fadiga": "fadiga",
    "obito": "óbito", "doenca_cardiovascular": "doença cardiovascular",
    "afastamento_prolongado": "afastamento prolongado",
}
CAMPOS_AEP = (
    ("real_work_description", "Descrição do trabalho real"),
    ("exposure_intensity", "Intensidade da exposição"),
    ("exposure_frequency", "Frequência da exposição"),
    ("exposure_duration", "Duração da exposição"),
    ("exposure_cofactors", "Cofatores da exposição"),
    ("health_indicators", "Indicadores de saúde disponíveis"),
    ("absenteeism_notes", "Absenteísmo e rotatividade"),
    ("previous_assessments", "Avaliações anteriores"),
    ("aet_justification", "Justificativa da AET"),
)
ORDEM_RISCO = {"critical": 0, "high": 1, "moderate": 2, "low": 3}


def e(valor) -> str:
    if valor is None or valor == "":
        return "—"
    return html.escape(str(valor))


def rotulo(mapa: dict, codigo) -> str:
    return e(mapa.get(codigo, codigo))


def dia(valor) -> str:
    if not valor:
        return "—"
    return "/".join(reversed(str(valor)[:10].split("-")))


def num(valor, casas=2) -> str:
    if valor is None or valor == "":
        return "—"
    return f"{float(valor):.{casas}f}".replace(".", ",")


def selo(nivel: str) -> str:
    return f'<span class="selo n-{e(nivel)}">{rotulo(RISCO, nivel)}</span>'


def ciclo_de(campanhas: dict, campaign_id: str) -> str:
    titulo = campanhas.get(campaign_id, {}).get("title", "")
    return "Reavaliação" if "reavalia" in titulo.lower() else "Linha de base"


# --- Seções ------------------------------------------------------------------

def capa(d: dict, p: dict) -> str:
    r = p["records"]
    total = sum(u["headcount"] or 0 for u in r["units"])
    unidades = "".join(
        f"<li><b>{e(u['name'])}</b> — {e(u['headcount'])} participantes</li>" for u in r["units"]
    )
    # 24/11/2026, pedido do dono: o logo era um retângulo escuro colado na
    # página branca. Agora a capa abre com uma faixa no mesmo azul-noite do
    # logo, de ponta a ponta, e traz o caminho para pedir a proposta já
    # calculada e a condição de gratuidade.
    return f"""
<section class="capa">
  <header class="capa-topo">
    <img class="logo" src="{LOGO.as_uri()}" alt="FROID — Frequency Recognition of Internal Dynamics">
    <p class="capa-selo">Kit de demonstração<br><b>NR-1 · capítulo 1.5</b></p>
  </header>
  <div class="capa-corpo">
  <h1>Gerenciamento de riscos psicossociais no GRO/PGR</h1>
  <p class="subtitulo">Como o FROID estrutura os documentos que a organização apresenta
  à Inspeção do Trabalho: critérios do GRO, AEP, classificação dos fatores,
  inventário de riscos e plano de ação.</p>
  <div class="aviso-capa">
    <b>DADOS SIMULADOS — documento demonstrativo, sem validade documental.</b>
    A organização <i>{e(p['organization']['legal_name'])}</i> é fictícia. Nenhum dado de
    pessoa real foi usado. Os documentos a seguir são a saída do próprio sistema
    para essa empresa de teste, sem retoque.
  </div>
  <div class="cenario">
    <h3>O cenário do piloto</h3>
    <p>Rede de farmácias com três grupos de exposição e {total} participantes:</p>
    <ul>{unidades}</ul>
    <p>Dois ciclos completos: linha de base e reavaliação após as medidas.</p>
  </div>
  <div class="capa-proposta">
    <p><b>Quer a proposta para a sua empresa?</b> Informe razão social, CNPJ, número de
    estabelecimentos e de trabalhadores e receba por e-mail a proposta de avaliação dos riscos
    psicossociais com o valor mensal já calculado:</p>
    <p class="capa-link"><a href="{URL_DO_PEDIDO}">{e(URL_DO_PEDIDO.replace("https://", ""))}</a></p>
    <p class="capa-gratis">Sem custo até a entrega do primeiro relatório de avaliação dos riscos psicossociais.</p>
  </div>
  <p class="carimbo">Dossiê selado versão {e(d['version'])} · {dia(d['sealed_at'])}<br>
  SHA-256 <code>{e(d['sha'])}</code></p>
  </div>
</section>"""


def sumario(p: dict) -> str:
    c = p["completeness"]["counts"]
    return f"""
<section class="pagina">
  <h2 class="sec">Como ler este kit</h2>
  <p>A NR-1 exige que o Programa de Gerenciamento de Riscos contenha, no mínimo,
  o <b>inventário de riscos</b> e o <b>plano de ação</b> (item 1.5.7.1), e que os
  critérios de avaliação estejam detalhados em documento (item 1.5.4.4.2.2).
  O FROID produz esses documentos encadeados: cada risco do inventário aponta
  para a AEP que o sustenta, e cada medida do plano aponta para o risco que a exigiu.</p>
  <ol class="indice">
    <li><b>Documento 1 — GRO: critérios, estrutura e coleta.</b> Matriz de
    severidade × probabilidade, unidades avaliadas, campanhas e participação dos trabalhadores.</li>
    <li><b>Documento 2 — AEP.</b> Descrição do trabalho real por grupo de exposição
    e as evidências que a sustentam ({c['aep_documents']} AEPs, {c['aep_evidence']} evidências).</li>
    <li><b>Documento 3 — Classificação dos fatores.</b> Onde cada risco caiu na
    matriz e o mapa de níveis por unidade e dimensão, nos dois ciclos.</li>
    <li><b>Documento 4 — Inventário de riscos.</b> {c['inventory_rows']} riscos com
    severidade, probabilidade, nível e a fundamentação de cada classificação.</li>
    <li><b>Documento 5 — Plano de ação.</b> {c['action_plan_items']} medidas com tipo,
    prazo, acompanhamento, forma de aferição e o resultado medido da eficácia.</li>
    <li><b>Encerramento — Dossiê de evidências.</b> Versão selada, base normativa e
    roteiro de resposta a uma fiscalização.</li>
  </ol>
  <div class="nota">
    <b>Privacidade.</b> {e(p['privacy']['employer_access'])}
    {e(p['privacy']['individual_answers'])}
    {e(p['privacy']['suppressed_cohorts'])}
  </div>
</section>"""


def matriz(criterios, contagem: Counter | None = None) -> str:
    linhas = []
    for sev in range(criterios.severity_max, 0, -1):
        celulas = [f'<th class="eixo">{sev}</th>']
        for prob in range(1, criterios.probability_max + 1):
            nivel = nr1_compliance.risk_level(sev, prob, criterios)
            n = (contagem or {}).get((sev, prob), 0)
            conteudo = f"<b>{n}</b>" if contagem is not None and n else (
                "" if contagem is not None else str(sev * prob)
            )
            celulas.append(f'<td class="n-{nivel}">{conteudo}</td>')
        linhas.append("<tr>" + "".join(celulas) + "</tr>")
    rodape = "".join(f'<th class="eixo">{p}</th>' for p in range(1, criterios.probability_max + 1))
    return f"""
<table class="matriz">
  <tr><td class="rotulo-eixo" rowspan="{criterios.severity_max + 2}"><span>Severidade</span></td></tr>
  {''.join(linhas)}
  <tr><th></th>{rodape}</tr>
  <tr><td></td><td colspan="{criterios.probability_max + 1}" class="rotulo-x">Probabilidade</td></tr>
</table>"""


def legenda(criterios) -> str:
    b = criterios.risk_bands
    return (
        f'<p class="legenda">{selo("low")} produto &lt; {b[0]} · {selo("moderate")} {b[0]} a {b[1]-1} · '
        f'{selo("high")} {b[1]} a {b[2]-1} · {selo("critical")} {b[2]} ou mais</p>'
    )


def documento_gro(p: dict) -> str:
    r = p["records"]
    doc = r["criteria"][0]
    criterios = nr1_compliance.GradationCriteria.from_document(doc)
    ps = doc["probability_scale"]
    mags = "".join(
        f"<tr><td>{rotulo(AGRAVO, k)}</td><td class='c'>{e(v)}</td></tr>"
        for k, v in sorted(doc["consequence_magnitudes"].items(), key=lambda kv: -kv[1])
    )
    reducoes = "".join(
        f"<tr><td>{rotulo(EFICACIA, k)}</td><td class='c'>{e(v)}</td></tr>"
        for k, v in ps["efficacy_reductions"].items()
    )
    faixas = " · ".join(f"{int(x * 100)}%" for x in ps["exposure_bands"])
    unidades = "".join(
        f"<tr><td>{e(u['name'])}</td><td>Grupo de exposição</td><td class='c'>{e(u['headcount'])}</td></tr>"
        for u in r["units"]
    )
    campanhas = "".join(
        f"<tr><td>{e(c['title'])}</td><td>{e(c['reference_period'])}</td>"
        f"<td>{e(c['instrument_title'])} v{e(c['instrument_version'])}</td>"
        f"<td class='c'>{e(c['target_headcount'])}</td><td class='c'>{e(c['substantive_responses'])}</td></tr>"
        for c in r["campaigns"]
    )
    unidade_nome = {u["id"]: u["name"] for u in r["units"]}
    participacao = "".join(
        f"<tr><td>{dia(w['occurred_on'])}</td><td>{rotulo(PARTICIPACAO, w['record_type'])}</td>"
        f"<td>{e(unidade_nome.get(w['unit_id'], w['unit_name']))}</td><td class='c'>{e(w['attendee_count'])}</td></tr>"
        for w in sorted(r["worker_participation"], key=lambda w: (w["occurred_on"], w["unit_name"]))
    )
    return f"""
<section class="pagina">
  <p class="doc-num">Documento 1</p>
  <h2 class="sec">GRO — Critérios de avaliação, estrutura e coleta</h2>
  <p class="base">NR-1 1.5.4.4.2: o nível de risco combina a severidade das possíveis lesões
  ou agravos com a probabilidade de ocorrência. 1.5.4.4.2.2: os critérios de gradação, os
  níveis de risco e os critérios de classificação e decisão devem estar detalhados em documento.</p>

  <h3>1.1 Critérios publicados — versão {e(doc['version'])}, em {dia(doc['published_at'])}</h3>
  <div class="duas">
    <div>
      {matriz(criterios)}
      {legenda(criterios)}
      <p class="mini">Cada célula mostra o produto severidade × probabilidade. A cor é calculada
      pela mesma função que classifica os riscos no sistema.</p>
    </div>
    <div>
      <p><b>Severidade</b> (1 a {criterios.severity_max}): {e(doc['severity_scale']['basis'])}.</p>
      <table class="t"><tr><th>Possível agravo</th><th>Magnitude</th></tr>{mags}</table>
      <p><b>Probabilidade</b> (1 a {criterios.probability_max}): {e(ps['basis'])}.
      Peso da profundidade da exigência: {num(ps['demand_weight'])}. Faixas de exposição: {faixas}.</p>
      <table class="t"><tr><th>Eficácia das medidas existentes</th><th>Redução de faixas</th></tr>{reducoes}</table>
      <p><b>Revisão</b>: a cada {e(doc['review_interval_months'])} meses, ou antes, nos gatilhos do item 1.5.4.4.6.
      Sistema de gestão de SST certificado: {"sim" if doc['has_certified_sst_system'] else "não"}.</p>
    </div>
  </div>

  <h3>1.2 Estrutura avaliada</h3>
  <table class="t"><tr><th>Unidade de avaliação</th><th>Tipo</th><th>Efetivo</th></tr>{unidades}</table>

  <h3>1.3 Coleta (campanhas encerradas)</h3>
  <table class="t"><tr><th>Campanha</th><th>Período</th><th>Instrumento</th><th>Público-alvo</th><th>Respostas válidas</th></tr>{campanhas}</table>
  <p class="mini">Nenhum resultado é liberado com a coleta aberta, e recortes abaixo do piso de proteção
  não exibem média.</p>

  <h3>1.4 Participação dos trabalhadores</h3>
  <table class="t"><tr><th>Data</th><th>Registro</th><th>Unidade</th><th>Presentes</th></tr>{participacao}</table>
</section>"""


def documento_aep(p: dict) -> str:
    r = p["records"]
    evid = defaultdict(list)
    for ev in r["evidence"]:
        evid[ev["aep_id"]].append(ev)
    blocos = []
    ordem = sorted(r["aep"], key=lambda a: ("reavalia" in a["reference_period"].lower(), a["unit_name"]))
    for a in ordem:
        campos = "".join(
            f"<dt>{rot}</dt><dd>{e(a.get(chave))}</dd>" for chave, rot in CAMPOS_AEP
            if not (chave == "aet_justification" and not a.get("aet_required"))
        )
        linhas_ev = "".join(
            f"<tr><td>{rotulo(METODO, x['method'])}</td><td>{dia(x['collected_on'])}</td>"
            f"<td>{e(x['collected_by'])}</td><td>{e(x['summary'])}</td></tr>"
            for x in sorted(evid.get(a["id"], []), key=lambda x: x["method"])
        )
        blocos.append(f"""
  <article class="aep">
    <header>
      <h3>{e(a['unit_name'])}</h3>
      <p>{e(a['reference_period'])} · Responsável: <b>{e(a['responsible_name'])}</b>
      ({e(a.get('responsible_qualification'))}) · Concluída em {dia(a['concluded_at'])} ·
      AET indicada: {"sim" if a['aet_required'] else "não"}</p>
    </header>
    <dl>{campos}</dl>
    <h4>Evidências ({len(evid.get(a['id'], []))} métodos combinados)</h4>
    <table class="t ev"><tr><th>Método</th><th>Data</th><th>Coletado por</th><th>Síntese</th></tr>{linhas_ev}</table>
  </article>""")
    return f"""
<section class="pagina">
  <p class="doc-num">Documento 2</p>
  <h2 class="sec">AEP — Avaliação Ergonômica Preliminar</h2>
  <p class="base">O Guia do MTE (2025) sobre fatores de riscos psicossociais orienta a
  identificação pelo trabalho real, combinando métodos e com participação dos trabalhadores.
  No FROID, cada grupo de exposição tem uma AEP por ciclo, e o questionário é apenas um dos métodos.</p>
  {''.join(blocos)}
</section>"""


def documento_classificacao(p: dict) -> str:
    r = p["records"]
    criterios = nr1_compliance.GradationCriteria.from_document(r["criteria"][0])
    campanhas = {c["id"]: c for c in r["campaigns"]}
    por_ciclo = defaultdict(Counter)
    for i in r["inventory"]:
        por_ciclo[ciclo_de(campanhas, i["campaign_id"])][(i["severity"], i["probability"])] += 1
    unidades = [u["name"] for u in sorted(r["units"], key=lambda u: -u["headcount"])]
    grade = {}
    fator_da_dim = {}
    for i in r["inventory"]:
        grade[(i["dimension_title"], i["unit_name"], ciclo_de(campanhas, i["campaign_id"]))] = i["risk_level"]
        fator_da_dim[i["dimension_title"]] = i["nr1_factor"]
    cab = "".join(f'<th colspan="2" class="un">{e(u)}</th>' for u in unidades)
    sub = "<th>Base</th><th>Reav.</th>" * len(unidades)
    linhas = []
    for fator in FATOR:
        dims = sorted(d for d, f in fator_da_dim.items() if f == fator)
        if not dims:
            continue
        linhas.append(f'<tr class="grupo"><td colspan="{1 + 2 * len(unidades)}">{rotulo(FATOR, fator)}</td></tr>')
        for d in dims:
            cel = []
            for u in unidades:
                for ciclo in ("Linha de base", "Reavaliação"):
                    nivel = grade.get((d, u, ciclo))
                    cel.append(f'<td class="n-{nivel}">{rotulo(RISCO, nivel)}</td>' if nivel else "<td>—</td>")
            linhas.append(f"<tr><td class='dim'>{e(d)}</td>{''.join(cel)}</tr>")
    resumo = []
    for ciclo in ("Linha de base", "Reavaliação"):
        cont = Counter(i["risk_level"] for i in r["inventory"] if ciclo_de(campanhas, i["campaign_id"]) == ciclo)
        partes = " · ".join(f"{selo(n)} {cont[n]}" for n in ("critical", "high", "moderate", "low") if cont[n])
        resumo.append(f"""
    <div><h4>{ciclo}</h4>{matriz(criterios, por_ciclo[ciclo])}<p class="mini">{partes}</p></div>""")
    return f"""
<section class="pagina">
  <p class="doc-num">Documento 3</p>
  <h2 class="sec">Classificação dos fatores de risco</h2>
  <p class="base">NR-1 1.5.4.4.3: determinados os níveis de risco, os riscos são classificados
  para identificar a necessidade de adotar ou manter medidas de prevenção e elaborar o plano de ação.</p>
  <h3>3.1 Onde cada risco caiu na matriz</h3>
  <div class="duas">{''.join(resumo)}</div>
  <p class="mini">Número na célula = quantidade de riscos do inventário com aquela severidade e probabilidade.</p>
  <h3>3.2 Mapa por fator da NR-1, dimensão e unidade</h3>
  <table class="mapa"><tr><th rowspan="2">Dimensão avaliada</th>{cab}</tr><tr>{sub}</tr>{''.join(linhas)}</table>
  <p class="mini">Os dois ciclos lado a lado mostram o que melhorou, o que se manteve e o que piorou.
  A reavaliação não é apresentada como sucesso automático.</p>
</section>"""


def documento_inventario(p: dict) -> str:
    r = p["records"]
    campanhas = {c["id"]: c for c in r["campaigns"]}
    blocos = []
    for ciclo in ("Linha de base", "Reavaliação"):
        itens = sorted(
            (i for i in r["inventory"] if ciclo_de(campanhas, i["campaign_id"]) == ciclo),
            key=lambda i: (ORDEM_RISCO.get(i["risk_level"], 9), -int(i["exposed_workers"] or 0), i["dimension_title"]),
        )
        graves = [i for i in itens if i["risk_level"] in ("critical", "high")]
        demais = [i for i in itens if i["risk_level"] not in ("critical", "high")]
        linhas = "".join(
            f"""<tr><td>{selo(i['risk_level'])}</td>
<td><b>{e(i['dimension_title'])}</b><br><span class="mini">{rotulo(FATOR, i['nr1_factor'])}</span></td>
<td>{e(i['unit_name'])}</td><td class="c">{e(i['exposed_workers'])}</td>
<td class="c">{num(i['mean_score'])}</td><td class="c">{e(i['severity'])}</td><td class="c">{e(i['probability'])}</td>
<td>{', '.join(rotulo(AGRAVO, a) for a in (i.get('possible_harms') or [])) or '—'}</td>
<td class="fund">{e(i['rationale'])}</td></tr>"""
            for i in graves
        )
        compactas = "".join(
            f"""<tr><td>{selo(i['risk_level'])}</td><td>{e(i['dimension_title'])}</td><td>{rotulo(FATOR, i['nr1_factor'])}</td>
<td>{e(i['unit_name'])}</td><td class="c">{e(i['exposed_workers'])}</td><td class="c">{num(i['mean_score'])}</td>
<td class="c">{e(i['severity'])}</td><td class="c">{e(i['probability'])}</td></tr>"""
            for i in demais
        )
        camp = next(c for c in r["campaigns"] if ciclo_de(campanhas, c["id"]) == ciclo)
        blocos.append(f"""
  <h3>{ciclo} — {e(camp['reference_period'])} ({len(itens)} riscos)</h3>
  <h4>Riscos altos e críticos ({len(graves)}), com a fundamentação registrada pelo sistema</h4>
  <table class="t inv"><thead><tr><th>Nível</th><th>Dimensão / fator NR-1</th><th>Unidade</th><th>Expostos</th>
  <th>Média</th><th>Sev.</th><th>Prob.</th><th>Possíveis agravos</th><th>Fundamentação da classificação</th></tr></thead>
  <tbody>{linhas}</tbody></table>
  <h4>Demais riscos ({len(demais)})</h4>
  <table class="t inv"><thead><tr><th>Nível</th><th>Dimensão</th><th>Fator NR-1</th><th>Unidade</th><th>Expostos</th>
  <th>Média</th><th>Sev.</th><th>Prob.</th></tr></thead><tbody>{compactas}</tbody></table>""")
    return f"""
<section class="pagina">
  <p class="doc-num">Documento 4</p>
  <h2 class="sec">Inventário de riscos ocupacionais — fatores psicossociais</h2>
  <p class="base">NR-1 1.5.7.3: os dados da identificação de perigos e da avaliação dos riscos são
  consolidados no inventário, mantido atualizado, com histórico guardado por no mínimo 20 anos.
  Cada linha abaixo está vinculada à AEP da mesma unidade e do mesmo ciclo.</p>
  {''.join(blocos)}
</section>"""


def documento_plano(p: dict, responsavel: str) -> str:
    r = p["records"]
    campanhas = {c["id"]: c for c in r["campaigns"]}
    inv = {i["id"]: i for i in r["inventory"]}
    blocos = []
    for ciclo in ("Linha de base", "Reavaliação"):
        itens = sorted(
            (a for a in r["action_plan"] if ciclo_de(campanhas, a["campaign_id"]) == ciclo),
            key=lambda a: (a["priority_rank"] or 999),
        )
        cartoes = []
        graves = [a for a in itens if inv.get(a["inventory_id"], {}).get("risk_level") in ("critical", "high")]
        demais = [a for a in itens if a not in graves]
        for a in graves:
            nivel = inv.get(a["inventory_id"], {}).get("risk_level")
            cartoes.append(f"""
    <article class="medida">
      <header><span class="prio">#{e(a['priority_rank'])}</span> {selo(nivel) if nivel else ''}
      <b>{e(a['dimension_title'])}</b> · {e(a['unit_name'])} · {e(a['exposed_workers'])} expostos</header>
      <p class="acao"><span class="tag">{rotulo(ACAO, a['plan_action'])}</span>
      <span class="tag">{rotulo(TIPO_MEDIDA, a['measure_type'])}</span> {e(a['measure'])}</p>
      <dl class="grade">
        <dt>Responsável</dt><dd>{e(responsavel)}</dd>
        <dt>Prazo</dt><dd>{dia(a['due_date'])}</dd>
        <dt>Situação</dt><dd>{rotulo(STATUS, a['status'])}{' em ' + dia(a['implemented_at']) if a.get('implemented_at') else ''}</dd>
        <dt>Eficácia</dt><dd>{rotulo(EFICACIA, a['effectiveness'])}</dd>
        <dt>Acompanhamento</dt><dd>{e(a['monitoring_method'])}</dd>
        <dt>Aferição do resultado</dt><dd>{e(a['result_measurement'])}</dd>
        <dt>Evidência</dt><dd>{e(a['evidence'])}</dd>
      </dl>
    </article>""")
        compactas = "".join(
            f"""<tr><td class="c">#{e(a['priority_rank'])}</td><td>{selo(inv.get(a['inventory_id'], {}).get('risk_level', ''))}</td>
<td>{e(a['dimension_title'])}</td><td>{e(a['unit_name'])}</td><td>{rotulo(ACAO, a['plan_action'])} · {rotulo(TIPO_MEDIDA, a['measure_type'])}</td>
<td>{dia(a['due_date'])}</td><td>{rotulo(STATUS, a['status'])}</td><td>{rotulo(EFICACIA, a['effectiveness'])}</td></tr>"""
            for a in demais
        )
        blocos.append(f"""<h3>{ciclo} — {len(itens)} medidas</h3>
  <h4>Medidas para riscos altos e críticos ({len(graves)})</h4>{''.join(cartoes)}
  <h4>Medidas para os demais riscos ({len(demais)})</h4>
  <p class="mini">Cada uma tem os mesmos campos obrigatórios das medidas acima (responsável, prazo,
  acompanhamento, aferição e evidência); aqui aparecem resumidas.</p>
  <table class="t ef"><tr><th>Prior.</th><th>Nível</th><th>Dimensão</th><th>Unidade</th><th>Ação · tipo</th>
  <th>Prazo</th><th>Situação</th><th>Eficácia</th></tr>{compactas}</table>""")

    efic = sorted(r["effectiveness"], key=lambda x: (not x["requires_correction"], x["unit_name"], x["dimension_title"]))
    linhas = "".join(
        f"""<tr class="{'corrigir' if x['requires_correction'] else ''}"><td>{e(x['unit_name'])}</td><td>{e(x['dimension_title'])}</td>
<td class="c">{num(x['baseline_mean'])}</td><td class="c">{num(x['followup_mean'])}</td><td class="c">{num(x['effect_size'])}</td>
<td>{rotulo(VEREDITO, x['verdict'])}</td><td class="c">{"sim" if x['requires_correction'] else "não"}</td></tr>"""
        for x in efic
    )
    corr = sum(1 for x in r["effectiveness"] if x["requires_correction"])
    return f"""
<section class="pagina">
  <p class="doc-num">Documento 5</p>
  <h2 class="sec">Plano de ação</h2>
  <p class="base">NR-1 1.5.5.2.1: o plano indica as medidas a serem introduzidas, aprimoradas ou
  mantidas; 1.5.5.2.1.1: o número de trabalhadores atingidos aumenta a prioridade; 1.5.5.2.2:
  cada medida tem cronograma, responsável, forma de acompanhamento e aferição de resultados.</p>
  {''.join(blocos)}
  <h3>5.1 Eficácia das medidas — linha de base × reavaliação</h3>
  <p>Mudança menor que o ruído da coorte é declarada “sem mudança”. {corr} comparações exigem
  correção no próximo ciclo e aparecem primeiro.</p>
  <table class="t ef"><tr><th>Unidade</th><th>Dimensão</th><th>Média base</th><th>Média reav.</th>
  <th>Efeito (d)</th><th>Veredito</th><th>Exige correção</th></tr>{linhas}</table>
</section>"""


def encerramento(d: dict, p: dict) -> str:
    base = "".join(
        f"<li><b>{e(n['reference'])}</b> — {e(n['purpose'])}</li>" for n in p["normative_basis"]
    )
    roteiro = "".join(f"<li>{e(x)}</li>" for x in p["response_protocol"])
    return f"""
<section class="pagina">
  <p class="doc-num">Encerramento</p>
  <h2 class="sec">Dossiê de evidências e resposta a uma fiscalização</h2>
  <p>Todos os documentos acima pertencem a uma única versão selada do dossiê. O SHA-256 permite
  verificar que o conteúdo apresentado é o mesmo que foi registrado; cada nova versão guarda o
  hash da anterior.</p>
  <table class="t"><tr><th>Versão</th><th>Selada em</th><th>SHA-256</th><th>Situação</th></tr>
  <tr><td class="c">{e(d['version'])}</td><td>{dia(d['sealed_at'])}</td><td><code>{e(d['sha'])}</code></td>
  <td>{"completo, sem lacunas" if p['completeness']['status'] == 'complete' else e(p['completeness']['status'])}</td></tr></table>
  <h3>Roteiro de resposta a uma requisição</h3>
  <ol>{roteiro}</ol>
  <h3>Base normativa</h3>
  <ul>{base}</ul>
  <div class="nota">O dossiê organiza a evidência existente e sua cadeia. Ele não cria declaração
  automática de conformidade nem substitui a revisão do responsável pelo GRO, do profissional
  competente ou da assessoria jurídica. O PGR deve ser datado e assinado pela organização (1.5.7.2).</div>
  <div class="cta">Quer ver o processo com a estrutura da sua empresa?<br>
  <b>www.froid.com.br</b> · froid@froid.com.br</div>
</section>"""


CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-left { content: "DADOS SIMULADOS — documento demonstrativo, sem validade documental"; font: 7.5pt Figtree, sans-serif; color: #b45309; }
  @bottom-right { content: "FROID · " counter(page) " / " counter(pages); font: 7.5pt Figtree, sans-serif; color: #64748b; } }
@page :first { margin: 0; @bottom-left { content: none; } @bottom-right { content: none; } }
* { box-sizing: border-box; }
body { font-family: 'Figtree', sans-serif; font-size: 9.5pt; color: #0f172a; line-height: 1.42; margin: 0; }
h1, h2, h3, h4 { font-family: 'Figtree', sans-serif; color: #0b1f44; margin: 0; }
h2.sec { font-size: 19pt; font-weight: 800; margin: 2mm 0 3mm; }
h3 { font-size: 12pt; font-weight: 700; margin: 6mm 0 2.5mm; break-after: avoid; }
h4 { font-size: 10pt; margin: 3mm 0 1.5mm; }
p { margin: 0 0 2.5mm; }
code { font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; word-break: break-all; }
.pagina { break-before: page; }
.doc-num { font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; letter-spacing: .12em; color: #2563eb; font-weight: 700; font-size: 8.5pt; margin: 0; }
.base { background: #eff6ff; border-left: 3px solid #2563eb; padding: 2.5mm 3.5mm; font-size: 8.8pt; color: #1e3a8a; }
.mini { font-size: 7.8pt; color: #475569; }
.nota { background: #f8fafc; border: 1px solid #e2e8f0; padding: 3mm 4mm; font-size: 8.5pt; margin-top: 4mm; border-radius: 2mm; }
.watermark { position: fixed; top: 45%; left: 0; right: 0; text-align: center; transform: rotate(-28deg);
  font-family: 'Figtree'; font-weight: 800; font-size: 64pt; color: rgba(180, 83, 9, .06); z-index: -1; letter-spacing: .05em; }
.capa { height: 297mm; display: flex; flex-direction: column; }
.capa-topo { background: #04060f; display: flex; align-items: center; justify-content: space-between;
  padding: 9mm 14mm 8mm; border-bottom: 1.2mm solid #2563eb;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.capa .logo { width: 78mm; display: block;
  /* Esfuma só a borda de fora da imagem, para o fundo dela se fundir à faixa
     sem apagar as pontas de "Frequency ... Dynamics". */
  -webkit-mask-image: linear-gradient(to right, transparent 0, #000 4%, #000 96%, transparent 100%),
                      linear-gradient(to bottom, transparent 0, #000 12%, #000 88%, transparent 100%);
  -webkit-mask-composite: source-in;
  mask-image: linear-gradient(to right, transparent 0, #000 4%, #000 96%, transparent 100%),
              linear-gradient(to bottom, transparent 0, #000 12%, #000 88%, transparent 100%);
  mask-composite: intersect; }
.capa-selo { margin: 0; text-align: right; color: #cbd5e1; font-family: 'Space Grotesk', sans-serif;
  text-transform: uppercase; letter-spacing: .14em; font-size: 8.5pt; line-height: 1.6; }
.capa-selo b { color: #fff; }
.capa-corpo { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 8mm 18mm 12mm; }
.capa-proposta { margin-top: 6mm; border: 1.5px solid #2563eb; background: #eff6ff; border-radius: 2mm;
  padding: 4mm 5mm; color: #0b1f44; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.capa-proposta p { margin: 0 0 2mm; }
.capa-link a { color: #1d4ed8; font-weight: 700; font-size: 11pt; text-decoration: none; }
.capa-gratis { margin: 3mm 0 0 !important; font-weight: 700; color: #047857; }
.sobretitulo { font-family: 'Space Grotesk'; text-transform: uppercase; letter-spacing: .14em; color: #2563eb; font-weight: 700; }
.capa h1 { font-size: 30pt; font-weight: 800; line-height: 1.08; margin: 2mm 0 4mm; }
.subtitulo { font-size: 12pt; color: #334155; max-width: 160mm; }
.aviso-capa { margin: 8mm 0 6mm; border: 1.5px solid #d97706; background: #fffbeb; color: #78350f; padding: 4mm 5mm; border-radius: 2mm; }
.cenario { border-top: 1px solid #cbd5e1; padding-top: 4mm; }
.cenario h3 { margin-top: 0; }
.cenario ul { margin: 1mm 0 2mm; }
.carimbo { margin-top: 8mm; font-size: 8pt; color: #64748b; }
.indice li { margin-bottom: 2.5mm; }
.duas { display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; align-items: start; }
table { border-collapse: collapse; width: 100%; }
.t { font-size: 8.3pt; margin-bottom: 3mm; }
.t th { background: #0b1f44; color: #fff; font-family: 'Figtree'; font-weight: 600; text-align: left; padding: 1.4mm 2mm; }
.t td { border-bottom: 1px solid #e2e8f0; padding: 1.4mm 2mm; vertical-align: top; }
.t tr { break-inside: avoid; }
.c { text-align: center; }
.matriz { width: auto; border-collapse: separate; border-spacing: 1.2mm; }
.matriz td, .matriz th { width: 12mm; height: 10mm; text-align: center; font-family: 'Figtree'; font-size: 9pt; border-radius: 1.2mm; }
.matriz th.eixo { color: #475569; font-weight: 600; }
.rotulo-eixo { width: 5mm !important; }
.rotulo-eixo span { display: inline-block; transform: rotate(-90deg); font-size: 8pt; color: #475569; white-space: nowrap; }
.rotulo-x { font-size: 8pt; color: #475569; height: auto !important; }
.n-low { background: #bbf7d0; color: #14532d; }
.n-moderate { background: #fde68a; color: #713f12; }
.n-high { background: #fdba74; color: #7c2d12; }
.n-critical { background: #f87171; color: #450a0a; }
.selo { display: inline-block; padding: .3mm 1.8mm; border-radius: 3mm; font-family: 'Figtree'; font-weight: 700; font-size: 7.5pt; white-space: nowrap; }
.legenda { font-size: 7.8pt; margin-top: 2mm; }
.aep { break-inside: auto; border: 1px solid #e2e8f0; border-radius: 2mm; padding: 4mm; margin: 4mm 0; }
.aep header { border-bottom: 1px solid #e2e8f0; margin-bottom: 2mm; }
.aep header p { font-size: 8.3pt; color: #475569; }
.aep dl { display: grid; grid-template-columns: 38mm 1fr; gap: 1.5mm 4mm; margin: 0; font-size: 8.6pt; }
.aep dt { font-weight: 700; color: #0b1f44; }
.aep dd { margin: 0; }
.ev td:nth-child(1) { white-space: nowrap; }
.mapa { font-size: 7.6pt; }
.mapa th { background: #0b1f44; color: #fff; padding: 1.2mm; font-family: 'Figtree'; font-weight: 600; }
.mapa th.un { font-size: 7.2pt; }
.mapa td { border: 1px solid #fff; padding: 1.1mm; text-align: center; }
.mapa td.dim { text-align: left; background: #f8fafc; }
.mapa tr.grupo td { text-align: left; font-weight: 700; background: #e2e8f0; color: #0b1f44; }
.inv { font-size: 7.4pt; }
.inv th { font-size: 7.4pt; }
.inv thead { display: table-header-group; }
.inv .fund { font-size: 6.8pt; color: #475569; width: 62mm; }
.medida { border: 1px solid #e2e8f0; border-left: 3px solid #2563eb; border-radius: 1.5mm; padding: 2.5mm 3.5mm; margin: 2.5mm 0; break-inside: avoid; font-size: 8.3pt; }
.medida header { margin-bottom: 1mm; }
.prio { font-family: 'Space Grotesk'; font-weight: 700; color: #2563eb; margin-right: 1mm; }
.acao { margin-bottom: 1.5mm; }
.tag { display: inline-block; background: #e0e7ff; color: #1e3a8a; border-radius: 1mm; padding: 0 1.5mm; font-size: 7.4pt; font-weight: 700; margin-right: 1mm; }
.medida .grade { display: grid; grid-template-columns: 30mm 1fr; gap: .8mm 3mm; margin: 0; font-size: 7.8pt; }
.medida dt { color: #475569; font-weight: 700; }
.medida dd { margin: 0; }
.ef { font-size: 7.6pt; }
.ef tr.corrigir td { background: #fef2f2; }
.cta { margin-top: 10mm; text-align: center; font-family: 'Figtree'; font-size: 12pt; color: #0b1f44; border: 1.5px solid #2563eb; border-radius: 2mm; padding: 6mm; }
"""


def montar_html(d: dict, responsavel: str) -> str:
    p = d["payload"]
    corpo = "".join((
        capa(d, p), sumario(p), documento_gro(p), documento_aep(p),
        documento_classificacao(p), documento_inventario(p), documento_plano(p, responsavel),
        encerramento(d, p),
    ))
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>FROID — Kit de demonstração NR-1 (dados simulados)</title>
<link rel="stylesheet" href="{FONTES.as_uri()}"><style>{CSS}</style></head>
<body><div class="watermark">DADOS SIMULADOS</div>{corpo}</body></html>"""


def imprimir(html_path: Path, pdf_path: Path) -> None:
    navegador = next((n for n in NAVEGADORES if n.exists()), None)
    if navegador is None:
        raise SystemExit("Nenhum Chrome/Edge encontrado para imprimir o PDF.")
    subprocess.run(
        [str(navegador), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--allow-file-access-from-files", f"--print-to-pdf={pdf_path}", html_path.as_uri()],
        check=True, capture_output=True, timeout=180,
    )
    if not pdf_path.exists() or pdf_path.stat().st_size < 10_000:
        raise SystemExit(f"O navegador não gerou o PDF em {pdf_path}.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossie", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--responsavel", default="",
                    help="Nome exibido da conta responsável pelas medidas (o dossiê guarda só o vínculo).")
    ap.add_argument("--html", type=Path, help="Também grava o HTML intermediário aqui.")
    args = ap.parse_args()

    d = json.loads(args.dossie.read_text(encoding="utf-8"))
    nome_org = d["payload"]["organization"]["legal_name"]
    if "DADOS SIMULADOS" not in nome_org:
        # O kit é público. Ele só pode nascer do piloto fictício, nunca do
        # dossiê de um cliente real.
        raise SystemExit(f"Recusado: o dossiê não é do piloto simulado ({nome_org!r}).")
    if d["payload"]["completeness"]["status"] != "complete":
        raise SystemExit("Recusado: o dossiê do piloto está incompleto; gere o piloto de novo.")

    pagina = montar_html(d, args.responsavel)
    if args.html:
        args.html.write_text(pagina, encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "kit.html"
        html_path.write_text(pagina, encoding="utf-8")
        imprimir(html_path, args.saida.resolve())
    print(f"PDF gerado: {args.saida} ({args.saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
