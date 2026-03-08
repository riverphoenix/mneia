from __future__ import annotations

import asyncio
import json
import logging
import signal
from typing import Any

from mneia.config import SOCKET_PATH, MneiaConfig
from mneia.core.agent import AgentState, BaseAgent

logger = logging.getLogger(__name__)


class AgentManager:
    def __init__(
        self,
        config: MneiaConfig,
        connector_filter: list[str] | None = None,
    ) -> None:
        self.config = config
        self.connector_filter = connector_filter
        self._agents: dict[str, BaseAgent] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._running = False
        self._server: asyncio.Server | None = None

    async def run(self) -> None:
        self._running = True

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self._signal_stop)
        loop.add_signal_handler(signal.SIGTERM, self._signal_stop)

        self._server = await asyncio.start_unix_server(
            self._handle_ipc,
            path=str(SOCKET_PATH),
        )

        await self._start_agents()

        logger.info("mneia daemon started")
        try:
            while self._running:
                await asyncio.sleep(1)
        finally:
            await self._stop_agents()
            if self._server:
                self._server.close()
                await self._server.wait_closed()
            if SOCKET_PATH.exists():
                SOCKET_PATH.unlink()
            logger.info("mneia daemon stopped")

    def _signal_stop(self) -> None:
        self._running = False

    async def _start_agents(self) -> None:
        from mneia.agents.listener import ListenerAgent
        from mneia.connectors import create_connector

        for name, conn_config in self.config.connectors.items():
            if not conn_config.enabled:
                continue
            if self.connector_filter and name not in self.connector_filter:
                continue

            connector = create_connector(name)
            if not connector:
                logger.warning(f"Could not create connector: {name}")
                continue

            authenticated = await connector.authenticate(conn_config.settings)
            if not authenticated:
                logger.warning(f"Authentication failed for connector: {name}")
                continue

            agent = ListenerAgent(
                name=f"listener-{name}",
                connector=connector,
                config=self.config,
                connector_config=conn_config,
            )
            self._agents[agent.name] = agent
            self._tasks[agent.name] = asyncio.create_task(
                self._run_agent(agent),
                name=agent.name,
            )
            logger.info(f"Started agent: {agent.name}")

    async def _run_agent(self, agent: BaseAgent) -> None:
        try:
            await agent.run()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(f"Agent {agent.name} crashed")
            agent._state = AgentState.ERROR

    async def _stop_agents(self) -> None:
        for name, agent in self._agents.items():
            await agent.stop()
        for name, task in self._tasks.items():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._agents.clear()
        self._tasks.clear()

    async def _handle_ipc(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            data = await reader.read(4096)
            if not data:
                return

            command = json.loads(data.decode())
            action = command.get("action", "")

            if action == "stop":
                self._running = False
                response = {"ok": True}
            elif action == "status":
                agents_info = []
                for name, agent in self._agents.items():
                    agents_info.append({
                        "name": name,
                        "state": agent.state.value,
                        "docs": agent._state == AgentState.RUNNING,
                    })
                response = {"running": True, "agents": agents_info}
            else:
                response = {"error": f"Unknown action: {action}"}

            writer.write(json.dumps(response).encode())
            await writer.drain()
        except Exception:
            logger.exception("IPC error")
        finally:
            writer.close()
            await writer.wait_closed()


async def send_command(action: str, **kwargs: Any) -> dict[str, Any]:
    reader, writer = await asyncio.open_unix_connection(str(SOCKET_PATH))
    try:
        command = {"action": action, **kwargs}
        writer.write(json.dumps(command).encode())
        await writer.drain()

        data = await reader.read(4096)
        return json.loads(data.decode())
    finally:
        writer.close()
        await writer.wait_closed()
