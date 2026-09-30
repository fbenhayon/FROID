"""Phase 2C acceptance: organizational license over Stripe TEST, real PostgreSQL.

Stripe is a recording fake; the tier structure and every quantity from 1 to
200 are proven locally against the backend formula, and the real-account
preview homologation is a separate explicit tool run recorded in the report.
"""

import json
import re
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psique_pricing
from psique_billing import BillingError
from psique_catalog_store import (
    install_draft,
    license_expected_tiers,
    register_license_test_mapping,
)
from psique_license import (
    CHANGE_STATUSES,
    CLINICAL_STATUSES,
    LICENSE_STATUSES,
    PsiqueLicense,
)
from tenant_access import AccessContext
from tools.migrate_schema import apply

QA_ACCOUNT = "acct_1UL3JIAg9NSIrvBV"
LOOKUP = "froid_psique_org_license_v2_1"


# -- Static proofs ------------------------------------------------------------

def test_graduated_tiers_reproduce_backend_formula_for_every_quantity():
    config = psique_pricing.load_config()
    tiers = license_expected_tiers(config)
    for quantity in range(1, 201):
        total = 0
        floor = 0
        for tier in tiers:
            ceiling = tier["up_to"] if tier["up_to"] is not None else quantity
            count = max(0, min(quantity, ceiling) - floor)
            if count and tier["flat_amount"]:
                total += tier["flat_amount"]
            total += count * tier["unit_amount"]
            floor = ceiling
            if floor >= quantity:
                break
        expected = psique_pricing.organization_quote(config, quantity)["monthly_cents"]
        assert total == expected, f"quantity {quantity}: tiers {total} != formula {expected}"


def test_checklist_price_points_are_exact():
    config = psique_pricing.load_config()
    points = {1: 49900, 2: 49900, 5: 85600, 10: 135100, 20: 224100, 25: 268600,
              30: 308100, 50: 466100, 100: 811100, 200: 1401100}
    for count, cents in points.items():
        quote = psique_pricing.organization_quote(config, count)
        assert quote["monthly_cents"] == cents and not quote["enterprise_required"]
    enterprise = psique_pricing.organization_quote(config, 201)
    assert enterprise["enterprise_required"] and enterprise["monthly_cents"] is None


def test_migration_040_domains_mirror_module_constants():
    sql = (ROOT / "migrations/040_psique_org_license_test.sql").read_text(encoding="utf-8")
    def domain(column):
        match = re.search(column + r" IN\s*\(([^)]*)\)", sql)
        return set(re.findall(r"'([A-Z_]+)'", match.group(1)))
    assert domain("clinical_status") == set(CLINICAL_STATUSES)
    assert domain("license_status") == set(LICENSE_STATUSES)
    assert domain("change_status") == set(CHANGE_STATUSES)


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
                apply(conn, ROOT / "migrations", "041_psique_financial_lookup_indexes", name)
                config = psique_pricing.load_config()
                install_draft(conn, config, actor="phase2c-tests")
                metadata = {"froid_product": "psique", "family": "psique_license",
                            "product_code": "FROID_ORG_LICENSE",
                            "pricing_version": config["version"],
                            "pricing_hash": psique_pricing.pricing_hash(config)}
                register_license_test_mapping(
                    conn, version=config["version"], account_id=QA_ACCOUNT,
                    product={"id": "prod_SYNTHETIClicense", "livemode": False,
                             "active": True, "metadata": metadata},
                    price={"id": "price_SYNTHETIClicense", "livemode": False, "active": True,
                           "product": "prod_SYNTHETIClicense", "currency": "brl",
                           "recurring": {"interval": "month", "interval_count": 1},
                           "billing_scheme": "tiered", "tiers_mode": "graduated",
                           "lookup_key": LOOKUP, "metadata": metadata,
                           "tiers": [{"up_to": t["up_to"], "flat_amount": t["flat_amount"],
                                      "unit_amount": t["unit_amount"]}
                                     for t in license_expected_tiers(config)]},
                    actor="phase2c-tests", lookup_key=LOOKUP)
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


