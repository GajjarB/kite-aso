"""Dependency-free ASCII chart helpers for the terminal UI."""

from __future__ import annotations

from collections import Counter
from typing import Iterable


def _clamp_width(width: int) -> int:
    return max(1, int(width or 1))


def mini_bar(value: float, max_value: float, width: int = 20) -> str:
    """Render a compact ASCII bar scaled to max_value."""
    width = _clamp_width(width)
    if max_value <= 0:
        filled = 0
        percent = 0
    else:
        ratio = max(0.0, min(1.0, float(value) / float(max_value)))
        filled = int(round(ratio * width))
        percent = int(round(ratio * 100))
    return f"{'#' * filled}{'-' * (width - filled)} {percent:3d}%"


def rank_bar(score: float, width: int = 18) -> str:
    """Render a 0-100 score bar."""
    capped = max(0.0, min(100.0, float(score or 0)))
    return f"{mini_bar(capped, 100, width)} {capped:5.1f}"


def sparkline(values: Iterable[float], width: int = 32) -> str:
    """Render values as an ASCII-only sparkline."""
    width = _clamp_width(width)
    series = [float(value or 0) for value in values]
    if not series:
        return " " * width
    if len(series) > width:
        step = len(series) / width
        series = [series[int(index * step)] for index in range(width)]
    if len(series) < width:
        series = ([0.0] * (width - len(series))) + series

    high = max(series)
    low = min(series)
    chars = "._-:=+*#%@"
    if high == low:
        return chars[0 if high <= 0 else len(chars) // 2] * width

    span = high - low
    rendered = []
    for value in series:
        index = int(round(((value - low) / span) * (len(chars) - 1)))
        rendered.append(chars[max(0, min(len(chars) - 1, index))])
    return "".join(rendered)


def count_by(items: Iterable[dict], field: str, default: str = "unknown") -> dict[str, int]:
    counts = Counter(str(item.get(field) or default) for item in items)
    return dict(sorted(counts.items()))


def score_buckets(items: Iterable[dict], field: str = "composite_score") -> dict[str, int]:
    buckets = {"0-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    for item in items:
        score = float(item.get(field) or 0)
        if score >= 80:
            buckets["80-100"] += 1
        elif score >= 60:
            buckets["60-79"] += 1
        elif score >= 40:
            buckets["40-59"] += 1
        else:
            buckets["0-39"] += 1
    return buckets


def is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True
