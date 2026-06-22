"""Empty, error, and success states."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static


class EmptyState(Vertical):
    def __init__(self, title: str, body: str, **kwargs):
        classes = kwargs.pop("classes", "")
        combined = "state-card empty-state"
        if classes:
            combined = f"{combined} {classes}"
        super().__init__(classes=combined, **kwargs)
        self.title = title
        self.body = body

    def compose(self):
        yield Static(self.title, classes="state-title")
        yield Static(self.body, classes="state-body")


class ErrorState(EmptyState):
    def __init__(self, title: str, body: str, **kwargs):
        super().__init__(title, body, classes="error-state", **kwargs)


class SuccessState(EmptyState):
    def __init__(self, title: str, body: str, **kwargs):
        super().__init__(title, body, classes="success-state", **kwargs)
