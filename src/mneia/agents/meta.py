from __future__ import annotations

import asyncio
import logging
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore
from mneia.pipeline.associate import merge_duplicate_entities

logger = logging.getLogger(__name__)


class MetaAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        config: MneiaConfig,
        agents: dict[str, BaseAgent] | None = None,
        store: MemoryStore | None = None,
        graph: KnowledgeGraph | None = None,
    ) -> None:
        super().__init__(name=name, description="Orchestrator and health monitor")
        self._config = config
        self._agents = agents or {}
        self._store = store or MemoryStore()
        self._graph = graph or KnowledgeGraph()
        self._stop_event = asyncio.Event()
        self._check_interval = 60

    async def run(self, **kwargs: Any) -> AgentResult:
        self._state = AgentState.RUNNING
        logger.info(f"{self.name}: started (checking every {self._check_interval}s)")

        while not self._stop_event.is_set():
            try:
                await self._health_check()
                await self._maintenance()
            except Exception:
                logger.exception(f"{self.name}: check failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._check_interval,
                )
            except asyncio.TimeoutError:
                pass

        self._state = AgentState.STOPPED
        return AgentResult(agent_name=self.name)

    async def _health_check(self) -> None:
        for name, agent in self._agents.items():
            if agent.state == AgentState.ERROR:
                logger.warning(f"{self.name}: agent {name} is in ERROR state")

    async def _maintenance(self) -> None:
        try:
            merged = merge_duplicate_entities(self._graph)
            if merged > 0:
                logger.info(f"{self.name}: merged {merged} duplicate entities")
        except Exception:
            logger.exception(f"{self.name}: entity merge failed")

    async def stop(self) -> None:
        self._stop_event.set()
