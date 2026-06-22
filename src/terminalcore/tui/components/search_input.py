"""Search input component."""

from __future__ import annotations

from textual.widgets import Input


class SearchInput(Input):
    """Compact search box."""

    def __init__(self, placeholder: str = "Search…", **kwargs):
        super().__init__(placeholder=placeholder, classes="search-input", **kwargs)
