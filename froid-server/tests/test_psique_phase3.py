"""Phase 3 acceptance: RBAC V2 on real PostgreSQL row level security.

Every probe below runs as the restricted froid_runtime role with the GUC
context of a synthetic member, so what is asserted is what the database
actually returns to that member — not what a Python layer promises.
"""

import re
import secrets
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psique_billing import BillingError
from psique_credits import PsiqueCredits
from psique_identity import TrialKeyring
from psique_license import PsiqueLicense
from psique_rbac import V2_ROLES, PsiqueRbac
from tenant_access import AccessContext
from tools.migrate_schema import apply


def test_migration_role_domain_mirrors_module_and_excludes_superadmin():
    sql = (ROOT / "migrations/042_psique_rbac_v2.sql").read_text(encoding="utf-8")
    match = re.search(r"v2_role IN\s*\(([^)]*)\)", sql)
    domain = set(re.findall(r"'([A-Z_]+)'", match.group(1)))
    assert domain == set(V2_ROLES)
    assert "SUPERADMIN" not in domain  # excecao de plataforma, nunca organizacional


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
                apply(conn, ROOT / "migrations", "042_psique_rbac_v2", name)
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


class Harness:
    def __init__(self, dsn):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        factory = lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime")
        self.rbac = PsiqueRbac(factory)
        self.license = PsiqueLicense(
            factory, stripe_client=None, account_id="acct_SYNTHETICrbac",
            billing_email_resolver=lambda ctx: "SYNTHETIC@example.invalid")
        self.credits = PsiqueCredits(
            factory, identity_loader=lambda u: None, material_loader=lambda u, r: None,
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

    def org(self, *, org_type="clinic"):
        org = str(uuid.uuid4())
        self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                 "VALUES(%s,%s,'SYNTHETIC rbac','SYNTHETIC rbac')", (org, org_type))
        return self.member(org, v1_role="owner")

    def v2_org(self):
        """Owner-enabled V2 organization; the owner holds ORG_ADMIN by snapshot."""
        owner = self.org()
        assert self.rbac.enable(owner)["enabled"] is True
        return owner

    def seed_patient(self, org, assigned_membership):
        patient = str(uuid.uuid4())
        self.sql("INSERT INTO patients(id,organization_id,full_name,legacy_payload) "
                 "VALUES(%s,%s,'SYNTHETIC PACIENTE','{\"clinico\":\"SYNTHETIC\"}')", (patient, org))
        self.sql("INSERT INTO patient_assignments(id,organization_id,patient_id,membership_id) "
                 "VALUES(%s,%s,%s,%s)", (str(uuid.uuid4()), org, patient, assigned_membership))
        return patient

    def seed_report(self, org, professional_membership, patient=None):
        report = str(uuid.uuid4())
        self.sql("INSERT INTO session_reports(id,organization_id,legacy_session_id,patient_id,"
                 "professional_membership_id,report_payload) VALUES(%s,%s,%s,%s,%s,'{}')",
                 (report, org, "SYN-" + report[:8], patient, professional_membership))
        return report

    def rows_as(self, ctx, query, params=()):
        """What the database returns to this member under RLS."""
        with self.pg.connect(self.dsn, options="-c role=froid_runtime") as conn:
            conn.execute("SELECT set_config('app.organization_id',%s,true)", (ctx.organization_id,))
            conn.execute("SELECT set_config('app.membership_id',%s,true)", (ctx.membership_id,))
            return conn.execute(query, params).fetchall()

    def report_ids_visible(self, ctx):
        return {str(row[0]) for row in self.rows_as(
            ctx, "SELECT id FROM session_reports WHERE organization_id=%s", (ctx.organization_id,))}


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


# -- Enable, snapshot and protection --------------------------------------------

