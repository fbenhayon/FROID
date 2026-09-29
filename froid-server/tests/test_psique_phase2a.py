"""Phase 2A acceptance with real PostgreSQL and independent concurrent workers.

All identities, material and reports are explicitly synthetic fixtures. No
clinical data, Stripe requests or generic production DB settings are used.
"""

import hashlib
import os
import secrets
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psique_analysis import AnalysisWorkflow, CompletedAnalysis
from psique_credits import CreditError, PsiqueCredits
from psique_identity import (
    AuthorizedMaterial,
    EvidenceError,
    TrialIdentity,
    TrialKeyring,
    source_sha256,
)
from tenant_access import AccessContext
from tools.migrate_schema import apply


def test_hash_is_incremental_and_does_not_depend_on_chunk_boundaries():
    original = b"SYNTHETIC original media bytes"
    assert source_sha256(iter([original[:4], b"", original[4:]])) == hashlib.sha256(original).hexdigest()
    assert source_sha256([original]) == source_sha256(bytes([byte]) for byte in original)
    with pytest.raises(EvidenceError, match="EMPTY_SOURCE"):
        source_sha256([b""])


def test_email_normalization_preserves_aliases_and_dots():
    ring = TrialKeyring({"test": secrets.token_bytes(32)}, "test")
    assert ring.tokens("  User.Name+tag@gmail.com ", []) == ring.tokens("user.name+tag@gmail.com", [])
    assert ring.tokens("user.name+tag@gmail.com", []) != ring.tokens("username@gmail.com", [])
    assert ring.tokens("user.name+tag@gmail.com", []) != ring.tokens("user.name@gmail.com", [])


def test_missing_key_and_missing_historical_key_fail_closed(monkeypatch):
    monkeypatch.delenv("FROID_PSIQUE_TRIAL_HMAC_KEYS", raising=False)
    monkeypatch.delenv("FROID_PSIQUE_TRIAL_HMAC_ACTIVE_VERSION", raising=False)
    with pytest.raises(EvidenceError, match="TRIAL_HMAC_KEY_REQUIRED"):
        TrialKeyring.from_env().tokens("test@example.invalid", [])
    with pytest.raises(EvidenceError, match="TRIAL_HISTORICAL_KEY_REQUIRED"):
        TrialKeyring({"new": secrets.token_bytes(32)}, "new").tokens("test@example.invalid", ["old"])


@pytest.fixture(scope="module")
def database():
    dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("explicit disposable Psique database required")
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(dsn)
    assert params.get("host") in {"127.0.0.1", "localhost"}
    assert params.get("dbname", "").startswith("psique_v2_test_")
    assert not params.get("hostaddr") and not params.get("service")
    name = "psique_v2_test_" + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname='froid_runtime'").fetchone()
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        try:
            isolated = make_conninfo(dsn, dbname=name)
            with psycopg.connect(isolated, autocommit=True) as conn:
                apply(conn, ROOT / "migrations", "038_psique_credit_commands", name)
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


@pytest.fixture(scope="module")
def keys():
    return {"test-v1": secrets.token_bytes(32), "test-v2": secrets.token_bytes(32)}


