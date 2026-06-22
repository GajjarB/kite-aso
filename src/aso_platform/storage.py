"""Small append-only history store for local ASO snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_PATH = Path(__file__).resolve().parents[2] / "data" / "rank_history.jsonl"


class HistoryStore:
    """Append-only JSONL store. Keeps v1 free, local, and inspectable."""

    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_HISTORY_PATH

    def append(self, event_type: str, payload: dict[str, Any]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        return self.path

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def query_rank_history(self, keyword: str = "", package_id: str = "") -> list[dict[str, Any]]:
        keyword = keyword.lower().strip()
        package_id = package_id.lower().strip()
        rows: list[dict[str, Any]] = []
        for record in self.read_all():
            payload = record.get("payload", {})
            if keyword and str(payload.get("keyword", "")).lower() != keyword:
                continue
            if package_id and str(payload.get("target_package_id", "")).lower() != package_id:
                continue
            rows.append(record)
        return rows
