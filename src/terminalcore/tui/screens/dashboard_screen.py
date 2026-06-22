"""Dashboard screen."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from ...core.adapters.demo_system_adapter import DemoSystemAdapter
from ...core.types import AppConfig
from ...utils.format import format_time, human_status, title_case_env
from ..components.card import StatCard
from src.aso_platform.services.intelligence import SourceHealthService
from src.aso_platform.services.workspace import WorkspaceService


class DashboardScreen(Vertical):
    """Overview dashboard."""

    def __init__(self, config: AppConfig, adapter: DemoSystemAdapter):
        super().__init__(classes="screen screen-dashboard")
        self.config = config
        self.adapter = adapter

    def compose(self):
        status = self.adapter.get_status(self.config)
        health = self.adapter.get_health(self.config)
        logs = self.adapter.get_logs(self.config)[:4]
        passed = sum(item.status == "ok" for item in health.checks)
        workspaces = WorkspaceService().list()
        source_health = SourceHealthService().health()["source_health"]
        ready_sources = sum(item["legal_ready"] for item in source_health)

        with Horizontal(classes="stat-row"):
            yield StatCard("Status", human_status(status.status), f"Last check {format_time(status.last_check)}")
            yield StatCard("Env", title_case_env(status.environment), f"Version {status.version}")
            yield StatCard("Health", f"{passed}/{len(health.checks)} checks passed", "No blocking issues")
            yield StatCard("ASO", f"{len(workspaces)} workspaces", f"{ready_sources}/{len(source_health)} sources ready")

        with Horizontal(classes="panel-row"):
            with Vertical(classes="panel card"):
                yield Static("Overview", classes="panel-title")
                yield Static(
                    f"Workspace [b]{self.config.workspace_name}[/b] is ready for daily operations.",
                    classes="panel-copy",
                )
                yield Static(
                    "Use the left rail to move between projects, tasks, logs, settings, and help.",
                    classes="panel-copy muted",
                )
            with Vertical(classes="panel card"):
                yield Static("Quick Actions", classes="panel-title")
                yield Static("Enter  Open selected section", classes="panel-copy")
                yield Static("d      Run primary action", classes="panel-copy")
                yield Static("l      Open logs", classes="panel-copy")
                yield Static("s      Open settings", classes="panel-copy")

        with Vertical(classes="panel card"):
            yield Static("ASO Signals", classes="panel-title")
            if workspaces:
                for workspace in workspaces[:4]:
                    yield Static(
                        f"{workspace.name}: {workspace.target_package_id}  {workspace.country}/{workspace.lang}  competitors={len(workspace.competitors)}",
                        classes="panel-copy",
                    )
            else:
                yield Static("No ASO workspaces yet. Create one with `kite workspace init`.", classes="panel-copy muted")

        with Vertical(classes="panel card"):
            yield Static("Recent Activity", classes="panel-title")
            for item in logs:
                tone = "muted"
                if item.level == "error":
                    tone = "error-text"
                elif item.level == "warning":
                    tone = "warning-text"
                elif item.level == "success":
                    tone = "success-text"
                level = item.level.upper().ljust(7)
                stamp = format_time(item.timestamp).ljust(12)
                yield Static(f"{stamp} {level} {item.message}", classes=f"panel-copy {tone}")

    def refresh_data(self) -> Widget:
        self.refresh(recompose=True)
        return self
