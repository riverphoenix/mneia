from __future__ import annotations

from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


SOURCE_COLORS = {
    "obsidian": "magenta",
    "slack": "cyan",
    "gmail": "red",
    "confluence": "blue",
    "notion": "white",
    "jira": "green",
    "github": "yellow",
}


class SearchResult(Static):
    DEFAULT_CSS = """
    SearchResult {
        padding: 1 2;
        margin-bottom: 1;
        border: solid $primary-background;
    }
    SearchResult:hover {
        background: $primary 10%;
        border: solid $primary;
    }
    SearchResult.selected {
        background: $primary 20%;
        border: solid $primary;
    }
    """

    class SearchResultSelected(Message):
        def __init__(self, doc_id: str) -> None:
            super().__init__()
            self.doc_id = doc_id

    doc_id: reactive[str] = reactive("")
    title: reactive[str] = reactive("")
    source: reactive[str] = reactive("")
    snippet: reactive[str] = reactive("")
    timestamp: reactive[str] = reactive("")

    def __init__(
        self,
        doc_id: str,
        title: str,
        source: str,
        snippet: str,
        timestamp: str,
    ) -> None:
        super().__init__()
        self.doc_id = doc_id
        self.title = title
        self.source = source
        self.snippet = snippet
        self.timestamp = timestamp

    def render(self) -> str:
        color = SOURCE_COLORS.get(self.source.lower(), "white")
        badge = f"[bold {color}]{self.source}[/bold {color}]"
        truncated = self.snippet[:200] if len(self.snippet) > 200 else self.snippet
        return (
            f"[bold]{self.title}[/bold]  {badge}\n"
            f"[dim]{truncated}[/dim]\n"
            f"[dim]{self.timestamp}[/dim]"
        )

    def on_click(self) -> None:
        self.post_message(self.SearchResultSelected(self.doc_id))
