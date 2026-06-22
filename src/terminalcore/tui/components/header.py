"""Header component."""

from __future__ import annotations

from textual.widgets import Static

from ...utils.format import human_status, title_case_env


class HeaderBar(Static):
    """Top command header."""

    def update_content(self, app_name: str, environment: str, version: str, status: str) -> None:
        self.update(
            f"[b]{app_name}[/b]    "
            f"[#8F8175]Env[/#8F8175] {title_case_env(environment)}    "
            f"[#8F8175]Version[/#8F8175] {version}    "
            f"[#8F8175]Status[/#8F8175] {human_status(status)}"
        )
