"""Logs command."""

from __future__ import annotations

import time

from rich.console import Console
from rich.live import Live
from rich.table import Table

from ...core.adapters.demo_system_adapter import DemoSystemAdapter
from ...core.config.config_store import ConfigStore
from ...core.services.log_service import LogService
from ...utils.format import format_time

console = Console()


def _render_logs(level: str | None = None) -> Table:
    config = ConfigStore().load()
    logs = LogService(DemoSystemAdapter()).get_logs(config, level=level)
    table = Table(show_header=True, header_style="bold")
    table.add_column("Time", style="#8F8175", width=12)
    table.add_column("Level", width=10)
    table.add_column("Message", ratio=1)
    for item in logs:
        table.add_row(format_time(item.timestamp), item.level.upper(), item.message)
    return table


def run_logs_command(tail: bool = False, level: str | None = None) -> int:
    console.print()
    console.print("[bold]TerminalCore Logs[/bold]")
    console.print()
    if not tail:
        console.print(_render_logs(level))
        return 0

    try:
        with Live(_render_logs(level), console=console, refresh_per_second=2) as live:
            while True:
                time.sleep(1)
                live.update(_render_logs(level))
    except KeyboardInterrupt:
        console.print()
        console.print("[#8F8175]Tail mode stopped.[/#8F8175]")
        return 0
