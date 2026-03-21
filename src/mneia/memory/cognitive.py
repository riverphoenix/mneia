from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _is_cognee_available() -> bool:
    try:
        import cognee  # noqa: F401
        return True
    except ImportError:
        return False


class CognitiveMemory:
    def __init__(self, llm_config: Any = None) -> None:
        self._available = _is_cognee_available()
        self._configured = False
        if self._available and llm_config:
            self._configure(llm_config)

    def _configure(self, llm_config: Any) -> None:
        try:
            import cognee

            provider = llm_config.provider
            if provider == "openai" and llm_config.openai_api_key:
                cognee.config.set_llm_config({
                    "llm_api_key": llm_config.openai_api_key,
                    "llm_model": llm_config.model,
                    "llm_provider": "openai",
                })
            elif provider == "anthropic" and llm_config.anthropic_api_key:
                cognee.config.set_llm_config({
                    "llm_api_key": llm_config.anthropic_api_key,
                    "llm_model": llm_config.model,
                    "llm_provider": "anthropic",
                })
            self._configured = True
        except Exception:
            logger.debug("Cognee configuration failed")

    @property
    def available(self) -> bool:
        return self._available and self._configured

    async def add(self, text: str, dataset: str = "default") -> bool:
        if not self.available:
            return False
        try:
            import cognee

            await cognee.add(text, dataset)
            await cognee.cognify()
            return True
        except Exception:
            logger.debug("Cognee add failed")
            return False

    async def search(self, query: str) -> list[dict[str, Any]]:
        if not self.available:
            return []
        try:
            import cognee

            results = await cognee.search(query)
            return [{"content": str(r), "source": "cognee"} for r in results] if results else []
        except Exception:
            logger.debug("Cognee search failed")
            return []
