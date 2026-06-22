"""Status command."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ...core.adapters.demo_system_adapter import DemoSystemAdapter
from ...core.config.config_store import ConfigStore
from ...core.services.status_service import StatusService
from ...utils.format import format_time, human_status, title_case_env

console = Console()


def run_status_command() -> int:
    config = ConfigStore().load()
    status = StatusService(DemoSystemAdapter()).get_status(config)

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("System", human_status(status.status))
    table.add_row("Environment", title_case_env(status.environment))
    table.add_row("Version", status.version)
    table.add_row("Config", human_status(status.config_status))
    table.add_row("Last Check", format_time(status.last_check))
    table.add_row("Projects", str(status.active_projects))
    table.add_row("Tasks", str(status.active_tasks))

    console.print()
    console.print("[bold]TerminalCore Status[/bold]")
    console.print()
    console.print(table)
    return 0