class Harness:
    def __init__(self, dsn, keys):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        self.identities = {}
        self.materials = {}
        self.keys = keys
        self.service = PsiqueCredits(
            lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime"),
            identity_loader=lambda user: self.identities[user],
            material_loader=lambda user, ref: self.materials[ref],
            keyring=TrialKeyring(keys, "test-v1"))

    def sql(self, query, params=()):
        with self.pg.connect(self.dsn, autocommit=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def context(self, *, role="owner", org_type="solo", user_id=None, organization_id=None):
        org = organization_id or str(uuid.uuid4())
        user = user_id or str(uuid.uuid4())
        member = str(uuid.uuid4())
        if organization_id is None:
            self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                     "VALUES(%s,%s,'SYNTHETIC test','SYNTHETIC test')", (org, org_type))
        if user_id is None:
            email = user + "@example.invalid"
            self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, email))
            self.identities[user] = TrialIdentity(email, datetime.now(timezone.utc)-timedelta(seconds=1),
                                                 "SYNTHETIC verified identity", legacy_history_checked=True)
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)", (member, org, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,%s)", (member, role))
        return AccessContext.create(organization_id=org, membership_id=member, user_id=user,
                                    roles=[role], organization_type=org_type)

    def enrolled(self, **kwargs):
        ctx = self.context(**kwargs)
        self.service.enroll_empty_wallet(ctx)
        return ctx

    def trial(self):
        ctx = self.enrolled()
        assert self.service.grant_trial(ctx)["granted"]
        return ctx

    def paid(self, amount=1):
        ctx = self.enrolled()
        self.service.manual_adjustment(ctx, amount, reason="SYNTHETIC paid fixture", idempotency_key="seed")
        return ctx

    def source(self, ctx, kind="stream", reference=None):
        ref = reference or uuid.uuid4().hex
        if ref not in self.materials:
            self.materials[ref] = AuthorizedMaterial(str(uuid.uuid4()), ctx.organization_id,
                ctx.user_id, "SYNTHETIC-session-"+ref, kind,
                [b"SYNTHETIC file "+ref.encode()] if kind == "file" else None)
        return self.service.register_source(ctx, ref)["analysis_source_id"]

    def begin(self, ctx, source=None, execution=None):
        return self.service.begin(ctx, source or self.source(ctx), execution or uuid.uuid4().hex,
                                  datetime.now(timezone.utc)+timedelta(hours=1))

    def deliver(self, ctx, attempt):
        return self.service.deliver(ctx, attempt, protected_report={"fixture": "SYNTHETIC", "inconclusive": True},
                                    technical_complete=True, minimum_result_verified=True)

    def consume(self, ctx, source=None):
        attempt = self.begin(ctx, source)["attempt_id"]
        self.deliver(ctx, attempt)
        return self.service.consume(ctx, attempt), attempt

    def events(self, ctx, kind):
        return self.sql("SELECT id,delta,reserved_delta,balance_after,reserved_after,funding,xmin::text "
                        "FROM credit_ledger WHERE organization_id=%s AND event_type=%s", (ctx.organization_id, kind))

    def expire(self, ctx):
        # Controlled time fixture, not an application clock override.
        self.sql("WITH tick AS (SELECT clock_timestamp() AS instant) "
                 "UPDATE psique_trials SET started_at=tick.instant-interval '337 hours', "
                 "expires_at=tick.instant-interval '1 hour' FROM tick WHERE organization_id=%s", (ctx.organization_id,))


@pytest.fixture
def harness(database, keys):
    return Harness(database, keys)


def race(*functions):
    barrier = threading.Barrier(len(functions))

    def run(fn):
        barrier.wait(timeout=10)
        try:
            return fn()
        except CreditError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return [f.result(timeout=30) for f in [pool.submit(run, fn) for fn in functions]]


def test_trial_ten_once_and_fourteen_days(harness):
    h = harness
    ctx = h.trial()
    assert not h.service.grant_trial(ctx)["granted"]
    assert h.service.balance(ctx)["available_balance"] == 10
    assert len(h.events(ctx, "TRIAL_GRANT")) == 1
    assert h.sql("SELECT expires_at-started_at FROM psique_trials WHERE organization_id=%s",
                 (ctx.organization_id,))[0][0] == timedelta(days=14)


