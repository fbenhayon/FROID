"""Multimoeda do FROID Psique (decisao do dono, 06 e 07/10/2026).

O mesmo numero em BRL, USD e EUR, sem conversao; a moeda vem do idioma da
pagina (pt brl, en usd, es/fr eur); NR-1 adiado. Tres frentes:

(1) a migration 051 e byte a byte o que o transformador declara a partir da
    046, e esta na lista opt-in (o arranque nunca a aplica sozinho);
(2) contra PostgreSQL real, a 051 aplica POR CIMA de um banco que ja tem a
    tabela BRL ativa, mapeamentos e compras — e reaplica como no-op; os tres
    CHECK de moeda passam a aceitar brl/usd/eur e nada mais;
(3) a compra em ingles cobra em USD na tabela "2.1-usd" com o Price USD, o
    webhook em reais para essa compra e recusado para revisao, sem idioma a
    compra continua em reais, idioma fora da lista e recusado com nome; a
    licenca cotada e pre-visualizada em ingles assina com o Price USD e grava
    currency='usd', e o banco recusa um Price de outra tabela na confirmacao.

Fixtures sinteticas; nenhuma chamada de rede.
"""

import json
import os
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psique_pricing
from froid_schema import PSIQUE_V2_VERSIONS
from psique_billing import BillingError
from psique_catalog_store import (
    install_draft,
    license_expected_tiers,
    register_license_test_mapping,
    register_test_mapping,
)
from test_psique_phase2b import AUTHORIZED, EXPECTED_TOTALS, QA_ACCOUNT
from test_psique_phase2b import Harness as HarnessCompra
from test_psique_phase2c import LOOKUP as LICENSE_LOOKUP
from test_psique_phase2c import Harness as HarnessLicenca
from tools.migrate_schema import apply
from tools.psique_multimoeda_sync import MOEDAS, RAIZ, VERSAO, gerar

# Objetos sinteticos por moeda: ids distintos dos BRL para provar que a
# resolucao de mapping respeita a TABELA da moeda, nao apenas o produto.
USD_OBJECTS = {"FROID_PRO_10": ("prod_SINTusd10", "price_SINTusd10", "froid_psique_pro_10_v2_1_usd")}
EUR_OBJECTS = {"FROID_PRO_25": ("prod_SINTeur25", "price_SINTeur25", "froid_psique_pro_25_v2_1_eur")}
LICENSE_BRL = ("prod_SYNTHETIClicense", "price_SYNTHETIClicense", LICENSE_LOOKUP)
LICENSE_USD = ("prod_SINTlicusd", "price_SINTlicusd", LICENSE_LOOKUP + "_usd")


# -- Guardas estaticas --------------------------------------------------------

def test_migration_051_e_byte_a_byte_o_que_o_transformador_declara():
    arquivo = (RAIZ / "migrations" / (VERSAO + ".sql")).read_text(encoding="utf-8")
    assert arquivo == gerar(), (
        "051 divergiu do transformador: regenere com tools/psique_multimoeda_sync.py "
        "ou atualize as transformacoes declaradas junto da origem 046")


def test_051_e_opt_in_e_a_lista_de_moedas_tem_uma_fonte():
    assert VERSAO in PSIQUE_V2_VERSIONS  # o arranque nao aplica V2 sozinho
    assert MOEDAS == psique_pricing.CURRENCIES
    sql = (RAIZ / "migrations" / (VERSAO + ".sql")).read_text(encoding="utf-8")
    assert sql.count("CHECK (currency IN ('brl','usd','eur'))") == 3
    assert "'brl',payload->>'account_id'" not in sql  # o literal saiu da licenca
    assert "moeda,payload->>'account_id'" in sql


# -- PostgreSQL --------------------------------------------------------------

def _registrar_creditos(conn, config, objetos, *, actor):
    for code, (product_id, price_id, lookup_key) in objetos.items():
        offer = psique_pricing.offer_for(config, code)
        metadata = {"froid_product": "psique", "family": "psique_credits",
                    "product_code": code, "credits": str(offer["credits"]),
                    "pricing_version": config["version"],
                    "pricing_hash": psique_pricing.pricing_hash(config)}
        register_test_mapping(
            conn, version=config["version"], product_code=code, account_id=QA_ACCOUNT,
            product={"id": product_id, "livemode": False, "active": True, "metadata": metadata},
            price={"id": price_id, "livemode": False, "active": True, "product": product_id,
                   "currency": config["currency"], "unit_amount": offer["total_cents"],
                   "type": "one_time", "recurring": None, "billing_scheme": "per_unit",
                   "lookup_key": lookup_key, "metadata": metadata},
            actor=actor, lookup_key=lookup_key)


