from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Markdown, Static


class DocViewer(VerticalScroll):
    DEFAULT_CSS = """
    DocViewer {
        padding: 1 2;
    }
    DocViewer .doc-title {
        text-style: bold;
        margin-bottom: 1;
    }
    DocViewer .doc-meta {
        color: $text-muted;
        margin-bottom: 1;
    }
    DocViewer .doc-empty {
        color: $text-muted;
        text-style: italic;
        margin: 4 0;
        text-align: center;
    }
    """

    title_text: reactive[str] = reactive("")
    source: reactive[str] = reactive("")
    timestamp: reactive[str] = reactive("")
    content: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Static("Select a document to preview", classes="doc-empty", id="empty-msg")
        yield Static("", classes="doc-title", id="doc-title")
        yield Static("", classes="doc-meta", id="doc-meta")
        yield Markdown("", id="doc-content")

    def watch_content(self, value: str) -> None:
        if not self.is_mounted:
            return
        empty = self.query_one("#empty-msg", Static)
        title_w = self.query_one("#doc-title", Static)
        meta_w = self.query_one("#doc-meta", Static)
        content_w = self.query_one("#doc-content", Markdown)

        if not value:
            empty.display = True
            title_w.display = False
            meta_w.display = False
            content_w.display = False
        else:
            empty.display = False
            title_w.display = True
            meta_w.display = True
            content_w.display = True
            title_w.update(self.title_text)
            source_badge = f"[bold cyan]{self.source}[/bold cyan]" if self.source else ""
            meta_w.update(f"{source_badge}  {self.timestamp}")
            content_w.update(value)

    def load_document(self, title: str, source: str, timestamp: str, content: str) -> None:
        self.title_text = title
        self.source = source
        self.timestamp = timestamp
        self.content = content

    def clear_document(self) -> None:
        self.title_text = ""
        self.source = ""
        self.timestamp = ""
        self.content = ""
