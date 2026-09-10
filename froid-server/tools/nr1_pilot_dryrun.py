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
UNIT_DIGITAL = str(uuid.uuid5(PILOT_NAMESPACE, "unit/digital"))
CRITERIA_ID = str(uuid.uuid5(PILOT_NAMESPACE, "criteria"))
CAMPAIGN_BASE = str(uuid.uuid5(PILOT_NAMESPACE, "campaign/baseline"))
CAMPAIGN_FOLLOW = str(uuid.uuid5(PILOT_NAMESPACE, "campaign/followup"))


def pilot_id(name: str) -> str:
    """Identificador estável para que completar o piloto seja idempotente."""
    return str(uuid.uuid5(PILOT_NAMESPACE, name))

INSTRUMENT_CODE = "froid-nr1-psicossocial"
INSTRUMENT_VERSION = "1.0"

# Amostra do estudo demonstrativo de uma rede com 1.084 farmácias em sete
# estados. Os números representam participantes, não perguntas nem o efetivo
# total da empresa. Todos os recortes ficam acima dos pisos de coorte.
POPULATION = {
    UNIT_ATENDIMENTO: 240,
    UNIT_LOGISTICA: 120,
    UNIT_DIGITAL: 90,
}

UNIT_NAMES = {
    UNIT_ATENDIMENTO: "Lojas — dispensação, atendimento e caixa",
    UNIT_LOGISTICA: "Centros de distribuição e abastecimento",
    UNIT_DIGITAL: "Comércio digital e televendas",
}

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

    Cada setor exercita uma decisão diferente do acompanhamento: melhora
    comprovada, melhora parcial, ausência de mudança e piora que exige correção.
    """
    code = dimension["code"]
    protective = dimension["polarity"] == "protective"

    if unit_id == UNIT_ATENDIMENTO and code == "sobrecarga":
        centro = 4.4 if wave == "baseline" else 2.9
    elif unit_id == UNIT_ATENDIMENTO and code == "violencia":
        centro = 3.6 if wave == "baseline" else 2.2
    elif unit_id == UNIT_LOGISTICA and code == "comunicacao":
        centro = 4.1 if wave == "baseline" else 2.7
    elif unit_id == UNIT_LOGISTICA and code == "sobrecarga":
        centro = 3.9 if wave == "baseline" else 3.5
    elif unit_id == UNIT_DIGITAL and code == "assedio":
        centro = 1.7 if wave == "baseline" else 3.2
    elif unit_id == UNIT_DIGITAL and code == "autonomia":
        centro = 2.0 if wave == "baseline" else 3.25
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

    for unit_id, nome in UNIT_NAMES.items():
        headcount = POPULATION[unit_id]
        connection.execute(
            """
            INSERT INTO organization_units
                (id, organization_id, unit_type, name, headcount, status)
            VALUES (%s,%s,'sector',%s,%s,'active')
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name,
                headcount=EXCLUDED.headcount,
                status='active'
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
        periodo = f"{abertura:%d/%m/%Y} a {encerramento:%d/%m/%Y}"
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
                "Mapear fatores de risco psicossociais relacionados ao trabalho em uma rede "
                "de 1.084 farmácias distribuídas por sete estados, comparar lojas, centros "
                "de distribuição e comércio digital e acompanhar a eficácia das medidas adotadas.",
                "Canal de acolhimento e orientação",
                "Atendimento confidencial pela equipe corporativa de Saúde e Segurança "
                "do Trabalho, com encaminhamento conforme a natureza da demanda.",
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
    """Narrativas operacionais completas para os três recortes do estudo."""
    if unit_id not in POPULATION or wave not in {"baseline", "followup"}:
        raise ValueError("unidade ou onda fora do cenário do piloto")

    scenarios = {
        (UNIT_ATENDIMENTO, "baseline"): {
            "reference_period": "Linha de base — ciclo nacional de lojas",
            "real_work_description": (
                "A rede opera 1.084 farmácias em sete estados: São Paulo, Rio de Janeiro, "
                "Minas Gerais, Paraná, Santa Catarina, Goiás e Bahia. Farmacêuticos, balconistas, operadores "
                "de caixa e gerentes conciliam dispensação segura, orientação ao consumidor, "
                "validação de receitas, controle de medicamentos sujeitos a controle especial, "
                "retirada de pedidos digitais, reposição de gôndola e fechamento financeiro. "
                "Lojas de rua, shopping e atendimento 24 horas têm ritmos e estruturas distintos."
            ),
            "exposure_duration": (
                "As exigências acompanham toda a jornada e se intensificam nos intervalos em "
                "que a mesma equipe atende balcão, caixa, telefone e retirada digital. Filas "
                "prolongadas reduzem a previsibilidade das pausas e concentram conferências "
                "técnicas no farmacêutico responsável."
            ),
            "exposure_frequency": (
                "Picos ocorrem diariamente no início da manhã, no horário de almoço e após o "
                "expediente comercial. Datas de pagamento, campanhas promocionais e períodos "
                "de maior procura por medicamentos respiratórios ampliam volume e conflitos."
            ),
            "exposure_intensity": (
                "A pressão é elevada quando há escala incompleta, indisponibilidade de produto, "
                "divergência entre preço do aplicativo e da loja ou necessidade de recusar uma "
                "dispensação. Nessas situações, rapidez comercial e segurança farmacêutica "
                "podem ser percebidas como objetivos concorrentes."
            ),
            "exposure_cofactors": (
                "Contribuem para a exposição a variação de porte das lojas, metas simultâneas, "
                "troca frequente de prioridade, falhas de integração de estoque, autonomia "
                "desigual das gerências, clientes agressivos e risco de roubo em unidades com "
                "funcionamento noturno."
            ),
            "health_indicators": (
                "Os registros coletivos de SST concentram relatos de desgaste após picos, "
                "dificuldade para realizar pausas e tensão em atendimentos com recusa técnica. "
                "A análise permanece ocupacional e agregada, sem acesso a resposta individual "
                "ou utilização de diagnóstico clínico."
            ),
            "absenteeism_notes": (
                "A série gerencial indica concentração de ausências breves em lojas com vagas "
                "temporariamente descobertas e jornadas de maior movimento. A informação orienta "
                "a investigação das condições de trabalho e não estabelece nexo individual."
            ),
            "previous_assessments": (
                "Inspeções anteriores tratavam ergonomia física, segurança patrimonial e escalas "
                "separadamente. Não havia avaliação psicossocial comparável por setor, estado e "
                "modelo de loja; esta coleta estabelece a referência inicial."
            ),
            "responsible_name": "Juliana Costa",
            "responsible_qualification": "Engenharia de Segurança do Trabalho — coordenação corporativa de SST",
            "aet_required": True,
            "aet_justification": (
                "Aprofundar a organização real do trabalho em lojas de diferentes portes, com "
                "ênfase em dimensionamento, pausas, metas concorrentes, autonomia para recusa "
                "técnica, atendimento hostil e trabalho noturno."
            ),
        },
        (UNIT_ATENDIMENTO, "followup"): {
            "reference_period": "Reavaliação — ciclo nacional de lojas",
            "real_work_description": (
                "A rede implantou matriz mínima de cobertura por faixa horária, célula regional "
                "para remanejamento de equipes, separação da fila de retirada digital e regra que "
                "preserva a decisão técnica do farmacêutico. Gerentes passaram a registrar pausas "
                "adiadas e acionar suporte regional quando a ocupação supera a capacidade prevista."
            ),
            "exposure_duration": (
                "Os períodos contínuos de pressão ficaram mais curtos nas lojas cobertas pelo "
                "novo dimensionamento. Unidades 24 horas e lojas com vaga aberta ainda acumulam "
                "atendimento, conferência, reposição e fechamento no mesmo profissional."
            ),
            "exposure_frequency": (
                "A sobrecarga deixou de dominar a rotina diária na maior parte do recorte, mas "
                "permanece recorrente em campanhas de preço, fechamento de mês, faltas imprevistas "
                "e indisponibilidade de itens anunciados nos canais digitais."
            ),
            "exposure_intensity": (
                "A redução das filas e a cobertura regional diminuíram a pressão por velocidade. "
                "Ocorrências de ameaça, tentativa de intimidação e agressão verbal continuam com "
                "alto impacto, embora o tempo de resposta da liderança tenha melhorado."
            ),
            "exposure_cofactors": (
                "Persistem diferenças entre estados na disponibilidade de mão de obra, na estrutura "
                "física e no apoio de segurança. A aplicação do protocolo de interrupção segura "
                "ainda varia entre gerentes recém-admitidos e equipes de turno noturno."
            ),
            "health_indicators": (
                "A devolutiva coletiva aponta melhora na recuperação após os picos e maior "
                "previsibilidade das pausas. Permanecem pedidos de apoio depois de agressões verbais "
                "e ocorrências de segurança, tratados sem exposição da identidade do trabalhador."
            ),
            "absenteeism_notes": (
                "A distribuição de ausências passou a ser acompanhada por porte de loja, turno e "
                "cobertura da escala. O período ainda é insuficiente para atribuir mudança às "
                "medidas, razão pela qual o indicador permanece em acompanhamento."
            ),
            "previous_assessments": (
                "A comparação utiliza a linha de base do mesmo instrumento, os mesmos três recortes "
                "ocupacionais e regras de coorte equivalentes. Alterações de composição das equipes "
                "foram registradas antes da análise de eficácia."
            ),
            "responsible_name": "Juliana Costa",
            "responsible_qualification": "Engenharia de Segurança do Trabalho — coordenação corporativa de SST",
            "aet_required": True,
            "aet_justification": (
                "Manter o aprofundamento nas lojas 24 horas e com escala incompleta, verificar a "
                "aplicação do protocolo de violência e consolidar critérios nacionais para pausas, "
                "remanejamento e interrupção de atendimento inseguro."
            ),
        },
        (UNIT_LOGISTICA, "baseline"): {
            "reference_period": "Linha de base — distribuição e abastecimento",
            "real_work_description": (
                "Quatro centros de distribuição recebem medicamentos, conferem lote e validade, "
                "armazenam produtos com requisitos distintos, separam pedidos e abastecem 1.084 "
                "lojas em sete estados. Planejamento, recebimento, armazenagem, picking, conferência, "
                "expedição e transporte coordenam janelas rígidas, cadeia fria, itens controlados, "
                "devoluções e bloqueios de qualidade."
            ),
            "exposure_duration": (
                "A pressão acompanha as ondas de separação e cresce nas quatro horas anteriores ao "
                "corte de expedição. Divergências de lote, atraso de transportadora e pedido urgente "
                "podem prolongar a atividade até a passagem para o turno seguinte."
            ),
            "exposure_frequency": (
                "Repriorizações acontecem em todas as janelas de carga. Eventos mais intensos se "
                "concentram em lançamentos comerciais, feriados, restrições de tráfego, ruptura de "
                "estoque e necessidade de redistribuição entre estados."
            ),
            "exposure_intensity": (
                "A exigência é alta quando WMS, quadro da doca e orientação por rádio apresentam "
                "prioridades diferentes. O trabalhador precisa manter rastreabilidade e qualidade "
                "ao mesmo tempo que responde à urgência de lojas sem estoque."
            ),
            "exposure_cofactors": (
                "Ruído, distância entre áreas, circulação de terceiros, metas por onda, diferenças "
                "entre turnos, baixa visibilidade da causa das urgências e responsabilidade pouco "
                "clara para liberar exceções ampliam a carga organizacional."
            ),
            "health_indicators": (
                "As escutas coletivas registram fadiga ao final das ondas, tensão nas divergências "
                "de inventário e receio de responsabilização por decisões recebidas por canais "
                "informais. Não são utilizados prontuários nem informações clínicas individuais."
            ),
            "absenteeism_notes": (
                "O acompanhamento gerencial identifica maior necessidade de recomposição de equipe "
                "nos turnos de fechamento. Não há base suficiente para atribuir causalidade, e a "
                "informação é usada apenas para orientar verificação do trabalho real."
            ),
            "previous_assessments": (
                "Os centros possuíam inspeções de segurança e indicadores de produtividade, porém "
                "sem integração entre organização do trabalho, comunicação e riscos psicossociais. "
                "A linha de base cria essa referência conjunta."
            ),
            "responsible_name": "Eduardo Ramos",
            "responsible_qualification": "Engenharia de Segurança do Trabalho — operações logísticas",
            "aet_required": True,
            "aet_justification": (
                "Analisar em profundidade as ondas de separação, os cortes de expedição, a passagem "
                "entre turnos, os canais de priorização e a autonomia para interromper uma operação "
                "quando rastreabilidade, segurança ou qualidade estiverem ameaçadas."
            ),
        },
        (UNIT_LOGISTICA, "followup"): {
            "reference_period": "Reavaliação — distribuição e abastecimento",
            "real_work_description": (
                "Os centros adotaram uma fila única de prioridades integrada ao WMS, reunião curta "
                "na troca de turno, autoridade formal para bloqueio de exceções e célula de controle "
                "para redistribuição entre estados. O plano de ondas passou a considerar capacidade "
                "real, pedidos críticos, cadeia fria e horário limite das transportadoras."
            ),
            "exposure_duration": (
                "O tempo gasto conciliando orientações divergentes caiu após a unificação do canal. "
                "A pressão próxima ao corte permanece prolongada quando atraso de fornecedor, avaria "
                "ou restrição de transporte afeta mais de uma rota."
            ),
            "exposure_frequency": (
                "Falhas de comunicação tornaram-se menos frequentes; repriorizações continuam "
                "diárias, agora registradas com origem, responsável, justificativa e impacto sobre "
                "a capacidade de cada turno."
            ),
            "exposure_intensity": (
                "A clareza do canal reduziu retrabalho e conflito entre planejamento, separação e "
                "doca. O volume dos dias críticos ainda supera a capacidade prevista em parte das "
                "rotas, produzindo melhora parcial de sobrecarga."
            ),
            "exposure_cofactors": (
                "A efetividade varia conforme adesão das transportadoras, estabilidade do WMS, "
                "antecedência da previsão comercial e disponibilidade de pessoal habilitado para "
                "itens controlados e produtos de cadeia fria."
            ),
            "health_indicators": (
                "A equipe relata menor ambiguidade na passagem de turno e menos conflito sobre a "
                "ordem de carregamento. Persistem sinais coletivos de desgaste em picos extensos, "
                "mantidos sob acompanhamento ocupacional agregado."
            ),
            "absenteeism_notes": (
                "As ausências e substituições são revisadas junto à ocupação das ondas, horas extras "
                "e aderência ao quadro planejado. O intervalo observado ainda não sustenta conclusão "
                "causal sobre a medida."
            ),
            "previous_assessments": (
                "A reavaliação repete instrumento, setores, critérios e regras de agregação da linha "
                "de base. A implantação do WMS integrado e da passagem estruturada foi registrada "
                "para permitir associação temporal com os resultados."
            ),
            "responsible_name": "Eduardo Ramos",
            "responsible_qualification": "Engenharia de Segurança do Trabalho — operações logísticas",
            "aet_required": True,
            "aet_justification": (
                "Verificar os picos que continuam acima da capacidade, a aderência ao canal único e "
                "a participação das transportadoras, preservando a autonomia de bloqueio e a "
                "rastreabilidade das decisões urgentes."
            ),
        },
        (UNIT_DIGITAL, "baseline"): {
            "reference_period": "Linha de base — comércio digital e televendas",
            "real_work_description": (
                "A operação reúne atendimento por telefone, chat e aplicativos, validação de receita, "
                "pagamento, consulta de estoque, substituição autorizada, separação na loja e entrega. "
                "Agentes atendem consumidores de sete estados e dependem da integração entre e-commerce, "
                "marketplaces, lojas, prescrições digitais, antifraude e parceiros logísticos."
            ),
            "exposure_duration": (
                "Filas multicanal ocupam a maior parte da jornada, com alternância rápida entre dúvidas "
                "técnicas, falha de pagamento, atraso de entrega e indisponibilidade. Casos pendentes "
                "permanecem atribuídos ao agente até a confirmação da solução."
            ),
            "exposure_frequency": (
                "A pressão por tempo é diária e aumenta após campanhas, indisponibilidade do aplicativo "
                "ou atraso regional de entregas. Comparações públicas de desempenho ocorrem nas reuniões "
                "semanais e nos painéis em tempo real."
            ),
            "exposure_intensity": (
                "Metas de tempo médio, conversão, qualidade e retenção são cobradas simultaneamente. A "
                "baixa autonomia para corrigir preço, prazo ou substituição prolonga conflitos e exige "
                "múltiplas autorizações para resolver uma única demanda."
            ),
            "exposure_cofactors": (
                "Monitoramento contínuo, mudanças de campanha sem briefing uniforme, trabalho remoto, "
                "falhas entre sistemas, clientes hostis e critérios diferentes entre supervisores "
                "ampliam a exposição."
            ),
            "health_indicators": (
                "As devolutivas coletivas concentram queixas sobre baixa margem de decisão, cobrança "
                "pública de resultados e dificuldade de desconexão após casos não resolvidos. A empresa "
                "recebe apenas achados agregados do trabalho."
            ),
            "absenteeism_notes": (
                "O acompanhamento mostra concentração de ausências curtas após semanas de instabilidade "
                "dos canais. O dado orienta investigação organizacional, sem atribuição individual ou "
                "conclusão clínica."
            ),
            "previous_assessments": (
                "Pesquisas de clima anteriores não separavam exposição ocupacional, satisfação com a "
                "empresa e experiência do cliente. Esta linha de base adota recorte e instrumento próprios."
            ),
            "responsible_name": "Camila Azevedo",
            "responsible_qualification": "Psicologia organizacional — prevenção de riscos psicossociais",
            "aet_required": True,
            "aet_justification": (
                "Aprofundar metas concorrentes, monitoramento, autonomia para solução, exposição a "
                "agressões de consumidores, critérios de supervisão e condições do trabalho remoto."
            ),
        },
        (UNIT_DIGITAL, "followup"): {
            "reference_period": "Reavaliação — comércio digital e televendas",
            "real_work_description": (
                "A operação adotou árvore de decisão com alçadas para crédito, substituição e prazo, "
                "reduziu transferências e criou célula de resolução para pedidos críticos. Ao mesmo tempo, "
                "uma reorganização introduziu ranking nominal diário, comparação pública entre agentes "
                "e cobrança direta em grupos de mensagem fora do fluxo formal."
            ),
            "exposure_duration": (
                "A autonomia reduziu a duração de demandas simples e o tempo de espera por autorização. "
                "A exposição à cobrança pública passou a acompanhar todo o turno por painel e mensagens, "
                "inclusive depois do encerramento de casos complexos."
            ),
            "exposure_frequency": (
                "Transferências e reaberturas diminuíram, enquanto comparações individuais e comentários "
                "depreciativos tornaram-se recorrentes nas reuniões de resultado e nos canais de equipe."
            ),
            "exposure_intensity": (
                "A maior alçada de decisão melhorou o controle sobre o trabalho. A forma de cobrança da "
                "nova gestão elevou o risco relacionado a humilhação, exposição vexatória e isolamento "
                "informal de agentes com resultado abaixo da meta."
            ),
            "exposure_cofactors": (
                "Trabalho remoto, registro permanente das mensagens, ausência de mediação, critérios de "
                "ranking pouco transparentes e competição por melhores filas reforçam o problema, apesar "
                "da melhoria operacional obtida com as novas alçadas."
            ),
            "health_indicators": (
                "A escuta agregada reconhece maior capacidade de resolver demandas e aponta aumento de "
                "relatos sobre constrangimento em reuniões e canais digitais. Nenhum relato individual é "
                "disponibilizado à gestão."
            ),
            "absenteeism_notes": (
                "O período de acompanhamento não permite relacionar ausências à reorganização. A análise "
                "mantém o indicador sem conclusão e prioriza as evidências convergentes do questionário, "
                "da observação e do diálogo coletivo."
            ),
            "previous_assessments": (
                "A comparação conserva instrumento, recorte, escala e critérios da linha de base. As alçadas "
                "e o ranking foram registrados como mudanças distintas para evitar atribuir o resultado a "
                "uma intervenção única."
            ),
            "responsible_name": "Camila Azevedo",
            "responsible_qualification": "Psicologia organizacional — prevenção de riscos psicossociais",
            "aet_required": True,
            "aet_justification": (
                "Interromper práticas de exposição nominal, revisar critérios de desempenho com participação "
                "dos trabalhadores e avaliar separadamente os benefícios das alçadas e os efeitos do modelo "
                "de supervisão."
            ),
        },
    }
    return scenarios[(unit_id, wave)]