@pytest.mark.parametrize("failure", ["unverified", "wrong_email", "missing_key", "legacy_v1", "unknown_history"])
def test_trial_eligibility_uses_server_evidence(harness, failure):
    h = harness
    ctx = h.enrolled()
    identity = h.identities[ctx.user_id]
    if failure == "unverified":
        h.identities[ctx.user_id] = replace(identity, verified_at=None)
    elif failure == "wrong_email":
        h.identities[ctx.user_id] = replace(identity, email="wrong@example.invalid")
    elif failure == "missing_key":
        h.service._keyring = TrialKeyring({}, "")
    elif failure == "unknown_history":
        h.identities[ctx.user_id] = replace(identity, legacy_history_checked=False)
    else:
        h.identities[ctx.user_id] = replace(identity, legacy_benefit_ref="SYNTHETIC V1 trial record")
    if failure == "legacy_v1":
        assert h.service.grant_trial(ctx) == {"granted": False, "status": "INELIGIBLE"}
    else:
        with pytest.raises(EvidenceError):
            h.service.grant_trial(ctx)
    assert not h.events(ctx, "TRIAL_GRANT")
    assert h.service.balance(ctx)["balance"] == 0


def test_shared_organization_grants_only_ten_and_invited_member_cannot_grant(harness):
    h = harness
    ctx = h.trial()
    member = h.context(role="professional", organization_id=ctx.organization_id)
    with pytest.raises(CreditError, match="TRIAL_OWNER_REQUIRED"):
        h.service.grant_trial(member)
    h.consume(member)
    assert h.service.balance(ctx)["balance"] == 9
    assert len(h.events(ctx, "TRIAL_GRANT")) == 1


def test_concurrent_grants_for_same_email_across_organizations_and_rotation(harness):
    h = harness
    one = h.enrolled()
    two = h.enrolled(user_id=one.user_id)
    results = race(lambda: h.service.grant_trial(one), lambda: h.service.grant_trial(two))
    assert sum(result["granted"] for result in results) == 1
    assert sum(h.service.balance(ctx)["balance"] for ctx in (one, two)) == 10
    three = h.enrolled(user_id=one.user_id)
    h.service._keyring = TrialKeyring(h.keys, "test-v2")
    assert not h.service.grant_trial(three)["granted"]


def test_same_organization_concurrent_trial_and_history_survives_closure(harness):
    h = harness
    ctx = h.enrolled()
    results = race(lambda: h.service.grant_trial(ctx), lambda: h.service.grant_trial(ctx))
    assert sum(r["granted"] for r in results) == 1
    h.sql("UPDATE organizations SET status='archived' WHERE id=%s", (ctx.organization_id,))
    new_org = h.enrolled(user_id=ctx.user_id)
    assert not h.service.grant_trial(new_org)["granted"]
    with pytest.raises(h.pg.Error):
        h.sql("DELETE FROM psique_trial_eligibility WHERE organization_id=%s", (ctx.organization_id,))


def test_trial_consumed_before_synthetic_purchase_and_expiry_preserves_paid(harness):
    h = harness
    ctx = h.trial()
    for _ in range(3):
        h.consume(ctx)
    # Test-only invocation of an ungranted internal primitive. No purchase API or Stripe.
    h.sql("SELECT psique_v2_append(%s,%s,'CREDIT_PURCHASE',25,0,'SYNTHETIC purchase',fund=>'PAID')",
          (ctx.organization_id, ctx.user_id))
    for _ in range(5):
        h.consume(ctx)
    assert h.service.balance(ctx)["balance"] == 27
    assert all(row[5] == "TRIAL" for row in h.events(ctx, "CREDIT_CONSUMPTION"))
    h.expire(ctx)
    assert h.service.expire_trial(ctx)["balance"] == 25
    assert h.events(ctx, "TRIAL_EXPIRATION")[0][1] == -2
    h.consume(ctx)
    assert h.service.balance(ctx)["balance"] == 24


def test_trial_exhaustion_before_deadline_keeps_existing_report_accessible(harness):
    h = harness
    ctx = h.trial()
    for _ in range(10):
        _, attempt = h.consume(ctx)
    assert h.service.balance(ctx)["trial_status"] == "EXHAUSTED"
    assert h.begin(ctx)["reason"] == "INSUFFICIENT_CREDITS"
    assert h.service.read_delivery(ctx, attempt)["report"]["fixture"] == "SYNTHETIC"


