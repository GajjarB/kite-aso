"""Badge component."""

from __future__ import annotations

from textual.widgets import Static


class Badge(Static):
    """Small status badge."""

    def __init__(self, label: str, tone: str = "muted", **kwargs):
        super().__init__(label, classes=f"badge {tone}", **kwargs)
