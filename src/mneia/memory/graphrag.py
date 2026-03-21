from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mneia.config import DATA_DIR

logger = logging.getLogger(__name__)

LIGHTRAG_DIR = DATA_DIR / "lightrag"


def _is_lightrag_available() -> bool:
    try:
        from lightrag import LightRAG  # noqa: F401
        return True
    except ImportError:
        return False


class GraphRAGStore:
    def __init__(self, working_dir: Path | None = None) -> None:
        self._dir = working_dir or LIGHTRAG_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._available = _is_lightrag_available()
        self._rag: Any = None

    @property
    def available(self) -> bool:
        return self._available

    def _ensure_rag(self) -> Any:
        if self._rag is None and self._available:
            from lightrag import LightRAG
            self._rag = LightRAG(working_dir=str(self._dir))
        return self._rag

    async def insert(self, text: str) -> bool:
        rag = self._ensure_rag()
        if not rag:
            return False
        try:
            await rag.ainsert(text)
            return True
        except Exception:
            logger.debug("LightRAG insert failed")
            return False

    async def query(self, query: str, mode: str = "hybrid") -> str:
        rag = self._ensure_rag()
        if not rag:
            return ""
        try:
            from lightrag import QueryParam
            return await rag.aquery(query, param=QueryParam(mode=mode))
        except Exception:
            logger.debug("LightRAG query failed")
            return ""
