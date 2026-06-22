"""Tasks screen."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from ...core.adapters.demo_system_adapter import DemoSystemAdapter
from ...core.types import AppConfig
from ...utils.format import format_time, human_status
from ..components.progress_bar import ProgressMeter


class TasksScreen(Vertical):
    """Task list and progress view."""

    def __init__(self, config: AppConfig, adapter: DemoSystemAdapter):
        super().__init__(classes="screen")
        self.config = config
        self.adapter = adapter

    def compose(self):
        tasks = self.adapter.get_tasks(self.config)
        with Vertical(classes="panel card"):
            yield Static("Tasks", classes="panel-title")
            for item in tasks:
                with Horizontal(classes="task-row"):
                    with Vertical(classes="task-copy"):
                        yield Static(item.name, classes="detail-head")
                        yield Static(f"{human_status(item.status)}  •  {format_time(item.last_run)}", classes="panel-copy muted")
                    yield ProgressMeter(item.progress)

    def refresh_data(self):
        self.refresh(recompose=True)
        return self
