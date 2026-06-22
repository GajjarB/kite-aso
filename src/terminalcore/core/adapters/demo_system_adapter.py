"""Demo adapter implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..types import AppConfig, HealthCheck, HealthReport, LogRecord, ProjectRecord, SystemStatus, TaskRecord


class DemoSystemAdapter:
    """Demo data provider for the CLI and TUI."""

    def get_status(self, config: AppConfig) -> SystemStatus:
        return SystemStatus(
            status="running",
            environment=config.environment,
            version=config.version,
            config_status="valid",
            last_check=datetime.now(UTC).isoformat(),
            active_projects=4,
            active_tasks=6,
        )

    def get_projects(self, config: AppConfig) -> list[ProjectRecord]:
        now = datetime.now(UTC)
        return [
            ProjectRecord("Core Workspace", "healthy", (now - timedelta(minutes=4)).isoformat(), config.environment),
            ProjectRecord("Command Router", "building", (now - timedelta(minutes=18)).isoformat(), config.environment),
            ProjectRecord("Warm Theme Pack", "healthy", (now - timedelta(hours=2)).isoformat(), "staging"),
            ProjectRecord("Logs Service", "attention", (now - timedelta(hours=5)).isoformat(), "production"),
        ]

    def get_tasks(self, config: AppConfig) -> list[TaskRecord]:
        now = datetime.now(UTC)
        return [
            TaskRecord("Sync workspace", "ready", 100, (now - timedelta(minutes=1)).isoformat()),
            TaskRecord("Generate health report", "running", 72, (now - timedelta(minutes=3)).isoformat()),
            TaskRecord("Collect logs", "queued", 0, (now - timedelta(minutes=15)).isoformat()),
            TaskRecord("Nightly snapshot", "healthy", 100, (now - timedelta(hours=8)).isoformat()),
        ]

    def get_logs(self, config: AppConfig, level: str | None = None) -> list[LogRecord]:
        now = datetime.now(UTC)
        rows = [
            LogRecord((now - timedelta(seconds=10)).isoformat(), "info", "Workspace loaded successfully."),
            LogRecord((now - timedelta(seconds=25)).isoformat(), "success", "Health summary refreshed."),
            LogRecord((now - timedelta(minutes=2)).isoformat(), "warning", "Demo mode is enabled for this workspace."),
            LogRecord((now - timedelta(minutes=5)).isoformat(), "error", "One background check missed its target SLA."),
            LogRecord((now - timedelta(minutes=8)).isoformat(), "info", "Sidebar layout recalculated for compact mode."),
        ]
        if level:
            return [item for item in rows if item.level == level.lower()]
        return rows

    def run_task(self, config: AppConfig, task_name: str) -> TaskRecord:
        return TaskRecord(
            name=task_name or "Run primary task",
            status="healthy",
            progress=100,
            last_run=datetime.now(UTC).isoformat(),
        )

    def get_health(self, config: AppConfig) -> HealthReport:
        checks = [
            HealthCheck("Config", "ok", "Config loaded and validated."),
            HealthCheck("Adapter", "ok", "Demo adapter responded successfully."),
            HealthCheck("Logs", "ok", "Recent logs available."),
            HealthCheck("Theme", "ok", f"Theme '{config.theme}' is available."),
        ]
        return HealthReport(checks=checks)

    def update_config(self, config: AppConfig) -> AppConfig:
        return config
