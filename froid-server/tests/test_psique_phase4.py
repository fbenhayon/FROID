"""Phase 4 acceptance: organizational scheduling on real PostgreSQL.

The internal Appointment is the authority: double-booking is forbidden by an
exclusion constraint in the database itself; the Google mirror is an outbox
whose failure is visible state and never touches the booking. Every actor
probe runs through the SECURITY DEFINER boundary as froid_runtime.
"""

import re
import secrets
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psique_billing import BillingError
from psique_credits import PsiqueCredits
from psique_identity import AuthorizedMaterial, TrialKeyring
from psique_rbac import PsiqueRbac
from psique_scheduling import (
    APPOINTMENT_EVENT_KINDS,
    APPOINTMENT_STATUSES,
    OUTBOX_OPERATIONS,
    OUTBOX_STATUSES,
    PsiqueScheduling,
)
from tenant_access import AccessContext
from tools.migrate_schema import apply

SP = ZoneInfo("America/Sao_Paulo")
BASE_START = datetime(2027, 3, 10, 14, 0, tzinfo=SP)  # quarta-feira, 14h em SP
BASE_DOW = (BASE_START.weekday() + 1) % 7  # DOW do PostgreSQL: domingo=0


def test_migration_044_domains_mirror_module_constants():
    sql = (ROOT / "migrations/044_psique_org_scheduling.sql").read_text(encoding="utf-8")
    def domain(column):
        match = re.search(column + r" IN\s*\n?\s*\(([^)]*)\)", sql)
        return set(re.findall(r"'([A-Z_]+)'", match.group(1)))
    assert domain("appointment_status") == set(APPOINTMENT_STATUSES)
    assert domain("event_kind") == set(APPOINTMENT_EVENT_KINDS)
    assert domain("outbox_status") == set(OUTBOX_STATUSES)
    assert domain("operation") == set(OUTBOX_OPERATIONS)


@pytest.fixture(scope="module")
def database():
    import os

    dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("explicit disposable Psique database required")
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(dsn)
    assert params.get("host") in {"127.0.0.1", "localhost"}
    assert params.get("dbname", "").startswith("psique_v2_test_")
    name = "psique_v2_test_" + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname='froid_runtime'").fetchone()
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        try:
            isolated = make_conninfo(dsn, dbname=name)
            with psycopg.connect(isolated, autocommit=True) as conn:
                apply(conn, ROOT / "migrations", "045_psique_scheduling_serialization", name)
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


class Harness:
    def __init__(self, dsn):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        self.materials = {}
        factory = lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime")
        self.rbac = PsiqueRbac(factory)
        self.scheduling = PsiqueScheduling(factory)
        self.credits = PsiqueCredits(
            factory, identity_loader=lambda u: None,
            material_loader=lambda user, ref: self.materials[ref],
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

    def clinic(self):
        """V2 org with owner(ORG_ADMIN), secretary, and one available clinician."""
        org = str(uuid.uuid4())
        self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                 "VALUES(%s,'clinic','SYNTHETIC agenda','SYNTHETIC agenda')", (org,))
        owner = self.member(org, v1_role="owner")
        assert self.rbac.enable(owner)["enabled"] is True
        secretary = self.member(org)
        self.rbac.grant_role(owner, secretary.membership_id, "SECRETARY")
        clinician = self.member(org)
        self.rbac.grant_role(owner, clinician.membership_id, "CLINICIAN")
        self.scheduling.set_availability(
            owner, clinician_membership_id=clinician.membership_id, weekday=BASE_DOW,
            start_minute=8 * 60, end_minute=18 * 60, timezone_name="America/Sao_Paulo")
        return owner, secretary, clinician

    def patient(self, org):
        patient = str(uuid.uuid4())
        self.sql("INSERT INTO patients(id,organization_id,full_name,legacy_payload) "
                 "VALUES(%s,%s,'SYNTHETIC PACIENTE','{\"clinico\":\"SYNTHETIC\"}')", (patient, org))
        return patient

    def book(self, actor, clinician, patient, *, offset_minutes=0, minutes=50, idem=None):
        start = BASE_START + timedelta(minutes=offset_minutes)
        return self.scheduling.create_appointment(
            actor, patient_id=patient, clinician_membership_id=clinician.membership_id,
            start_at=start, end_at=start + timedelta(minutes=minutes),
            timezone_name="America/Sao_Paulo", idempotency_key=idem or uuid.uuid4().hex)

    def outbox_rows(self, org):
        return self.sql("SELECT operation,outbox_status,payload FROM psique_calendar_outbox "
                        "WHERE organization_id=%s ORDER BY created_at", (org,))


