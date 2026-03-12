from __future__ import annotations

import asyncio
import logging
import threading
import time

import rumps

from mneia.config import PID_PATH, SOCKET_PATH

logger = logging.getLogger(__name__)


class MneiaMenuBar(rumps.App):
    def __init__(self) -> None:
        super().__init__("mneia", title="M", quit_button=None)
        self._agent_items: dict[str, rumps.MenuItem] = {}
        self._recording = False
        self._record_thread: threading.Thread | None = None
        self._refresh_timer = rumps.Timer(self._refresh, 5)
        self._refresh_timer.start()
        self._build_menu()

    def _build_menu(self) -> None:
        self.menu.clear()
        rec_label = (
            "\u23f9 Stop Recording" if self._recording
            else "\u23fa Start Recording"
        )
        self.menu = [
            rumps.MenuItem("mneia", callback=None),
            None,
            rumps.MenuItem(rec_label, callback=self._on_toggle_recording),
            None,
            rumps.MenuItem("Start All", callback=self._on_start_all),
            rumps.MenuItem("Stop All", callback=self._on_stop_all),
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
            self.title = "\U0001f534 M" if self._recording else "M"
            self.menu.insert_after(
                None, rumps.MenuItem("Daemon not running"),
            )
            return

        running_count = sum(
            1 for a in agents if a["state"] == "running"
        )
        total = len(agents)
        if self._recording:
            self.title = f"\U0001f534 M({running_count}/{total})"
        elif agents:
            self.title = f"M({running_count}/{total})"
        else:
            self.title = "M"

        for a in agents:
            is_running = a["state"] == "running"
            icon = "\u2705" if is_running else "\u26aa"
            item = rumps.MenuItem(
                f"{icon} {a['name']}",
                callback=lambda sender, name=a["name"], running=is_running: (
                    self._toggle_agent(name, running)
                ),
            )
            self._agent_items[a["name"]] = item
            insert_pos = "Stop All"
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
            else:
                asyncio.run(self._send("start_agent", name=name))
        except Exception:
            pass
        time.sleep(0.5)
        self._update_status()

    def _on_toggle_recording(self, sender: rumps.MenuItem) -> None:
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self._recording = True
        self._rebuild_recording_item()
        self._update_status()

        def _run() -> None:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._recording_loop())
            except Exception:
                logger.exception("Recording thread error")
            finally:
                self._recording = False
                rumps.App._log(self, "Recording stopped")

        self._record_thread = threading.Thread(
            target=_run, daemon=True,
        )
        self._record_thread.start()

    def _stop_recording(self) -> None:
        self._recording = False
        self._rebuild_recording_item()
        self._update_status()

    def _rebuild_recording_item(self) -> None:
        label = (
            "\u23f9 Stop Recording" if self._recording
            else "\u23fa Start Recording"
        )
        try:
            old_key = (
                "\u23f9 Stop Recording" if not self._recording
                else "\u23fa Start Recording"
            )
            if old_key in self.menu:
                self.menu[old_key].title = label
        except Exception:
            pass

    async def _recording_loop(self) -> None:
        from mneia.config import MneiaConfig
        from mneia.connectors.live_audio import LiveAudioConnector
        from mneia.memory.store import MemoryStore

        config = MneiaConfig.load()
        connector = LiveAudioConnector()

        conn_config = config.connectors.get("live-audio")
        settings = conn_config.settings if conn_config else {}

        ok = await connector.authenticate(settings)
        if not ok:
            rumps.notification(
                "mneia",
                "Recording failed",
                connector.last_error or "Audio setup failed",
            )
            return

        store = MemoryStore()

        rumps.notification(
            "mneia", "Recording started",
            "Capturing system audio...",
        )

        async for doc in connector.start_recording():
            if not self._recording:
                break
            try:
                await store.store_document(doc)
            except Exception:
                logger.exception("Failed to store audio chunk")

        await connector.stop_recording()
        rumps.notification(
            "mneia", "Recording stopped",
            f"Transcribed {connector._chunk_index} chunk(s)",
        )

    def _on_start_all(self, _: rumps.MenuItem) -> None:
        import subprocess
        import sys

        if SOCKET_PATH.exists():
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
        time.sleep(2)
        self._update_status()

    def _on_stop_all(self, _: rumps.MenuItem) -> None:
        try:
            asyncio.run(self._send("stop"))
        except Exception:
            pass
        time.sleep(1)
        self._update_status()

    def _on_exit(self, _: rumps.MenuItem) -> None:
        if self._recording:
            self._stop_recording()
        rumps.quit_application()

    def _refresh(self, _: rumps.Timer) -> None:
        self._update_status()


def run_menubar() -> None:
    MneiaMenuBar().run()
