from __future__ import annotations

import asyncio
import logging
from typing import Any

from mneia.config import ConnectorConfig, MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.core.connector import BaseConnector, ConnectorMode
from mneia.memory.embeddings import EmbeddingClient
from mneia.memory.store import MemoryStore
from mneia.memory.vector_store import VectorStore
from mneia.pipeline.ingest import ingest_connector

logger = logging.getLogger(__name__)


class ListenerAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        connector: BaseConnector,
        config: MneiaConfig,
        connector_config: ConnectorConfig,
        vector_store: VectorStore | None = None,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        super().__init__(
            name=name,
            description=f"Listener for {connector.manifest.display_name}",
        )
        self._connector = connector
        self._config = config
        self._connector_config = connector_config
        self._vector_store = vector_store
        self._embedding_client = embedding_client
        self._stop_event = asyncio.Event()
        self._total_docs = 0

    async def run(self, **kwargs: Any) -> AgentResult:
        self._state = AgentState.RUNNING

        use_watch = (
            self._connector.manifest.mode == ConnectorMode.WATCH
            and self._connector.manifest.watch_paths_config_key
        )

        if use_watch:
            watch_path = self._connector.get_watch_path(
                self._connector_config.settings,
            )
            if watch_path:
                logger.info(
                    f"{self.name}: watch mode on {watch_path}"
                )
                await self._run_poll_cycle()
                await self._run_watch_mode(watch_path)
            else:
                logger.info(
                    f"{self.name}: watch path not found, "
                    "falling back to poll mode"
                )
                await self._run_poll_mode()
        else:
            interval = self._connector_config.poll_interval_seconds
            logger.info(
                f"{self.name}: poll mode (every {interval}s)"
            )
            await self._run_poll_mode()

        self._state = AgentState.STOPPED
        return AgentResult(
            agent_name=self.name,
            documents_processed=self._total_docs,
        )

    async def _run_poll_mode(self) -> None:
        while not self._stop_event.is_set():
            await self._run_poll_cycle()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._connector_config.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

    async def _run_watch_mode(self, watch_path: Any) -> None:
        from pathlib import Path

        from mneia.core.watcher import FileWatcher

        extensions = set(
            self._connector.manifest.watch_extensions
        ) or {".md"}
        watcher = FileWatcher(
            watch_path=Path(watch_path),
            extensions=extensions,
        )

        store = MemoryStore()

        try:
            async for changed_paths in watcher.watch():
                if self._stop_event.is_set():
                    break

                ingested = 0
                async for doc in self._connector.fetch_changed(
                    changed_paths,
                ):
                    try:
                        doc_id = await store.store_document(doc)
                        ingested += 1

                        if (
                            self._vector_store
                            and self._vector_store.available
                            and self._embedding_client
                            and doc_id
                        ):
                            try:
                                emb = await self._embedding_client.embed_document(
                                    doc.title, doc.content, doc.source,
                                )
                                if emb:
                                    await self._vector_store.add_document(
                                        doc_id=str(doc_id),
                                        embedding=emb,
                                        text=f"{doc.title}\n{doc.content[:2000]}",
                                        metadata={
                                            "source": doc.source,
                                            "title": doc.title,
                                            "content_type": doc.content_type,
                                        },
                                    )
                            except Exception:
                                pass
                    except Exception:
                        logger.exception(
                            f"{self.name}: failed to store changed doc"
                        )

                if ingested > 0:
                    self._total_docs += ingested
                    logger.info(
                        f"{self.name}: watch ingested {ingested} doc(s)"
                    )
        except asyncio.CancelledError:
            pass

    async def _run_poll_cycle(self) -> None:
        try:
            result = await ingest_connector(
                self._connector,
                self._connector_config,
                self._config,
                vector_store=self._vector_store,
                embedding_client=self._embedding_client,
            )
            self._total_docs += result.documents_ingested
            if result.documents_ingested > 0:
                logger.info(
                    f"{self.name}: ingested "
                    f"{result.documents_ingested} new docs"
                )
            if result.checkpoint:
                self._connector_config.last_checkpoint = (
                    result.checkpoint
                )
        except Exception:
            logger.exception(f"{self.name}: sync failed")

    async def stop(self) -> None:
        self._stop_event.set()
