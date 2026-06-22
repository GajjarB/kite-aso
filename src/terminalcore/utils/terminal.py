"""Terminal support helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TerminalSupport:
    width: int
    height: int
    truecolor: bool
    unicode: bool


def detect_terminal_support() -> TerminalSupport:
    size = os.get_terminal_size() if os.isatty(1) else os.terminal_size((100, 32))
    colorterm = (os.environ.get("COLORTERM") or "").lower()
    term = (os.environ.get("TERM") or "").lower()
    truecolor = "truecolor" in colorterm or "24bit" in colorterm or "direct" in term
    return TerminalSupport(
        width=size.columns,
        height=size.lines,
        truecolor=truecolor,
        unicode=True,
    )


def layout_mode(width: int) -> str:
    if width >= 100:
        return "wide"
    if width >= 70:
        return "compact"
    if width >= 50:
        return "stack"
    return "minimal"
