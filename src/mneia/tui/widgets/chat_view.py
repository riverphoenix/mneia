from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class ChatMessage(Static):
    DEFAULT_CSS = """
    ChatMessage {
        margin: 1 0;
        padding: 1 2;
        width: 100%;
    }
    ChatMessage.user-message {
        background: $primary 20%;
        text-align: right;
    }
    ChatMessage.assistant-message {
        background: $surface;
        text-align: left;
    }
    ChatMessage .sources {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }
    """

    def __init__(self, role: str, content: str, sources: list[str] | None = None) -> None:
        super().__init__()
        self.role = role
        self.msg_content = content
        self.sources = sources

    def on_mount(self) -> None:
        self.add_class(f"{self.role}-message")

    def render(self) -> str:
        label = "[bold cyan]You[/bold cyan]" if self.role == "user" else "[bold green]mneia[/bold green]"
        lines = [f"{label}\n{self.msg_content}"]
        if self.sources:
            refs = ", ".join(self.sources)
            lines.append(f"\n[dim]Sources: {refs}[/dim]")
        return "\n".join(lines)


class ChatView(VerticalScroll):
    DEFAULT_CSS = """
    ChatView {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[dim]Start a conversation...[/dim]", id="chat-placeholder")

    def add_message(
        self, role: str, content: str, sources: list[str] | None = None
    ) -> None:
        placeholder = self.query("#chat-placeholder")
        if placeholder:
            placeholder.first().remove()
        message = ChatMessage(role, content, sources)
        self.mount(message)
        self.scroll_end(animate=False)
