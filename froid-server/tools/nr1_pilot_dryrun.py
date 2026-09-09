"""Piloto do módulo NR-1 com uma empresa de teste.

Monta uma organização `enterprise` fictícia, aplica o instrumento FROID,
simula respostas suficientes para cruzar o piso de coorte, encerra a coleta e
exercita gradação, inventário e comparação de eficácia contra o banco real.

O que este roteiro NÃO faz, por desenho:

  * não lê, escreve ou apaga qualquer registro de paciente, sessão, relatório,
    consentimento ou carteira. Toca exclusivamente as tabelas do módulo NR-1
    mais uma única linha em `organizations`, criada por ele;
  * não usa dados de pessoas reais. Todas as respostas são geradas por um
    gerador determinístico com semente fixa, para que duas execuções produzam
    exatamente o mesmo resultado e a conferência seja possível;
  * não deixa resíduo. `--destroy` remove tudo o que `--create` criou, e nada
    além disso.

Uso, de dentro do contêiner do backend:

    python tools/nr1_pilot_dryrun.py --create
    python tools/nr1_pilot_dryrun.py --report
    python tools/nr1_pilot_dryrun.py --destroy
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import nr1_compliance  # noqa: E402
import nr1_effectiveness  # noqa: E402


# Namespace fixo: tudo o que o piloto cria deriva deste identificador, então a
# remoção é exata e não depende de o operador lembrar de nada.
PILOT_NAMESPACE = uuid.UUID("f01d0000-0000-4000-8000-000000000001")
ORG_ID = str(uuid.uuid5(PILOT_NAMESPACE, "organization"))
ORG_LEGAL_NAME = "FROID NR-1 Piloto 01 — DADOS SIMULADOS"
ORG_DISPLAY_NAME = "FROID NR-1 Piloto 01 — DADOS SIMULADOS"

# O nome ja foi outro, e a remocao confere o nome antes de apagar.
#
# `destroy` exige `legal_name = ORG_LEGAL_NAME` como trava: e o que impede o
# script de apagar uma organizacao real que por acaso tivesse o mesmo id. Mas
# renomear a constante sem lembrar disso deixaria orfa qualquer organizacao
# criada com o nome anterior — o --destroy nao a encontraria, e o piloto ficaria
# no banco para sempre, com nome de demonstracao, na lista de um cliente.
NOMES_ANTERIORES = (
    "EMPRESA TESTE FROID — PILOTO NR-1 (REMOVER)",
    "FROID NR-1 Piloto 01",
)
# A agregação exige vínculo ativo (froid_membership_is_active), então o piloto
# precisa de um usuário e um vínculo próprios. São criados com e-mail que não
# existe e removidos no --destroy. É a única incursão fora das tabelas do NR-1.
PILOT_USER_ID = str(uuid.uuid5(PILOT_NAMESPACE, "user"))
PILOT_USER_EMAIL = "piloto-nr1@teste.invalid"
MEMBERSHIP_ID = str(uuid.uuid5(PILOT_NAMESPACE, "membership"))
UNIT_ATENDIMENTO = str(uuid.uuid5(PILOT_NAMESPACE, "unit/atendimento"))
UNIT_LOGISTICA = str(uuid.uuid5(PILOT_NAMESPACE, "unit/logistica"))
CRITERIA_ID = str(uuid.uuid5(PILOT_NAMESPACE, "criteria"))
CAMPAIGN_BASE = str(uuid.uuid5(PILOT_NAMESPACE, "campaign/baseline"))
CAMPAIGN_FOLLOW = str(uuid.uuid5(PILOT_NAMESPACE, "campaign/followup"))


def pilot_id(name: str) -> str:
    """Identificador estável para que completar o piloto seja idempotente."""
    return str(uuid.uuid5(PILOT_NAMESPACE, name))

INSTRUMENT_CODE = "froid-nr1-psicossocial"
INSTRUMENT_VERSION = "1.0"

# População simulada por unidade. Acima do piso total (50) e do piso por
# recorte (10), para que os dois sejam exercitados de verdade.
POPULATION = {UNIT_ATENDIMENTO: 64, UNIT_LOGISTICA: 22}

RESET = "\033[0m"
BOLD = "\033[1m"


def paint(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"


def connect():
    dsn = os.getenv("FROID_DATABASE_URL", "").strip()
    if not dsn:
        raise SystemExit(
            "FROID_DATABASE_URL não está definido. Rode dentro do contêiner do "
            "backend, onde a variável existe."
        )
    import psycopg

    return psycopg.connect(dsn, connect_timeout=15)


def ensure_migrations() -> None:
    """Garante que o schema esteja em dia antes de qualquer coisa.

    `ensure_schema()` é preguiçoso: no processo do servidor ele só dispara na
    primeira operação de tenant, tipo um login. Depois de um deploy pode levar
    horas até isso acontecer, e uma migration nova fica no limbo sem ninguém
    perceber. Aqui a chamada é explícita, e é idempotente — o que já está
    aplicado é ignorado.
    """
    from tenant_store import TenantStore

    store = TenantStore.from_env()
    if not store.enabled:
        raise SystemExit(
            "FROID_PERSISTENCE_MODE não está em 'dual'. O piloto precisa do "
            "espelho em PostgreSQL ativo."
        )
    store.ensure_schema()
    print("Schema conferido: migrations pendentes aplicadas.")


def instrument_of(connection):
    row = connection.execute(
        """
        SELECT id, scale_min, scale_max FROM assessment_instruments
        WHERE code=%s AND version=%s
        """,
        (INSTRUMENT_CODE, INSTRUMENT_VERSION),
    ).fetchone()
    if not row:
        raise SystemExit(
            "Instrumento FROID v1 não encontrado mesmo após aplicar as "
            "migrations. Verifique se 015_nr1_instrument_froid_v1.sql chegou "
            "ao servidor: git log --oneline -1"
        )
    return {"id": row[0], "scale_min": int(row[1]), "scale_max": int(row[2])}


def dimensions_of(connection, instrument_id):
    rows = connection.execute(
        """
        SELECT d.id, d.code, d.title, d.polarity, d.nr1_factor,
               array_agg(i.id ORDER BY i.display_order)
        FROM assessment_dimensions d
        JOIN assessment_items i ON i.dimension_id = d.id
        WHERE d.instrument_id=%s
        GROUP BY d.id, d.code, d.title, d.polarity, d.nr1_factor, d.display_order
        ORDER BY d.display_order
        """,
        (instrument_id,),
    ).fetchall()
    return [
        {
            "id": row[0], "code": row[1], "title": row[2],
            "polarity": row[3], "factor": row[4], "items": row[5],
        }
        for row in rows
    ]


def answer_for(rng, dimension, unit_id, wave):
    """Resposta simulada para um item, na escala 1..5.

    O cenário é montado para produzir um resultado interpretável:

      * Atendimento tem sobrecarga alta na linha de base e melhora na segunda
        onda — é o caso que deve sair como "medida eficaz".
      * Assédio piora entre as ondas — deve sair como "piorou" e entrar para
        correção.
      * As demais dimensões oscilam pouco, dentro do ruído — devem sair como
        "sem mudança", que é o veredito mais importante de conferir, porque é
        onde todo concorrente declararia sucesso.
    """
    code = dimension["code"]
    protective = dimension["polarity"] == "protective"

    if unit_id == UNIT_ATENDIMENTO and code == "sobrecarga":
        centro = 4.4 if wave == "baseline" else 2.9
    elif unit_id == UNIT_ATENDIMENTO and code == "assedio":
        centro = 1.8 if wave == "baseline" else 3.1
    elif protective:
        centro = 3.6 if wave == "baseline" else 3.7
    else:
        centro = 2.4 if wave == "baseline" else 2.35

    valor = round(rng.gauss(centro, 0.9))
    return max(1, min(5, valor))


def create(connection) -> None:
    instrument = instrument_of(connection)
    dimensions = dimensions_of(connection, instrument["id"])
    print(f"Instrumento: {len(dimensions)} dimensões, "
          f"{sum(len(d['items']) for d in dimensions)} itens.")

    connection.execute(
        """
        INSERT INTO organizations (id, organization_type, legal_name, display_name, status)
        VALUES (%s, 'enterprise', %s, %s, 'active')
        -- Renomear a constante tem de renomear a organizacao ja criada:
        -- senao a primeira execucao fixa o nome e as seguintes so parecem
        -- funcionar.
        ON CONFLICT (id) DO UPDATE SET
            organization_type='enterprise',
            legal_name=EXCLUDED.legal_name,
            display_name=EXCLUDED.display_name
        """,
        (ORG_ID, ORG_LEGAL_NAME, ORG_DISPLAY_NAME),
    )
    connection.execute(
        """
        INSERT INTO users (id, email, display_name, status)
        VALUES (%s,%s,%s,'active') ON CONFLICT (id) DO NOTHING
        """,
        (PILOT_USER_ID, PILOT_USER_EMAIL, "Piloto NR-1"),
    )
    connection.execute(
        """
        INSERT INTO organization_memberships
            (id, organization_id, user_id, status, joined_at)
        VALUES (%s,%s,%s,'active',now()) ON CONFLICT (id) DO NOTHING
        """,
        (MEMBERSHIP_ID, ORG_ID, PILOT_USER_ID),
    )
    for papel in ("compliance_manager", "occupational_health"):
        connection.execute(
            "INSERT INTO membership_roles (membership_id, role) VALUES (%s,%s) "
            "ON CONFLICT DO NOTHING",
            (MEMBERSHIP_ID, papel),
        )

    for unit_id, (nome, headcount) in {
        UNIT_ATENDIMENTO: ("Atendimento ao cliente", POPULATION[UNIT_ATENDIMENTO]),
        UNIT_LOGISTICA: ("Logística", POPULATION[UNIT_LOGISTICA]),
    }.items():
        connection.execute(
            """
            INSERT INTO organization_units
                (id, organization_id, unit_type, name, headcount, status)
            VALUES (%s,%s,'sector',%s,%s,'active')
            ON CONFLICT (id) DO NOTHING
            """,
            (unit_id, ORG_ID, nome, headcount),
        )

    criteria = nr1_compliance.DEFAULT_CRITERIA.as_document()
    connection.execute(
        """
        INSERT INTO gro_risk_criteria
            (id, organization_id, version, severity_scale, probability_scale,
             risk_matrix, classification_rules, decision_rules,
             consequence_magnitudes, published_at)
        VALUES (%s,%s,1,%s::jsonb,%s::jsonb,%s::jsonb,
                %s::jsonb,%s::jsonb,%s::jsonb, now())
        ON CONFLICT (id) DO NOTHING
        """,
        (
            CRITERIA_ID, ORG_ID,
            _json(criteria["severity_scale"]), _json(criteria["probability_scale"]),
            _json(criteria["risk_matrix"]), _json({"base": "NR-1 1.5.4.4.3"}),
            _json({"base": "NR-1 1.5.5.2.1.1"}),
            _json(criteria["consequence_magnitudes"]),
        ),
    )

    agora = datetime.now(timezone.utc)
    for campaign_id, titulo, wave, inicio_ha, fim_ha in (
        (CAMPAIGN_BASE, "FROID NR-1 Piloto 1 — linha de base", "baseline", 210, 180),
        (CAMPAIGN_FOLLOW, "FROID NR-1 Piloto 1 — reavaliação", "followup", 30, 1),
    ):
        abertura = agora - timedelta(days=inicio_ha)
        encerramento = agora - timedelta(days=fim_ha)
        periodo = (
            f"Cenário demonstrativo: {abertura:%d/%m/%Y} a "
            f"{encerramento:%d/%m/%Y}"
        )
        connection.execute(
            """
            INSERT INTO assessment_campaigns
                (id, organization_id, instrument_id, title, opens_at, closes_at,
                 status, criteria_id, target_headcount, purpose_notice,
                 support_channel_label, support_channel_detail, reference_period)
            VALUES (%s,%s,%s,%s,%s,%s,'open',%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                title=EXCLUDED.title,
                opens_at=EXCLUDED.opens_at,
                closes_at=EXCLUDED.closes_at,
                criteria_id=EXCLUDED.criteria_id,
                target_headcount=EXCLUDED.target_headcount,
                purpose_notice=EXCLUDED.purpose_notice,
                support_channel_label=EXCLUDED.support_channel_label,
                support_channel_detail=EXCLUDED.support_channel_detail,
                reference_period=EXCLUDED.reference_period
            """,
            (
                campaign_id, ORG_ID, instrument["id"], titulo,
                abertura, encerramento,
                CRITERIA_ID, sum(POPULATION.values()),
                "Demonstração do ciclo NR-1 com cenário empresarial inteiramente fictício.",
                "Acolhimento demonstrativo",
                "Em uma operação real, este campo informa o canal independente de apoio.",
                periodo,
            ),
        )
        _simulate_wave(connection, campaign_id, dimensions, wave)
        connection.execute(
            "UPDATE assessment_campaigns SET status='closed', closed_at=closes_at WHERE id=%s",
            (campaign_id,),
        )
        print(f"Campanha '{titulo}': respostas simuladas e coleta encerrada.")

    complete_cycle(connection, dimensions)


def _aep_text(unit_id: str, wave: str) -> dict:
    """Quatro narrativas coerentes, todas reconhecíveis como cenário fictício."""
    if unit_id not in POPULATION or wave not in {"baseline", "followup"}:
        raise ValueError("unidade ou onda fora do cenário demonstrativo")
    if unit_id == UNIT_ATENDIMENTO and wave == "baseline":
        return {
            "reference_period": "DEMONSTRAÇÃO — linha de base fictícia, sem validade documental.",
            "real_work_description": (
                "Cenário fictício: 64 atendentes alternam voz, chat e e-mail em filas "
                "simultâneas. Em campanhas comerciais, a prioridade muda durante o "
                "turno; metas de tempo, qualidade e retenção competem entre si, e pausas "
                "são negociadas com a supervisão conforme o tamanho da fila."
            ),
            "exposure_duration": (
                "Hipótese do piloto: blocos contínuos de atendimento ocupam a maior "
                "parte da jornada, intercalados por pausas curtas e troca de canal."
            ),
            "exposure_frequency": (
                "Premissa demonstrativa: picos aparecem diariamente na abertura, no "
                "horário de almoço e após comunicações promocionais."
            ),
            "exposure_intensity": (
                "Leitura simulada: sobrecarga elevada quando filas crescem e o atendente "
                "precisa resolver a demanda sem autonomia para exceções."
            ),
            "exposure_cofactors": (
                "Elementos fictícios do cenário: ruído da operação, mensagens "
                "contraditórias, clientes hostis, monitoramento em tempo real e apoio "
                "desigual entre supervisores."
            ),
            "health_indicators": (
                "Indicadores demonstrativos sugerem relatos coletivos de tensão ao fim "
                "do turno e dificuldade de recuperação após dias de pico; nenhum dado "
                "clínico individual foi utilizado."
            ),
            "absenteeism_notes": (
                "Padrão hipotético: ausências breves se concentram após campanhas de "
                "alto volume. A demonstração não atribui causa nem informa quantidade real."
            ),
            "previous_assessments": (
                "Histórico demonstrativo: primeira medição estruturada deste setor; não "
                "há resultado anterior usado como substituto."
            ),
            "responsible_name": "DEMONSTRAÇÃO — Marina Lopes (personagem fictícia)",
            "responsible_qualification": "Papel simulado: coordenação de SST da empresa-piloto",
            "aet_required": True,
            "aet_justification": (
                "Decisão demonstrativa: aprofundar a análise de filas, metas concorrentes, "
                "margem de decisão e recuperação entre atendimentos."
            ),
        }
    if unit_id == UNIT_ATENDIMENTO:
        return {
            "reference_period": "DEMONSTRAÇÃO — reavaliação fictícia, sem validade documental.",
            "real_work_description": (
                "Cenário fictício de reavaliação: o roteamento passou a separar demandas "
                "simples e complexas, reforços cobrem horários de pico e micro-pausas são "
                "programadas. A carga caiu, mas o novo escalonamento de clientes agressivos "
                "funciona de modo desigual e expõe parte da equipe a conflitos repetidos."
            ),
            "exposure_duration": (
                "Hipótese pós-medida: os picos ficaram mais curtos, enquanto interações "
                "hostis ainda podem ocupar todo o atendimento até a chegada da supervisão."
            ),
            "exposure_frequency": (
                "Premissa da segunda onda: pressão por volume permanece diária; episódios "
                "de desrespeito aparecem de forma intermitente e sem resposta uniforme."
            ),
            "exposure_intensity": (
                "Leitura agregada simulada: melhora expressiva de excesso de demandas e "
                "agravamento de assédio, combinação que exige medidas diferentes."
            ),
            "exposure_cofactors": (
                "Cofatores hipotéticos: treinamento desigual de líderes, transferência "
                "tardia de chamadas críticas e cobrança de retenção durante conflitos."
            ),
            "health_indicators": (
                "Painel demonstrativo: diminuem referências coletivas a exaustão por fila, "
                "enquanto aumentam pedidos de apoio após interação ofensiva."
            ),
            "absenteeism_notes": (
                "Registro cenográfico: o padrão de ausências não permite conclusão; no "
                "caso real, RH e PCMSO precisariam validar tendência e nexo."
            ),
            "previous_assessments": (
                "Comparação demonstrativa: usa a linha de base fictícia da mesma unidade, "
                "instrumento e recorte, preservando comparabilidade."
            ),
            "responsible_name": "DEMONSTRAÇÃO — Marina Lopes (personagem fictícia)",
            "responsible_qualification": "Papel simulado: coordenação de SST da empresa-piloto",
            "aet_required": True,
            "aet_justification": (
                "Decisão demonstrativa: manter o aprofundamento e observar o protocolo de "
                "escalonamento, pois o risco crítico de assédio piorou na segunda onda."
            ),
        }
    if wave == "baseline":
        return {
            "reference_period": "DEMONSTRAÇÃO — linha de base logística fictícia, sem validade documental.",
            "real_work_description": (
                "Cenário fictício: 22 trabalhadores recebem, separam e expedem pedidos, "
                "com reprogramações urgentes no fechamento de carga. A passagem entre "
                "turnos ocorre por rádio e quadro de doca, e motoristas aguardam liberação "
                "em área compartilhada com a conferência."
            ),
            "exposure_duration": (
                "Hipótese do piloto: alternância durante todo o turno entre separação "
                "planejada e janelas curtas de carregamento."
            ),
            "exposure_frequency": (
                "Premissa demonstrativa: urgências concentram-se no fim de cada janela de "
                "expedição e nas trocas de turno."
            ),
            "exposure_intensity": (
                "Leitura simulada: exigência moderada na rotina, com elevação súbita diante "
                "de atraso, divergência de pedido ou bloqueio de doca."
            ),
            "exposure_cofactors": (
                "Elementos fictícios: comunicação por canais paralelos, iluminação variável, "
                "ruído, espera de terceiros e responsabilidade pouco clara por exceções."
            ),
            "health_indicators": (
                "Indicadores demonstrativos mencionam fadiga no fechamento e tensão em "
                "situações de divergência; não há prontuários ou diagnósticos no piloto."
            ),
            "absenteeism_notes": (
                "Padrão hipotético: não foi formada tendência confiável de ausências; a "
                "lacuna permanece declarada em vez de preenchida com zero."
            ),
            "previous_assessments": (
                "Histórico demonstrativo: inspeções operacionais anteriores não continham "
                "avaliação psicossocial comparável."
            ),
            "responsible_name": "DEMONSTRAÇÃO — Rafael Nunes (personagem fictício)",
            "responsible_qualification": "Papel simulado: engenharia de segurança da empresa-piloto",
            "aet_required": False,
            "aet_justification": (
                "Decisão demonstrativa inicial: acompanhar a atividade e reavaliar antes de "
                "escalonar; nenhuma dispensa real de AET é produzida por este piloto."
            ),
        }
    return {
        "reference_period": "DEMONSTRAÇÃO — reavaliação logística fictícia, sem validade documental.",
        "real_work_description": (
            "Cenário fictício de reavaliação: o quadro de doca foi padronizado e a passagem "
            "de turno ganhou conferência conjunta. Persistem reprogramações de última hora; "
            "um episódio encenado de ameaça durante uma divergência de entrega revelou que "
            "o protocolo de segurança e acolhimento ainda não está claro."
        ),
        "exposure_duration": (
            "Hipótese pós-medida: a pressão continua concentrada nas janelas de expedição; "
            "incidentes críticos são curtos, mas podem produzir impacto prolongado."
        ),
        "exposure_frequency": (
            "Premissa da segunda onda: reprogramações seguem semanais e conflitos são raros, "
            "porém plausíveis no cenário operacional."
        ),
        "exposure_intensity": (
            "Leitura agregada simulada: não há melhora estatisticamente demonstrável e a "
            "dimensão de eventos violentos permanece em prioridade crítica."
        ),
        "exposure_cofactors": (
            "Cofatores hipotéticos: acesso de terceiros, espera em doca, rádio congestionado, "
            "liderança fora do local e ausência de roteiro pós-incidente."
        ),
        "health_indicators": (
            "Painel demonstrativo registra procura espontânea por orientação após o episódio "
            "encenado; nenhuma informação identificada ou clínica integra o cenário."
        ),
        "absenteeism_notes": (
            "Registro cenográfico: não se atribui ausência ao episódio; uma operação real "
            "exigiria análise conjunta de RH, PCMSO e contexto de trabalho."
        ),
        "previous_assessments": (
            "Comparação demonstrativa: a linha de base logística fictícia é mantida como "
            "referência, sem trocar recorte ou instrumento."
        ),
        "responsible_name": "DEMONSTRAÇÃO — Rafael Nunes (personagem fictício)",
        "responsible_qualification": "Papel simulado: engenharia de segurança da empresa-piloto",
        "aet_required": True,
        "aet_justification": (
            "Decisão demonstrativa: aprofundar a análise do trabalho em doca, resposta a "
            "ameaças, suporte pós-incidente e coordenação com terceiros."
        ),
    }


def _graded_payload(risk) -> dict:
    row = asdict(risk)
    row.update(
        selected_consequence=risk.consequence,
        possible_harms=list(risk.consequences_considered),
        risk_classification=risk.risk_level,
    )
    return row


def _evidence_summaries(unit_id: str, wave: str) -> dict:
    """Evidências cenográficas que se completam, em vez de repetir um aviso."""
    if unit_id not in POPULATION or wave not in {"baseline", "followup"}:
        raise ValueError("unidade ou onda fora do cenário demonstrativo")
    if unit_id == UNIT_ATENDIMENTO and wave == "baseline":
        return {
            "questionnaire": (
                "Questionário fictício com 64 respostas agregadas: maior exigência em "
                "excesso de demandas e diferenças de apoio entre momentos do turno."
            ),
            "activity_observation": (
                "Observação encenada do atendimento multicanal: troca frequente de tela, "
                "fila visível, interrupções e negociação de pausas durante picos."
            ),
            "worker_dialogue": (
                "Roda de conversa simulada: o grupo associa desgaste à combinação de metas "
                "concorrentes, baixa autonomia para exceções e clientes hostis."
            ),
            "document_analysis": (
                "Documentos cenográficos examinados: escala, roteiro de qualidade, regra de "
                "pausas e fluxo de escalonamento; nenhum arquivo empresarial real foi usado."
            ),
        }
    if unit_id == UNIT_ATENDIMENTO:
        return {
            "questionnaire": (
                "Segunda onda fictícia com 64 respostas agregadas: queda consistente da "
                "sobrecarga e aumento do risco relacionado a assédio."
            ),
            "activity_observation": (
                "Revisita encenada: reforço nos picos e micro-pausas estão visíveis, mas "
                "chamadas ofensivas nem sempre recebem apoio imediato da supervisão."
            ),
            "worker_dialogue": (
                "Devolutiva simulada: a equipe reconhece melhora das filas e pede regra única "
                "para interromper interação abusiva sem prejuízo da meta."
            ),
            "document_analysis": (
                "Comparação cenográfica entre escalas e protocolos: o dimensionamento foi "
                "revisto; o procedimento de proteção diante de agressões permanece incompleto."
            ),
        }
    if wave == "baseline":
        return {
            "questionnaire": (
                "Questionário fictício com 22 respostas agregadas: pressão em janelas de "
                "expedição e fragilidade na comunicação de exceções."
            ),
            "activity_observation": (
                "Percurso encenado da doca: rádio, quadro de carga e orientação verbal podem "
                "divergir quando um pedido é reprogramado."
            ),
            "worker_dialogue": (
                "Diálogo simulado de turno: conferentes e expedição relatam dúvida sobre quem "
                "decide diante de atraso, avaria ou recusa de terceiros."
            ),
            "document_analysis": (
                "Peças demonstrativas analisadas: passagem de turno, checklist de doca e "
                "registro de ocorrência; nenhuma informação de empresa real foi anexada."
            ),
        }
    return {
        "questionnaire": (
            "Segunda onda fictícia com 22 respostas agregadas: variação dentro do ruído e "
            "prioridade crítica mantida para eventos violentos ou traumáticos."
        ),
        "activity_observation": (
            "Simulação na doca: o quadro reduziu desencontros, mas uma ameaça encenada mostrou "
            "demora para acionar liderança e retirar a equipe da exposição."
        ),
        "worker_dialogue": (
            "Debriefing fictício: trabalhadores pedem canal de emergência, autoridade clara "
            "para suspender a operação e acolhimento após incidente."
        ),
        "document_analysis": (
            "Auditoria cenográfica: checklist operacional atualizado, sem fluxo completo de "
            "resposta, comunicação e aprendizagem pós-incidente."
        ),
    }


def _store_inventory(connection, campaign_id: str, graded, aep_by_unit: dict) -> None:
    """Grava o mesmo resultado calculado pelo motor e o liga à AEP do ciclo."""
    for risk in graded:
        row = _graded_payload(risk)
        inventory_id = pilot_id(
            f"inventory/{campaign_id}/{risk.unit_id}/{risk.dimension_id}"
        )
        connection.execute(
            """
            INSERT INTO psychosocial_risk_inventory
                (id, organization_id, campaign_id, unit_id, dimension_id,
                 nr1_factor, cohort_size, mean_score, severity, probability,
                 risk_level, rationale, possible_harms, selected_consequence,
                 exposed_workers, measure_efficacy, exposure_level,
                 risk_classification, review_due_at, review_trigger,
                 criteria_id, aep_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    now() + interval '24 months','scheduled',%s,%s)
            ON CONFLICT (campaign_id, unit_id, dimension_id) DO UPDATE SET
                cohort_size=EXCLUDED.cohort_size,
                mean_score=EXCLUDED.mean_score,
                severity=EXCLUDED.severity,
                probability=EXCLUDED.probability,
                risk_level=EXCLUDED.risk_level,
                rationale=EXCLUDED.rationale,
                possible_harms=EXCLUDED.possible_harms,
                selected_consequence=EXCLUDED.selected_consequence,
                exposed_workers=EXCLUDED.exposed_workers,
                measure_efficacy=EXCLUDED.measure_efficacy,
                exposure_level=EXCLUDED.exposure_level,
                risk_classification=EXCLUDED.risk_classification,
                criteria_id=EXCLUDED.criteria_id,
                aep_id=EXCLUDED.aep_id,
                generated_at=now()
            """,
            (
                inventory_id, ORG_ID, campaign_id, risk.unit_id,
                risk.dimension_id, risk.nr1_factor, risk.cohort_size,
                risk.mean_score, risk.severity, risk.probability,
                risk.risk_level, risk.rationale, row["possible_harms"],
                risk.consequence, risk.exposed_workers, risk.measure_efficacy,
                risk.exposure_level, risk.risk_level, CRITERIA_ID,
                aep_by_unit[risk.unit_id],
            ),
        )


def _create_aep_documents(connection, campaign_id: str, wave: str) -> dict:
    aep_by_unit = {}
    unit_names = {
        UNIT_ATENDIMENTO: "Atendimento ao cliente",
        UNIT_LOGISTICA: "Logística",
    }
    for unit_id, unit_name in unit_names.items():
        aep_id = pilot_id(f"aep/{campaign_id}/{unit_id}")
        aep_by_unit[unit_id] = aep_id
        fields = _aep_text(unit_id, wave)
        evidence_date = (
            datetime.now(timezone.utc) - timedelta(days=185 if wave == "baseline" else 2)
        ).date()
        connection.execute(
            """
            INSERT INTO aep_assessments
                (id, organization_id, unit_id, criteria_id, reference_period,
                 status, real_work_description, exposure_duration,
                 exposure_frequency, exposure_intensity, exposure_cofactors,
                 health_indicators, absenteeism_notes, previous_assessments,
                 responsible_name, responsible_qualification,
                 responsible_membership_id, aet_required, aet_justification,
                 concluded_at)
            VALUES (%s,%s,%s,%s,%s,'in_progress',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,NULL)
            ON CONFLICT (id) DO UPDATE SET
                reference_period=EXCLUDED.reference_period,
                status='in_progress',
                real_work_description=EXCLUDED.real_work_description,
                exposure_duration=EXCLUDED.exposure_duration,
                exposure_frequency=EXCLUDED.exposure_frequency,
                exposure_intensity=EXCLUDED.exposure_intensity,
                exposure_cofactors=EXCLUDED.exposure_cofactors,
                health_indicators=EXCLUDED.health_indicators,
                absenteeism_notes=EXCLUDED.absenteeism_notes,
                previous_assessments=EXCLUDED.previous_assessments,
                responsible_name=EXCLUDED.responsible_name,
                responsible_qualification=EXCLUDED.responsible_qualification,
                aet_required=EXCLUDED.aet_required,
                aet_justification=EXCLUDED.aet_justification,
                updated_at=now()
            """,
            (
                aep_id, ORG_ID, unit_id, CRITERIA_ID,
                fields["reference_period"], fields["real_work_description"],
                fields["exposure_duration"], fields["exposure_frequency"],
                fields["exposure_intensity"], fields["exposure_cofactors"],
                fields["health_indicators"], fields["absenteeism_notes"],
                fields["previous_assessments"], fields["responsible_name"],
                fields["responsible_qualification"], MEMBERSHIP_ID,
                fields["aet_required"],
                fields["aet_justification"],
            ),
        )
        evidence = _evidence_summaries(unit_id, wave)
        for method, summary in evidence.items():
            evidence_id = pilot_id(f"aep-evidence/{aep_id}/{method}")
            connection.execute(
                """
                INSERT INTO aep_evidence
                    (id, organization_id, aep_id, method, campaign_id,
                     collected_on, collected_by, summary, evidence_reference)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    campaign_id=EXCLUDED.campaign_id,
                    collected_on=EXCLUDED.collected_on,
                    collected_by=EXCLUDED.collected_by,
                    summary=EXCLUDED.summary,
                    evidence_reference=EXCLUDED.evidence_reference
                """,
                (
                    evidence_id, ORG_ID, aep_id, method, campaign_id, evidence_date,
                    "Equipe FROID — exercício demonstrativo",
                    summary,
                    f"demo://{campaign_id}/{unit_id}/{method}",
                ),
            )
        connection.execute(
            """
            UPDATE aep_assessments
               SET status='concluded',
                   concluded_at=coalesce(concluded_at, now()),
                   updated_at=now()
             WHERE id=%s AND organization_id=%s
               AND EXISTS (SELECT 1 FROM aep_evidence WHERE aep_id=%s)
            """,
            (aep_id, ORG_ID, aep_id),
        )
    return aep_by_unit


def _store_effectiveness(connection, verdicts) -> None:
    verdict_labels = {
        "eliminated": "o cenário indica eliminação do perigo",
        "effective": "a melhora supera o ruído e sustenta eficácia",
        "partial": "há melhora parcial que ainda exige acompanhamento",
        "no_change": "a variação não se distingue do ruído da coorte",
        "worsened": "o cenário piorou e exige correção",
        "inconclusive": "os dados do cenário não permitem concluir",
    }
    for verdict in verdicts:
        review_id = pilot_id(
            f"effectiveness/{CAMPAIGN_FOLLOW}/{verdict.unit_id}/{verdict.dimension_id}"
        )
        action_id = pilot_id(
            f"action/{CAMPAIGN_BASE}/{verdict.unit_id}/{verdict.dimension_id}"
        )
        connection.execute(
            """
            INSERT INTO measure_effectiveness_reviews
                (id, organization_id, unit_id, dimension_id, action_plan_id,
                 baseline_campaign_id, followup_campaign_id, baseline_cohort,
                 followup_cohort, baseline_mean, followup_mean, effect_size,
                 verdict, measure_efficacy, requires_correction, rationale)
            VALUES (%s,%s,%s,%s,
                    (SELECT plan.id FROM psychosocial_action_plan plan
                      WHERE plan.id=%s AND plan.organization_id=%s),
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (followup_campaign_id, unit_id, dimension_id) DO UPDATE SET
                baseline_cohort=EXCLUDED.baseline_cohort,
                followup_cohort=EXCLUDED.followup_cohort,
                baseline_mean=EXCLUDED.baseline_mean,
                followup_mean=EXCLUDED.followup_mean,
                effect_size=EXCLUDED.effect_size,
                verdict=EXCLUDED.verdict,
                measure_efficacy=EXCLUDED.measure_efficacy,
                requires_correction=EXCLUDED.requires_correction,
                rationale=EXCLUDED.rationale,
                reviewed_at=now()
            """,
            (
                review_id, ORG_ID, verdict.unit_id, verdict.dimension_id,
                action_id, ORG_ID, CAMPAIGN_BASE, CAMPAIGN_FOLLOW,
                verdict.baseline_cohort,
                verdict.followup_cohort, verdict.baseline_mean,
                verdict.followup_mean, verdict.effect_size, verdict.verdict,
                verdict.measure_efficacy, verdict.requires_correction,
                "Cenário demonstrativo: "
                + verdict_labels.get(verdict.verdict, verdict.verdict)
                + ". " + verdict.rationale,
            ),
        )
        connection.execute(
            """
            UPDATE psychosocial_action_plan plan
               SET effectiveness=%s, effectiveness_reviewed_at=now(),
                   evidence=evidence || %s
             WHERE plan.id=%s AND plan.organization_id=%s
            """,
            (
                verdict.measure_efficacy,
                " Reavaliação fictícia: "
                + verdict_labels.get(verdict.verdict, verdict.verdict)
                + ".",
                action_id, ORG_ID,
            ),
        )


def _action_plan_text(seed: dict, title: str, *, implemented: bool) -> dict:
    unit = "atendimento multicanal" if seed["unit_id"] == UNIT_ATENDIMENTO else "operação logística"
    action = {
        "introduce": "Introduzir",
        "improve": "Aprimorar",
        "maintain": "Manter",
    }.get(seed["plan_action"], "Revisar")
    measures = {
        "work_organization": (
            f"{action} regras de prioridade, passagem de responsabilidade e autonomia "
            f"para {title.lower()} na {unit}, com validação da equipe."
        ),
        "workload_demand": (
            f"{action} o balanceamento de capacidade, filas, pausas e limites de trabalho "
            f"simultâneo para reduzir {title.lower()} na {unit}."
        ),
        "harassment_violence": (
            f"{action} protocolo de interrupção segura, escalonamento imediato, registro e "
            f"acolhimento para situações de {title.lower()} na {unit}."
        ),
        "environment_modality": (
            f"{action} condições de comunicação, suporte e coordenação relacionadas a "
            f"{title.lower()} na {unit}."
        ),
    }
    monitoring = {
        "work_organization": "Revisão quinzenal do fluxo, das exceções e da passagem entre responsáveis.",
        "workload_demand": "Painel semanal de filas, pausas adiadas, retrabalho e capacidade por turno.",
        "harassment_violence": "Revisão mensal de ocorrências agregadas, tempo de resposta e acolhimento oferecido.",
        "environment_modality": "Ronda mensal das condições de comunicação e consulta estruturada às equipes.",
    }
    evidence_done = {
        "work_organization": "Registro cenográfico: fluxo redesenhado, líderes orientados e equipe consultada.",
        "workload_demand": "Registro cenográfico: escala de pico, regra de pausas e limite de simultaneidade implantados.",
        "harassment_violence": "Registro cenográfico: protocolo divulgado, liderança treinada e canal de acolhimento ensaiado.",
        "environment_modality": "Registro cenográfico: canais e responsabilidades atualizados no roteiro operacional.",
    }
    deadline_days = {"critical": 15, "high": 30, "moderate": 60, "low": 90}
    today = datetime.now(timezone.utc).date()
    return {
        "measure": "Cenário demonstrativo — " + measures[seed["nr1_factor"]],
        "evidence": (
            evidence_done[seed["nr1_factor"]]
            if implemented
            else "Pendência do exercício: pactuar a medida com liderança e trabalhadores antes da implementação."
        ),
        "monitoring": monitoring[seed["nr1_factor"]],
        "measurement": (
            f"Comparar o resultado agregado de {title} no mesmo recorte e instrumento; "
            "mudança dentro da margem permanece sem eficácia demonstrada."
        ),
        "due_date": (
            today - timedelta(days=150 - min(seed["priority_rank"], 20))
            if implemented
            else today + timedelta(days=deadline_days[seed["risk_level"]])
        ),
        "implemented_at": (
            datetime.now(timezone.utc) - timedelta(days=120)
            if implemented else None
        ),
        "created_at": (
            datetime.now(timezone.utc) - timedelta(days=178)
            if implemented
            else datetime.now(timezone.utc) - timedelta(days=1)
        ),
    }


def _store_action_plan(
    connection, campaign_id: str, graded, *, implemented: bool,
    dimension_titles: dict | None = None,
) -> None:
    titles = dimension_titles or {}
    for seed in nr1_compliance.action_plan_seed(graded):
        item_id = pilot_id(
            f"action/{campaign_id}/{seed['unit_id']}/{seed['dimension_id']}"
        )
        title = titles.get(str(seed["dimension_id"]), seed["nr1_factor"].replace("_", " "))
        content = _action_plan_text(seed, title, implemented=implemented)
        connection.execute(
            """
            INSERT INTO psychosocial_action_plan
                (id, organization_id, inventory_id, campaign_id, criteria_id,
                 measure, measure_type, plan_action, responsible_membership_id,
                 due_date, status, evidence, monitoring_method,
                 result_measurement, implemented_at, effectiveness_reviewed_at,
                 effectiveness, exposed_workers, priority_rank, created_at)
            SELECT %s,%s,inventory.id,%s,%s,%s,%s,%s,%s,
                   %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
              FROM psychosocial_risk_inventory inventory
             WHERE inventory.organization_id=%s
               AND inventory.campaign_id=%s
               AND inventory.dimension_id=%s
               AND inventory.unit_id IS NOT DISTINCT FROM %s
            ON CONFLICT (id) DO UPDATE SET
                measure=EXCLUDED.measure,
                measure_type=EXCLUDED.measure_type,
                plan_action=EXCLUDED.plan_action,
                responsible_membership_id=EXCLUDED.responsible_membership_id,
                due_date=EXCLUDED.due_date,
                status=EXCLUDED.status,
                evidence=EXCLUDED.evidence,
                monitoring_method=EXCLUDED.monitoring_method,
                result_measurement=EXCLUDED.result_measurement,
                implemented_at=coalesce(
                    psychosocial_action_plan.implemented_at,
                    EXCLUDED.implemented_at
                ),
                effectiveness_reviewed_at=EXCLUDED.effectiveness_reviewed_at,
                effectiveness=EXCLUDED.effectiveness,
                exposed_workers=EXCLUDED.exposed_workers,
                priority_rank=EXCLUDED.priority_rank
            """,
            (
                item_id, ORG_ID, campaign_id, CRITERIA_ID, content["measure"],
                seed["measure_type"], seed["plan_action"], MEMBERSHIP_ID,
                content["due_date"],
                "done" if implemented else "planned",
                content["evidence"], content["monitoring"], content["measurement"],
                content["implemented_at"],
                None,
                None,
                seed["exposed_workers"], seed["priority_rank"],
                content["created_at"],
                ORG_ID, campaign_id, seed["dimension_id"], seed["unit_id"],
            ),
        )


def complete_cycle(connection, dimensions) -> None:
    """Fecha as camadas documentais do piloto sem tocar em dados reais."""
    # Versões anteriores do piloto conseguiam gerar rascunhos aleatórios do
    # plano pela API e deixá-los no mesmo inventário. Eles não podem receber um
    # veredito: medida planejada ainda não foi implementada. Como esta
    # organização é exclusiva do gerador, reconstruir somente os seus planos e
    # revisões remove o estado antigo sem alcançar campanha real alguma.
    connection.execute(
        "DELETE FROM measure_effectiveness_reviews WHERE organization_id=%s",
        (ORG_ID,),
    )
    connection.execute(
        "DELETE FROM psychosocial_action_plan WHERE organization_id=%s",
        (ORG_ID,),
    )
    base_aep = _create_aep_documents(connection, CAMPAIGN_BASE, "baseline")
    follow_aep = _create_aep_documents(connection, CAMPAIGN_FOLLOW, "followup")

    base_scores = _scores(connection, CAMPAIGN_BASE)
    follow_scores = _scores(connection, CAMPAIGN_FOLLOW)
    dimension_titles = {str(item["id"]): item["title"] for item in dimensions}
    base_graded = nr1_compliance.grade_all(base_scores)
    _store_inventory(connection, CAMPAIGN_BASE, base_graded, base_aep)
    _store_action_plan(
        connection, CAMPAIGN_BASE, base_graded, implemented=True,
        dimension_titles=dimension_titles,
    )

    verdicts = nr1_effectiveness.compare_campaigns(base_scores, follow_scores)
    _store_effectiveness(connection, verdicts)
    # A revisão gravada passa a compor a probabilidade do ciclo seguinte.
    follow_graded = nr1_compliance.grade_all(_scores(connection, CAMPAIGN_FOLLOW))
    _store_inventory(connection, CAMPAIGN_FOLLOW, follow_graded, follow_aep)
    # A reavaliação fecha a apuração e abre, corretamente, as correções do
    # próximo giro. Declará-las concluídas sem uma terceira medição seria
    # transformar ausência de evidência em eficácia.
    _store_action_plan(
        connection, CAMPAIGN_FOLLOW, follow_graded, implemented=False,
        dimension_titles=dimension_titles,
    )
    print(
        "Ciclo documental demonstrativo concluído: AEP, evidências, inventários, "
        "planos de ação e eficácia vinculados."
    )


def _json(value) -> str:
    import json

    return json.dumps(value)


def pseudonym_for(unit_id: str, indice: int) -> str:
    """Pseudônimo simulado, único por pessoa dentro da campanha.

    O banco impõe UNIQUE (campaign_id, subject_pseudonym) justamente para
    impedir que a mesma pessoa responda duas vezes. A primeira versão deste
    roteiro numerava a partir de zero em cada unidade e colidia — ou seja,
    simulava duas pessoas diferentes com o mesmo crachá. A restrição estava
    certa; o gerador é que estava errado.
    """
    return f"piloto-{unit_id}-{indice:04d}"


def _simulate_wave(connection, campaign_id, dimensions, wave) -> None:
    rng = random.Random(f"{campaign_id}|{wave}")
    for unit_id, total in POPULATION.items():
        for indice in range(total):
            invitation_id = str(
                uuid.uuid5(PILOT_NAMESPACE, f"invite/{campaign_id}/{unit_id}/{indice}")
            )
            response_id = str(
                uuid.uuid5(PILOT_NAMESPACE, f"response/{campaign_id}/{unit_id}/{indice}")
            )
            connection.execute(
                """
                INSERT INTO assessment_invitations
                    (id, organization_id, campaign_id, unit_id, subject_pseudonym,
                     token_hash, status, responded_at)
                VALUES (%s,%s,%s,%s,%s,%s,'responded',now())
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    invitation_id, ORG_ID, campaign_id, unit_id,
                    pseudonym_for(unit_id, indice),
                    f"piloto-token-{invitation_id}",
                ),
            )
            connection.execute(
                """
                INSERT INTO assessment_responses
                    (id, organization_id, campaign_id, invitation_id, unit_id, completed)
                VALUES (%s,%s,%s,%s,%s,true)
                ON CONFLICT (id) DO NOTHING
                """,
                (response_id, ORG_ID, campaign_id, invitation_id, unit_id),
            )
            for dimension in dimensions:
                for item_id in dimension["items"]:
                    connection.execute(
                        """
                        INSERT INTO assessment_response_items (response_id, item_id, value)
                        VALUES (%s,%s,%s)
                        ON CONFLICT DO NOTHING
                        """,
                        (response_id, item_id, answer_for(rng, dimension, unit_id, wave)),
                    )


