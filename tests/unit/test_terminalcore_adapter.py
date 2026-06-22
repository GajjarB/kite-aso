import unittest

from src.terminalcore.core.adapters.demo_system_adapter import DemoSystemAdapter
from src.terminalcore.core.config.config_schema import default_config


class TerminalCoreAdapterTests(unittest.TestCase):
    def test_demo_adapter_returns_status_projects_tasks_and_logs(self):
        adapter = DemoSystemAdapter()
        config = default_config()

        self.assertEqual(adapter.get_status(config).status, "running")
        self.assertTrue(adapter.get_projects(config))
        self.assertTrue(adapter.get_tasks(config))
        self.assertTrue(adapter.get_logs(config))
        self.assertTrue(adapter.get_health(config).checks)


if __name__ == "__main__":
    unittest.main()
