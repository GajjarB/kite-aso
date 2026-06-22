import json
import tempfile
import unittest
from pathlib import Path

from src.terminalcore.core.config.config_schema import default_config, validate_config
from src.terminalcore.core.config.config_store import ConfigStore
from src.terminalcore.utils.errors import ConfigValidationError


class TerminalCoreConfigTests(unittest.TestCase):
    def test_validate_config_accepts_valid_payload(self):
        config = validate_config(
            {
                "workspaceName": "TerminalCore",
                "environment": "development",
                "theme": "claude-warm",
                "demoData": True,
                "createdAt": "2026-05-16T00:00:00+00:00",
                "version": "1.0.0",
            }
        )

        self.assertEqual(config.workspace_name, "TerminalCore")
        self.assertEqual(config.environment, "development")

    def test_validate_config_rejects_missing_workspace_name(self):
        with self.assertRaises(ConfigValidationError):
            validate_config(
                {
                    "environment": "development",
                    "theme": "claude-warm",
                    "demoData": True,
                    "createdAt": "2026-05-16T00:00:00+00:00",
                    "version": "1.0.0",
                }
            )

    def test_config_store_reads_and_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = ConfigStore(path)
            saved = store.save(default_config(workspace_name="Lab"))
            loaded = store.load()

            self.assertTrue(path.exists())
            self.assertEqual(saved.workspace_name, "Lab")
            self.assertEqual(loaded.workspace_name, "Lab")

    def test_config_store_update_changes_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = ConfigStore(path)
            store.save(default_config())
            updated = store.update("environment", "staging")

            self.assertEqual(updated.environment, "staging")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["environment"], "staging")


if __name__ == "__main__":
    unittest.main()
