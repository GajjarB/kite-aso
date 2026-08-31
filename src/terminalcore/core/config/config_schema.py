"""Validation logic for TerminalCore config."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...utils.errors import ConfigValidationError
from ..types import AppConfig

VALID_ENVIRONMENTS = {"development", "staging", "production"}
VALID_THEMES = {"kite-warm", "classic-dark", "minimal-light"}

#: Themes renamed after release. Configs written by older versions still carry
#: the old value, so map it forward instead of failing validation.
LEGACY_THEMES = {"claude-warm": "kite-warm"}


def normalize_theme(theme: str) -> str:
    """Fold a legacy theme name onto its current name."""
    cleaned = str(theme or "").strip().lower()
    return LEGACY_THEMES.get(cleaned, cleaned)


def default_config(
    workspace_name: str = "TerminalCore",
    environment: str = "development",
    theme: str = "kite-warm",
    demo_data: bool = True,
    version: str = "1.0.0",
) -> AppConfig:
    return AppConfig(
        workspace_name=workspace_name,
        environment=environment,
        theme=theme,
        demo_data=demo_data,
        created_at=datetime.now(UTC).isoformat(),
        version=version,
    )


def validate_config(raw: dict[str, Any]) -> AppConfig:
    if not isinstance(raw, dict):
        raise ConfigValidationError("Config file is not a valid object.")

    workspace_name = str(raw.get("workspaceName", "") or "").strip()
    if not workspace_name:
        raise ConfigValidationError("Missing required field: workspaceName")

    environment = str(raw.get("environment", "") or "").strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        raise ConfigValidationError("Environment must be development, staging, or production.")

    theme = normalize_theme(raw.get("theme", ""))
    if theme not in VALID_THEMES:
        raise ConfigValidationError("Theme must be kite-warm, classic-dark, or minimal-light.")

    created_at = str(raw.get("createdAt", "") or "").strip()
    if not created_at:
        raise ConfigValidationError("Missing required field: createdAt")

    version = str(raw.get("version", "") or "").strip()
    if not version:
        raise ConfigValidationError("Missing required field: version")

    return AppConfig(
        workspace_name=workspace_name,
        environment=environment,
        theme=theme,
        demo_data=bool(raw.get("demoData", True)),
        created_at=created_at,
        version=version,
    )
