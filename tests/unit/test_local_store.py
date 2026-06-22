import tempfile
import unittest
from pathlib import Path

from src.aso_platform.services.local_store import LocalDataStore


class LocalDataStoreTests(unittest.TestCase):
    def test_append_and_read_events_keeps_payload_inspectable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalDataStore(Path(tmp))
            store.append_event("rank_history", {"keyword": "calculator", "target_position": 2})

            rows = store.read_events("rank_history")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "rank_history")
        self.assertEqual(rows[0]["payload"]["keyword"], "calculator")

    def test_json_roundtrip_uses_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalDataStore(Path(tmp))
            store.write_json("snapshots/app.json", {"title": "Stub"})
            payload = store.read_json("snapshots/app.json")

        self.assertEqual(payload["title"], "Stub")


if __name__ == "__main__":
    unittest.main()

