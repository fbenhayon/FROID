# -*- coding: utf-8 -*-
"""Migration 053: o supervisor clinico na agenda, o nome do paciente e as
listagens do painel. Prova contra PostgreSQL real e descartavel.

Decisoes do dono (18/10/2026): o supervisor ve a agenda inteira e marca,
reagenda e cancela atendimentos dos profissionais; o nome do paciente aparece
para secretaria, administrador e o proprio clinico — nao para o supervisor.

Decisao do dono (20/10/2026, revisao pre-fase 5, item 2): na listagem de
pacientes o clinico recebe o nome so dos pacientes atribuidos a ele ou com
atendimento dele; os demais saem por identificador curto (a 053 dava a
qualquer clinico o nome de todos, mais que o papel V1 professional le).
"""

from __future__ import annotations

import sys
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psique_billing import BillingError  # noqa: E402
from psique_harness import (  # noqa: E402
    BASE_START,
    HarnessBase,
    aplica_incremental_e_reaplicar_e_no_op,
    definicao_corrente,
    fixture_de_banco,
    funcao_sql,
)

MIGRACAO = "053_psique_scheduling_supervisor"
ANTERIOR = "052_psique_member_quota_v2"
# A 054 regrava psique_v2_scheduling_patients (nome so dos pacientes do
# clinico); o banco de prova aplica ate ela, e o espelho da 053 segue aqui.
CORRENTE = "054_cota_conta_e_paciente_do_clinico"


database = fixture_de_banco(CORRENTE)


class Harness(HarnessBase):
    """O que so este modulo precisa: a clinica com os quatro papeis."""

    def clinica(self):
        org = self.organizacao("clinic", "SYNTHETIC agenda")
        owner = self.member(org, v1_role="owner")
        assert self.rbac.enable(owner)["enabled"] is True
        secretary = self.member(org)
        self.rbac.grant_role(owner, secretary.membership_id, "SECRETARY")
        supervisor = self.member(org, v1_role="supervisor")
        self.rbac.grant_role(owner, supervisor.membership_id, "CLINICAL_SUPERVISOR")
        clinician = self.clinico_disponivel(owner)
        return owner, secretary, supervisor, clinician

    def clinico(self, owner):
        return self.clinico_disponivel(owner)

    def paciente(self, org, nome="SYNTHETIC PACIENTE"):
        return self.patient(org, nome)

    def agenda(self, actor):
        return self.scheduling.list_appointments(
            actor, from_at=BASE_START - timedelta(hours=1), to_at=BASE_START + timedelta(hours=8))["appointments"]


@pytest.fixture
def harness(database):
    return Harness(database[0])


# -- O supervisor -----------------------------------------------------------------

def test_supervisor_marca_reagenda_e_cancela_para_qualquer_clinico(harness):
    h = harness
    owner, _secretary, supervisor, clinician = h.clinica()
    outro = h.clinico(owner)
    patient = h.paciente(owner.organization_id)
    a = h.marcar(supervisor, clinician, patient)
    b = h.marcar(supervisor, outro, patient, offset_minutes=120)
    assert a["created"] and b["created"]
    mudado = h.scheduling.change_appointment(
        supervisor, appointment_id=a["appointment_id"], expected_version=a["version"],
        start_at=BASE_START + timedelta(minutes=60), end_at=BASE_START + timedelta(minutes=110))
    assert mudado["applied"] is True
    cancelado = h.scheduling.cancel_appointment(
        supervisor, appointment_id=b["appointment_id"], expected_version=b["version"], reason="x")
    assert cancelado["applied"] is True
    assert {x["appointment_id"] for x in h.agenda(supervisor)} == {a["appointment_id"], b["appointment_id"]}
    historia = h.scheduling.appointment_history(supervisor, a["appointment_id"])["events"]
    assert [e["event_kind"] for e in historia] == ["CREATED", "RESCHEDULED"]


def test_clinico_continua_so_na_propria_agenda(harness):
    h = harness
    owner, _secretary, _supervisor, clinician = h.clinica()
    outro = h.clinico(owner)
    patient = h.paciente(owner.organization_id)
    with pytest.raises(BillingError, match="OWN_AGENDA_ONLY"):
        h.marcar(clinician, outro, patient)


