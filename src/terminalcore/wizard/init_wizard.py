"""Interactive setup wizard."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .. import __version__
from ..core.config.config_schema import default_config
from ..core.config.config_store import ConfigStore
from ..utils.format import title_case_env

console = Console()

THEME_CHOICES = {
    "1": ("claude-warm", "Claude Warm"),
    "2": ("classic-dark", "Classic Dark"),
    "3": ("minimal-light", "Minimal Light"),
}
ENV_CHOICES = {
    "1": ("development", "Development"),
    "2": ("staging", "Staging"),
    "3": ("production", "Production"),
}


def run_init_wizard(config_store: ConfigStore | None = None) -> None:
    """Run the first-time interactive setup flow."""
    store = config_store or ConfigStore()

    console.clear()
    console.print()
    console.print(
        Panel.fit(
            "[bold]Welcome to TerminalCore[/bold]\n\nA calm, powerful terminal workspace for managing your system.",
            border_style="#D97745",
            padding=(1, 2),
        )
    )
    console.print()

    workspace_name = Prompt.ask("Workspace name", default="terminal-core").strip() or "terminal-core"

    console.print()
    console.print("[bold]Environment[/bold]")
    for key, (_, label) in ENV_CHOICES.items():
        console.print(f"  {key}. {label}")
    env_choice = Prompt.ask("Choose environment", choices=tuple(ENV_CHOICES), default="1")
    environment, environment_label = ENV_CHOICES[env_choice]

    console.print()
    console.print("[bold]Theme[/bold]")
    for key, (_, label) in THEME_CHOICES.items():
        console.print(f"  {key}. {label}")
    theme_choice = Prompt.ask("Choose theme", choices=tuple(THEME_CHOICES), default="1")
    theme, theme_label = THEME_CHOICES[theme_choice]

    demo_data = Confirm.ask("Create demo data?", default=True)

    config = default_config(
        workspace_name=workspace_name,
        environment=environment,
        theme=theme,
        demo_data=demo_data,
        version=__version__,
    )
    store.save(config)

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Workspace", config.workspace_name)
    summary.add_row("Environment", title_case_env(environment_label))
    summary.add_row("Theme", theme_label)
    summary.add_row("Demo data", "Enabled" if demo_data else "Disabled")

    console.print()
    console.print(Panel(summary, title="Workspace Ready", border_style="#7FA66A", padding=(1, 2)))
    console.print()
    console.print("[bold #7FA66A]Config created[/bold #7FA66A]")
    console.print("[bold #7FA66A]Workspace ready[/bold #7FA66A]")
    console.print()
    console.print("Next:")
    console.print("  terminalcore dashboard")
