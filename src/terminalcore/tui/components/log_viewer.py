"""Scrollable log viewer."""

from __future__ import annotations

from textual.widgets import RichLog


class LogViewer(RichLog):
    """Warm-themed log surface."""

    def __init__(self, **kwargs):
        super().__init__(highlight=True, markup=True, wrap=True, classes="log-viewer", **kwargs)
