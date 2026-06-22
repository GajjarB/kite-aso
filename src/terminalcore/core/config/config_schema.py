"""Validation logic for TerminalCore config."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...utils.errors import ConfigValidationError
from ..types import AppConfig

VALID_ENVIRONMENTS = {"development", "staging", "production"}
VALID_THEMES = {"claude-warm", "classic-dark", "minimal-light"}


def default_config(
    workspace_name: str = "TerminalCore",
    environment: str = "development",
    theme: str = "claude-warm",
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

    theme = str(raw.get("theme", "") or "").strip().lower()
    if theme not in VALID_THEMES:
        raise ConfigValidationError("Theme must be claude-warm, classic-dark, or minimal-light.")

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
