"""Init command."""

from __future__ import annotations

from ...core.config.config_store import ConfigStore
from ...wizard.init_wizard import run_init_wizard


def run_init_command() -> int:
    run_init_wizard(ConfigStore())
    return 0