@pytest.mark.parametrize("outcome", ["consume", "release", "restore"])
def test_reserved_trial_across_expiry_and_compensation(harness, outcome):
    h = harness
    ctx = h.trial()
    attempt = h.begin(ctx)["attempt_id"]
    if outcome == "restore":
        h.deliver(ctx, attempt)
        consumed = h.service.consume(ctx, attempt)
    h.expire(ctx)
    assert h.service.expire_trial(ctx)["balance"] == (0 if outcome == "restore" else 1)
    if outcome == "consume":
        h.deliver(ctx, attempt)
        assert h.service.consume(ctx, attempt)["applied"]
    elif outcome == "release":
        assert h.service.release(ctx, attempt, "SYNTHETIC timeout")["applied"]
        release_tx = h.events(ctx, "CREDIT_RELEASE")[0][6]
        assert any(row[6] == release_tx and row[1] == -1 for row in h.events(ctx, "TRIAL_EXPIRATION"))
    else:
        assert h.service.restore(ctx, consumed["ledger_id"], reason="SYNTHETIC technical error",
                                 evidence_ref="SYNTHETIC incident")["applied"]
        restore_tx = h.events(ctx, "CREDIT_RESTORE")[0][6]
        assert any(row[6] == restore_tx and row[1] == -1 for row in h.events(ctx, "TRIAL_EXPIRATION"))
    state = h.service.balance(ctx)
    assert state["balance"] == state["reserved_balance"] == state["available_balance"] == 0


def test_last_credit_two_workers_only_one_reserves(harness):
    h = harness
    ctx = h.paid()
    a, b = h.source(ctx), h.source(ctx)
    results = race(lambda: h.begin(ctx, a), lambda: h.begin(ctx, b))
    assert sum(r["started"] for r in results) == 1
    assert [r["reason"] for r in results if not r["started"]] == ["INSUFFICIENT_CREDITS"]
    state = h.service.balance(ctx)
    assert (state["balance"], state["reserved_balance"], state["available_balance"]) == (1, 1, 0)


@pytest.mark.parametrize("same_execution", [False, True])
def test_same_source_concurrent_reservation_is_idempotent(harness, same_execution):
    h = harness
    ctx = h.paid(2)
    source = h.source(ctx)
    key = uuid.uuid4().hex
    results = race(lambda: h.begin(ctx, source, key),
                   lambda: h.begin(ctx, source, key if same_execution else uuid.uuid4().hex))
    assert sum(r["started"] for r in results) == 1
    assert len(h.events(ctx, "CREDIT_RESERVATION")) == 1


def test_consume_and_release_compete_without_double_spending(harness):
    h = harness
    ctx = h.paid()
    attempt = h.begin(ctx)["attempt_id"]
    h.deliver(ctx, attempt)
    results = race(lambda: h.service.consume(ctx, attempt), lambda: h.service.release(ctx, attempt, "SYNTHETIC abort"))
    assert any(isinstance(r, dict) and r["applied"] for r in results)
    assert "DELIVERED_REQUIRES_SETTLEMENT" in results
    assert not h.events(ctx, "CREDIT_RELEASE")
    assert len(h.events(ctx, "CREDIT_CONSUMPTION")) == 1
    assert not h.service.consume(ctx, attempt)["applied"]


def test_release_retry_and_late_completion_cannot_charge(harness):
    h = harness
    ctx = h.paid()
    attempt = h.begin(ctx)["attempt_id"]
    assert h.service.release(ctx, attempt, "SYNTHETIC abort")["applied"]
    assert not h.service.release(ctx, attempt, "SYNTHETIC abort")["applied"]
    with pytest.raises(CreditError):
        h.deliver(ctx, attempt)
    with pytest.raises(CreditError):
        h.service.consume(ctx, attempt)
    assert h.service.balance(ctx)["available_balance"] == 1


