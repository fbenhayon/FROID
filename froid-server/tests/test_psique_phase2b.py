"""Phase 2B acceptance: Stripe TEST checkout/webhook with real PostgreSQL.

Stripe is exercised through a recording fake that returns the session truth
the tests define; signatures use the real verification code with a synthetic
secret. No network, no LIVE, no real cards: the hosted-payment matrix with
Stripe test cards is a separate, explicitly declared homologation step.
"""

import hashlib
import hmac
import json
import re
import secrets
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psique_pricing
from psique_billing import (
    EVENT_PROCESSING_STATUSES,
    PURCHASE_STATUSES,
    BillingError,
    PsiqueBilling,
    StripeTestClient,
    flatten_session,
    verify_stripe_signature,
)
from psique_catalog_store import install_draft, register_test_mapping
from psique_credits import PsiqueCredits
from psique_identity import TrialKeyring
from tenant_access import AccessContext
from tools.migrate_schema import apply

QA_ACCOUNT = "acct_1UL3JIAg9NSIrvBV"
AUTHORIZED = {
    "FROID_PRO_10": ("prod_VLl3bMw1tZJQuA", "price_1UL3XJAg9NSIrvBV3VTX3ybq", "froid_psique_pro_10_v2_1"),
    "FROID_PRO_25": ("prod_VLl4nNVvpxxcxc", "price_1UL3YkAg9NSIrvBV6IRjcdsj", "froid_psique_pro_25_v2_1"),
    "FROID_PRO_50": ("prod_VLl5GzlS0a3GpK", "price_1UL3ZOAg9NSIrvBVPwXMuaDn", "froid_psique_pro_50_v2_1"),
    "FROID_PRO_100": ("prod_VLl6eS8CVPTMvf", "price_1UL3a2Ag9NSIrvBV5s7lNuaW", "froid_psique_pro_100_v2_1"),
    "FROID_PRO_200": ("prod_VLl6H6AGS2lgrl", "price_1UL3alAg9NSIrvBVzKmjHPEc", "froid_psique_pro_200_v2_1"),
    "FROID_PRO_500": ("prod_VLl89PtmMJFb9z", "price_1UL3bwAg9NSIrvBV8b47kl4L", "froid_psique_pro_500_v2_1"),
}
EXPECTED_TOTALS = {"FROID_PRO_10": 19900, "FROID_PRO_25": 46900, "FROID_PRO_50": 91500,
                   "FROID_PRO_100": 169000, "FROID_PRO_200": 318000, "FROID_PRO_500": 745000}


# -- Static guards -----------------------------------------------------------

def test_purchase_status_check_mirrors_module_constant():
    sql = (ROOT / "migrations/039_psique_stripe_test_checkout.sql").read_text(encoding="utf-8")
    match = re.search(r"psique_purchases_status_check CHECK \(status IN\s*\(([^)]*)\)", sql)
    assert match, "status CHECK not found in 039"
    assert set(re.findall(r"'([A-Za-z_]+)'", match.group(1))) == set(PURCHASE_STATUSES)
    match = re.search(r"processing_status IN \(([^)]*)\)", sql)
    assert set(re.findall(r"'([a-z_]+)'", match.group(1))) == set(EVENT_PROCESSING_STATUSES)


def test_stripe_client_refuses_non_test_keys():
    for key in ("sk_live_SYNTHETIC", "rk_live_SYNTHETIC", "whsec_x", "", "sk_teste"):
        with pytest.raises(BillingError, match="STRIPE_TEST_KEY_REQUIRED"):
            StripeTestClient(key)
    assert StripeTestClient("sk_test_SYNTHETIC") is not None


