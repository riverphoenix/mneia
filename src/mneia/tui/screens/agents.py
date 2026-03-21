from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


STATE_ICONS = {
    "running": "[green]●[/green]",
    "idle": "[yellow]●[/yellow]",
    "error": "[red]●[/red]",
    "stopped": "[dim]○[/dim]",
}


class AgentsScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "refresh", "Refresh"),
    ]

    CSS = """
    #agents-container {
        padding: 1 2;
        height: 1fr;
        overflow-y: auto;
    }
    #agents-header {
        padding: 1 2;
        background: $surface;
        border-bottom: solid $primary;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="agents-header")
        yield Static(id="agents-container")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load_agents())

    async def _load_agents(self) -> None:
        header = self.query_one("#agents-header", Static)
        container = self.query_one("#agents-container", Static)
        bridge = self.app.bridge
        daemon = bridge.daemon

        if not daemon:
            header.update("[bold]Agents[/bold]  [dim]daemon not available[/dim]")
            container.update("[dim]Start the daemon to see agents[/dim]")
            return

        agents = daemon.agents or {}
        total = len(agents)
        header.update(f"[bold]Agents[/bold]  [dim]{total} total[/dim]")

        lines = []
        for name, agent in sorted(agents.items()):
            state = getattr(agent, "state", "unknown")
            icon = STATE_ICONS.get(state, "[dim]?[/dim]")
            lines.append(f"  {icon}  [bold]{name}[/bold]  [{state}]")

        failed = daemon.failed_connectors if hasattr(daemon, "failed_connectors") and daemon.failed_connectors else {}
        if failed:
            lines.append("")
            lines.append("[red bold]Failed Connectors[/red bold]")
            for name, reason in failed.items():
                lines.append(f"  [red]●[/red]  [bold]{name}[/bold]  [dim]{reason}[/dim]")

        if not lines:
            lines.append("[dim]No agents registered[/dim]")

        container.update("\n".join(lines))

    def action_refresh(self) -> None:
        self.run_worker(self._load_agents())
