from __future__ import annotations

import logging
from typing import Any

from mneia.config import DATA_DIR

logger = logging.getLogger(__name__)

DOCUMENTS_COLLECTION = "mneia_documents"
ENTITIES_COLLECTION = "mneia_entities"


class VectorStore:
    """Vector store for semantic search using ChromaDB with dual collections."""

    def __init__(self) -> None:
        try:
            import chromadb

            path = DATA_DIR / "chroma"
            path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(path))
            self._docs = self._client.get_or_create_collection(
                name=DOCUMENTS_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            self._entities = self._client.get_or_create_collection(
                name=ENTITIES_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            self._available = True
        except ImportError:
            self._client = None
            self._docs = None
            self._entities = None
            self._available = False
            logger.debug("chromadb not installed — vector search disabled")
        except Exception:
            self._client = None
            self._docs = None
            self._entities = None
            self._available = False
            logger.warning("Failed to initialize ChromaDB", exc_info=True)

    @property
    def available(self) -> bool:
        return self._available

    async def add_document(
        self,
        doc_id: str,
        embedding: list[float],
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._docs:
            return
        safe_meta = _sanitize_metadata(metadata)
        self._docs.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[safe_meta],
        )

    async def add_entity(
        self,
        entity_id: str,
        embedding: list[float],
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._entities:
            return
        safe_meta = _sanitize_metadata(metadata)
        self._entities.upsert(
            ids=[entity_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[safe_meta],
        )

    async def search_documents(
        self,
        embedding: list[float],
        n_results: int = 10,
    ) -> list[dict[str, Any]]:
        if not self._docs:
            return []
        return _query_collection(self._docs, embedding, n_results)

    async def search_entities(
        self,
        embedding: list[float],
        n_results: int = 10,
    ) -> list[dict[str, Any]]:
        if not self._entities:
            return []
        return _query_collection(self._entities, embedding, n_results)

    async def search_similar(
        self,
        embedding: list[float],
        n_results: int = 10,
        collection: str = "documents",
    ) -> list[dict[str, Any]]:
        if collection == "entities":
            return await self.search_entities(embedding, n_results)
        return await self.search_documents(embedding, n_results)

    async def delete_document(self, doc_id: str) -> None:
        if not self._docs:
            return
        try:
            self._docs.delete(ids=[doc_id])
        except Exception:
            pass

    async def delete_entity(self, entity_id: str) -> None:
        if not self._entities:
            return
        try:
            self._entities.delete(ids=[entity_id])
        except Exception:
            pass

    def get_stats(self) -> dict[str, int]:
        if not self._available:
            return {"documents": 0, "entities": 0}
        return {
            "documents": self._docs.count() if self._docs else 0,
            "entities": self._entities.count() if self._entities else 0,
        }


def _query_collection(
    collection: Any, embedding: list[float], n_results: int,
) -> list[dict[str, Any]]:
    count = collection.count()
    if count == 0:
        return []
    actual_n = min(n_results, count)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=actual_n,
    )
    items = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results.get("distances") else 0.0
            items.append({
                "id": doc_id,
                "document": results["documents"][0][i] if results.get("documents") else "",
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "distance": distance,
                "score": 1.0 - distance,
            })
    return items


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    safe: dict[str, Any] = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)):
            safe[k] = v
        elif v is None:
            continue
        else:
            safe[k] = str(v)
    return safe
