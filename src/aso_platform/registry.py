"""Source registry loading and compliance helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ComplianceStatus, FetchPolicy, SourceDescriptor

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "source_registry.json"


class RegistryError(RuntimeError):
    """Raised when the source registry cannot be loaded or used safely."""


def load_source_registry(path: Path | None = None) -> dict[str, SourceDescriptor]:
    registry_path = path or DEFAULT_REGISTRY_PATH
    raw = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    descriptors: dict[str, SourceDescriptor] = {}
    for item in raw.get("sources", []):
        descriptor = SourceDescriptor(
            source_id=item["source_id"],
            display_name=item["display_name"],
            purpose=item["purpose"],
            cost=item["cost"],
            auth=item["auth"],
            legal_notes=item["legal_notes"],
            compliance_status=ComplianceStatus(item["compliance_status"]),
            enabled=bool(item["enabled"]),
            policy=FetchPolicy(
                rate_limit=item["rate_limit"],
                cache_ttl_minutes=int(item["cache_ttl_minutes"]),
                minimal_collection="Collect only the minimum public data required for analysis.",
                fallback_behavior=item["fallback_behavior"],
            ),
        )
        descriptors[descriptor.source_id] = descriptor
    if not descriptors:
        raise RegistryError(f"No sources were defined in registry: {registry_path}")
    return descriptors


def get_source(source_id: str, registry: dict[str, SourceDescriptor] | None = None) -> SourceDescriptor:
    sources = registry or load_source_registry()
    try:
        return sources[source_id]
    except KeyError as exc:
        raise RegistryError(f"Unknown source id: {source_id}") from exc


def ensure_source_approved(source: SourceDescriptor) -> None:
    if source.cost != "free":
        raise RegistryError(f"Source '{source.source_id}' is not free.")
    if source.auth != "none":
        raise RegistryError(f"Source '{source.source_id}' requires authentication.")
    if not source.enabled or source.compliance_status is not ComplianceStatus.APPROVED:
        raise RegistryError(
            f"Source '{source.source_id}' is not approved for runtime use "
            f"({source.compliance_status.value}, enabled={source.enabled})."
        )
