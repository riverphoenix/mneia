from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


STATE_INDICATORS = {
    "running": "[green]\u25cf[/green]",
    "idle": "[yellow]\u25cf[/yellow]",
    "error": "[red]\u25cf[/red]",
    "stopped": "[dim]\u25cb[/dim]",
}


class AgentCard(Static):
    DEFAULT_CSS = """
    AgentCard {
        height: 1;
        padding: 0 1;
    }
    AgentCard:hover {
        background: $primary 10%;
    }
    """

    name: reactive[str] = reactive("")
    state: reactive[str] = reactive("stopped")

    def __init__(self, name: str, state: str = "stopped") -> None:
        super().__init__()
        self.name = name
        self.state = state

    def render(self) -> str:
        indicator = STATE_INDICATORS.get(self.state, STATE_INDICATORS["stopped"])
        return f"{indicator} {self.name}"
