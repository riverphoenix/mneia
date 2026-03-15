from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from mneia.config import MneiaConfig
from mneia.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class ContextWatcher:
    def __init__(self, config: MneiaConfig) -> None:
        self._config = config
        self._store = MemoryStore()
        self._last_gen_time: datetime | None = None
        self._running = False

    async def run(self) -> None:
        self._running = True
        interval = self._config.context_regenerate_interval_minutes * 60

        logger.info(
            f"ContextWatcher started (every {interval}s, "
            f"min_changes={self._config.context_min_changes_for_regen})"
        )

        while self._running:
            try:
                should_regen = await self._should_regenerate()
                if should_regen:
                    await self._regenerate()
            except Exception:
                logger.exception("ContextWatcher cycle failed")

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    async def stop(self) -> None:
        self._running = False

    async def _should_regenerate(self) -> bool:
        if not self._config.auto_generate_context:
            return False

        stats = await self._store.get_stats()
        total = stats.get("total_documents", 0)

        if total == 0:
            return False

        if self._last_gen_time is None:
            return True

        cutoff = self._last_gen_time.isoformat()
        recent = await self._store.get_recent(
            limit=self._config.context_min_changes_for_regen + 5,
        )

        new_docs = 0
        for doc in recent:
            if doc.timestamp and doc.timestamp > cutoff:
                new_docs += 1

        return new_docs >= self._config.context_min_changes_for_regen

    async def _regenerate(self) -> None:
        from mneia.core.llm import LLMClient
        from mneia.memory.graph import KnowledgeGraph
        from mneia.pipeline.generate import generate_context_files

        graph = KnowledgeGraph()
        llm = LLMClient(self._config.llm)

        try:
            generated = await generate_context_files(
                self._config, self._store, graph, llm,
            )
            self._last_gen_time = datetime.now(timezone.utc)

            if generated:
                logger.info(
                    f"ContextWatcher regenerated {len(generated)} "
                    f"context file(s)"
                )
        except Exception:
            logger.exception("Context regeneration failed")
        finally:
            await llm.close()
