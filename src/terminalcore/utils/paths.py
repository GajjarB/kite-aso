"""Filesystem paths for TerminalCore."""

from __future__ import annotations

from pathlib import Path


APP_DIR = Path.home() / ".terminalcore"
CONFIG_PATH = APP_DIR / "config.json"
LOGS_PATH = APP_DIR / "logs.jsonl"
STATE_PATH = APP_DIR / "state.json"


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR
