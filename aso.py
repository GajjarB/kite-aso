#!/usr/bin/env python3
"""
ASO Pro — Android App Store Optimization Terminal
"""

import sys
import os
import json
import time
import threading
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich import box

from src.aso_platform.ui.branding import APP_NAME

console = Console()

# ─────────────────────────────────────────────
# SESSION STATE  (persists across screens)
# ─────────────────────────────────────────────
_SESSION: dict = {
    "last_pkg":    "",      # last package ID used
    "last_seeds":  "",      # last keyword seeds
    "last_query":  "",      # last competitor search query
    "pkg_history": [],      # last 5 unique package IDs
}

# ── Rich markup colors (Claude Code palette) ──────────────────
C_BRAND    = "#CC785C"      # Claude orange
C_ACCENT   = "#4EC9A0"      # teal-green
C_WARN     = "#E5C07B"      # amber
C_ERROR    = "#E06C75"      # rose-red
C_DIM      = "grey50"       # dim gray
C_GOOD     = "#4EC9A0"      # teal-green
C_BAD      = "#E06C75"      # rose-red
C_SCORE_HI = "#4EC9A0"
C_SCORE_MD = "#E5C07B"
C_SCORE_LO = "#E06C75"

# ── Raw ANSI codes for interactive menus (no Rich overhead) ───
A_RST   = "\033[0m"
A_BRAND = "\033[38;2;204;120;92m"   # #CC785C exact true-color
A_DIM   = "\033[2m\033[37m"
A_SEL   = "\033[1m\033[97m"         # bold bright-white for selected item
A_HINT  = "\033[2m\033[37m"
A_GREEN = "\033[38;2;78;201;160m"   # #4EC9A0
A_AMBER = "\033[38;2;229;192;123m"  # #E5C07B
A_RED   = "\033[38;2;224;108;117m"  # #E06C75


# ─────────────────────────────────────────────
# CONSOLE INIT (call once at startup)
# ─────────────────────────────────────────────

def _init_console():
    """
    Windows: enable VT processing (ANSI output) + PROCESSED_INPUT (Ctrl+V paste).
    Both platforms: reconfigure stdout/stdin to UTF-8.
    """
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            # Output handle: PROCESSED_OUTPUT | WRAP_AT_EOL | VIRTUAL_TERMINAL_PROCESSING
            k32.SetConsoleMode(k32.GetStdHandle(-11), 0x0001 | 0x0002 | 0x0004 | 0x0100)
            # Input handle: PROCESSED_INPUT | LINE_INPUT | ECHO_INPUT
            # NOTE: do NOT set ENABLE_VIRTUAL_TERMINAL_INPUT (0x0200) — it swallows Ctrl+V
            k32.SetConsoleMode(k32.GetStdHandle(-10), 0x0001 | 0x0002 | 0x0004)
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleCP(65001)       # input UTF-8
            ctypes.windll.kernel32.SetConsoleOutputCP(65001) # output UTF-8
        except Exception:
            pass
    # Reconfigure streams to UTF-8 (Python 3.7+)
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def _clipboard_paste() -> str:
    """Read clipboard text on Windows. Returns '' on failure or non-Windows."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        CF_UNICODETEXT = 13
        if not ctypes.windll.user32.OpenClipboard(None):
            return ""
        try:
            h = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return ""
            ptr = ctypes.windll.kernel32.GlobalLock(h)
            if not ptr:
                return ""
            try:
                text = ctypes.wstring_at(ptr)
            finally:
                ctypes.windll.kernel32.GlobalUnlock(h)
            return text.strip()
        finally:
            ctypes.windll.user32.CloseClipboard()
    except Exception:
        return ""


# ─────────────────────────────────────────────
# TERMINAL UTILS
# ─────────────────────────────────────────────

def term_dims() -> tuple[int, int]:
    """Return (columns, lines) of current terminal."""
    s = shutil.get_terminal_size((120, 30))
    return s.columns, s.lines


def clear():
    """Instant ANSI clear — no subprocess, no flicker."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _getch() -> str:
    """Read a single keypress. Returns 'up', 'down', 'enter', 'esc', or char."""
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\xe0", b"\x00"):          # special key prefix
            ch2 = msvcrt.getch()
            if ch2 == b"H": return "up"
            if ch2 == b"P": return "down"
            if ch2 == b"K": return "left"
            if ch2 == b"M": return "right"
            return ""
        if ch == b"\r":  return "enter"
        if ch == b"\n":  return "enter"
        if ch == b"\x1b": return "esc"
        if ch == b"\x03": return "esc"        # Ctrl+C
        try:
            return ch.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                rest = sys.stdin.read(2)
                if rest == "[A": return "up"
                if rest == "[B": return "down"
                if rest == "[C": return "right"
                if rest == "[D": return "left"
                return "esc"
            if ch in ("\r", "\n"): return "enter"
            if ch == "\x03":       return "esc"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _ansi(code: str) -> str:
    return f"\033[{code}"


def _cursor_up(n: int):
    if n > 0:
        sys.stdout.write(f"\033[{n}A")
        sys.stdout.flush()


def _clear_below():
    sys.stdout.write("\033[J")
    sys.stdout.flush()


# ─────────────────────────────────────────────
# INPUT HELPERS
# ─────────────────────────────────────────────

def _extract_package_from_url(text: str) -> str:
    """Extract Android package ID from Play Store URL or return text unchanged."""
    import re as _re
    # Standard URL: ?id=com.example.app  or  &id=com.example.app
    m = _re.search(r'[?&]id=([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+)', text)
    if m:
        return m.group(1)
    # Direct path: /details/com.example.app  (some share links)
    m2 = _re.search(r'/details/([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+)', text)
    if m2:
        return m2.group(1)
    return text.strip()


def _push_pkg_history(pkg: str):
    """Keep last-5 unique package IDs in session."""
    hist = _SESSION["pkg_history"]
    if pkg and pkg not in hist:
        hist.insert(0, pkg)
        _SESSION["pkg_history"] = hist[:5]
    _SESSION["last_pkg"] = pkg


def _pkg_prompt(label: str = "Search app", allow_empty: bool = False) -> str:
    """
    Unified app lookup prompt.
    - Type app name → Enter → search Play Store → pick from list
    - Paste package ID (com.x.y) or Play Store URL → Enter → use directly
    - Ctrl+V = paste from Windows clipboard
    - Recent apps shown as hints; Enter alone = last used
    """
    last = _SESSION.get("last_pkg", "")
    hist = _SESSION.get("pkg_history", [])

    if hist:
        hint_pkgs = "  ".join(f"[{i + 1}] {p}" for i, p in enumerate(hist[:3]))
        console.print(f"  [{C_DIM}]recent: {hint_pkgs}[/]")
    if last:
        console.print(f"  [{C_DIM}]Enter = use last: {last}[/]")
    console.print(
        f"  [{C_DIM}]Type app name to search  ·  or paste package ID / Play Store URL[/]"
    )

    def _search(q: str):
        try:
            from core.fetcher import search_apps
            return [
                {"title": r.get("title") or "", "package_id": r.get("package_id") or ""}
                for r in search_apps(q, n_hits=8)
                if r.get("package_id")
            ]
        except Exception:
            return []

    raw = _live_search_input(label, default=last, search_fn=_search)

    if not raw:
        return "" if allow_empty else ""

    # History shortcut: "1"/"2"/"3"
    if raw.isdigit() and 1 <= int(raw) <= len(hist):
        raw = hist[int(raw) - 1]

    return _extract_package_from_url(raw)


def _looks_like_pkg_id(s: str) -> bool:
    """No spaces + has dot → treat as package ID or URL, skip search."""
    return " " not in s and "." in s


