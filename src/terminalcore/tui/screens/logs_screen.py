"""Logs screen."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static

from ...core.adapters.demo_system_adapter import DemoSystemAdapter
from ...core.types import AppConfig
from ...utils.format import format_time
from ..components.log_viewer import LogViewer
from ..components.search_input import SearchInput


class LogsScreen(Vertical):
    """Log browsing screen."""

    def __init__(self, config: AppConfig, adapter: DemoSystemAdapter):
        super().__init__(classes="screen")
        self.config = config
        self.adapter = adapter
        self.level = ""

    def compose(self):
        yield SearchInput("Filter by level or text", id="logs-search")
        yield Static("Logs", classes="panel-title")
        viewer = LogViewer(id="logs-viewer")
        for item in self._filtered_logs():
            tone = {"info": "#7DA7C7", "success": "#7FA66A", "warning": "#D0A24C", "error": "#C7655A"}.get(item.level, "#C9BDB1")
            viewer.write(f"[{tone}]{format_time(item.timestamp):<12} {item.level.upper():<7}[/] {item.message}")
        yield viewer

    def _filtered_logs(self):
        items = self.adapter.get_logs(self.config)
        if not self.level:
            return items
        query = self.level.lower()
        return [item for item in items if query in item.level.lower() or query in item.message.lower()]

    def on_input_changed(self, event: SearchInput.Changed) -> None:
        self.level = event.value.strip()
        self.refresh(recompose=True)

    def refresh_data(self):
        self.refresh(recompose=True)
        return self
