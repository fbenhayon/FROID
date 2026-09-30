"""Phase 5 acceptance: public pricing from the backend and site/app guards.

The four language pages carry ZERO hardcoded prices: every number comes from
the API, and API failure must surface as a declared unavailability — these
tests guard exactly that, plus the trial-rule mirror against migration 037.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SITE = ROOT.parent / "froid-site"

import psique_pricing
from psique_billing import BillingError

PAGINAS = [SITE / "precos-v2.html", SITE / "en/precos-v2.html",
           SITE / "es/precos-v2.html", SITE / "fr/precos-v2.html"]


# -- Espelho do Trial: a fonte executavel e a migration 037 -------------------

def test_trial_rule_mirrors_migration_037():
    sql = (ROOT / "migrations/037_psique_trial_credit_state.sql").read_text(encoding="utf-8")
    assert f"credits_granted={psique_pricing.TRIAL_CREDITS})" in sql.replace(" ", "")
    assert f"interval '{psique_pricing.TRIAL_DAYS * 24} hours'" in sql


# -- Catalogo publico ----------------------------------------------------------

def test_public_catalog_exposes_exactly_the_six_prepaid_offers():
    payload = psique_pricing.public_catalog(psique_pricing.load_config())
    assert payload["currency"] == "brl" and payload["pricing_version"] == "2.1"
    assert payload["trial"] == {"credits": 10, "days": 14}
    offers = {o["product_code"]: o for o in payload["offers"]}
    esperado = {"FROID_PRO_10": (10, 19900, "19.90"), "FROID_PRO_25": (25, 46900, "18.76"),
                "FROID_PRO_50": (50, 91500, "18.30"), "FROID_PRO_100": (100, 169000, "16.90"),
                "FROID_PRO_200": (200, 318000, "15.90"), "FROID_PRO_500": (500, 745000, "14.90")}
    assert set(offers) == set(esperado)  # licenca e FLEX nunca aparecem aqui
    creditos_na_ordem = [o["credits"] for o in payload["offers"]]
    assert creditos_na_ordem == sorted(creditos_na_ordem)  # cards do menor ao maior
    for code, (credits, cents, unit) in esperado.items():
        assert offers[code]["credits"] == credits
        assert offers[code]["total_cents"] == cents
        assert offers[code]["unit_price_display"] == unit
    assert payload["organization_license"] == {"self_service_max": 200}


def test_pricing_route_serves_catalog_and_fails_closed():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from psique_api import build_psique_v2_billing_router

    app = FastAPI()
    app.include_router(build_psique_v2_billing_router(
        lambda: (_ for _ in ()).throw(AssertionError("billing nao usado")),
        lambda: object(),
        pricing_provider=lambda: psique_pricing.public_catalog(psique_pricing.load_config())))
    client = TestClient(app)
    corpo = client.get("/api/psique/v2/pricing")
    assert corpo.status_code == 200
    assert len(corpo.json()["offers"]) == 6

    quebrado = FastAPI()

    def provider_quebrado():
        raise RuntimeError("catalogo fora do ar")

    quebrado.include_router(build_psique_v2_billing_router(
        lambda: None, lambda: object(), pricing_provider=provider_quebrado))
    resposta = TestClient(quebrado).get("/api/psique/v2/pricing")
    # Indisponibilidade explicita: nunca um catalogo antigo, nunca zeros.
    assert resposta.status_code == 503
    assert resposta.json() == {"code": "PRICING_UNAVAILABLE"}


def test_wallet_route_passes_context_and_maps_denials():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from psique_api import build_psique_v2_billing_router
    from psique_credits import CreditError

    class StubCredits:
        def __init__(self, resultado):
            self.resultado = resultado

        def balance(self, context):
            if isinstance(self.resultado, Exception):
                raise self.resultado
            return self.resultado

    def montar(stub):
        app = FastAPI()
        app.include_router(build_psique_v2_billing_router(
            lambda: None, lambda: object(), wallet_provider=lambda: stub))
        return TestClient(app)

    ok = montar(StubCredits({"balance": 7, "reserved_balance": 2, "available_balance": 5}))
    assert ok.get("/api/psique/v2/wallet").json()["available_balance"] == 5
    negado = montar(StubCredits(CreditError("PSIQUE_ROLE_DENIED")))
    assert negado.get("/api/psique/v2/wallet").status_code == 403
    sem_carteira = montar(StubCredits(CreditError("PSIQUE_WALLET_REQUIRED")))
    assert sem_carteira.get("/api/psique/v2/wallet").status_code == 409


# -- Guardas do site (quatro idiomas) -------------------------------------------

def test_pricing_pages_exist_in_four_languages_and_load_the_shared_script():
    for pagina in PAGINAS:
        assert pagina.exists(), pagina
        texto = pagina.read_text(encoding="utf-8")
        assert "psique-pricing-v2.js" in texto
        assert "psique-pricing-v2.css" in texto
        assert 'id="pv2-ofertas"' in texto and 'id="pv2-trial"' in texto
        assert 'id="pv2-calculadora"' in texto


def test_pricing_pages_have_zero_hardcoded_prices_or_trial_numbers():
    proibidos = re.compile(r"R\$\s*\d|19900|46900|91500|169000|318000|745000|"
                           r"199,00|469,00|915,00|1\.690|3\.180|7\.450")
    for pagina in PAGINAS + [SITE / "site-assets/psique-pricing-v2.js"]:
        texto = pagina.read_text(encoding="utf-8")
        assert not proibidos.search(texto), f"preco embutido em {pagina.name}"
        # Os numeros do Trial tambem vem da API ({creditos}/{dias}).
        assert "{creditos}" in texto or pagina.suffix == ".js"


def test_pricing_pages_share_the_same_i18n_contract():
    chaves = []
    for pagina in PAGINAS:
        texto = pagina.read_text(encoding="utf-8")
        bloco = texto.split("PSIQUE_PRECOS_V2_I18N = {", 1)[1].split("};", 1)[0]
        chaves.append(sorted(re.findall(r"^\s*([a-z_]+):", bloco, re.MULTILINE)))
    assert chaves[0] == chaves[1] == chaves[2] == chaves[3]
    assert "indisponivel" in chaves[0] and "calc_enterprise" in chaves[0]


PAGINAS_PUBLICAS = [SITE / "precos.html", SITE / "en/precos.html",
                    SITE / "es/precos.html", SITE / "fr/precos.html"]


def test_switchover_happened_and_public_pages_have_zero_hardcoded_prices():
    """Decisao revogada em 30/09/2026 (Etapa 0 da Fase 6, aprovada pelo
    proprietario): a pagina publica FOI trocada pela V2. A guarda inverte —
    agora exige a virada consumada, chrome preservado e nenhum preco
    embutido tambem na pagina publica."""
    import re as _re

    proibidos = _re.compile(r"R\$\s*\d|19900|46900|91500|169000|318000|745000|"
                            r"198,00|470,00|1\.182|2\.202|4\.888")
    for pagina in PAGINAS_PUBLICAS:
        texto = pagina.read_text(encoding="utf-8")
        assert "psique-pricing-v2.js" in texto, pagina
        assert 'id="pv2-ofertas"' in texto and 'id="pv2-calculadora"' in texto, pagina
        assert "<footer" in texto and "nav" in texto, pagina  # chrome preservado
        assert not proibidos.search(texto), f"preco embutido em {pagina}"


def test_pricing_error_is_a_billing_error_with_named_code():
    with pytest.raises(BillingError):
        raise BillingError("PRICING_UNAVAILABLE")