def test_quem_sem_papel_de_agenda_e_recusado(harness):
    h = harness
    owner, _s, _sup, clinician = h.clinica()
    financeiro = h.member(owner.organization_id)
    h.rbac.grant_role(owner, financeiro.membership_id, "FINANCE")
    patient = h.paciente(owner.organization_id)
    with pytest.raises(BillingError, match="PSIQUE_SCHEDULING_ROLE_DENIED"):
        h.marcar(financeiro, clinician, patient)


# -- O nome do paciente ------------------------------------------------------------

def test_nome_para_secretaria_administrador_e_clinico_nunca_para_o_supervisor(harness):
    h = harness
    owner, secretary, supervisor, clinician = h.clinica()
    outro = h.clinico(owner)
    patient = h.paciente(owner.organization_id, "SYNTHETIC MARIA")
    h.marcar(secretary, clinician, patient)
    h.marcar(secretary, outro, patient, offset_minutes=120)

    def nomes(actor):
        return {x["clinician_membership_id"]: x["patient_name"] for x in h.agenda(actor)}

    assert set(nomes(secretary).values()) == {"SYNTHETIC MARIA"}
    assert set(nomes(owner).values()) == {"SYNTHETIC MARIA"}
    assert set(nomes(supervisor).values()) == {None}
    proprios = nomes(clinician)
    assert proprios == {clinician.membership_id: "SYNTHETIC MARIA"}


def test_listagens_do_painel(harness):
    h = harness
    owner, secretary, supervisor, clinician = h.clinica()
    h.paciente(owner.organization_id, "SYNTHETIC ANA")
    clinicos = h.scheduling.list_clinicians(secretary)["clinicians"]
    assert [c["membership_id"] for c in clinicos] == [clinician.membership_id]
    assert clinicos[0]["availability"][0]["start_minute"] == 8 * 60
    assert clinicos[0]["availability"][0]["timezone"] == "America/Sao_Paulo"
    com_nome = h.scheduling.list_patients(secretary)
    assert com_nome["with_names"] is True
    assert com_nome["patients"][0]["label"] == "SYNTHETIC ANA"
    sem_nome = h.scheduling.list_patients(supervisor)
    assert sem_nome["with_names"] is False
    assert sem_nome["patients"][0]["label"].startswith("Paciente ")
    assert "ANA" not in sem_nome["patients"][0]["label"]
    # 054: o clinico sem paciente atribuido nem atendimento ve so identificadores.
    do_clinico = h.scheduling.list_patients(clinician)
    assert do_clinico["with_names"] is True and do_clinico["names_scope"] == "own"
    assert do_clinico["patients"][0]["label"].startswith("Paciente ")
    assert com_nome["names_scope"] == "all" and sem_nome["names_scope"] == "none"


def test_o_clinico_ve_o_nome_so_dos_pacientes_dele(harness):
    """Teste negativo da 054: dois clinicos, um paciente atribuido a cada um e
    um terceiro sem vinculo. Cada clinico le o nome do seu — por atribuicao
    (patient_assignments) ou por atendimento marcado — e identificador dos
    outros. Secretaria e administrador seguem lendo todos."""
    h = harness
    owner, secretary, supervisor, clinician = h.clinica()
    outro = h.clinico(owner)
    org = owner.organization_id
    atribuido = h.paciente(org, "SYNTHETIC ATRIBUIDO")
    atendido = h.paciente(org, "SYNTHETIC ATENDIDO")
    alheio = h.paciente(org, "SYNTHETIC ALHEIO")
    h.sql("INSERT INTO patient_assignments(id,organization_id,patient_id,membership_id) "
          "VALUES(%s,%s,%s,%s)", (str(uuid.uuid4()), org, atribuido, clinician.membership_id))
    h.marcar(secretary, outro, atendido)

    def rotulos(actor):
        return {p["patient_id"]: p["label"] for p in h.scheduling.list_patients(actor)["patients"]}

    do_clinico = rotulos(clinician)
    assert do_clinico[atribuido] == "SYNTHETIC ATRIBUIDO"
    assert do_clinico[atendido].startswith("Paciente ") and "ATENDIDO" not in do_clinico[atendido]
    assert do_clinico[alheio].startswith("Paciente ") and "ALHEIO" not in do_clinico[alheio]
    do_outro = rotulos(outro)
    assert do_outro[atendido] == "SYNTHETIC ATENDIDO"
    assert "ATRIBUIDO" not in do_outro[atribuido] and "ALHEIO" not in do_outro[alheio]
    # Atribuicao revogada deixa de dar o nome.
    h.sql("UPDATE patient_assignments SET status='revoked', revoked_at=now() WHERE patient_id=%s", (atribuido,))
    assert "ATRIBUIDO" not in rotulos(clinician)[atribuido]
    assert set(rotulos(secretary).values()) == {"SYNTHETIC ATRIBUIDO", "SYNTHETIC ATENDIDO", "SYNTHETIC ALHEIO"}
    assert set(rotulos(owner).values()) == set(rotulos(secretary).values())
    assert all(r.startswith("Paciente ") for r in rotulos(supervisor).values())