def _registrar_licenca(conn, config, objeto, *, actor):
    product_id, price_id, lookup_key = objeto
    metadata = {"froid_product": "psique", "family": "psique_license",
                "product_code": "FROID_ORG_LICENSE",
                "pricing_version": config["version"],
                "pricing_hash": psique_pricing.pricing_hash(config)}
    register_license_test_mapping(
        conn, version=config["version"], account_id=QA_ACCOUNT,
        product={"id": product_id, "livemode": False, "active": True, "metadata": metadata},
        price={"id": price_id, "livemode": False, "active": True, "product": product_id,
               "currency": config["currency"],
               "recurring": {"interval": "month", "interval_count": 1},
               "billing_scheme": "tiered", "tiers_mode": "graduated",
               "lookup_key": lookup_key, "metadata": metadata,
               "tiers": [{"up_to": t["up_to"], "flat_amount": t["flat_amount"],
                          "unit_amount": t["unit_amount"]}
                         for t in license_expected_tiers(config)]},
        actor=actor, lookup_key=lookup_key)


def _ativar(conn, version):
    conn.execute("UPDATE psique_pricing_tables SET status='active',valid_from=now() "
                 "WHERE code='FROID_PSIQUE_V2' AND version=%s", (version,))


@pytest.fixture(scope="module")
def banco():
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
                # O estado de producao de hoje: ate a 050, tabela BRL instalada
                # e ativa, mapeamentos BRL dos seis pacotes e da licenca.
                apply(conn, ROOT / "migrations", "050_psique_session_charge_fix", name)
                brl = psique_pricing.load_config()
                install_draft(conn, brl, actor="multimoeda-tests")
                _ativar(conn, brl["version"])
                _registrar_creditos(conn, brl, AUTHORIZED, actor="multimoeda-tests")
                _registrar_licenca(conn, brl, LICENSE_BRL, actor="multimoeda-tests")
                # A 051 por cima do estado real, e reaplicada como no-op.
                assert apply(conn, ROOT / "migrations", VERSAO, name) == [VERSAO]
                assert apply(conn, ROOT / "migrations", VERSAO, name) == []
                # As tabelas USD e EUR nascem DERIVADAS da BRL e ativas, cada
                # uma com os proprios objetos Stripe (sinteticos aqui).
                for moeda, objetos in (("usd", USD_OBJECTS), ("eur", EUR_OBJECTS)):
                    derivada = psique_pricing.load_config(currency=moeda)
                    install_draft(conn, derivada, actor="multimoeda-tests")
                    _ativar(conn, derivada["version"])
                    _registrar_creditos(conn, derivada, objetos, actor="multimoeda-tests")
                _registrar_licenca(conn, psique_pricing.load_config(currency="usd"),
                                   LICENSE_USD, actor="multimoeda-tests")
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


def _sql(dsn, query, params=()):
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall() if cursor.description else []


def test_051_amplia_os_tres_check_e_nao_deixa_o_literal_brl(banco):
    linhas = _sql(banco, """SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid)
                            FROM pg_constraint WHERE contype='c' AND conrelid IN
                            ('psique_pricing_tables'::regclass,'psique_purchases'::regclass,
                             'psique_organization_licenses'::regclass)
                            AND pg_get_constraintdef(oid) ILIKE '%%currency%%'""")
    por_tabela = {}
    for tabela, nome, definicao in linhas:
        assert "currency = 'brl'" not in definicao, (tabela, nome, definicao)
        if nome.endswith("_moeda"):
            por_tabela[tabela] = definicao
    assert set(por_tabela) == {"psique_pricing_tables", "psique_purchases",
                               "psique_organization_licenses"}
    for definicao in por_tabela.values():
        assert "'brl'" in definicao and "'usd'" in definicao and "'eur'" in definicao
    ativas = _sql(banco, "SELECT version,currency FROM psique_pricing_tables "
                         "WHERE status='active' ORDER BY version")
    assert ativas == [("2.1", "brl"), ("2.1-eur", "eur"), ("2.1-usd", "usd")]


