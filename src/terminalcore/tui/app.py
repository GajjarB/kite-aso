"""Textual app for TerminalCore."""

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Button, Static

from ..core.adapters.demo_system_adapter import DemoSystemAdapter
from ..core.config.config_store import ConfigStore
from ..core.types import AppConfig
from ..utils.terminal import layout_mode
from .components.app_shell import AppShell
from .components.confirm_modal import ConfirmModal
from .components.footer_help import FooterHelp
from .components.header import HeaderBar
from .components.sidebar import Sidebar
from .components.status_bar import StatusBar
from .screens.dashboard_screen import DashboardScreen
from .screens.aso_screen import (
    AsoCompetitorsScreen,
    AsoKeywordsScreen,
    AsoReportsScreen,
    AsoReviewsScreen,
    AsoSourcesScreen,
    AsoWorkspacesScreen,
)
from .screens.help_screen import HelpScreen
from .screens.logs_screen import LogsScreen
from .screens.projects_screen import ProjectsScreen
from .screens.settings_screen import SettingsScreen
from .screens.tasks_screen import TasksScreen


class TerminalCoreApp(App):
    """Warm, keyboard-first dashboard."""

    CSS = """
    Screen {
        background: #1E1A17;
        color: #F4EFE7;
    }
    #shell {
        layout: vertical;
        height: 100%;
        padding: 1 2 0 2;
        background: #2A241F;
        border: solid #5A4C42;
    }
    #header {
        background: #2A241F;
        color: #F4EFE7;
        border-bottom: solid #5A4C42;
        padding: 0 1 0 1;
        height: 3;
    }
    #body {
        height: 1fr;
        layout: horizontal;
        background: #2A241F;
        border-bottom: solid #5A4C42;
    }
    #sidebar {
        width: 22;
        background: #2A241F;
        border-right: solid #5A4C42;
        padding: 1 1 1 1;
    }
    .sidebar-title {
        color: #8F8175;
        margin-bottom: 1;
    }
    .nav-item {
        color: #C9BDB1;
        padding: 0 1 0 1;
        height: 1;
        margin-bottom: 0;
    }
    .nav-item.active {
        color: #F4EFE7;
        background: #332B25;
        text-style: bold;
    }
    #content-shell {
        width: 1fr;
        background: #2A241F;
    }
    #content-header {
        height: 3;
        color: #F4EFE7;
        text-style: bold;
        border-bottom: solid #5A4C42;
        padding: 0 2 0 2;
        background: #2A241F;
    }
    #content {
        width: 1fr;
        background: #2A241F;
        padding: 1 2;
    }
    #status-bar {
        background: #2A241F;
        color: #C9BDB1;
        padding: 0 1 0 1;
        height: 1;
    }
    #footer-help {
        color: #8F8175;
        padding: 0 1 0 1;
        height: 1;
    }
    .screen {
        height: 100%;
    }
    .card, .panel, .state-card {
        background: #332B25;
        border: round #5A4C42;
        padding: 1 2;
        margin-bottom: 1;
    }
    .stat-row, .panel-row {
        layout: horizontal;
        height: auto;
    }
    .stat-card {
        background: #332B25;
        border: round #5A4C42;
        padding: 1 2;
        width: 1fr;
        margin-right: 1;
        height: auto;
    }
    .stat-label {
        color: #8F8175;
    }
    .stat-value {
        color: #F4EFE7;
        text-style: bold;
    }
    .stat-detail, .panel-copy.muted, .state-body, .detail-copy {
        color: #8F8175;
    }
    .panel-title, .detail-head, .state-title, .modal-title {
        color: #F4EFE7;
        text-style: bold;
        margin-bottom: 1;
    }
    .panel-copy, .modal-body {
        color: #C9BDB1;
        margin-bottom: 1;
    }
    .success-text { color: #7FA66A; }
    .warning-text { color: #D0A24C; }
    .error-text { color: #C7655A; }
    .search-input {
        margin-bottom: 1;
        border: round #5A4C42;
        background: #3B322B;
    }
    .data-table {
        width: 2fr;
        margin-right: 1;
    }
    .details-panel {
        width: 1fr;
    }
    .log-viewer {
        border: round #5A4C42;
        background: #332B25;
    }
    .task-row {
        margin-bottom: 1;
        align: left middle;
    }
    .task-copy {
        width: 1fr;
        margin-right: 1;
    }
    .task-progress {
        width: 40;
    }
    .confirm-modal {
        width: 60;
        height: auto;
        background: #332B25;
        border: round #5A4C42;
        padding: 1 2;
        margin: 8 16;
    }
    .modal-actions {
        height: auto;
        margin-top: 1;
    }
    TerminalCoreApp.compact #sidebar {
        width: 16;
    }
    TerminalCoreApp.stack #body {
        layout: vertical;
    }
    TerminalCoreApp.stack #sidebar {
        width: 100%;
        height: auto;
        border-right: none;
        border-bottom: solid #5A4C42;
    }
    TerminalCoreApp.stack #content-header {
        padding: 0 1 0 1;
    }
    TerminalCoreApp.stack .panel-row,
    TerminalCoreApp.stack .stat-row {
        layout: vertical;
    }
    TerminalCoreApp.stack .data-table,
    TerminalCoreApp.stack .details-panel,
    TerminalCoreApp.stack .task-progress {
        width: 100%;
        margin-right: 0;
    }
    TerminalCoreApp.minimal #sidebar {
        display: none;
    }
    TerminalCoreApp.minimal #shell {
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("enter", "activate_current", "Select"),
        Binding("up,k", "move_up", "Up"),
        Binding("down,j", "move_down", "Down"),
        Binding("left", "previous_section", "Back"),
        Binding("right", "activate_current", "Open"),
        Binding("/", "focus_search", "Search"),
        Binding("question_mark", "show_help", "Help"),
        Binding("r", "refresh_screen", "Refresh"),
        Binding("d", "run_primary", "Run"),
        Binding("l", "open_logs", "Logs"),
        Binding("s", "open_settings", "Settings"),
        Binding("escape", "dismiss_modal", "Back"),
    ]

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.adapter = DemoSystemAdapter()
        self.current_screen = "dashboard"

    def compose(self) -> ComposeResult:
        with AppShell(id="shell"):
            yield HeaderBar(id="header")
            with Container(id="body"):
                yield Sidebar(id="sidebar")
                with Vertical(id="content-shell"):
                    yield Static("Overview", id="content-header")
                    yield Vertical(id="content")
            yield StatusBar("Overview loaded.", id="status-bar")
            yield FooterHelp("↑↓ Navigate   Enter Select   / Search   ? Help   q Quit", id="footer-help")

    def on_mount(self) -> None:
        self._apply_layout_mode(self.size.width)
        self._update_header()
        self._show_screen("dashboard")

    def _apply_layout_mode(self, width: int) -> None:
        mode = layout_mode(width)
        for name in ("wide", "compact", "stack", "minimal"):
            self.set_class(name == mode, name)

    def _update_header(self) -> None:
        status = self.adapter.get_status(self.config)
        self.query_one(HeaderBar).update_content("TerminalCore", status.environment, status.version, status.status)

    def _show_screen(self, name: str) -> None:
        content = self.query_one("#content", Vertical)
        for child in list(content.children):
            child.remove()

        if name == "dashboard":
            content.mount(DashboardScreen(self.config, self.adapter))
            title = "Overview"
            message = "Overview loaded."
        elif name == "projects":
            content.mount(ProjectsScreen(self.config, self.adapter))
            title = "Projects"
            message = "Projects ready. Press / to search."
        elif name == "tasks":
            content.mount(TasksScreen(self.config, self.adapter))
            title = "Tasks"
            message = "Tasks ready. Press d to run the primary action."
        elif name == "logs":
            content.mount(LogsScreen(self.config, self.adapter))
            title = "Logs"
            message = "Logs ready. Press / to filter."
        elif name == "settings":
            content.mount(SettingsScreen(self.config))
            title = "Settings"
            message = "Settings ready."
        elif name == "aso_workspaces":
            content.mount(AsoWorkspacesScreen(classes="screen card"))
            title = "ASO Workspaces"
            message = "ASO workspaces loaded."
        elif name == "aso_keywords":
            content.mount(AsoKeywordsScreen(classes="screen card"))
            title = "ASO Keywords"
            message = "Keyword intelligence commands ready."
        elif name == "aso_competitors":
            content.mount(AsoCompetitorsScreen(classes="screen card"))
            title = "ASO Competitors"
            message = "Competitor workflows ready."
        elif name == "aso_reviews":
            content.mount(AsoReviewsScreen(classes="screen card"))
            title = "ASO Reviews"
            message = "Review intelligence ready."
        elif name == "aso_reports":
            content.mount(AsoReportsScreen(classes="screen card"))
            title = "ASO Reports"
            message = "Report exports ready."
        elif name == "aso_sources":
            content.mount(AsoSourcesScreen(classes="screen card"))
            title = "ASO Sources"
            message = "Source health loaded."
        else:
            content.mount(HelpScreen())
            title = "Help"
            message = "Help loaded."

        self.current_screen = name
        self.query_one(Sidebar).set_current(name)
        self.query_one("#content-header", Static).update(title)
        self.query_one(StatusBar).set_message(message)

    @on(Button.Pressed)
    def handle_button_press(self, event):
        if event.button.id == "reset-config":
            self.push_screen(
                ConfirmModal("Reset config?", "This will restore the default workspace settings."),
                self._handle_reset_response,
            )

    def _handle_reset_response(self, confirmed: bool) -> None:
        if confirmed:
            self.config = ConfigStore().reset()
            self._update_header()
            self._show_screen("settings")
            self.query_one(StatusBar).set_message("Config reset to the default warm profile.")

    def on_resize(self, event) -> None:
        self._apply_layout_mode(event.size.width)

    def action_move_up(self) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.move(-1)
        self.query_one(StatusBar).set_message(f"Selected {sidebar.current}. Press Enter to open.")

    def action_move_down(self) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.move(1)
        self.query_one(StatusBar).set_message(f"Selected {sidebar.current}. Press Enter to open.")

    def action_activate_current(self) -> None:
        self._show_screen(self.query_one(Sidebar).current)

    def action_previous_section(self) -> None:
        self._show_screen("dashboard")

    def action_show_help(self) -> None:
        self._show_screen("help")

    def action_open_logs(self) -> None:
        self._show_screen("logs")

    def action_open_settings(self) -> None:
        self._show_screen("settings")

    def action_run_primary(self) -> None:
        task = self.adapter.run_task(self.config, "Run primary task")
        self.query_one(StatusBar).set_message(f"{task.name} completed successfully.")
        self._show_screen("tasks")

    def action_refresh_screen(self) -> None:
        self._update_header()
        self._show_screen(self.current_screen)

    def action_focus_search(self) -> None:
        inputs = self.query("Input")
        if inputs:
            inputs.first().focus()
            self.query_one(StatusBar).set_message("Search focused.")
        else:
            self.query_one(StatusBar).set_message("No search input on this screen.")

    def action_dismiss_modal(self) -> None:
        if self.screen_stack and len(self.screen_stack) > 1:
            self.pop_screen()
        else:
            self._show_screen("dashboard")


def run_dashboard_app(config: AppConfig) -> None:
    TerminalCoreApp(config).run()
