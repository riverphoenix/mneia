from __future__ import annotations

from datetime import datetime

import pytest

from mneia.core.connector import RawDocument
from mneia.memory.store import Entity, MemoryStore


@pytest.fixture
def sample_doc() -> RawDocument:
    return RawDocument(
        source="test",
        source_id="doc-001",
        content="This is a test document about Project Alpha.",
        content_type="note",
        title="Test Note",
        timestamp=datetime(2026, 1, 15, 10, 0, 0),
        metadata={"folder": "notes"},
    )


@pytest.mark.asyncio
async def test_store_and_retrieve(tmp_db: MemoryStore, sample_doc: RawDocument):
    doc_id = await tmp_db.store_document(sample_doc)
    assert doc_id > 0

    stats = await tmp_db.get_stats()
    assert stats["total_documents"] == 1
    assert stats["by_source"]["test"] == 1


@pytest.mark.asyncio
async def test_deduplication(tmp_db: MemoryStore, sample_doc: RawDocument):
    await tmp_db.store_document(sample_doc)
    await tmp_db.store_document(sample_doc)

    stats = await tmp_db.get_stats()
    assert stats["total_documents"] == 1


@pytest.mark.asyncio
async def test_search(tmp_db: MemoryStore, sample_doc: RawDocument):
    await tmp_db.store_document(sample_doc)

    results = await tmp_db.search("Project Alpha")
    assert len(results) == 1
    assert results[0].title == "Test Note"


@pytest.mark.asyncio
async def test_search_no_results(tmp_db: MemoryStore, sample_doc: RawDocument):
    await tmp_db.store_document(sample_doc)
    results = await tmp_db.search("nonexistent query xyz")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_get_recent(tmp_db: MemoryStore, sample_doc: RawDocument):
    await tmp_db.store_document(sample_doc)

    doc2 = RawDocument(
        source="test",
        source_id="doc-002",
        content="Second document",
        content_type="note",
        title="Second Note",
        timestamp=datetime(2026, 1, 16, 10, 0, 0),
    )
    await tmp_db.store_document(doc2)

    recent = await tmp_db.get_recent(limit=1)
    assert len(recent) == 1
    assert recent[0].source_id == "doc-002"


@pytest.mark.asyncio
async def test_checkpoint(tmp_db: MemoryStore):
    assert await tmp_db.get_checkpoint("obsidian") is None

    await tmp_db.set_checkpoint("obsidian", "2026-01-15T10:00:00")
    result = await tmp_db.get_checkpoint("obsidian")
    assert result == "2026-01-15T10:00:00"

    await tmp_db.set_checkpoint("obsidian", "2026-01-16T10:00:00")
    result = await tmp_db.get_checkpoint("obsidian")
    assert result == "2026-01-16T10:00:00"


@pytest.mark.asyncio
async def test_purge(tmp_db: MemoryStore, sample_doc: RawDocument):
    await tmp_db.store_document(sample_doc)
    assert (await tmp_db.get_stats())["total_documents"] == 1

    await tmp_db.purge()
    assert (await tmp_db.get_stats())["total_documents"] == 0


@pytest.mark.asyncio
async def test_purge_by_source(tmp_db: MemoryStore):
    doc1 = RawDocument(
        source="source_a",
        source_id="1",
        content="A content",
        content_type="note",
        title="A",
        timestamp=datetime(2026, 1, 1),
    )
    doc2 = RawDocument(
        source="source_b",
        source_id="2",
        content="B content",
        content_type="note",
        title="B",
        timestamp=datetime(2026, 1, 2),
    )
    await tmp_db.store_document(doc1)
    await tmp_db.store_document(doc2)

    await tmp_db.purge(source="source_a")
    stats = await tmp_db.get_stats()
    assert stats["total_documents"] == 1
    assert "source_a" not in stats["by_source"]


@pytest.mark.asyncio
async def test_store_entity(tmp_db: MemoryStore):
    entity = Entity(
        id=None,
        name="John Smith",
        entity_type="person",
        description="Team lead for Project Alpha",
    )
    entity_id = await tmp_db.store_entity(entity)
    assert entity_id > 0

    stats = await tmp_db.get_stats()
    assert stats["total_entities"] == 1
