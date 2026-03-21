from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

from mneia.tui.bridge import TUIBridge

STYLES_PATH = Path(__file__).parent / "styles.tcss"

SOURCE_COLORS: dict[str, str] = {
    "obsidian": "source-obsidian",
    "gmail": "source-gmail",
    "google-calendar": "source-calendar",
    "google-drive": "source-drive",
    "granola": "source-granola",
    "local-folders": "source-local-folders",
}

SCREEN_NAV: list[tuple[str, str, str]] = [
    ("dashboard", "1 Dashboard", "ctrl+d"),
    ("search", "2 Search", "ctrl+s"),
    ("chat", "3 Chat", ""),
    ("agents", "4 Agents", ""),
    ("connectors", "5 Connectors", ""),
    ("graph", "6 Graph", ""),
    ("settings", "7 Settings", ""),
]


def source_css_class(source: str) -> str:
    return SOURCE_COLORS.get(source, "source-default")


class StatusHeader(Static):
    agent_count: reactive[int] = reactive(0)
    doc_count: reactive[int] = reactive(0)
    daemon_running: reactive[bool] = reactive(False)

    def render(self) -> str:
        now = datetime.now().strftime("%H:%M:%S")
        daemon_indicator = "[green]ON[/]" if self.daemon_running else "[red]OFF[/]"
        return (
            f" mneia  |  daemon: {daemon_indicator}  "
            f"|  agents: {self.agent_count}  "
            f"|  docs: {self.doc_count:,}  "
            f"|  {now}"
        )


