from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mneia.core.connector import RawDocument
from mneia.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr("mneia.memory.store.DB_PATH", tmp_path / "test.db")
    return MemoryStore()


@pytest.fixture
async def populated_store(store):
    docs = [
        RawDocument(
            source="google-calendar",
            source_id="cal-1",
            content="Meeting with Alice about Q1 planning",
            content_type="event",
            title="Q1 Planning Meeting",
            timestamp=datetime(2026, 1, 15, tzinfo=timezone.utc),
        ),
        RawDocument(
            source="obsidian",
            source_id="note-1",
            content="Notes about Q1 planning session and goals",
            content_type="note",
            title="Q1 Planning Notes",
            timestamp=datetime(2026, 1, 15, tzinfo=timezone.utc),
        ),
        RawDocument(
            source="gmail",
            source_id="email-1",
            content="Email thread about Q1 planning follow-up",
            content_type="email",
            title="Re: Q1 Planning",
            timestamp=datetime(2026, 1, 16, tzinfo=timezone.utc),
        ),
    ]
    for doc in docs:
        await store.store_document(doc)
    return store


async def test_search_no_filter(populated_store):
    results = await populated_store.search("Q1 planning")
    assert len(results) == 3


async def test_search_single_source(populated_store):
    results = await populated_store.search(
        "Q1 planning", source="google-calendar",
    )
    assert len(results) == 1
    assert results[0].source == "google-calendar"


async def test_search_sources_list(populated_store):
    results = await populated_store.search(
        "Q1 planning", sources=["google-calendar", "gmail"],
    )
    assert len(results) == 2
    sources = {r.source for r in results}
    assert sources == {"google-calendar", "gmail"}


async def test_search_source_no_match(populated_store):
    results = await populated_store.search(
        "Q1 planning", source="live-audio",
    )
    assert len(results) == 0


async def test_search_sources_empty_list(populated_store):
    results = await populated_store.search(
        "Q1 planning", sources=[],
    )
    assert len(results) == 3