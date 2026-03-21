from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Button, Footer, Header, Static


class DashboardScreen(Screen):
    BINDINGS = [("r", "refresh", "Refresh")]

    CSS = """
    #dashboard-grid {
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1;
        height: 1fr;
        padding: 1;
    }
    .panel {
        border: solid $primary;
        padding: 1 2;
        height: 100%;
    }
    #status-panel { border: solid $success; }
    #kb-panel { border: solid $accent; }
    #recent-panel { border: solid $warning; }
    #actions-panel { border: solid $secondary; }
    #actions-panel Button {
        margin: 1 0 0 0;
        width: 100%;
    }
    """

    _timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="dashboard-grid"):
            yield Static(id="status-panel", classes="panel")
            yield Static(id="kb-panel", classes="panel")
            yield Static(id="recent-panel", classes="panel")
            with Vertical(id="actions-panel", classes="panel"):
                yield Static("[bold]Quick Actions[/bold]\n")
                yield Button("Search", id="btn-search", variant="primary")
                yield Button("Chat", id="btn-chat", variant="success")
                yield Button("Sync Now", id="btn-sync", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self._timer = self.set_interval(5, self._refresh_data)
        self._refresh_data()

    def _refresh_data(self) -> None:
        self.run_worker(self._load_data(), exclusive=True)

    async def _load_data(self) -> None:
        bridge = self.app.bridge
        await self._update_status(bridge)
        await self._update_kb(bridge)
        await self._update_recent(bridge)

    async def _update_status(self, bridge) -> None:
        panel = self.query_one("#status-panel", Static)
        daemon = bridge.daemon
        running = daemon.running if daemon else False
        agent_count = len(daemon.agents) if daemon else 0
        failed = len(daemon.failed_connectors) if daemon and daemon.failed_connectors else 0
        status_icon = "[green]●[/green] Running" if running else "[red]○[/red] Stopped"
        lines = [
            "[bold]System Status[/bold]\n",
            f"  Daemon:  {status_icon}",
            f"  Agents:  {agent_count}",
        ]
        if failed:
            lines.append(f"  [red]Failed:  {failed}[/red]")
        panel.update("\n".join(lines))

    async def _update_kb(self, bridge) -> None:
        panel = self.query_one("#kb-panel", Static)
        try:
            stats = await bridge.get_stats()
            lines = [
                "[bold]Knowledge Base[/bold]\n",
                f"  Documents:     {stats.get('total_documents', 0):,}",
                f"  Entities:      {stats.get('total_entities', 0):,}",
                f"  Associations:  {stats.get('total_associations', 0):,}",
            ]
            by_source = stats.get("by_source", {})
            if by_source:
                lines.append("")
                for source, count in sorted(by_source.items()):
                    lines.append(f"  [dim]{source}:[/dim] {count:,}")
            panel.update("\n".join(lines))
        except Exception:
            panel.update("[bold]Knowledge Base[/bold]\n\n  [red]Error loading stats[/red]")

    async def _update_recent(self, bridge) -> None:
        panel = self.query_one("#recent-panel", Static)
        try:
            docs = await bridge.get_recent(limit=5)
            lines = ["[bold]Recent Activity[/bold]\n"]
            if not docs:
                lines.append("  [dim]No documents yet[/dim]")
            for doc in docs:
                ts = doc.timestamp.strftime("%H:%M") if isinstance(doc.timestamp, datetime) else str(doc.timestamp)[:5]
                lines.append(f"  [cyan]{ts}[/cyan] [{doc.source}] {doc.title[:40]}")
            panel.update("\n".join(lines))
        except Exception:
            panel.update("[bold]Recent Activity[/bold]\n\n  [red]Error loading[/red]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-search":
            from mneia.tui.screens.search import SearchScreen
            self.app.push_screen(SearchScreen())
        elif event.button.id == "btn-chat":
            from mneia.tui.screens.chat import ChatScreen
            self.app.push_screen(ChatScreen())

    def action_refresh(self) -> None:
        self._refresh_data()
