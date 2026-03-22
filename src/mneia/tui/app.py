from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Static

from mneia.tui.bridge import TUIBridge

STYLES_PATH = Path(__file__).parent / "styles.tcss"

SCREEN_NAV: list[tuple[str, str]] = [
    ("dashboard", "1 Dashboard"),
    ("search", "2 Search"),
    ("chat", "3 Chat"),
    ("agents", "4 Agents"),
    ("connectors", "5 Sources"),
    ("graph", "6 Graph"),
    ("settings", "7 Settings"),
]


class StatusHeader(Static):
    agent_count: reactive[int] = reactive(0)
    doc_count: reactive[int] = reactive(0)
    daemon_running: reactive[bool] = reactive(False)

    def render(self) -> str:
        now = datetime.now().strftime("%H:%M:%S")
        indicator = "[green]ON[/]" if self.daemon_running else "[yellow]starting[/]"
        return (
            f" [bold cyan]mneia[/]  |  daemon: {indicator}  "
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


class CommandSubmitted(Message):
    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class CommandBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static(" mneia > ", classes="command-prefix")
        yield Input(placeholder="type a command or question...", id="command-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self.post_message(CommandSubmitted(value))
            event.input.value = ""


class DashboardPanel(Static):
    content_text: reactive[str] = reactive("Loading...")

    def render(self) -> str:
        return self.content_text


STATE_ICONS = {
    "running": "[green]●[/]",
    "idle": "[yellow]●[/]",
    "error": "[red]●[/]",
    "stopped": "[dim]○[/]",
}


class DashboardView(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("[bold]Dashboard[/]", classes="screen-title")
        with Horizontal(classes="panel-row"):
            yield DashboardPanel(id="panel-status", classes="panel")
            yield DashboardPanel(id="panel-memory", classes="panel")
        with Horizontal(classes="panel-row"):
            yield DashboardPanel(id="panel-graph", classes="panel")
            yield DashboardPanel(id="panel-recent", classes="panel")


class SearchView(Vertical):
    _results: list = []

    def compose(self) -> ComposeResult:
        yield Static("[bold]Search[/]", classes="screen-title")
        yield Input(placeholder="Search your knowledge base...", id="search-input")
        with Horizontal(id="search-layout"):
            yield VerticalScroll(id="search-results")
            yield VerticalScroll(Static("[dim]Type a query and press Enter[/]", id="search-preview"), id="search-preview-pane")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input" and event.value.strip():
            self.run_worker(self._do_search(event.value.strip()))

    async def _do_search(self, query: str) -> None:
        results_container = self.query_one("#search-results", VerticalScroll)
        preview = self.query_one("#search-preview", Static)
        preview.update("[dim]Searching...[/]")
        results_container.remove_children()
        self._results = []

        try:
            docs = await self.app.bridge.search(query, limit=20)
            self._results = docs
            if not docs:
                preview.update("[dim]No results found[/]")
                return
            for i, doc in enumerate(docs):
                snippet = (doc.content[:150].replace("\n", " ") + "...") if doc.content else ""
                ts = str(doc.timestamp)[:10] if doc.timestamp else ""
                label = f"[bold]{doc.title[:60]}[/]\n[cyan][{doc.source}][/] [dim]{ts}[/]\n[dim]{snippet}[/]"
                item = Static(label, classes="search-result-item", id=f"result-{i}")
                item.can_focus = True
                await results_container.mount(item)
            preview.update(f"[dim]{len(docs)} results — click one to preview[/]")
        except Exception as exc:
            preview.update(f"[red]Search error: {exc}[/]")

    def on_static_click(self, event: Static.Click) -> None:
        widget_id = event.widget.id or ""
        if widget_id.startswith("result-"):
            try:
                idx = int(widget_id.split("-")[1])
                if idx < len(self._results):
                    doc = self._results[idx]
                    preview = self.query_one("#search-preview", Static)
                    header = f"[bold]{doc.title}[/]\n[cyan][{doc.source}][/]  [dim]{doc.timestamp}[/]\n{'─' * 40}\n"
                    preview.update(header + (doc.content[:3000] or "[dim]No content[/]"))
            except (ValueError, IndexError):
                pass


class ChatView(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("[bold]Chat[/]", classes="screen-title")
        yield VerticalScroll(id="chat-messages")
        yield Static("", id="thinking-indicator")
        yield Input(placeholder="Ask a question...", id="chat-input")

    def on_mount(self) -> None:
        msgs = self.query_one("#chat-messages", VerticalScroll)
        msgs.mount(Static("[dim]Ask anything about your knowledge base. Press Enter to send.[/]"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input" and event.value.strip():
            question = event.value.strip()
            event.input.value = ""
            self._add_message("You", question, "cyan")
            self.run_worker(self._get_answer(question))

    def _add_message(self, role: str, text: str, color: str = "green") -> None:
        msgs = self.query_one("#chat-messages", VerticalScroll)
        msgs.mount(Static(f"\n[bold {color}]{role}:[/]  {text}"))
        msgs.scroll_end(animate=False)

    async def _get_answer(self, question: str) -> None:
        indicator = self.query_one("#thinking-indicator", Static)
        indicator.update("[dim italic]  Thinking...[/]")
        try:
            result = await self.app.bridge.ask(question)
            indicator.update("")
            answer = result.get("answer", "No answer available.")
            self._add_message("mneia", answer, "green")

            sources = result.get("sources", [])
            if sources:
                msgs = self.query_one("#chat-messages", VerticalScroll)
                source_text = ", ".join(str(s) for s in sources[:5])
                msgs.mount(Static(f"  [dim]Sources: {source_text}[/]"))
        except Exception as exc:
            indicator.update("")
            self._add_message("error", str(exc), "red")


class AgentsView(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("[bold]Agents[/]", classes="screen-title")
        yield Static(id="agents-content")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        panel = self.query_one("#agents-content", Static)
        bridge = self.app.bridge
        if not bridge or not bridge.daemon:
            panel.update("[dim]Daemon not started yet...[/]")
            return

        agents = bridge.daemon.agents or {}
        failed = bridge.daemon.failed_connectors or {}

        lines = [f"[dim]{len(agents)} agents running[/]\n"]
        for name, agent in sorted(agents.items()):
            state = agent.state.value if hasattr(agent.state, "value") else str(agent.state)
            icon = STATE_ICONS.get(state, "[dim]?[/]")
            lines.append(f"  {icon}  [bold]{name}[/]  [{state}]")

        if failed:
            lines.append(f"\n[red bold]Failed ({len(failed)})[/]\n")
            for name, reason in failed.items():
                lines.append(f"  [red]●[/]  [bold]{name}[/]  [dim]{reason}[/]")

        panel.update("\n".join(lines))


class ConnectorsView(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("[bold]Sources (Connectors)[/]", classes="screen-title")
        yield Static(id="connectors-content")

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        from mneia.connectors import get_available_connectors

        panel = self.query_one("#connectors-content", Static)
        manifests = get_available_connectors()
        config = self.app.bridge.config if self.app.bridge else None
        enabled_names = set()
        if config:
            enabled_names = {n for n, cc in config.connectors.items() if cc.enabled}

        lines = []
        for m in sorted(manifests, key=lambda x: x.name):
            is_on = m.name in enabled_names
            status = "[green]enabled[/]" if is_on else "[dim]disabled[/]"
            lines.append(f"  {status:30s}  [bold]{m.name:<20}[/]  {m.display_name}  [dim]({m.auth_type}, {m.mode.value})[/]")

        panel.update("\n".join(lines) if lines else "[dim]No connectors found[/]")


class GraphView(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("[bold]Knowledge Graph[/]", classes="screen-title")
        yield Static(id="graph-content")

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        panel = self.query_one("#graph-content", Static)
        try:
            stats = await self.app.bridge.get_graph_stats()
            total_nodes = stats.get("total_nodes", 0)
            total_edges = stats.get("total_edges", 0)
            by_type = stats.get("by_type", {})

            lines = [
                f"  Entities:       {total_nodes:,}",
                f"  Relationships:  {total_edges:,}",
                "",
            ]

            if by_type:
                lines.append("[bold]By Type[/]\n")
                max_count = max(by_type.values()) if by_type else 1
                for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
                    bar_len = min(int(count / max_count * 20), 20)
                    bar = "█" * bar_len
                    lines.append(f"  {etype:<15} {count:>5}  [cyan]{bar}[/]")

            graph = self.app.bridge.graph
            if graph and graph._graph:
                degree_map = dict(graph._graph.degree())
                top = sorted(degree_map.items(), key=lambda x: -x[1])[:10]
                if top:
                    lines.append(f"\n[bold]Top Connected[/]\n")
                    for node_id, degree in top:
                        name = graph._graph.nodes[node_id].get("name", node_id)
                        lines.append(f"  {str(name)[:30]:<30}  [yellow]{degree}[/] connections")

            panel.update("\n".join(lines))
        except Exception as exc:
            panel.update(f"[red]Error loading graph: {exc}[/]")


class SettingsView(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("[bold]Settings[/]", classes="screen-title")
        yield Static(id="settings-content")

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        panel = self.query_one("#settings-content", Static)
        config = self.app.bridge.config if self.app.bridge else None
        if not config:
            panel.update("[red]Configuration not available[/]")
            return

        on = "[green]on[/]"
        off = "[red]off[/]"

        lines = [
            "[bold underline]LLM[/]\n",
            f"  Provider:    {config.llm.provider}",
            f"  Model:       {config.llm.model}",
            f"  Embedding:   {config.llm.embedding_model}",
            f"  Temperature: {config.llm.temperature}",
            "",
            "[bold underline]Enabled Connectors[/]\n",
        ]

        enabled = [n for n, cc in config.connectors.items() if cc.enabled]
        for name in sorted(enabled):
            lines.append(f"  [green]●[/] {name}")
        if not enabled:
            lines.append("  [dim]None[/]")

        lines += [
            "",
            "[bold underline]Behavior[/]\n",
            f"  Autonomous:    {on if config.autonomous_enabled else off}",
            f"  Context Gen:   {on if config.auto_generate_context else off}",
            f"  NER:           {on if config.ner_enabled else off}",
            f"  Reranker:      {on if config.reranker_enabled else off}",
            f"  GraphRAG:      {on if config.graphrag_enabled else off}",
            "",
            "[bold underline]Resources[/]\n",
            f"  Max Memory:    {config.max_memory_mb} MB",
            f"  Log Level:     {config.log_level}",
        ]

        panel.update("\n".join(lines))


VIEW_CLASSES = {
    "dashboard": DashboardView,
    "search": SearchView,
    "chat": ChatView,
    "agents": AgentsView,
    "connectors": ConnectorsView,
    "graph": GraphView,
    "settings": SettingsView,
}


class MneiaApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "mneia"
    SUB_TITLE = "personal knowledge agent"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("1", "nav('dashboard')", show=False),
        Binding("2", "nav('search')", show=False),
        Binding("3", "nav('chat')", show=False),
        Binding("4", "nav('agents')", show=False),
        Binding("5", "nav('connectors')", show=False),
        Binding("6", "nav('graph')", show=False),
        Binding("7", "nav('settings')", show=False),
    ]

    bridge: TUIBridge | None = None
    current_view: reactive[str] = reactive("dashboard")

    def compose(self) -> ComposeResult:
        yield StatusHeader(id="status-header")
        with Horizontal(id="app-layout"):
            with Vertical(id="sidebar"):
                yield Static("[bold cyan]mneia[/]", id="sidebar-logo")
                for screen_name, label in SCREEN_NAV:
                    yield NavItem(label, screen_name, classes="nav-item")
            with Vertical(id="main-content"):
                yield DashboardView(id="view-dashboard")
                yield SearchView(id="view-search")
                yield ChatView(id="view-chat")
                yield AgentsView(id="view-agents")
                yield ConnectorsView(id="view-connectors")
                yield GraphView(id="view-graph")
                yield SettingsView(id="view-settings")
        yield CommandBar(id="command-bar")

    def on_mount(self) -> None:
        self.bridge = TUIBridge()
        self._show_view("dashboard")
        self.set_interval(5, self._tick)
        self.run_worker(self._start_daemon(), exclusive=True, group="daemon")

    async def _start_daemon(self) -> None:
        if self.bridge:
            await self.bridge.start_daemon()
            self._tick()
            await asyncio.sleep(2)
            self.run_worker(self._refresh_dashboard(), group="refresh")

    def _tick(self) -> None:
        header = self.query_one("#status-header", StatusHeader)
        if self.bridge and self.bridge.daemon:
            header.daemon_running = self.bridge.daemon.running
            header.agent_count = len(self.bridge.daemon.agents)
        self.run_worker(self._update_doc_count(), group="doc-count")

    async def _update_doc_count(self) -> None:
        if not self.bridge:
            return
        try:
            stats = await self.bridge.get_stats()
            header = self.query_one("#status-header", StatusHeader)
            header.doc_count = stats.get("total_documents", 0)
        except Exception:
            pass

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

        lines = [
            "[bold]System Status[/]\n",
            f"  Daemon:  {daemon_state}",
            f"  Agents:  {agent_count}",
        ]
        if failed:
            lines.append(f"  [red]Failed:  {len(failed)}[/]")
            for name, reason in list(failed.items())[:3]:
                lines.append(f"    [dim]{name}: {reason}[/]")
        status_panel.content_text = "\n".join(lines)

        memory_panel = self.query_one("#panel-memory", DashboardPanel)
        total_docs = stats.get("total_documents", 0)
        total_entities = stats.get("total_entities", 0)
        by_source = stats.get("by_source", {})
        mem_lines = [
            "[bold]Knowledge Base[/]\n",
            f"  Documents:  {total_docs:,}",
            f"  Entities:   {total_entities:,}",
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
        graph_panel.content_text = "\n".join([
            "[bold]Knowledge Graph[/]\n",
            f"  Nodes:  {graph_stats.get('total_nodes', 0):,}",
            f"  Edges:  {graph_stats.get('total_edges', 0):,}",
        ])

        try:
            recent_docs = await self.bridge.get_recent(limit=5)
        except Exception:
            recent_docs = []
        recent_panel = self.query_one("#panel-recent", DashboardPanel)
        if recent_docs:
            r_lines = ["[bold]Recent Documents[/]\n"]
            for doc in recent_docs:
                r_lines.append(f"  [cyan][{doc.source}][/] {doc.title[:50]}")
            recent_panel.content_text = "\n".join(r_lines)
        else:
            recent_panel.content_text = "[bold]Recent Documents[/]\n\n  [dim]No documents yet[/]"

    def _show_view(self, name: str) -> None:
        for sn, _ in SCREEN_NAV:
            try:
                widget = self.query_one(f"#view-{sn}")
                widget.display = sn == name
            except Exception:
                pass
        try:
            for nav_item in self.query("#sidebar NavItem"):
                nav_item.is_active = nav_item.screen_name == name
        except Exception:
            pass
        self.current_view = name

    def on_nav_selected(self, message: NavSelected) -> None:
        self._show_view(message.screen_name)
        if message.screen_name == "dashboard":
            self.run_worker(self._refresh_dashboard(), group="refresh")

    def action_nav(self, name: str) -> None:
        cmd_input = self.query_one("#command-input", Input)
        if cmd_input.has_focus:
            return
        self._show_view(name)
        if name == "dashboard":
            self.run_worker(self._refresh_dashboard(), group="refresh")

    def on_command_submitted(self, message: CommandSubmitted) -> None:
        value = message.value.lstrip("/").strip()
        parts = value.split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        nav_map = {
            "quit": None, "q": None, "exit": None,
            "dashboard": "dashboard", "dash": "dashboard", "home": "dashboard",
            "search": "search", "find": "search",
            "chat": "chat",
            "agents": "agents",
            "connectors": "connectors", "conn": "connectors", "sources": "connectors",
            "graph": "graph",
            "settings": "settings", "config": "settings",
            "refresh": "dashboard", "r": "dashboard",
        }

        if cmd in ("quit", "q", "exit"):
            self.exit()
            return

        if cmd == "search" and args:
            self._show_view("search")
            try:
                search_input = self.query_one("#search-input", Input)
                search_input.value = args
                search_view = self.query_one("#view-search", SearchView)
                search_view.run_worker(search_view._do_search(args))
            except Exception:
                pass
            return

        if cmd in ("ask", "chat") and args:
            self._show_view("chat")
            try:
                chat_view = self.query_one("#view-chat", ChatView)
                chat_view._add_message("You", args, "cyan")
                chat_view.run_worker(chat_view._get_answer(args))
            except Exception:
                pass
            return

        if cmd in nav_map:
            target = nav_map[cmd]
            if target:
                self._show_view(target)
                if target == "dashboard":
                    self.run_worker(self._refresh_dashboard(), group="refresh")

    async def action_quit(self) -> None:
        if self.bridge:
            await self.bridge.stop_daemon()
        self.exit()


def run_tui() -> None:
    from mneia.config import ensure_dirs
    ensure_dirs()
    app = MneiaApp()
    app.run()