def test_enable_requires_owner_is_idempotent_and_snapshots_roles(harness):
    h = harness
    owner = h.org()
    professional = h.member(owner.organization_id, v1_role="professional")
    with pytest.raises(BillingError, match="RBAC_ENABLE_OWNER_REQUIRED"):
        h.rbac.enable(professional)
    first = h.rbac.enable(owner)
    assert first["enabled"] is True
    assert first["org_admin_grants"] == 1 and first["clinician_grants"] == 1
    assert h.rbac.enable(owner)["enabled"] is False
    caps = h.rbac.capabilities(owner)
    assert caps["rbac_version"] == 2 and caps["v2_roles"] == ["ORG_ADMIN"]
    caps = h.rbac.capabilities(professional)
    assert caps["v2_roles"] == ["CLINICIAN"] and caps["capabilities"]["clinical_analysis"] is True
    assert caps["capabilities"]["purchase_credits"] is False


def test_nr1_organizations_cannot_enter_the_v2_branch(harness):
    h = harness
    nr1 = str(uuid.uuid4())
    h.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
          "VALUES(%s,'enterprise','SYNTHETIC NR1','SYNTHETIC NR1')", (nr1,))
    with pytest.raises(h.pg.Error):
        h.sql("INSERT INTO psique_organization_settings(organization_id,rbac_version,enabled_at,enabled_by) "
              "VALUES(%s,2,now(),%s)", (nr1, str(uuid.uuid4())))


def test_rbac_downgrade_is_forbidden(harness):
    h = harness
    owner = h.v2_org()
    with pytest.raises(h.pg.Error, match="PSIQUE_RBAC_DOWNGRADE_FORBIDDEN"):
        h.sql("UPDATE psique_organization_settings SET rbac_version=1 WHERE organization_id=%s",
              (owner.organization_id,))


# -- V1 and NR-1 remain exactly as before ----------------------------------------

def test_v1_organization_keeps_wide_owner_read(harness):
    h = harness
    owner = h.org()  # sem enable: org V1
    professional = h.member(owner.organization_id, v1_role="professional")
    patient = h.seed_patient(owner.organization_id, professional.membership_id)
    report = h.seed_report(owner.organization_id, professional.membership_id, patient)
    assert h.report_ids_visible(owner) == {report}
    supervisor = h.member(owner.organization_id, v1_role="supervisor")
    assert h.report_ids_visible(supervisor) == {report}


# -- The V2 matrix ----------------------------------------------------------------

def test_v2_owner_and_admin_lose_wide_clinical_read(harness):
    h = harness
    owner = h.v2_org()
    clinician = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, clinician.membership_id, "CLINICIAN")
    patient = h.seed_patient(owner.organization_id, clinician.membership_id)
    report = h.seed_report(owner.organization_id, clinician.membership_id, patient)
    # O dono (papel V1 owner + ORG_ADMIN V2) nao le conteudo clinico: a
    # politica V1 nao contorna a V2.
    assert h.report_ids_visible(owner) == set()
    assert h.rows_as(owner, "SELECT id FROM patients WHERE organization_id=%s",
                     (owner.organization_id,)) == []
    assert h.report_ids_visible(clinician) == {report}


def test_v2_secretary_finance_auditor_have_no_clinical_rows(harness):
    h = harness
    owner = h.v2_org()
    clinician = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, clinician.membership_id, "CLINICIAN")
    patient = h.seed_patient(owner.organization_id, clinician.membership_id)
    h.seed_report(owner.organization_id, clinician.membership_id, patient)
    for role in ("SECRETARY", "FINANCE", "AUDITOR_COMPLIANCE"):
        staff = h.member(owner.organization_id, v1_role="professional")
        h.rbac.grant_role(owner, staff.membership_id, role)
        assert h.report_ids_visible(staff) == set(), role
        assert h.rows_as(staff, "SELECT legacy_payload FROM patients WHERE organization_id=%s",
                         (owner.organization_id,)) == [], role
        assert h.rows_as(staff, "SELECT id FROM consents WHERE organization_id=%s",
                         (owner.organization_id,)) == [], role


