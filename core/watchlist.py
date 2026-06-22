"""
App Watch List — persistent JSON-backed tracker.
Stores snapshots of app metadata for change detection and trend tracking.
No external dependencies — plain JSON file in reports directory.
"""

import json
from pathlib import Path
from datetime import datetime

_REPORTS_DIR = Path(__file__).parent.parent / "reports"
_WATCHLIST_FILE = _REPORTS_DIR / "watchlist.json"


# ─────────────────────────────────────────────
# INTERNAL I/O
# ─────────────────────────────────────────────

def _load() -> dict:
    _REPORTS_DIR.mkdir(exist_ok=True)
    if not _WATCHLIST_FILE.exists():
        return {"apps": {}, "updated_at": ""}
    try:
        return json.loads(_WATCHLIST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"apps": {}, "updated_at": ""}


def _save(data: dict):
    data["updated_at"] = datetime.now().isoformat()
    _REPORTS_DIR.mkdir(exist_ok=True)
    _WATCHLIST_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str)
    )


def _make_snapshot(app_data: dict) -> dict:
    """Extract trackable fields for one snapshot."""
    return {
        "ts": datetime.now().isoformat(),
        "score": round(float(app_data.get("score") or 0), 2),
        "ratings": int(app_data.get("ratings") or 0),
        "installs": str(
            app_data.get("installs", "")
            or app_data.get("min_installs", "")
            or ""
        ),
        "version": str(app_data.get("version", "") or ""),
        "title_len": len(app_data.get("title", "") or ""),
        "short_len": len(app_data.get("summary", "") or ""),
        "long_len": len(app_data.get("description", "") or ""),
    }


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def add_app(package_id: str, app_data: dict, platform: str = "android"):
    """
    Add an app to the watch list and record its first snapshot.
    If already watched, just adds a new snapshot.
    """
    wl = _load()
    apps = wl.setdefault("apps", {})
    now = datetime.now().isoformat()

    if package_id not in apps:
        apps[package_id] = {
            "platform": platform,
            "title": app_data.get("title", package_id),
            "added_at": now,
            "snapshots": [],
        }

    entry = apps[package_id]
    entry["title"] = app_data.get("title", entry.get("title", package_id))
    entry["snapshots"] = (entry.get("snapshots", []) + [_make_snapshot(app_data)])[-30:]
    _save(wl)


def refresh_snapshot(package_id: str, app_data: dict):
    """Add a new snapshot for an already-watched app (no-op if not watched)."""
    wl = _load()
    if package_id not in wl.get("apps", {}):
        return
    entry = wl["apps"][package_id]
    entry["title"] = app_data.get("title", entry.get("title", package_id))
    entry["snapshots"] = (entry.get("snapshots", []) + [_make_snapshot(app_data)])[-30:]
    _save(wl)


def remove_app(package_id: str):
    """Remove an app from the watch list."""
    wl = _load()
    wl.get("apps", {}).pop(package_id, None)
    _save(wl)


def get_all() -> dict:
    """Return full watchlist dict: {apps: {pkg_id: entry}, updated_at: '...'}"""
    return _load()


def get_app(package_id: str) -> dict | None:
    """Return a single watched app entry, or None if not watched."""
    return _load().get("apps", {}).get(package_id)


def is_watched(package_id: str) -> bool:
    return package_id in _load().get("apps", {})


def get_delta(entry: dict) -> dict:
    """
    Compute change metrics between first and most recent snapshot.
    Returns empty dict if fewer than 2 snapshots available.
    """
    snaps = entry.get("snapshots", [])
    if len(snaps) < 2:
        return {}
    first, last = snaps[0], snaps[-1]

    def _safe_float(v) -> float:
        try:
            return float(v or 0)
        except Exception:
            return 0.0

    def _safe_int(v) -> int:
        try:
            return int(v or 0)
        except Exception:
            return 0

    return {
        "score_delta": round(_safe_float(last["score"]) - _safe_float(first["score"]), 2),
        "ratings_delta": _safe_int(last["ratings"]) - _safe_int(first["ratings"]),
        "version_changed": last.get("version", "") != first.get("version", ""),
        "first_version": first.get("version", ""),
        "last_version": last.get("version", ""),
        "title_len_delta": _safe_int(last["title_len"]) - _safe_int(first["title_len"]),
        "short_len_delta": _safe_int(last["short_len"]) - _safe_int(first["short_len"]),
        "long_len_delta": _safe_int(last["long_len"]) - _safe_int(first["long_len"]),
        "first_ts": first.get("ts", "")[:10],
        "last_ts": last.get("ts", "")[:10],
        "snapshots": len(snaps),
    }


def get_score_history(entry: dict) -> list[float]:
    """Return list of rating scores from all snapshots (for sparkline)."""
    return [
        float(s.get("score") or 0)
        for s in entry.get("snapshots", [])
    ]
