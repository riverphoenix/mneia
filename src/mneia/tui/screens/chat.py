from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Static


class ChatScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    #chat-messages {
        height: 1fr;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }
    #thinking-indicator {
        height: 1;
        margin: 0 1;
        display: none;
    }
    #thinking-indicator.visible {
        display: block;
    }
    #chat-input {
        dock: bottom;
        margin: 0 1 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield RichLog(id="chat-messages", wrap=True, markup=True)
            yield Static("[dim italic]Thinking...[/dim italic]", id="thinking-indicator")
            yield Input(placeholder="Ask a question...", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#chat-messages", RichLog)
        log.write("[dim]Ask anything about your knowledge base.[/dim]\n")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input" and event.value.strip():
            question = event.value.strip()
            event.input.value = ""
            self._add_user_message(question)
            self.run_worker(self._get_answer(question))

    def _add_user_message(self, text: str) -> None:
        log = self.query_one("#chat-messages", RichLog)
        log.write(f"\n[bold cyan]You:[/bold cyan]  {text}")

    def _show_thinking(self, show: bool) -> None:
        indicator = self.query_one("#thinking-indicator", Static)
        if show:
            indicator.add_class("visible")
        else:
            indicator.remove_class("visible")

    async def _get_answer(self, question: str) -> None:
        self._show_thinking(True)
        log = self.query_one("#chat-messages", RichLog)
        try:
            result = await self.app.bridge.ask(question)
            self._show_thinking(False)
            answer = result.get("answer", "No answer available.")
            log.write(f"\n[bold green]mneia:[/bold green]  {answer}")

            sources = result.get("sources", [])
            if sources:
                source_text = ", ".join(str(s) for s in sources[:5])
                log.write(f"  [dim]Sources: {source_text}[/dim]")

            follow_ups = result.get("follow_ups", [])
            if follow_ups:
                log.write("  [dim italic]Follow-ups:[/dim italic]")
                for fu in follow_ups[:3]:
                    log.write(f"    [dim]- {fu}[/dim]")
        except Exception as exc:
            self._show_thinking(False)
            log.write(f"\n[red]Error: {exc}[/red]")
