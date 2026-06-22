import io
import unittest

from rich.console import Console

import aso


class TuiDashboardTests(unittest.TestCase):
    def test_dashboard_renderer_prints_core_panels_without_input(self):
        buffer = io.StringIO()
        original_console = aso.console
        try:
            aso.console = Console(file=buffer, force_terminal=False, width=140)
            aso.render_system_overview()
        finally:
            aso.console = original_console

        rendered = buffer.getvalue()
        self.assertIn("SOURCE HEALTH", rendered)
        self.assertIn("REPORT TELEMETRY", rendered)
        self.assertIn("KEYWORD CATEGORIES", rendered)
        self.assertIn("Free/legal sources only", rendered)


if __name__ == "__main__":
    unittest.main()
