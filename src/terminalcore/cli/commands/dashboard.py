"""Dashboard command."""

from __future__ import annotations

from ...core.config.config_store import ConfigStore
from ...wizard.init_wizard import run_init_wizard
from ...tui.app import run_dashboard_app


def run_dashboard_command() -> int:
    store = ConfigStore()
    if not store.exists():
        run_init_wizard(store)
    config = store.load()
    run_dashboard_app(config)
    return 0