def test_quem_gere_papeis_ve_os_papeis_de_todos(harness):
    h = harness
    owner, secretary, supervisor, clinician = h.clinica()
    membros = {m["membership_id"]: m["v2_roles"] for m in h.rbac.list_role_grants(owner)["members"]}
    assert membros[secretary.membership_id] == ["SECRETARY"]
    assert membros[supervisor.membership_id] == ["CLINICAL_SUPERVISOR"]
    assert membros[clinician.membership_id] == ["CLINICIAN"]
    assert "ORG_ADMIN" in membros[owner.membership_id]
    with pytest.raises(BillingError, match="PSIQUE_SCHEDULING_ROLE_DENIED"):
        h.rbac.list_role_grants(secretary)


# -- A migration ---------------------------------------------------------------------

def test_a_053_copia_as_funcoes_correntes_e_so_acrescenta_o_supervisor():
    """A fonte de cada funcao e a ULTIMA migration anterior a 053 que a define
    (item 25): uma migration intermediaria que a regravasse apareceria aqui."""
    sql053 = (ROOT / "migrations" / f"{MIGRACAO}.sql").read_text(encoding="utf-8")
    for nome in ("psique_v2_appointment_create", "psique_v2_appointment_change",
                 "psique_v2_appointment_cancel", "psique_v2_appointment_history"):
        origem, corrente = definicao_corrente(nome, antes_de=MIGRACAO)
        assert origem in ("044_psique_org_scheduling", "045_psique_scheduling_serialization"), (nome, origem)
        esperado = (corrente
                    .replace("ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']",
                             "ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']")
                    .replace("psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])",
                             "psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR'])"))
        assert funcao_sql(sql053, nome) == esperado, nome
    listagem = funcao_sql(sql053, "psique_v2_appointments_list")
    assert "'patient_name',CASE WHEN psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])" in listagem
    assert "LEFT JOIN patients p" in listagem


def test_a_054_copia_a_listagem_de_pacientes_da_053_e_so_restringe_o_clinico():
    sql053 = (ROOT / "migrations" / f"{MIGRACAO}.sql").read_text(encoding="utf-8")
    sql054 = (ROOT / "migrations" / f"{CORRENTE}.sql").read_text(encoding="utf-8")
    antiga = funcao_sql(sql053, "psique_v2_scheduling_patients")
    nova = funcao_sql(sql054, "psique_v2_scheduling_patients")
    assert nova != antiga
    assert "psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])" in nova
    assert "psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN'])" not in nova
    assert "pa.membership_id=member AND pa.status='active'" in nova
    assert "ap.clinician_membership_id=member" in nova
    assert "'names_scope',escopo" in nova
    # Fora do trecho do nome, a funcao e a mesma: o ORDER BY e o filtro de ativos.
    assert "WHERE p.organization_id=org AND p.status='active'" in nova
    assert "ORDER BY CASE WHEN com_nome THEN p.full_name ELSE p.id::text END" in nova


def test_aplica_incremental_sobre_a_052_e_reaplicar_e_no_op():
    aplica_incremental_e_reaplicar_e_no_op(ANTERIOR, MIGRACAO)


def test_053_e_opt_in():
    from froid_schema import PSIQUE_V2_VERSIONS

    assert MIGRACAO in PSIQUE_V2_VERSIONS
