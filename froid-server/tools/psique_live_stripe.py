"""Etapa 3 da Fase 6: objetos Stripe LIVE do Psique V2, por decisao explicita.

--create-objects: cria os 6 Products/Prices de credito (one_time, BRL,
  unit_amount exato do catalogo) e o Price graduado da licenca na conta REAL,
  idempotente por lookup_key (existente e reutilizado, nunca duplicado).
--homolog: preview da primeira fatura da licenca nas 16 quantidades-fronteira
  contra a formula do backend; o customer de QA e apagado ao final.
--register: registra os mapeamentos imutaveis (livemode=true) no banco dito
  em voz alta por --confirm-database, via FROID_PSIQUE_OPERACAO_DATABASE_URL.
--coupon-demo: garante o cupom FROID-DEMO-100 (100%, forever) da clinica de
  demonstracao — a licenca da demo fatura R$ 0,00.

Exige FROID_PSIQUE_STRIPE_LIVE_SECRET_KEY; nunca imprime segredo; nao apaga
nem arquiva objetos (a unica remocao e o customer de QA da homologacao).
"""

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import psique_pricing
from psique_billing import BillingError, StripeTestClient
from psique_catalog_store import register_license_test_mapping, register_test_mapping
from tools.psique_license_stripe import LOOKUP_KEY as LICENSE_LOOKUP_KEY
from tools.psique_license_stripe import create_objects as create_license_objects
from tools.psique_license_stripe import find_price as find_license_price
from tools.psique_license_stripe import homolog as homolog_license

CUPOM_DEMO = "FROID-DEMO-100"


def lookup_key_de(product_code: str) -> str:
    # FROID_PRO_10 -> froid_psique_pro_10_v2_1 (mesma regra dos objetos TEST)
    return "froid_psique_" + product_code.removeprefix("FROID_").lower() + "_v2_1"


def achar_por_lookup(client, lookup_key):
    listing = client._request(
        "GET", "/v1/prices?lookup_keys[]=" + urllib.parse.quote(lookup_key))
    data = listing.get("data") or []
    return data[0] if data else None


def criar_creditos(client, config):
    """Um Product+Price one_time por oferta de credito; idempotente."""
    criados = {}
    for offer in sorted(config["offers"], key=lambda o: o.get("credits") or 0):
        if offer.get("billing_type") != "one_time":
            continue
        code = offer["product_code"]
        lookup_key = lookup_key_de(code)
        price = achar_por_lookup(client, lookup_key)
        if price is not None:
            criados[code] = (price, False)
            continue
        metadata = {"froid_product": "psique", "family": "psique_credits",
                    "product_code": code, "credits": str(offer["credits"]),
                    "pricing_version": config["version"],
                    "pricing_hash": psique_pricing.pricing_hash(config)}
        fields = [("name", "FROID Psique - " + offer["name"])]
        fields += [(f"metadata[{k}]", v) for k, v in metadata.items()]
        product = client._request("POST", "/v1/products", fields)
        fields = [("product", product["id"]), ("currency", config["currency"]),
                  ("unit_amount", str(offer["total_cents"])),
                  ("lookup_key", lookup_key)]
        fields += [(f"metadata[{k}]", v) for k, v in metadata.items()]
        criados[code] = (client._request("POST", "/v1/prices", fields), True)
    return criados


