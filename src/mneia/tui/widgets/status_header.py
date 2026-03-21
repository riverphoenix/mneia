from __future__ import annotations

from datetime import datetime

from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static


class StatusHeader(Static):
    DEFAULT_CSS = """
    StatusHeader {
        dock: top;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 2;
    }
    """

    agent_count: reactive[int] = reactive(0)
    agents_running: reactive[bool] = reactive(False)
    doc_count: reactive[int] = reactive(0)
    current_time: reactive[str] = reactive("")

    _timer: Timer | None = None

    def on_mount(self) -> None:
        self._update_time()
        self._timer = self.set_interval(1, self._update_time)

    def _update_time(self) -> None:
        self.current_time = datetime.now().strftime("%H:%M:%S")

    def render(self) -> str:
        agent_dot = "[green]\u25cf[/green]" if self.agents_running else "[dim]\u25cf[/dim]"
        agent_text = f"{agent_dot} {self.agent_count} agents"
        doc_text = f"{self.doc_count} docs"
        brand = "[bold]mneia[/bold]"
        padding = " " * 4
        return f"{brand}{padding}{agent_text}{padding}{doc_text}{padding}{self.current_time}"
