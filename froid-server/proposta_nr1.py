"""Proposta de execução NR-1, montada para cada cliente que pede o kit no site.

Pedido do dono, 24/11/2026: quem preenche o formulário do kit recebe, no
mesmo e-mail, a proposta de avaliação dos riscos psicossociais já com a razão
social, o CNPJ, o responsável, o número de estabelecimentos e de trabalhadores
e o valor mensal calculado.

Este módulo é a ÚNICA fonte do texto da proposta. A minuta enviada pelo dono
(23/11/2026) foi revista aqui; não existe outra cópia para divergir.

Regras que ele não negocia:

  * Nenhum preço é escrito aqui. O valor sai de `pricing_nr1.simular` sobre a
    tabela vigente (a mesma do simulador do site), e o retrato que se grava
    no banco leva o código, a versão e a digital da tabela. A proposta aberta
    depois mostra o que foi calculado no pedido, não o que a tabela diria hoje.
  * Os pisos de anonimato vêm de `nr1_compliance` (os mesmos que o servidor
    aplica). Escrever "10" e "15" aqui criaria um espelho de número (regra 2.7).
  * O que a plataforma não faz não é prometido: não há importação de planilha,
    e a lista de trabalhadores é só de matrículas, colada pelo RH no próprio
    painel (Nr1Campaign.tsx). O FROID não recebe nome, e-mail ou CPF de ninguém.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

import leitura_governanca
import nr1_compliance
import pricing_nr1

# Decisão do dono: a proposta vale 30 dias (minuta de 23/11/2026). O LINK que a
# entrega vale 24 horas (main.KIT_NR1_VALIDADE_HORAS); quem quiser guardá-la
# salva em PDF. São dois prazos diferentes de propósito.
VALIDADE_DA_PROPOSTA_DIAS = 30
VIGENCIA_MESES = 12
# Limites de bom senso para formulário público, os mesmos da rota de simulação.
MAX_TRABALHADORES = 200_000
MAX_ESTABELECIMENTOS = 5_000


# ------------------------------------------------------------------ CNPJ ---
# Desde julho de 2026 a Receita emite CNPJ alfanumérico: 12 posições de letra
# ou número e 2 dígitos verificadores. O cálculo do dígito é o mesmo de sempre,
# com o valor de cada caractere tomado como (código ASCII − 48). Para um CNPJ só
# de números isto dá exatamente o cálculo antigo.
_PESOS_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _digito(base: str, pesos: tuple[int, ...]) -> int:
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def normalizar_cnpj(valor: str) -> Optional[str]:
    """O CNPJ em 14 caracteres maiúsculos, ou None se não for um CNPJ válido."""
    bruto = re.sub(r"[.\-/\s]", "", str(valor or "")).upper()
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", bruto):
        return None
    if len(set(bruto)) == 1:
        return None
    if _digito(bruto[:12], _PESOS_1) != int(bruto[12]):
        return None
    if _digito(bruto[:13], _PESOS_2) != int(bruto[13]):
        return None
    return bruto


def formatar_cnpj(cnpj: str) -> str:
    c = str(cnpj or "")
    if len(c) != 14:
        return c
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def inteiro_positivo(valor: Any, maximo: int) -> Optional[int]:
    """Inteiro entre 1 e `maximo`, aceitando "1.200" e " 35 "; senão None."""
    texto = re.sub(r"[.\s]", "", str(valor if valor is not None else ""))
    if not texto.isdigit():
        return None
    numero = int(texto)
    return numero if 1 <= numero <= maximo else None


# --------------------------------------------------------------- retrato ---
def montar_retrato(
    *, lead: dict, lead_id: str, tabela: dict, procedencia: str, emitida_em: datetime,
) -> dict:
    """O que a proposta mostra, calculado UMA vez, no pedido, e gravado no banco.

    `tabela` é a tabela vigente já conferida pela digital
    (main._nr1_pricing_tabela_vigente). Levanta `pricing_nr1.TabelaInvalida`
    se o cálculo recusar os números — quem chama decide o que dizer.
    """
    calculo = pricing_nr1.simular(lead["trabalhadores"], lead["estabelecimentos"], tabela)
    faixas = {f["order"]: f for f in tabela["tiers"]}
    memoria = []
    for faixa in calculo["tierBreakdown"]:
        if not faixa["workersInTier"]:
            continue
        limites = faixas[faixa["order"]]
        memoria.append({
            "faixa": faixa["order"],
            "de": limites["lowerBound"],
            "ate": limites["upperBound"],
            "trabalhadores": faixa["workersInTier"],
            "preco": pricing_nr1.formatar_brl(faixa["workerPriceCents"]),
            "subtotal": pricing_nr1.formatar_brl(faixa["subtotalCents"]),
        })
    total = calculo["monthlyTotalCents"]
    return {
        "numero": f"{emitida_em:%Y}-{str(lead_id).replace('-', '')[:6].upper()}",
        "emitida_em": emitida_em.date().isoformat(),
        "valida_ate": (emitida_em.date() + timedelta(days=VALIDADE_DA_PROPOSTA_DIAS)).isoformat(),
        "empresa": lead["empresa"],
        "cnpj": lead["cnpj"],
        "responsavel": lead["nome"],
        "cargo": lead.get("cargo") or "",
        "email": lead["email"],
        "estabelecimentos": lead["estabelecimentos"],
        "trabalhadores": lead["trabalhadores"],
        "base_por_estabelecimento": pricing_nr1.formatar_brl(tabela["baseEstablishmentCents"]),
        "base_subtotal": pricing_nr1.formatar_brl(calculo["baseSubtotalCents"]),
        "faixas": memoria,
        "mensal": pricing_nr1.formatar_brl(total),
        "anual": pricing_nr1.formatar_brl(total * 12),
        "por_trabalhador": pricing_nr1.formatar_brl(calculo["perWorkerMonthCents"]),
        # Decidido no pedido e gravado, com o percentual e os valores: a
        # proposta já enviada não ganha, não perde e não reprecifica o bloco
        # do adicional depois. Retrato antigo não tem a chave e não o mostra.
        "leitura_governanca": _adicional_governanca(lead["estabelecimentos"], total),
        "tabela": {
            "codigo": calculo["pricingTable"]["code"],
            "versao": calculo["pricingTable"]["version"],
            "vigente_desde": calculo["pricingTable"]["validFrom"],
            "sha256": calculo["pricingTable"]["sha256"],
            "procedencia": procedencia,
        },
    }


def _adicional_governanca(estabelecimentos: int, mensal_centavos: int) -> Optional[dict]:
    """O adicional da Leitura de Governança, se a empresa pode contratá-lo."""
    if not leitura_governanca.pode_oferecer(estabelecimentos):
        return None
    adicional = pricing_nr1.adicional_leitura_governanca(mensal_centavos)
    return {
        "percentual": pricing_nr1.ADICIONAL_LEITURA_GOVERNANCA_PERCENTUAL,
        "mensal": pricing_nr1.formatar_brl(adicional),
        "total_com_adicional": pricing_nr1.formatar_brl(mensal_centavos + adicional),
    }


# ---------------------------------------------------------------- página ---
def _data(iso: str) -> str:
    try:
        return date.fromisoformat(str(iso)).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def _n(numero: int) -> str:
    return f"{int(numero):,}".replace(",", ".")


def _plural(numero: int, singular: str, plural: str) -> str:
    return f"{_n(numero)} {singular if int(numero) == 1 else plural}"


def renderizar(r: dict) -> str:
    """A proposta pronta para ler na tela e salvar em PDF pelo navegador."""
    e = lambda v: html.escape(str(v if v is not None else ""))  # noqa: E731
    piso_recorte = nr1_compliance.MIN_COHORT_CUT
    piso_campanha = nr1_compliance.MIN_COHORT_TOTAL
    estab = _plural(r["estabelecimentos"], "estabelecimento", "estabelecimentos")
    trab = _plural(r["trabalhadores"], "trabalhador", "trabalhadores")
    ac = e(r["responsavel"]) + (f", {e(r['cargo'])}" if r.get("cargo") else "")

    linhas_faixa = "".join(
        f"<tr><td>Faixa {f['faixa']} — "
        + (f"de {_n(f['de'])} a {_n(f['ate'])}" if f["ate"] else f"acima de {_n(f['de'] - 1)}")
        + f" trabalhadores</td><td class=\"n\">{_n(f['trabalhadores'])} × {e(f['preco'])}</td>"
        f"<td class=\"n\">{e(f['subtotal'])}</td></tr>"
        for f in r["faixas"]
    )

    porte = ""
    if r["trabalhadores"] < piso_campanha:
        porte = (
            f"<p class=\"alerta\">Com {trab}, a campanha por questionário não alcança o "
            f"mínimo de {piso_campanha} respostas concluídas que a plataforma exige para "
            "exibir qualquer resultado. O caminho de avaliação para esse porte é definido "
            "na reunião de dimensionamento, antes de qualquer cobrança.</p>"
        )
    elif r["trabalhadores"] < 2 * piso_recorte:
        porte = (
            f"<p class=\"alerta\">Com {trab}, a avaliação comporta um único recorte: cada "
            f"recorte precisa de ao menos {piso_recorte} respondentes para ter resultado "
            "exibido.</p>"
        )

    tabela = r["tabela"]
    governanca = ""
    adicional = r.get("leitura_governanca")
    if isinstance(adicional, dict):
        # O adicional é oferecido, nunca apresentado como necessário: o
        # escopo acima atende à NR-1 sozinho. Percentual e valores vêm do
        # retrato, calculados por pricing_nr1 no pedido.
        governanca = f"""<div class="adicional">
