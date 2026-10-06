"""Fase 7.2: consumo de sessao no ledger V2 ("uma sessao = um credito").

Exercita a funcao SECURITY DEFINER psique_v2_session_charge de 047 contra um
PostgreSQL real descartavel, pelo servico PsiqueCredits.charge_session. Sem
rede, sem Stripe: o que se prova aqui e a maquina de credito, nao o comercio.

Invariantes da politica A (decidida pelo proprietario): o registro clinico
nunca e bloqueado por falta de saldo; sem credito a sessao vira pendencia
auditavel (delta=0) e e liquidada em ordem (FIFO) quando o credito entra.
"""

import secrets
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psique_credits import CreditError, PsiqueCredits
from psique_identity import TrialKeyring
from tenant_access import AccessContext
from tools.migrate_schema import apply


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
                apply(conn, ROOT / "migrations", "050_psique_session_charge_fix", name)
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


class Harness:
    def __init__(self, dsn):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        factory = lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime")
        self.credits = PsiqueCredits(
            factory, identity_loader=lambda user: None, material_loader=lambda user, ref: None,
            keyring=TrialKeyring({"test": secrets.token_bytes(32)}, "test"))

    def sql(self, query, params=()):
        with self.pg.connect(self.dsn, autocommit=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def context(self, *, role="owner", organization_type="solo"):
        org = str(uuid.uuid4())
        user = str(uuid.uuid4())
        member = str(uuid.uuid4())
        self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                 "VALUES(%s,%s,'SYNTHETIC test','SYNTHETIC test')", (org, organization_type))
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (member, org, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,%s)", (member, role))
        return AccessContext.create(organization_id=org, membership_id=member, user_id=user,
                                    roles=[role], organization_type=organization_type)

    def enrolled(self, credits=0, *, role="owner", organization_type="solo"):
        ctx = self.context(role=role, organization_type=organization_type)
        self.credits.enroll_empty_wallet(ctx)
        if credits:
            self.credits.manual_adjustment(ctx, credits, reason="seed cortesia",
                                           idempotency_key="seed:" + uuid.uuid4().hex)
        return ctx

    def add_member(self, organization_id, role, *, organization_type="clinic"):
        user = str(uuid.uuid4())
        member = str(uuid.uuid4())
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (member, organization_id, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,%s)", (member, role))
        return AccessContext.create(organization_id=organization_id, membership_id=member, user_id=user,
                                    roles=[role], organization_type=organization_type)

    def balance(self, ctx):
        return self.sql("SELECT balance,reserved_balance FROM organization_wallets "
                        "WHERE organization_id=%s", (ctx.organization_id,))[0]

    def ledger(self, ctx, event_type):
        return self.sql("SELECT idempotency_key FROM credit_ledger WHERE organization_id=%s "
                        "AND event_type=%s ORDER BY created_at,id", (ctx.organization_id, event_type))


@pytest.fixture
def harness(database):
    return Harness(database)


# -- Core: uma sessao = um credito -------------------------------------------

def test_charges_one_credit_per_new_session(harness):
    ctx = harness.enrolled(3)
    result = harness.credits.charge_session(ctx, "sess-1")
    assert result["charged"] is True and result["pending"] is False
    assert result["applied"] is True and result["settled_pending"] == 0
    assert result["balance"] == 2 and result["available_balance"] == 2
    assert result["pending_total"] == 0
    assert harness.balance(ctx) == (2, 0)


def test_distinct_sessions_each_cost_one(harness):
    ctx = harness.enrolled(3)
    for sid in ("a", "b", "c"):
        harness.credits.charge_session(ctx, sid)
    assert harness.balance(ctx) == (0, 0)
    assert len(harness.ledger(ctx, "SESSION_CONSUMPTION")) == 3


def test_same_session_never_charged_twice(harness):
    ctx = harness.enrolled(3)
    first = harness.credits.charge_session(ctx, "sess-1")
    second = harness.credits.charge_session(ctx, "sess-1")
    assert first["charged"] is True and first["applied"] is True
    assert second["charged"] is True and second["applied"] is False
    assert harness.balance(ctx) == (2, 0)
    assert len(harness.ledger(ctx, "SESSION_CONSUMPTION")) == 1


# -- Politica A: esgotado entrega, nunca bloqueia ----------------------------

def test_exhausted_balance_marks_pending_without_blocking(harness):
    ctx = harness.enrolled(0)
    result = harness.credits.charge_session(ctx, "sess-overdrawn")
    assert result["charged"] is False and result["pending"] is True
    assert result["applied"] is True and result["pending_total"] == 1
    assert harness.balance(ctx) == (0, 0)
    assert len(harness.ledger(ctx, "SESSION_PENDING")) == 1
    assert harness.ledger(ctx, "SESSION_CONSUMPTION") == []


def test_pending_is_idempotent_by_session(harness):
    ctx = harness.enrolled(0)
    harness.credits.charge_session(ctx, "sess-overdrawn")
    again = harness.credits.charge_session(ctx, "sess-overdrawn")
    assert again["pending"] is True and again["pending_total"] == 1
    assert len(harness.ledger(ctx, "SESSION_PENDING")) == 1


def test_new_credit_reconciles_old_pending_fifo(harness):
    ctx = harness.enrolled(0)
    harness.credits.charge_session(ctx, "older")
    harness.credits.charge_session(ctx, "newer")
    assert harness.credits.charge_session(ctx, "older")["pending_total"] == 2

    harness.credits.manual_adjustment(ctx, 3, reason="recarga",
                                      idempotency_key="recarga:" + uuid.uuid4().hex)
    # A proxima sessao atendida liquida as pendencias antigas (ordem) e cobra a si:
    # tres creditos cobrem as duas dividas antigas (FIFO) e a sessao corrente.
    result = harness.credits.charge_session(ctx, "current")
    assert result["charged"] is True and result["settled_pending"] == 2
    assert result["pending_total"] == 0 and result["balance"] == 0
    consumed = {k for (k,) in harness.ledger(ctx, "SESSION_CONSUMPTION")}
    assert consumed == {"session:older", "session:newer", "session:current"}


