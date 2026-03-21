from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class SettingsScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    #settings-content {
        padding: 1 2;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="settings-content")
        yield Footer()

    def on_mount(self) -> None:
        panel = self.query_one("#settings-content", Static)
        config = self.app.bridge.config

        if not config:
            panel.update("[red]Configuration not available[/red]")
            return

        lines = []

        lines.append("[bold underline]LLM Configuration[/bold underline]\n")
        lines.append(f"  Provider:         {config.llm.provider}")
        lines.append(f"  Model:            {config.llm.model}")
        lines.append(f"  Embedding Model:  {config.llm.embedding_model}")
        lines.append(f"  Temperature:      {config.llm.temperature}")
        lines.append(f"  Max Tokens:       {config.llm.max_tokens}")

        lines.append("\n[bold underline]Enabled Connectors[/bold underline]\n")
        enabled = [
            name for name, cc in config.connectors.items() if cc.enabled
        ]
        if enabled:
            for name in sorted(enabled):
                lines.append(f"  [green]●[/green] {name}")
        else:
            lines.append("  [dim]None enabled[/dim]")

        lines.append("\n[bold underline]Behavior[/bold underline]\n")
        lines.append(f"  Autonomous:       {'[green]on[/green]' if config.autonomous_enabled else '[red]off[/red]'}")
        lines.append(f"  Auto Interval:    {config.autonomous_interval_minutes}m")
        lines.append(f"  Max Actions:      {config.autonomous_max_actions}")
        lines.append(f"  Context Gen:      {'[green]on[/green]' if config.auto_generate_context else '[red]off[/red]'}")
        lines.append(f"  Context Interval: {config.context_regenerate_interval_minutes}m")
        lines.append(f"  Hermes:           {'[green]on[/green]' if config.hermes_enabled else '[red]off[/red]'}")

        lines.append("\n[bold underline]Safety[/bold underline]\n")
        lines.append(f"  Auto-approve low risk:  {'[green]yes[/green]' if config.safety.auto_approve_low_risk else '[red]no[/red]'}")
        lines.append(f"  Approval TTL:           {config.safety.approval_ttl_hours}h")
        if config.safety.blocked_operations:
            lines.append(f"  Blocked:                {', '.join(config.safety.blocked_operations)}")

        lines.append("\n[bold underline]Resources[/bold underline]\n")
        lines.append(f"  Max Memory:       {config.max_memory_mb} MB")
        lines.append(f"  Log Level:        {config.log_level}")

        panel.update("\n".join(lines))