def test_expiry_racing_with_completion_honors_original_trial_reservation(harness):
    h = harness
    ctx = h.trial()
    attempt = h.begin(ctx)["attempt_id"]
    h.deliver(ctx, attempt)
    h.expire(ctx)
    results = race(lambda: h.service.expire_trial(ctx), lambda: h.service.consume(ctx, attempt))
    assert all(isinstance(r, dict) for r in results)
    assert h.service.balance(ctx)["available_balance"] == 0
    assert len(h.events(ctx, "CREDIT_CONSUMPTION")) == 1


def test_restore_concurrent_once_and_same_source_stays_free(harness):
    h = harness
    ctx = h.paid()
    source = h.source(ctx)
    consumption, _ = h.consume(ctx, source)
    restore = lambda: h.service.restore(ctx, consumption["ledger_id"], reason="SYNTHETIC technical error",
                                        evidence_ref="SYNTHETIC incident")
    results = race(restore, restore)
    assert sum(r["applied"] for r in results) == 1
    assert h.service.balance(ctx)["balance"] == 1
    for _ in ("reanalysis", "reprocessing", "new model", "regenerate report"):
        retry, _ = h.consume(ctx, source)
        assert not retry["applied"]
    assert h.service.balance(ctx)["balance"] == 1
    assert len(h.events(ctx, "CREDIT_CONSUMPTION")) == 1


def test_source_owner_and_organization_are_checked_server_side(harness):
    h = harness
    owner = h.paid()
    other = h.paid()
    source = h.source(owner, "file", "shared-reference")
    with pytest.raises(EvidenceError, match="MATERIAL_ACCESS_DENIED"):
        h.service.register_source(other, "shared-reference")
    with pytest.raises(CreditError, match="SOURCE_ACCESS_DENIED"):
        h.begin(other, source)
    member = h.context(role="professional", organization_id=owner.organization_id)
    with pytest.raises(CreditError, match="SOURCE_ACCESS_DENIED"):
        h.begin(member, source)
    with pytest.raises(h.pg.Error):
        h.sql("UPDATE psique_analysis_sources SET source_sha256=repeat('a',64) WHERE id=%s", (source,))


def test_gate_runs_before_processor_and_crash_reconciliation_releases(harness):
    h = harness
    ctx = h.enrolled()
    source = h.source(ctx)
    called = []
    workflow = AnalysisWorkflow(h.service)
    result = workflow.run(ctx, source, execution_key="job", lease_until=datetime.now(timezone.utc)+timedelta(hours=1),
                          processor=lambda: called.append(True))
    assert result["reason"] == "INSUFFICIENT_CREDITS" and called == []
    h.service.manual_adjustment(ctx, 1, reason="SYNTHETIC fixture", idempotency_key="seed")
    attempt = h.begin(ctx, source, "crashed-job")["attempt_id"]
    h.sql("UPDATE psique_analysis_attempts SET started_at=clock_timestamp()-interval '2 hours', "
          "lease_until=clock_timestamp()-interval '1 hour' WHERE id=%s", (attempt,))
    assert h.service.reconcile_pending(ctx)[0]["status"] == "FAILED"
    assert h.service.balance(ctx)["available_balance"] == 1
    assert not h.begin(ctx, source, "crashed-job")["started"]
    assert h.begin(ctx, source, "new-execution")["started"]


def test_processor_failure_releases_and_durable_delivery_survives_retry(harness):
    h = harness
    ctx = h.paid()
    source = h.source(ctx)
    workflow = AnalysisWorkflow(h.service)

    def broken():
        assert h.service.balance(ctx)["reserved_balance"] == 1
        raise TimeoutError("SYNTHETIC processing failure")

    with pytest.raises(TimeoutError):
        workflow.run(ctx, source, execution_key="failed", lease_until=datetime.now(timezone.utc)+timedelta(hours=1), processor=broken)
    assert h.service.balance(ctx)["available_balance"] == 1
    attempt = h.begin(ctx, source, "delivered-before-worker-crash")["attempt_id"]
    h.deliver(ctx, attempt)
    assert not h.events(ctx, "CREDIT_CONSUMPTION")
    assert h.service.reconcile_pending(ctx)[0]["applied"]
    assert h.service.read_delivery(ctx, attempt)["report"]["fixture"] == "SYNTHETIC"
    assert not h.service.reconcile(ctx, attempt)["applied"]


