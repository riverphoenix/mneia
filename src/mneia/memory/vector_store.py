from __future__ import annotations

from typing import Any


class VectorStore:
    """Vector store for semantic search. Requires chromadb optional dependency."""

    def __init__(self, collection_name: str = "mneia") -> None:
        try:
            import chromadb

            self._client = chromadb.PersistentClient(path=str(self._get_path()))
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except ImportError:
            self._client = None
            self._collection = None

    def _get_path(self) -> Any:
        from mneia.config import DATA_DIR

        path = DATA_DIR / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def available(self) -> bool:
        return self._collection is not None

    async def add(
        self,
        doc_id: str,
        embedding: list[float],
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._collection:
            return
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
        )

    async def query(
        self,
        embedding: list[float],
        n_results: int = 10,
    ) -> list[dict[str, Any]]:
        if not self._collection:
            return []
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
        )
        items = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                items.append({
                    "id": doc_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })
        return items
