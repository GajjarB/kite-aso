"""Capability catalog and legal/free readiness audit."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .registry import load_source_registry

DEFAULT_CAPABILITY_PATH = Path(__file__).resolve().parents[2] / "config" / "capability_catalog.json"


@dataclass(frozen=True)
class CapabilityDescriptor:
    id: str
    area: str
    name: str
    status: str
    priority: str
    sources: list[str]
    properties: list[str]
    logic: list[str]
    free_legal_notes: str

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "CapabilityDescriptor":
        return cls(
            id=str(raw["id"]),
            area=str(raw["area"]),
            name=str(raw["name"]),
            status=str(raw["status"]),
            priority=str(raw["priority"]),
            sources=[str(item) for item in raw.get("sources", [])],
            properties=[str(item) for item in raw.get("properties", [])],
            logic=[str(item) for item in raw.get("logic", [])],
            free_legal_notes=str(raw.get("free_legal_notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_capability_catalog(path: Path | None = None) -> list[CapabilityDescriptor]:
    catalog_path = path or DEFAULT_CAPABILITY_PATH
    raw = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    return [CapabilityDescriptor.from_mapping(item) for item in raw.get("capabilities", [])]


def audit_capabilities(
    catalog: list[CapabilityDescriptor] | None = None,
    registry=None,
) -> dict[str, Any]:
    capabilities = catalog or load_capability_catalog()
    sources = registry or load_source_registry()
    rows: list[dict[str, Any]] = []
    summary = {"active": 0, "planned": 0, "blocked": 0, "missing_sources": 0, "legal_ready": 0}

    for capability in capabilities:
        missing = [source for source in capability.sources if source not in sources]
        blocked_sources = []
        for source_id in capability.sources:
            source = sources.get(source_id)
            if source and (not source.enabled or source.compliance_status.value != "approved" or source.cost != "free" or source.auth != "none"):
                blocked_sources.append(source_id)

        source_legal_ready = not missing and not blocked_sources
        legal_ready = source_legal_ready and capability.status != "blocked"
        summary[capability.status] = summary.get(capability.status, 0) + 1
        if missing:
            summary["missing_sources"] += 1
        if legal_ready:
            summary["legal_ready"] += 1

        rows.append(
            {
                **capability.to_dict(),
                "legal_ready": legal_ready,
                "source_legal_ready": source_legal_ready,
                "missing_sources": missing,
                "blocked_sources": blocked_sources,
            }
        )

    return {
        "summary": summary,
        "capabilities": rows,
    }
