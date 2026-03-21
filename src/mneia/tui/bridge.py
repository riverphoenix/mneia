from __future__ import annotations

import logging
from typing import Any

from mneia.config import MneiaConfig, ensure_dirs
from mneia.conversation import ConversationEngine
from mneia.core.lifecycle import EmbeddedDaemon
from mneia.core.llm import LLMClient
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore, StoredDocument
from mneia.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)

_instance: TUIBridge | None = None


class TUIBridge:
    def __init__(self, config: MneiaConfig | None = None) -> None:
        ensure_dirs()
        self.config = config or MneiaConfig.load()
        self.store = MemoryStore()
        self.graph = KnowledgeGraph()
        self.vector_store = VectorStore()
        self.llm = LLMClient(self.config.llm)
        self.daemon: EmbeddedDaemon | None = None
        self._conversation = ConversationEngine(
            config=self.config,
            vector_store=self.vector_store if self.vector_store.available else None,
        )

        global _instance
        _instance = self

    async def start_daemon(self) -> None:
        self.daemon = EmbeddedDaemon(self.config)
        try:
            await self.daemon.start()
            logger.info("Embedded daemon started")
        except Exception:
            logger.exception("Failed to start embedded daemon")
            self.daemon = None

    async def stop_daemon(self) -> None:
        if self.daemon:
            await self.daemon.stop()
            self.daemon = None
        await self.llm.close()
        await self._conversation.close()

    async def search(
        self,
        query: str,
        limit: int = 10,
        source: str | None = None,
    ) -> list[StoredDocument]:
        return await self.store.search(query, limit=limit, source=source)

    async def ask(self, question: str) -> dict[str, Any]:
        result = await self._conversation.ask(question)
        return {
            "answer": result.answer,
            "sources": [
                {"title": c.title, "source": c.source, "snippet": c.snippet}
                for c in result.citations
            ],
            "follow_ups": result.suggested_followups,
        }

    async def get_stats(self) -> dict[str, Any]:
        return await self.store.get_stats()

    async def get_graph_stats(self) -> dict[str, Any]:
        return self.graph.get_stats()

    async def get_recent(self, limit: int = 10) -> list[StoredDocument]:
        return await self.store.get_recent(limit=limit)

    @staticmethod
    def instance() -> TUIBridge | None:
        return _instance