def test_v2_clinician_sees_own_and_assigned_only(harness):
    h = harness
    owner = h.v2_org()
    first = h.member(owner.organization_id, v1_role="professional")
    second = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, first.membership_id, "CLINICIAN")
    h.rbac.grant_role(owner, second.membership_id, "CLINICIAN")
    patient_first = h.seed_patient(owner.organization_id, first.membership_id)
    report_first = h.seed_report(owner.organization_id, first.membership_id, patient_first)
    patient_second = h.seed_patient(owner.organization_id, second.membership_id)
    report_second = h.seed_report(owner.organization_id, second.membership_id, patient_second)
    assert h.report_ids_visible(first) == {report_first}
    assert h.report_ids_visible(second) == {report_second}
    # Sem o grant CLINICIAN, o papel V1 professional sozinho nao le nada.
    ungranted = h.member(owner.organization_id, v1_role="professional")
    h.seed_patient(owner.organization_id, ungranted.membership_id)
    assert h.report_ids_visible(ungranted) == set()


def test_v2_supervisor_reads_only_explicit_scope_and_revocation_stops_it(harness):
    h = harness
    owner = h.v2_org()
    supervised = h.member(owner.organization_id, v1_role="professional")
    other = h.member(owner.organization_id, v1_role="professional")
    supervisor = h.member(owner.organization_id, v1_role="professional")
    for ctx in (supervised, other):
        h.rbac.grant_role(owner, ctx.membership_id, "CLINICIAN")
    h.rbac.grant_role(owner, supervisor.membership_id, "CLINICAL_SUPERVISOR")
    report_supervised = h.seed_report(
        owner.organization_id, supervised.membership_id,
        h.seed_patient(owner.organization_id, supervised.membership_id))
    h.seed_report(owner.organization_id, other.membership_id,
                  h.seed_patient(owner.organization_id, other.membership_id))
    assert h.report_ids_visible(supervisor) == set()  # papel sem escopo nao le nada
    h.rbac.set_supervision(owner, supervisor_membership_id=supervisor.membership_id,
                           supervised_membership_id=supervised.membership_id, active=True)
    assert h.report_ids_visible(supervisor) == {report_supervised}
    h.rbac.set_supervision(owner, supervisor_membership_id=supervisor.membership_id,
                           supervised_membership_id=supervised.membership_id, active=False)
    assert h.report_ids_visible(supervisor) == set()


def test_supervision_requires_roles_and_org_admin_grantor(harness):
    h = harness
    owner = h.v2_org()
    supervisor = h.member(owner.organization_id, v1_role="professional")
    supervised = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, supervised.membership_id, "CLINICIAN")
    with pytest.raises(BillingError, match="SUPERVISOR_ROLE_REQUIRED"):
        h.rbac.set_supervision(owner, supervisor_membership_id=supervisor.membership_id,
                               supervised_membership_id=supervised.membership_id, active=True)
    h.rbac.grant_role(owner, supervisor.membership_id, "CLINICAL_SUPERVISOR")
    with pytest.raises(BillingError, match="PSIQUE_ORG_ADMIN_REQUIRED"):
        h.rbac.set_supervision(supervised, supervisor_membership_id=supervisor.membership_id,
                               supervised_membership_id=supervised.membership_id, active=True)


def test_roles_are_cumulative_and_revocable(harness):
    h = harness
    owner = h.v2_org()
    hybrid = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, hybrid.membership_id, "CLINICIAN")
    h.rbac.grant_role(owner, hybrid.membership_id, "FINANCE")
    caps = h.rbac.capabilities(hybrid)
    assert set(caps["v2_roles"]) == {"CLINICIAN", "FINANCE"}
    assert caps["capabilities"]["clinical_analysis"] and caps["capabilities"]["purchase_credits"]
    assert h.rbac.revoke_role(owner, hybrid.membership_id, "FINANCE")["revoked"] is True
    assert h.rbac.capabilities(hybrid)["capabilities"]["purchase_credits"] is False
    assert h.rbac.grant_role(owner, hybrid.membership_id, "FINANCE")["granted"] is True


