"""Core typed contracts for TerminalCore."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    workspace_name: str
    environment: str
    theme: str
    demo_data: bool
    created_at: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SystemStatus:
    status: str
    environment: str
    version: str
    config_status: str
    last_check: str
    active_projects: int
    active_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectRecord:
    name: str
    status: str
    updated_at: str
    environment: str


@dataclass(frozen=True)
class TaskRecord:
    name: str
    status: str
    progress: int
    last_run: str


@dataclass(frozen=True)
class LogRecord:
    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class HealthReport:
    checks: list[HealthCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(item.status == "ok" for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [asdict(item) for item in self.checks],
        }
