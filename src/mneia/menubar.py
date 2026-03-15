from __future__ import annotations

import asyncio
import logging
import time

import rumps

from mneia.config import PID_PATH, SOCKET_PATH

logger = logging.getLogger(__name__)


class MneiaMenuBar(rumps.App):
    def __init__(self) -> None:
        super().__init__("mneia", title="M", quit_button=None)
        self._agent_items: dict[str, rumps.MenuItem] = {}
        self._refresh_timer = rumps.Timer(self._refresh, 5)
        self._refresh_timer.start()
        self._build_menu()

    def _build_menu(self) -> None:
        self.menu.clear()
        self.menu = [
            rumps.MenuItem("mneia", callback=None),
            None,
            rumps.MenuItem("Start Daemon", callback=self._on_start_all),
            rumps.MenuItem("Stop Daemon", callback=self._on_stop_all),
            None,
        ]
        self._update_status()
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("Exit", callback=self._on_exit))

    def _update_status(self) -> None:
        for name, item in list(self._agent_items.items()):
            if name in self.menu:
                del self.menu[name]
        self._agent_items.clear()

        agents = self._get_agents()
        if agents is None:
            self.title = "M"
            try:
                self.menu.insert_after(
                    None, rumps.MenuItem("Daemon not running"),
                )
            except Exception:
                pass
            return

        running_count = sum(
            1 for a in agents if a["state"] == "running"
        )
        total = len(agents)
        if running_count > 0:
            self.title = f"\u2705 M({running_count}/{total})"
        elif agents:
            self.title = f"M({running_count}/{total})"
        else:
            self.title = "M"

        for a in agents:
            is_running = a["state"] == "running"
            icon = "\u2705" if is_running else "\u26aa"
            action = "Stop" if is_running else "Start"
            item = rumps.MenuItem(
                f"{icon} {a['name']}  [{action}]",
                callback=lambda sender, name=a["name"], running=is_running: (
                    self._toggle_agent(name, running)
                ),
            )
            self._agent_items[a["name"]] = item
            insert_pos = "Stop Daemon"
            try:
                self.menu.insert_after(insert_pos, item)
            except Exception:
                self.menu.add(item)

    def _get_agents(self) -> list[dict[str, str]] | None:
        if not SOCKET_PATH.exists():
            return None
        try:
            result = asyncio.run(self._send("status"))
            if result.get("running"):
                return result.get("agents", [])
        except Exception:
            pass
        return None

    async def _send(self, action: str, **kwargs: str) -> dict:
        import json

        reader, writer = await asyncio.open_unix_connection(
            str(SOCKET_PATH),
        )
        try:
            command = {"action": action, **kwargs}
            writer.write(json.dumps(command).encode())
            await writer.drain()
            data = await reader.read(4096)
            return json.loads(data.decode())
        finally:
            writer.close()
            await writer.wait_closed()

    def _toggle_agent(
        self, name: str, currently_running: bool,
    ) -> None:
        try:
            if currently_running:
                asyncio.run(self._send("stop_agent", name=name))
                rumps.notification(
                    "mneia", "Agent stopped", f"{name} has been stopped",
                )
            else:
                asyncio.run(self._send("start_agent", name=name))
                rumps.notification(
                    "mneia", "Agent started", f"{name} has been started",
                )
        except Exception:
            pass
        time.sleep(0.5)
        self._update_status()

    def _on_start_all(self, _: rumps.MenuItem) -> None:
        import subprocess
        import sys

        if SOCKET_PATH.exists():
            rumps.notification(
                "mneia", "Already running",
                "Daemon is already running",
            )
            return

        python = sys.executable
        cmd = [
            python, "-c",
            "import asyncio, os; "
            f"open({str(PID_PATH)!r}, 'w').write(str(os.getpid())); "
            "from mneia.config import MneiaConfig; "
            "from mneia.core.lifecycle import AgentManager; "
            "config = MneiaConfig.load(); "
            "manager = AgentManager(config); "
            "asyncio.run(manager.run())"
        ]
        from mneia.config import MNEIA_DIR

        log_path = MNEIA_DIR / "logs" / "daemon.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(str(log_path), "a")
        subprocess.Popen(
            cmd,
            stdin=open("/dev/null"),
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        rumps.notification(
            "mneia", "Starting daemon",
            "Daemon is starting up...",
        )
        time.sleep(2)
        self._update_status()

    def _on_stop_all(self, _: rumps.MenuItem) -> None:
        try:
            asyncio.run(self._send("stop"))
            rumps.notification(
                "mneia", "Daemon stopped",
                "All agents have been stopped",
            )
        except Exception:
            pass
        time.sleep(1)
        self._update_status()

    def _on_exit(self, _: rumps.MenuItem) -> None:
        rumps.quit_application()

    def _refresh(self, _: rumps.Timer) -> None:
        self._update_status()


def run_menubar() -> None:
    MneiaMenuBar().run()
