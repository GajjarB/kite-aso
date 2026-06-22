"""Formatting helpers for CLI and TUI output."""

from __future__ import annotations

from datetime import UTC, datetime


def title_case_env(value: str) -> str:
    return (value or "").replace("-", " ").replace("_", " ").title()


def human_status(value: str) -> str:
    return (value or "").replace("_", " ").title()


def truncate(value: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: max(width - 1, 0)] + "…"


def format_time(value: str) -> str:
    if not value:
        return "Unknown"
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    delta = datetime.now(UTC) - moment.astimezone(UTC)
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 10:
        return "Just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"