def _scores(connection, campaign_id):
    connection.execute("SELECT set_config('app.organization_id', %s, true)", (ORG_ID,))
    connection.execute("SELECT set_config('app.membership_id', %s, true)", (MEMBERSHIP_ID,))
    rows = connection.execute(
        """
        SELECT unit_id, dimension_id, nr1_factor, polarity, cut_favorable,
               cut_critical, cohort_size, mean_score, critical_ratio,
               score_stddev, consequences, measure_efficacy, exposed_workers
        FROM froid_nr1_dimension_scores(%s)
        """,
        (campaign_id,),
    ).fetchall()
    return [
        nr1_compliance.DimensionScore(
            unit_id=str(r[0]) if r[0] else None, dimension_id=str(r[1]),
            nr1_factor=r[2], polarity=r[3], cut_favorable=float(r[4]),
            cut_critical=float(r[5]), cohort_size=int(r[6]),
            mean_score=float(r[7]), critical_ratio=float(r[8]),
            score_stddev=float(r[9] or 0), consequences=tuple(r[10] or ()),
            measure_efficacy=r[11] or "none", exposed_workers=int(r[12] or 0),
        )
        for r in rows
    ]


def report(connection) -> None:
    titulos = dict(
        connection.execute(
            "SELECT id, title FROM assessment_dimensions WHERE instrument_id="
            "(SELECT id FROM assessment_instruments WHERE code=%s AND version=%s)",
            (INSTRUMENT_CODE, INSTRUMENT_VERSION),
        ).fetchall()
    )
    unidades = dict(
        connection.execute(
            "SELECT id, name FROM organization_units WHERE organization_id=%s",
            (ORG_ID,),
        ).fetchall()
    )

    base = _scores(connection, CAMPAIGN_BASE)
    follow = _scores(connection, CAMPAIGN_FOLLOW)

    print()
    print(paint("PISO DE COORTE", BOLD))
    for unit_id, total in POPULATION.items():
        recortes = [s for s in follow if s.unit_id == unit_id]
        nome = unidades.get(uuid.UUID(unit_id), unit_id)
        print(f"  {nome}: {total} respostas -> "
              f"{len(recortes)} dimensões liberadas")
    print(f"  Total de recortes liberados: {len(follow)}")

    print()
    print(paint("GRADAÇÃO — REAVALIAÇÃO", BOLD))
    graded = nr1_compliance.grade_all(follow)
    for risk in graded[:8]:
        nome = titulos.get(uuid.UUID(risk.dimension_id), risk.dimension_id)
        unidade = unidades.get(uuid.UUID(risk.unit_id), "—") if risk.unit_id else "—"
        print(f"  {risk.risk_level.upper():9} S{risk.severity}xP{risk.probability}  "
              f"{nome} · {unidade} · n={risk.cohort_size} · "
              f"média {risk.mean_score:.2f} · {risk.exposed_workers} expostos")

    print()
    print(paint("EFICÁCIA — LINHA DE BASE vs REAVALIAÇÃO", BOLD))
    verdicts = nr1_effectiveness.compare_campaigns(base, follow)
    for verdict in verdicts:
        nome = titulos.get(uuid.UUID(verdict.dimension_id), verdict.dimension_id)
        unidade = unidades.get(uuid.UUID(verdict.unit_id), "—") if verdict.unit_id else "—"
        marca = "!" if verdict.requires_correction else " "
        sig = "sig" if verdict.significant else "   "
        print(f" {marca} d={verdict.effect_size:+.2f} ±{verdict.effect_margin:.2f} {sig}  "
              f"{verdict.verdict:12} {nome} · {unidade} · "
              f"{verdict.baseline_mean:.2f} -> {verdict.followup_mean:.2f}")
    falhas = nr1_effectiveness.measures_requiring_correction(verdicts)
    print(f"\n  Medidas que exigem correção: {len(falhas)}")

    print()
    print(paint("ROAD MAP DOCUMENTAL DO PILOTO", BOLD))
    counts = {
        "campanhas encerradas": connection.execute(
            "SELECT count(*) FROM assessment_campaigns "
            "WHERE organization_id=%s AND status='closed'",
            (ORG_ID,),
        ).fetchone()[0],
        "AEP concluídas": connection.execute(
            "SELECT count(*) FROM aep_assessments "
            "WHERE organization_id=%s AND status='concluded'",
            (ORG_ID,),
        ).fetchone()[0],
        "evidências metodológicas": connection.execute(
            "SELECT count(*) FROM aep_evidence WHERE organization_id=%s",
            (ORG_ID,),
        ).fetchone()[0],
        "riscos no inventário": connection.execute(
            "SELECT count(*) FROM psychosocial_risk_inventory WHERE organization_id=%s",
            (ORG_ID,),
        ).fetchone()[0],
        "medidas no plano de ação": connection.execute(
            "SELECT count(*) FROM psychosocial_action_plan WHERE organization_id=%s",
            (ORG_ID,),
        ).fetchone()[0],
        "revisões de eficácia": connection.execute(
            "SELECT count(*) FROM measure_effectiveness_reviews WHERE organization_id=%s",
            (ORG_ID,),
        ).fetchone()[0],
    }
    for label, count in counts.items():
        print(f"  OK  {label}: {count}")

    inventory_without_aep = connection.execute(
        "SELECT count(*) FROM psychosocial_risk_inventory "
        "WHERE organization_id=%s AND aep_id IS NULL",
        (ORG_ID,),
    ).fetchone()[0]
    expected_reviews = len({(item.unit_id, item.dimension_id) for item in base})
    incomplete = (
        counts["campanhas encerradas"] != 2
        or counts["AEP concluídas"] != len(POPULATION) * 2
        or counts["evidências metodológicas"] != len(POPULATION) * 2 * 4
        or counts["riscos no inventário"] == 0
        or counts["medidas no plano de ação"] == 0
        or counts["revisões de eficácia"] != expected_reviews
        or inventory_without_aep != 0
    )
    print(f"  OK  vínculos inventário → AEP: {inventory_without_aep} pendente(s)")
    if incomplete:
        raise SystemExit(
            "Piloto incompleto: execute --create novamente e confira os erros acima."
        )

    print()
    print(paint("CONFERÊNCIA DAS GARANTIAS", BOLD))
    aberta = connection.execute(
        "SELECT count(*) FROM froid_nr1_dimension_scores(%s)", (CAMPAIGN_BASE,)
    ).fetchone()
    connection.execute(
        "UPDATE assessment_campaigns SET status='open' WHERE id=%s", (CAMPAIGN_BASE,)
    )
    durante = connection.execute(
        "SELECT count(*) FROM froid_nr1_dimension_scores(%s)", (CAMPAIGN_BASE,)
    ).fetchone()
    connection.execute(
        "UPDATE assessment_campaigns SET status='closed' WHERE id=%s", (CAMPAIGN_BASE,)
    )
    print(f"  Campanha encerrada devolve {aberta[0]} recortes; "
          f"reaberta devolve {durante[0]}.")
    if durante[0] != 0:
        print(paint("  FALHA: campanha aberta liberou resultado.", BOLD))
    else:
        print("  OK: nenhum resultado sai com a coleta aberta.")