def test_minimum_delivery_and_retrievability_are_required(harness):
    h = harness
    ctx = h.paid()
    attempt = h.begin(ctx)["attempt_id"]
    with pytest.raises(CreditError, match="DURABLE_DELIVERY_REQUIRED"):
        h.service.consume(ctx, attempt)
    with pytest.raises(CreditError, match="DELIVERY_CONTRACT_NOT_MET"):
        h.service.deliver(ctx, attempt, protected_report={}, technical_complete=False, minimum_result_verified=False)
    report_id = h.deliver(ctx, attempt)["report_id"]
    h.sql("UPDATE session_reports SET deleted_at=clock_timestamp() WHERE id=%s", (report_id,))
    with pytest.raises(CreditError, match="DELIVERY_UNAVAILABLE"):
        h.service.consume(ctx, attempt)
    assert not h.events(ctx, "CREDIT_CONSUMPTION")
    assert h.service.release(ctx, attempt, "SYNTHETIC delivery became inaccessible")["applied"]
    assert h.service.balance(ctx)["available_balance"] == 1
    assert h.sql("SELECT count(*) FROM session_reports WHERE id=%s", (report_id,))[0][0] == 1


def test_workflow_delivers_inconclusive_result_and_free_reanalysis(harness):
    h = harness
    ctx = h.paid()
    source = h.source(ctx)
    workflow = AnalysisWorkflow(h.service)
    for key in ("original", "reanalysis"):
        result = workflow.run(ctx, source, execution_key=key,
            lease_until=datetime.now(timezone.utc)+timedelta(hours=1),
            processor=lambda: CompletedAnalysis({"fixture": "SYNTHETIC", "inconclusive": True}, True, True))
        assert result["status"] == "DELIVERED"
    assert len(h.events(ctx, "CREDIT_CONSUMPTION")) == 1
    assert h.service.balance(ctx)["balance"] == 0


def test_adjustment_cannot_spend_trial_or_reserved_paid_and_is_audited(harness):
    h = harness
    ctx = h.trial()
    with pytest.raises(CreditError, match="INSUFFICIENT_PAID_CREDITS"):
        h.service.manual_adjustment(ctx, -1, reason="SYNTHETIC", idempotency_key="negative")
    with pytest.raises(CreditError):
        h.service.manual_adjustment(ctx, 1, reason="", idempotency_key="invalid")
    h.service.manual_adjustment(ctx, 2, reason="SYNTHETIC correction", idempotency_key="positive")
    assert not h.service.manual_adjustment(ctx, 2, reason="SYNTHETIC correction", idempotency_key="positive")["applied"]
    assert h.sql("SELECT count(*) FROM audit_events WHERE organization_id=%s AND action='psique.MANUAL_ADJUSTMENT'",
                 (ctx.organization_id,))[0][0] == 1
    paid = h.paid()
    h.begin(paid)
    with pytest.raises(CreditError, match="INSUFFICIENT_PAID_CREDITS"):
        h.service.manual_adjustment(paid, -1, reason="SYNTHETIC correction", idempotency_key="negative")


