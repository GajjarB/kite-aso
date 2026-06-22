"""Doctor command."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ...core.services.doctor_service import DoctorService

console = Console()


def run_doctor_command() -> int:
    report = DoctorService().run()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("status", width=2)
    table.add_column("name", style="bold", width=18)
    table.add_column("detail")

    icon_map = {"ok": "[#7FA66A]OK[/#7FA66A]", "warning": "[#D0A24C]!![/#D0A24C]", "error": "[#C7655A]ER[/#C7655A]"}
    for item in report.checks:
        table.add_row(icon_map.get(item.status, "-"), item.name, item.detail)

    console.print()
    console.print("[bold]TerminalCore Doctor[/bold]")
    console.print()
    console.print("[bold]Checks[/bold]")
    console.print(table)
    console.print()
    console.print("[bold]Result[/bold]")
    console.print("Your workspace looks healthy." if report.ok else "One or more checks need attention.")
    return 0
