"""Status and dashboard service."""

from __future__ import annotations

from ..adapters.demo_system_adapter import DemoSystemAdapter
from ..types import AppConfig, SystemStatus


class StatusService:
    """Wrapper around adapter status operations."""

    def __init__(self, adapter: DemoSystemAdapter | None = None):
        self.adapter = adapter or DemoSystemAdapter()

    def get_status(self, config: AppConfig) -> SystemStatus:
        return self.adapter.get_status(config)