def test_superadmin_and_unknown_roles_are_not_grantable(harness):
    h = harness
    owner = h.v2_org()
    target = h.member(owner.organization_id, v1_role="professional")
    for role in ("SUPERADMIN", "owner", "professional", ""):
        with pytest.raises(BillingError, match="RBAC_ROLE_UNKNOWN"):
            h.rbac.grant_role(owner, target.membership_id, role)


def test_last_org_admin_is_protected_and_non_admin_cannot_manage(harness):
    h = harness
    owner = h.v2_org()
    with pytest.raises(BillingError, match="LAST_ORG_ADMIN_PROTECTED"):
        h.rbac.revoke_role(owner, owner.membership_id, "ORG_ADMIN")
    second = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, second.membership_id, "ORG_ADMIN")
    assert h.rbac.revoke_role(owner, owner.membership_id, "ORG_ADMIN")["revoked"] is True
    with pytest.raises(BillingError, match="PSIQUE_ORG_ADMIN_REQUIRED"):
        h.rbac.grant_role(owner, owner.membership_id, "CLINICIAN")


def test_cross_org_grants_and_capabilities_are_denied(harness):
    h = harness
    owner = h.v2_org()
    outsider_owner = h.v2_org()
    outsider = h.member(outsider_owner.organization_id, v1_role="professional")
    with pytest.raises(BillingError, match="RBAC_TARGET_MEMBERSHIP_REQUIRED"):
        h.rbac.grant_role(owner, outsider.membership_id, "CLINICIAN")
    foreign = AccessContext.create(
        organization_id=owner.organization_id, membership_id=outsider.membership_id,
        user_id=outsider.user_id, roles=["professional"], organization_type="clinic")
    with pytest.raises(BillingError, match="PSIQUE_CONTEXT_MISMATCH|PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED"):
        h.rbac.capabilities(foreign)


# -- Financial gates under V2 ------------------------------------------------------

def test_credit_command_gates_follow_v2_roles(harness):
    h = harness
    owner = h.v2_org()
    clinician = h.member(owner.organization_id, v1_role="professional")
    finance = h.member(owner.organization_id, v1_role="professional")
    secretary = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, clinician.membership_id, "CLINICIAN")
    h.rbac.grant_role(owner, finance.membership_id, "FINANCE")
    h.rbac.grant_role(owner, secretary.membership_id, "SECRETARY")
    h.credits.enroll_empty_wallet(owner)  # ORG_ADMIN
    h.credits.manual_adjustment(owner, 3, reason="SYNTHETIC seed", idempotency_key="seed")
    from psique_credits import CreditError

    with pytest.raises(CreditError, match="PSIQUE_ORG_ADMIN_REQUIRED"):
        h.credits.manual_adjustment(finance, 1, reason="x", idempotency_key="f1")
    assert h.credits.balance(finance)["available_balance"] == 3  # FINANCE le saldo
    with pytest.raises(CreditError, match="PSIQUE_ROLE_DENIED"):
        h.credits.balance(secretary)
    with pytest.raises(CreditError, match="PSIQUE_CLINICIAN_REQUIRED"):
        h.credits.read_delivery(finance, str(uuid.uuid4()))  # financeiro sem conteudo clinico
    with pytest.raises(CreditError, match="PSIQUE_CLINICIAN_REQUIRED"):
        h.credits.begin(owner, str(uuid.uuid4()), "exec", datetime.now(timezone.utc) + timedelta(hours=1))