def garantir_cupom_demo(client):
    try:
        cupom = client._request("GET", "/v1/coupons/" + CUPOM_DEMO)
        return cupom, False
    except BillingError as erro:
        if "STRIPE_HTTP_404" not in erro.args[0]:
            raise
    cupom = client._request("POST", "/v1/coupons", [
        ("id", CUPOM_DEMO), ("percent_off", "100"), ("duration", "forever"),
        ("name", "FROID demonstracao - licenca cortesia")])
    return cupom, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-objects", action="store_true")
    parser.add_argument("--homolog", action="store_true")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--coupon-demo", action="store_true")
    parser.add_argument("--confirm-database", default="")
    parser.add_argument("--actor", default="")
    args = parser.parse_args()
    try:
        secret = os.environ.get("FROID_PSIQUE_STRIPE_LIVE_SECRET_KEY", "")
        if not secret:
            parser.error("FROID_PSIQUE_STRIPE_LIVE_SECRET_KEY is required")
        client = StripeTestClient(secret, live=True)
        account = client.account()["id"]
        config = psique_pricing.load_config()
        result = {"account": account, "live": True, "version": config["version"]}

        creditos = {}
        license_price = None
        if args.create_objects:
            creditos = criar_creditos(client, config)
            result["credit_prices"] = {code: {"price_id": price["id"], "created": created}
                                       for code, (price, created) in creditos.items()}
            license_price, created = create_license_objects(client, config)
            result["license_price_id"] = license_price["id"]
            result["license_price_created"] = created

        if license_price is None and (args.homolog or args.register):
            license_price = find_license_price(client)
        if (args.homolog or args.register) and license_price is None:
            raise ValueError("license_price_not_found_run_create_objects")

        if args.homolog:
            assert license_price is not None
            rows, failures = homolog_license(client, config, license_price["id"])
            result["homolog"] = [{"quantity": q, "expected_cents": e, "stripe_cents": g}
                                 for q, e, g in rows]
            result["homolog_failures"] = len(failures)
            # O customer de QA nasceu dentro de homolog_license; apagar o mais
            # recente customer de homologacao mantem a conta real limpa.
            clientes = client._request(
                "GET", "/v1/customers?limit=10")["data"]
            for cliente in clientes:
                if (cliente.get("description") or "").startswith("FROID Psique V2 QA homolog"):
                    client._request("DELETE", "/v1/customers/" + cliente["id"])
                    result.setdefault("homolog_customers_removed", 0)
                    result["homolog_customers_removed"] += 1
            if failures:
                raise ValueError(f"tiered_preview_divergent:{failures[:3]}")

        if args.coupon_demo:
            cupom, created = garantir_cupom_demo(client)
            result["coupon"] = {"id": cupom["id"], "percent_off": cupom.get("percent_off"),
                                "duration": cupom.get("duration"), "created": created}

        if args.register:
            if not args.confirm_database.strip() or not args.actor.strip():
                parser.error("--register requires --confirm-database and --actor")
            dsn = os.environ.get("FROID_PSIQUE_OPERACAO_DATABASE_URL", "")
            if not dsn:
                parser.error("FROID_PSIQUE_OPERACAO_DATABASE_URL is required")
            import psycopg
            with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conn:
                row = conn.execute("SELECT current_database()").fetchone()
                if row is None or row[0] != args.confirm_database:
                    raise ValueError("database_confirmation_mismatch")
                result["registered"] = 0
                for offer in config["offers"]:
                    if offer.get("billing_type") != "one_time":
                        continue
                    code = offer["product_code"]
                    lookup_key = lookup_key_de(code)
                    price = (creditos.get(code) or (achar_por_lookup(client, lookup_key),))[0]
                    if price is None:
                        raise ValueError(f"credit_price_not_found:{code}")
                    product = client._request(
                        "GET", "/v1/products/" + price["product"])
                    register_test_mapping(
                        conn, version=config["version"], product_code=code,
                        account_id=account, product=product, price=price,
                        actor=args.actor, lookup_key=lookup_key, live=True)
                    result["registered"] += 1
                assert license_price is not None
                detalhado = client._request(
                    "GET", f"/v1/prices/{license_price['id']}?expand[]=tiers")
                product = client._request(
                    "GET", "/v1/products/" + detalhado["product"])
                result["license_mapping_id"] = register_license_test_mapping(
                    conn, version=config["version"], account_id=account,
                    product=product, price=detalhado, actor=args.actor,
                    lookup_key=LICENSE_LOOKUP_KEY, live=True)
        print(json.dumps(result))
        return 0
    except Exception as exc:  # noqa: BLE001 -- fronteira de CLI sanitizada; nunca imprimir credencial
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__,
                          "detail": str(exc)[:200]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
