"""saas command — launch the local ASO web console."""

from __future__ import annotations

import os

from rich.console import Console
from rich.panel import Panel

console = Console()


def run_saas_command(host: str = "127.0.0.1", port: int = 8787) -> int:
    """Start the local SaaS web console."""

    # Auto-generate a local dev secret key if one isn't set.
    # This makes `kite saas` work out of the box without any env setup.
    if not os.environ.get("ASO_SECRET_KEY"):
        import hashlib
        import platform
        seed = f"kite-aso-local-{platform.node()}"
        os.environ["ASO_SECRET_KEY"] = hashlib.sha256(seed.encode()).hexdigest()

    console.print()
    console.print(
        Panel(
            f"[bold]Kite Web Console[/bold]\n\n"
            f"Starting at [link=http://{host}:{port}]http://{host}:{port}[/link]\n\n"
            f"Press [bold]Ctrl+C[/bold] to stop.",
            title="kite saas",
            border_style="#D97745",
            padding=(1, 2),
        )
    )
    console.print()

    try:
        from src.aso_platform.saas_app import run as saas_run  # type: ignore[import]
        saas_run(host=host, port=port)
    except ImportError:
        # Fallback for installed package layout
        from aso_platform.saas_app import run as saas_run  # type: ignore[import]
        saas_run(host=host, port=port)

    return 0