def test_v1_conversion_and_v1_mutation_of_v2_are_blocked(harness):
    h = harness
    legacy = h.context()
    h.sql("INSERT INTO organization_wallets(organization_id,balance) VALUES(%s,5)", (legacy.organization_id,))
    with pytest.raises(CreditError, match="V1_WALLET_CONVERSION_NOT_AUTHORIZED"):
        h.service.enroll_empty_wallet(legacy)
    ctx = h.paid()
    with (
        h.pg.connect(h.dsn, autocommit=True) as conn,
        pytest.raises(h.pg.Error, match="WALLET_CREDIT_MODEL_MISMATCH"),
        conn.transaction(),
    ):
        conn.execute("SELECT set_config('app.organization_id',%s,true)", (ctx.organization_id,))
        conn.execute("SELECT set_config('app.membership_id',%s,true)", (ctx.membership_id,))
        conn.execute("SELECT * FROM froid_apply_credit_event(%s,%s,%s,-1,'consumption','V1-bypass')",
                     (ctx.organization_id, ctx.membership_id, ctx.user_id))
    assert h.service.balance(ctx)["balance"] == 1
    assert not h.events(ctx, "consumption")


def test_runtime_has_no_direct_financial_writes_and_nr1_cannot_enroll(harness):
    h = harness
    enterprise = h.context(org_type="enterprise")
    with pytest.raises(CreditError, match="PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED"):
        h.service.enroll_empty_wallet(enterprise)
    for table in ("organization_wallets", "credit_ledger", "psique_trials", "psique_trial_eligibility",
                  "psique_analysis_sources", "psique_analysis_attempts", "psique_credit_reservations"):
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            assert not h.sql("SELECT has_table_privilege('froid_runtime',%s,%s)", (table, privilege))[0][0]
    assert not h.sql("SELECT has_schema_privilege('froid_runtime','public','CREATE')")[0][0]
    assert not h.sql("SELECT has_function_privilege('froid_runtime',"
                    "'psique_v2_append(uuid,uuid,text,integer,integer,text,uuid,uuid,uuid,text,text)','EXECUTE')")[0][0]


def test_existing_v1_credit_event_and_quota_keep_their_original_semantics(harness):
    h = harness
    ctx = h.context()
    h.sql("INSERT INTO organization_wallets(organization_id,balance,authority) VALUES(%s,2,'shared')", (ctx.organization_id,))
    h.sql("INSERT INTO organization_member_quotas(organization_id,membership_id,quota_sessions) VALUES(%s,%s,0)",
          (ctx.organization_id, ctx.membership_id))

    def legacy_consume():
        with h.pg.connect(h.dsn, autocommit=True, options="-c role=froid_runtime") as conn, conn.transaction():
            conn.execute("SELECT set_config('app.organization_id',%s,true)", (ctx.organization_id,))
            conn.execute("SELECT set_config('app.membership_id',%s,true)", (ctx.membership_id,))
            return conn.execute("SELECT * FROM froid_apply_credit_event(%s,%s,%s,-1,'consumption','same-session')",
                                (ctx.organization_id, ctx.membership_id, ctx.user_id)).fetchone()

    with pytest.raises(h.pg.Error, match="member quota exhausted"):
        legacy_consume()
    h.sql("DELETE FROM organization_member_quotas WHERE organization_id=%s", (ctx.organization_id,))
    assert legacy_consume()[1:] == (1, True)
    assert legacy_consume()[1:] == (1, False)
    assert h.sql("SELECT ledger_version,analysis_source_id,reserved_delta,funding FROM credit_ledger WHERE organization_id=%s",
                 (ctx.organization_id,)) == [(1, None, 0, None)]


def test_v2_does_not_inherit_v1_quota_or_block_an_already_charged_source(harness):
    h = harness
    ctx = h.paid(2)
    h.sql("INSERT INTO organization_member_quotas(organization_id,membership_id,quota_sessions) VALUES(%s,%s,0)",
          (ctx.organization_id, ctx.membership_id))
    one, two = h.source(ctx, "file"), h.source(ctx, "file")
    assert one != two
    h.consume(ctx, one)
    h.consume(ctx, two)
    for _ in ("reanalysis", "reprocess", "another model", "report regeneration"):
        consumed, _ = h.consume(ctx, one)
        assert not consumed["applied"]
    assert len(h.events(ctx, "CREDIT_CONSUMPTION")) == 2
    assert h.service.balance(ctx)["balance"] == 0
    assert h.sql("SELECT consumed_sessions FROM organization_member_quotas WHERE organization_id=%s",
                 (ctx.organization_id,)) == [(0,)]


