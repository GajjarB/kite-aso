"""Status bar and footer components."""

from __future__ import annotations

from textual.widgets import Static


class StatusBar(Static):
    """Bottom status area."""

    def set_message(self, message: str) -> None:
        self.update(message)


class FooterHelp(Static):
    """Keyboard hint footer."""