def test_billing_gate_accepts_finance_and_denies_secretary(harness):
    h = harness
    owner = h.v2_org()
    finance = h.member(owner.organization_id, v1_role="professional")
    secretary = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, finance.membership_id, "FINANCE")
    h.rbac.grant_role(owner, secretary.membership_id, "SECRETARY")
    assert h.license.state(finance)["active_clinical_seat_count"] == 0
    with pytest.raises(BillingError, match="PSIQUE_BILLING_ADMIN_REQUIRED"):
        h.license.state(secretary)
    v1_owner = h.org()
    assert h.license.state(v1_owner)["active_clinical_seat_count"] == 0  # ponte V1 preservada
    someone = h.member(owner.organization_id, v1_role="professional")
    with pytest.raises(BillingError, match="PSIQUE_ORG_ADMIN_REQUIRED"):
        h.license.set_clinical(finance, someone.membership_id, active=True)
    assert h.license.set_clinical(owner, someone.membership_id, active=True)["changed"] is True


def test_wallet_ledger_and_audit_reads_follow_v2_roles(harness):
    h = harness
    owner = h.v2_org()
    finance = h.member(owner.organization_id, v1_role="professional")
    clinician = h.member(owner.organization_id, v1_role="professional")
    secretary = h.member(owner.organization_id, v1_role="professional")
    auditor = h.member(owner.organization_id, v1_role="professional")
    for ctx, role in ((finance, "FINANCE"), (clinician, "CLINICIAN"),
                      (secretary, "SECRETARY"), (auditor, "AUDITOR_COMPLIANCE")):
        h.rbac.grant_role(owner, ctx.membership_id, role)
    h.credits.enroll_empty_wallet(owner)
    wallet_query = "SELECT balance FROM organization_wallets WHERE organization_id=%s"
    ledger_query = "SELECT id FROM credit_ledger WHERE organization_id=%s"
    audit_query = "SELECT id FROM audit_events WHERE organization_id=%s"
    org = (owner.organization_id,)
    assert h.rows_as(finance, wallet_query, org) != []
    assert h.rows_as(clinician, wallet_query, org) != []
    assert h.rows_as(secretary, wallet_query, org) == []
    assert h.rows_as(clinician, ledger_query, org) == []  # extrato e financeiro
    assert h.rows_as(auditor, audit_query, org) != []
    assert h.rows_as(finance, audit_query, org) == []


def test_v2_delete_of_clinical_history_is_denied_even_for_admin(harness):
    h = harness
    owner = h.v2_org()
    clinician = h.member(owner.organization_id, v1_role="professional")
    h.rbac.grant_role(owner, clinician.membership_id, "CLINICIAN")
    report = h.seed_report(owner.organization_id, clinician.membership_id,
                           h.seed_patient(owner.organization_id, clinician.membership_id))
    with h.pg.connect(h.dsn, options="-c role=froid_runtime") as conn:
        conn.execute("SELECT set_config('app.organization_id',%s,true)", (owner.organization_id,))
        conn.execute("SELECT set_config('app.membership_id',%s,true)", (owner.membership_id,))
        deleted = conn.execute("DELETE FROM session_reports WHERE id=%s RETURNING id", (report,)).fetchall()
        conn.rollback()
    assert deleted == []


# -- Concurrency --------------------------------------------------------------------

def test_concurrent_enable_and_duplicate_grant_apply_once(harness):
    h = harness
    owner = h.org()
    outcomes = race(lambda: h.rbac.enable(owner), lambda: h.rbac.enable(owner))
    enabled = [o for o in outcomes if isinstance(o, dict) and o.get("enabled")]
    assert len(enabled) == 1
    target = h.member(owner.organization_id, v1_role="professional")
    outcomes = race(lambda: h.rbac.grant_role(owner, target.membership_id, "SECRETARY"),
                    lambda: h.rbac.grant_role(owner, target.membership_id, "SECRETARY"))
    rows = h.sql("SELECT count(*) FROM psique_membership_role_grants "
                 "WHERE membership_id=%s AND v2_role='SECRETARY' AND revoked_at IS NULL",
                 (target.membership_id,))
    assert rows[0][0] == 1
