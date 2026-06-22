import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.terminalcore.core.config.config_store import ConfigStore
from src.terminalcore.wizard.init_wizard import run_init_wizard


class TerminalCoreWizardTests(unittest.TestCase):
    def test_init_wizard_creates_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(Path(tmp) / "config.json")
            with patch("src.terminalcore.wizard.init_wizard.Prompt.ask", side_effect=["demo-space", "1", "1"]):
                with patch("src.terminalcore.wizard.init_wizard.Confirm.ask", return_value=True):
                    run_init_wizard(store)

            config = store.load()
            self.assertEqual(config.workspace_name, "demo-space")
            self.assertEqual(config.environment, "development")


if __name__ == "__main__":
    unittest.main()
