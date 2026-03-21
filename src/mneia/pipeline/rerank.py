from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_reranker_cache: dict[str, Any] = {}


def _is_rerankers_available() -> bool:
    try:
        from rerankers import Reranker  # noqa: F401
        return True
    except ImportError:
        return False


class SearchReranker:
    def __init__(self, model_name: str = "cross-encoder") -> None:
        self._model_name = model_name
        self._available = _is_rerankers_available()

    @property
    def available(self) -> bool:
        return self._available

    def rerank(
        self,
        query: str,
        documents: list[Any],
        top_k: int = 10,
    ) -> list[Any]:
        if not self._available or not documents:
            return documents[:top_k]

        try:
            if self._model_name not in _reranker_cache:
                from rerankers import Reranker
                _reranker_cache[self._model_name] = Reranker(self._model_name)

            ranker = _reranker_cache[self._model_name]
            texts = [getattr(d, "content", str(d))[:1000] for d in documents]

            results = ranker.rank(query=query, docs=texts)

            ranked_indices = [r.doc_id for r in results.results]
            reranked = [documents[i] for i in ranked_indices if i < len(documents)]
            return reranked[:top_k]
        except Exception:
            logger.debug("Reranking failed, returning original order")
            return documents[:top_k]


_default_reranker: SearchReranker | None = None


def get_reranker() -> SearchReranker:
    global _default_reranker
    if _default_reranker is None:
        _default_reranker = SearchReranker()
    return _default_reranker
