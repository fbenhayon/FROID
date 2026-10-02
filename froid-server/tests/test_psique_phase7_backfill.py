"""Fase 7.3: backfill nao destrutivo de carteira V1 para a carteira unica V2.

Exercita o comando SECURITY DEFINER psique_v2_backfill_from_v1 de 048 contra um
PostgreSQL real descartavel, pelo servico PsiqueCredits.backfill_from_v1. Sem
rede, sem Stripe. A carteira V1 e montada no FORMATO DE PRODUCAO: linha
organization_wallets credit_model='v1' + um migration_opening no ledger (como o
espelho dual grava), para provar que a conversao preserva saldo E trilha.

Invariantes (decisoes do proprietario 02/10/2026): nenhuma org perde saldo; a
trilha v1 e preservada (sem DELETE); carrega como PAID; carrega as pendencias
V1 como SESSION_PENDING; idempotente por organizacao.
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
                apply(conn, ROOT / "migrations", "048_psique_v2_backfill", name)
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

    def context(self, *, role="owner", organization_type="clinic"):
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

    def seed_v1_wallet(self, ctx, balance):
        """Carteira V1 no formato de producao: linha v1 + migration_opening."""
        self.sql("INSERT INTO organization_wallets(organization_id,balance,credit_model) "
                 "VALUES(%s,%s,'v1')", (ctx.organization_id, balance))
        self.sql("INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,"
                 "idempotency_key,actor_user_id) "
                 "VALUES(gen_random_uuid(),%s,%s,%s,'migration_opening',%s,%s)",
                 (ctx.organization_id, balance, balance,
                  "legacy-opening-v1:" + ctx.user_id, ctx.user_id))

    def wallet(self, ctx):
        return self.sql("SELECT balance,reserved_balance,credit_model,authority,ever_purchased "
                        "FROM organization_wallets WHERE organization_id=%s", (ctx.organization_id,))[0]

    def ledger(self, ctx, event_type, *, version=None):
        if version is None:
            return self.sql("SELECT delta,funding,idempotency_key FROM credit_ledger "
                            "WHERE organization_id=%s AND event_type=%s ORDER BY created_at,id",
                            (ctx.organization_id, event_type))
        return self.sql("SELECT delta,funding,idempotency_key FROM credit_ledger "
                        "WHERE organization_id=%s AND event_type=%s AND ledger_version=%s "
                        "ORDER BY created_at,id", (ctx.organization_id, event_type, version))


@pytest.fixture
def harness(database):
    return Harness(database)


# -- Conversao: saldo e trilha preservados -----------------------------------

def test_backfill_converts_and_preserves_balance(harness):
    ctx = harness.context()
    harness.seed_v1_wallet(ctx, 7)
    result = harness.credits.backfill_from_v1(ctx, 7, ever_purchased=True, note="piloto")
    assert result["converted"] is True and result["already_v2"] is False
    assert result["opened"] is True and result["balance"] == 7
    assert result["prior_pool"] == 7 and result["ever_purchased"] is True

    balance, reserved, model, authority, ever = harness.wallet(ctx)
    assert (balance, reserved, model, authority, ever) == (7, 0, "psique_v2", "shared", True)

    opening = harness.ledger(ctx, "V2_MIGRATION_OPENING")
    assert opening == [(7, "PAID", "v2-backfill-opening:" + ctx.organization_id)]
    # Trilha V1 preservada (sem DELETE): o migration_opening v1 continua la.
    assert len(harness.ledger(ctx, "migration_opening", version=1)) == 1


def test_backfill_is_idempotent(harness):
    ctx = harness.context()
    harness.seed_v1_wallet(ctx, 5)
    first = harness.credits.backfill_from_v1(ctx, 5, ever_purchased=False)
    second = harness.credits.backfill_from_v1(ctx, 5, ever_purchased=True)
    assert first["converted"] is True
    assert second["converted"] is False and second["already_v2"] is True
    assert harness.wallet(ctx)[0] == 5
    # Nem o saldo nem ever_purchased mudam no no-op; so uma abertura existe.
    assert harness.wallet(ctx)[4] is False
    assert len(harness.ledger(ctx, "V2_MIGRATION_OPENING")) == 1


def test_backfill_zero_net_flips_empty(harness):
    ctx = harness.context()
    harness.seed_v1_wallet(ctx, 0)
    result = harness.credits.backfill_from_v1(ctx, 0, ever_purchased=False)
    assert result["converted"] is True and result["opened"] is False
    assert harness.wallet(ctx)[:3] == (0, 0, "psique_v2")
    assert harness.ledger(ctx, "V2_MIGRATION_OPENING") == []


def test_backfill_carries_v1_pendings(harness):
    ctx = harness.context()
    harness.seed_v1_wallet(ctx, 0)
    result = harness.credits.backfill_from_v1(ctx, 0, ever_purchased=False,
                                              pending_ids=["p1", "p2", "", "  "])
    assert result["pending_carried"] == 2
    pend = {k for (_d, _f, k) in harness.ledger(ctx, "SESSION_PENDING")}
    assert pend == {"session-pending:p1", "session-pending:p2"}


def test_backfill_negative_net_rejected(harness):
    ctx = harness.context()
    harness.seed_v1_wallet(ctx, 3)
    with pytest.raises(CreditError) as exc:
        harness.credits.backfill_from_v1(ctx, -1, ever_purchased=False)
    assert exc.value.code == "BACKFILL_NET_INVALID"
    # Nada convertido: a carteira segue V1.
    assert harness.wallet(ctx)[2] == "v1"


def test_backfill_requires_existing_wallet(harness):
    ctx = harness.context()
    with pytest.raises(CreditError) as exc:
        harness.credits.backfill_from_v1(ctx, 0, ever_purchased=False)
    assert exc.value.code == "PSIQUE_WALLET_REQUIRED"


# -- Integracao com a 7.2: a org convertida consome pela maquina V2 ----------

def test_backfilled_org_charges_and_reconciles_via_v2(harness):
    ctx = harness.context()
    harness.seed_v1_wallet(ctx, 0)
    # Uma pendencia V1 carregada e saldo zero.
    harness.credits.backfill_from_v1(ctx, 0, ever_purchased=True, pending_ids=["antiga"])
    # Entra 1 credito; atender uma nova sessao liquida a pendencia antiga (FIFO)
    # e a propria sessao fica pendente (so um credito).
    harness.credits.manual_adjustment(ctx, 1, reason="recarga",
                                      idempotency_key="r:" + uuid.uuid4().hex)
    charged = harness.credits.charge_session(ctx, "nova")
    assert charged["settled_pending"] == 1 and charged["charged"] is False
    # 'antiga' foi liquidada (virou consumo); 'nova' ficou pendente -> 1 em aberto.
    assert charged["pending_total"] == 1
    consumed = {k for (_d, _f, k) in harness.ledger(ctx, "SESSION_CONSUMPTION")}
    assert consumed == {"session:antiga"}


def test_backfilled_org_spends_carried_balance(harness):
    ctx = harness.context()
    harness.seed_v1_wallet(ctx, 2)
    harness.credits.backfill_from_v1(ctx, 2, ever_purchased=True)
    harness.credits.charge_session(ctx, "s1")
    harness.credits.charge_session(ctx, "s2")
    assert harness.wallet(ctx)[0] == 0
    third = harness.credits.charge_session(ctx, "s3")
    assert third["charged"] is False and third["pending"] is True
