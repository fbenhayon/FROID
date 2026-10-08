"""Commercial acceptance examples from Psique V2.1; no clinical data."""

import copy
import unittest
from datetime import datetime, timedelta, timezone

from psique_pricing import (
    PricingError,
    canonical_json,
    load_config,
    offer_for,
    organization_quote,
    pricing_hash,
    purchase_snapshot,
    require_effective,
    unit_price_display,
    validate,
)


class PsiquePricingTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_all_six_prepaid_packages_have_exact_credits_and_totals(self):
        expected = {10: 19900, 25: 46900, 50: 91500, 100: 169000,
                    200: 318000, 500: 745000}
        for credits, cents in expected.items():
            with self.subTest(credits=credits):
                snapshot = purchase_snapshot(self.config, f"FROID_PRO_{credits}")
                self.assertEqual(snapshot["credits"], credits)
                self.assertEqual(snapshot["total_cents"], cents)
                self.assertEqual(snapshot["currency"], "brl")
                self.assertEqual(snapshot["pricing_hash"], pricing_hash(self.config))
        self.assertEqual(sum(o["active"] for o in self.config["offers"]), 6)
        self.assertFalse(any(o["public"] for o in self.config["offers"]))

    def test_unit_display_never_drives_the_purchase_total(self):
        self.assertEqual(unit_price_display(self.config, "FROID_PRO_25"), "18.76")
        self.assertEqual(purchase_snapshot(self.config, "FROID_PRO_25")["total_cents"], 46900)

    def test_every_required_organization_boundary(self):
        # Values in reais from section 54 plus the explicit marginal tier edges.
        expected = {0: 0, 1: 499, 2: 499, 3: 618, 5: 856, 6: 955, 10: 1351,
                    11: 1440, 20: 2241, 25: 2686, 26: 2765, 30: 3081,
                    50: 4661, 51: 4730, 100: 8111, 101: 8170, 200: 14011}
        for count, reais in expected.items():
            with self.subTest(count=count):
                quote = organization_quote(self.config, count)
                self.assertEqual(quote["monthly_cents"], reais * 100)
                self.assertFalse(quote["enterprise_required"])
        quote = organization_quote(self.config, 201)
        self.assertTrue(quote["enterprise_required"])
        self.assertIsNone(quote["monthly_cents"])

    def test_invalid_seat_counts_do_not_become_a_quote(self):
        for count in (-1, 1.5, True, None, "2"):
            with self.subTest(count=count), self.assertRaises(PricingError):
                organization_quote(self.config, count)

    def test_hash_is_independent_of_keys_and_offer_order(self):
        reordered = dict(reversed(list(self.config.items())))
        reordered["offers"] = list(reversed(self.config["offers"]))
        self.assertEqual(pricing_hash(reordered), pricing_hash(self.config))
        self.assertEqual(canonical_json(reordered), canonical_json(self.config))

    def test_commercial_changes_change_the_hash(self):
        for field, value in (("total_cents", 20000), ("credits", 11), ("active", False)):
            changed = copy.deepcopy(self.config)
            changed["offers"][0][field] = value
            self.assertNotEqual(pricing_hash(changed), pricing_hash(self.config))

    def test_float_boolean_and_non_brl_amounts_are_rejected(self):
        for value in (19900.0, True, -1, 0):
            changed = copy.deepcopy(self.config)
            changed["offers"][0]["total_cents"] = value
            with self.subTest(value=value), self.assertRaises(PricingError):
                validate(changed)
        self.config["currency"] = "usd"
        with self.assertRaises(PricingError):
            validate(self.config)

    def test_tier_gap_overlap_and_duplicate_product_are_rejected(self):
        for start in (5, 7):
            changed = copy.deepcopy(self.config)
            changed["organization_license"]["tiers"][1]["from"] = start
            with self.assertRaises(PricingError):
                validate(changed)
        self.config["offers"].append(copy.deepcopy(self.config["offers"][0]))
        with self.assertRaises(PricingError):
            validate(self.config)

    def test_inactive_and_unknown_products_cannot_be_purchased(self):
        for code in ("FROID_FLEX", "FROID_ORG_LICENSE", "FROID_NR1", "PRO999"):
            with self.subTest(code=code), self.assertRaises(PricingError):
                purchase_snapshot(self.config, code)
        for offer in self.config["offers"]:
            if offer["product_code"] == "FROID_ORG_LICENSE":
                offer["active"] = True
        self.assertIsNone(offer_for(self.config, "FROID_ORG_LICENSE")["credits"])
        with self.assertRaisesRegex(PricingError, "not_a_prepaid_offer"):
            purchase_snapshot(self.config, "FROID_ORG_LICENSE")

    def test_validity_is_explicit_and_end_is_exclusive(self):
        start = datetime(2026, 9, 29, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        require_effective("active", start, end, start)
        for status, at in (("draft", start), ("inactive", start), ("active", end),
                           ("active", start - timedelta(seconds=1))):
            with self.subTest(status=status, at=at), self.assertRaises(PricingError):
                require_effective(status, start, end, at)
        with self.assertRaisesRegex(PricingError, "timezone_required"):
            require_effective("active", start, end, start.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()


class PsiqueMultimoedaTests(unittest.TestCase):
    """Multimoeda (decisao do dono, 06 e 07/10/2026): mesmo numero em BRL, USD
    e EUR, sem conversao; moeda pelo idioma; tabelas USD/EUR derivadas da BRL
    por codigo, com a versao sufixada. NR-1 fica fora (adiado)."""

    def setUp(self):
        self.base = load_config()

    def test_tabelas_derivadas_tem_os_mesmos_numeros_e_outra_moeda(self):
        from psique_pricing import (CURRENCIES, config_for_currency, public_catalog,
                                    version_for)
        numeros = [(o["product_code"], o["credits"], o["total_cents"]) for o in self.base["offers"]]
        hashes = set()
        for moeda in CURRENCIES:
            with self.subTest(moeda=moeda):
                derivada = load_config(currency=moeda)
                self.assertEqual(derivada, config_for_currency(self.base, moeda))
                self.assertEqual(derivada["currency"], moeda)
                self.assertEqual(derivada["version"], version_for(self.base["version"], moeda))
                self.assertEqual([(o["product_code"], o["credits"], o["total_cents"])
                                  for o in derivada["offers"]], numeros)
                self.assertEqual(derivada["organization_license"], self.base["organization_license"])
                self.assertEqual(public_catalog(derivada)["currency"], moeda)
                self.assertEqual(organization_quote(derivada, 10)["monthly_cents"],
                                 organization_quote(self.base, 10)["monthly_cents"])
                self.assertEqual(purchase_snapshot(derivada, "FROID_PRO_10")["currency"], moeda)
                hashes.add(pricing_hash(derivada))
        self.assertEqual(len(hashes), 3)  # moeda diferente, tabela diferente
        self.assertEqual(load_config(currency="brl"), self.base)
        self.assertEqual(version_for("2.1", "brl"), "2.1")
        self.assertEqual(version_for("2.1", "eur"), "2.1-eur")

    def test_idioma_e_lista_fechada(self):
        from psique_pricing import LANGUAGE_CURRENCY, currency_for_language
        self.assertEqual({idioma: currency_for_language(idioma) for idioma in ("pt", "en", "es", "fr")},
                         {"pt": "brl", "en": "usd", "es": "eur", "fr": "eur"})
        self.assertEqual(dict(LANGUAGE_CURRENCY), {"pt": "brl", "en": "usd", "es": "eur", "fr": "eur"})
        self.assertEqual(currency_for_language(" EN "), "usd")
        for ruim in ("de", "", None, 1, "pt-BR", "brl"):
            with self.subTest(idioma=ruim), self.assertRaises(PricingError):
                currency_for_language(ruim)

    def test_versao_e_moeda_andam_juntas(self):
        from psique_pricing import config_for_currency, version_for
        with self.assertRaisesRegex(PricingError, "brl_version_must_not_carry_currency_suffix"):
            validate({**self.base, "version": "2.1-usd"})
        with self.assertRaisesRegex(PricingError, "version_must_carry_currency_suffix"):
            validate({**self.base, "currency": "usd"})
        with self.assertRaisesRegex(PricingError, "invalid_product_or_currency"):
            validate({**self.base, "currency": "cny", "version": "2.1-cny"})
        with self.assertRaisesRegex(PricingError, "source_config_must_be_brl"):
            config_for_currency(load_config(currency="usd"), "eur")
        with self.assertRaisesRegex(PricingError, "unsupported_currency"):
            version_for("2.1", "cny")
        with self.assertRaisesRegex(PricingError, "unsupported_currency"):
            load_config(currency="cny")
