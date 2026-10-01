"""Fase 6: o modo LIVE existe por decisao explicita, nunca por acidente.

Tres frentes: (1) a migration 046 e byte a byte o que o transformador declara
a partir das 039/040; (2) o cliente exige que chave e intencao confiram;
(3) o percurso de compra inteiro roda em modo live contra PostgreSQL real,
com cs_live_ e livemode=true de ponta a ponta — e cada modo recusa alto o
trafego do outro. Fixtures sinteticas; nenhuma chamada de rede.
"""

import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from test_psique_phase2b import (  # noqa: F401 (fixture database reutilizada)
    QA_ACCOUNT,
    FakeStripe,
    Harness,
    database,
)

import psique_pricing
from psique_billing import BillingError, PsiqueBilling, StripeTestClient
from psique_catalog_store import register_test_mapping
from tools.psique_live_mode_sync import RAIZ, VERSAO, gerar

# Objetos LIVE sinteticos: ids distintos dos TEST para provar que a resolucao
# de mapeamento respeita o modo, nao apenas a conta.
LIVE_OBJECTS = {
    "FROID_PRO_10": ("prod_LIVEsint10", "price_LIVEsint10", "froid_psique_pro_10_v2_1"),
}


def test_migration_046_e_byte_a_byte_o_que_o_transformador_declara():
    arquivo = (RAIZ / "migrations" / (VERSAO + ".sql")).read_text(encoding="utf-8")
    assert arquivo == gerar(), (
        "046 divergiu do transformador: regenere com tools/psique_live_mode_sync.py "
        "ou atualize as transformacoes declaradas junto da origem 039/040")


def test_cliente_exige_que_chave_e_intencao_confiram():
    with pytest.raises(BillingError, match="STRIPE_LIVE_KEY_REQUIRED"):
        StripeTestClient("sk_test_SINTETICA", live=True)
    with pytest.raises(BillingError, match="STRIPE_TEST_KEY_REQUIRED"):
        StripeTestClient("sk_live_SINTETICA")
    vivo = StripeTestClient("rk_live_SINTETICA", live=True)
    teste = StripeTestClient("rk_test_SINTETICA")
    assert vivo.live is True and teste.live is False


class FakeStripeLive(FakeStripe):
    """Sessoes cs_live_ com livemode=true; o resto identico ao fake TEST."""

    live = True

    def create_checkout_session(self, **kwargs):
        session = super().create_checkout_session(**kwargs)
        vivo_id = "cs_live_" + session["id"][len("cs_test_"):]
        vivo = dict(session, id=vivo_id, livemode=True)
        del self.sessions[session["id"]]
        self.sessions[vivo_id] = vivo
        return dict(vivo)


@pytest.fixture(scope="module")
def harness_live(database):  # noqa: F811
    h = Harness(database)
    config = psique_pricing.load_config()
    with h.pg.connect(database, autocommit=True) as conn:
        for code, (product_id, price_id, lookup_key) in LIVE_OBJECTS.items():
            offer = psique_pricing.offer_for(config, code)
            metadata = {"froid_product": "psique", "family": "psique_credits",
                        "product_code": code, "credits": str(offer["credits"]),
                        "pricing_version": config["version"],
                        "pricing_hash": psique_pricing.pricing_hash(config)}
            register_test_mapping(
                conn, version=config["version"], product_code=code,
                account_id=QA_ACCOUNT,
                product={"id": product_id, "livemode": True, "active": True,
                         "metadata": metadata},
                price={"id": price_id, "livemode": True, "active": True,
                       "product": product_id, "currency": "brl",
                       "unit_amount": offer["total_cents"], "type": "one_time",
                       "recurring": None, "billing_scheme": "per_unit",
                       "lookup_key": lookup_key, "metadata": metadata},
                actor="phase6-tests", lookup_key=lookup_key, live=True)
    h.stripe = FakeStripeLive()
    h.billing = PsiqueBilling(
        h.billing._connect, stripe_client=h.stripe,
        webhook_secret=h.webhook_secret, account_id=QA_ACCOUNT,
        pricing_version=config["version"],
        success_url="https://example.invalid/ok", cancel_url="https://example.invalid/no")
    return h


