import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from language_validation import (  # noqa: E402
    character_error_rate,
    critical_term_recall,
    evaluate_records,
    percentile,
    word_error_rate,
)


class LanguageValidationMetricTests(unittest.TestCase):
    def test_word_and_character_error_rate(self):
        self.assertEqual(word_error_rate("patient feels well", "patient feels well"), 0.0)
        self.assertAlmostEqual(word_error_rate("patient feels well", "patient well"), 1 / 3)
        self.assertEqual(character_error_rate("FROID", "FROID"), 0.0)

    def test_critical_terms_are_counted_only_when_expected(self):
        matched, expected = critical_term_recall(
            "The FROID IPM value changed",
            "The FROID value changed",
            ["FROID", "IPM", "MFCC"],
        )
        self.assertEqual((matched, expected), (1, 2))

    def test_percentile_interpolates(self):
        self.assertEqual(percentile([100, 200, 300], 0.5), 200)
        self.assertEqual(percentile([], 0.95), None)

    def test_batch_report_separates_locales_and_subgroups(self):
        report = evaluate_records(
            [
                {
                    "locale": "en-US",
                    "reference": "FROID records the session",
                    "hypothesis": "FROID records the session",
                    "critical_terms": ["FROID"],
                    "latency_ms": 100,
                    "status": "ok",
                    "subgroups": {"device": "desktop"},
                },
                {
                    "locale": "en",
                    "reference": "FROID records the session",
                    "hypothesis": "records session",
                    "critical_terms": ["FROID"],
                    "latency_ms": 300,
                    "status": "truncated",
                    "subgroups": {"device": "mobile"},
                },
                {
                    "locale": "fr-FR",
                    "reference": "FROID enregistre la séance",
                    "hypothesis": "FROID enregistre la séance",
                    "critical_terms": ["FROID"],
                    "latency_ms": 150,
                    "status": "ok",
                    "subgroups": {"device": "desktop"},
                },
            ]
        )
        self.assertEqual(report["records"], 3)
        self.assertEqual(report["locales"]["en-US"]["records"], 2)
        self.assertEqual(report["locales"]["en-US"]["critical_term_recall"], 0.5)
        self.assertEqual(report["locales"]["en-US"]["truncated_rate"], 0.5)
        self.assertEqual(report["locales"]["en-US"]["latency_ms_p50"], 200)
        self.assertGreater(report["locales"]["en-US"]["subgroup_wer_absolute_gap"], 0)


if __name__ == "__main__":
    unittest.main()
