"""Help screen."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static


class HelpScreen(Vertical):
    """Keyboard shortcuts and about info."""

    def __init__(self):
        super().__init__(classes="screen")

    def compose(self):
        yield Static("Help", classes="panel-title")
        yield Static("q        Quit", classes="panel-copy")
        yield Static("Enter    Select current section", classes="panel-copy")
        yield Static("↑↓ j/k   Navigate sections", classes="panel-copy")
        yield Static("←→       Switch panels or tabs", classes="panel-copy")
        yield Static("/        Focus search when available", classes="panel-copy")
        yield Static("?        Open help", classes="panel-copy")
        yield Static("r        Refresh current screen", classes="panel-copy")
        yield Static("d        Run primary action", classes="panel-copy")
        yield Static("l        Open logs", classes="panel-copy")
        yield Static("s        Open settings", classes="panel-copy")
        yield Static("", classes="panel-copy")
        yield Static("TerminalCore is a reusable warm terminal shell that can wrap any backend adapter later.", classes="panel-copy muted")

    def refresh_data(self):
        self.refresh(recompose=True)
        return self