def test_objeto_do_modo_errado_nao_registra(harness_live, database):  # noqa: F811
    import psycopg

    from psique_catalog_store import PricingError

    config = psique_pricing.load_config()
    with psycopg.connect(database, autocommit=True) as conn,             pytest.raises(PricingError, match="stripe_object_mode_mismatch"):
        register_test_mapping(
            conn, version=config["version"], product_code="FROID_PRO_10",
            account_id=QA_ACCOUNT, actor="phase6-tests",
            product={"id": "prod_x", "livemode": False},
            price={"id": "price_x", "livemode": False}, live=True)


def test_compra_live_de_ponta_a_ponta_credita_e_grava_o_modo(harness_live):
    h = harness_live
    ctx = h.enrolled()
    resultado = h.checkout(ctx, "FROID_PRO_10")
    session_id = h.session_of(resultado)
    assert session_id.startswith("cs_live_")
    gravado = h.sql("SELECT livemode, stripe_account_id FROM psique_purchases WHERE id=%s",
                    (resultado["purchase_id"],))[0]
    assert gravado == (True, QA_ACCOUNT)

    produto, preco, _ = LIVE_OBJECTS["FROID_PRO_10"]
    total = h.sql("SELECT total_cents FROM psique_purchases WHERE id=%s",
                  (resultado["purchase_id"],))[0][0]
    sessao = h.stripe.sessions[session_id]
    sessao.update({"payment_status": "paid", "amount_total": total, "currency": "brl",
                   "payment_intent": "pi_" + uuid.uuid4().hex[:20],
                   "client_reference_id": str(resultado["purchase_id"]),
                   "metadata": {"purchase_id": str(resultado["purchase_id"])},
                   "line_items": {"data": [{"quantity": 1,
                                            "price": {"id": preco, "product": produto}}]}})
    payload = json.dumps({"id": "evt_" + uuid.uuid4().hex,
                          "type": "checkout.session.completed", "livemode": True,
                          "data": {"object": dict(sessao)}}).encode()
    status, body = h.billing.webhook(payload, h.sign(payload))
    assert status == 200 and body.get("received") is True
    assert h.balance(ctx) == (10, 0)
    evento = h.sql("SELECT livemode, processing_status FROM psique_stripe_events "
                   "WHERE checkout_session_id=%s", (session_id,))[0]
    assert evento == (True, "credited")


def test_endpoint_live_recusa_alto_o_trafego_de_teste(harness_live):
    h = harness_live
    payload = json.dumps({"id": "evt_" + uuid.uuid4().hex,
                          "type": "checkout.session.completed", "livemode": False,
                          "data": {"object": {"id": "cs_test_x", "livemode": False}}}).encode()
    status, body = h.billing.webhook(payload, h.sign(payload))
    assert status == 400 and body["code"] == "TEST_EVENT_REFUSED"

    # Evento que se declara live mas carrega sessao cs_test_: payload invalido.
    payload = json.dumps({"id": "evt_" + uuid.uuid4().hex,
                          "type": "checkout.session.completed", "livemode": True,
                          "data": {"object": {"id": "cs_test_x", "livemode": True}}}).encode()
    status, body = h.billing.webhook(payload, h.sign(payload))
    assert status == 400 and body["code"] == "EVENT_PAYLOAD_INVALID"


def test_checkout_live_recusa_sessao_que_o_stripe_devolve_em_teste(harness_live):
    h = harness_live

    class FakeModoTrocado(FakeStripeLive):
        def create_checkout_session(self, **kwargs):
            session = super().create_checkout_session(**kwargs)
            self.sessions[session["id"]]["livemode"] = False
            return dict(self.sessions[session["id"]])

    original = h.stripe
    h.billing._stripe = FakeModoTrocado()
    try:
        with pytest.raises(BillingError, match="TEST_SESSION_REFUSED"):
            h.checkout(h.enrolled(), "FROID_PRO_10")
    finally:
        h.billing._stripe = original


def test_compra_de_teste_continua_em_cs_test_no_mesmo_banco(harness_live, database):  # noqa: F811
    h = Harness(database)
    ctx = h.enrolled()
    resultado = h.checkout(ctx, "FROID_PRO_10")
    assert h.session_of(resultado).startswith("cs_test_")
    assert h.sql("SELECT livemode FROM psique_purchases WHERE id=%s",
                 (resultado["purchase_id"],))[0] == (False,)
