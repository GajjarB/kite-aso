"""Logs service."""

from __future__ import annotations

from ..adapters.demo_system_adapter import DemoSystemAdapter
from ..types import AppConfig, LogRecord


class LogService:
    """Load logs from the current adapter."""

    def __init__(self, adapter: DemoSystemAdapter | None = None):
        self.adapter = adapter or DemoSystemAdapter()

    def get_logs(self, config: AppConfig, level: str | None = None) -> list[LogRecord]:
        return self.adapter.get_logs(config, level=level)
