import unittest
from unittest.mock import patch

from src.aso_platform.models import AppDetails
from src.aso_platform.services.app_inspector import AppInspectionService


class StubProvider:
    source_id = "google_play_public_store"

    def __init__(self, from_cache=False):
        self.from_cache = from_cache

    def fetch_app(self, package_id: str, lang: str = "en", country: str = "us") -> AppDetails:
        return AppDetails.from_mapping(
            {
                "package_id": package_id,
                "title": "Stub App",
                "summary": "Short summary",
                "description": "Long description",
                "score": 4.6,
                "ratings": 12000,
                "reviews": 800,
                "installs": "1,000,000+",
                "min_installs": 1000000,
                "category": "Tools",
                "category_id": "TOOLS",
                "developer": "Stub Dev",
                "developer_email": "stub@example.com",
                "price": 0,
                "free": True,
                "content_rating": "Everyone",
                "updated": "2026-05-15",
                "version": "1.0.0",
                "android_version": "8.0 and up",
                "contains_ads": False,
                "released": "2024-01-01",
                "histogram": {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5},
                "_fetched_at": "2026-05-16T00:00:00+00:00",
                "_from_cache": self.from_cache,
            }
        )


class DisabledProvider(StubProvider):
    source_id = "google_trends_public"


class FailingProvider(StubProvider):
    def fetch_app(self, package_id: str, lang: str = "en", country: str = "us") -> AppDetails:
        raise RuntimeError("upstream fetch failed")


class NoHistogramProvider(StubProvider):
    def fetch_app(self, package_id: str, lang: str = "en", country: str = "us") -> AppDetails:
        from dataclasses import replace
        app = super().fetch_app(package_id, lang, country)
        return replace(app, histogram={})


class LowScoreProvider(StubProvider):
    def fetch_app(self, package_id: str, lang: str = "en", country: str = "us") -> AppDetails:
        from dataclasses import replace
        app = super().fetch_app(package_id, lang, country)
        return replace(app, score=3.2)


class NoReviewsProvider(StubProvider):
    def fetch_app(self, package_id: str, lang: str = "en", country: str = "us") -> AppDetails:
        from dataclasses import replace
        app = super().fetch_app(package_id, lang, country)
        return replace(app, reviews=0, ratings=0)


class AppInspectionTests(unittest.TestCase):
    def test_inspection_returns_expected_contract(self):
        service = AppInspectionService(provider=StubProvider())
        report = service.inspect("com.example.app").to_dict()

        self.assertEqual(report["request_context"]["package_id"], "com.example.app")
        self.assertEqual(report["app"]["title"], "Stub App")
        self.assertTrue(report["evidence"])
        self.assertTrue(report["scores"])
        self.assertEqual(report["confidence"]["label"], "high")

    def test_cache_hit_produces_warning(self):
        service = AppInspectionService(provider=StubProvider(from_cache=True))
        report = service.inspect("com.example.app").to_dict()
        self.assertTrue(any(item["code"] == "CACHE_HIT" for item in report["warnings"]))

    def test_disabled_source_is_blocked(self):
        service = AppInspectionService(provider=DisabledProvider())
        report = service.inspect("com.example.app").to_dict()
        self.assertEqual(report["confidence"]["label"], "blocked")
        self.assertTrue(any(item["code"] == "SOURCE_DISABLED" for item in report["warnings"]))

    def test_provider_failure_returns_structured_warning(self):
        service = AppInspectionService(provider=FailingProvider())
        report = service.inspect("com.example.app").to_dict()
        self.assertEqual(report["confidence"]["label"], "low")
        self.assertTrue(any(item["code"] == "PROVIDER_FAILURE" for item in report["warnings"]))

    def test_no_histogram_produces_warning(self):
        service = AppInspectionService(provider=NoHistogramProvider())
        report = service.inspect("com.example.app").to_dict()
        self.assertTrue(any(item["code"] == "PARTIAL_DATA" for item in report["warnings"]))

    def test_low_score_produces_weak_rating_insight(self):
        service = AppInspectionService(provider=LowScoreProvider())
        report = service.inspect("com.example.app").to_dict()
        self.assertTrue(any("Public store rating is weak" in insight for insight in report["insights"]))

    def test_no_reviews_lowers_confidence(self):
        service = AppInspectionService(provider=NoReviewsProvider())
        report = service.inspect("com.example.app").to_dict()
        # Stub has score 85, no warnings = 85. No reviews drops it by 20 to 65. label = "medium"
        self.assertEqual(report["confidence"]["label"], "medium")

    @patch("src.aso_platform.services.app_inspector.AppInspectionService")
    def test_inspect_app_convenience_function(self, MockService):
        from src.aso_platform.services.app_inspector import inspect_app
        mock_instance = MockService.return_value
        mock_instance.inspect.return_value.to_dict.return_value = {"dummy": "report"}

        result = inspect_app("com.example.test")

        self.assertEqual(result, {"dummy": "report"})
        mock_instance.inspect.assert_called_once_with("com.example.test", lang="en", country="us")


if __name__ == "__main__":
    unittest.main()
