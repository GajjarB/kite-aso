import tempfile
import unittest
from pathlib import Path

from src.aso_platform.services.workspace import WorkspaceService


class StubAppService:
    def inspect(self, package_id: str, lang: str = "en", country: str = "us"):
        class Result:
            def to_dict(self_inner):
                return {
                    "request_context": {"package_id": package_id, "lang": lang, "country": country},
                    "app": {"package_id": package_id, "title": "Stub App"},
                    "evidence": [],
                    "scores": [{"name": "store_quality_score", "value": 81}],
                    "insights": ["stub app insight"],
                    "warnings": [],
                    "confidence": {"label": "high", "score": 85, "rationale": "stub"},
                }

        return Result()


class StubKeywordService:
    def discover(self, seed_text: str = "", category: str = "", *, lang: str = "en", country: str = "us", limit: int = 40):
        class Result:
            def to_dict(self_inner):
                return {
                    "request_context": {"category": category, "seed_text": seed_text, "lang": lang, "country": country},
                    "input_review": {"seeds": ["scientific calculator"]},
                    "category": {"category": category or "tools", "matched": True},
                    "seed_sources": {"scientific calculator": "normalized_input"},
                    "keywords": [
                        {"keyword": "scientific calculator", "composite_score": 71, "priority": "HIGH"},
                        {"keyword": "bmi calculator", "composite_score": 66, "priority": "MEDIUM"},
                    ][:limit],
                    "evidence": [],
                    "warnings": [],
                    "confidence": {"label": "medium", "score": 70, "rationale": "stub"},
                }

        return Result()


class StubRankService:
    def rank(self, config):
        class Result:
            def to_dict(self_inner):
                return {
                    "request_context": {"keyword": config.keyword, "target_package_id": config.target_package_id, "lang": config.lang, "country": config.country},
                    "keyword": config.keyword,
                    "target_package_id": config.target_package_id,
                    "target_position": 2 if "scientific" in config.keyword else None,
                    "top_results": [],
                    "evidence": [],
                    "warnings": [],
                    "confidence": {"label": "high", "score": 80, "rationale": "stub"},
                }

        return Result()


class WorkspaceServiceTests(unittest.TestCase):
    def test_create_and_get_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WorkspaceService(workspace_dir=Path(tmp))
            created = service.create(
                "Calc Lab",
                "com.example.calc",
                category="tools",
                seed_text="scientific calculator",
                competitors=["com.comp.one", "com.comp.two"],
            )

            loaded = service.get("calc-lab")

            self.assertEqual(created.workspace_id, "calc-lab")
            self.assertEqual(loaded.target_package_id, "com.example.calc")
            self.assertEqual(loaded.competitors, ["com.comp.one", "com.comp.two"])

    def test_baseline_runs_app_keyword_and_rank_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = WorkspaceService(
                workspace_dir=Path(tmp),
                app_service=StubAppService(),
                keyword_service=StubKeywordService(),
                rank_service=StubRankService(),
            )
            service.create(
                "Calc Lab",
                "com.example.calc",
                category="tools",
                seed_text="scientific calculator",
            )

            report = service.baseline("calc-lab", keyword_limit=5, top_keywords=2, rank_limit=10).to_dict()

            self.assertEqual(report["workspace"]["workspace_id"], "calc-lab")
            self.assertEqual(report["summary"]["keyword_count"], 2)
            self.assertEqual(report["summary"]["rank_checks_run"], 2)
            self.assertEqual(report["summary"]["best_rank"], 2)


if __name__ == "__main__":
    unittest.main()
