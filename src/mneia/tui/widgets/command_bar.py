from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Static


SUPPORTED_COMMANDS = {
    "/search", "/ask", "/quit", "/help",
    "/dashboard", "/chat", "/agents", "/settings",
}


class CommandBar(Horizontal):
    DEFAULT_CSS = """
    CommandBar {
        dock: bottom;
        height: 3;
        padding: 0 1;
        background: $surface;
        border-top: solid $primary-background;
    }
    CommandBar .prompt-label {
        width: 10;
        padding: 1 0;
        color: $text-muted;
    }
    CommandBar Input {
        width: 1fr;
        border: none;
        background: transparent;
    }
    """

    class CommandSubmitted(Message):
        def __init__(self, command: str, args: str) -> None:
            super().__init__()
            self.command = command
            self.args = args

    def compose(self) -> ComposeResult:
        yield Static("mneia \u203a ", classes="prompt-label")
        yield Input(placeholder="Type a command (/help for list)")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
        else:
            command = "/ask"
            args = text
        self.post_message(self.CommandSubmitted(command, args))
        event.input.value = ""