class FakeStripeSubscriptions:
    """Records every call; quantity/cancel state is the truth tests assert on."""

    def __init__(self):
        self.customers = []
        self.subscriptions = {}
        self.quantity_updates = []
        self.cancel_calls = []

    def create_customer(self, *, description, email):
        customer_id = "cus_SYN" + uuid.uuid4().hex[:16]
        self.customers.append({"id": customer_id, "description": description, "email": email})
        return {"id": customer_id, "livemode": False}

    def create_license_subscription(self, *, customer_id, price_id, quantity):
        subscription_id = "sub_SYN" + uuid.uuid4().hex[:16]
        item_id = "si_SYN" + uuid.uuid4().hex[:16]
        record = {"id": subscription_id, "livemode": False, "status": "active",
                  "customer": customer_id, "cancel_at_period_end": False,
                  "current_period_end": 1800000000,
                  "items": {"data": [{"id": item_id, "quantity": quantity,
                                      "price": {"id": price_id}}]}}
        self.subscriptions[subscription_id] = record
        return json.loads(json.dumps(record))

    def update_subscription_quantity(self, *, subscription_item_id, quantity):
        self.quantity_updates.append({"item": subscription_item_id, "quantity": quantity})
        for record in self.subscriptions.values():
            if record["items"]["data"][0]["id"] == subscription_item_id:
                record["items"]["data"][0]["quantity"] = quantity
        return {"id": subscription_item_id, "quantity": quantity}

    def set_cancel_at_period_end(self, *, subscription_id, cancel):
        self.cancel_calls.append({"subscription": subscription_id, "cancel": cancel})
        self.subscriptions[subscription_id]["cancel_at_period_end"] = cancel
        return {"id": subscription_id, "cancel_at_period_end": cancel}


class Harness:
    def __init__(self, dsn):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        self.stripe = FakeStripeSubscriptions()
        factory = lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime")
        self.license = PsiqueLicense(
            factory, stripe_client=self.stripe, account_id=QA_ACCOUNT,
            billing_email_resolver=lambda ctx: "SYNTHETIC-faturamento@example.invalid")

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
                     "VALUES(%s,'clinic','SYNTHETIC test','SYNTHETIC test')", (org,))
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (member, org, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,%s)", (member, role))
        return AccessContext.create(organization_id=org, membership_id=member, user_id=user,
                                    roles=[role], organization_type="clinic")

    def clinicians(self, ctx, count):
        """Create members and activate exactly `count` clinical seats."""
        created = []
        for _ in range(count):
            other = self.context(role="professional", organization_id=ctx.organization_id)
            self.license.set_clinical(ctx, other.membership_id, active=True)
            created.append(other.membership_id)
        return created

    def active(self, ctx):
        return self.license.state(ctx)["active_clinical_seat_count"]

    def change(self, ctx):
        preview = self.license.preview(ctx)
        return self.license.confirm(ctx, preview_id=preview["preview_id"],
                                    expected_version=preview["license_version"])


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


# -- Clinical status: immediate and separate from billing ----------------------

def test_clinical_activation_is_immediate_idempotent_and_admin_only(harness):
    h = harness
    ctx = h.context()
    target = h.context(role="professional", organization_id=ctx.organization_id)
    assert h.active(ctx) == 0
    result = h.license.set_clinical(ctx, target.membership_id, active=True)
    assert result["changed"] is True and result["active_clinical_seat_count"] == 1
    result = h.license.set_clinical(ctx, target.membership_id, active=True)
    assert result["changed"] is False and h.active(ctx) == 1
    with pytest.raises(BillingError, match="PSIQUE_BILLING_ADMIN_REQUIRED"):
        h.license.set_clinical(target, target.membership_id, active=True)
    outsider = h.context()
    with pytest.raises(BillingError, match="CLINICAL_TARGET_MEMBERSHIP_REQUIRED"):
        h.license.set_clinical(outsider, target.membership_id, active=True)


def test_non_clinical_members_are_free_and_unlimited(harness):
    h = harness
    ctx = h.context()
    for _ in range(5):
        h.context(role="professional", organization_id=ctx.organization_id)
    h.context(role="administrator", organization_id=ctx.organization_id)
    assert h.active(ctx) == 0
    result = h.change(ctx)
    assert result["applied"] is True and result.get("code") == "NO_LICENSE_REQUIRED"
    assert h.stripe.customers == [] and h.stripe.quantity_updates == []


# -- Subscription lifecycle ----------------------------------------------------

