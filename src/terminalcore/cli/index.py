"""TerminalCore CLI entrypoint."""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.panel import Panel

from ..utils.errors import ConfigValidationError
from .commands.config import run_config_get, run_config_list, run_config_reset, run_config_set
from .commands.dashboard import run_dashboard_command
from .commands.doctor import run_doctor_command
from .commands.help import run_help_command
from .commands.init import run_init_command
from .commands.logs import run_logs_command
from .commands.run import run_primary_action
from .commands.status import run_status_command
from .commands.saas import run_saas_command

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terminalcore",
        description="A warm, keyboard-first hybrid CLI and TUI workspace.",
    )
    parser.add_argument("--version", action="version", version="TerminalCore 1.0.0")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init")
    subparsers.add_parser("dashboard")
    subparsers.add_parser("status")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("task_name", nargs="*", help="Optional task label")

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("--tail", action="store_true")
    logs_parser.add_argument("--level", choices=("info", "success", "warning", "error"))

    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_subparsers.add_parser("list")
    config_get = config_subparsers.add_parser("get")
    config_get.add_argument("key")
    config_set = config_subparsers.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_subparsers.add_parser("reset")

    subparsers.add_parser("doctor")
    subparsers.add_parser("help")

    saas_parser = subparsers.add_parser("saas", help="Launch the local web console")
    saas_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    saas_parser.add_argument("--port", type=int, default=8787, help="Port to listen on (default: 8787)")

    return parser


def _print_error(message: str, fix: str = "terminalcore doctor") -> int:
    console.print()
    console.print(
        Panel(
            f"[bold]Config file is invalid.[/bold]\n\nReason:\n{message}\n\nFix:\n{fix}",
            title="TerminalCore Error",
            border_style="#C7655A",
            padding=(1, 2),
        )
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {None, "dashboard"}:
            return run_dashboard_command()
        if args.command == "init":
            return run_init_command()
        if args.command == "status":
            return run_status_command()
        if args.command == "run":
            task_name = " ".join(args.task_name) if args.task_name else "Run primary task"
            return run_primary_action(task_name)
        if args.command == "logs":
            return run_logs_command(tail=args.tail, level=args.level)
        if args.command == "doctor":
            return run_doctor_command()
        if args.command == "help":
            return run_help_command()
        if args.command == "config":
            if args.config_command in {None, "list"}:
                return run_config_list()
            if args.config_command == "get":
                return run_config_get(args.key)
            if args.config_command == "set":
                return run_config_set(args.key, args.value)
            if args.config_command == "reset":
                return run_config_reset()
        if args.command == "saas":
            return run_saas_command(host=args.host, port=args.port)
        return run_help_command()
    except ConfigValidationError as exc:
        return _print_error(str(exc), "terminalcore config reset")
