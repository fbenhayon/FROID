# -*- coding: utf-8 -*-
"""Migration 053: o supervisor clinico na agenda, o nome do paciente e as
listagens do painel. Prova contra PostgreSQL real e descartavel.

Decisoes do dono (18/10/2026): o supervisor ve a agenda inteira e marca,
reagenda e cancela atendimentos dos profissionais; o nome do paciente aparece
para secretaria, administrador e o proprio clinico — nao para o supervisor.
"""

from __future__ import annotations

import secrets
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psique_billing import BillingError  # noqa: E402
from psique_credits import PsiqueCredits  # noqa: E402
from psique_identity import TrialKeyring  # noqa: E402
from psique_rbac import PsiqueRbac  # noqa: E402
from psique_scheduling import PsiqueScheduling  # noqa: E402
from tenant_access import AccessContext  # noqa: E402
from tools.migrate_schema import apply  # noqa: E402

MIGRACAO = "053_psique_scheduling_supervisor"
ANTERIOR = "052_psique_member_quota_v2"
SP = ZoneInfo("America/Sao_Paulo")
BASE_START = datetime(2027, 3, 10, 14, 0, tzinfo=SP)
BASE_DOW = (BASE_START.weekday() + 1) % 7


def _dsn():
    import os

    dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("explicit disposable Psique database required")
    from psycopg.conninfo import conninfo_to_dict

    params = conninfo_to_dict(dsn)
    assert params.get("host") in {"127.0.0.1", "localhost"}
    assert params.get("dbname", "").startswith("psique_v2_test_")
    return dsn


def _banco(dsn, through):
    import psycopg
    from psycopg.conninfo import make_conninfo

    name = "psique_v2_test_" + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        try:
            isolated = make_conninfo(dsn, dbname=name)
            with psycopg.connect(isolated, autocommit=True) as conn:
                apply(conn, ROOT / "migrations", through, name)
            yield isolated, name
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


@pytest.fixture(scope="module")
def database():
    yield from _banco(_dsn(), MIGRACAO)


class Harness:
    def __init__(self, dsn):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        factory = lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime")
        self.rbac = PsiqueRbac(factory)
        self.scheduling = PsiqueScheduling(factory)
        self.credits = PsiqueCredits(factory, identity_loader=lambda u: None,
                                     material_loader=lambda user, ref: None,
                                     keyring=TrialKeyring({"t": secrets.token_bytes(32)}, "t"))

    def sql(self, query, params=()):
        with self.pg.connect(self.dsn, autocommit=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def member(self, org, *, v1_role="professional"):
        user, membership = str(uuid.uuid4()), str(uuid.uuid4())
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (membership, org, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,%s)", (membership, v1_role))
        return AccessContext.create(organization_id=org, membership_id=membership, user_id=user,
                                    roles=[v1_role], organization_type="clinic")

    def clinica(self):
        org = str(uuid.uuid4())
        self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                 "VALUES(%s,'clinic','SYNTHETIC agenda','SYNTHETIC agenda')", (org,))
        owner = self.member(org, v1_role="owner")
        assert self.rbac.enable(owner)["enabled"] is True
        secretary = self.member(org)
        self.rbac.grant_role(owner, secretary.membership_id, "SECRETARY")
        supervisor = self.member(org, v1_role="supervisor")
        self.rbac.grant_role(owner, supervisor.membership_id, "CLINICAL_SUPERVISOR")
        clinician = self.clinico(owner)
        return owner, secretary, supervisor, clinician

    def clinico(self, owner):
        clinician = self.member(owner.organization_id)
        self.rbac.grant_role(owner, clinician.membership_id, "CLINICIAN")
        self.scheduling.set_availability(
            owner, clinician_membership_id=clinician.membership_id, weekday=BASE_DOW,
            start_minute=8 * 60, end_minute=18 * 60, timezone_name="America/Sao_Paulo")
        return clinician

    def paciente(self, org, nome="SYNTHETIC PACIENTE"):
        patient = str(uuid.uuid4())
        self.sql("INSERT INTO patients(id,organization_id,full_name,legacy_payload) "
                 "VALUES(%s,%s,%s,'{}')", (patient, org, nome))
        return patient

    def marcar(self, actor, clinician, patient, *, offset_minutes=0, minutes=50):
        start = BASE_START + timedelta(minutes=offset_minutes)
        return self.scheduling.create_appointment(
            actor, patient_id=patient, clinician_membership_id=clinician.membership_id,
            start_at=start, end_at=start + timedelta(minutes=minutes),
            timezone_name="America/Sao_Paulo", idempotency_key=uuid.uuid4().hex)

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
    assert h.scheduling.list_patients(clinician)["with_names"] is True


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

def _funcao(texto, nome):
    inicio = texto.index(f"FUNCTION {nome}(")
    inicio = texto.rindex("CREATE", 0, inicio)
    fim = texto.index("END $$;", inicio) + len("END $$;")
    return texto[inicio:fim].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1).replace("\r\n", "\n")


def test_a_053_copia_as_funcoes_correntes_e_so_acrescenta_o_supervisor():
    sql053 = (ROOT / "migrations" / f"{MIGRACAO}.sql").read_text(encoding="utf-8").replace("\r\n", "\n")
    sql045 = (ROOT / "migrations" / "045_psique_scheduling_serialization.sql").read_text(encoding="utf-8")
    sql044 = (ROOT / "migrations" / "044_psique_org_scheduling.sql").read_text(encoding="utf-8")
    fontes = {
        "psique_v2_appointment_create": sql045,
        "psique_v2_appointment_change": sql045,
        "psique_v2_appointment_cancel": sql044,
        "psique_v2_appointment_history": sql044,
    }
    for nome, fonte in fontes.items():
        esperado = (_funcao(fonte, nome)
                    .replace("ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']",
                             "ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']")
                    .replace("psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])",
                             "psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR'])"))
        assert _funcao(sql053, nome) == esperado, nome
    listagem = _funcao(sql053, "psique_v2_appointments_list")
    assert "'patient_name',CASE WHEN psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])" in listagem
    assert "LEFT JOIN patients p" in listagem


def test_aplica_incremental_sobre_a_052_e_reaplicar_e_no_op():
    import psycopg

    gerador = _banco(_dsn(), ANTERIOR)
    isolated, name = next(gerador)
    try:
        with psycopg.connect(isolated, autocommit=True) as conn:
            assert apply(conn, ROOT / "migrations", MIGRACAO, name) == [MIGRACAO]
            assert apply(conn, ROOT / "migrations", MIGRACAO, name) == []
    finally:
        try:
            next(gerador)
        except StopIteration:
            pass


def test_053_e_opt_in():
    from froid_schema import PSIQUE_V2_VERSIONS

    assert MIGRACAO in PSIQUE_V2_VERSIONS