def destroy(connection) -> None:
    """Remove exatamente o que o piloto criou, e nada além disso."""
    passos = [
        ("measure_effectiveness_reviews", "organization_id=%s"),
        ("psychosocial_action_plan", "organization_id=%s"),
        ("psychosocial_risk_inventory_history", "organization_id=%s"),
        ("psychosocial_risk_inventory", "organization_id=%s"),
        ("aep_evidence", "organization_id=%s"),
        ("aep_assessments", "organization_id=%s"),
        ("worker_participation_records", "organization_id=%s"),
    ]
    connection.execute(
        """
        DELETE FROM assessment_response_items WHERE response_id IN (
            SELECT id FROM assessment_responses WHERE organization_id=%s
        )
        """,
        (ORG_ID,),
    )
    connection.execute("DELETE FROM assessment_responses WHERE organization_id=%s", (ORG_ID,))
    connection.execute("DELETE FROM assessment_invitations WHERE organization_id=%s", (ORG_ID,))
    for tabela, condicao in passos:
        connection.execute(f"DELETE FROM {tabela} WHERE {condicao}", (ORG_ID,))
    connection.execute("DELETE FROM assessment_campaigns WHERE organization_id=%s", (ORG_ID,))
    connection.execute("DELETE FROM gro_risk_criteria WHERE organization_id=%s", (ORG_ID,))
    connection.execute("DELETE FROM organization_units WHERE organization_id=%s", (ORG_ID,))
    # Associacoes concedidas por --grant a contas reais. A conta em si nunca
    # e tocada: ela existia antes do piloto e continua existindo depois.
    connection.execute(
        "DELETE FROM membership_roles WHERE membership_id IN ("
        "SELECT id FROM organization_memberships WHERE organization_id=%s)",
        (ORG_ID,),
    )
    connection.execute(
        "DELETE FROM organization_memberships WHERE organization_id=%s", (ORG_ID,)
    )
    connection.execute("DELETE FROM membership_roles WHERE membership_id=%s", (MEMBERSHIP_ID,))
    connection.execute("DELETE FROM organization_memberships WHERE id=%s", (MEMBERSHIP_ID,))
    connection.execute(
        "DELETE FROM users WHERE id=%s AND email=%s", (PILOT_USER_ID, PILOT_USER_EMAIL)
    )
    connection.execute(
        "DELETE FROM organizations WHERE id=%s AND legal_name = ANY(%s)",
        (ORG_ID, [ORG_LEGAL_NAME, *NOMES_ANTERIORES]),
    )
    print("Piloto removido. Nenhum resíduo permanece.")