def test_partial_credit_settles_only_what_it_covers(harness):
    ctx = harness.enrolled(0)
    harness.credits.charge_session(ctx, "p1")
    harness.credits.charge_session(ctx, "p2")
    harness.credits.manual_adjustment(ctx, 1, reason="um credito",
                                      idempotency_key="um:" + uuid.uuid4().hex)
    # Um credito entra; a sessao atual liquida a pendencia mais antiga (p1) e a
    # propria (current) fica pendente, pois o credito so cobre uma.
    result = harness.credits.charge_session(ctx, "current")
    assert result["settled_pending"] == 1 and result["charged"] is False
    assert result["pending"] is True and result["pending_total"] == 2
    consumed = {k for (k,) in harness.ledger(ctx, "SESSION_CONSUMPTION")}
    assert consumed == {"session:p1"}


# -- Fronteira de seguranca --------------------------------------------------

def test_clinician_professional_can_charge(harness):
    # O dono inscreve e abastece a carteira; o clinico que atende e outra
    # membership (papel professional) e pode cobrar a propria sessao.
    owner = harness.enrolled(1, organization_type="clinic")
    prof = harness.add_member(owner.organization_id, "professional")
    assert harness.credits.charge_session(prof, "sess-1")["charged"] is True


def test_v1_wallet_is_refused_untouched(harness):
    ctx = harness.context(role="professional")
    # Carteira V1 (default credit_model='v1'): o atendimento V1 nao passa por aqui.
    harness.sql("INSERT INTO organization_wallets(organization_id,balance) VALUES(%s,20)",
                (ctx.organization_id,))
    with pytest.raises(CreditError) as exc:
        harness.credits.charge_session(ctx, "sess-1")
    assert exc.value.code == "PSIQUE_WALLET_REQUIRED"
    assert harness.ledger(ctx, "SESSION_CONSUMPTION") == []


def test_blank_session_id_is_rejected(harness):
    ctx = harness.enrolled(1)
    with pytest.raises(CreditError) as exc:
        harness.credits.charge_session(ctx, "   ")
    assert exc.value.code == "SESSION_ID_REQUIRED"


def test_organization_credit_model_routes_attendance(harness):
    """O roteamento do atendimento (main.py) pergunta o modelo de credito aqui:
    'psique_v2' desvia para a carteira unica; 'v1'/ausencia segue no V1."""
    from tenant_store import TenantStore

    store = TenantStore(mode="dual", database_url=harness.dsn,
                        migration_path=ROOT / "migrations" / "001_multitenant_foundation.sql",
                        runtime_database_url=harness.dsn)
    v2 = harness.enrolled(0)
    assert store.organization_credit_model(v2.organization_id) == "psique_v2"

    legacy = harness.context(role="professional")
    harness.sql("INSERT INTO organization_wallets(organization_id,balance) VALUES(%s,5)",
                (legacy.organization_id,))
    assert store.organization_credit_model(legacy.organization_id) == "v1"

    assert store.organization_credit_model(str(uuid.uuid4())) == ""


def test_context_mismatch_is_refused(harness):
    ctx = harness.enrolled(1)
    other = str(uuid.uuid4())
    with harness.pg.connect(harness.dsn, autocommit=True, options="-c role=froid_runtime") as conn, conn.transaction():
        conn.execute("SELECT set_config('app.organization_id',%s,true)", (ctx.organization_id,))
        conn.execute("SELECT set_config('app.membership_id',%s,true)", (ctx.membership_id,))
        # PSIQUE_CONTEXT_MISMATCH usa ERRCODE 42501 (insufficient_privilege).
        with pytest.raises(harness.pg.errors.InsufficientPrivilege):
            conn.execute("SELECT psique_v2_session_charge(%s,%s,%s,%s,%s)",
                         (other, ctx.membership_id, ctx.user_id, "sess-1", "")).fetchone()


# -- 050: a sessao que ja estava pendente e cobrada de novo -------------------

def test_pendente_cobrada_de_novo_com_dois_creditos_nao_quebra(harness):
    """Na 047 a fila liquidava S e o ramo atual gravava S de novo: UNIQUE violado
    e a transacao inteira desfeita (PSIQUE_STORAGE_ERROR)."""
    ctx = harness.enrolled(0)
    assert harness.credits.charge_session(ctx, "S")["pending"] is True
    harness.credits.manual_adjustment(ctx, 2, reason="recarga",
                                      idempotency_key="r:" + uuid.uuid4().hex)
    result = harness.credits.charge_session(ctx, "S")
    assert result["charged"] is True and result["pending"] is False
    assert result["pending_total"] == 0 and result["balance"] == 1
    assert [k for (k,) in harness.ledger(ctx, "SESSION_CONSUMPTION")] == ["session:S"]


def test_pendente_cobrada_de_novo_com_um_credito_fica_paga(harness):
    """Na 047 respondia "pendente" sobre a sessao que acabara de liquidar."""
    ctx = harness.enrolled(0)
    harness.credits.charge_session(ctx, "S")
    harness.credits.manual_adjustment(ctx, 1, reason="um",
                                      idempotency_key="u:" + uuid.uuid4().hex)
    result = harness.credits.charge_session(ctx, "S")
    assert result["charged"] is True and result["pending"] is False
    assert result["pending_total"] == 0 and result["balance"] == 0
