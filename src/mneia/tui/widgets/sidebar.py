from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


MENU_ITEMS = [
    ("dashboard", "\u2261", "Dashboard"),
    ("search", "?", "Search"),
    ("chat", ">", "Chat"),
    ("agents", "@", "Agents"),
    ("sources", "+", "Sources"),
    ("graph", "*", "Graph"),
    ("settings", "#", "Settings"),
]


class SidebarItem(Static):
    active: reactive[bool] = reactive(False)

    def __init__(self, screen_name: str, icon: str, label: str) -> None:
        super().__init__(f" {icon}  {label}")
        self.screen_name = screen_name

    def watch_active(self, value: bool) -> None:
        self.set_class(value, "active")

    def on_click(self) -> None:
        self.post_message(Sidebar.SidebarItemSelected(self.screen_name))


class Sidebar(Vertical):
    DEFAULT_CSS = """
    Sidebar {
        width: 16;
        dock: left;
        background: $surface;
        border-right: solid $primary-background;
    }
    Sidebar SidebarItem {
        height: 3;
        padding: 1 1;
        content-align: left middle;
    }
    Sidebar SidebarItem:hover {
        background: $primary 20%;
    }
    Sidebar SidebarItem.active {
        background: $primary 40%;
        text-style: bold;
    }
    """

    class SidebarItemSelected(Message):
        def __init__(self, screen_name: str) -> None:
            super().__init__()
            self.screen_name = screen_name

    active_item: reactive[str] = reactive("dashboard")

    def compose(self) -> ComposeResult:
        for screen_name, icon, label in MENU_ITEMS:
            yield SidebarItem(screen_name, icon, label)

    def watch_active_item(self, value: str) -> None:
        for item in self.query(SidebarItem):
            item.active = item.screen_name == value

    def on_mount(self) -> None:
        self.watch_active_item(self.active_item)
