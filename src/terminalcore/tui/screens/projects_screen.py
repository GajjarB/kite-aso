"""Projects screen."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from ...core.adapters.demo_system_adapter import DemoSystemAdapter
from ...core.types import AppConfig
from ...utils.format import format_time, human_status
from ..components.empty_state import EmptyState
from ..components.search_input import SearchInput


class ProjectsScreen(Vertical):
    """Project list with search and detail panel."""

    def __init__(self, config: AppConfig, adapter: DemoSystemAdapter):
        super().__init__(classes="screen")
        self.config = config
        self.adapter = adapter
        self.query = ""
        self._search_cache: dict[str, str] = {}

    def compose(self):
        yield SearchInput("Search projects", id="projects-search")
        projects = self._filtered_projects()
        if not projects:
            yield EmptyState("No projects yet", "Create your first project to get started.")
            return
        with Horizontal(classes="panel-row"):
            table = DataTable(id="projects-table", classes="data-table")
            table.cursor_type = "row"
            table.add_columns("Project", "Status", "Updated", "Environment")
            for item in projects:
                table.add_row(item.name, human_status(item.status), format_time(item.updated_at), item.environment.title())
            yield table
            with Vertical(classes="panel card details-panel"):
                selected = projects[0]
                yield Static("Details", classes="panel-title")
                yield Static(selected.name, classes="detail-head")
                yield Static(f"Status      {human_status(selected.status)}", classes="panel-copy")
                yield Static(f"Updated     {format_time(selected.updated_at)}", classes="panel-copy")
                yield Static(f"Environment {selected.environment.title()}", classes="panel-copy")

    def _filtered_projects(self):
        items = self.adapter.get_projects(self.config)
        if not self.query:
            return items
        needle = self.query.lower()

        cache = self._search_cache
        result = []
        for item in items:
            try:
                name_lower = cache[item.name]
            except KeyError:
                name_lower = cache[item.name] = item.name.lower()

            if needle in name_lower:
                result.append(item)
                continue

            try:
                status_lower = cache[item.status]
            except KeyError:
                status_lower = cache[item.status] = item.status.lower()

            if needle in status_lower:
                result.append(item)

        return result

    def on_input_changed(self, event: SearchInput.Changed) -> None:
        self.query = event.value.strip()
        self.refresh(recompose=True)

    def refresh_data(self):
        self.refresh(recompose=True)
        return self
