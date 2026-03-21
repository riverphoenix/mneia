from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header


class ConnectorsScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    CSS = """
    #connectors-table {
        height: 1fr;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="connectors-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#connectors-table", DataTable)
        table.add_columns("Name", "Display Name", "Status", "Auth", "Mode")
        table.cursor_type = "row"
        self._load_connectors(table)

    def _load_connectors(self, table: DataTable) -> None:
        from mneia.connectors import get_available_connectors

        manifests = get_available_connectors()
        config = self.app.bridge.config
        enabled_names = {
            name
            for name, cc in (config.connectors if config else {}).items()
            if cc.enabled
        }

        for m in sorted(manifests, key=lambda x: x.name):
            is_enabled = m.name in enabled_names
            status = "[green]enabled[/green]" if is_enabled else "[dim]disabled[/dim]"
            table.add_row(
                m.name,
                m.display_name,
                status,
                m.auth_type,
                m.mode.value,
            )
