import unittest
from datetime import UTC, datetime, timedelta

from src.aso_platform.services.intelligence import RankHistoryService

class StubDataStore:
    def __init__(self, records=None):
        self.records = records or []

    def read_events(self, name: str):
        if name == "rank_history":
            return self.records
        return []

class TestRankHistoryService(unittest.TestCase):
    def test_history_empty(self):
        store = StubDataStore([])
        service = RankHistoryService(store=store)

        result = service.history(keyword="test", package_id="com.test")

        self.assertEqual(len(result["history"]), 0)
        self.assertEqual(result["summary"]["checks"], 0)
        self.assertEqual(result["summary"]["hits"], 0)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["warnings"][0]["code"], "NO_HISTORY")
        self.assertEqual(result["confidence"]["label"], "low")

    def test_history_with_data(self):
        now = datetime.now(UTC)
        t1 = (now - timedelta(days=2)).isoformat()
        t2 = (now - timedelta(days=1)).isoformat()
        t3 = now.isoformat()

        records = [
            {"recorded_at": t1, "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 5, "request_context": {"country": "us", "lang": "en"}}},
            {"recorded_at": t2, "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 2, "request_context": {"country": "us", "lang": "en"}}},
            {"recorded_at": t3, "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 4, "request_context": {"country": "us", "lang": "en"}}},
        ]

        store = StubDataStore(records)
        service = RankHistoryService(store=store)

        result = service.history(keyword="test", package_id="com.test")

        self.assertEqual(len(result["history"]), 3)
        self.assertEqual(result["summary"]["checks"], 3)
        self.assertEqual(result["summary"]["hits"], 3)
        self.assertEqual(result["summary"]["best_position"], 2)
        self.assertEqual(result["summary"]["worst_position"], 5)
        self.assertEqual(result["summary"]["first_seen"], t1)
        self.assertEqual(result["summary"]["last_seen"], t3)

        # Volatility: mean(abs(2-5), abs(4-2)) = mean(3, 2) = 2.5
        self.assertEqual(result["summary"]["volatility"], 2.5)

        self.assertEqual(len(result["warnings"]), 0)
        self.assertEqual(result["confidence"]["label"], "high")

    def test_history_filtering(self):
        records = [
            {"recorded_at": "2023-01-01", "payload": {"keyword": "test1", "target_package_id": "com.test1", "target_position": 1}},
            {"recorded_at": "2023-01-02", "payload": {"keyword": "test1", "target_package_id": "com.test2", "target_position": 2}},
            {"recorded_at": "2023-01-03", "payload": {"keyword": "test2", "target_package_id": "com.test1", "target_position": 3}},
        ]

        store = StubDataStore(records)
        service = RankHistoryService(store=store)

        # Filter by keyword
        res_kw = service.history(keyword="test1")
        self.assertEqual(len(res_kw["history"]), 2)

        # Filter by package
        res_pkg = service.history(package_id="com.test1")
        self.assertEqual(len(res_pkg["history"]), 2)

        # Filter by both
        res_both = service.history(keyword="test1", package_id="com.test1")
        self.assertEqual(len(res_both["history"]), 1)
        self.assertEqual(res_both["history"][0]["position"], 1)

    def test_delta_insufficient_history(self):
        records = [
            {"recorded_at": "2023-01-01", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 5}},
        ]

        store = StubDataStore(records)
        service = RankHistoryService(store=store)

        result = service.delta(keyword="test", package_id="com.test")

        self.assertEqual(result["delta"]["movement"], "new")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["warnings"][0]["code"], "INSUFFICIENT_HISTORY")

    def test_delta_movements(self):
        # up
        records_up = [
            {"recorded_at": "2023-01-01", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 5}},
            {"recorded_at": "2023-01-02", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 2}},
        ]
        res_up = RankHistoryService(store=StubDataStore(records_up)).delta("test", "com.test")
        self.assertEqual(res_up["delta"]["movement"], "up")
        self.assertEqual(res_up["delta"]["delta"], 3)  # 5 - 2 = +3

        # down
        records_down = [
            {"recorded_at": "2023-01-01", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 2}},
            {"recorded_at": "2023-01-02", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 5}},
        ]
        res_down = RankHistoryService(store=StubDataStore(records_down)).delta("test", "com.test")
        self.assertEqual(res_down["delta"]["movement"], "down")
        self.assertEqual(res_down["delta"]["delta"], -3)  # 2 - 5 = -3

        # unchanged
        records_same = [
            {"recorded_at": "2023-01-01", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 3}},
            {"recorded_at": "2023-01-02", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 3}},
        ]
        res_same = RankHistoryService(store=StubDataStore(records_same)).delta("test", "com.test")
        self.assertEqual(res_same["delta"]["movement"], "unchanged")
        self.assertEqual(res_same["delta"]["delta"], 0)

    def test_delta_new_movement(self):
        # previous is None, current has position
        records = [
            {"recorded_at": "2023-01-01", "payload": {"keyword": "test", "target_package_id": "com.test", "target_position": 5}},
        ]
        res = RankHistoryService(store=StubDataStore(records)).delta("test", "com.test")
        self.assertEqual(res["delta"]["movement"], "new")
        self.assertIsNone(res["delta"]["delta"])

    def test_volatility_edge_cases(self):
        service = RankHistoryService()
        self.assertEqual(service._volatility([]), 0.0)
        self.assertEqual(service._volatility([5]), 0.0)

if __name__ == '__main__':
    unittest.main()