def test_first_subscription_is_created_with_active_count(harness):
    h = harness
    ctx = h.context()
    h.clinicians(ctx, 2)
    preview = h.license.preview(ctx)
    assert preview["to_active"] == 2 and preview["quote"]["monthly_cents"] == 49900
    assert preview["requires_stripe_quantity_update"] is True
    result = h.license.confirm(ctx, preview_id=preview["preview_id"],
                               expected_version=preview["license_version"])
    assert result["applied"] is True
    assert result["billed_clinical_seat_count"] == 2
    assert result["next_cycle_clinical_seat_count"] == 2
    assert result["license_status"] == "ACTIVE"
    assert len(h.stripe.customers) == 1
    state = h.license.state(ctx)
    assert state["stripe_subscription_id"].startswith("sub_")
    assert state["license_version"] == 1
    assert h.sql("SELECT count(*) FROM credit_ledger WHERE organization_id=%s",
                 (ctx.organization_id,))[0][0] == 0  # a licenca nunca concede credito


def test_increase_bills_only_new_seats_with_accrued_proration(harness):
    h = harness
    ctx = h.context()
    h.clinicians(ctx, 2)
    h.change(ctx)
    h.clinicians(ctx, 1)
    result = h.change(ctx)
    assert result["billed_clinical_seat_count"] == 3
    assert h.stripe.quantity_updates == [{"item": h.stripe.quantity_updates[0]["item"], "quantity": 3}]
    change = h.sql("SELECT stripe_result FROM psique_seat_changes WHERE organization_id=%s "
                   "AND change_status='CONFIRMED' ORDER BY created_at DESC LIMIT 1",
                   (ctx.organization_id,))[0][0]
    assert change["proration_behavior"] == "create_prorations"


def test_ten_to_eight_to_nine_never_charges_again(harness):
    h = harness
    ctx = h.context()
    members = h.clinicians(ctx, 10)
    h.change(ctx)
    updates_after_setup = len(h.stripe.quantity_updates)
    for membership in members[:2]:
        h.license.set_clinical(ctx, membership, active=False)
    result = h.change(ctx)
    assert result["billed_clinical_seat_count"] == 10
    assert result["next_cycle_clinical_seat_count"] == 8
    h.license.set_clinical(ctx, members[0], active=True)
    result = h.change(ctx)
    assert result["billed_clinical_seat_count"] == 10
    assert result["next_cycle_clinical_seat_count"] == 9
    assert len(h.stripe.quantity_updates) == updates_after_setup
    assert h.stripe.cancel_calls == []


def test_ten_to_eight_to_eleven_charges_only_the_eleventh(harness):
    h = harness
    ctx = h.context()
    members = h.clinicians(ctx, 10)
    h.change(ctx)
    for membership in members[:2]:
        h.license.set_clinical(ctx, membership, active=False)
    h.change(ctx)
    h.license.set_clinical(ctx, members[0], active=True)
    h.license.set_clinical(ctx, members[1], active=True)
    h.clinicians(ctx, 1)
    result = h.change(ctx)
    assert result["billed_clinical_seat_count"] == 11
    assert result["next_cycle_clinical_seat_count"] == 11
    assert [u["quantity"] for u in h.stripe.quantity_updates] == [11]


def test_zero_cancels_at_period_end_and_reactivation_uncancels(harness):
    h = harness
    ctx = h.context()
    members = h.clinicians(ctx, 2)
    h.change(ctx)
    for membership in members:
        h.license.set_clinical(ctx, membership, active=False)
    result = h.change(ctx)
    assert result["license_status"] == "CANCEL_AT_PERIOD_END"
    assert result["next_cycle_clinical_seat_count"] == 0
    assert h.stripe.cancel_calls[-1]["cancel"] is True
    h.license.set_clinical(ctx, members[0], active=True)
    result = h.change(ctx)
    assert result["license_status"] == "ACTIVE"
    assert result["billed_clinical_seat_count"] == 2
    assert result["next_cycle_clinical_seat_count"] == 1
    assert h.stripe.cancel_calls[-1]["cancel"] is False
    assert h.stripe.quantity_updates == []


def test_enterprise_scale_has_no_self_service(harness):
    h = harness
    ctx = h.context()
    h.sql("""
        WITH new_users AS (
            INSERT INTO users(id,email)
            SELECT gen_random_uuid(), 'syn'||n||'-'||%s||'@example.invalid'
            FROM generate_series(1,201) n RETURNING id
        ), new_members AS (
            INSERT INTO organization_memberships(id,organization_id,user_id)
            SELECT gen_random_uuid(), %s, id FROM new_users RETURNING id, organization_id
        )
        INSERT INTO psique_clinical_memberships(membership_id,organization_id,clinical_status,activated_at)
        SELECT id, organization_id, 'ACTIVE', now() FROM new_members
    """, (uuid.uuid4().hex, ctx.organization_id))
    assert h.active(ctx) == 201
    with pytest.raises(BillingError, match="ENTERPRISE_REQUIRED_NO_SELF_SERVICE"):
        h.license.preview(ctx)
    assert h.stripe.customers == []


