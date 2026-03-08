from __future__ import annotations

import logging

from mneia.core.llm import LLMClient

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            return True
        return self._available

    async def check_availability(self) -> bool:
        try:
            result = await self._llm.embed("test")
            self._available = len(result) > 0
        except Exception:
            self._available = False
            logger.info("Embedding service unavailable — vector search disabled")
        return self._available

    async def embed(self, text: str) -> list[float] | None:
        if self._available is False:
            return None
        try:
            result = await self._llm.embed(text)
            self._available = True
            return result
        except Exception:
            if self._available is None:
                self._available = False
                logger.info("Embedding service unavailable — vector search disabled")
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        if self._available is False:
            return [None] * len(texts)
        if not texts:
            return []
        try:
            results = await self._llm.embed_batch(texts)
            self._available = True
            return results
        except Exception:
            results: list[list[float] | None] = []
            for text in texts:
                result = await self.embed(text)
                results.append(result)
            return results

    async def embed_for_search(self, query: str) -> list[float] | None:
        return await self.embed(query)

    def _truncate(self, text: str, max_chars: int = 8000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars]

    async def embed_document(self, title: str, content: str, source: str) -> list[float] | None:
        text = f"{title}\n{source}\n{self._truncate(content)}"
        return await self.embed(text)

    async def embed_entity(
        self, name: str, entity_type: str, description: str
    ) -> list[float] | None:
        if description:
            text = f"{name} ({entity_type}): {description}"
        else:
            text = f"{name} ({entity_type})"
        return await self.embed(text)
