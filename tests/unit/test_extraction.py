from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import Entity, MemoryStore, StoredDocument
from mneia.pipeline.extract import _make_node_id, extract_and_store, extract_entities


@pytest.fixture
def sample_doc():
    return StoredDocument(
        id=1,
        source="obsidian",
        source_id="test.md",
        content="Met with Alice about the Falcon project. She's the PM and we decided to ship v2.",
        content_type="markdown",
        title="Meeting Notes",
        timestamp="2025-01-15T10:00:00",
    )


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate_json = AsyncMock(return_value={
        "entities": [
            {"name": "Alice", "type": "person", "description": "Product Manager"},
            {"name": "Falcon", "type": "project", "description": "Main project"},
        ],
        "relationships": [
            {"source": "Alice", "target": "Falcon", "relation": "manages"},
        ],
    })
    return llm


def test_make_node_id():
    assert _make_node_id("Alice Smith", "person") == "person:alice-smith"
    assert _make_node_id("Falcon", "project") == "project:falcon"


async def test_extract_entities(sample_doc, mock_llm):
    result = await extract_entities(sample_doc, mock_llm)
    assert "entities" in result
    assert len(result["entities"]) == 2
    assert result["entities"][0]["name"] == "Alice"
    assert len(result["relationships"]) == 1


async def test_extract_entities_llm_failure(sample_doc):
    llm = MagicMock()
    llm.generate_json = AsyncMock(side_effect=Exception("LLM down"))
    result = await extract_entities(sample_doc, llm)
    assert result["entities"] == []
    assert result["relationships"] == []


async def test_extract_and_store(sample_doc, mock_llm, tmp_path):
    store = MemoryStore(db_path=tmp_path / "test.db")
    from mneia.core.connector import RawDocument
    from datetime import datetime

    raw = RawDocument(
        source="obsidian",
        source_id="test.md",
        content=sample_doc.content,
        content_type="markdown",
        title="Meeting Notes",
        timestamp=datetime(2025, 1, 15, 10, 0, 0),
    )
    await store.store_document(raw)

    graph = KnowledgeGraph(db_path=tmp_path / "graph.db")

    result = await extract_and_store(sample_doc, mock_llm, store, graph)
    assert result["entities"] == 2
    assert result["relationships"] == 1

    stats = graph.get_stats()
    assert stats["total_nodes"] == 2
    assert stats["total_edges"] == 1
