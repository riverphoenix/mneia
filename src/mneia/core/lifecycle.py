from __future__ import annotations

import asyncio
import json
import logging
import signal
from typing import Any

from mneia.config import PID_PATH, SOCKET_PATH, MneiaConfig
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
        self._failed_connectors: dict[str, str] = {}
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

        from rich.console import Console

        console = Console()

        if self._agents:
            console.print(f"[green]Daemon running with {len(self._agents)} agent(s):[/green]")
            for name in self._agents:
                console.print(f"  [cyan]{name}[/cyan]")
        else:
            enabled = [
                n for n, c in self.config.connectors.items() if c.enabled
            ]
            if not enabled:
                console.print(
                    "[yellow]No connectors enabled. "
                    "Run [cyan]mneia connector enable <name>[/cyan] first.[/yellow]"
                )
            else:
                console.print(
                    "[yellow]No agents started. Check connector configuration "
                    "with [cyan]mneia connector list[/cyan][/yellow]"
                )

        if self._failed_connectors:
            console.print("\n[yellow]Failed to start:[/yellow]")
            for name, reason in self._failed_connectors.items():
                console.print(f"  [red]✗ {name}[/red]: {reason}")
            console.print(
                "[dim]Run [cyan]mneia connector setup <name>[/cyan] to reconfigure.[/dim]"
            )

        console.print("[dim]Listening on socket. Press Ctrl+C to stop.[/dim]\n")

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
            if PID_PATH.exists():
                PID_PATH.unlink(missing_ok=True)
            logger.info("mneia daemon stopped")

    def _signal_stop(self) -> None:
        self._running = False

    async def _start_agents(self) -> None:
        from mneia.agents.listener import ListenerAgent
        from mneia.agents.meta import MetaAgent
        from mneia.agents.worker import WorkerAgent
        from mneia.connectors import create_connector
        from mneia.core.llm import LLMClient
        from mneia.memory.embeddings import EmbeddingClient
        from mneia.memory.graph import KnowledgeGraph
        from mneia.memory.store import MemoryStore
        from mneia.memory.vector_store import VectorStore

        store = MemoryStore()
        graph = KnowledgeGraph()
        vector_store = VectorStore()
        embedding_client = EmbeddingClient(LLMClient(self.config.llm))

        if vector_store.available:
            await embedding_client.check_availability()
            if embedding_client.available:
                logger.info("Vector search enabled")
            else:
                logger.info("Embedding service unavailable — vector search disabled")
        else:
            logger.info("ChromaDB not installed — vector search disabled")

        for name, conn_config in self.config.connectors.items():
            if not conn_config.enabled:
                continue
            if self.connector_filter is not None and name not in self.connector_filter:
                continue

            connector = create_connector(name)
            if not connector:
                logger.warning(f"Could not create connector: {name}")
                self._failed_connectors[name] = "Unknown connector type"
                continue

            try:
                authenticated = await connector.authenticate(conn_config.settings)
            except Exception as exc:
                logger.warning(f"Connector {name} auth error: {exc}")
                self._failed_connectors[name] = str(exc)
                continue

            if not authenticated:
                reason = getattr(connector, "last_error", "Authentication failed")
                logger.warning(f"Authentication failed for connector: {name} — {reason}")
                self._failed_connectors[name] = str(reason)
                continue

            agent = ListenerAgent(
                name=f"listener-{name}",
                connector=connector,
                config=self.config,
                connector_config=conn_config,
                vector_store=vector_store,
                embedding_client=embedding_client,
            )
            self._agents[agent.name] = agent
            self._tasks[agent.name] = asyncio.create_task(
                self._run_agent(agent),
                name=agent.name,
            )
            logger.info(f"Started agent: {agent.name}")

        worker = WorkerAgent(
            name="worker",
            config=self.config,
            store=store,
            graph=graph,
            vector_store=vector_store,
            embedding_client=embedding_client,
        )
        self._agents[worker.name] = worker
        self._tasks[worker.name] = asyncio.create_task(
            self._run_agent(worker),
            name=worker.name,
        )
        logger.info("Started agent: worker")

        meta = MetaAgent(
            name="meta",
            config=self.config,
            agents=self._agents,
            store=store,
            graph=graph,
        )
        self._agents[meta.name] = meta
        self._tasks[meta.name] = asyncio.create_task(
            self._run_agent(meta),
            name=meta.name,
        )
        logger.info("Started agent: meta")

        if self.config.autonomous_enabled:
            from mneia.agents.autonomous import AutonomousAgent

            autonomous = AutonomousAgent(
                name="autonomous",
                config=self.config,
                store=store,
                graph=graph,
            )
            self._agents[autonomous.name] = autonomous
            self._tasks[autonomous.name] = asyncio.create_task(
                self._run_agent(autonomous),
                name=autonomous.name,
            )
            logger.info("Started agent: autonomous")

        if self.config.auto_generate_context:
            from mneia.context.watcher import ContextWatcher

            ctx_watcher = ContextWatcher(self.config)
            self._tasks["context-watcher"] = asyncio.create_task(
                ctx_watcher.run(),
                name="context-watcher",
            )
            logger.info("Started context auto-regeneration watcher")

    async def _run_agent(
        self, agent: BaseAgent, max_restarts: int = 3,
    ) -> None:
        from mneia.core.agent_stats import AgentStatsDB

        stats_db = AgentStatsDB()
        stats_db.record(agent.name, "start")
        restarts = 0
        backoff = 5.0
        while True:
            try:
                await agent.run()
                break
            except asyncio.CancelledError:
                break
            except Exception:
                restarts += 1
                stats_db.record(agent.name, "error", f"crash #{restarts}")
                logger.exception(
                    f"Agent {agent.name} crashed "
                    f"(restart {restarts}/{max_restarts})"
                )
                if restarts >= max_restarts:
                    logger.error(
                        f"Agent {agent.name} exceeded max restarts"
                    )
                    agent._state = AgentState.ERROR
                    stats_db.record(agent.name, "stopped", "max restarts exceeded")
                    break
                stats_db.record(agent.name, "restart", f"attempt {restarts}")
                agent._state = AgentState.IDLE
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
        stats_db.close()

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
            elif action == "stop_agent":
                agent_name = command.get("name", "")
                if agent_name in self._agents:
                    await self._agents[agent_name].stop()
                    if agent_name in self._tasks:
                        self._tasks[agent_name].cancel()
                    logger.info(f"Stopped agent: {agent_name}")
                    response = {"ok": True, "stopped": agent_name}
                else:
                    response = {"error": f"Agent not found: {agent_name}"}
            elif action == "start_agent":
                agent_name = command.get("name", "")
                connector_name = agent_name.replace("listener-", "")
                already_running = (
                    agent_name in self._agents
                    and self._agents[agent_name].state != AgentState.STOPPED
                )
                if already_running:
                    response = {"error": f"Agent already running: {agent_name}"}
                else:
                    from mneia.agents.listener import ListenerAgent
                    from mneia.connectors import create_connector

                    conn_config = self.config.connectors.get(connector_name)
                    if not conn_config or not conn_config.enabled:
                        response = {"error": f"Connector not enabled: {connector_name}"}
                    else:
                        connector = create_connector(connector_name)
                        if not connector:
                            response = {"error": f"Unknown connector: {connector_name}"}
                        else:
                            authenticated = await connector.authenticate(conn_config.settings)
                            if not authenticated:
                                response = {"error": f"Auth failed: {connector_name}"}
                            else:
                                agent = ListenerAgent(
                                    name=f"listener-{connector_name}",
                                    connector=connector,
                                    config=self.config,
                                    connector_config=conn_config,
                                )
                                self._agents[agent.name] = agent
                                self._tasks[agent.name] = asyncio.create_task(
                                    self._run_agent(agent), name=agent.name,
                                )
                                logger.info(f"Started agent: {agent.name}")
                                response = {"ok": True, "started": agent.name}
            elif action == "list_agents":
                response = {
                    "agents": [
                        {"name": n, "state": a.state.value}
                        for n, a in self._agents.items()
                    ]
                }
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