<h3>Adicional opcional — {e(leitura_governanca.NOME)}</h3>
<p>Com {estab}, a {e(r['empresa'])} pode contratar a leitura da liderança por função: gerentes,
subgerentes ou supervisores lidos como um grupo que atravessa os endereços, com o resultado
lançado no inventário de cada estabelecimento onde a função existe. No inventário de cada
endereço, a equipe e a liderança aparecem lado a lado, o que mostra se o risco nasce na política
da empresa, na camada de liderança ou no local.</p>
<ul>
  <li>Condição: ao menos {leitura_governanca.PESSOAS_NA_FUNCAO_MINIMAS} pessoas numa mesma função
  de liderança, confirmada pela simulação com o cadastro antes de abrir a campanha. A cobrança do
  adicional só começa depois dessa confirmação.</li>
  <li>O anonimato não muda: cada pessoa responde em um único grupo, e os mínimos da seção 7
  continuam valendo.</li>
  <li>O resultado de cada função descreve condições de trabalho e não pode ser usado como
  avaliação de desempenho ou de conduta de quem a ocupa (cláusula 2.3 do Contrato).</li>
  <li>Para contratar, a planilha da seção 4 ganha uma aba “Funções”: função, estabelecimento e
  número de pessoas.</li>
</ul>
<table>
<tr><th>Adicional</th><th class="n">Cálculo</th><th class="n">Valor mensal</th></tr>
<tr><td>{e(leitura_governanca.NOME)}</td><td class="n">{e(adicional['percentual'])}% sobre {e(r['mensal'])}</td><td class="n">{e(adicional['mensal'])}</td></tr>
<tr class="total"><td>Total mensal com o adicional</td><td class="n"></td><td class="n">{e(adicional['total_com_adicional'])}</td></tr>
</table>
<p class="mini">Não é necessário para cumprir a NR-1: o escopo desta proposta atende à norma
sozinho. O adicional não está incluído no total da tabela anterior e só é cobrado por quem o
contratar, a partir da confirmação da condição acima.</p>
</div>"""
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Proposta {e(r['numero'])} — {e(r['empresa'])} — FROID NR-1</title>
<style>
:root {{ --noite:#060b1d; --azul:#2563eb; --tinta:#0f172a; --cinza:#475569; --linha:#e2e8f0; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#eef2f7; color:var(--tinta); font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
.folha {{ max-width:860px; margin:24px auto; background:#fff; box-shadow:0 2px 18px rgba(15,23,42,.08); }}
.topo {{ background:var(--noite); color:#fff; padding:26px 44px 22px; display:flex; align-items:center; justify-content:space-between; gap:24px; }}
.topo img {{ height:46px; display:block; }}
.topo .id {{ text-align:right; font-size:13px; color:#cbd5e1; }}
.topo .id b {{ color:#fff; font-size:15px; }}
.corpo {{ padding:30px 44px 40px; }}
h1 {{ font-size:24px; line-height:1.2; margin:0 0 4px; }}
.sub {{ color:var(--cinza); margin:0 0 22px; }}
h2 {{ font-size:17px; margin:30px 0 8px; padding-bottom:4px; border-bottom:2px solid var(--azul); }}
h3 {{ font-size:15px; margin:18px 0 6px; }}
.partes {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; background:#f8fafc; border:1px solid var(--linha); border-radius:8px; padding:14px 18px; }}
.partes p {{ margin:0; }} .partes small {{ color:var(--cinza); text-transform:uppercase; letter-spacing:.06em; font-size:11px; }}
table {{ width:100%; border-collapse:collapse; margin:8px 0; font-size:14px; }}
th {{ text-align:left; background:#0b1f44; color:#fff; font-weight:600; padding:7px 10px; }}
td {{ border-bottom:1px solid var(--linha); padding:7px 10px; vertical-align:top; }}
td.n {{ text-align:right; white-space:nowrap; }}
tr.total td {{ font-weight:700; border-top:2px solid var(--tinta); }}
.gratis {{ border:1.5px solid #059669; background:#ecfdf5; color:#064e3b; border-radius:8px; padding:12px 16px; margin:14px 0; }}
.alerta {{ border-left:3px solid #d97706; background:#fffbeb; padding:8px 12px; }}
.nao {{ color:var(--cinza); }}
.adicional {{ border:1.5px solid var(--azul); background:#eff6ff; border-radius:8px; padding:4px 16px 10px; margin:16px 0; }}
ul, ol {{ padding-left:22px; }} li {{ margin-bottom:4px; }}
code {{ font-size:12px; word-break:break-all; }}
.mini {{ font-size:12px; color:var(--cinza); }}
.assinatura {{ display:grid; grid-template-columns:1fr 1fr; gap:28px; margin-top:26px; }}
.assinatura div {{ border-top:1px solid var(--tinta); padding-top:6px; font-size:13px; }}
.acoes {{ max-width:860px; margin:16px auto 0; text-align:right; }}
.acoes button {{ font:inherit; background:var(--azul); color:#fff; border:0; border-radius:999px; padding:9px 18px; cursor:pointer; }}
@media (max-width:640px) {{ .topo, .corpo {{ padding-left:20px; padding-right:20px; }} .partes, .assinatura {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:#fff; }} .folha {{ margin:0; box-shadow:none; max-width:none; }} .acoes {{ display:none; }}
  .topo {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }} th, .gratis {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  h2 {{ break-after:avoid; }} tr, .gratis, .partes {{ break-inside:avoid; }} }}
</style></head>
<body>
<div class="acoes"><button type="button" onclick="window.print()">Salvar em PDF ou imprimir</button></div>
<article class="folha">
<header class="topo">
  <img src="/site-assets/img/froid-logo.png" alt="FROID — Frequency Recognition of Internal Dynamics">
  <div class="id"><b>Proposta nº {e(r['numero'])}</b><br>Emitida em {_data(r['emitida_em'])}<br>Válida até {_data(r['valida_ate'])}</div>
</header>
<div class="corpo">
<h1>Proposta de execução — avaliação dos riscos psicossociais (NR-1)</h1>
<p class="sub">Camada psicossocial do GRO/PGR, conforme o capítulo 1.5 da NR-1.</p>

<div class="partes">
  <p><small>Contratante</small><br><b>{e(r['empresa'])}</b><br>CNPJ {e(formatar_cnpj(r['cnpj']))}<br>A/C {ac}</p>
  <p><small>Dimensionamento informado</small><br><b>{estab}</b><br><b>{trab}</b><br>Confirmado na reunião de dimensionamento.</p>
</div>

<h2>1. O que propomos</h2>
<p>Executar, em {estab} da {e(r['empresa'])}, com {trab}, a avaliação dos fatores de riscos
psicossociais relacionados ao trabalho que a NR-1 exige no GRO/PGR: identificar, avaliar e
classificar os fatores, entregar o inventário de riscos, o plano de ação, a AEP e o documento
de critérios, e reavaliar depois das medidas para comprovar se o risco de fato diminuiu.</p>
<p>O resultado não é uma pesquisa com relatório. É uma trilha que pode ser auditada entre o
risco identificado, a providência adotada e o resultado verificado depois.</p>

<h2>2. O que a fiscalização examina</h2>
<p>Desde 26 de maio de 2026 a gestão dos riscos psicossociais é exigível no GRO (Portaria MTE
nº 1.419/2024). A norma não pede diagnóstico de saúde mental de cada empregado: pede que a
empresa demonstre o processo. Na prática, o auditor examina:</p>
<ul>
  <li>inventário de riscos e plano de ação com responsável e prazo;</li>
  <li>evidências de que as medidas foram implementadas;</li>
  <li>registro da participação dos trabalhadores (item 1.5.3.3);</li>
  <li>coerência entre o documento e a realidade da empresa;</li>
  <li>reavaliação ao menos a cada dois anos e correção das medidas ineficazes.</li>
</ul>
<p>Em ações por adoecimento relacionado ao trabalho, o PGR pode ser requisitado como prova.</p>

<h2>3. Escopo</h2>
<h3>Incluído</h3>
<ul>
  <li>Definição dos recortes de avaliação (unidade, setor, nível hierárquico ou cruzados) e verificação do grupo mínimo de cada um.</li>
  <li>Campanhas de avaliação ilimitadas, com questionário que cobre os fatores do Guia do MTE, aplicadas na mesma janela a todos os recortes.</li>
  <li>Acompanhamento da adesão durante a coleta, sem acesso a respostas individuais.</li>
  <li>Classificação dos fatores por severidade e probabilidade, na matriz já usada no PGR da {e(r['empresa'])} quando houver.</li>
  <li>Os documentos da seção 6 e a reunião de devolutiva à diretoria.</li>
  <li>Reavaliação dos recortes com risco moderado, alto ou crítico, para comprovar a eficácia das medidas ou a necessidade de corrigi-las.</li>
  <li>Acesso à plataforma para registrar providências, responsáveis e prazos durante a vigência.</li>
</ul>
<h3 class="nao">Não incluído</h3>
<ul class="nao">
  <li>Execução das medidas de prevenção e avaliação presencial em campo.</li>
  <li>Demais riscos do PGR (físicos, químicos, biológicos e de acidentes), SESMT, CIPA, PCMSO, assessoria jurídica e atendimento psicológico.</li>
</ul>
<p>O FROID avalia de forma independente se as ações da empresa ou de seus prestadores produziram efeito; não substitui nenhum deles.</p>

<h2>4. Como nos enviar as informações</h2>
<p>Para começar, precisamos de três conjuntos de informações. Os dois primeiros vêm numa
planilha (.xlsx ou .csv) enviada por e-mail a <b>froid@froid.com.br</b>, com o assunto
<b>“Proposta {e(r['numero'])} — dados para início”</b>. O terceiro não passa pelo FROID.</p>

<h3>4.1 Aba “Estabelecimentos” — uma linha por endereço</h3>
<table>
<tr><th>Coluna</th><th>O que preencher</th></tr>
<tr><td>Estabelecimento</td><td>Nome usado internamente (ex.: “Loja Centro”, “Fábrica 2”).</td></tr>
<tr><td>CNPJ</td><td>CNPJ do estabelecimento, quando for filial com CNPJ próprio.</td></tr>
<tr><td>Endereço</td><td>Logradouro, número, bairro, cidade, UF e CEP.</td></tr>
<tr><td>Efetivo</td><td>Número de trabalhadores lotados ali.</td></tr>
</table>

<h3>4.2 Aba “Setores” — uma linha por setor de cada estabelecimento</h3>
<table>
<tr><th>Coluna</th><th>O que preencher</th></tr>
<tr><td>Estabelecimento</td><td>Exatamente o mesmo nome usado na aba anterior.</td></tr>
<tr><td>Setor</td><td>Nome do setor como aparece na folha de pagamento.</td></tr>
<tr><td>Efetivo</td><td>Número de trabalhadores do setor.</td></tr>
<tr><td>Atividade e jornada</td><td>Uma frase sobre o trabalho realizado e o regime de turnos.</td></tr>
</table>
<p class="mini">A soma dos efetivos dos setores deve fechar com o efetivo do estabelecimento.
Setor com menos de {piso_recorte} trabalhadores é agregado ao nível imediatamente acima,
porque nenhum resultado é exibido para recorte menor que isso.</p>

<h3>4.3 Lista de trabalhadores — só matrícula e setor, lançada pela própria empresa</h3>
<p>Na abertura de cada campanha, o RH cola no painel do FROID uma lista com duas colunas,
<b>matrícula</b> e <b>setor</b>, copiada da planilha da folha. A plataforma gera um link
individual de questionário para cada matrícula, e o RH os distribui pelos canais que já usa.
<b>Não envie ao FROID nome, CPF, e-mail, telefone ou qualquer dado de saúde dos trabalhadores:</b>
eles não são necessários e não são aceitos.</p>

<h3>4.4 Junto com a planilha</h3>
<ul>
  <li>Nome e contato do responsável interno pelo projeto e do responsável técnico (SESMT ou consultoria de SST).</li>
  <li>O canal de apoio ao trabalhador (nome e contato), real, acessível e sigiloso. Sem ele a plataforma não abre campanha.</li>
  <li>A matriz de risco e os critérios de gradação do PGR atual, se houver.</li>
  <li>Indicadores que queira cruzar com o resultado (rotatividade, absenteísmo, afastamentos, denúncias), opcional.</li>
  <li>O encarregado de dados (DPO), quando houver.</li>
</ul>

<h2>5. Etapas e prazos</h2>
<table>
<tr><th>Etapa</th><th>Prazo estimado</th><th>Depende de</th></tr>
<tr><td>Dimensionamento e cadastro da estrutura</td><td>Semanas 1–2</td><td>Informações da seção 4 completas</td></tr>
<tr><td>Comunicação aos trabalhadores (modelo fornecido pelo FROID)</td><td>Semana 2</td><td>Canal de apoio definido</td></tr>
<tr><td>Coleta</td><td>Semanas 3–4</td><td>Adesão mínima por recorte</td></tr>
<tr><td>Análise, documentos e devolutiva</td><td>Semanas 5–6</td><td>Encerramento da coleta</td></tr>
<tr><td>Medidas de prevenção (pela empresa)</td><td>Conforme o plano de ação</td><td>Decisão da diretoria</td></tr>
<tr><td>Reavaliação dos recortes priorizados</td><td>Em geral 3 a 6 meses depois</td><td>Providências registradas</td></tr>
</table>
<p class="mini">Os prazos são confirmados na reunião de dimensionamento.</p>

<h2>6. Documentos entregues</h2>
<table>
<tr><th>Documento</th><th>Conteúdo</th></tr>
<tr><td>AEP — Avaliação Ergonômica Preliminar</td><td>Por unidade avaliada: condições reais de trabalho, exposição, evidências e responsável.</td></tr>
<tr><td>Inventário de riscos</td><td>Fatores avaliados, grupos expostos, medidas existentes e classificação.</td></tr>
<tr><td>Plano de ação</td><td>Medidas, responsáveis, cronograma e forma de aferição (estrutura entregue; preenchido pela empresa).</td></tr>
<tr><td>Documento de critérios</td><td>Gradações de severidade e probabilidade, matriz, níveis de risco e regras de decisão.</td></tr>
<tr><td>Histórico de eficácia</td><td>Sequência entre risco identificado, ação realizada e resultado verificado, atualizada a cada campanha.</td></tr>
</table>

<h2>7. Anonimato e proteção de dados</h2>
<p>Nenhum resultado é exibido para recorte com menos de {piso_recorte} respondentes nem para
campanha com menos de {piso_campanha} respostas concluídas. Quando a evidência é insuficiente,
o sistema registra a insuficiência em vez de concluir por baixo risco. A empresa não recebe
respostas individuais nem resultados parciais que permitam identificar alguém: a avaliação
trata de condições de trabalho, não de pessoas. O tratamento tem como base o cumprimento de
obrigação legal do empregador decorrente da NR-1.</p>
{porte}
<h2>8. Investimento</h2>
<table>
<tr><th>Componente</th><th class="n">Cálculo</th><th class="n">Valor mensal</th></tr>
<tr><td>Base da plataforma</td><td class="n">{_n(r['estabelecimentos'])} × {e(r['base_por_estabelecimento'])}</td><td class="n">{e(r['base_subtotal'])}</td></tr>
{linhas_faixa}
<tr class="total"><td>Total mensal</td><td class="n">{e(r['por_trabalhador'])} por trabalhador</td><td class="n">{e(r['mensal'])}</td></tr>
</table>
<p class="mini">As faixas são cumulativas sobre o efetivo total. Campanhas ilimitadas, sem
cobrança por setor nem por reavaliação. Doze meses: {e(r['anual'])}.</p>
<div class="gratis"><b>Sem custo até a entrega do primeiro relatório.</b> Nada é cobrado até a
entrega do primeiro relatório de avaliação dos riscos psicossociais. A mensalidade acima passa a
ser cobrada a partir do mês seguinte a essa entrega.</div>
<ul>
  <li>Vigência: {VIGENCIA_MESES} meses a partir do aceite.</li>
  <li>Faturamento mensal. Data de vencimento e índice de reajuste são definidos no contrato.</li>
</ul>
{governanca}
<p class="mini">Valores calculados em {_data(r['emitida_em'])} pela tabela {e(tabela['codigo'])},
versão {e(tabela['versao'])}, vigente desde {_data(tabela['vigente_desde'])}
(digital <code>{e(tabela['sha256'])}</code>).</p>

<h2>9. Validade e aceite</h2>
<p>Esta proposta vale até {_data(r['valida_ate'])}. O aceite pode ser dado por assinatura abaixo
ou respondendo por e-mail a froid@froid.com.br, e dá início à etapa de dimensionamento.</p>
<div class="assinatura">
  <div>De acordo — {e(r['empresa'])}<br>Nome e cargo:<br><br>Data: ____/____/______</div>
  <div>FROID<br>froid@froid.com.br</div>
</div>
</div>
</article>
</body></html>"""
