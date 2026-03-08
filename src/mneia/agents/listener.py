from __future__ import annotations

import asyncio
import logging
from typing import Any

from mneia.config import ConnectorConfig, MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.core.connector import BaseConnector
from mneia.pipeline.ingest import ingest_connector

logger = logging.getLogger(__name__)


class ListenerAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        connector: BaseConnector,
        config: MneiaConfig,
        connector_config: ConnectorConfig,
    ) -> None:
        super().__init__(name=name, description=f"Listener for {connector.manifest.display_name}")
        self._connector = connector
        self._config = config
        self._connector_config = connector_config
        self._stop_event = asyncio.Event()
        self._total_docs = 0

    async def run(self, **kwargs: Any) -> AgentResult:
        self._state = AgentState.RUNNING
        logger.info(f"{self.name}: started (polling every {self._connector_config.poll_interval_seconds}s)")

        while not self._stop_event.is_set():
            try:
                result = await ingest_connector(
                    self._connector,
                    self._connector_config,
                    self._config,
                )
                self._total_docs += result.documents_ingested
                if result.documents_ingested > 0:
                    logger.info(f"{self.name}: ingested {result.documents_ingested} new docs")
                if result.checkpoint:
                    self._connector_config.last_checkpoint = result.checkpoint
            except Exception:
                logger.exception(f"{self.name}: sync failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._connector_config.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

        self._state = AgentState.STOPPED
        return AgentResult(
            agent_name=self.name,
            documents_processed=self._total_docs,
        )

    async def stop(self) -> None:
        self._stop_event.set()