def _live_search_input(
    label: str,
    default: str = "",
    search_fn=None,
) -> str:
    """
    Two-phase input:
      Phase 1  — Type / paste query.  Enter submits.
                 Ctrl+V reads Windows clipboard.
                 Backspace deletes. Esc cancels.
      Phase 2  — If text looks like a package ID / URL → use directly.
                 Otherwise search (via search_fn) and show pick list.
                 ↑↓ navigate results, Enter select, Esc go back to Phase 1.

    App name shown bold, package ID dim — on the same line.
    All rendering via sys.stdout.write (no Rich console.print in draw loops).
    """
    # ── non-interactive fallback ──────────────────────────
    if not sys.stdin.isatty():
        try:
            raw = Prompt.ask(
                f"  [{C_BRAND}]{label}[/]",
                default=default,
                show_default=bool(default),
            ).strip()
            return raw or default
        except (KeyboardInterrupt, EOFError):
            return default

    # ── Phase 1: single-line text input ──────────────────
    def _phase1(pre: str = "") -> str:
        """Read a line of text. Returns stripped text or '' on Esc/Ctrl+C."""
        text: list[str] = list(pre)
        prev_len = [0]

        def _draw():
            q = "".join(text)
            prompt = f"  {A_BRAND}{label}:{A_RST} {q}"
            # Pad to clear any previously longer text
            pad = max(0, prev_len[0] - len(q))
            sys.stdout.write(f"\r{prompt}{' ' * pad}")
            sys.stdout.flush()
            prev_len[0] = len(q)

        sys.stdout.write("\n")
        _draw()

        try:
            while True:
                key = _getch()

                if key == "enter":
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    typed = "".join(text).strip()
                    # Empty + default → use default (user just pressed Enter)
                    return typed if typed else default

                elif key in ("esc", "\x03"):  # Esc / Ctrl+C
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    return ""

                elif key in ("\x08", "\x7f"):  # Backspace
                    if text:
                        text.pop()
                        _draw()

                elif key == "\x16":  # Ctrl+V
                    pasted = _clipboard_paste()
                    if pasted:
                        # Replace whole text with pasted content (common paste UX)
                        text.clear()
                        text.extend(list(pasted.strip()))
                        _draw()

                elif len(key) == 1 and key.isprintable():
                    text.append(key)
                    _draw()
                # else: ignore special keys (arrows etc.)

        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return ""

    # ── Phase 2: search results picker ───────────────────
    def _phase2(results: list, query: str) -> str:
        """Arrow-key picker over search results. Returns package_id or query."""
        n = len(results)
        if n == 0:
            return query
        idx = [0]

        # Column widths
        cols_w, _ = term_dims()
        name_w = min(36, (cols_w - 20) // 2)
        pkg_w  = min(40, cols_w - name_w - 12)

        def _draw_block() -> int:
            """Write the result block. Returns number of lines written."""
            buf = [
                f"\n  {A_DIM}Found {n} results for \"{query}\"{A_RST}\n\n"
            ]
            for i, r in enumerate(results):
                name = (r.get("title") or "")[:name_w]
                pkg  = (r.get("package_id") or "")[:pkg_w]
                if i == idx[0]:
                    buf.append(
                        f"  {A_BRAND}❯{A_RST}  \033[1m{name:<{name_w}}\033[0m"
                        f"  {A_DIM}{pkg}{A_RST}\n"
                    )
                else:
                    buf.append(
                        f"     {name:<{name_w}}  {A_DIM}{pkg}{A_RST}\n"
                    )
            buf.append(
                f"\n  {A_DIM}↑↓ navigate   Enter select"
                f"   1-{min(n,9)} quick-pick   Esc new search{A_RST}\n"
            )
            out = "".join(buf)
            sys.stdout.write(out)
            sys.stdout.flush()
            return n + 5   # blank + header + blank + items + blank + hint

        block_lines = _draw_block()

        try:
            while True:
                key = _getch()

                if key == "enter":
                    return results[idx[0]]["package_id"]

                elif key in ("esc", "q", "Q"):
                    # Erase block, go back to Phase 1
                    sys.stdout.write(f"\033[{block_lines}A\033[0J")
                    sys.stdout.flush()
                    return ""   # sentinel → caller re-runs Phase 1

                elif key == "up":
                    idx[0] = (idx[0] - 1) % n

                elif key == "down":
                    idx[0] = (idx[0] + 1) % n

                elif key.isdigit():
                    k = int(key)
                    if 1 <= k <= n:
                        return results[k - 1]["package_id"]
                    continue   # don't redraw for out-of-range digit

                else:
                    continue   # unknown key — no redraw

                # Redraw
                sys.stdout.write(f"\033[{block_lines}A\033[0J")
                sys.stdout.flush()
                block_lines = _draw_block()

        except (KeyboardInterrupt, EOFError):
            return query

    # ── main loop (Phase 1 → Phase 2 → maybe back to Phase 1) ──
    pre = default
    while True:
        q = _phase1(pre)

        if not q:
            return default   # Esc / empty

        # URL or direct package ID → no search needed
        if _looks_like_pkg_id(q) or not search_fn:
            return q

        # Search
        console.print(f"  [{C_DIM}]Searching Play Store for \"{q}\"…[/]")
        try:
            results = search_fn(q)
        except Exception as e:
            console.print(f"  [{C_WARN}]Search failed: {e}[/]")
            return q

        if not results:
            console.print(f"  [{C_DIM}]No results. Using \"{q}\" as-is.[/]")
            return q

        chosen = _phase2(results, q)
        if chosen:           # non-empty → confirmed selection
            return chosen
        # empty → user pressed Esc in Phase 2 → loop back to Phase 1
        pre = q              # pre-fill with what they typed last time


# ─────────────────────────────────────────────
# DISPLAY HELPERS (lean text rows — no Rich Tables)
# ─────────────────────────────────────────────

def _kv(label: str, value: str, w: int = 12):
    """Single key-value row."""
    console.print(f"  [{C_DIM}]{label:<{w}}[/]  {value}")


def _text_row(cols: list[tuple[str, int]], dim_first: bool = False):
    """
    Print one row of fixed-width columns. cols = [(text, width), ...]
    Used instead of Rich Table for clean, zero-overhead rows.
    """
    parts = []
    for i, (text, width) in enumerate(cols):
        cell = str(text)[:width]
        padded = f"{cell:<{width}}"
        if dim_first and i == 0:
            parts.append(f"[{C_DIM}]{padded}[/]")
        else:
            parts.append(padded)
    console.print("  " + "  ".join(parts))


def _table_header(cols: list[tuple[str, int]]):
    """Print column headers matching _text_row widths."""
    parts = [f"[bold {C_BRAND}]{h:<{w}}[/]" for h, w in cols]  # {h:<{w}} not {h:<w}
    console.print("  " + "  ".join(parts))
    console.print(f"  [{C_DIM}]" + "  ".join("─" * w for _, w in cols) + "[/]")


# ─────────────────────────────────────────────
# INFRASTRUCTURE
# ─────────────────────────────────────────────

def _cleanup_cache(max_files: int = 60):
    """Delete oldest cache files when cache grows beyond max_files."""
    try:
        cache_dir = Path(__file__).parent / "cache"
        if not cache_dir.exists():
            return
        files = sorted(cache_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)
        for f in files[: max(0, len(files) - max_files)]:
            try:
                f.unlink()
            except Exception:
                pass
    except Exception:
        pass


# ─────────────────────────────────────────────
# NAVIGATION HELPERS
# ─────────────────────────────────────────────

def arrow_menu(
    options: list[tuple[str, str]],
    title: str = "",
    header_fn=None,
    start: int = 0,
) -> str:
    """
    Full-screen arrow-key menu — zero-flicker.
    Header is drawn ONCE on first render.
    Only menu items are redrawn on navigation (cursor-up + clear-to-end).
    options : list of (label, value) tuples
    Returns the value of the selected option.
    """
    n = len(options)
    idx = max(0, min(start, n - 1))

    # --- raw ANSI menu block (no Rich overhead per keypress) ---
    def _render_block() -> int:
        """Write menu items to stdout. Returns number of lines written."""
        buf = []
        if title:
            buf.append(f"\n  {A_DIM}{title}{A_RST}\n\n")
            extra = 3
        else:
            buf.append("\n")
            extra = 1
        for i, (label, _) in enumerate(options):
            if i == idx:
                buf.append(f"  {A_BRAND}❯{A_RST}  {A_SEL}{label}{A_RST}\n")
            else:
                buf.append(f"     {A_DIM}{label}{A_RST}\n")
        buf.append(f"\n  {A_HINT}↑↓ navigate   Enter select   q quit{A_RST}\n")
        out = "".join(buf)
        sys.stdout.write(out)
        sys.stdout.flush()
        return n + extra + 2   # items + blank(s) + hint line

    # --- first render: clear + static header + menu block ---
    clear()
    if header_fn:
        header_fn()
    menu_lines = _render_block()

    while True:
        key = _getch()
        if key == "up":
            idx = (idx - 1) % n
        elif key == "down":
            idx = (idx + 1) % n
        elif key == "enter":
            return options[idx][1]
        elif key in ("esc", "q", "Q"):
            return options[-1][1]
        elif key.isdigit():
            for _, val in options:
                if val == key:
                    return val
            continue
        else:
            continue
        # nav key: redraw only the menu block (cursor up + erase + redraw)
        sys.stdout.write(f"\033[{menu_lines}A\033[J")
        sys.stdout.flush()
        menu_lines = _render_block()


def action_select(options: list[tuple[str, str]]) -> str:
    """
    Inline arrow-key selector appended below current content.
    All writes batched into single sys.stdout.write() — no Rich overhead.
    options : list of (label, value) tuples
    """
    n = len(options)
    idx = 0
    # total lines this block occupies: blank + options + blank + hint
    BLOCK = n + 3

    def _write_block():
        buf = ["\n"]
        for i, (label, _) in enumerate(options):
            if i == idx:
                buf.append(f"  {A_BRAND}❯{A_RST}  {A_SEL}{label}{A_RST}\n")
            else:
                buf.append(f"     {A_DIM}{label}{A_RST}\n")
        buf.append(f"\n  {A_HINT}↑↓ navigate   Enter select{A_RST}\n")
        sys.stdout.write("".join(buf))
        sys.stdout.flush()

    def _redraw():
        sys.stdout.write(f"\033[{BLOCK}A\033[J")
        _write_block()

    _write_block()
    while True:
        key = _getch()
        if key == "up":
            idx = (idx - 1) % n
            _redraw()
        elif key == "down":
            idx = (idx + 1) % n
            _redraw()
        elif key == "enter":
            sys.stdout.write(f"\033[{BLOCK}A\033[J")
            sys.stdout.flush()
            return options[idx][1]
        elif key in ("esc", "q", "Q"):
            sys.stdout.write(f"\033[{BLOCK}A\033[J")
            sys.stdout.flush()
            return options[-1][1]


# ─────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────

def score_color(s: int) -> str:
    if s >= 75: return C_SCORE_HI
    if s >= 50: return C_SCORE_MD
    return C_SCORE_LO


def score_bar(s: int, width: int = 20) -> str:
    filled = max(0, min(width, int(s / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def draw_hbar(
    labels: list,
    values: list,
    title: str = "",
    bar_width: int | None = None,
    colors: list | None = None,
    show_pct: bool = False,
    fmt: str = "{:.0f}",
    label_width: int | None = None,
):
    """
    Horizontal bar chart using Unicode blocks.
    Auto-sizes bar width to terminal if bar_width is None.
    """
    if not labels or not values:
        return
    cols, _ = term_dims()
    lw = label_width or max(len(str(l)) for l in labels)
    bw = bar_width or min(30, cols - lw - 20)
    max_val = max(float(v) for v in values) or 1

    if title:
        console.print(f"  [{C_DIM}]{title}[/]")

    for i, (label, val) in enumerate(zip(labels, values)):
        pct = float(val) / max_val
        filled = int(pct * bw)
        bar = "█" * filled + "░" * (bw - filled)
        color = colors[i] if colors else score_color(int(pct * 100))
        val_str = fmt.format(val)
        pct_str = f"  {pct*100:.0f}%" if show_pct else ""
        console.print(
            f"  [{C_DIM}]{str(label):>{lw}}[/]  [{color}]{bar}[/]  "
            f"[bold]{val_str}[/]{pct_str}"
        )


def draw_score_gauges(items: list[tuple[str, int, int]], bar_width: int = 20):
    """
    Score gauge bars.
    items : list of (label, value, limit) tuples
    Displays: label  value/limit  ████████░░░░  [OK/WARN]
    """
    for label, val, limit in items:
        pct = val / limit if limit else 0
        filled = int(pct * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        color = C_GOOD if pct <= 1 and val >= int(limit * 0.5) else C_WARN if pct <= 1 else C_BAD
        tag = "[OK]" if pct <= 1 and val >= int(limit * 0.5) else "[WARN]"
        console.print(
            f"  [{C_DIM}]{label:<8}[/]  [{color}]{val:>4}/{limit}[/]  "
            f"[{color}]{bar}[/]  [{color}]{tag}[/]"
        )


def draw_sparkline(values: list, width: int = 20) -> str:
    """
    Compact ASCII sparkline using Unicode block chars.
    values: list of numbers (0-100 or any scale).
    Returns a string exactly `width` chars wide.
    """
    BLOCKS = " ▁▂▃▄▅▆▇█"
    if not values:
        return "─" * width
    src = [float(v) for v in values]
    mn, mx = min(src), max(src)
    span = mx - mn or 1
    # Resample to exactly `width` points
    if len(src) >= width:
        step = len(src) / width
        sampled = [src[int(i * step)] for i in range(width)]
    else:
        # Stretch: repeat each value proportionally
        sampled = []
        for i in range(width):
            idx = int(i / width * len(src))
            sampled.append(src[min(idx, len(src) - 1)])
    normalized = [(v - mn) / span * (len(BLOCKS) - 1) for v in sampled]
    return "".join(BLOCKS[max(0, min(len(BLOCKS) - 1, int(v + 0.5)))] for v in normalized)


def _draw_comparison_grid(rows: list):
    """
    Side-by-side competitor comparison.
    rows: list of comparison row dicts (from compare_metadata result['comparison']).
    Transposes the view — apps are columns, metrics are rows.
    Uses raw ANSI codes so column widths are visually exact.
    """
    if not rows:
        return
    cols_w, _ = term_dims()
    n = min(4, len(rows))
    apps = rows[:n]

    LW = 10
    ACW = max(16, min(22, (cols_w - LW - 4) // n - 2))

    # ── ANSI color helpers (exact visual width) ──
    def _c(ansi_code: str, text: str, pad: int = 0) -> str:
        s = str(text)[:ACW]
        if pad:
            s = f"{s:<{pad}}"
        return f"{ansi_code}{s}{A_RST}"

    def _dim(text: str, pad: int = 0) -> str:
        return _c(A_DIM, text, pad)

    def _brand(text: str, pad: int = 0) -> str:
        return _c(A_BRAND, text, pad)

    def _ansi_score(s: float) -> str:
        if s >= 75: return A_GREEN
        if s >= 50: return A_AMBER
        return A_RED

    def mini_bar(val: float, mx: float = 100, w: int = 6) -> str:
        pct = min(float(val) / max(float(mx), 1), 1.0)
        filled = int(pct * w)
        return "█" * filled + "░" * (w - filled)

    def stars(r: str) -> str:
        try:
            rv = float(str(r).replace("★", "").strip())
            return "★" * int(rv) + "·" * (5 - int(rv))
        except Exception:
            return "·····"

    import re as _re2

    def _row(label: str, cells: list[str]):
        """Print one metric row. cells have ANSI codes; pads by visible width."""
        parts = []
        for cell in cells:
            visible = _re2.sub(r'\033\[[0-9;]*m', '', cell)
            pad = max(0, ACW - len(visible))
            parts.append(cell + " " * pad)
        sys.stdout.write(f"  {A_DIM}{label:<{LW}}{A_RST}  " + "  ".join(parts) + "\n")
        sys.stdout.flush()

    # ── Header ──────────────────────────────────
    hdr_cells = []
    for row in apps:
        is_you = row.get("is_you", False)
        name = (("[YOU] " + row["app"])[:ACW] if is_you else row["app"][:ACW])
        ansi = A_GREEN if is_you else A_BRAND
        hdr_cells.append(f"\033[1m{ansi}{name}{A_RST}")
    _row("", hdr_cells)
    sys.stdout.write(
        f"  {A_DIM}{'─' * LW}  " + "  ".join(["─" * ACW] * n) + f"{A_RST}\n"
    )
    sys.stdout.flush()

    # ── Score ────────────────────────────────────
    score_cells = []
    for row in apps:
        s = int(row["score"])
        b = mini_bar(s)
        ansi = _ansi_score(s)
        score_cells.append(f"{ansi}{b} {s:>3}/100{A_RST}")
    _row("Score", score_cells)

    # ── Rating ───────────────────────────────────
    rat_cells = []
    for row in apps:
        r = str(row.get("rating", "N/A"))
        sc = stars(r)
        rat_cells.append(f"{A_BRAND}{r:<5}{A_RST} {A_DIM}{sc}{A_RST}")
    _row("Rating", rat_cells)

    # ── Installs ─────────────────────────────────
    _row("Installs", [str(row.get("installs", ""))[:ACW] for row in apps])

    # ── Title length ─────────────────────────────
    title_cells = []
    for row in apps:
        tl = int(row.get("title_len", 0))
        b = mini_bar(tl, 30, 5)
        ansi = A_GREEN if tl >= 20 else A_AMBER if tl >= 12 else A_RED
        title_cells.append(f"{ansi}{b} {tl}/30{A_RST}")
    _row("Title", title_cells)

    # ── Short desc ───────────────────────────────
    short_cells = []
    for row in apps:
        sl = int(row.get("short_len", 0))
        b = mini_bar(sl, 80, 5)
        ansi = A_GREEN if sl >= 60 else A_AMBER if sl >= 30 else A_RED
        short_cells.append(f"{ansi}{b} {sl}/80{A_RST}")
    _row("Short", short_cells)

    # ── Long desc ────────────────────────────────
    long_cells = []
    for row in apps:
        ll = int(row.get("long_len", 0))
        b = mini_bar(ll, 4000, 5)
        ansi = A_GREEN if ll >= 2000 else A_AMBER if ll >= 800 else A_RED
        long_cells.append(f"{ansi}{b} {ll:,}{A_RST}")
    _row("Long", long_cells)


def section(title: str):
    console.print()
    console.print(Rule(f" {title} ", style=C_DIM, align="left"))
    console.print()


def pause(msg: str = "Press any key to continue..."):
    console.print(f"\n  [{C_DIM}]{msg}[/]")
    _getch()


def _safe_count(path: Path, pattern: str) -> int:
    try:
        return len(list(path.glob(pattern)))
    except Exception:
        return 0


def success(msg: str):
    console.print(f"\n  [bold {C_ACCENT}][OK][/] {msg}")


def warn(msg: str):
    console.print(f"\n  [bold {C_WARN}][WARN][/] {msg}")


def error(msg: str):
    console.print(f"\n  [bold {C_ERROR}][ERROR][/] {msg}")


def info(msg: str):
    console.print(f"  [{C_DIM}][INFO][/] {msg}")


def clean_text(value: str) -> str:
    replacements = {
        "✓": "OK", "⚠": "Attention:", "—": "-", "→": "->",
        "↑": "up", "↓": "down", "\U0001f525": "HIGH",
        "⚡": "MEDIUM", "\U0001f4cc": "LOW", "•": "-",
        "●": "-", "★": "*", "◆": "-", "✗": "X", "›": ">",
    }
    text = str(value)
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.encode("ascii", "ignore").decode()
    return " ".join(text.split())


def spin(message: str, fn, *args, **kwargs):
    """Run fn() with a spinner. Returns result."""
    result = [None]
    err = [None]

    def worker():
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            err[0] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    with Progress(
        SpinnerColumn(spinner_name="dots", style="#CC785C"),
        TextColumn(f"  [#CC785C]{message}[/]"),
        transient=True,
        console=console,
    ) as prog:
        prog.add_task("", total=None)
        while t.is_alive():
            time.sleep(0.1)

    if err[0]:
        raise err[0]
    return result[0]


# ─────────────────────────────────────────────
# HEADER / SPLASH
# ─────────────────────────────────────────────

_stats_cache: dict | None = None
_stats_cache_ts: float = 0.0
_STATS_TTL = 30.0   # seconds before re-reading


def _get_header_stats() -> dict:
    global _stats_cache, _stats_cache_ts
    now = time.time()
    if _stats_cache is not None and (now - _stats_cache_ts) < _STATS_TTL:
        return _stats_cache

    root = Path(__file__).parent
    try:
        from src.aso_platform.registry import load_source_registry
        sources = load_source_registry()
        approved = sum(
            1 for s in sources.values()
            if s.enabled and s.compliance_status.value == "approved"
        )
        total_sources = len(sources)
    except Exception:
        approved = 7
        total_sources = 8
    try:
        from core.keywords import available_keyword_categories
        categories = len(available_keyword_categories())
    except Exception:
        categories = 18
    reports = _safe_count(root / "reports", "*.json")
    _stats_cache = {
        "sources": approved,
        "total_sources": total_sources,
        "categories": categories,
        "reports": reports,
    }
    _stats_cache_ts = now
    return _stats_cache


def header(subtitle: str = ""):
    clear()
    stats = _get_header_stats()
    cols, _ = term_dims()
    console.print(
        f"  [bold {C_BRAND}]{APP_NAME}[/]  [{C_DIM}]"
        f"{stats['sources']}/{stats['total_sources']} sources  "
        f"{stats['categories']} categories  "
        f"{stats['reports']} reports[/]"
    )
    console.print(Rule(style=C_DIM))
    if subtitle:
        console.print(f"  [{C_BRAND}]{subtitle}[/]")
        console.print()


def splash():
    clear()
    cols, lines = term_dims()
    pad = max(1, (lines - 10) // 3)
    sys.stdout.write("\n" * pad)
    sys.stdout.write(
        f"  {A_BRAND}{APP_NAME}{A_RST}  "
        f"{A_DIM}terminal intelligence for mobile app growth{A_RST}\n\n"
        f"  {A_DIM}Analyze listings  ·  Discover keywords  "
        f"·  Benchmark competitors  ·  Export evidence{A_RST}\n"
        f"  {A_DIM}free/legal sources only  "
        f"·  no API keys required  ·  no hidden fees{A_RST}\n\n"
        f"  {A_HINT}Press Enter to launch...{A_RST}"
    )
    sys.stdout.flush()
    input()


# ─────────────────────────────────────────────
# MAIN MENU (arrow-key)
# ─────────────────────────────────────────────

_MENU_OPTIONS = [
    ("1  App Inspector        Fetch live app data by package ID",        "1"),
    ("2  Keyword Research     Discover keywords via seeds + taxonomy",   "2"),
    ("3  Competitor Analysis  Compare metadata against competitors",     "3"),
    ("4  Metadata Analyzer    Score title, short & long description",    "4"),
    ("5  Keyword Gap          Find keywords competitors use that you don't", "5"),
    ("6  Google Trends        Trend signals  (disabled by policy)",      "6"),
    ("7  Review Miner         NLP keyword mining from real user reviews","7"),
    ("8  Saved Reports        Browse and view previous analyses",        "8"),
    ("9  Keyword Rank         Check where an app ranks for a keyword",   "9"),
    ("A  iOS Inspector        Analyze App Store listings (iTunes API)",  "A"),
    ("B  Watch List           Track app changes over time",              "B"),
    ("0  Exit",                                                          "0"),
]


def main_menu():
    def _hdr():
        # Uses cached stats — no file I/O on each menu open
        stats = _get_header_stats()
        # Raw ANSI for speed; Rich Rule rendered via console for the separator
        sys.stdout.write(
            f"  {A_BRAND}{APP_NAME}{A_RST}  "
            f"{A_DIM}{stats['sources']}/{stats['total_sources']} sources  "
            f"{stats['categories']} categories  "
            f"{stats['reports']} reports{A_RST}\n"
        )
        sys.stdout.flush()
        console.print(Rule(style=C_DIM))

    while True:
        choice = arrow_menu(_MENU_OPTIONS, header_fn=_hdr)

        if choice == "0":
            clear()
            console.print(f"\n  [{C_DIM}]Session closed.[/]\n")
            sys.exit(0)
        elif choice == "1": screen_app_inspector()
        elif choice == "2": screen_keyword_research()
        elif choice == "3": screen_competitor_analysis()
        elif choice == "4": screen_metadata_analyzer()
        elif choice == "5": screen_keyword_gap()
        elif choice == "6": screen_google_trends()
        elif choice == "7": screen_review_miner()
        elif choice == "8": screen_saved_reports()
        elif choice == "9": screen_keyword_rank()
        elif choice == "A": screen_ios_inspector()
        elif choice == "B": screen_watchlist()


# ─────────────────────────────────────────────
# SCREEN 1 — APP INSPECTOR
# ─────────────────────────────────────────────

def screen_app_inspector():
    header("App Inspector")
    console.print(f"  [{C_DIM}]Paste a package ID (com.example.app) or Play Store URL.[/]")
    console.print()

    package = _pkg_prompt("Package ID")
    if not package:
        return

    from core.fetcher import validate_package_id, fetch_app_details
    valid, pkg_err = validate_package_id(package)
    if not valid:
        error(pkg_err)
        pause()
        return

    try:
        data = spin(f"Fetching {package}...", fetch_app_details, package)
    except Exception as e:
        error(f"Could not fetch app: {e}")
        pause()
        return

    # Save to session state
    _push_pkg_history(package)
    _SESSION["last_seeds"] = data.get("title", "")   # seed reviews/keywords with app name

    console.print()
    source_note = "cached" if data.get("_from_cache") else "live"
    score_val = data.get("score") or 0.0

    if score_val > 0:
        stars_filled = int(score_val)
        star_str = "★" * stars_filled + "·" * (5 - stars_filled)
        ratings_count = data.get("ratings") or 0
        rating_display = (
            f"[{C_BRAND}]{score_val:.1f}/5.0[/]  [{C_WARN}]{star_str}[/]  "
            f"[{C_DIM}]({ratings_count:,} ratings)[/]"
        )
    else:
        rating_display = f"[{C_DIM}]N/A (not yet rated)[/]"

    price_str = "Free" if data.get("free", True) else f"${data.get('price', 0):.2f}"
    if data.get("contains_ads"):
        price_str += "  · ads"

    # ── Compact 2-column KV layout ──────────────────────────
    cols_w, _ = term_dims()
    half = max(30, cols_w // 2 - 4)

    def _kv2(l1, v1, l2="", v2="", lw=10):
        left = f"  [{C_DIM}]{l1:<{lw}}[/]  {v1}"
        if l2:
            right = f"  [{C_DIM}]{l2:<{lw}}[/]  {v2}"
            console.print(f"{left:<{half}}{right}")
        else:
            console.print(left)

    _kv2("Title",     f"[bold white]{data['title']}[/]  [{C_DIM}]({source_note})[/]")
    _kv2("Developer", data.get("developer", ""), "Category", data.get("category", ""))
    _kv2("Rating",    rating_display)
    _kv2("Installs",  data.get("installs", ""), "Price", price_str)
    _kv2("Version",
         f"{data.get('version', 'N/A')} · Android {data.get('android_version', 'N/A')}+",
         "Updated", str(data.get("updated", "N/A")))

    # ── Compact rating histogram ────────────────────────────
    hist = data.get("histogram", {})
    # Also accept list format (defensive)
    if isinstance(hist, list) and len(hist) >= 5:
        hist = {str(i + 1): hist[i] for i in range(5)}
    if hist and any(hist.values()):
        section("Rating Distribution")
        total = max(sum(int(v) for v in hist.values()), 1)
        cols_w2, _ = term_dims()
        bw = min(20, cols_w2 - 32)
        for stars in range(5, 0, -1):
            count = int(hist.get(str(stars), hist.get(stars, 0)))
            pct = count / total * 100
            filled = int(pct / 100 * bw)
            bar = "█" * filled + "░" * (bw - filled)
            color = C_GOOD if stars >= 4 else C_WARN if stars == 3 else C_BAD
            console.print(
                f"  [{color}]{stars}★[/]  [{color}]{bar}[/]  "
                f"[bold]{pct:>4.0f}%[/]  [{C_DIM}]({count:,})[/]"
            )

    # ── Metadata score gauges ───────────────────────────────
    section("Metadata Snapshot")
    title_len = len(data["title"])
    short_len = len(data.get("summary", ""))
    long_len  = len(data.get("description", ""))
    draw_score_gauges([
        ("Title",  title_len,  30),
        ("Short",  short_len,  80),
        ("Long",   long_len,   4000),
    ])
    console.print()
    console.print(f"  [{C_DIM}]Title:[/]  [italic]{data['title']}[/]")
    if data.get("summary"):
        cols, _ = term_dims()
        console.print(f"  [{C_DIM}]Short:[/]  [italic]{data['summary'][:cols-12]}[/]")

    from core.reporter import save_report
    path = save_report("app_inspector", data)
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")

    from core.watchlist import is_watched as _is_watched
    already_watching = _is_watched(package)
    watch_label = (
        "Watching  ✓  (refresh snapshot)" if already_watching
        else "Watch this app  (track changes)"
    )

    console.print()
    next_action = action_select([
        ("Full metadata analysis",     "M"),
        ("Mine reviews for insights",  "R"),
        ("Find similar apps",          "S"),
        (watch_label,                  "W"),
        ("Back to main menu",          "B"),
    ])

    if next_action == "M":
        _run_metadata_analysis(data)
    elif next_action == "R":
        _run_review_miner(data["package_id"], data["title"])
    elif next_action == "S":
        _run_similar_apps(package, data["title"])
    elif next_action == "W":
        from core.watchlist import add_app
        add_app(package, data, platform="android")
        success(f"{'Snapshot saved' if already_watching else 'Added to Watch List'}: {data.get('title','')[:40]}")
        time.sleep(1)


# ─────────────────────────────────────────────
# SCREEN 2 — KEYWORD RESEARCH
# ─────────────────────────────────────────────

def screen_keyword_research():
    header("Keyword Research")
    console.print(
        f"  [{C_DIM}]Approved free/legal sources only. "
        f"Local estimates when live sources are disabled.[/]"
    )
    console.print()

    last_seeds = _SESSION.get("last_seeds", "")
    category_input = Prompt.ask(
        f"  [{C_BRAND}]Category[/] [{C_DIM}](optional, e.g. tools, finance, health)[/]",
        default="", show_default=False,
    ).strip()
    raw_input = Prompt.ask(
        f"  [{C_BRAND}]Seed keywords[/] [{C_DIM}](optional, words or app name)[/]",
        default=last_seeds if last_seeds else "", show_default=bool(last_seeds),
    ).strip()
    if not raw_input and not category_input:
        return
    _SESSION["last_seeds"] = raw_input

    from src.aso_platform.services.keyword_discovery import KeywordDiscoveryService
    report = KeywordDiscoveryService().discover(
        seed_text=raw_input,
        category=category_input,
        lang="en",
        country="us",
        limit=40,
    ).to_dict()

    input_review    = report["input_review"]
    category_review = report["category"]
    seed_sources    = report["seed_sources"]
    combined_seeds  = list(seed_sources.keys())

    section("Input Review")
    if category_input:
        console.print(
            f"  [{C_DIM}]category[/]     {category_review['category'] or 'not matched'}"
        )
    if raw_input:
        console.print(
            f"  [{C_DIM}]quality[/]      "
            f"{input_review['quality_label'].upper()} ({input_review['quality_score']}/100)"
        )
    for c in input_review["corrections"][:3]:
        console.print(f"  [{C_DIM}]correction[/]   {c['from']} -> {c['to']}")
    lq = report["request_context"].get("live_search_queries", [])
    if lq:
        console.print(
            f"  [{C_DIM}]live search[/]  {len(lq)} queries  ·  "
            f"{report['request_context'].get('live_suggestions', 0)} suggestions"
        )
    console.print(f"  [{C_DIM}]policy[/]       Google Trends disabled by compliance policy")

    for msg in category_review["warnings"]:
        warn(msg)
    for msg in input_review["warnings"]:
        warn(msg)
    for item in report["warnings"]:
        if item.get("severity") == "info":
            info(item.get("message", ""))
        elif item.get("severity") == "warning":
            warn(item.get("message", ""))

    if not combined_seeds:
        pause()
        return

    policy_warnings = [
        "Play Store autocomplete not used until source policy is approved."
    ]
    try:
        from src.aso_platform.registry import ensure_source_approved, get_source
        ensure_source_approved(get_source("google_trends_public"))
        from core.keywords import get_google_trends
        trend_data = spin("Fetching Google Trends...", get_google_trends, [i["keyword"] for i in report["keywords"]][:10])
    except Exception as e:
        trend_data = {
            "data": {}, "related_queries": [], "warnings": [str(e)],
            "source_status": "disabled_by_policy",
        }
        policy_warnings.append(f"Google Trends skipped: {e}")

    from core.keywords import score_keywords
    scored = score_keywords(report["keywords"], trend_data)
    report["keywords"] = scored

    _display_keyword_table(scored, trend_data)

    # ── Score distribution chart ────────────────────────────
    section("Score Distribution")
    buckets = {"70-100": 0, "40-70": 0, "0-40": 0}
    for kw in scored:
        s = kw["composite_score"]
        if s >= 70:   buckets["70-100"] += 1
        elif s >= 40: buckets["40-70"]  += 1
        else:         buckets["0-40"]   += 1

    draw_hbar(
        list(buckets.keys()),
        list(buckets.values()),
        colors=[C_GOOD, C_WARN, C_BAD],
    )

    # ── Source mix chart ────────────────────────────────────
    src_counts: dict = {}
    conf_counts: dict = {}
    for kw in scored:
        s = kw.get("source", "unknown")
        src_counts[s] = src_counts.get(s, 0) + 1
        c = kw.get("confidence", "low")
        conf_counts[c] = conf_counts.get(c, 0) + 1

    section("Source & Confidence Mix")
    console.print(f"  [{C_DIM}]sources[/]")
    draw_hbar(
        [clean_text(k)[:20] for k in src_counts],
        list(src_counts.values()),
        label_width=20,
    )
    console.print()
    console.print(f"  [{C_DIM}]confidence[/]")
    draw_hbar(
        list(conf_counts.keys()),
        list(conf_counts.values()),
        colors=[C_GOOD if k == "high" else C_WARN if k == "medium" else C_BAD
                for k in conf_counts],
        label_width=20,
    )

    related = trend_data.get("related_queries", [])
    if related:
        section("Related Queries")
        for i, q in enumerate(related[:8], 1):
            console.print(f"  [{C_BRAND}]{i:2}.[/] {q}")

    from core.reporter import save_report
    save_data = {
        "seed": combined_seeds[0] if combined_seeds else raw_input,
        "category": category_review,
        "raw_input": raw_input,
        "input_review": input_review,
        "seed_sources": seed_sources,
        "request_context": report["request_context"],
        "keywords_analyzed": len(scored),
        "scored_keywords": scored,
        "trend_data": trend_data,
        "related_queries": related,
        "warnings": policy_warnings + [i.get("message", "") for i in report["warnings"]],
        "sources": {
            "normalized_input": "user provided",
            "category_seed": "local curated category taxonomy",
            "local_variant": "local deterministic expansion",
            "approved_public_suggestion": "approved public Play Store search enrichment",
            "google_trends_public": trend_data.get("source_status", "disabled_by_policy"),
        },
        "generated_at": datetime.now().isoformat(),
    }
    path = save_report("keyword_research", save_data)
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")
    pause()


def _display_keyword_table(scored: list, trend_data: dict):
    section("Keyword Opportunities")
    _, h = term_dims()
    max_rows = max(5, h - 18)

    # Header
    _table_header([
        ("#", 3), ("Keyword", 26), ("Score", 12), ("Trend", 5),
        ("Priority", 8), ("Conf", 6),
    ])

    shown = scored[:max_rows]
    for i, kw in enumerate(shown, 1):
        trend_int = kw.get("trend_interest", 0)
        trend_str = str(trend_int) if trend_int else "-"
        sc        = kw["composite_score"]
        bar       = score_bar(min(int(sc), 100), 8)
        color     = score_color(min(int(sc * 0.8), 100))
        prio      = clean_text(kw.get("priority", ""))
        conf      = kw.get("confidence", "low")
        console.print(
            f"  [{C_DIM}]{i:>3}[/]  "
            f"[bold white]{kw['keyword']:<26.26}[/]  "
            f"[{color}]{bar}[/] [{color}]{sc:>3.0f}[/]  "
            f"[{C_DIM}]{trend_str:>5}[/]  "
            f"{prio:<8}  [{C_DIM}]{conf:<6}[/]"
        )

    if len(scored) > max_rows:
        console.print(
            f"\n  [{C_DIM}]... and {len(scored) - max_rows} more (saved to report)[/]"
        )


# ─────────────────────────────────────────────
# SCREEN 3 — COMPETITOR ANALYSIS
# ─────────────────────────────────────────────

def screen_competitor_analysis():
    header("Competitor Analysis")
    console.print(
        f"  [{C_DIM}]Optionally enter your own package ID, then search for competitors.[/]"
    )
    console.print()

    your_pkg = _pkg_prompt("Your app (optional — Enter to skip)", allow_empty=True)
    _SESSION["last_query"] = _SESSION.get("last_query", "")
    last_q = _SESSION["last_query"]

    console.print()
    query = Prompt.ask(
        f"  [{C_BRAND}]Search query[/] [{C_DIM}](e.g. file manager)[/]",
        default=last_q if last_q else "", show_default=bool(last_q),
    ).strip()
    if not query:
        return
    _SESSION["last_query"] = query

    try:
        from core.fetcher import search_apps
        results = spin(f"Searching for \"{query}\"...", search_apps, query, n_hits=10)
    except Exception as e:
        error(f"Search failed: {e}")
        pause()
        return

    if not results:
        warn("No results found.")
        pause()
        return

    _, h = term_dims()
    max_rows = max(5, h - 16)

    console.print()
    _table_header([("#", 3), ("App", 26), ("Developer", 20), ("Rating", 7), ("Installs", 10)])
    for i, r in enumerate(results[:max_rows], 1):
        rating = f"{r['score']:.1f}" if r.get("score") else "N/A"
        console.print(
            f"  [{C_DIM}]{i:>3}[/]  "
            f"[bold white]{r['title'][:26]:<26}[/]  "
            f"[{C_DIM}]{r['developer'][:20]:<20}[/]  "
            f"[{C_BRAND}]{rating:>7}[/]  "
            f"{r.get('installs',''):<10}"
        )
    console.print()

    choices_raw = Prompt.ask(
        f"  [{C_BRAND}]Pick apps to compare[/] [{C_DIM}](e.g. 1,3,5 — Enter for top 3)[/]",
        default="", show_default=False,
    ).strip()
    indices = (
        [int(x.strip()) - 1 for x in choices_raw.split(",") if x.strip().isdigit()]
        if choices_raw else [0, 1, 2]
    )
    selected = [results[i] for i in indices if i < len(results)]

    from core.fetcher import fetch_app_details, validate_package_id
    full_apps = []
    for sel in selected:
        try:
            full_apps.append(
                spin(f"Fetching {sel['title'][:28]}...", fetch_app_details, sel["package_id"])
            )
        except Exception as e:
            warn(f"Could not fetch {sel['title']}: {e}")

    if not full_apps:
        error("Could not fetch any app details.")
        pause()
        return

    reference_app = None
    if your_pkg:
        valid, pkg_err = validate_package_id(your_pkg)
        if valid:
            try:
                reference_app = spin(
                    f"Fetching your app \"{your_pkg}\"...", fetch_app_details, your_pkg
                )
            except Exception as e:
                warn(f"Could not fetch your app: {e}")
        else:
            warn(f"Invalid package ID: {pkg_err}")

    from core.analyzer import compare_metadata
    comparison = (
        compare_metadata(reference_app, full_apps)
        if reference_app
        else compare_metadata(full_apps[0], full_apps[1:])
    )

    section("Metadata Score Comparison")
    rows = comparison["comparison"]

    # ── Side-by-side comparison grid ───────────────────────
    _draw_comparison_grid(rows)

    # ── Score bar chart overview ────────────────────────────
    console.print()
    app_labels = [
        f"[YOU] {r['app'][:16]}" if r.get("is_you") else r["app"][:20]
        for r in rows
    ]
    app_scores = [r["score"] for r in rows]
    draw_hbar(
        app_labels,
        app_scores,
        bar_width=20,
        colors=[C_ACCENT if r.get("is_you") else score_color(r["score"]) for r in rows],
        label_width=20,
        fmt="{:.0f}/100",
    )

    # ── Keyword overlap (quick insight) ────────────────────────
    try:
        from core.keywords import find_keyword_gaps
        if reference_app:
            gaps = find_keyword_gaps(reference_app, full_apps)
        else:
            gaps = find_keyword_gaps(full_apps[0], full_apps[1:])
        top_missed = [g["keyword"] for g in gaps["top_gaps"][:8] if g["type"] != "word" or len(g["keyword"]) > 5][:6]
        if top_missed:
            section("Keyword Opportunities  (phrases competitors use, you don't)")
            console.print("  " + "  ·  ".join(
                f"[{C_WARN}]{kw}[/]" for kw in top_missed
            ))
    except Exception:
        pass

    from core.reporter import save_report
    path = save_report("competitor_analysis", {
        "query": query,
        "comparison": comparison,
        "apps": [a.get("package_id") for a in full_apps],
    })
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")
    pause()


# ─────────────────────────────────────────────
# SCREEN 4 — METADATA ANALYZER
# ─────────────────────────────────────────────

def screen_metadata_analyzer():
    header("Metadata Analyzer")
    _run_metadata_analysis()


def _run_metadata_analysis(prefill: dict = None):
    console.print()
    if prefill:
        title = prefill.get("title", "")
        short = prefill.get("summary", "")
        long_d = prefill.get("description", "")
        console.print(f"  [{C_DIM}]Using fetched app: {title}[/]")
        console.print()
    else:
        console.print(f"  [{C_DIM}]Enter your Play Store metadata below.[/]")
        console.print()
        title = Prompt.ask(f"  [{C_BRAND}]Title[/]").strip()
        short = Prompt.ask(
            f"  [{C_BRAND}]Short Description[/] [{C_DIM}](max 80 chars)[/]"
        ).strip()
        console.print(
            f"  [{C_BRAND}]Long Description[/] "
            f"[{C_DIM}](paste below, type END on new line to finish)[/]:"
        )
        lines = []
        while True:
            line = input("  ")
            if line.strip() == "END":
                break
            lines.append(line)
        long_d = "\n".join(lines)

    from core.analyzer import analyze_metadata
    result = spin("Analyzing...", analyze_metadata, title, short, long_d)
    _display_metadata_report(result)

    from core.reporter import save_report
    result["title_text"] = title
    path = save_report("metadata_analysis", result)
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")
    pause()


def _display_metadata_report(result: dict):
    # ── Overall score gauge ─────────────────────────────────
    section("Overall Score")
    score = result["overall_score"]
    grade = result["grade"]
    color = score_color(score)
    cols, _ = term_dims()
    bw = min(30, cols - 20)
    bar = score_bar(score, bw)
    console.print(
        f"  [{color}]{bar}[/]  [{color}]{score}/100[/]  "
        f"[bold white]Grade: {grade}[/]"
    )

    # ── Section score comparison chart ──────────────────────
    tr = result["title"]
    sr = result["short_description"]
    lr = result["long_description"]
    console.print()
    draw_hbar(
        ["Title", "Short Desc", "Long Desc"],
        [tr["score"], sr["score"], lr["score"]],
        bar_width=20,
        colors=[score_color(tr["score"]), score_color(sr["score"]), score_color(lr["score"])],
        label_width=10,
        fmt="{:.0f}/100",
    )

    # ── Priority fixes ──────────────────────────────────────
    console.print()
    console.print(f"  [bold {C_WARN}]Priority Fixes:[/]")
    for win in result.get("quick_wins", []):
        ic = C_BAD if win["impact"] == "HIGH" else C_WARN if win["impact"] == "MEDIUM" else C_DIM
        console.print(
            f"  [{ic}][{win['impact']}][/]  [{C_BRAND}]{win['area']:<14}[/]  "
            f"{clean_text(win['fix'])}"
        )

    # ── Per-section details ─────────────────────────────────
    section(f"Title  ({tr['score']}/100)")
    console.print(
        f"  [{C_DIM}]length[/]  [{score_color(tr['score'])}]"
        f"{tr['length']}/{tr['limit']} chars  "
        f"{score_bar(tr['score'], 20)}  "
        f"{tr['chars_remaining']} remaining[/]"
    )
    for iss in tr["issues"]:
        console.print(f"  [{C_BAD}][ISSUE][/]  {clean_text(iss)}")
    for sug in tr["suggestions"]:
        c = clean_text(sug)
        console.print(
            f"  [{C_GOOD if any(x in c for x in ('OK','Good','Has')) else C_DIM}]{c}[/]"
        )

    section(f"Short Description  ({sr['score']}/100)")
    console.print(
        f"  [{C_DIM}]length[/]  [{score_color(sr['score'])}]"
        f"{sr['length']}/{sr['limit']} chars  "
        f"{score_bar(sr['score'], 20)}  "
        f"{sr['chars_remaining']} remaining[/]"
    )
    for iss in sr["issues"]:
        console.print(f"  [{C_BAD}][ISSUE][/]  {clean_text(iss)}")
    for sug in sr["suggestions"]:
        c = clean_text(sug)
        console.print(
            f"  [{C_GOOD if any(x in c for x in ('OK','Good','Has')) else C_DIM}]{c}[/]"
        )

    section(f"Long Description  ({lr['score']}/100)")
    console.print(
        f"  [{C_DIM}]length[/]  [{score_color(lr['score'])}]"
        f"{lr['length']}/{lr['limit']} chars  "
        f"{score_bar(lr['score'], 20)}[/]"
    )
    console.print(
        f"  [{C_DIM}]words[/]   {lr['word_count']}  "
        f"[{C_DIM}]top:[/] {', '.join(lr['top_keywords_found'][:6])}"
    )

    # Above-fold
    af = lr.get("above_fold", {})
    if af:
        af_color = C_GOOD if af.get("score", 100) >= 80 else C_WARN if af.get("score", 0) >= 50 else C_BAD
        console.print(
            f"  [{C_DIM}]above-fold[/]  [{af_color}]{af.get('length', 0)}/80 chars  "
            f"{af.get('keyword_count', 0)} keywords[/]"
        )
        if af.get("text"):
            console.print(f"  [{C_DIM}]preview:  \"{af['text'][:72]}...\"[/]")

    # Readability
    rd = lr.get("readability", {})
    if rd and rd.get("sentence_count", 0) > 0:
        rd_color = C_GOOD if rd["score"] >= 80 else C_WARN
        console.print(
            f"  [{C_DIM}]readability[/]  [{rd_color}]{rd['grade']}  "
            f"avg {rd['avg_words_per_sentence']} words/sentence[/]"
        )

    # Keyword density warnings
    density = lr.get("density", {})
    for warn_msg in density.get("stuffing_warnings", []):
        console.print(f"  [{C_BAD}][ISSUE][/]  {clean_text(warn_msg)}")

    for iss in lr["issues"]:
        console.print(f"  [{C_BAD}][ISSUE][/]  {clean_text(iss)}")
    for sug in lr["suggestions"]:
        c = clean_text(sug)
        if any(x in c for x in ("OK", "Good", "Has", "Above")):
            console.print(f"  [{C_GOOD}]{c}[/]")
        else:
            console.print(f"  [{C_DIM}]{c}[/]")

    section("Keyword Consistency")
    ks = result["keyword_strategy"]
    cs_color = score_color(ks["consistency_score"])
    draw_hbar(
        ["Consistency"],
        [ks["consistency_score"]],
        colors=[cs_color],
        bar_width=20,
        fmt="{:.0f}%",
        label_width=11,
    )
    console.print(f"\n  {clean_text(ks['recommendation'])}")
    if ks["title_keywords_missing_from_short"]:
        console.print(
            f"  [{C_WARN}]missing from short:[/]  "
            f"{', '.join(ks['title_keywords_missing_from_short'])}"
        )
    if ks["short_keywords_missing_from_long"]:
        console.print(
            f"  [{C_WARN}]missing from long:[/]   "
            f"{', '.join(ks['short_keywords_missing_from_long'])}"
        )


# ─────────────────────────────────────────────
# SCREEN 5 — KEYWORD GAP
# ─────────────────────────────────────────────

def screen_keyword_gap():
    header("Keyword Gap")
    console.print(f"  [{C_DIM}]Enter YOUR app package ID, then competitor IDs.[/]")
    console.print()

    your_pkg = _pkg_prompt("Your app package ID")
    if not your_pkg:
        return
    comp_raw = Prompt.ask(
        f"  [{C_BRAND}]Competitor package IDs[/] [{C_DIM}](comma separated, or Play Store URLs)[/]"
    ).strip()
    if not comp_raw:
        return
    # Extract package IDs from each comma-separated entry (handles URLs)
    comp_raw = ",".join(_extract_package_from_url(p.strip()) for p in comp_raw.split(",") if p.strip())

    comp_pkgs = [p.strip() for p in comp_raw.split(",") if p.strip()]

    from core.fetcher import fetch_app_details
    try:
        your_app = spin("Fetching your app...", fetch_app_details, your_pkg)
    except Exception as e:
        error(f"Could not fetch your app: {e}")
        pause()
        return

    comp_apps = []
    for pkg in comp_pkgs[:5]:
        try:
            comp_apps.append(spin(f"Fetching {pkg}...", fetch_app_details, pkg))
        except Exception as e:
            warn(f"Skipping {pkg}: {e}")

    if not comp_apps:
        error("Could not fetch any competitor data.")
        pause()
        return

    from core.keywords import find_keyword_gaps
    gaps = spin("Analyzing keyword gaps...", find_keyword_gaps, your_app, comp_apps)

    console.print()
    console.print(
        f"  [{C_BRAND}]{your_app['title']}[/]  "
        f"[{C_DIM}]({gaps['your_keyword_count']} unique keywords in metadata)[/]"
    )

    section(f"Missing Keywords  ({gaps['gaps_found']} gaps found)")
    console.print(
        f"  [{C_DIM}]These keywords appear in competitor metadata but not yours.[/]"
    )
    console.print()

    # ── Gap urgency chart ───────────────────────────────────
    top_gaps = gaps["top_gaps"][:15]
    if top_gaps:
        draw_hbar(
            [g["keyword"][:22] for g in top_gaps],
            [g["used_by_competitors"] for g in top_gaps],
            bar_width=20,
            colors=[
                C_BAD if g["used_by_competitors"] >= 3
                else C_WARN if g["used_by_competitors"] == 2
                else C_DIM
                for g in top_gaps
            ],
            label_width=22,
            fmt="{:.0f} competitors",
        )

    _, h = term_dims()
    max_rows = max(5, h - 18)

    console.print()
    _table_header([("#", 3), ("Keyword / Phrase", 30), ("Type", 8), ("Used by", 7), ("Urgency", 10)])
    for i, gap in enumerate(top_gaps[:max_rows], 1):
        count = gap["used_by_competitors"]
        kw_type = gap.get("type", "word")
        if count >= 3:
            urgency_str = f"[{C_BAD}][CRITICAL][/]"
        elif count >= 2:
            urgency_str = f"[{C_WARN}][HIGH][/]"
        else:
            urgency_str = f"[{C_DIM}][LOW][/]"
        phrase_color = C_WARN if kw_type != "word" else "white"
        console.print(
            f"  [{C_DIM}]{i:>3}[/]  "
            f"[{phrase_color}]{gap['keyword'][:30]:<30}[/]  "
            f"[{C_DIM}]{kw_type:<8}[/]  "
            f"[bold]{count:>7}[/]  "
            f"{urgency_str}"
        )
    if len(top_gaps) > max_rows:
        console.print(f"\n  [{C_DIM}]... and {len(top_gaps) - max_rows} more (saved to report)[/]")

    section("Your Unique Keywords")
    unique = gaps.get("your_unique_keywords", [])
    if unique:
        console.print(
            "  " + "  ·  ".join(f"[{C_ACCENT}]{w}[/]" for w in unique[:20])
        )
    else:
        warn("No unique keywords found. Heavy overlap with competitors.")

    from core.reporter import save_report
    report_data = {"your_app": your_pkg, "competitors": comp_pkgs, "gaps": gaps}
    path = save_report("keyword_gap", report_data)
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")

    # ── CSV export option ───────────────────────────────────
    console.print()
    export_choice = action_select([
        ("Export gaps as CSV  (for spreadsheets)", "csv"),
        ("Done — back to menu",                    "back"),
    ])
    if export_choice == "csv":
        from core.reporter import export_gaps_csv
        csv_path = export_gaps_csv(report_data)
        if csv_path:
            success(f"CSV saved: {csv_path.name}")
        else:
            warn("No gap data to export.")
        pause()


# ─────────────────────────────────────────────
# SCREEN 6 — GOOGLE TRENDS
# ─────────────────────────────────────────────

def screen_google_trends():
    header("Google Trends")
    console.print()
    console.print(
        f"  [{C_WARN}][WARN][/] Google Trends disabled until compliance review completes."
    )
    console.print(f"  [{C_DIM}]       Scores below are local estimates only.[/]")
    console.print()

    raw = Prompt.ask(
        f"  [{C_BRAND}]Keywords[/] [{C_DIM}](max 5, comma separated)[/]"
    ).strip()
    if not raw:
        return

    keywords = [k.strip() for k in raw.split(",") if k.strip()][:5]
    tf_choice = action_select([
        ("7 days",    "1"),
        ("30 days",   "2"),
        ("3 months",  "3"),
        ("12 months", "4"),
    ])
    tf_map = {
        "1": ("now 7-d",    "7 days"),
        "2": ("today 1-m",  "30 days"),
        "3": ("today 3-m",  "3 months"),
        "4": ("today 12-m", "12 months"),
    }
    timeframe, tf_label = tf_map[tf_choice]

    from core.keywords import get_google_trends
    try:
        trend_data = spin(f"Fetching Google Trends ({tf_label})...", get_google_trends, keywords, timeframe)
    except Exception as e:
        error(f"Google Trends error: {e}")
        pause()
        return

    section(f"Trend Scores  ({tf_label})")
    data = trend_data.get("data", {})
    if not data:
        warn("No trend data. Rate-limited — try again in 60s.")
        pause()
        return

    # ── Trend bar chart ─────────────────────────────────────
    chart_labels = []
    chart_values = []
    for kw in keywords:
        info_d = data.get(kw, {})
        avg = info_d.get("avg_interest", 0) if isinstance(info_d, dict) else 0
        chart_labels.append(kw[:20])
        chart_values.append(avg)

    draw_hbar(
        chart_labels,
        chart_values,
        title="Average Interest (0-100)",
        bar_width=24,
        colors=[score_color(int(v)) for v in chart_values],
        label_width=20,
    )
    console.print()

    # ── Full detail rows with sparklines ───────────────────
    _table_header([
        ("Keyword", 22), ("Sparkline", 20), ("Avg", 4), ("Peak", 4), ("Dir", 14),
    ])
    for kw in keywords:
        info_d = data.get(kw, {})
        if isinstance(info_d, dict) and "error" not in info_d:
            raw_dir = info_d.get("trend", "stable")
            dir_color = C_GOOD if "rising" in raw_dir else C_BAD if "falling" in raw_dir else C_DIM
            timeline = info_d.get("timeline", [])
            spark = draw_sparkline(timeline, width=20) if timeline else "─" * 20
            avg = info_d.get("avg_interest", 0)
            peak = info_d.get("peak", 0)
            spark_color = C_GOOD if "rising" in raw_dir else C_BAD if "falling" in raw_dir else C_WARN
            console.print(
                f"  [bold white]{kw[:22]:<22}[/]  "
                f"[{spark_color}]{spark}[/]  "
                f"[{C_BRAND}]{avg:>4}[/]  "
                f"[{C_WARN}]{peak:>4}[/]  "
                f"[{dir_color}]{clean_text(raw_dir)[:14]:<14}[/]"
            )
        else:
            console.print(
                f"  [bold white]{kw[:22]:<22}[/]  "
                f"[{C_DIM}]{'─' * 20}[/]  "
                f"[{C_DIM}]{'--':>4}  {'--':>4}  n/a (policy)[/]"
            )
    console.print(
        f"\n  [{C_DIM}]Activate in config/source_registry.json for real trend data.[/]"
    )

    related = trend_data.get("related_queries", [])
    if related:
        section("Related Queries")
        for q in related[:8]:
            console.print(f"  [{C_ACCENT}]>[/] {q}")

    from core.reporter import save_report
    path = save_report("google_trends", {
        "keywords": keywords, "timeframe": tf_label, "data": trend_data,
    })
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")
    pause()


# ─────────────────────────────────────────────
# SCREEN 7 — REVIEW MINER
# ─────────────────────────────────────────────

def screen_review_miner():
    header("Review Miner")
    console.print(
        f"  [{C_DIM}]Mines real user reviews. Extracts how users describe your app.[/]"
    )
    console.print()

    package = _pkg_prompt("Package ID")
    if not package:
        return
    _push_pkg_history(package)

    title = package
    try:
        from core.fetcher import fetch_app_details
        app_data = spin("Fetching app info...", fetch_app_details, package)
        title = app_data.get("title", package)
    except Exception:
        pass

    _run_review_miner(package, title)


def _run_review_miner(package: str, title: str):
    from core.fetcher import fetch_reviews
    from core.keywords import mine_review_keywords, get_google_trends, score_keywords

    count_choice = action_select([
        ("50 reviews  (fast)",   "50"),
        ("100 reviews (recommended)", "100"),
        ("200 reviews (thorough)", "200"),
    ])
    count = int(count_choice)

    try:
        reviews = spin(
            f"Fetching {count} reviews for {title[:28]}...", fetch_reviews, package, count
        )
    except Exception as e:
        error(f"Could not fetch reviews: {e}")
        pause()
        return

    if not reviews:
        warn("No reviews found.")
        pause()
        return

    mined = spin("Mining keywords...", mine_review_keywords, reviews)

    section(f"Review Stats  ({title[:36]})")
    total = mined["review_count"]
    pos   = mined["positive_count"]
    neg   = mined["negative_count"]
    neu   = total - pos - neg

    # ── Sentiment distribution bar ──────────────────────────
    draw_hbar(
        ["Positive (4-5★)", "Neutral (3★)", "Negative (1-2★)"],
        [pos, neu, neg],
        bar_width=24,
        colors=[C_GOOD, C_WARN, C_BAD],
        label_width=16,
        show_pct=True,
    )

    # ── Positive keywords bar chart ─────────────────────────
    section("What Users Love  (5 star reviews)")
    pos_kws = mined["positive_keywords"][:12]
    if pos_kws:
        max_c = max(k.get("count", 1) for k in pos_kws)
        _, h = term_dims()
        limit = max(5, h // 3)
        draw_hbar(
            [k["keyword"][:18] for k in pos_kws[:limit]],
            [k.get("count", 1) for k in pos_kws[:limit]],
            bar_width=22,
            colors=[C_GOOD] * limit,
            label_width=18,
        )

    # ── Pain points chart ───────────────────────────────────
    section("Pain Points  (1-2 star reviews)")
    neg_kws = mined["negative_keywords"][:8]
    if neg_kws:
        draw_hbar(
            [k["keyword"][:18] for k in neg_kws],
            [k.get("count", 1) for k in neg_kws],
            bar_width=22,
            colors=[C_BAD] * len(neg_kws),
            label_width=18,
        )
    else:
        console.print(f"  [{C_DIM}]No negative keywords found.[/]")

    # ── All keywords table ──────────────────────────────────
    section("All Keywords")
    all_kws = mined["all_keywords"][:15]
    draw_hbar(
        [k["keyword"][:18] for k in all_kws],
        [k.get("count", 1) for k in all_kws],
        bar_width=22,
        label_width=18,
    )

    top_kws = [k["keyword"] for k in mined["all_keywords"][:8]]
    if top_kws:
        console.print()
        check_trends = action_select([
            ("Check Google Trends for top keywords", "yes"),
            ("Skip — save report now",              "no"),
        ])
        if check_trends == "yes":
            try:
                trend_data = spin("Fetching Google Trends...", get_google_trends, top_kws)
                scored = score_keywords(mined["all_keywords"][:20], trend_data)
                _display_keyword_table(scored, trend_data)
            except Exception as e:
                warn(f"Trends unavailable: {e}")

    from core.reporter import save_report
    path = save_report("review_miner", {
        "package": package, "title": title,
        "review_count": count, "mined_data": mined,
    })
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")
    pause()


# ─────────────────────────────────────────────
# SCREEN 8 — SAVED REPORTS
# ─────────────────────────────────────────────

def screen_saved_reports():
    header("Saved Reports")
    from core.reporter import list_reports

    reports = list_reports()
    if not reports:
        warn("No reports saved yet. Run some analyses first.")
        pause()
        return

    _, h = term_dims()
    max_rows = max(5, h - 12)

    console.print(f"  [{C_DIM}]{len(reports)} reports  ·  {(Path(__file__).parent / 'reports').resolve()}[/]")
    console.print()
    _table_header([("#", 3), ("Type", 22), ("App / Seed", 22), ("Created", 17), ("Size", 6)])
    for i, r in enumerate(reports[:max_rows], 1):
        rtype = r["file"].rsplit("_", 2)[0] if "_" in r["file"] else r["file"][:22]
        console.print(
            f"  [{C_DIM}]{i:>3}[/]  "
            f"[{C_BRAND}]{rtype[:22]:<22}[/]  "
            f"[white]{r['app'][:22]:<22}[/]  "
            f"[{C_DIM}]{r['created'][:17]:<17}[/]  "
            f"[{C_DIM}]{r['size']:>6}[/]"
        )
    if len(reports) > max_rows:
        console.print(f"  [{C_DIM}]... and {len(reports) - max_rows} more[/]")

    console.print()
    action = action_select([
        ("Open report",           "open"),
        ("Export keywords as CSV","csv"),
        ("Back to main menu",     "back"),
    ])

    reports_path = Path(__file__).parent / "reports"

    if action == "open":
        # Arrow-key paginated viewer
        idx_raw = Prompt.ask(f"  [{C_BRAND}]Report number[/]").strip()
        try:
            idx = int(idx_raw) - 1
        except ValueError:
            idx = -1
        if 0 <= idx < len(reports):
            path = reports_path / reports[idx]["file"]
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                _view_report(data, reports[idx]["file"])
            except Exception as e:
                error(f"Could not read report: {e}")
                pause()

    elif action == "csv":
        idx_raw = Prompt.ask(f"  [{C_BRAND}]Report number to export[/]").strip()
        try:
            idx = int(idx_raw) - 1
        except ValueError:
            idx = -1
        if 0 <= idx < len(reports):
            path = reports_path / reports[idx]["file"]
            try:
                from core.reporter import export_keywords_csv, export_gaps_csv
                data = json.loads(path.read_text(encoding="utf-8"))
                csv_path = export_keywords_csv(data) or export_gaps_csv({"gaps": data.get("gaps", {})})
                if csv_path:
                    success(f"CSV saved: {csv_path.name}")
                else:
                    warn("No exportable keyword data in this report.")
            except Exception as e:
                error(f"Export failed: {e}")
        pause()


def _view_report(data: dict, filename: str):
    """
    Paginated report viewer. ↑↓ scroll, q quit.
    Shows a readable summary then raw JSON, screen-height pages.
    """
    cols, h = term_dims()
    page_h  = max(5, h - 6)

    # Build human-readable lines first, then JSON
    lines = [f"  [{C_BRAND}]{filename}[/]", ""]

    # Smart summary depending on report type
    if "overall_score" in data:
        lines += [
            f"  [{C_DIM}]Score:[/]  [{score_color(data['overall_score'])}]{data['overall_score']}/100  Grade: {data.get('grade','')}[/]",
            f"  [{C_DIM}]Title:[/]  {data.get('title_text','')[:60]}",
        ]
        for w in data.get("quick_wins", [])[:4]:
            ic = C_BAD if w["impact"] == "HIGH" else C_WARN
            lines.append(f"  [{ic}][{w['impact']}][/]  {w['area']}: {clean_text(w['fix'])[:60]}")
    elif "scored_keywords" in data:
        kws = data["scored_keywords"][:10]
        lines.append(f"  [{C_DIM}]Top keywords ({len(data['scored_keywords'])} total):[/]")
        for kw in kws:
            sc = kw.get("composite_score", 0)
            lines.append(f"  [{score_color(int(sc))}]{score_bar(int(sc),8)}[/]  {kw['keyword']}")
    elif "gaps" in data:
        gaps = data["gaps"].get("top_gaps", [])[:8]
        lines.append(f"  [{C_DIM}]Top keyword gaps:[/]")
        for g in gaps:
            lines.append(f"  [{C_WARN}]{g['keyword']:<30}[/]  [{C_DIM}]{g.get('type','word')}  {g['used_by_competitors']} competitors[/]")
    elif "mined_data" in data:
        md = data["mined_data"]
        lines += [
            f"  [{C_DIM}]Reviews:[/]  {md.get('review_count',0)} total  "
            f"[{C_GOOD}]{md.get('positive_count',0)} positive[/]  "
            f"[{C_BAD}]{md.get('negative_count',0)} negative[/]",
        ]
        for kw in md.get("all_keywords", [])[:6]:
            lines.append(f"  {kw['keyword']}")

    lines += ["", f"  [{C_DIM}]─── raw JSON ──────────────────────────────────────[/]", ""]
    raw = json.dumps(data, indent=2, default=str).splitlines()
    lines += [f"  [{C_DIM}]{l}[/]" for l in raw]

    # Paginator
    total = len(lines)
    offset = 0

    def _render_page():
        clear()
        sys.stdout.write(
            f"{A_DIM}  {filename}   {offset+1}-{min(offset+page_h, total)} of {total} lines"
            f"   ↑↓ scroll   q quit{A_RST}\n\n"
        )
        sys.stdout.flush()
        for line in lines[offset: offset + page_h]:
            console.print(line)
        sys.stdout.write(
            f"\n{A_DIM}  ↑↓ scroll   PgUp/PgDn   q quit{A_RST}\n"
        )
        sys.stdout.flush()

    _render_page()
    while True:
        key = _getch()
        if key in ("q", "Q", "esc"):
            break
        elif key == "down" and offset + page_h < total:
            offset = min(offset + 3, total - page_h)
            _render_page()
        elif key == "up" and offset > 0:
            offset = max(0, offset - 3)
            _render_page()
        elif key == "right":   # page down
            offset = min(offset + page_h, max(0, total - page_h))
            _render_page()
        elif key == "left":    # page up
            offset = max(0, offset - page_h)
            _render_page()


# ─────────────────────────────────────────────
# SCREEN 9 — KEYWORD RANK
# ─────────────────────────────────────────────

def screen_keyword_rank():
    header("Keyword Rank")
    console.print(
        f"  [{C_DIM}]Check where an app appears for one keyword "
        f"in public Play Store search results.[/]"
    )
    console.print()

    keyword = Prompt.ask(f"  [{C_BRAND}]Keyword[/]").strip()
    package = _pkg_prompt("Your app package ID")
    if not keyword or not package:
        warn("Keyword and package ID are required.")
        pause()
        return

    limit_choice = action_select([
        ("Scan top 10",  "10"),
        ("Scan top 20",  "20"),
        ("Scan top 30",  "30"),
        ("Scan top 50",  "50"),
    ])
    country = Prompt.ask(f"  [{C_BRAND}]Country[/]", default="us").strip().lower()
    lang    = Prompt.ask(f"  [{C_BRAND}]Language[/]", default="en").strip().lower()

    try:
        from src.aso_platform.services.keyword_rank import KeywordRankService
        service = KeywordRankService()
        report = spin(
            f"Scanning Play Store for \"{keyword}\" (top {limit_choice})...",
            service.rank,
            keyword, package, lang, country, int(limit_choice), True,
        ).to_dict()
    except Exception as e:
        error(f"Could not check keyword rank: {e}")
        pause()
        return

    section("Rank Result")
    position   = report["target_position"] if report["target_position"] is not None else "Not found"
    confidence = report["confidence"]
    console.print(f"  [{C_DIM}]keyword[/]     [{C_BRAND}]{report['keyword']}[/]")
    console.print(f"  [{C_DIM}]your app[/]    [{C_BRAND}]{report['target_package_id']}[/]")
    console.print(
        f"  [{C_DIM}]position[/]    [bold white]{position} of {limit_choice} scanned[/]"
    )
    console.print(
        f"  [{C_DIM}]confidence[/]  "
        f"[bold white]{confidence['label']} ({confidence['score']})[/]"
    )
    console.print(f"  [{C_DIM}]note[/]        {confidence['rationale']}")

    # ── Position gauge ──────────────────────────────────────
    if isinstance(position, int):
        limit_int = int(limit_choice)
        pct_rank  = max(0, 100 - int(position / limit_int * 100))
        draw_hbar(
            ["Rank Position"],
            [pct_rank],
            bar_width=24,
            colors=[score_color(pct_rank)],
            label_width=13,
            fmt=f"#{position} of {limit_choice}",
        )

    for item in report.get("warnings", []):
        warn(f"{item['code']}: {item['message']}")

    section("Top Results")
    _, h = term_dims()
    max_rows = max(5, h - 18)
    _table_header([("#", 3), ("App", 26), ("Package", 28), ("Rating", 7), ("Installs", 10)])
    for item in report["top_results"][:max_rows]:
        is_you = item["is_target"]
        rating = f"{item['score']:.1f}" if item.get("score") else "N/A"
        you_tag = f" [{C_ACCENT}][YOU][/]" if is_you else ""
        name_color = C_ACCENT if is_you else "white"
        console.print(
            f"  [{C_DIM}]{item['position']:>3}[/]  "
            f"[bold {name_color}]{item['title'][:26]:<26}[/]{you_tag}  "
            f"[{C_DIM}]{item['package_id'][:28]:<28}[/]  "
            f"[{C_BRAND}]{rating:>7}[/]  "
            f"{item.get('installs', ''):<10}"
        )

    from core.reporter import save_report
    path = save_report("keyword_rank", report)
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")
    pause()


# ─────────────────────────────────────────────
# SIMILAR APPS (called from App Inspector)
# ─────────────────────────────────────────────

def _run_similar_apps(package_id: str, title: str):
    """Show apps similar to the given package and optionally compare them."""
    header(f"Similar Apps  —  {title[:40]}")

    from core.fetcher import fetch_similar_apps
    try:
        similar = spin("Finding similar apps...", fetch_similar_apps, package_id)
    except Exception as e:
        error(f"Could not find similar apps: {e}")
        pause()
        return

    if not similar:
        warn("No similar apps found.")
        pause()
        return

    section(f"Apps similar to {title[:36]}  ({len(similar)} found)")
    _, h = term_dims()
    max_rows = max(5, h - 14)
    _table_header([("#", 3), ("App", 28), ("Developer", 20), ("Rating", 7), ("Installs", 10)])
    for i, r in enumerate(similar[:max_rows], 1):
        rating = f"{r['score']:.1f}" if r.get("score") else "N/A"
        console.print(
            f"  [{C_DIM}]{i:>3}[/]  "
            f"[bold white]{(r.get('title') or '')[:28]:<28}[/]  "
            f"[{C_DIM}]{(r.get('developer') or '')[:20]:<20}[/]  "
            f"[{C_BRAND}]{rating:>7}[/]  "
            f"{r.get('installs', ''):<10}"
        )
    if len(similar) > max_rows:
        console.print(f"\n  [{C_DIM}]... and {len(similar) - max_rows} more[/]")

    console.print()
    action = action_select([
        ("Compare top 3 against each other",  "compare"),
        ("Back",                               "back"),
    ])

    if action == "compare":
        from core.fetcher import fetch_app_details
        from core.analyzer import compare_metadata
        full = []
        for app in similar[:3]:
            pkg = app.get("package_id", "")
            if not pkg:
                continue
            try:
                full.append(spin(f"Fetching {app.get('title','')[:28]}...", fetch_app_details, pkg))
            except Exception as e:
                warn(f"Skipping {pkg}: {e}")
        if len(full) >= 2:
            section("Comparison")
            comp = compare_metadata(full[0], full[1:])
            _draw_comparison_grid(comp["comparison"])
    pause()


# ─────────────────────────────────────────────
# SCREEN A — iOS APP INSPECTOR
# ─────────────────────────────────────────────

def screen_ios_inspector():
    header("iOS App Inspector")
    console.print(
        f"  [{C_DIM}]Apple App Store data via iTunes Lookup API  ·  free  ·  no key required[/]"
    )
    console.print()

    # iOS search uses iTunes API, not Play Store
    def _ios_search(q: str) -> list:
        try:
            from core.ios_fetcher import search_ios_apps
            return [
                {"title": r.get("title") or "", "package_id": r.get("bundle_id") or ""}
                for r in search_ios_apps(q, limit=8)
                if r.get("bundle_id")
            ]
        except Exception:
            return []

    last = _SESSION.get("last_pkg", "")
    hist = _SESSION.get("pkg_history", [])
    if hist:
        hint_pkgs = "  ".join(f"[{i+1}] {p}" for i, p in enumerate(hist[:3]))
        console.print(f"  [{C_DIM}]recent: {hint_pkgs}[/]")
    if last:
        console.print(f"  [{C_DIM}]Enter = use last: {last}[/]")
    console.print(
        f"  [{C_DIM}]Type app name to search App Store  ·  or paste bundle ID / App Store URL[/]"
    )

    raw = _live_search_input("iOS App", default=last, search_fn=_ios_search)
    if not raw:
        return

    from core.ios_fetcher import extract_bundle_from_url, fetch_ios_app
    identifier = extract_bundle_from_url(raw)

    try:
        data = spin(f"Fetching {identifier[:40]}...", fetch_ios_app, identifier)
    except Exception as e:
        error(f"Could not fetch app: {e}")
        pause()
        return

    _push_pkg_history(identifier)

    console.print()
    source_note = "cached" if data.get("_from_cache") else "live"
    score_val = data.get("score") or 0.0

    if score_val > 0:
        stars_filled = int(score_val)
        star_str = "★" * stars_filled + "·" * (5 - stars_filled)
        ratings_count = data.get("ratings") or 0
        rating_display = (
            f"[{C_BRAND}]{score_val:.1f}/5.0[/]  [{C_WARN}]{star_str}[/]  "
            f"[{C_DIM}]({ratings_count:,} ratings)[/]"
        )
        cv_score = data.get("current_version_score") or 0.0
        cv_ratings = data.get("current_version_ratings") or 0
        if cv_score > 0 and cv_ratings > 0:
            cv_stars = "★" * int(cv_score) + "·" * (5 - int(cv_score))
            rating_display += (
                f"\n  [{C_DIM}]{'':10}[/]  "
                f"[{C_DIM}]current ver: {cv_score:.1f} {cv_stars}  ({cv_ratings:,})[/]"
            )
    else:
        rating_display = f"[{C_DIM}]N/A (not yet rated)[/]"

    price_str = data.get("formatted_price", "Free") or "Free"

    cols_w, _ = term_dims()
    half = max(30, cols_w // 2 - 4)

    def _kv2(l1: str, v1: str, l2: str = "", v2: str = "", lw: int = 10):
        left = f"  [{C_DIM}]{l1:<{lw}}[/]  {v1}"
        if l2:
            right = f"  [{C_DIM}]{l2:<{lw}}[/]  {v2}"
            console.print(f"{left:<{half}}{right}")
        else:
            console.print(left)

    _kv2("Title",     f"[bold white]{data['title']}[/]  [{C_DIM}]({source_note})[/]")
    _kv2("Developer", data.get("developer", ""),  "Category", data.get("category", ""))
    _kv2("Rating",    rating_display)
    _kv2("Bundle ID", f"[{C_DIM}]{data.get('bundle_id', identifier)}[/]",
         "Price",     price_str)
    _kv2(
        "Version",
        f"{data.get('version', 'N/A')} · iOS {data.get('min_os', 'N/A')}+",
        "Size",
        f"{data.get('size_mb', 0)} MB" if data.get("size_mb") else "N/A",
    )
    _kv2(
        "Updated",
        (data.get("updated", "") or "")[:10],
        "Released",
        (data.get("released", "") or "")[:10],
    )
    if data.get("content_rating"):
        _kv2("Content", data["content_rating"])

    # Metadata snapshot
    section("Metadata Snapshot")
    title_len = len(data.get("title", ""))
    desc_len  = len(data.get("description", ""))
    draw_score_gauges([
        ("Title",  title_len,  30),
        ("Desc",   desc_len,   4000),
    ])
    console.print()
    console.print(f"  [{C_DIM}]Title:[/]  [italic]{data['title']}[/]")
    if data.get("description"):
        cols, _ = term_dims()
        preview = (data["description"] or "")[:cols - 12]
        console.print(f"  [{C_DIM}]Desc:[/]   [italic]{preview}[/]")

    from core.reporter import save_report
    path = save_report("ios_inspector", data)
    _invalidate_stats_cache()
    success(f"Report saved: {path.name}")

    console.print()
    next_action = action_select([
        ("Watch this app  (track changes)", "W"),
        ("Back to main menu",               "B"),
    ])

    if next_action == "W":
        from core.watchlist import add_app
        add_app(
            data.get("bundle_id") or identifier,
            data,
            platform="ios",
        )
        success(f"Added to Watch List: {data.get('title', identifier)[:40]}")
        time.sleep(1)


# ─────────────────────────────────────────────
# SCREEN B — WATCH LIST
# ─────────────────────────────────────────────

def screen_watchlist():
    """Track watched apps, view rating sparklines and metadata change diffs."""
    header("Watch List")
    from core.watchlist import get_all, remove_app, refresh_snapshot, get_delta, get_score_history

    wl = get_all()
    apps = wl.get("apps", {})

    if not apps:
        console.print(f"  [{C_DIM}]No apps being watched yet.[/]")
        console.print()
        console.print(f"  [{C_DIM}]In App Inspector, choose \"Watch this app\" to start tracking changes.[/]")
        console.print(f"  [{C_DIM}]Refresh periodically to build a history of rating and metadata changes.[/]")
        pause()
        return

    section(f"Watched Apps  ({len(apps)} total)")
    items = list(apps.items())

    _table_header([
        ("#", 3), ("App", 26), ("Platform", 8), ("Rating", 7),
        ("Snaps", 5), ("Added", 10),
    ])
    for i, (pkg_id, entry) in enumerate(items, 1):
        snaps = entry.get("snapshots", [])
        last  = snaps[-1] if snaps else {}
        added = (entry.get("added_at", "") or "")[:10]
        rating = f"{last.get('score', 0):.1f}" if last.get("score") else "N/A"
        platform = entry.get("platform", "android")
        plat_color = C_ACCENT if platform == "ios" else C_BRAND
        console.print(
            f"  [{C_DIM}]{i:>3}[/]  "
            f"[bold white]{entry.get('title','')[:26]:<26}[/]  "
            f"[{plat_color}]{platform:<8}[/]  "
            f"[{C_BRAND}]{rating:>7}[/]  "
            f"[{C_DIM}]{len(snaps):>5}[/]  "
            f"[{C_DIM}]{added:<10}[/]"
        )

    # Compact sparkline overview
    section("Rating History Sparklines")
    for pkg_id, entry in items:
        scores = get_score_history(entry)
        if not scores:
            continue
        spark = draw_sparkline(scores, width=min(24, max(4, len(scores) * 2)))
        latest = scores[-1] if scores else 0
        first  = scores[0] if scores else 0
        delta  = latest - first
        d_color = C_GOOD if delta > 0 else C_BAD if delta < 0 else C_DIM
        d_sign  = "+" if delta > 0 else ""
        console.print(
            f"  [{C_DIM}]{entry.get('title','')[:24]:<24}[/]  "
            f"[{C_BRAND}]{spark}[/]  "
            f"[bold]{latest:.1f}[/]  "
            f"[{d_color}]{d_sign}{delta:+.2f}[/]"
        )

    console.print()
    action = action_select([
        ("Refresh all snapshots  (re-fetch live data)",  "refresh"),
        ("View changes for one app",                      "diff"),
        ("Remove an app",                                 "remove"),
        ("Back to main menu",                             "back"),
    ])

    if action == "refresh":
        from core.fetcher import fetch_app_details
        from core.ios_fetcher import fetch_ios_app
        any_fail = False
        for pkg_id, entry in items:
            platform = entry.get("platform", "android")
            try:
                if platform == "ios":
                    data = spin(f"Refreshing {entry.get('title','')[:26]}...", fetch_ios_app, pkg_id)
                else:
                    data = spin(f"Refreshing {entry.get('title','')[:26]}...", fetch_app_details, pkg_id)
                refresh_snapshot(pkg_id, data)
                console.print(f"  [{C_ACCENT}][OK][/]  {entry.get('title','')[:40]}")
            except Exception as e:
                warn(f"Could not refresh {pkg_id}: {e}")
                any_fail = True
        if not any_fail:
            success("All snapshots refreshed.")
        pause()

    elif action == "diff":
        idx_raw = Prompt.ask(f"  [{C_BRAND}]App number[/]").strip()
        try:
            idx = int(idx_raw) - 1
        except ValueError:
            idx = -1
        if 0 <= idx < len(items):
            pkg_id, entry = items[idx]
            delta = get_delta(entry)
            if not delta:
                warn("Need at least 2 snapshots to compare. Refresh again tomorrow.")
            else:
                section(f"Changes  —  {entry.get('title','')[:40]}")
                console.print(
                    f"  [{C_DIM}]period[/]    {delta['first_ts']}  →  {delta['last_ts']}"
                    f"  [{C_DIM}]({delta['snapshots']} snapshots)[/]"
                )
                console.print()

                def _delta_row(label: str, val, positive_good: bool = True, is_float: bool = False):
                    v = float(val) if is_float else int(val)
                    if v == 0:
                        color, sign = C_DIM, " "
                    elif (v > 0) == positive_good:
                        color, sign = C_GOOD, "+"
                    else:
                        color, sign = C_BAD, ""
                    fmt = f"{sign}{v:+.2f}" if is_float else f"{sign}{v:+d}"
                    console.print(f"  [{C_DIM}]{label:<22}[/]  [{color}]{fmt}[/]")

                _delta_row("Rating",            delta["score_delta"],     is_float=True)
                _delta_row("Ratings count",     delta["ratings_delta"])
                _delta_row("Title length",      delta["title_len_delta"])
                _delta_row("Short desc length", delta["short_len_delta"])
                _delta_row("Long desc length",  delta["long_len_delta"])

                if delta.get("version_changed"):
                    console.print(
                        f"  [{C_WARN}]version changed[/]       "
                        f"{delta.get('first_version','?')} → {delta.get('last_version','?')}"
                    )

                # Score history sparkline
                scores = get_score_history(entry)
                if len(scores) >= 2:
                    spark = draw_sparkline(scores, width=min(30, len(scores) * 2))
                    console.print(
                        f"\n  [{C_DIM}]rating history[/]  [{C_BRAND}]{spark}[/]  "
                        f"[{C_DIM}]{scores[0]:.1f} → {scores[-1]:.1f}[/]"
                    )
        pause()

    elif action == "remove":
        idx_raw = Prompt.ask(f"  [{C_BRAND}]App number to remove[/]").strip()
        try:
            idx = int(idx_raw) - 1
        except ValueError:
            idx = -1
        if 0 <= idx < len(items):
            pkg_id, entry = items[idx]
            remove_app(pkg_id)
            success(f"Removed from Watch List: {entry.get('title', pkg_id)[:40]}")
        pause()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def _invalidate_stats_cache():
    """Reset stats cache so next header reads fresh report count."""
    global _stats_cache, _stats_cache_ts
    _stats_cache = None
    _stats_cache_ts = 0.0


if __name__ == "__main__":
    try:
        _init_console()           # UTF-8 + Windows VT + paste support
        _cleanup_cache()          # prune old cache files
        Path(__file__).parent.joinpath("reports").mkdir(exist_ok=True)
        splash()
        main_menu()
    except KeyboardInterrupt:
        clear()
        console.print(f"\n  [{C_DIM}]Interrupted. Goodbye.[/]\n")
        sys.exit(0)
