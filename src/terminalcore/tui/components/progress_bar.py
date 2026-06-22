"""Simple text progress bar."""

from __future__ import annotations

from textual.widgets import Static


class ProgressMeter(Static):
    """ASCII progress bar with percentage."""

    def __init__(self, progress: int, width: int = 20, **kwargs):
        self.progress = max(0, min(progress, 100))
        self.width = width
        super().__init__(self.render_bar(), classes="task-progress", **kwargs)

    def render_bar(self) -> str:
        filled = max(0, min(self.width, round(self.progress / 100 * self.width)))
        return f"[{'#' * filled}{'-' * (self.width - filled)}] {self.progress:>3}%"
