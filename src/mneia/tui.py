from __future__ import annotations

import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

from mneia.config import SOCKET_PATH
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore


class StatusPanel(Static):
    daemon_status: reactive[str] = reactive("checking...")

    def render(self) -> str:
        return self.daemon_status


class AgentsPanel(Static):
    agents_text: reactive[str] = reactive("Loading...")

    def render(self) -> str:
        return self.agents_text


class MemoryPanel(Static):
    memory_text: reactive[str] = reactive("Loading...")

    def render(self) -> str:
        return self.memory_text


class GraphPanel(Static):
    graph_text: reactive[str] = reactive("Loading...")

    def render(self) -> str:
        return self.graph_text


class MneiaDashboard(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1;
    }
    StatusPanel {
        border: solid $primary;
        padding: 1 2;
    }
    AgentsPanel {
        border: solid $secondary;
        padding: 1 2;
    }
    MemoryPanel {
        border: solid $success;
        padding: 1 2;
    }
    GraphPanel {
        border: solid $warning;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    _timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatusPanel(id="status")
        yield AgentsPanel(id="agents")
        yield MemoryPanel(id="memory")
        yield GraphPanel(id="graph")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "mneia — Agent Dashboard"
        self._timer = self.set_interval(5, self.action_refresh)
        self.action_refresh()

    def action_refresh(self) -> None:
        self._update_status()
        self._update_memory()
        self._update_graph()

    def _update_status(self) -> None:
        status_panel = self.query_one("#status", StatusPanel)
        agents_panel = self.query_one("#agents", AgentsPanel)

        if not SOCKET_PATH.exists():
            status_panel.daemon_status = "◉ DAEMON STATUS\n\n  ○ Not running\n\n  Start with: mneia start -d"
            agents_panel.agents_text = "◉ AGENTS\n\n  No agents active"
            return

        try:
            from mneia.core.lifecycle import send_command

            result = asyncio.get_event_loop().run_until_complete(send_command("status"))

            if result.get("running"):
                status_panel.daemon_status = "◉ DAEMON STATUS\n\n  ● Running"
                agents = result.get("agents", [])
                if agents:
                    lines = ["◉ AGENTS\n"]
                    for a in agents:
                        state_icon = "●" if a["state"] == "running" else "○"
                        lines.append(f"  {state_icon} {a['name']}  [{a['state']}]")
                    agents_panel.agents_text = "\n".join(lines)
                else:
                    agents_panel.agents_text = "◉ AGENTS\n\n  No agents active"
            else:
                status_panel.daemon_status = "◉ DAEMON STATUS\n\n  ○ Not responding"
        except Exception:
            status_panel.daemon_status = "◉ DAEMON STATUS\n\n  ○ Connection failed"

    def _update_memory(self) -> None:
        panel = self.query_one("#memory", MemoryPanel)
        try:
            store = MemoryStore()
            stats = asyncio.get_event_loop().run_until_complete(store.get_stats())
            lines = [
                "◉ KNOWLEDGE BASE\n",
                f"  Documents:     {stats.get('total_documents', 0):,}",
                f"  Entities:      {stats.get('total_entities', 0):,}",
                f"  Associations:  {stats.get('total_associations', 0):,}",
            ]
            by_source = stats.get("by_source", {})
            if by_source:
                lines.append("")
                for source, count in by_source.items():
                    lines.append(f"  {source}: {count:,}")
            panel.memory_text = "\n".join(lines)
        except Exception:
            panel.memory_text = "◉ KNOWLEDGE BASE\n\n  Error loading stats"

    def _update_graph(self) -> None:
        panel = self.query_one("#graph", GraphPanel)
        try:
            graph = KnowledgeGraph()
            stats = graph.get_stats()
            lines = [
                "◉ KNOWLEDGE GRAPH\n",
                f"  Entities:       {stats['total_nodes']:,}",
                f"  Relationships:  {stats['total_edges']:,}",
            ]
            by_type = stats.get("by_type", {})
            if by_type:
                lines.append("")
                for etype, count in sorted(by_type.items()):
                    lines.append(f"  {etype}: {count}")
            panel.graph_text = "\n".join(lines)
        except Exception:
            panel.graph_text = "◉ KNOWLEDGE GRAPH\n\n  Error loading graph"


def run_dashboard() -> None:
    app = MneiaDashboard()
    app.run()