def _graded_payload(risk) -> dict:
    row = asdict(risk)
    row.update(
        selected_consequence=risk.consequence,
        possible_harms=list(risk.consequences_considered),
        risk_classification=risk.risk_level,
    )
    return row


def _evidence_summaries(unit_id: str, wave: str) -> dict:
    """Evidências complementares específicas para cada setor e ciclo."""
    if unit_id not in POPULATION or wave not in {"baseline", "followup"}:
        raise ValueError("unidade ou onda fora do cenário do piloto")

    evidence = {
        (UNIT_ATENDIMENTO, "baseline"): {
            "questionnaire": (
                "Questionário respondido por 240 trabalhadores de lojas, com 39 itens analisados "
                "exclusivamente de forma agregada. Excesso de demandas e eventos violentos aparecem "
                "como prioridades convergentes entre portes de loja e estados."
            ),
            "activity_observation": (
                "Observação de jornadas em loja de rua, shopping e operação 24 horas registrou "
                "sobreposição entre balcão, caixa, retirada digital, telefone e conferência técnica, "
                "além de pausas adiadas durante filas prolongadas."
            ),
            "worker_dialogue": (
                "Grupos de diálogo com farmacêuticos, balconistas, caixas e gerentes relacionaram o "
                "desgaste à escala incompleta, às metas concorrentes e à dificuldade de interromper "
                "atendimentos com agressão verbal ou tentativa de intimidação."
            ),
            "document_analysis": (
                "Foram confrontados matriz de cobertura, escalas, regras de pausa, campanhas, registro "
                "de ocorrências de segurança, procedimento de recusa técnica e fluxo de apoio regional."
            ),
        },
        (UNIT_ATENDIMENTO, "followup"): {
            "questionnaire": (
                "A segunda coleta reuniu 240 participantes e mostrou redução consistente de excesso de "
                "demandas e exposição a violência, preservadas as mesmas regras de agregação e recorte."
            ),
            "activity_observation": (
                "A revisita confirmou fila separada para retirada digital, acionamento da célula regional, "
                "registro de pausas e presença de cobertura adicional nos horários previstos. Lojas 24 "
                "horas ainda apresentaram aplicação desigual do protocolo de segurança."
            ),
            "worker_dialogue": (
                "As equipes reconheceram maior previsibilidade e apoio para recusa técnica. Gerentes recém-"
                "admitidos e trabalhadores noturnos solicitaram treinamento prático sobre interrupção de "
                "atendimento, preservação do local e acolhimento após ocorrência."
            ),
            "document_analysis": (
                "Escalas, acionamentos regionais, pausas adiadas, registros de ocorrência e treinamentos "
                "foram comparados com a linha de base. As pendências ficaram associadas a responsáveis e prazos."
            ),
        },
        (UNIT_LOGISTICA, "baseline"): {
            "questionnaire": (
                "Questionário respondido por 120 trabalhadores dos centros de distribuição, com resultado "
                "agregado por setor. Comunicação operacional e excesso de demandas concentraram os achados."
            ),
            "activity_observation": (
                "O percurso acompanhou recebimento, armazenagem, picking, conferência e doca em duas trocas "
                "de turno. Foram observadas prioridades divergentes entre WMS, rádio e quadro, além de "
                "reprocessamento quando uma carga era alterada perto do corte."
            ),
            "worker_dialogue": (
                "Planejamento, separação, conferência e expedição relataram dúvidas sobre quem podia bloquear "
                "uma exceção, alterar a sequência das ondas ou aceitar impacto sobre cadeia fria e rastreabilidade."
            ),
            "document_analysis": (
                "Foram analisados plano de ondas, janelas de transportadoras, passagem de turno, registros de "
                "avaria, bloqueios de qualidade, horas extras e pedidos urgentes originados pelas lojas."
            ),
        },
        (UNIT_LOGISTICA, "followup"): {
            "questionnaire": (
                "A reavaliação contou com 120 participantes. Condições de comunicação melhoraram de forma "
                "consistente; excesso de demandas apresentou redução parcial e permaneceu sob acompanhamento."
            ),
            "activity_observation": (
                "A fila única de prioridades e a reunião de troca de turno reduziram instruções conflitantes. "
                "Em dias com atraso de fornecedor e restrição de rota, a capacidade planejada ainda foi excedida."
            ),
            "worker_dialogue": (
                "As equipes confirmaram maior clareza para bloquear exceções e pediram participação mais cedo "
                "na previsão de campanhas, dimensionamento de ondas e negociação de horários com transportadoras."
            ),
            "document_analysis": (
                "Logs do WMS, atas de passagem, justificativas de repriorização, ocupação por turno e cortes de "
                "expedição demonstraram adesão ao novo fluxo e localizaram as rotas ainda críticas."
            ),
        },
        (UNIT_DIGITAL, "baseline"): {
            "questionnaire": (
                "Questionário respondido por 90 trabalhadores de comércio digital e televendas. Baixa autonomia, "
                "excesso de demandas e condições de comunicação formaram o conjunto prioritário."
            ),
            "activity_observation": (
                "Acompanhamento de telefone, chat e aplicativos registrou múltiplas transferências, espera por "
                "alçada, alternância entre sistemas e manutenção do caso com o agente até a solução final."
            ),
            "worker_dialogue": (
                "Os agentes relacionaram retrabalho à falta de autonomia para crédito, prazo e substituição, "
                "além de critérios diferentes entre supervisores e cobrança fora do fluxo formal."
            ),
            "document_analysis": (
                "Foram examinados metas de tempo, conversão e qualidade, matriz de alçadas, scripts, escalas, "
                "transferências, reaberturas, campanhas e regras de monitoramento do atendimento."
            ),
        },
        (UNIT_DIGITAL, "followup"): {
            "questionnaire": (
                "A segunda coleta, também com 90 participantes, apontou melhora de autonomia e agravamento de "
                "assédio após a adoção de ranking nominal e comparação pública de resultados."
            ),
            "activity_observation": (
                "A árvore de decisão reduziu espera e transferência. Reuniões e canais digitais exibiram "
                "resultados nominais, comentários depreciativos e cobrança persistente sobre agentes abaixo da meta."
            ),
            "worker_dialogue": (
                "A equipe diferenciou os ganhos das novas alçadas dos efeitos do modelo de supervisão e solicitou "
                "retirada imediata do ranking nominal, mediação de conflitos e critérios transparentes."
            ),
            "document_analysis": (
                "Matriz de alçadas, taxa de transferência, critérios do ranking, atas de reunião e mensagens de "
                "gestão foram relacionados cronologicamente às duas mudanças organizacionais."
            ),
        },
    }
    return evidence[(unit_id, wave)]


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
    for unit_id in UNIT_NAMES:
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
                    "Equipe corporativa de Saúde e Segurança do Trabalho",
                    summary,
                    f"registro-interno://{campaign_id}/{unit_id}/{method}",
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
        "eliminated": "a comparação indica eliminação do perigo",
        "effective": "a melhora supera o ruído e sustenta eficácia",
        "partial": "há melhora parcial que ainda exige acompanhamento",
        "no_change": "a variação não se distingue do ruído da coorte",
        "worsened": "o resultado piorou e exige correção",
        "inconclusive": "os dados disponíveis não permitem concluir",
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
                verdict_labels.get(verdict.verdict, verdict.verdict).capitalize()
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
                " Resultado da reavaliação: "
                + verdict_labels.get(verdict.verdict, verdict.verdict)
                + ".",
                action_id, ORG_ID,
            ),
        )


