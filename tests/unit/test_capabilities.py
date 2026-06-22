import unittest

from src.aso_platform.capabilities import audit_capabilities, load_capability_catalog


class CapabilityCatalogTests(unittest.TestCase):
    def test_catalog_loads_missing_feature_inventory(self):
        catalog = load_capability_catalog()
        ids = {item.id for item in catalog}

        self.assertIn("keyword_volume_estimation", ids)
        self.assertIn("review_intelligence", ids)
        self.assertIn("ios_app_store_support", ids)
        self.assertIn("source_health_monitor", ids)

    def test_audit_marks_legal_ready_and_blocked_capabilities(self):
        audit = audit_capabilities()
        rows = {item["id"]: item for item in audit["capabilities"]}

        self.assertTrue(rows["keyword_rank_tracking"]["legal_ready"])
        self.assertTrue(rows["ios_app_store_support"]["legal_ready"])
        self.assertEqual(rows["download_estimates"]["status"], "blocked")
        self.assertFalse(rows["download_estimates"]["legal_ready"])
        self.assertTrue(rows["download_estimates"]["source_legal_ready"])
        self.assertGreaterEqual(audit["summary"]["legal_ready"], 1)


if __name__ == "__main__":
    unittest.main()
