"""Espelhos de numero: os precos copiados na documentacao Psique V2.

Regra da casa (2.7): numero tem UMA fonte; onde a copia e inevitavel, um teste
compara todas as copias contra a fonte. A fonte aqui e o catalogo 2.1 via
psique_pricing; os espelhos sao as tabelas estruturadas dos documentos. Se um
valor mudar no catalogo e ficar publicado antigo num doc, este teste quebra.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
DOCS = SERVER_DIR.parent / "docs"

import psique_pricing


class ChecklistLicensePointsMirrorTests(unittest.TestCase):
    def test_price_points_in_checklist_match_the_formula(self):
        text = (DOCS / "psique-v2-checklist-execucao.md").read_text(encoding="utf-8")
        pairs = re.findall(r"- \[.\] (\d+(?:/\d+)?)=([\d.]+)\b", text)
        self.assertGreaterEqual(len(pairs), 9, "pontos de preco sumiram do checklist")
        config = psique_pricing.load_config()
        for counts, shown in pairs:
            expected_cents = int(shown.replace(".", "")) * 100
            for count in counts.split("/"):
                with self.subTest(clinicos=count):
                    quote = psique_pricing.organization_quote(config, int(count))
                    self.assertEqual(quote["monthly_cents"], expected_cents)
                    self.assertFalse(quote["enterprise_required"])


class StripeDocProTableMirrorTests(unittest.TestCase):
    def test_pro_table_amounts_match_the_catalog(self):
        text = (DOCS / "psique-stripe-v2.md").read_text(encoding="utf-8")
        rows = re.findall(
            r"\| (FROID_PRO_\d+) \| prod_[A-Za-z0-9]+ \| price_[A-Za-z0-9]+ \| (\d+) \|", text)
        self.assertEqual(len(rows), 6, "a tabela PRO do doc mudou de forma")
        config = psique_pricing.load_config()
        for code, cents in rows:
            with self.subTest(code=code):
                offer = psique_pricing.offer_for(config, code)
                self.assertEqual(offer["total_cents"], int(cents))
                self.assertEqual(offer["credits"], int(code.rsplit("_", 1)[1]))


if __name__ == "__main__":
    unittest.main()
