"""Shared branding helpers for Kite."""

from __future__ import annotations

import sys
from shutil import get_terminal_size

APP_NAME = "Kite"
APP_TAGLINE = "Free, legal ASO intelligence for Android apps."
KITE_ASCII_LOGO = """██╗  ██╗██╗████████╗███████╗
██║ ██╔╝██║╚══██╔══╝██╔════╝
█████╔╝ ██║   ██║   █████╗
██╔═██╗ ██║   ██║   ██╔══╝
██║  ██╗██║   ██║   ███████╗
╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝"""

LOGO_ACCENT = "#D97745"
LOGO_TEXT = "#F4EFE7"
LOGO_MUTED = "#8F8175"


def render_kite_logo(compact: bool = False, with_tagline: bool = True) -> str:
    """Return the Kite logo with a compact fallback for narrow terminals."""
    width = get_terminal_size(fallback=(100, 30)).columns
    use_compact = compact or width < 50 or not _stdout_supports_logo()
    lines = ["KITE"] if use_compact else [KITE_ASCII_LOGO]
    if with_tagline:
        lines.append(APP_TAGLINE)
    return "\n\n" + "\n".join(lines) + "\n"


def render_kite_logo_markup(compact: bool = False, with_tagline: bool = True) -> str:
    """Return the Kite logo with Rich markup styling."""
    width = get_terminal_size(fallback=(100, 30)).columns
    use_compact = compact or width < 50
    if use_compact:
        logo = f"[bold {LOGO_ACCENT}]KITE[/]"
    else:
        logo = f"[bold {LOGO_ACCENT}]{KITE_ASCII_LOGO}[/]"
    if with_tagline:
        return f"\n{logo}\n[{LOGO_MUTED}]{APP_TAGLINE}[/]\n"
    return f"\n{logo}\n"


def _stdout_supports_logo() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        KITE_ASCII_LOGO.encode(encoding)
    except UnicodeEncodeError:
        return False
    except LookupError:
        return False
    return True