def test_trial_restore_before_deadline_returns_only_one_usable_credit(harness):
    h = harness
    ctx = h.trial()
    consumed, _ = h.consume(ctx)
    result = h.service.restore(ctx, consumed["ledger_id"], reason="SYNTHETIC technical failure", evidence_ref="SYNTHETIC case")
    assert result["applied"]
    assert h.service.balance(ctx)["available_balance"] == 10
    assert not h.service.restore(ctx, consumed["ledger_id"], reason="SYNTHETIC retry", evidence_ref="SYNTHETIC case")["applied"]
    assert h.sql("SELECT credits_used FROM psique_trials WHERE organization_id=%s", (ctx.organization_id,)) == [(0,)]


def test_context_role_claim_cannot_grant_financial_privilege(harness):
    h = harness
    ctx = h.trial()
    member = h.context(role="professional", organization_id=ctx.organization_id)
    forged_roles = replace(member, roles=frozenset({"owner"}))
    with pytest.raises(CreditError, match="PSIQUE_CREDIT_ADMIN_REQUIRED"):
        h.service.manual_adjustment(forged_roles, 1, reason="SYNTHETIC forged role", idempotency_key="forged")
    forged_actor = replace(member, user_id=ctx.user_id)
    with pytest.raises(CreditError, match="PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED"):
        h.service.balance(forged_actor)
    consumed, _ = h.consume(ctx)
    outsider = h.paid()
    with pytest.raises(CreditError, match="ORIGINAL_CONSUMPTION_REQUIRED"):
        h.service.restore(outsider, consumed["ledger_id"], reason="SYNTHETIC cross org", evidence_ref="SYNTHETIC case")


def test_reservation_bounds_and_consumed_history_cannot_be_overwritten(harness):
    h = harness
    ctx = h.paid()
    consumed, _ = h.consume(ctx)
    with pytest.raises(h.pg.Error, match="PSIQUE_LEDGER_IMMUTABLE"):
        h.sql("UPDATE credit_ledger SET delta=0 WHERE id=%s", (consumed["ledger_id"],))
    with pytest.raises(h.pg.Error, match="PSIQUE_LEDGER_IMMUTABLE"):
        h.sql("DELETE FROM credit_ledger WHERE id=%s", (consumed["ledger_id"],))
    with pytest.raises(h.pg.Error):
        h.sql("UPDATE organization_wallets SET reserved_balance=1 WHERE organization_id=%s", (ctx.organization_id,))
    with pytest.raises(h.pg.Error):
        h.sql("UPDATE organization_wallets SET balance=-1 WHERE organization_id=%s", (ctx.organization_id,))


def test_stream_hash_is_declared_absent_and_file_identity_detects_changed_bytes(harness):
    h = harness
    ctx = h.paid()
    stream = h.source(ctx)
    assert h.sql("SELECT source_sha256 FROM psique_analysis_sources WHERE id=%s", (stream,)) == [(None,)]
    file_source = h.source(ctx, "file", "file-reference")
    assert h.source(ctx, "file", "file-reference") == file_source
    h.materials["file-reference"] = replace(h.materials["file-reference"], original_chunks=[b"SYNTHETIC changed content"])
    with pytest.raises(CreditError, match="SOURCE_IDENTITY_MISMATCH"):
        h.service.register_source(ctx, "file-reference")


def test_grant_requires_all_historical_hmac_keys(harness):
    h = harness
    h.trial()
    ctx = h.enrolled()
    h.service._keyring = TrialKeyring({"test-v2": h.keys["test-v2"]}, "test-v2")
    with pytest.raises(EvidenceError, match="TRIAL_HISTORICAL_KEY_REQUIRED"):
        h.service.grant_trial(ctx)
    assert not h.events(ctx, "TRIAL_GRANT")