@pytest.fixture
def harness(database):
    return Harness(database)


def race(*functions):
    barrier = threading.Barrier(len(functions))

    def run(fn):
        barrier.wait(timeout=10)
        try:
            return fn()
        except BillingError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return [f.result(timeout=30) for f in [pool.submit(run, fn) for fn in functions]]


# -- Authority, roles and clinical boundary -------------------------------------

def test_serialization_functions_stay_in_sync_with_044():
    """Espelho de codigo: a 045 embute as funcoes da 044 com UMA adicao (o
    advisory lock por clinico). Editar a 044 sem regravar a 045 quebra aqui."""
    sql045 = (ROOT / "migrations/045_psique_scheduling_serialization.sql").read_text(encoding="utf-8")
    sql044 = (ROOT / "migrations/044_psique_org_scheduling.sql").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock(hashtextextended('psique_agenda:'||clinician::text, 0))" in sql045
    assert "pg_advisory_xact_lock(hashtextextended('psique_agenda:'||appointment.clinician_membership_id::text, 0))" in sql045
    sem_lock = "\n".join(linha for linha in sql045.splitlines()
                          if "advisory" not in linha and "deadlock" not in linha
                          and "40P01" not in linha and not linha.strip().startswith("--"))
    for nome in ("psique_v2_appointment_create", "psique_v2_appointment_change"):
        inicio = sql044.index(f"CREATE FUNCTION {nome}")
        fim = sql044.index("END $$;", inicio) + len("END $$;")
        corpo = sql044[inicio:fim].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
        corpo_sem_comentarios = "\n".join(l for l in corpo.splitlines()
                                           if not l.strip().startswith("--"))
        assert corpo_sem_comentarios in sem_lock, nome


def test_scheduling_requires_rbac_v2(harness):
    h = harness
    org = str(uuid.uuid4())
    h.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
          "VALUES(%s,'clinic','SYNTHETIC v1','SYNTHETIC v1')", (org,))
    owner = h.member(org, v1_role="owner")
    with pytest.raises(BillingError, match="RBAC_V2_NOT_ENABLED"):
        h.scheduling.list_appointments(owner, from_at=BASE_START,
                                       to_at=BASE_START + timedelta(days=1))


