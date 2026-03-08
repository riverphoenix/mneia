from __future__ import annotations

from mneia.core.llm import LLMClient


class EmbeddingClient:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def embed(self, text: str) -> list[float]:
        return await self._llm.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            results.append(await self._llm.embed(text))
        return results