def test_signature_verification_accepts_valid_and_rejects_forgeries():
    secret_value = secrets.token_hex(16)
    payload = b'{"id":"evt_1","livemode":false}'
    now = time.time()
    stamp = str(int(now))
    good = hmac.new(secret_value.encode(), stamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    verify_stripe_signature(payload, f"t={stamp},v1={good}", secret_value, now=now)
    verify_stripe_signature(payload, f"t={stamp},v1={'0' * 64},v1={good}", secret_value, now=now)
    with pytest.raises(BillingError, match="SIGNATURE_INVALID"):
        verify_stripe_signature(payload + b" ", f"t={stamp},v1={good}", secret_value, now=now)
    with pytest.raises(BillingError, match="SIGNATURE_INVALID"):
        verify_stripe_signature(payload, f"t={stamp},v1={'0' * 64}", secret_value, now=now)
    with pytest.raises(BillingError, match="SIGNATURE_TIMESTAMP_OUT_OF_TOLERANCE"):
        verify_stripe_signature(payload, f"t={stamp},v1={good}", secret_value, now=now + 301)
    with pytest.raises(BillingError, match="SIGNATURE_HEADER_INVALID"):
        verify_stripe_signature(payload, "v1=" + good, secret_value, now=now)
    with pytest.raises(BillingError, match="WEBHOOK_SECRET_REQUIRED"):
        verify_stripe_signature(payload, f"t={stamp},v1={good}", "", now=now)


def test_flatten_session_projects_only_validated_fields():
    flat = flatten_session({
        "id": "cs_test_a", "livemode": False, "payment_status": "paid",
        "amount_total": 19900, "currency": "brl", "client_reference_id": "p1",
        "payment_intent": "pi_1", "metadata": {"purchase_id": "p1", "other": "x"},
        "line_items": {"data": [{"quantity": 1, "price": {"id": "price_1", "product": "prod_1"}}]},
    })
    assert flat["price_id"] == "price_1" and flat["product_id"] == "prod_1"
    assert flat["quantity"] == 1 and flat["metadata"] == {"purchase_id": "p1"}
    assert "line_items" not in flat


# -- PostgreSQL fixtures ------------------------------------------------------

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
                apply(conn, ROOT / "migrations", "039_psique_stripe_test_checkout", name)
                config = psique_pricing.load_config()
                install_draft(conn, config, actor="phase2b-tests")
                for code, (product_id, price_id, lookup_key) in AUTHORIZED.items():
                    offer = psique_pricing.offer_for(config, code)
                    metadata = {"froid_product": "psique", "family": "psique_credits",
                                "product_code": code, "credits": str(offer["credits"]),
                                "pricing_version": config["version"],
                                "pricing_hash": psique_pricing.pricing_hash(config)}
                    register_test_mapping(
                        conn, version=config["version"], product_code=code,
                        account_id=QA_ACCOUNT,
                        product={"id": product_id, "livemode": False, "active": True,
                                 "metadata": metadata},
                        price={"id": price_id, "livemode": False, "active": True,
                               "product": product_id, "currency": "brl",
                               "unit_amount": offer["total_cents"], "type": "one_time",
                               "recurring": None, "billing_scheme": "per_unit",
                               "lookup_key": lookup_key, "metadata": metadata},
                        actor="phase2b-tests", lookup_key=lookup_key)
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


class FakeStripe:
    """Records requests; the tests define the session truth Stripe returns."""

    def __init__(self):
        self.sessions = {}
        self.created = []

    def create_checkout_session(self, *, price_id, purchase_id, success_url, cancel_url):
        self.created.append({"price_id": price_id, "purchase_id": purchase_id,
                             "success_url": success_url, "cancel_url": cancel_url})
        session_id = "cs_test_" + uuid.uuid4().hex
        self.sessions[session_id] = {"id": session_id, "livemode": False,
                                     "payment_status": "unpaid", "url": "https://checkout.stripe.com/c/" + session_id,
                                     "client_reference_id": purchase_id,
                                     "metadata": {"purchase_id": purchase_id}}
        return dict(self.sessions[session_id])

    def get_checkout_session(self, session_id):
        if session_id not in self.sessions:
            raise BillingError("STRIPE_HTTP_404 No such checkout.session")
        return dict(self.sessions[session_id])


class Harness:
    def __init__(self, dsn):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        self.stripe = FakeStripe()
        self.webhook_secret = secrets.token_hex(24)
        factory = lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime")
        self.billing = PsiqueBilling(
            factory, stripe_client=self.stripe, webhook_secret=self.webhook_secret,
            account_id=QA_ACCOUNT, pricing_version="2.1",
            success_url="https://example.invalid/ok", cancel_url="https://example.invalid/no")
        self.credits = PsiqueCredits(
            factory, identity_loader=lambda user: None, material_loader=lambda user, ref: None,
            keyring=TrialKeyring({"test": secrets.token_bytes(32)}, "test"))

    def sql(self, query, params=()):
        with self.pg.connect(self.dsn, autocommit=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def context(self, *, role="owner", organization_id=None):
        org = organization_id or str(uuid.uuid4())
        user = str(uuid.uuid4())
        member = str(uuid.uuid4())
        if organization_id is None:
            self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                     "VALUES(%s,'solo','SYNTHETIC test','SYNTHETIC test')", (org,))
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (member, org, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,%s)", (member, role))
        return AccessContext.create(organization_id=org, membership_id=member, user_id=user,
                                    roles=[role], organization_type="solo")

    def enrolled(self, **kwargs):
        ctx = self.context(**kwargs)
        self.credits.enroll_empty_wallet(ctx)
        return ctx

    def checkout(self, ctx, code, idem=None):
        return self.billing.checkout(ctx, {"product_code": code},
                                     idempotency_key=idem or uuid.uuid4().hex)

    def session_of(self, result):
        return self.sql("SELECT stripe_checkout_session_id FROM psique_purchases WHERE id=%s",
                        (result["purchase_id"],))[0][0]

    def pay(self, session_id, purchase_id, code, **overrides):
        """Mark the fake session as paid with the Stripe-side truth."""
        product_id, price_id, _ = AUTHORIZED[code]
        session = self.stripe.sessions[session_id]
        session.update({"payment_status": "paid", "amount_total": EXPECTED_TOTALS[code],
                        "currency": "brl", "payment_intent": "pi_" + uuid.uuid4().hex[:20],
                        "client_reference_id": str(purchase_id),
                        "metadata": {"purchase_id": str(purchase_id)},
                        "line_items": {"data": [{"quantity": 1,
                                                 "price": {"id": price_id, "product": product_id}}]}})
        session.update(overrides)

    def sign(self, payload: bytes, *, secret=None, timestamp=None):
        stamp = str(int(timestamp if timestamp is not None else time.time()))
        digest = hmac.new((secret or self.webhook_secret).encode(),
                          stamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
        return f"t={stamp},v1={digest}"

    def event(self, event_type, target, event_id=None):
        payload = json.dumps({"id": event_id or ("evt_" + uuid.uuid4().hex),
                              "type": event_type, "livemode": False,
                              "data": {"object": target}}).encode()
        return self.billing.webhook(payload, self.sign(payload))

    def balance(self, ctx):
        return self.sql("SELECT balance,reserved_balance FROM organization_wallets "
                        "WHERE organization_id=%s", (ctx.organization_id,))[0]

    def grants(self, ctx):
        return self.sql("SELECT id,delta,purchase_id FROM credit_ledger "
                        "WHERE organization_id=%s AND event_type='CREDIT_PURCHASE'",
                        (ctx.organization_id,))

    def paid_flow(self, ctx, code, idem=None):
        result = self.checkout(ctx, code, idem)
        session_id = self.session_of(result)
        self.pay(session_id, result["purchase_id"], code)
        status, body = self.event("checkout.session.completed",
                                  {"id": session_id, "livemode": False})
        return result, session_id, status, body


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


# -- Checkout ----------------------------------------------------------------

@pytest.mark.parametrize("code", sorted(AUTHORIZED))
def test_each_sku_grants_exact_credits_once_paid(harness, code):
    h = harness
    ctx = h.enrolled()
    result, _session_id, status, body = h.paid_flow(ctx, code)
    assert status == 200 and body["applied"] is True
    credits = int(code.rsplit("_", 1)[1])
    assert body["credits"] == credits
    assert h.balance(ctx) == (credits, 0)
    grants = h.grants(ctx)
    assert len(grants) == 1 and grants[0][1] == credits
    assert str(grants[0][2]) == str(result["purchase_id"])
    state = h.billing.purchase_state(ctx, str(result["purchase_id"]))
    assert state["status"] == "APPLIED" and state["total_cents"] == EXPECTED_TOTALS[code]
    row = h.sql("SELECT stripe_payment_intent_id,applied_at FROM psique_purchases WHERE id=%s",
                (result["purchase_id"],))[0]
    assert row[0].startswith("pi_") and row[1] is not None


def test_checkout_sends_only_price_and_quantity_one_to_stripe(harness):
    h = harness
    ctx = h.enrolled()
    h.checkout(ctx, "FROID_PRO_10")
    sent = h.stripe.created[-1]
    assert sent["price_id"] == AUTHORIZED["FROID_PRO_10"][1]
    assert set(sent) == {"price_id", "purchase_id", "success_url", "cancel_url"}


def test_browser_cannot_send_amount_credits_or_price(harness):
    h = harness
    ctx = h.enrolled()
    for body in ({"product_code": "FROID_PRO_10", "credits": 500},
                 {"product_code": "FROID_PRO_10", "amount": 1},
                 {"product_code": "FROID_PRO_10", "currency": "usd"},
                 {"product_code": "FROID_PRO_10", "stripe_price_id": "price_x"},
                 {"product_code": "FROID_PRO_10", "product_id": "prod_x"},
                 {"credits": 500}, {}, []):
        with pytest.raises(BillingError, match="CHECKOUT_BODY_MUST_BE_PRODUCT_CODE_ONLY"):
            h.billing.checkout(ctx, body, idempotency_key=uuid.uuid4().hex)
    assert h.stripe.created == [] and h.grants(ctx) == []


def test_checkout_idempotency_returns_same_purchase(harness):
    h = harness
    ctx = h.enrolled()
    first = h.checkout(ctx, "FROID_PRO_25", idem="same-key")
    second = h.checkout(ctx, "FROID_PRO_25", idem="same-key")
    assert first["purchase_id"] == second["purchase_id"]
    assert len(h.stripe.created) == 1
    with pytest.raises(BillingError, match="IDEMPOTENCY_MISMATCH"):
        h.checkout(ctx, "FROID_PRO_50", idem="same-key")


def test_checkout_requires_admin_enrolled_wallet_and_known_product(harness):
    h = harness
    owner = h.enrolled()
    professional = h.context(role="professional", organization_id=owner.organization_id)
    with pytest.raises(BillingError, match="PSIQUE_BILLING_ADMIN_REQUIRED"):
        h.checkout(professional, "FROID_PRO_10")
    not_enrolled = h.context()
    with pytest.raises(BillingError, match="PSIQUE_WALLET_REQUIRED"):
        h.checkout(not_enrolled, "FROID_PRO_10")
    ctx = h.enrolled()
    for code in ("FROID_FLEX", "FROID_ORG_LICENSE", "NOPE"):
        with pytest.raises(BillingError, match="PRODUCT_CODE_NOT_PURCHASABLE|PRODUCT_CODE"):
            h.checkout(ctx, code)
    assert h.stripe.created == []


def test_cross_org_purchase_state_denied(harness):
    h = harness
    ctx = h.enrolled()
    other = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    with pytest.raises(BillingError, match="PURCHASE_ACCESS_DENIED"):
        h.billing.purchase_state(other, str(result["purchase_id"]))


# -- Webhook: idempotency and duplicates --------------------------------------

def test_duplicate_webhook_delivery_grants_nothing_extra(harness):
    h = harness
    ctx = h.enrolled()
    _result, session_id, _, _ = h.paid_flow(ctx, "FROID_PRO_10")
    payload = json.dumps({"id": "evt_" + uuid.uuid4().hex, "type": "checkout.session.completed",
                          "livemode": False, "data": {"object": {"id": session_id, "livemode": False}}}).encode()
    first = h.billing.webhook(payload, h.sign(payload))
    second = h.billing.webhook(payload, h.sign(payload))
    assert first[0] == 200 and second[0] == 200
    assert h.balance(ctx) == (10, 0) and len(h.grants(ctx)) == 1


def test_new_event_for_already_applied_purchase_is_resolved(harness):
    h = harness
    ctx = h.enrolled()
    _, session_id, _, _ = h.paid_flow(ctx, "FROID_PRO_25")
    status, body = h.event("checkout.session.completed", {"id": session_id, "livemode": False})
    assert status == 200 and body["applied"] is False
    assert body["code"] == "PURCHASE_ALREADY_APPLIED"
    assert h.balance(ctx) == (25, 0)


def test_reload_and_state_polling_never_grant(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    for _ in range(3):
        state = h.billing.purchase_state(ctx, str(result["purchase_id"]))
        assert state["status"] == "CHECKOUT_CREATED"
    assert h.balance(ctx) == (0, 0) and h.grants(ctx) == []


def test_concurrent_deliveries_of_same_event_grant_once(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_50")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_50")
    payload = json.dumps({"id": "evt_" + uuid.uuid4().hex, "type": "checkout.session.completed",
                          "livemode": False, "data": {"object": {"id": session_id, "livemode": False}}}).encode()
    header = h.sign(payload)
    outcomes = race(lambda: h.billing.webhook(payload, header),
                    lambda: h.billing.webhook(payload, header))
    assert all(isinstance(o, tuple) and o[0] == 200 for o in outcomes)
    assert h.balance(ctx) == (50, 0) and len(h.grants(ctx)) == 1


def test_two_events_for_same_purchase_concurrently_grant_once(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_100")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_100")
    target = {"id": session_id, "livemode": False}
    outcomes = race(lambda: h.event("checkout.session.completed", target),
                    lambda: h.event("checkout.session.async_payment_succeeded", target))
    assert all(isinstance(o, tuple) and o[0] == 200 for o in outcomes)
    assert h.balance(ctx) == (100, 0) and len(h.grants(ctx)) == 1


# -- Webhook: failures never grant ---------------------------------------------

def test_async_flow_pending_then_succeeded_grants_once(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10", payment_status="unpaid")
    _status, body = h.event("checkout.session.completed", {"id": session_id, "livemode": False})
    assert body["code"] == "ASYNC_PAYMENT_PENDING" and h.balance(ctx) == (0, 0)
    assert h.billing.purchase_state(ctx, str(result["purchase_id"]))["status"] == "PENDING_PAYMENT"
    h.stripe.sessions[session_id]["payment_status"] = "paid"
    _status, body = h.event("checkout.session.async_payment_succeeded", {"id": session_id, "livemode": False})
    assert body["applied"] is True and h.balance(ctx) == (10, 0)


def test_declined_and_abandoned_payments_grant_nothing(harness):
    h = harness
    ctx = h.enrolled()
    declined = h.checkout(ctx, "FROID_PRO_10")
    status, body = h.event("payment_intent.payment_failed", {"id": "pi_" + uuid.uuid4().hex[:20]})
    assert status == 200 and body["outcome"] == "RESOLVED"
    expired = h.checkout(ctx, "FROID_PRO_25")
    status, body = h.event("checkout.session.expired",
                           {"id": h.session_of(expired), "livemode": False})
    assert body["applied"] is True
    assert h.billing.purchase_state(ctx, str(expired["purchase_id"]))["status"] == "EXPIRED"
    failed = h.checkout(ctx, "FROID_PRO_50")
    status, body = h.event("checkout.session.async_payment_failed",
                           {"id": h.session_of(failed), "livemode": False})
    assert h.billing.purchase_state(ctx, str(failed["purchase_id"]))["status"] == "FAILED"
    assert h.balance(ctx) == (0, 0) and h.grants(ctx) == []
    assert h.billing.purchase_state(ctx, str(declined["purchase_id"]))["status"] == "CHECKOUT_CREATED"


def test_payment_intent_succeeded_is_audit_only(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10")
    status, body = h.event("payment_intent.succeeded", {"id": "pi_" + uuid.uuid4().hex[:20]})
    assert status == 200 and body["outcome"] == "RESOLVED"
    assert h.balance(ctx) == (0, 0) and h.grants(ctx) == []


@pytest.mark.parametrize("mutation,code", [
    ({"amount_total": 1}, "WRONG_AMOUNT"),
    ({"amount_total": 745000}, "WRONG_AMOUNT"),
    ({"currency": "usd"}, "WRONG_CURRENCY"),
    ({"line_items": {"data": [{"quantity": 1, "price": {
        "id": AUTHORIZED["FROID_PRO_500"][1], "product": AUTHORIZED["FROID_PRO_10"][0]}}]}}, "WRONG_PRICE"),
    ({"line_items": {"data": [{"quantity": 1, "price": {
        "id": AUTHORIZED["FROID_PRO_10"][1], "product": AUTHORIZED["FROID_PRO_500"][0]}}]}}, "WRONG_PRODUCT"),
    ({"line_items": {"data": [{"quantity": 2, "price": {
        "id": AUTHORIZED["FROID_PRO_10"][1], "product": AUTHORIZED["FROID_PRO_10"][0]}}]}}, "WRONG_QUANTITY"),
    ({"client_reference_id": "tampered"}, "WRONG_PURCHASE_REFERENCE"),
])
def test_session_truth_divergence_is_rejected_for_review(harness, mutation, code):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10", **mutation)
    status, body = h.event("checkout.session.completed", {"id": session_id, "livemode": False})
    assert status == 200 and body["applied"] is False and body["code"] == code
    assert h.balance(ctx) == (0, 0) and h.grants(ctx) == []
    assert h.billing.purchase_state(ctx, str(result["purchase_id"]))["status"] == "REVIEW_REQUIRED"


def test_wrong_account_recorded_event_is_rejected(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10")
    event_id = "evt_" + uuid.uuid4().hex
    h.sql("SELECT psique_v2_stripe_event(%s,false,%s,'checkout.session.completed',%s,%s)",
          ("acct_SYNTHETICother", event_id, session_id, hashlib.sha256(b"x").hexdigest()))
    row = h.sql("SELECT psique_v2_apply_purchase(%s,%s::jsonb)",
                (event_id, json.dumps(flatten_session(h.stripe.sessions[session_id]))))
    assert row[0][0]["code"] == "WRONG_STRIPE_ACCOUNT"
    assert h.grants(ctx) == []


def test_unknown_session_and_unknown_event_type(harness):
    h = harness
    ctx = h.enrolled()
    ghost = "cs_test_" + uuid.uuid4().hex
    status, body = h.event("checkout.session.completed", {"id": ghost, "livemode": False})
    # A session our key cannot retrieve is another account's or fabricated.
    assert status == 200 and body["applied"] is False and body["outcome"] == "RESOLVED"
    orphan = "cs_test_" + uuid.uuid4().hex
    h.stripe.sessions[orphan] = {"id": orphan, "livemode": False, "payment_status": "paid",
                                 "amount_total": 19900, "currency": "brl"}
    status, body = h.event("checkout.session.completed", {"id": orphan, "livemode": False})
    assert status == 200 and body["code"] == "PURCHASE_NOT_FOUND"
    status, body = h.event("customer.created", {"id": "cus_x"})
    assert status == 200 and body["outcome"] == "RESOLVED"
    assert h.grants(ctx) == []


def test_disputes_and_refunds_only_open_review(harness):
    h = harness
    ctx = h.enrolled()
    result, _session_id, _, _ = h.paid_flow(ctx, "FROID_PRO_25")
    for event_type in ("charge.dispute.created", "charge.refunded", "refund.created"):
        status, body = h.event(event_type, {"id": "ch_" + uuid.uuid4().hex[:20]})
        assert status == 200 and body["outcome"] == "REVIEW"
    assert h.balance(ctx) == (25, 0)
    assert h.billing.purchase_state(ctx, str(result["purchase_id"]))["status"] == "APPLIED"
    reviews = h.sql("SELECT count(*) FROM psique_stripe_events WHERE processing_status='review'")
    assert reviews[0][0] >= 3


def test_terminal_purchase_with_same_key_is_refused(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10", idem="chave-terminal")
    h.event("checkout.session.expired", {"id": h.session_of(result), "livemode": False})
    assert h.billing.purchase_state(ctx, str(result["purchase_id"]))["status"] == "EXPIRED"
    with pytest.raises(BillingError, match="PURCHASE_TERMINAL_USE_NEW_IDEMPOTENCY_KEY"):
        h.checkout(ctx, "FROID_PRO_10", idem="chave-terminal")
    fresh = h.checkout(ctx, "FROID_PRO_10", idem="chave-nova")
    assert fresh["purchase_id"] != result["purchase_id"]
    assert h.grants(ctx) == []


def test_router_requires_idempotency_header():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from psique_api import build_psique_v2_billing_router

    captured = {}

    class StubBilling:
        def checkout(self, context, body, *, idempotency_key):
            captured["key"] = idempotency_key
            return {"purchase_id": "SYNTHETIC", "status": "CREATED", "checkout_url": "https://x"}

    app = FastAPI()
    app.include_router(build_psique_v2_billing_router(lambda: StubBilling(), lambda: object()))
    client = TestClient(app)
    denied = client.post("/api/psique/v2/checkout", json={"product_code": "FROID_PRO_10"})
    assert denied.status_code == 422 and denied.json()["detail"] == "IDEMPOTENCY_KEY_REQUIRED"
    blank = client.post("/api/psique/v2/checkout", json={"product_code": "FROID_PRO_10"},
                        headers={"X-Idempotency-Key": "   "})
    assert blank.status_code == 422
    ok = client.post("/api/psique/v2/checkout", json={"product_code": "FROID_PRO_10"},
                     headers={"X-Idempotency-Key": "cliente-define"})
    assert ok.status_code == 200 and captured["key"] == "cliente-define"


# -- Webhook: signature and payload boundary -----------------------------------

def test_invalid_signature_is_rejected_and_not_recorded(harness):
    h = harness
    before = h.sql("SELECT count(*) FROM psique_stripe_events")[0][0]
    payload = json.dumps({"id": "evt_" + uuid.uuid4().hex, "type": "checkout.session.completed",
                          "livemode": False, "data": {"object": {"id": "cs_test_x", "livemode": False}}}).encode()
    assert h.billing.webhook(payload, h.sign(payload, secret="wrong" * 8))[0] == 400
    assert h.billing.webhook(payload, h.sign(payload, timestamp=time.time() - 4000))[0] == 400
    assert h.billing.webhook(payload, "")[0] == 400
    assert h.billing.webhook(b"not-json", h.sign(b"not-json"))[0] == 400
    assert h.sql("SELECT count(*) FROM psique_stripe_events")[0][0] == before


def test_live_event_is_refused_loudly(harness):
    h = harness
    payload = json.dumps({"id": "evt_" + uuid.uuid4().hex, "type": "checkout.session.completed",
                          "livemode": True, "data": {"object": {"id": "cs_test_x", "livemode": False}}}).encode()
    status, body = h.billing.webhook(payload, h.sign(payload))
    assert status == 400 and body["code"] == "LIVE_EVENT_REFUSED"


def test_same_event_id_with_different_payload_is_a_conflict(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10")
    event_id = "evt_" + uuid.uuid4().hex
    h.event("checkout.session.completed", {"id": session_id, "livemode": False}, event_id=event_id)
    with pytest.raises(BillingError, match="STRIPE_EVENT_PAYLOAD_MISMATCH"):
        h.event("checkout.session.expired", {"id": session_id, "livemode": False}, event_id=event_id)


# -- Failure of the grant keeps the event reprocessable -------------------------

def test_grant_failure_rolls_back_and_event_stays_reprocessable(harness):
    h = harness
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10")
    h.sql("UPDATE organization_wallets SET credit_model='v1' WHERE organization_id=%s",
          (ctx.organization_id,))
    event_id = "evt_" + uuid.uuid4().hex
    with pytest.raises(BillingError, match="PSIQUE_WALLET_REQUIRED"):
        h.event("checkout.session.completed", {"id": session_id, "livemode": False},
                event_id=event_id)
    assert h.billing.purchase_state(ctx, str(result["purchase_id"]))["status"] == "CHECKOUT_CREATED"
    assert h.sql("SELECT processing_status FROM psique_stripe_events WHERE stripe_event_id=%s",
                 (event_id,))[0][0] == "received"
    h.sql("UPDATE organization_wallets SET credit_model='psique_v2' WHERE organization_id=%s",
          (ctx.organization_id,))
    _status, body = h.event("checkout.session.completed", {"id": session_id, "livemode": False},
                            event_id=event_id)
    assert body["applied"] is True and h.balance(ctx) == (10, 0)
    assert len(h.grants(ctx)) == 1
