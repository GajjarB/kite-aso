import asyncio
import tempfile
import unittest
from pathlib import Path

from src.terminalcore.core.config.config_schema import default_config
from src.terminalcore.core.config.config_store import ConfigStore
from src.terminalcore.tui.app import TerminalCoreApp


class TerminalCoreTuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_app_can_boot_and_navigate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(Path(tmp) / "config.json")
            config = store.save(default_config())
            app = TerminalCoreApp(config)

            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()

            self.assertEqual(app.current_screen, "projects")


if __name__ == "__main__":
    unittest.main()