def test_compra_em_ingles_cobra_em_dolar_na_tabela_usd(banco):
    h = HarnessCompra(banco)
    ctx = h.enrolled()
    result = h.billing.checkout(ctx, {"product_code": "FROID_PRO_10", "language": "en"},
                                idempotency_key=uuid.uuid4().hex)
    assert result["status"] == "CHECKOUT_CREATED"
    product_id, price_id, _ = USD_OBJECTS["FROID_PRO_10"]
    assert h.stripe.created[-1]["price_id"] == price_id  # o Price USD, nao o BRL
    row = h.sql("SELECT currency,pricing_version,total_cents,credits FROM psique_purchases "
                "WHERE id=%s", (result["purchase_id"],))[0]
    assert row == ("usd", "2.1-usd", EXPECTED_TOTALS["FROID_PRO_10"], 10)  # mesmo numero
    session_id = h.session_of(result)
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10", currency="usd",
          line_items={"data": [{"quantity": 1, "price": {"id": price_id, "product": product_id}}]})
    status, body = h.event("checkout.session.completed", {"id": session_id, "livemode": False})
    assert status == 200 and body["applied"] is True and body["credits"] == 10
    assert h.balance(ctx) == (10, 0)


def test_sessao_em_reais_para_compra_em_dolar_vai_para_revisao(banco):
    h = HarnessCompra(banco)
    ctx = h.enrolled()
    result = h.billing.checkout(ctx, {"product_code": "FROID_PRO_10", "language": "en"},
                                idempotency_key=uuid.uuid4().hex)
    session_id = h.session_of(result)
    product_id, price_id, _ = USD_OBJECTS["FROID_PRO_10"]
    # Mesmo Price e valor, moeda errada: a verdade da sessao diverge da compra.
    h.pay(session_id, result["purchase_id"], "FROID_PRO_10", currency="brl",
          line_items={"data": [{"quantity": 1, "price": {"id": price_id, "product": product_id}}]})
    status, body = h.event("checkout.session.completed", {"id": session_id, "livemode": False})
    assert status == 200 and body["applied"] is False and body["code"] == "WRONG_CURRENCY"
    assert h.balance(ctx) == (0, 0) and h.grants(ctx) == []
    assert h.billing.purchase_state(ctx, str(result["purchase_id"]))["status"] == "REVIEW_REQUIRED"


def test_espanhol_e_frances_compram_em_euro(banco):
    h = HarnessCompra(banco)
    for idioma in ("es", "fr"):
        ctx = h.enrolled()
        result = h.billing.checkout(ctx, {"product_code": "FROID_PRO_25", "language": idioma},
                                    idempotency_key=uuid.uuid4().hex)
        assert h.stripe.created[-1]["price_id"] == EUR_OBJECTS["FROID_PRO_25"][1]
        row = h.sql("SELECT currency,pricing_version,total_cents FROM psique_purchases WHERE id=%s",
                    (result["purchase_id"],))[0]
        assert row == ("eur", "2.1-eur", EXPECTED_TOTALS["FROID_PRO_25"]), idioma


def test_sem_idioma_continua_em_reais_e_o_resto_e_recusado_com_nome(banco):
    h = HarnessCompra(banco)
    ctx = h.enrolled()
    result = h.checkout(ctx, "FROID_PRO_10")
    assert h.stripe.created[-1]["price_id"] == AUTHORIZED["FROID_PRO_10"][1]
    row = h.sql("SELECT currency,pricing_version FROM psique_purchases WHERE id=%s",
                (result["purchase_id"],))[0]
    assert row == ("brl", "2.1")
    with pytest.raises(BillingError, match="CHECKOUT_LANGUAGE_UNSUPPORTED"):
        h.billing.checkout(ctx, {"product_code": "FROID_PRO_10", "language": "de"},
                           idempotency_key=uuid.uuid4().hex)
    with pytest.raises(BillingError, match="CHECKOUT_LANGUAGE_UNSUPPORTED"):
        h.billing.checkout(ctx, {"product_code": "FROID_PRO_10", "language": None},
                           idempotency_key=uuid.uuid4().hex)
    # Moeda, valor ou Price continuam vindo so do servidor: campo a mais e recusa.
    for body in ({"product_code": "FROID_PRO_10", "currency": "usd"},
                 {"product_code": "FROID_PRO_10", "language": "en", "amount": 1}):
        with pytest.raises(BillingError, match="CHECKOUT_BODY_MUST_BE_PRODUCT_CODE_ONLY"):
            h.billing.checkout(ctx, body, idempotency_key=uuid.uuid4().hex)
    assert h.sql("SELECT count(*) FROM psique_purchases WHERE organization_id=%s",
                 (ctx.organization_id,))[0][0] == 1


