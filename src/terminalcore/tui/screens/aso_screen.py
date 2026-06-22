"""ASO intelligence screens for the local TerminalCore dashboard."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static

from src.aso_platform.services.intelligence import SourceHealthService
from src.aso_platform.services.workspace import WorkspaceService


class AsoWorkspacesScreen(Vertical):
    def compose(self):
        yield Static("ASO Workspaces", classes="panel-title")
        workspaces = WorkspaceService().list()
        if not workspaces:
            yield Static("No ASO workspaces yet. Create one with `kite workspace init`.", classes="panel-copy muted")
            return
        for workspace in workspaces[:10]:
            yield Static(
                f"{workspace.name}  {workspace.target_package_id}  {workspace.country}/{workspace.lang}  competitors={len(workspace.competitors)}",
                classes="panel-copy",
            )


class AsoKeywordsScreen(Vertical):
    def compose(self):
        yield Static("Keyword Intelligence", classes="panel-title")
        yield Static("Use `kite keywords build`, `kite keywords score`, `kite rank history`, and `kite share-of-voice`.", classes="panel-copy")


class AsoCompetitorsScreen(Vertical):
    def compose(self):
        yield Static("Competitor Intelligence", classes="panel-title")
        yield Static("Use `kite competitors add`, `kite competitors gap`, `kite competitors timeline`, and `kite competitors creatives`.", classes="panel-copy")


class AsoReviewsScreen(Vertical):
    def compose(self):
        yield Static("Review Intelligence", classes="panel-title")
        yield Static("Use `kite reviews analyze` for public review topics, praise, complaints, and rating drivers.", classes="panel-copy")


class AsoReportsScreen(Vertical):
    def compose(self):
        yield Static("Reports", classes="panel-title")
        yield Static("Use `kite reports export` for JSON, CSV, and Markdown workspace reports.", classes="panel-copy")


class AsoSourcesScreen(Vertical):
    def compose(self):
        yield Static("Source Health", classes="panel-title")
        payload = SourceHealthService().health()
        for row in payload["source_health"]:
            status = "ready" if row["legal_ready"] else "blocked"
            yield Static(f"{status.upper():7} {row['source_id']}  {row['policy_status']}", classes="panel-copy")

