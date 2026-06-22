import unittest
from unittest.mock import MagicMock

from src.aso_platform.models import KeywordDiscoveryReport
from src.aso_platform.services.keyword_discovery import KeywordDiscoveryService
from src.aso_platform.providers.play_store import PlayStoreSearchProvider

class TestKeywordDiscoveryService(unittest.TestCase):
    def setUp(self):
        self.mock_search_provider = MagicMock(spec=PlayStoreSearchProvider)
        # Mocking the search method to return some basic results
        self.mock_search_provider.search.return_value = [
            {
                "title": "Calculator Plus",
                "summary": "A great calculator",
                "category": "Tools",
            },
            {
                "title": "Scientific Calc",
                "summary": "For science",
                "category": "Tools",
            }
        ]
        self.service = KeywordDiscoveryService(search_provider=self.mock_search_provider)

    def test_discover_with_seed_and_category_returns_report_and_uses_search(self):
        report = self.service.discover(seed_text="calculator", category="tools", limit=10)

        self.assertIsInstance(report, KeywordDiscoveryReport)
        self.assertEqual(report.request_context["seed_text"], "calculator")
        self.assertEqual(report.request_context["category"], "tools")
        self.assertTrue(len(report.keywords) > 0)
        self.assertTrue(any(e.source_type == "public_search" for e in report.evidence))

        # Verify that the search provider was called
        self.mock_search_provider.search.assert_called()

    def test_discover_with_no_input_returns_warnings(self):
        report = self.service.discover(seed_text="", category="")

        self.assertIsInstance(report, KeywordDiscoveryReport)
        self.assertEqual(len(report.keywords), 0)
        self.assertTrue(any(w.code == "no_keyword_seeds" for w in report.warnings))
        self.assertEqual(report.confidence.label, "low")

    def test_discover_with_search_provider_exception_returns_warning(self):
        self.mock_search_provider.search.side_effect = Exception("API error")

        report = self.service.discover(seed_text="calculator", limit=10)

        self.assertIsInstance(report, KeywordDiscoveryReport)
        self.assertTrue(any("API error" in w.message for w in report.warnings))
        self.assertTrue(len(report.keywords) > 0) # Should still return candidates from seeds

    def test_discover_with_only_category_works(self):
        report = self.service.discover(category="tools", limit=10)

        self.assertIsInstance(report, KeywordDiscoveryReport)
        self.assertEqual(report.request_context["category"], "tools")
        self.assertTrue(len(report.keywords) > 0)
        self.assertTrue(any(e.source_type == "local_taxonomy" for e in report.evidence))

if __name__ == "__main__":
    unittest.main()