def grant_access(connection, email: str) -> None:
    """Dá a uma conta real acesso de leitura e gestão à empresa do piloto.

    Sem isto o piloto prova o motor e não prova nada na tela: os dados existem
    ligados a um usuário fictício que ninguém consegue autenticar. Para conferir
    painel, inventário e plano de ação COM OS OLHOS — que é o que decide se o
    produto está pronto para vender — é preciso que uma conta de verdade enxergue
    a organização de teste.

    O papel concedido é `compliance_manager`: é ele que roda o programa NR-1 do
    lado do empregador e é ele que, por desenho, NÃO lê registro clínico
    identificado. Conceder `professional` aqui devolveria pela porta dos fundos
    exatamente o que o módulo existe para impedir.

    `--destroy` remove esta associação junto com o resto. A conta em si nunca é
    tocada: ela já existia antes e continua existindo depois.
    """
    alvo = (email or "").strip().lower()
    if not alvo:
        raise SystemExit("informe o e-mail da conta que vai acompanhar o piloto")
    linha = connection.execute(
        "SELECT id FROM users WHERE lower(email) = %s", (alvo,)
    ).fetchone()
    if not linha:
        raise SystemExit(
            f"nenhuma conta com o e-mail {alvo}. Faça login uma vez no FROID "
            "com essa conta antes de rodar este comando."
        )
    user_id = str(linha[0])
    membership_id = str(uuid.uuid5(PILOT_NAMESPACE, f"membership/{alvo}"))
    connection.execute(
        """
        INSERT INTO organization_memberships
            (id, organization_id, user_id, status, joined_at)
        VALUES (%s,%s,%s,'active',now())
        ON CONFLICT (organization_id, user_id) DO UPDATE
            SET status='active', revoked_at=NULL, updated_at=now()
        """,
        (membership_id, ORG_ID, user_id),
    )
    real = connection.execute(
        "SELECT id FROM organization_memberships WHERE organization_id=%s AND user_id=%s",
        (ORG_ID, user_id),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO membership_roles (membership_id, role) VALUES (%s,'compliance_manager') "
        "ON CONFLICT DO NOTHING",
        (str(real),),
    )
    print(f"{BOLD}Acesso concedido a {alvo}{RESET}")
    print(
        "  Entre no FROID com essa conta, troque para a organização "
        "'Piloto NR-1' e abra o painel NR-1."
    )
    print("  Papel: compliance_manager (não lê prontuário, por desenho).")