class NavItem(Static):
    is_active: reactive[bool] = reactive(False)

    def __init__(self, label: str, screen_name: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.screen_name = screen_name

    def on_click(self) -> None:
        self.post_message(NavSelected(self.screen_name))

    def watch_is_active(self, value: bool) -> None:
        self.set_class(value, "--active")


class NavSelected(Message):
    def __init__(self, screen_name: str) -> None:
        super().__init__()
        self.screen_name = screen_name


class Sidebar(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("mneia", id="sidebar-logo")
        for screen_name, label, _ in SCREEN_NAV:
            yield NavItem(label, screen_name, classes="nav-item")


class CommandSubmitted(Message):
    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class CommandBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static("/", classes="command-prefix")
        yield Input(placeholder="type a command...", id="command-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self.post_message(CommandSubmitted(value))
            event.input.value = ""


class PlaceholderScreen(Static):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(f"{name}\n\nComing soon.", classes="placeholder-screen", **kwargs)


class DashboardPanel(Static):
    content_text: reactive[str] = reactive("Loading...")

    def render(self) -> str:
        return self.content_text


class DashboardView(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("Dashboard", classes="screen-title")
        yield DashboardPanel(id="panel-status", classes="panel")
        yield DashboardPanel(id="panel-memory", classes="panel")
        yield DashboardPanel(id="panel-graph", classes="panel")
        yield DashboardPanel(id="panel-recent", classes="panel")


class MneiaApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "mneia"
    SUB_TITLE = "personal knowledge agent"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+d", "switch_screen('dashboard')", "Dashboard", show=False),
        Binding("ctrl+s", "switch_screen('search')", "Search", show=False),
        Binding("1", "switch_screen_num('dashboard')", show=False),
        Binding("2", "switch_screen_num('search')", show=False),
        Binding("3", "switch_screen_num('chat')", show=False),
        Binding("4", "switch_screen_num('agents')", show=False),
        Binding("5", "switch_screen_num('connectors')", show=False),
        Binding("6", "switch_screen_num('graph')", show=False),
        Binding("7", "switch_screen_num('settings')", show=False),
    ]

    bridge: TUIBridge | None = None
    current_view: reactive[str] = reactive("dashboard")

    def compose(self) -> ComposeResult:
        yield StatusHeader(id="status-header")
        with Horizontal(id="app-layout"):
            yield Sidebar(id="sidebar")
            with Vertical(id="main-content"):
                yield DashboardView(id="view-dashboard")
                yield PlaceholderScreen("Search", id="view-search")
                yield PlaceholderScreen("Chat", id="view-chat")
                yield PlaceholderScreen("Agents", id="view-agents")
                yield PlaceholderScreen("Connectors", id="view-connectors")
                yield PlaceholderScreen("Graph", id="view-graph")
                yield PlaceholderScreen("Settings", id="view-settings")
        yield CommandBar(id="command-bar")

    def on_mount(self) -> None:
        self.bridge = TUIBridge()
        self._show_view("dashboard")
        self.set_interval(5, self._refresh_status_header)
        self.run_worker(self._start_daemon(), exclusive=True, group="daemon")
        self.run_worker(self._refresh_dashboard(), group="refresh")

    async def _start_daemon(self) -> None:
        if self.bridge:
            await self.bridge.start_daemon()
            self._refresh_status_header()

    async def _refresh_dashboard(self) -> None:
        if not self.bridge:
            return

        try:
            stats = await self.bridge.get_stats()
        except Exception:
            stats = {}

        status_panel = self.query_one("#panel-status", DashboardPanel)
        daemon_state = "Running" if (self.bridge.daemon and self.bridge.daemon.running) else "Starting..."
        agent_count = len(self.bridge.daemon.agents) if self.bridge.daemon else 0
        failed = self.bridge.daemon.failed_connectors if self.bridge.daemon else {}

        status_lines = [
            f"  Daemon:  {daemon_state}",
            f"  Agents:  {agent_count}",
        ]
        if failed:
            status_lines.append(f"  Failed:  {len(failed)}")
        status_panel.content_text = "\n".join(status_lines)

        memory_panel = self.query_one("#panel-memory", DashboardPanel)
        total_docs = stats.get("total_documents", 0)
        total_entities = stats.get("total_entities", 0)
        total_assocs = stats.get("total_associations", 0)
        by_source = stats.get("by_source", {})

        mem_lines = [
            f"  Documents:     {total_docs:,}",
            f"  Entities:      {total_entities:,}",
            f"  Associations:  {total_assocs:,}",
        ]
        if by_source:
            mem_lines.append("")
            for src, count in sorted(by_source.items()):
                mem_lines.append(f"  {src}: {count:,}")
        memory_panel.content_text = "\n".join(mem_lines)

        try:
            graph_stats = await self.bridge.get_graph_stats()
        except Exception:
            graph_stats = {}

        graph_panel = self.query_one("#panel-graph", DashboardPanel)
        g_nodes = graph_stats.get("total_nodes", 0)
        g_edges = graph_stats.get("total_edges", 0)
        g_by_type = graph_stats.get("by_type", {})

        graph_lines = [
            f"  Nodes:         {g_nodes:,}",
            f"  Relationships: {g_edges:,}",
        ]
        if g_by_type:
            graph_lines.append("")
            for etype, count in sorted(g_by_type.items()):
                graph_lines.append(f"  {etype}: {count}")
        graph_panel.content_text = "\n".join(graph_lines)

        try:
            recent_docs = await self.bridge.get_recent(limit=5)
        except Exception:
            recent_docs = []

        recent_panel = self.query_one("#panel-recent", DashboardPanel)
        if recent_docs:
            recent_lines = []
            for doc in recent_docs:
                recent_lines.append(f"  [{doc.source}] {doc.title}")
                recent_lines.append(f"  {doc.timestamp[:16]}")
                recent_lines.append("")
            recent_panel.content_text = "\n".join(recent_lines)
        else:
            recent_panel.content_text = "  No documents yet."

    def _refresh_status_header(self) -> None:
        header = self.query_one("#status-header", StatusHeader)
        if self.bridge and self.bridge.daemon:
            header.daemon_running = self.bridge.daemon.running
            header.agent_count = len(self.bridge.daemon.agents)
        try:
            self.run_worker(self._update_doc_count(), group="doc-count")
        except Exception:
            pass

    async def _update_doc_count(self) -> None:
        if not self.bridge:
            return
        try:
            stats = await self.bridge.get_stats()
            header = self.query_one("#status-header", StatusHeader)
            header.doc_count = stats.get("total_documents", 0)
        except Exception:
            pass

    def _show_view(self, name: str) -> None:
        screen_names = [s[0] for s in SCREEN_NAV]
        for sn in screen_names:
            try:
                widget = self.query_one(f"#view-{sn}")
                widget.display = sn == name
            except Exception:
                pass

        try:
            sidebar = self.query_one("#sidebar", Sidebar)
            for nav_item in sidebar.query(NavItem):
                nav_item.is_active = nav_item.screen_name == name
        except Exception:
            pass

        self.current_view = name

    def on_nav_selected(self, message: NavSelected) -> None:
        self._show_view(message.screen_name)
        if message.screen_name == "dashboard":
            self.run_worker(self._refresh_dashboard(), group="refresh")

    def action_switch_screen(self, name: str) -> None:
        self._show_view(name)
        if name == "dashboard":
            self.run_worker(self._refresh_dashboard(), group="refresh")

    def action_switch_screen_num(self, name: str) -> None:
        cmd_input = self.query_one("#command-input", Input)
        if cmd_input.has_focus:
            return
        self._show_view(name)
        if name == "dashboard":
            self.run_worker(self._refresh_dashboard(), group="refresh")

    def on_command_submitted(self, message: CommandSubmitted) -> None:
        command = message.value.lstrip("/").strip()
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""

        if cmd in ("quit", "q", "exit"):
            self.exit()
        elif cmd in ("dashboard", "dash", "home"):
            self._show_view("dashboard")
            self.run_worker(self._refresh_dashboard(), group="refresh")
        elif cmd in ("search", "find"):
            self._show_view("search")
        elif cmd in ("chat", "ask"):
            self._show_view("chat")
        elif cmd in ("agents",):
            self._show_view("agents")
        elif cmd in ("connectors", "conn"):
            self._show_view("connectors")
        elif cmd in ("graph",):
            self._show_view("graph")
        elif cmd in ("settings", "config"):
            self._show_view("settings")
        elif cmd in ("refresh", "r"):
            self.run_worker(self._refresh_dashboard(), group="refresh")

    async def action_quit(self) -> None:
        if self.bridge:
            await self.bridge.stop_daemon()
        self.exit()


def run_tui() -> None:
    app = MneiaApp()
    app.run()
