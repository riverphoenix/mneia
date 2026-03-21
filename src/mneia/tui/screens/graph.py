from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class GraphScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "refresh", "Refresh"),
    ]

    CSS = """
    #graph-layout {
        layout: horizontal;
        height: 1fr;
        padding: 1;
    }
    .graph-panel {
        width: 1fr;
        border: solid $primary;
        padding: 1 2;
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="graph-layout"):
            yield Static(id="graph-overview", classes="graph-panel")
            yield Static(id="graph-types", classes="graph-panel")
            yield Static(id="graph-top", classes="graph-panel")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load_graph())

    async def _load_graph(self) -> None:
        overview = self.query_one("#graph-overview", Static)
        types_panel = self.query_one("#graph-types", Static)
        top_panel = self.query_one("#graph-top", Static)

        try:
            stats = await self.app.bridge.get_graph_stats()
            total_nodes = stats.get("total_nodes", 0)
            total_edges = stats.get("total_edges", 0)

            overview.update(
                "[bold]Graph Overview[/bold]\n\n"
                f"  Entities:       {total_nodes:,}\n"
                f"  Relationships:  {total_edges:,}"
            )

            by_type = stats.get("by_type", {})
            if by_type:
                lines = ["[bold]Entities by Type[/bold]\n"]
                for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
                    bar_len = min(int(count / max(by_type.values()) * 20), 20) if by_type.values() else 0
                    bar = "█" * bar_len
                    lines.append(f"  {etype:<15} {count:>5}  [cyan]{bar}[/cyan]")
                types_panel.update("\n".join(lines))
            else:
                types_panel.update("[bold]Entities by Type[/bold]\n\n  [dim]No type data[/dim]")

            self._load_top_entities(top_panel)
        except Exception as exc:
            overview.update(f"[bold]Graph Overview[/bold]\n\n  [red]Error: {exc}[/red]")
            types_panel.update("")
            top_panel.update("")

    def _load_top_entities(self, panel: Static) -> None:
        try:
            graph = self.app.bridge.graph
            if not graph or not graph._graph:
                panel.update("[bold]Top Connected[/bold]\n\n  [dim]No graph data[/dim]")
                return

            nx_graph = graph._graph
            degree_map = dict(nx_graph.degree())
            top = sorted(degree_map.items(), key=lambda x: -x[1])[:15]

            if not top:
                panel.update("[bold]Top Connected[/bold]\n\n  [dim]No entities[/dim]")
                return

            lines = ["[bold]Top Connected[/bold]\n"]
            for node, degree in top:
                name = str(node)[:30]
                lines.append(f"  {name:<30} [yellow]{degree}[/yellow] connections")
            panel.update("\n".join(lines))
        except Exception:
            panel.update("[bold]Top Connected[/bold]\n\n  [dim]Unavailable[/dim]")

    def action_refresh(self) -> None:
        self.run_worker(self._load_graph())