def validate_grant_accounts(connection, emails) -> None:
    """Recusa antes de criar o piloto quando qualquer conta ainda não existe.

    A criação e os vínculos vivem na mesma transação e já eram revertidos em
    caso de falha. Porém, stdout fica armazenado quando o script roda com
    ``docker compose exec -T``: as mensagens de sucesso apareciam depois do
    erro escrito em stderr e davam a impressão de concessão parcial. Validar a
    lista inteira primeiro torna a ordem visível igual à ordem real.
    """
    requested = sorted({str(email or "").strip().lower() for email in emails if email})
    if not requested:
        return
    rows = connection.execute(
        "SELECT lower(email) FROM users WHERE lower(email) = ANY(%s)",
        (requested,),
    ).fetchall()
    existing = {str(row[0]).strip().lower() for row in rows}
    missing = [email for email in requested if email not in existing]
    if missing:
        raise SystemExit(
            "conta(s) ainda não cadastrada(s) no FROID: " + ", ".join(missing)
            + ". Faça login uma vez com cada conta e execute novamente; nenhum "
            "dado do piloto foi criado."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="monta a empresa teste")
    parser.add_argument("--report", action="store_true", help="imprime a análise")
    parser.add_argument("--destroy", action="store_true", help="remove tudo")
    parser.add_argument(
        "--grant",
        metavar="EMAIL",
        action="append",
        help=(
            "dá acesso à empresa do piloto; repita a opção para conceder a "
            "mais de uma conta na mesma transação"
        ),
    )
    args = parser.parse_args()
    if not (args.create or args.report or args.destroy or args.grant):
        parser.error("escolha --create, --report, --grant ou --destroy")

    # Vale para --destroy também, e a razão é concreta: a migration 017 corrige
    # o gatilho que impedia remover os critérios do GRO. Como eu só aplicava o
    # schema em --create e --report, a limpeza continuava batendo no gatilho
    # antigo mesmo depois da correção publicada — o conserto existia e não
    # chegava a quem precisava dele.
    #
    # Fora da transação do piloto de propósito: aplicar migration dentro dela
    # misturaria mudança de schema com dado de teste no mesmo rollback.
    ensure_migrations()

    with connect() as connection:
        with connection.transaction():
            if args.destroy:
                destroy(connection)
                return 0
            validate_grant_accounts(connection, args.grant or [])
            if args.create:
                create(connection)
            for email in args.grant or []:
                grant_access(connection, email)
            if args.create or args.report:
                report(connection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
