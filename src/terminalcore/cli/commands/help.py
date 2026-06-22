"""Help command."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

console = Console()


def run_help_command() -> int:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("command", style="bold #D97745", width=24)
    table.add_column("description")
    rows = [
        ("terminalcore", "Open the dashboard, or run first-time setup when config is missing."),
        ("terminalcore init", "Run the interactive setup wizard."),
        ("terminalcore dashboard", "Open the full-screen dashboard."),
        ("terminalcore status", "Show clean system status output."),
        ("terminalcore run", "Run the primary task with progress feedback."),
        ("terminalcore logs", "Show logs with optional tail mode and level filter."),
        ("terminalcore config", "List, get, set, or reset config."),
        ("terminalcore doctor", "Run local health checks."),
        ("terminalcore help", "Show this command reference."),
    ]
    for command, description in rows:
        table.add_row(command, description)

    console.print()
    console.print("[bold]TerminalCore Help[/bold]")
    console.print()
    console.print(table)
    return 0
