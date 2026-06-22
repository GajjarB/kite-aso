"""Card components."""

from __future__ import annotations

from textual.containers import Container, Vertical
from textual.widgets import Static


class Card(Container):
    """Generic panel card."""

    def __init__(self, title: str, *children, **kwargs):
        super().__init__(*children, classes="card", **kwargs)
        self.title = title

    def compose(self):
        yield Static(self.title, classes="card-title")
        for child in self.children:
            yield child


class StatCard(Vertical):
    """Compact stat card."""

    def __init__(self, label: str, value: str, detail: str = "", **kwargs):
        super().__init__(classes="stat-card", **kwargs)
        self.label = label
        self.value = value
        self.detail = detail

    def compose(self):
        yield Static(self.label, classes="stat-label")
        yield Static(self.value, classes="stat-value")
        if self.detail:
            yield Static(self.detail, classes="stat-detail")
