import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.aso_platform.cli import main
from src.aso_platform.models import AppDetails


class StubProvider:
    source_id = "google_play_public_store"

    def fetch_app(self, package_id: str, lang: str = "en", country: str = "us") -> AppDetails:
        return AppDetails.from_mapping(
            {
                "package_id": package_id,
                "title": "CLI Stub App",
                "summary": "Summary",
                "description": "Description",
                "score": 4.8,
                "ratings": 5000,
                "reviews": 400,
                "installs": "500,000+",
                "min_installs": 500000,
                "category": "Productivity",
                "category_id": "PRODUCTIVITY",
                "developer": "CLI Dev",
                "developer_email": "cli@example.com",
                "price": 0,
                "free": True,
                "content_rating": "Everyone",
                "updated": "2026-05-15",
                "version": "2.0.0",
                "android_version": "9 and up",
                "contains_ads": False,
                "released": "2024-01-01",
                "histogram": {"5": 10},
                "_fetched_at": "2026-05-16T00:00:00+00:00",
                "_from_cache": False,
            }
        )


class CliContractTests(unittest.TestCase):
    def test_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with patch("src.aso_platform.cli.AppInspectionService") as service_cls:
            service_cls.return_value.inspect.return_value.to_dict.return_value = {
                "request_context": {
                    "package_id": "com.example.cli",
                    "lang": "en",
                    "country": "us",
                    "requested_at": "2026-05-16T00:00:00+00:00",
                    "sources": ["google_play_public_store"]
                },
                "app": StubProvider().fetch_app("com.example.cli").__dict__,
                "evidence": [
                    {
                        "source_id": "google_play_public_store",
                        "display_name": "Google Play Public Store",
                        "source_type": "public_store",
                        "scope": "single_app_inspection",
                        "fetched_at": "2026-05-16T00:00:00+00:00",
                        "from_cache": False,
                        "locale": "en",
                        "country": "us"
                    }
                ],
                "scores": [
                    {
                        "name": "store_quality_score",
                        "value": 82,
                        "scale": "0-100",
                        "formula_version": "1.0.0",
                        "explanation": "stub"
                    }
                ],
                "insights": ["stub insight"],
                "warnings": [],
                "confidence": {
                    "label": "high",
                    "score": 90,
                    "rationale": "stub"
                }
            }
            with redirect_stdout(output):
                exit_code = main(["inspect", "com.example.cli", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        for key in ("request_context", "app", "evidence", "scores", "insights", "warnings", "confidence"):
            self.assertIn(key, payload)

    def test_rank_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with patch("src.aso_platform.cli.KeywordRankService") as service_cls:
            service_cls.return_value.rank.return_value.to_dict.return_value = {
                "request_context": {
                    "keyword": "cleaner",
                    "target_package_id": "com.example.cli",
                    "lang": "en",
                    "country": "us",
                    "limit": 20,
                    "requested_at": "2026-05-16T00:00:00+00:00",
                    "sources": ["google_play_public_search"]
                },
                "keyword": "cleaner",
                "target_package_id": "com.example.cli",
                "target_position": 3,
                "top_results": [],
                "evidence": [],
                "warnings": [],
                "confidence": {
                    "label": "high",
                    "score": 80,
                    "rationale": "stub"
                }
            }
            with redirect_stdout(output):
                exit_code = main(["rank", "cleaner", "com.example.cli", "--format", "json", "--no-history"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        for key in ("request_context", "keyword", "target_package_id", "target_position", "top_results", "evidence", "warnings", "confidence"):
            self.assertIn(key, payload)

    def test_capabilities_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["capabilities", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("summary", payload)
        self.assertIn("capabilities", payload)
        self.assertTrue(payload["capabilities"])
        self.assertIn("legal_ready", payload["capabilities"][0])

    def test_discover_keywords_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main([
                "keywords",
                "--category",
                "tools",
                "--seed",
                "bmi calculator",
                "--limit",
                "10",
                "--format",
                "json",
            ])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        for key in ("request_context", "input_review", "category", "seed_sources", "keywords", "evidence", "warnings", "confidence"):
            self.assertIn(key, payload)
        self.assertTrue(payload["keywords"])
        self.assertEqual(payload["category"]["category"], "tools")

    def test_discover_keywords_alias_still_works(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main([
                "discover-keywords",
                "--category",
                "tools",
                "--limit",
                "3",
                "--format",
                "json",
            ])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["request_context"]["category"], "tools")
        self.assertEqual(len(payload["keywords"]), 3)

    def test_categories_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["categories", "--category", "tools", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("categories", payload)
        self.assertIn("selected", payload)
        self.assertEqual(payload["selected"]["category"], "tools")
        self.assertTrue(payload["selected"]["seeds"])

    def test_doctor_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["doctor", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("status", payload)
        self.assertIn("checks", payload)
        self.assertIn("policy", payload)
        self.assertTrue(payload["checks"])

    def test_workspace_init_and_show_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with patch("src.aso_platform.cli.WorkspaceService") as service_cls:
            service_cls.return_value.create.return_value.to_dict.return_value = {
                "workspace_id": "calc-lab",
                "name": "Calc Lab",
                "target_package_id": "com.example.cli",
                "category": "tools",
                "seed_text": "scientific calculator",
                "lang": "en",
                "country": "us",
                "competitors": ["com.comp.one"],
                "notes": "",
                "created_at": "2026-05-16T00:00:00+00:00",
                "updated_at": "2026-05-16T00:00:00+00:00",
            }
            with redirect_stdout(output):
                exit_code = main([
                    "workspace",
                    "init",
                    "Calc Lab",
                    "com.example.cli",
                    "--category",
                    "tools",
                    "--format",
                    "json",
                ])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["workspace_id"], "calc-lab")
        self.assertEqual(payload["target_package_id"], "com.example.cli")

    def test_workspace_baseline_cli_json_contract_contains_required_sections(self):
        output = io.StringIO()
        with patch("src.aso_platform.cli.WorkspaceService") as service_cls:
            service_cls.return_value.baseline.return_value.to_dict.return_value = {
                "workspace": {
                    "workspace_id": "calc-lab",
                    "name": "Calc Lab",
                    "target_package_id": "com.example.cli",
                    "category": "tools",
                    "seed_text": "scientific calculator",
                    "lang": "en",
                    "country": "us",
                    "competitors": [],
                    "notes": "",
                    "created_at": "2026-05-16T00:00:00+00:00",
                    "updated_at": "2026-05-16T00:00:00+00:00",
                },
                "generated_at": "2026-05-16T00:00:00+00:00",
                "app_report": {"app": {"package_id": "com.example.cli"}},
                "keyword_report": {"keywords": [{"keyword": "scientific calculator", "composite_score": 71, "priority": "HIGH"}]},
                "rank_checks": [],
                "warnings": [],
                "summary": {
                    "target_package_id": "com.example.cli",
                    "country": "us",
                    "lang": "en",
                    "keyword_count": 1,
                    "rank_checks_run": 0,
                    "rank_hits": 0,
                    "best_rank": None,
                    "app_confidence": "high",
                    "keyword_confidence": "medium",
                },
            }
            with redirect_stdout(output):
                exit_code = main(["workspace", "baseline", "calc-lab", "--format", "json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("workspace", payload)
        self.assertIn("summary", payload)
        self.assertIn("keyword_report", payload)
        self.assertIn("app_report", payload)


if __name__ == "__main__":
    unittest.main()
