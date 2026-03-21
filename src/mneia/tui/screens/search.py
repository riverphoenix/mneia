from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static


SOURCE_COLORS = {
    "obsidian": "cyan",
    "gmail": "red",
    "slack": "magenta",
    "github": "white",
    "jira": "blue",
    "confluence": "blue",
    "notion": "yellow",
    "google-drive": "green",
    "google-calendar": "green",
}


class SearchScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    #search-layout {
        layout: horizontal;
        height: 1fr;
    }
    #search-left {
        width: 2fr;
        height: 100%;
    }
    #search-input {
        dock: top;
        margin: 1;
    }
    #results-list {
        height: 1fr;
        border: solid $primary;
        margin: 0 1;
    }
    #preview-pane {
        width: 3fr;
        height: 100%;
        border: solid $accent;
        padding: 1 2;
        margin: 1;
        overflow-y: auto;
    }
    """

    _results: list = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="search-layout"):
            with Vertical(id="search-left"):
                yield Input(placeholder="Search your knowledge base...", id="search-input")
                yield ListView(id="results-list")
            yield Static(
                "[dim]Type a query to search your knowledge base[/dim]",
                id="preview-pane",
            )
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input" and event.value.strip():
            self.run_worker(self._do_search(event.value.strip()))

    async def _do_search(self, query: str) -> None:
        results_view = self.query_one("#results-list", ListView)
        preview = self.query_one("#preview-pane", Static)
        preview.update("[dim]Searching...[/dim]")
        results_view.clear()
        self._results = []

        try:
            docs = await self.app.bridge.search(query, limit=20)
            self._results = docs
            if not docs:
                preview.update("[dim]No results found[/dim]")
                return
            for doc in docs:
                color = SOURCE_COLORS.get(doc.source, "white")
                snippet = doc.content[:200].replace("\n", " ") if doc.content else ""
                ts = doc.timestamp.strftime("%Y-%m-%d") if isinstance(doc.timestamp, datetime) else str(doc.timestamp)[:10]
                label = f"[bold]{doc.title[:50]}[/bold]\n[{color}][{doc.source}][/{color}] [dim]{ts}[/dim]\n[dim]{snippet}...[/dim]"
                results_view.append(ListItem(Static(label)))
            preview.update(f"[dim]{len(docs)} results — select one to preview[/dim]")
        except Exception as exc:
            preview.update(f"[red]Search error: {exc}[/red]")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        preview = self.query_one("#preview-pane", Static)
        idx = event.list_view.index
        if idx is not None and idx < len(self._results):
            doc = self._results[idx]
            color = SOURCE_COLORS.get(doc.source, "white")
            ts = doc.timestamp.strftime("%Y-%m-%d %H:%M") if isinstance(doc.timestamp, datetime) else str(doc.timestamp)
            header = f"[bold]{doc.title}[/bold]\n[{color}][{doc.source}][/{color}]  [dim]{ts}[/dim]\n{'─' * 40}\n"
            preview.update(header + (doc.content or "[dim]No content[/dim]"))