def test_secretary_books_reschedules_and_cancels_without_clinical_content(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    created = h.book(secretary, clinician, patient)
    assert created["created"] is True and created["appointment_status"] == "SCHEDULED"
    moved = h.scheduling.change_appointment(
        secretary, appointment_id=created["appointment_id"],
        expected_version=created["version"],
        start_at=BASE_START + timedelta(hours=1),
        end_at=BASE_START + timedelta(hours=1, minutes=50))
    assert moved["applied"] is True and moved["version"] == 2
    cancelled = h.scheduling.cancel_appointment(
        secretary, appointment_id=created["appointment_id"],
        expected_version=moved["version"], reason="SYNTHETIC remarcado pelo paciente")
    assert cancelled["applied"] is True and cancelled["appointment_status"] == "CANCELLED"
    # O registro permanece; nada foi apagado.
    assert h.sql("SELECT appointment_status FROM psique_appointments WHERE id=%s",
                 (created["appointment_id"],))[0][0] == "CANCELLED"
    history = h.scheduling.appointment_history(secretary, created["appointment_id"])
    kinds = [event["event_kind"] for event in history["events"]]
    assert kinds == ["CREATED", "RESCHEDULED", "CANCELLED"]
    assert history["events"][1]["previous_state"]["version"] == 1
    # Trilha e espelho carregam somente dados administrativos.
    for event in history["events"]:
        blob = str(event)
        assert "PACIENTE" not in blob and "legacy_payload" not in blob and "patient_id" not in blob
    operations = [row[0] for row in h.outbox_rows(owner.organization_id)]
    assert operations == ["UPSERT", "UPSERT", "CANCEL"]
    for _, _, payload in h.outbox_rows(owner.organization_id):
        assert "patient_id" not in payload and "PACIENTE" not in str(payload)


def test_clinician_owns_their_agenda_and_secretary_sees_all(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    other = h.member(owner.organization_id)
    h.rbac.grant_role(owner, other.membership_id, "CLINICIAN")
    h.scheduling.set_availability(owner, clinician_membership_id=other.membership_id,
                                  weekday=BASE_DOW, start_minute=8 * 60, end_minute=18 * 60,
                                  timezone_name="America/Sao_Paulo")
    patient = h.patient(owner.organization_id)
    mine = h.book(clinician, clinician, patient)
    theirs = h.book(secretary, other, patient, offset_minutes=120)
    window = {"from_at": BASE_START - timedelta(hours=1), "to_at": BASE_START + timedelta(hours=6)}
    own_view = h.scheduling.list_appointments(clinician, **window)["appointments"]
    assert {a["appointment_id"] for a in own_view} == {mine["appointment_id"]}
    staff_view = h.scheduling.list_appointments(secretary, **window)["appointments"]
    assert {a["appointment_id"] for a in staff_view} == {mine["appointment_id"], theirs["appointment_id"]}
    with pytest.raises(BillingError, match="OWN_AGENDA_ONLY"):
        h.book(clinician, other, patient, offset_minutes=240)
    with pytest.raises(BillingError, match="OWN_AGENDA_ONLY"):
        h.scheduling.cancel_appointment(clinician, appointment_id=theirs["appointment_id"],
                                        expected_version=theirs["version"], reason="x")


def test_double_booking_is_impossible_and_cancel_frees_the_slot(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    first = h.book(secretary, clinician, patient)
    with pytest.raises(BillingError, match="APPOINTMENT_CONFLICT"):
        h.book(secretary, clinician, patient, offset_minutes=25)  # sobrepoe
    other = h.member(owner.organization_id)
    h.rbac.grant_role(owner, other.membership_id, "CLINICIAN")
    h.scheduling.set_availability(owner, clinician_membership_id=other.membership_id,
                                  weekday=BASE_DOW, start_minute=8 * 60, end_minute=18 * 60,
                                  timezone_name="America/Sao_Paulo")
    assert h.book(secretary, other, patient, offset_minutes=25)["created"] is True
    h.scheduling.cancel_appointment(secretary, appointment_id=first["appointment_id"],
                                    expected_version=first["version"], reason="abre o horario")
    assert h.book(secretary, clinician, patient, offset_minutes=25)["created"] is True


def test_outside_availability_is_refused_and_own_availability_rules(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    with pytest.raises(BillingError, match="OUTSIDE_AVAILABILITY"):
        h.book(secretary, clinician, patient, offset_minutes=5 * 60)  # 19h > 18h
    with pytest.raises(BillingError, match="OUTSIDE_AVAILABILITY"):
        start = BASE_START + timedelta(days=1)  # quinta: sem slot
        h.scheduling.create_appointment(
            secretary, patient_id=patient, clinician_membership_id=clinician.membership_id,
            start_at=start, end_at=start + timedelta(minutes=50),
            timezone_name="America/Sao_Paulo", idempotency_key=uuid.uuid4().hex)
    other = h.member(owner.organization_id)
    h.rbac.grant_role(owner, other.membership_id, "CLINICIAN")
    assert h.scheduling.set_availability(
        other, clinician_membership_id=other.membership_id, weekday=BASE_DOW,
        start_minute=8 * 60, end_minute=12 * 60,
        timezone_name="America/Sao_Paulo")["changed"] is True
    with pytest.raises(BillingError, match="OWN_AVAILABILITY_ONLY"):
        h.scheduling.set_availability(other, clinician_membership_id=clinician.membership_id,
                                      weekday=BASE_DOW, start_minute=8 * 60, end_minute=12 * 60,
                                      timezone_name="America/Sao_Paulo")
    with pytest.raises(BillingError, match="AVAILABILITY_CLINICIAN_REQUIRED"):
        h.scheduling.set_availability(owner, clinician_membership_id=secretary.membership_id,
                                      weekday=BASE_DOW, start_minute=8 * 60, end_minute=12 * 60,
                                      timezone_name="America/Sao_Paulo")


def test_idempotent_create_and_version_conflicts(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    first = h.book(secretary, clinician, patient, idem="mesma-chave")
    again = h.book(secretary, clinician, patient, idem="mesma-chave")
    assert again["created"] is False and again["appointment_id"] == first["appointment_id"]
    stale = h.scheduling.change_appointment(
        secretary, appointment_id=first["appointment_id"], expected_version=99,
        appointment_status="CONFIRMED")
    assert stale["applied"] is False and stale["code"] == "APPOINTMENT_VERSION_CONFLICT"
    ok = h.scheduling.change_appointment(
        secretary, appointment_id=first["appointment_id"],
        expected_version=first["version"], appointment_status="CONFIRMED")
    assert ok["applied"] is True and ok["appointment_status"] == "CONFIRMED"
    done = h.scheduling.change_appointment(
        secretary, appointment_id=first["appointment_id"],
        expected_version=ok["version"], appointment_status="COMPLETED")
    assert done["applied"] is True
    terminal = h.scheduling.change_appointment(
        secretary, appointment_id=first["appointment_id"],
        expected_version=done["version"], appointment_status="CONFIRMED")
    assert terminal["applied"] is False and terminal["code"] == "APPOINTMENT_TERMINAL"


def test_session_link_belongs_to_the_appointment_clinician_only(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    booked = h.book(secretary, clinician, patient)
    h.credits.enroll_empty_wallet(owner)
    reference = uuid.uuid4().hex
    h.materials[reference] = AuthorizedMaterial(
        str(uuid.uuid4()), owner.organization_id, clinician.user_id,
        "SYNTHETIC-sessao-" + reference, "stream", None)
    source = h.credits.register_source(clinician, reference)["analysis_source_id"]
    with pytest.raises(BillingError, match="PSIQUE_SCHEDULING_ROLE_DENIED"):
        h.scheduling.link_source(secretary, appointment_id=booked["appointment_id"],
                                 analysis_source_id=source)
    other = h.member(owner.organization_id)
    h.rbac.grant_role(owner, other.membership_id, "CLINICIAN")
    with pytest.raises(BillingError, match="APPOINTMENT_ACCESS_DENIED"):
        h.scheduling.link_source(other, appointment_id=booked["appointment_id"],
                                 analysis_source_id=source)
    linked = h.scheduling.link_source(clinician, appointment_id=booked["appointment_id"],
                                      analysis_source_id=source)
    assert linked["linked"] is True
    duplicate = h.scheduling.link_source(clinician, appointment_id=booked["appointment_id"],
                                         analysis_source_id=source)
    assert duplicate["linked"] is False


def test_mirror_failure_is_visible_and_never_touches_the_booking(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    booked = h.book(secretary, clinician, patient)
    taken = h.scheduling.outbox_take(owner, how_many=5)["items"]
    assert len(taken) == 1 and taken[0]["attempts"] == 1
    settled = h.scheduling.outbox_settle(
        owner, outbox_id=taken[0]["outbox_id"], delivered=False,
        error_note="SYNTHETIC google indisponivel")
    assert settled["outbox_status"] == "FAILED"
    status = h.scheduling.calendar_sync_status(secretary)
    assert status["failed"] == 1 and status["pending"] == 0
    assert status["failures"][0]["last_error_sanitized"] == "SYNTHETIC google indisponivel"
    row = h.sql("SELECT appointment_status,version FROM psique_appointments WHERE id=%s",
                (booked["appointment_id"],))[0]
    assert row == ("SCHEDULED", 1)  # o espelho falhou; a autoridade nao se moveu
    retaken = h.scheduling.outbox_take(owner, how_many=5)["items"]
    assert retaken == []  # FAILED nao volta sozinho para a fila; reprocesso e decisao


def test_outbox_take_is_concurrent_safe_and_delivery_is_idempotent(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    for offset in (0, 60, 120):
        h.book(secretary, clinician, patient, offset_minutes=offset)
    outcomes = race(lambda: h.scheduling.outbox_take(owner, how_many=2),
                    lambda: h.scheduling.outbox_take(owner, how_many=2))
    ids = [item["outbox_id"] for outcome in outcomes if isinstance(outcome, dict)
           for item in outcome["items"]]
    assert len(ids) == len(set(ids)) == 3
    first = ids[0]
    assert h.scheduling.outbox_settle(owner, outbox_id=first, delivered=True,
                                      external_event_id="SYNTHETICevt")["outbox_status"] == "DELIVERED"
    assert h.scheduling.outbox_settle(owner, outbox_id=first, delivered=True)["settled"] is False


def test_concurrent_bookings_for_the_same_slot_yield_exactly_one(harness):
    h = harness
    owner, secretary, clinician = h.clinic()
    patient = h.patient(owner.organization_id)
    outcomes = race(lambda: h.book(secretary, clinician, patient, offset_minutes=180),
                    lambda: h.book(secretary, clinician, patient, offset_minutes=180))
    created = [o for o in outcomes if isinstance(o, dict) and o.get("created")]
    conflicts = [o for o in outcomes if o == "APPOINTMENT_CONFLICT"]
    assert len(created) == 1 and len(conflicts) == 1
    count = h.sql("SELECT count(*) FROM psique_appointments WHERE organization_id=%s "
                  "AND clinician_membership_id=%s AND appointment_status='SCHEDULED'",
                  (owner.organization_id, clinician.membership_id))[0][0]
    assert count == 1
