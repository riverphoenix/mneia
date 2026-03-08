from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mneia.memory.vector_store import VectorStore, _sanitize_metadata


def test_sanitize_metadata_none():
    assert _sanitize_metadata(None) == {}


def test_sanitize_metadata_empty():
    assert _sanitize_metadata({}) == {}


def test_sanitize_metadata_simple():
    meta = {"title": "Test", "count": 5, "score": 0.9, "active": True}
    result = _sanitize_metadata(meta)
    assert result == meta


def test_sanitize_metadata_converts_complex_types():
    meta = {"tags": ["a", "b"], "nested": {"x": 1}, "none_val": None}
    result = _sanitize_metadata(meta)
    assert result["tags"] == "['a', 'b']"
    assert result["nested"] == "{'x': 1}"
    assert "none_val" not in result


def test_vector_store_unavailable_without_chromadb():
    with patch.dict("sys.modules", {"chromadb": None}):
        with patch("mneia.memory.vector_store.DATA_DIR"):
            store = VectorStore.__new__(VectorStore)
            store._client = None
            store._docs = None
            store._entities = None
            store._available = False
            assert store.available is False


def test_vector_store_stats_unavailable():
    store = VectorStore.__new__(VectorStore)
    store._client = None
    store._docs = None
    store._entities = None
    store._available = False
    assert store.get_stats() == {"documents": 0, "entities": 0}


async def test_add_document_noop_when_unavailable():
    store = VectorStore.__new__(VectorStore)
    store._docs = None
    store._entities = None
    store._available = False
    await store.add_document("doc1", [0.1, 0.2], "text")


async def test_add_entity_noop_when_unavailable():
    store = VectorStore.__new__(VectorStore)
    store._docs = None
    store._entities = None
    store._available = False
    await store.add_entity("ent1", [0.1, 0.2], "text")


async def test_search_documents_empty_when_unavailable():
    store = VectorStore.__new__(VectorStore)
    store._docs = None
    store._entities = None
    store._available = False
    result = await store.search_documents([0.1, 0.2])
    assert result == []


async def test_search_entities_empty_when_unavailable():
    store = VectorStore.__new__(VectorStore)
    store._docs = None
    store._entities = None
    store._available = False
    result = await store.search_entities([0.1, 0.2])
    assert result == []


async def test_search_similar_routes_to_documents():
    store = VectorStore.__new__(VectorStore)
    store._docs = None
    store._entities = None
    store._available = False
    result = await store.search_similar([0.1], collection="documents")
    assert result == []


async def test_search_similar_routes_to_entities():
    store = VectorStore.__new__(VectorStore)
    store._docs = None
    store._entities = None
    store._available = False
    result = await store.search_similar([0.1], collection="entities")
    assert result == []


async def test_delete_document_noop_when_unavailable():
    store = VectorStore.__new__(VectorStore)
    store._docs = None
    store._available = False
    await store.delete_document("doc1")


async def test_delete_entity_noop_when_unavailable():
    store = VectorStore.__new__(VectorStore)
    store._entities = None
    store._available = False
    await store.delete_entity("ent1")


async def test_add_and_search_documents_with_mock():
    mock_collection = MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = {
        "ids": [["doc1"]],
        "documents": [["test content"]],
        "metadatas": [[{"source": "obsidian"}]],
        "distances": [[0.15]],
    }

    store = VectorStore.__new__(VectorStore)
    store._docs = mock_collection
    store._entities = MagicMock()
    store._available = True

    await store.add_document("doc1", [0.1, 0.2, 0.3], "test content", {"source": "obsidian"})
    mock_collection.upsert.assert_called_once()

    results = await store.search_documents([0.1, 0.2, 0.3], n_results=5)
    assert len(results) == 1
    assert results[0]["id"] == "doc1"
    assert results[0]["document"] == "test content"
    assert results[0]["score"] == pytest.approx(0.85)
    assert results[0]["distance"] == pytest.approx(0.15)


async def test_add_and_search_entities_with_mock():
    mock_collection = MagicMock()
    mock_collection.count.return_value = 1
    mock_collection.query.return_value = {
        "ids": [["person:alice"]],
        "documents": [["Alice (person): Product Manager"]],
        "metadatas": [[{"entity_type": "person"}]],
        "distances": [[0.1]],
    }

    store = VectorStore.__new__(VectorStore)
    store._docs = MagicMock()
    store._entities = mock_collection
    store._available = True

    await store.add_entity("person:alice", [0.1, 0.2], "Alice (person): PM", {"entity_type": "person"})
    mock_collection.upsert.assert_called_once()

    results = await store.search_entities([0.1, 0.2], n_results=5)
    assert len(results) == 1
    assert results[0]["id"] == "person:alice"
    assert results[0]["score"] == pytest.approx(0.9)


async def test_search_empty_collection():
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0

    store = VectorStore.__new__(VectorStore)
    store._docs = mock_collection
    store._available = True

    results = await store.search_documents([0.1, 0.2])
    assert results == []
    mock_collection.query.assert_not_called()


def test_get_stats_with_mock():
    mock_docs = MagicMock()
    mock_docs.count.return_value = 42
    mock_entities = MagicMock()
    mock_entities.count.return_value = 15

    store = VectorStore.__new__(VectorStore)
    store._docs = mock_docs
    store._entities = mock_entities
    store._available = True

    stats = store.get_stats()
    assert stats == {"documents": 42, "entities": 15}
