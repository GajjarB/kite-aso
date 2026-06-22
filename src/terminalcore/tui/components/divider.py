"""Divider component."""

from __future__ import annotations

from textual.widgets import Static


class Divider(Static):
    """Muted section divider."""

    def __init__(self, label: str = "", **kwargs):
        super().__init__(label, classes="divider", **kwargs)
