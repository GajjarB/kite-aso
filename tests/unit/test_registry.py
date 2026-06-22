import unittest

from src.aso_platform.models import ComplianceStatus
from src.aso_platform.registry import DEFAULT_REGISTRY_PATH, RegistryError, ensure_source_approved, get_source, load_source_registry


class RegistryTests(unittest.TestCase):
    def test_registry_loads_expected_sources(self):
        registry = load_source_registry(DEFAULT_REGISTRY_PATH)
        self.assertIn("google_play_public_store", registry)
        self.assertIn("google_play_public_search", registry)
        self.assertIn("google_trends_public", registry)

    def test_approved_source_passes_policy_check(self):
        registry = load_source_registry(DEFAULT_REGISTRY_PATH)
        source = get_source("google_play_public_store", registry)
        ensure_source_approved(source)

    def test_review_required_source_is_blocked(self):
        registry = load_source_registry(DEFAULT_REGISTRY_PATH)
        source = get_source("google_trends_public", registry)
        self.assertEqual(source.compliance_status, ComplianceStatus.REVIEW_REQUIRED)
        with self.assertRaises(RegistryError):
            ensure_source_approved(source)


if __name__ == "__main__":
    unittest.main()
