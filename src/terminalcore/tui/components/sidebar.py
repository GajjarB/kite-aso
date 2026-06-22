"""Sidebar component."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static


class Sidebar(Vertical):
    """Simple navigation rail."""

    items = [
        "Dashboard",
        "Projects",
        "Tasks",
        "Logs",
        "Settings",
        "Help",
        "ASO Workspaces",
        "ASO Keywords",
        "ASO Competitors",
        "ASO Reviews",
        "ASO Reports",
        "ASO Sources",
    ]

    def __init__(self, **kwargs):
        super().__init__(classes="sidebar", **kwargs)
        self.index = 0

    def compose(self):
        yield Static("Navigate", classes="sidebar-title")
        for position, item in enumerate(self.items):
            css = "nav-item active" if position == self.index else "nav-item"
            prefix = "> " if position == self.index else "  "
            yield Static(prefix + item, classes=css, id=f"nav-{item.lower().replace(' ', '-')}")

    def move(self, delta: int) -> str:
        self.index = (self.index + delta) % len(self.items)
        self.refresh(recompose=True)
        return self.current

    @property
    def current(self) -> str:
        return self.items[self.index].lower().replace(" ", "_")

    def set_current(self, name: str) -> None:
        for idx, item in enumerate(self.items):
            if item.lower().replace(" ", "_") == name.lower():
                self.index = idx
                self.refresh(recompose=True)
                return
