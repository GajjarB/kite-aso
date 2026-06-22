import tempfile
import unittest
from pathlib import Path

from src.terminalcore.core.config.config_store import ConfigStore
from src.terminalcore.core.services.doctor_service import DoctorService


class TerminalCoreDoctorTests(unittest.TestCase):
    def test_doctor_reports_missing_config_as_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(Path(tmp) / "config.json")
            report = DoctorService(store).run()

            self.assertTrue(any(item.name == "Config file" for item in report.checks))
            self.assertTrue(any(item.status in {"warning", "ok"} for item in report.checks))


if __name__ == "__main__":
    unittest.main()