def _action_plan_text(seed: dict, title: str, *, implemented: bool) -> dict:
    action = {
        "introduce": "Implantar",
        "improve": "Aprimorar",
        "maintain": "Manter e verificar",
    }.get(seed["plan_action"], "Revisar")
    unit_id = seed["unit_id"]
    factor = seed["nr1_factor"]

    measures = {
        UNIT_ATENDIMENTO: {
            "work_organization": (
                f"{action} padrão nacional para {title.lower()} nas lojas, definindo alçadas do "
                "farmacêutico e do gerente, regra de remanejamento, cobertura dos horários críticos "
                "e participação das equipes na revisão de escala e fluxo."
            ),
            "workload_demand": (
                f"{action} dimensionamento por porte e faixa horária para reduzir {title.lower()}, "
                "separar retirada digital da fila de balcão, proteger pausas e acionar cobertura "
                "regional antes que caixa, dispensação e reposição se acumulem na mesma pessoa."
            ),
            "harassment_violence": (
                f"{action} protocolo nacional para {title.lower()}, autorizando interrupção segura "
                "do atendimento, acionamento de liderança e segurança, preservação do registro da "
                "ocorrência e acolhimento do trabalhador sem cobrança de continuidade da venda."
            ),
            "environment_modality": (
                f"{action} canais de suporte relacionados a {title.lower()}, com contato regional "
                "único, redundância para falha de sistema e resposta prioritária às lojas noturnas "
                "ou operadas temporariamente com equipe reduzida."
            ),
        },
        UNIT_LOGISTICA: {
            "work_organization": (
                f"{action} governança de {title.lower()} nos centros de distribuição, definindo quem "
                "pode alterar ondas, bloquear exceções, aceitar impacto de rota e decidir sobre "
                "cadeia fria, itens controlados e pedidos urgentes."
            ),
            "workload_demand": (
                f"{action} planejamento de capacidade para reduzir {title.lower()}, incorporando "
                "previsão comercial, presença real por turno, limites das docas, horário das "
                "transportadoras e reserva operacional para avarias e redistribuições."
            ),
            "harassment_violence": (
                f"{action} resposta a {title.lower()} no recebimento e na expedição, com autoridade "
                "para suspender a operação, retirar a equipe da exposição, acionar segurança, "
                "registrar terceiros envolvidos e conduzir análise pós-incidente."
            ),
            "environment_modality": (
                f"{action} condições de {title.lower()} por meio de fila única integrada ao WMS, "
                "passagem estruturada entre turnos e confirmação formal de toda repriorização que "
                "afete separação, conferência, doca ou transporte."
            ),
        },
        UNIT_DIGITAL: {
            "work_organization": (
                f"{action} regras de {title.lower()} no atendimento digital, com alçadas claras para "
                "crédito, prazo e substituição, critérios transparentes de distribuição de filas e "
                "proibição de ranking nominal ou cobrança vexatória."
            ),
            "workload_demand": (
                f"{action} capacidade e limites para {title.lower()}, equilibrando voz, chat e "
                "aplicativos, restringindo casos simultâneos, distribuindo incidentes sistêmicos e "
                "impedindo acionamento rotineiro fora da jornada."
            ),
            "harassment_violence": (
                f"{action} prevenção e resposta a {title.lower()}, retirando comparações nominais, "
                "criando mediação independente, preservando evidências de canais digitais e "
                "protegendo quem relata conduta abusiva contra retaliação."
            ),
            "environment_modality": (
                f"{action} suporte para {title.lower()} no trabalho remoto e multicanal, com canal "
                "único de ajuda, plantão técnico, reunião regular com a liderança e atualização "
                "sincronizada de campanhas, estoque e regras de atendimento."
            ),
        },
    }
    monitoring = {
        UNIT_ATENDIMENTO: {
            "work_organization": "Revisão mensal de escalas, alçadas, remanejamentos e participação por estado e porte de loja.",
            "workload_demand": "Painel semanal de filas, cobertura, pausas adiadas, retirada digital e horas extraordinárias por faixa horária.",
            "harassment_violence": "Revisão mensal de ocorrências agregadas, tempo de acionamento, interrupção segura e acolhimento oferecido.",
            "environment_modality": "Teste trimestral dos canais de suporte e auditoria de disponibilidade em lojas noturnas e com equipe reduzida.",
        },
        UNIT_LOGISTICA: {
            "work_organization": "Revisão quinzenal de exceções, bloqueios, alterações de onda e decisões transferidas entre áreas e turnos.",
            "workload_demand": "Painel por turno de ocupação das ondas, capacidade planejada, cortes perdidos, retrabalho e horas extraordinárias.",
            "harassment_violence": "Análise mensal de incidentes com terceiros, tempo de resposta, suspensão da atividade e ações pós-incidente.",
            "environment_modality": "Auditoria semanal de divergências entre WMS, rádio, quadro da doca e registro da passagem de turno.",
        },
        UNIT_DIGITAL: {
            "work_organization": "Revisão mensal das alçadas, distribuição de filas, critérios de desempenho e decisões contestadas pela equipe.",
            "workload_demand": "Painel semanal de simultaneidade, espera, transferências, reaberturas, pausas e acionamentos fora da jornada.",
            "harassment_violence": "Acompanhamento mensal de relatos agregados, medidas de proteção, prazo de apuração e reincidência por área de gestão.",
            "environment_modality": "Teste mensal dos canais de suporte, estabilidade das integrações e contato regular de equipes remotas com a liderança.",
        },
    }
    completed_evidence = {
        UNIT_ATENDIMENTO: {
            "work_organization": "Matriz de alçadas publicada, escalas críticas revisadas e atas de consulta às equipes anexadas.",
            "workload_demand": "Cobertura regional ativada, fila digital separada e rotina de registro de pausas incorporada à gestão das lojas.",
            "harassment_violence": "Protocolo distribuído, gestores treinados e exercícios de acionamento concluídos nos três modelos de loja.",
            "environment_modality": "Canal regional único divulgado e contingência validada com unidades noturnas e de menor quadro.",
        },
        UNIT_LOGISTICA: {
            "work_organization": "Responsabilidades por exceção formalizadas e autoridade de bloqueio comunicada a todos os turnos.",
            "workload_demand": "Plano de capacidade passou a incorporar previsão comercial, presença por turno e reserva para contingências.",
            "harassment_violence": "Fluxo de suspensão, segurança, registro de terceiros e acolhimento incluído no procedimento das docas.",
            "environment_modality": "Fila única integrada ao WMS e passagem de turno com confirmação conjunta implantadas nos quatro centros.",
        },
        UNIT_DIGITAL: {
            "work_organization": "Árvore de decisão e novas alçadas publicadas; agentes e supervisores receberam orientação operacional.",
            "workload_demand": "Limites de simultaneidade configurados e célula de resolução passou a absorver pedidos críticos.",
            "harassment_violence": "Canal independente divulgado e procedimento de preservação de mensagens e proteção contra retaliação formalizado.",
            "environment_modality": "Plantão técnico, canal único e rotina de alinhamento com equipes remotas incorporados à operação.",
        },
    }
    planned_evidence = {
        "work_organization": "Entrega prevista: norma interna aprovada, matriz de responsabilidades, registro de consulta e comprovação de treinamento.",
        "workload_demand": "Entrega prevista: estudo de capacidade, escala revisada, regra de contingência e série de acompanhamento por turno.",
        "harassment_violence": "Entrega prevista: protocolo aprovado, treinamento, teste de acionamento e registro agregado das providências adotadas.",
        "environment_modality": "Entrega prevista: fluxo de comunicação publicado, teste de contingência e auditoria de adesão dos setores envolvidos.",
    }
    deadline_days = {"critical": 15, "high": 30, "moderate": 60, "low": 90}
    today = datetime.now(timezone.utc).date()
    return {
        "measure": measures[unit_id][factor],
        "evidence": completed_evidence[unit_id][factor] if implemented else planned_evidence[factor],
        "monitoring": monitoring[unit_id][factor],
        "measurement": (
            f"Comparar o resultado agregado de {title} no mesmo setor, instrumento e regra de "
            "coorte; verificar tamanho do efeito, margem e aderência operacional antes de concluir eficácia."
        ),
        "due_date": (
            today - timedelta(days=150 - min(seed["priority_rank"], 20))
            if implemented else today + timedelta(days=deadline_days[seed["risk_level"]])
        ),
        "implemented_at": datetime.now(timezone.utc) - timedelta(days=120) if implemented else None,
        "created_at": (
            datetime.now(timezone.utc) - timedelta(days=178)
            if implemented else datetime.now(timezone.utc) - timedelta(days=1)
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
                        ON CONFLICT (response_id, item_id) DO UPDATE SET
                            value=EXCLUDED.value
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
