from __future__ import annotations

import logging
from datetime import datetime, timezone

from mneia.config import MneiaConfig
from mneia.core.llm import LLMClient
from mneia.memory.persistent import PersistentMemory

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(
        self,
        config: MneiaConfig,
        persistent_memory: PersistentMemory | None = None,
    ) -> None:
        self._config = config
        self._memory = persistent_memory or PersistentMemory()
        self._llm = LLMClient(config.llm)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self._interactions: list[dict[str, str]] = []

    def record_interaction(self, role: str, content: str) -> None:
        self._interactions.append({
            "role": role,
            "content": content[:500],
        })

    def get_personal_context(self, limit: int = 5) -> str:
        preferences = self._memory.get_by_category("preference", limit=limit)
        patterns = self._memory.get_by_category("pattern", limit=limit)

        parts = []
        if preferences:
            parts.append("User preferences:")
            for entry in preferences:
                parts.append(f"- {entry.value}")

        if patterns:
            parts.append("\nKnown patterns:")
            for entry in patterns:
                parts.append(f"- {entry.value}")

        return "\n".join(parts)

    async def end_session(self) -> str | None:
        if len(self._interactions) < 2:
            return None

        self._memory.apply_decay()

        summary = await self._summarize_session()
        if summary:
            self._memory.store(
                key=f"session-{self._session_id}",
                value=summary,
                category="session",
                metadata={
                    "interaction_count": len(self._interactions),
                    "session_id": self._session_id,
                },
            )
            logger.info(f"Saved session summary: {self._session_id}")

        return summary

    async def _summarize_session(self) -> str | None:
        if not self._interactions:
            return None

        conversation = "\n".join(
            f"{item['role']}: {item['content']}"
            for item in self._interactions[-20:]
        )

        prompt = (
            "Summarize this conversation session in 2-3 sentences. "
            "Focus on topics discussed, questions asked, and any "
            "preferences or patterns you notice.\n\n"
            f"Conversation:\n{conversation}"
        )

        try:
            return await self._llm.generate(prompt)
        except Exception:
            logger.debug("Session summarization failed", exc_info=True)
            return None

    async def close(self) -> None:
        await self._llm.close()
