"""Read and write TerminalCore config."""

from __future__ import annotations

import json
from pathlib import Path

from ...utils.errors import ConfigValidationError
from ...utils.paths import CONFIG_PATH, ensure_app_dir
from .config_schema import default_config, validate_config
from ..types import AppConfig


class ConfigStore:
    """Simple JSON config storage with schema validation."""

    def __init__(self, path: Path | None = None):
        self.path = path or CONFIG_PATH

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> AppConfig:
        if not self.path.exists():
            raise ConfigValidationError("Config file was not found.")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigValidationError(f"Config file is not valid JSON: {exc.msg}") from exc
        return validate_config(raw)

    def save(self, config: AppConfig) -> AppConfig:
        ensure_app_dir()
        payload = {
            "workspaceName": config.workspace_name,
            "environment": config.environment,
            "theme": config.theme,
            "demoData": config.demo_data,
            "createdAt": config.created_at,
            "version": config.version,
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return config

    def create_default(self, workspace_name: str = "TerminalCore") -> AppConfig:
        config = default_config(workspace_name=workspace_name)
        return self.save(config)

    def update(self, key: str, value: str) -> AppConfig:
        current = self.load()
        payload = current.to_dict()
        if key == "workspaceName":
            payload["workspace_name"] = value
        elif key == "environment":
            payload["environment"] = value.lower()
        elif key == "theme":
            payload["theme"] = value.lower()
        elif key == "demoData":
            payload["demo_data"] = value.lower() in {"1", "true", "yes", "on"}
        else:
            raise ConfigValidationError(f"Unsupported config key: {key}")
        updated = AppConfig(
            workspace_name=payload["workspace_name"],
            environment=payload["environment"],
            theme=payload["theme"],
            demo_data=payload["demo_data"],
            created_at=payload["created_at"],
            version=payload["version"],
        )
        self.save(updated)
        return self.load()

    def reset(self) -> AppConfig:
        config = default_config()
        return self.save(config)
