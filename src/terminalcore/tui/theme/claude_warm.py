"""Warm terminal theme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TerminalTheme:
    primary_background: str = "#1E1A17"
    secondary_background: str = "#2A241F"
    surface: str = "#332B25"
    elevated_surface: str = "#3B322B"
    primary_text: str = "#F4EFE7"
    secondary_text: str = "#C9BDB1"
    muted_text: str = "#8F8175"
    primary_accent: str = "#D97745"
    accent_soft: str = "#E8A36F"
    accent_dark: str = "#A85632"
    border: str = "#5A4C42"
    success: str = "#7FA66A"
    warning: str = "#D0A24C"
    error: str = "#C7655A"
    info: str = "#7DA7C7"


CLAUDE_WARM = TerminalTheme()
