"""Writable runtime locations for the ASO platform.

Everything the platform writes at runtime (caches, reports, rank history,
workspaces) lives under a single user-owned home directory instead of the
installed package tree, so a `pip install` into a read-only or shared
site-packages still works. Override the location with ``KITE_HOME``.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Root for all user-owned runtime state. Override with ``KITE_HOME``.
KITE_HOME = Path(os.environ.get("KITE_HOME") or (Path.home() / ".kite")).expanduser()

DATA_DIR = KITE_HOME / "data"
CACHE_DIR = KITE_HOME / "cache"
REPORTS_DIR = KITE_HOME / "reports"
CONFIG_DIR = KITE_HOME / "config"

#: Read-only JSON shipped inside the wheel (source registry, capability catalog).
RESOURCES_DIR = Path(__file__).resolve().parent / "resources"


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(name: str) -> Path:
    """Resolve a bundled resource, letting ``KITE_HOME/config`` override it."""
    override = CONFIG_DIR / name
    if override.is_file():
        return override
    return RESOURCES_DIR / name
