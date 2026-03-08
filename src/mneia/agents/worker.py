from __future__ import annotations

import asyncio
import logging
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.core.llm import LLMClient
from mneia.memory.embeddings import EmbeddingClient
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore
from mneia.memory.vector_store import VectorStore
from mneia.pipeline.extract import extract_and_store

logger = logging.getLogger(__name__)


class WorkerAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        config: MneiaConfig,
        store: MemoryStore | None = None,
        graph: KnowledgeGraph | None = None,
        vector_store: VectorStore | None = None,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        super().__init__(name=name, description="Entity extraction and association worker")
        self._config = config
        self._store = store or MemoryStore()
        self._graph = graph or KnowledgeGraph()
        self._vector_store = vector_store
        self._embedding_client = embedding_client
        self._stop_event = asyncio.Event()
        self._total_entities = 0
        self._total_relationships = 0
        self._docs_processed = 0
        self._batch_size = 10
        self._poll_interval = 30

    async def run(self, **kwargs: Any) -> AgentResult:
        self._state = AgentState.RUNNING
        logger.info(f"{self.name}: started (polling every {self._poll_interval}s)")

        llm = LLMClient(self._config.llm)
        try:
            while not self._stop_event.is_set():
                try:
                    processed = await self._process_batch(llm)
                    if processed > 0:
                        logger.info(f"{self.name}: processed {processed} docs")
                except Exception:
                    logger.exception(f"{self.name}: batch processing failed")

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._poll_interval,
                    )
                except asyncio.TimeoutError:
                    pass
        finally:
            await llm.close()

        self._state = AgentState.STOPPED
        return AgentResult(
            agent_name=self.name,
            documents_processed=self._docs_processed,
            entities_extracted=self._total_entities,
            associations_created=self._total_relationships,
        )

    async def _process_batch(self, llm: LLMClient) -> int:
        docs = await self._store.get_unprocessed(limit=self._batch_size)
        if not docs:
            return 0

        processed = 0
        for doc in docs:
            try:
                result = await extract_and_store(
                    doc, llm, self._store, self._graph,
                    vector_store=self._vector_store,
                    embedding_client=self._embedding_client,
                )
                self._total_entities += result["entities"]
                self._total_relationships += result["relationships"]
                self._docs_processed += 1
                processed += 1
            except Exception:
                logger.exception(f"{self.name}: failed to process doc {doc.id}")

        return processed

    async def stop(self) -> None:
        self._stop_event.set()
