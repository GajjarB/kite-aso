"""Config commands."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ...core.config.config_store import ConfigStore
from ...utils.format import human_status, title_case_env

console = Console()


def run_config_list() -> int:
    config = ConfigStore().load()
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("workspaceName", config.workspace_name)
    table.add_row("environment", title_case_env(config.environment))
    table.add_row("theme", config.theme)
    table.add_row("demoData", human_status(str(config.demo_data)))
    table.add_row("createdAt", config.created_at)
    table.add_row("version", config.version)
    console.print()
    console.print("[bold]TerminalCore Config[/bold]")
    console.print()
    console.print(table)
    return 0


def run_config_get(key: str) -> int:
    config = ConfigStore().load()
    mapping = {
        "workspaceName": config.workspace_name,
        "environment": config.environment,
        "theme": config.theme,
        "demoData": str(config.demo_data).lower(),
        "createdAt": config.created_at,
        "version": config.version,
    }
    console.print(mapping.get(key, ""))
    return 0


def run_config_set(key: str, value: str) -> int:
    config = ConfigStore().update(key, value)
    mapping = {
        "workspaceName": config.workspace_name,
        "environment": config.environment,
        "theme": config.theme,
        "demoData": str(config.demo_data).lower(),
    }
    console.print(f"[bold #7FA66A]Updated[/bold #7FA66A]  {key} = {mapping.get(key, value)}")
    return 0


def run_config_reset() -> int:
    config = ConfigStore().reset()
    console.print(f"[bold #D0A24C]Config reset[/bold #D0A24C]  Workspace: {config.workspace_name}")
    return 0
