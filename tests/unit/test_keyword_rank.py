import tempfile
import unittest
from pathlib import Path

from src.aso_platform.services.keyword_rank import KeywordRankService, RankConfig
from src.aso_platform.storage import HistoryStore


class StubSearchProvider:
    source_id = "google_play_public_search"

    def search(self, query: str, n_hits: int = 20, lang: str = "en", country: str = "us") -> list[dict]:
        return [
            {
                "package_id": "com.first",
                "title": "First App",
                "developer": "First Dev",
                "score": 4.1,
                "installs": "100,000+",
            },
            {
                "package_id": "com.target",
                "title": "Target App",
                "developer": "Target Dev",
                "score": 4.7,
                "installs": "1,000,000+",
            },
        ]


class DisabledSearchProvider(StubSearchProvider):
    source_id = "google_trends_public"


class FailingSearchProvider(StubSearchProvider):
    def search(self, query: str, n_hits: int = 20, lang: str = "en", country: str = "us") -> list[dict]:
        raise RuntimeError("upstream search failed")


class KeywordRankTests(unittest.TestCase):
    def test_rank_finds_target_position_and_saves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = HistoryStore(Path(tmp) / "rank_history.jsonl")
            service = KeywordRankService(provider=StubSearchProvider(), history=history)

            report = service.rank(RankConfig(keyword="cleaner", target_package_id="com.target", save_history=True)).to_dict()

            self.assertEqual(report["target_position"], 2)
            self.assertEqual(report["confidence"]["label"], "high")
            self.assertEqual(len(history.read_all()), 1)

    def test_rank_returns_warning_when_target_missing(self):
        service = KeywordRankService(provider=StubSearchProvider())

        report = service.rank(RankConfig(keyword="cleaner", target_package_id="com.missing", save_history=False)).to_dict()

        self.assertIsNone(report["target_position"])
        self.assertTrue(any(item["code"] == "TARGET_NOT_IN_TOP_RESULTS" for item in report["warnings"]))

    def test_disabled_source_is_blocked(self):
        service = KeywordRankService(provider=DisabledSearchProvider())

        report = service.rank(RankConfig(keyword="cleaner", target_package_id="com.target", save_history=False)).to_dict()

        self.assertEqual(report["confidence"]["label"], "blocked")
        self.assertTrue(any(item["code"] == "SOURCE_DISABLED" for item in report["warnings"]))

    def test_provider_failure_returns_structured_warning(self):
        service = KeywordRankService(provider=FailingSearchProvider())

        report = service.rank(RankConfig(keyword="cleaner", target_package_id="com.target", save_history=False)).to_dict()

        self.assertEqual(report["confidence"]["label"], "low")
        self.assertTrue(any(item["code"] == "PROVIDER_FAILURE" for item in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