# -- Versioning, staleness and compensation ------------------------------------

def test_new_preview_supersedes_and_wrong_version_aborts(harness):
    h = harness
    ctx = h.context()
    h.clinicians(ctx, 2)
    h.change(ctx)
    h.clinicians(ctx, 1)
    first = h.license.preview(ctx)
    second = h.license.preview(ctx)
    result = h.license.confirm(ctx, preview_id=first["preview_id"],
                               expected_version=first["license_version"])
    assert result["applied"] is False and result["code"] == "PREVIEW_SUPERSEDED"
    result = h.license.confirm(ctx, preview_id=second["preview_id"], expected_version=999)
    assert result["applied"] is False and result["code"] == "LICENSE_VERSION_CONFLICT"
    # Cada confirm recusado compensou a quantidade de volta ao faturado (2).
    assert [u["quantity"] for u in h.stripe.quantity_updates] == [3, 2, 3, 2]


def test_stale_seat_count_aborts_and_compensates(harness):
    h = harness
    ctx = h.context()
    h.clinicians(ctx, 2)
    h.change(ctx)
    h.clinicians(ctx, 1)
    preview = h.license.preview(ctx)
    h.clinicians(ctx, 1)  # count moves after the preview
    result = h.license.confirm(ctx, preview_id=preview["preview_id"],
                               expected_version=preview["license_version"])
    assert result["applied"] is False and result["code"] == "PREVIEW_STALE_SEAT_COUNT"
    assert [u["quantity"] for u in h.stripe.quantity_updates] == [4, 2]
    state = h.license.state(ctx)
    assert state["billed_clinical_seat_count"] == 2


def test_concurrent_confirms_apply_once(harness):
    h = harness
    ctx = h.context()
    h.clinicians(ctx, 2)
    h.change(ctx)
    h.clinicians(ctx, 1)
    preview = h.license.preview(ctx)
    outcomes = race(
        lambda: h.license.confirm(ctx, preview_id=preview["preview_id"],
                                  expected_version=preview["license_version"]),
        lambda: h.license.confirm(ctx, preview_id=preview["preview_id"],
                                  expected_version=preview["license_version"]))
    results = [o for o in outcomes if isinstance(o, dict)]
    assert len([r for r in results if r.get("applied")]) == 1
    assert h.license.state(ctx)["billed_clinical_seat_count"] == 3


def test_cross_org_preview_and_state_are_denied(harness):
    h = harness
    ctx = h.context()
    other = h.context()
    h.clinicians(ctx, 1)
    preview = h.license.preview(ctx)
    with pytest.raises(BillingError, match="PREVIEW_ACCESS_DENIED"):
        h.license.confirm(other, preview_id=preview["preview_id"], expected_version=None)


# -- Billing state never suspends the professional ------------------------------

def test_license_sync_updates_billing_without_touching_clinical(harness):
    h = harness
    ctx = h.context()
    h.clinicians(ctx, 2)
    h.change(ctx)
    subscription_id = h.license.state(ctx)["stripe_subscription_id"]
    synced = h.sql("SELECT psique_v2_license_sync(%s::jsonb)",
                   (json.dumps({"subscription_id": subscription_id,
                                "stripe_status": "past_due", "quantity": 2}),))[0][0]
    assert synced["synced"] is True and synced["license_status"] == "PAST_DUE"
    state = h.license.state(ctx)
    assert state["license_status"] == "PAST_DUE"
    assert state["active_clinical_seat_count"] == 2  # billing nunca suspende o clinico
    synced = h.sql("SELECT psique_v2_license_sync(%s::jsonb)",
                   (json.dumps({"subscription_id": subscription_id,
                                "stripe_status": "active", "quantity": 7}),))[0][0]
    assert "STRIPE_QUANTITY_DIVERGENT:7" in (synced["status_reason"] or "")
    unknown = h.sql("SELECT psique_v2_license_sync(%s::jsonb)",
                    (json.dumps({"subscription_id": "sub_SYNunknown", "stripe_status": "active"}),))[0][0]
    assert unknown["synced"] is False
