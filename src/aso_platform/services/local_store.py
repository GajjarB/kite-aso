"""Local JSON/JSONL storage helpers for ASO intelligence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


class LocalDataStore:
    """Small local-first store with inspectable JSON and JSONL files."""

    def __init__(self, root: Path | None = None):
        self.root = root or DATA_ROOT

    def append_event(self, name: str, payload: dict[str, Any]) -> Path:
        path = self.root / f"{name}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": name,
            "recorded_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        return path

    def read_events(self, name: str) -> list[dict[str, Any]]:
        path = self.root / f"{name}.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def read_json(self, relative_path: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.root / relative_path
        if not path.exists():
            return dict(default or {})
        return json.loads(path.read_text(encoding="utf-8"))

    def list_json(self, relative_dir: str) -> list[dict[str, Any]]:
        directory = self.root / relative_dir
        if not directory.exists():
            return []
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]

