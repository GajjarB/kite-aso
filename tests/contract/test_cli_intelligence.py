import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.aso_platform.cli import main


class CliIntelligenceContractTests(unittest.TestCase):
    def test_keyword_score_outputs_estimate_contract(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main([
                "keywords",
                "score",
                "bmi calculator,loan calculator",
                "--app-text",
                "calculator finance tools",
                "--format",
                "json",
            ])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("request_context", payload)
        self.assertIn("scores", payload)
        self.assertIn("evidence", payload)
        self.assertIn("warnings", payload)
        self.assertIn("confidence", payload)
        estimate = payload["scores"][0]["volume_estimate"]
        self.assertTrue(estimate["is_estimate"])
        self.assertIn("method", estimate)

    def test_source_health_outputs_governance_contract(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["sources", "health", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("source_health", payload)
        self.assertIn("evidence", payload)
        self.assertIn("warnings", payload)
        self.assertTrue(any(row["source_id"] == "google_trends_public" for row in payload["source_health"]))

    def test_ios_inspect_json_contract_can_be_stubbed(self):
        output = io.StringIO()
        with patch("src.aso_platform.cli.IOSInspectionService") as service_cls:
            service_cls.return_value.inspect.return_value = {
                "request_context": {"identifier": "com.example.ios", "sources": ["apple_itunes_lookup_api"]},
                "ios_app": {"bundle_id": "com.example.ios", "title": "Stub iOS"},
                "evidence": [],
                "warnings": [],
                "confidence": {"label": "high", "score": 80, "rationale": "stub"},
            }
            with redirect_stdout(output):
                exit_code = main(["ios", "inspect", "com.example.ios", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        for key in ("request_context", "ios_app", "evidence", "warnings", "confidence"):
            self.assertIn(key, payload)

    def test_metadata_audit_json_contract_can_be_stubbed(self):
        output = io.StringIO()
        with patch("src.aso_platform.cli.MetadataAuditService") as service_cls:
            service_cls.return_value.audit.return_value = {
                "request_context": {"package_id": "com.example.app", "sources": ["google_play_public_store"]},
                "metadata_audit": {"title_score": 80, "recommendations": []},
                "evidence": [],
                "warnings": [],
                "confidence": {"label": "medium", "score": 70, "rationale": "stub"},
            }
            with redirect_stdout(output):
                exit_code = main(["audit", "metadata", "com.example.app", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("metadata_audit", payload)
        self.assertIn("confidence", payload)


if __name__ == "__main__":
    unittest.main()

