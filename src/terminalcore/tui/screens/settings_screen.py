"""Settings screen."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from ...core.config.config_store import ConfigStore
from ...core.types import AppConfig


class SettingsScreen(Vertical):
    """Config and theme screen."""

    def __init__(self, config: AppConfig):
        super().__init__(classes="screen")
        self.config = config

    def compose(self):
        with Horizontal(classes="panel-row"):
            with Vertical(classes="panel card"):
                yield Static("Settings", classes="panel-title")
                yield Static(f"Workspace     {self.config.workspace_name}", classes="panel-copy")
                yield Static(f"Environment   {self.config.environment.title()}", classes="panel-copy")
                yield Static(f"Theme         {self.config.theme}", classes="panel-copy")
                yield Static(f"Demo data     {'Enabled' if self.config.demo_data else 'Disabled'}", classes="panel-copy")
            with Vertical(classes="panel card"):
                yield Static("Actions", classes="panel-title")
                yield Button("Reset Config", id="reset-config")
                yield Static("Resetting returns the workspace to the default warm profile.", classes="panel-copy muted")

    def refresh_data(self):
        self.refresh(recompose=True)
        return self
