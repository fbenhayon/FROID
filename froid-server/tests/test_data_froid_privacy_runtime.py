import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None


@unittest.skipUnless(DUCKDB_AVAILABLE, "duckdb is installed in the backend image")
class DataFroidPrivacyRuntimeTests(unittest.TestCase):
    def _create_database(self, path: Path, *, literal_text: str = "") -> None:
        import duckdb

        connection = duckdb.connect(str(path))
        connection.execute(
            """CREATE TABLE anonymous_sessions(
                session_hash VARCHAR, pii_excluded BOOLEAN,
                raw_audio_retained BOOLEAN, literal_transcript_retained BOOLEAN,
                ingestion_basis VARCHAR
            )"""
        )
        connection.execute(
            """CREATE TABLE anonymous_session_cuts(
                cut_summary_anon VARCHAR, patient_summary_anon VARCHAR,
                professional_summary_anon VARCHAR, relevant_dissonances VARCHAR
            )"""
        )
        connection.execute(
            """CREATE TABLE privacy_ingestion_audit(
                session_hash VARCHAR, accepted BOOLEAN, reason VARCHAR,
                checked_at VARCHAR, pipeline_version VARCHAR
            )"""
        )
        session_hash = "a" * 64
        connection.execute(
            "INSERT INTO anonymous_sessions VALUES (?, true, false, false, 'post_anonymization')",
            [session_hash],
        )
        connection.execute(
            "INSERT INTO anonymous_session_cuts VALUES (?, '', '', '')",
            [literal_text],
        )
        connection.execute(
            "INSERT INTO privacy_ingestion_audit VALUES (?, true, 'approved', 'now', 'v3')",
            [session_hash],
        )
        connection.close()

    def _run_audit(self, path: Path) -> tuple[int, dict]:
        from tools import audit_data_froid_privacy

        output = io.StringIO()
        with patch.object(sys, "argv", ["audit", "--database", str(path)]):
            with contextlib.redirect_stdout(output):
                result = audit_data_froid_privacy.main()
        return result, json.loads(output.getvalue())

    def test_safe_post_anonymization_database_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "safe.duckdb"
            self._create_database(path)
            exit_code, result = self._run_audit(path)
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["checks"]["literal_text_absent"])
            self.assertTrue(result["checks"]["safe_session_flags"])

    def test_literal_text_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.duckdb"
            self._create_database(path, literal_text="conteudo literal indevido")
            exit_code, result = self._run_audit(path)
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["checks"]["literal_text_absent"])


if __name__ == "__main__":
    unittest.main()
