"""Adapter contract for TerminalCore systems."""

from __future__ import annotations

from typing import Protocol

from ..types import AppConfig, HealthReport, LogRecord, ProjectRecord, SystemStatus, TaskRecord


class SystemAdapter(Protocol):
    """Generic adapter for any real backend later."""

    def get_status(self, config: AppConfig) -> SystemStatus: ...

    def get_projects(self, config: AppConfig) -> list[ProjectRecord]: ...

    def get_tasks(self, config: AppConfig) -> list[TaskRecord]: ...

    def get_logs(self, config: AppConfig, level: str | None = None) -> list[LogRecord]: ...

    def run_task(self, config: AppConfig, task_name: str) -> TaskRecord: ...

    def get_health(self, config: AppConfig) -> HealthReport: ...

    def update_config(self, config: AppConfig) -> AppConfig: ...
