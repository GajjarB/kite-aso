"""Health and doctor checks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ...utils.paths import APP_DIR, CONFIG_PATH, ensure_app_dir
from ...utils.terminal import detect_terminal_support
from ..config.config_store import ConfigStore
from ..types import HealthCheck, HealthReport


class DoctorService:
    """Run local environment checks."""

    def __init__(self, config_store: ConfigStore | None = None):
        self.config_store = config_store or ConfigStore()

    def run(self) -> HealthReport:
        ensure_app_dir()
        checks: list[HealthCheck] = []

        checks.append(
            HealthCheck(
                "Node version",
                "ok",
                "Not required in Python mode; current product shell is native Python.",
            )
        )

        checks.append(
            HealthCheck(
                "Config file",
                "ok" if CONFIG_PATH.exists() else "warning",
                "Found" if CONFIG_PATH.exists() else "Missing; run terminalcore init.",
            )
        )

        try:
            self.config_store.load()
            checks.append(HealthCheck("Config schema", "ok", "Valid"))
        except Exception as exc:
            checks.append(HealthCheck("Config schema", "warning", str(exc)))

        support = detect_terminal_support()
        checks.append(
            HealthCheck(
                "Terminal colors",
                "ok" if support.truecolor else "warning",
                "True color supported" if support.truecolor else "Falling back to basic palette",
            )
        )

        writable = os.access(str(APP_DIR), os.W_OK) if APP_DIR.exists() else os.access(str(Path.home()), os.W_OK)
        checks.append(
            HealthCheck(
                "Write permission",
                "ok" if writable else "error",
                "OK" if writable else "Cannot write to the TerminalCore home directory",
            )
        )

        checks.append(
            HealthCheck(
                "Python version",
                "ok" if sys.version_info >= (3, 11) else "warning",
                ".".join(str(part) for part in sys.version_info[:3]),
            )
        )
        return HealthReport(checks=checks)