def test_pacote_sem_objeto_stripe_na_moeda_e_recusado_com_nome(banco):
    # So FROID_PRO_10 tem Price USD neste banco: PRO_25 em ingles nao pode
    # cair no Price BRL em silencio.
    h = HarnessCompra(banco)
    ctx = h.enrolled()
    with pytest.raises(BillingError, match="STRIPE_TEST_MAPPING_REQUIRED"):
        h.billing.checkout(ctx, {"product_code": "FROID_PRO_25", "language": "en"},
                           idempotency_key=uuid.uuid4().hex)


def test_cotacao_da_licenca_por_idioma_mesmo_numero_outra_moeda(banco):
    h = HarnessLicenca(banco)
    for idioma, moeda in psique_pricing.LANGUAGE_CURRENCY.items():
        cotacao = h.license.quote(10, idioma)
        assert cotacao["currency"] == moeda and cotacao["monthly_cents"] == 135100, idioma
        assert cotacao["pricing_version"] == psique_pricing.version_for("2.1", moeda)
    assert h.license.quote(10) == h.license.quote(10, "pt")
    with pytest.raises(BillingError, match="LANGUAGE_UNSUPPORTED"):
        h.license.quote(10, "de")
    with pytest.raises(BillingError, match="LANGUAGE_UNSUPPORTED"):
        h.license.preview(h.context(), "de")


def test_licenca_pre_visualizada_em_ingles_assina_com_o_price_usd(banco):
    h = HarnessLicenca(banco)
    ctx = h.context()
    h.clinicians(ctx, 3)
    preview = h.license.preview(ctx, "en")
    assert preview["quote"]["currency"] == "usd"
    assert preview["quote"]["pricing_version"] == "2.1-usd"
    result = h.license.confirm(ctx, preview_id=preview["preview_id"],
                               expected_version=preview["license_version"])
    assert result["applied"] is True
    row = h.sql("SELECT currency,pricing_version,stripe_price_id,billed_clinical_seat_count "
                "FROM psique_organization_licenses WHERE organization_id=%s",
                (ctx.organization_id,))[0]
    assert row == ("usd", "2.1-usd", LICENSE_USD[1], 3)
    assinatura = list(h.stripe.subscriptions.values())[-1]
    assert assinatura["items"]["data"][0]["price"]["id"] == LICENSE_USD[1]


def test_licenca_em_portugues_continua_em_reais(banco):
    h = HarnessLicenca(banco)
    ctx = h.context()
    h.clinicians(ctx, 2)
    preview = h.license.preview(ctx)
    result = h.license.confirm(ctx, preview_id=preview["preview_id"],
                               expected_version=preview["license_version"])
    assert result["applied"] is True
    row = h.sql("SELECT currency,pricing_version,stripe_price_id FROM psique_organization_licenses "
                "WHERE organization_id=%s", (ctx.organization_id,))[0]
    assert row == ("brl", "2.1", LICENSE_BRL[1])


def test_banco_recusa_price_de_outra_tabela_na_confirmacao(banco):
    # Defesa em profundidade: mesmo que um chamador resolvesse o Price BRL
    # para um preview em USD, psique_v2_seat_confirm (051) recusa.
    h = HarnessLicenca(banco)
    ctx = h.context()
    h.clinicians(ctx, 2)
    preview = h.license.preview(ctx, "en")
    args = {"preview_id": preview["preview_id"], "expected_version": preview["license_version"],
            "expected_livemode": False,
            "stripe": {"account_id": QA_ACCOUNT, "livemode": False,
                       "customer_id": "cus_SYNoutra", "subscription_id": "sub_SYNoutra",
                       "item_id": "si_SYNoutra", "price_id": LICENSE_BRL[1], "quantity": 2}}
    with pytest.raises(BillingError, match="LICENSE_PRICE_NOT_FROM_PREVIEW_CATALOG"):
        h.license._call("SELECT psique_v2_seat_confirm(%s,%s,%s,%s::jsonb)",  # noqa: SLF001
                        (ctx.organization_id, ctx.membership_id, ctx.user_id,
                         json.dumps(args)), ctx)
    assert h.sql("SELECT count(*) FROM psique_organization_licenses WHERE organization_id=%s",
                 (ctx.organization_id,))[0][0] == 0
