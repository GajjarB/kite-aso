"""Run command."""

from __future__ import annotations

import time

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ...core.adapters.demo_system_adapter import DemoSystemAdapter
from ...core.config.config_store import ConfigStore

console = Console()


def run_primary_action(task_name: str = "Run primary task") -> int:
    config = ConfigStore().load()
    adapter = DemoSystemAdapter()

    console.print()
    console.print("[bold]TerminalCore Run[/bold]")
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running system action", total=100)
        for step in range(0, 101, 20):
            progress.update(task, completed=step)
            time.sleep(0.12)

    result = adapter.run_task(config, task_name)
    console.print(f"[bold #7FA66A]Success[/bold #7FA66A]  {result.name} completed.")
    console.print(f"Last run   {result.last_run}")
    return 0
