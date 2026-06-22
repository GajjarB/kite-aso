"""
Report Generator
Saves full ASO analysis to JSON. Also exports keyword lists as CSV.
"""

import csv
import io
import json
from pathlib import Path
from datetime import datetime

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def save_report(name: str, data: dict) -> Path:
    """Save a named report as timestamped JSON."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{ts}.json"
    path = REPORTS_DIR / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def load_latest_report(name_prefix: str) -> dict | None:
    """Load the most recent report matching a prefix."""
    matches = sorted(REPORTS_DIR.glob(f"{name_prefix}_*.json"), reverse=True)
    if not matches:
        return None
    return json.loads(matches[0].read_text())


def list_reports() -> list:
    """List all saved reports with metadata."""
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            reports.append({
                "file": f.name,
                "size": f"{f.stat().st_size // 1024}KB",
                "created": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "app": data.get("app_id", data.get("package_id", "unknown")),
            })
        except Exception:
            pass
    return reports


def export_keywords_csv(report_data: dict) -> Path | None:
    """
    Export keyword list from any report type as CSV.
    Returns CSV path or None if no keywords found.
    """
    keywords = (
        report_data.get("scored_keywords")
        or report_data.get("keywords")
        or report_data.get("mined_data", {}).get("all_keywords")
        or []
    )
    if not keywords:
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = REPORTS_DIR / f"keywords_{ts}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["keyword", "score", "type", "source", "priority", "confidence",
                      "trend_interest", "count"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for kw in keywords:
            if isinstance(kw, str):
                writer.writerow({"keyword": kw})
            else:
                writer.writerow(kw)

    return csv_path


def export_gaps_csv(gaps_data: dict) -> Path | None:
    """Export keyword gap list as CSV."""
    gaps = gaps_data.get("gaps", {}).get("top_gaps", [])
    if not gaps:
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = REPORTS_DIR / f"keyword_gaps_{ts}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "type", "used_by_competitors"],
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(gaps)

    return csv_path


def format_aso_score(score: int) -> str:
    bars = "█" * (score // 10) + "░" * (10 - score // 10)
    return f"[{bars}] {score}/100"
