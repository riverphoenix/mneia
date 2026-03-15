from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.agents.knowledge import KnowledgeAgent, KNOWLEDGE_INTERVAL_SECONDS
from mneia.config import MneiaConfig
from mneia.core.agent import AgentState
from mneia.memory.store import StoredDocument


@pytest.fixture
def config():
    return MneiaConfig()


@pytest.fixture
def store():
    s = MagicMock()
    s._get_conn = MagicMock()
    s._row_to_doc = MagicMock()
    s.get_checkpoint = AsyncMock(return_value=None)
    s.set_checkpoint = AsyncMock()
    s.store_document = AsyncMock(return_value=1)
    return s


@pytest.fixture
def graph():
    g = MagicMock()
    g.add_entity = MagicMock()
    g.add_relationship = MagicMock()
    g._graph = MagicMock()
    g._graph.nodes = {}
    return g


@pytest.fixture
def agent(config, store, graph):
    return KnowledgeAgent(
        name="test-knowledge",
        config=config,
        store=store,
        graph=graph,
    )


def test_init(agent):
    assert agent.name == "test-knowledge"
    assert agent._state == AgentState.IDLE
    assert agent._docs_processed == 0
    assert agent._connections_made == 0
    assert agent._summaries_generated == 0
    assert agent._last_processed_id == 0


async def test_stop(agent):
    assert not agent._stop_event.is_set()
    await agent.stop()
    assert agent._stop_event.is_set()


async def test_initial_sync_no_checkpoint(agent):
    agent._store.get_checkpoint = AsyncMock(return_value=None)
    await agent._initial_sync()
    assert agent._last_processed_id == 0


async def test_initial_sync_with_checkpoint(agent):
    agent._store.get_checkpoint = AsyncMock(return_value="42")
    await agent._initial_sync()
    assert agent._last_processed_id == 42


def test_extract_entities(agent):
    doc = StoredDocument(
        id=1,
        source="test",
        source_id="t1",
        content="test",
        content_type="text",
        title="Test Doc",
        timestamp="2026-01-01T00:00:00",
        metadata={},
    )
    agent._extract_entities(
        "Alice (person), Kubernetes (tool), Mneia (project)", doc,
    )
    assert agent._graph.add_entity.call_count == 3


def test_extract_entities_skips_empty(agent):
    doc = StoredDocument(
        id=1,
        source="test",
        source_id="t1",
        content="test",
        content_type="text",
        title="Test",
        timestamp="2026-01-01T00:00:00",
        metadata={},
    )
    agent._extract_entities("x, , ", doc)
    assert agent._graph.add_entity.call_count == 0


def test_extract_relationships_needs_graph_nodes(agent):
    doc = StoredDocument(
        id=1,
        source="test",
        source_id="t1",
        content="test",
        content_type="text",
        title="Test",
        timestamp="2026-01-01T00:00:00",
        metadata={},
    )
    agent._graph._graph.__contains__ = MagicMock(return_value=False)
    agent._extract_relationships(
        "Alice -> works_with -> Bob", doc,
    )
    assert agent._graph.add_relationship.call_count == 0


def test_parse_and_store_analysis(agent):
    doc = StoredDocument(
        id=1,
        source="test",
        source_id="t1",
        content="test",
        content_type="text",
        title="Test",
        timestamp="2026-01-01T00:00:00",
        metadata={},
    )
    response = (
        "ENTITIES: Alice (person), Project X (project)\n"
        "RELATIONSHIPS: Alice -> leads -> Project X\n"
        "SUMMARY: Alice leads Project X."
    )
    agent._parse_and_store_analysis(doc, response)
    assert agent._graph.add_entity.call_count == 2


async def test_cycle_no_new_docs(agent):
    conn_mock = MagicMock()
    cursor_mock = MagicMock()
    cursor_mock.fetchall.return_value = []
    conn_mock.execute.return_value = cursor_mock
    conn_mock.close = MagicMock()
    agent._store._get_conn.return_value = conn_mock

    await agent._cycle()
    assert agent._docs_processed == 0


def test_knowledge_interval():
    assert KNOWLEDGE_INTERVAL_SECONDS == 300


async def test_notify_new_documents(agent):
    conn_mock = MagicMock()
    cursor_mock = MagicMock()
    cursor_mock.fetchall.return_value = []
    conn_mock.execute.return_value = cursor_mock
    conn_mock.close = MagicMock()
    agent._store._get_conn.return_value = conn_mock

    await agent.notify_new_documents()
    conn_mock.execute.assert_called_once()


def test_hermes_disabled_by_default_when_not_installed(config, store, graph):
    agent = KnowledgeAgent(
        name="test-no-hermes",
        config=config,
        store=store,
        graph=graph,
    )
    assert agent._use_hermes is False
    assert agent._hermes_agent is None


def test_hermes_disabled_by_config(store, graph):
    config = MneiaConfig()
    config.hermes_enabled = False
    agent = KnowledgeAgent(
        name="test-hermes-off",
        config=config,
        store=store,
        graph=graph,
    )
    assert agent._use_hermes is False


async def test_native_cycle_processes_docs(agent):
    doc = StoredDocument(
        id=5,
        source="test",
        source_id="t5",
        content="x" * 60,
        content_type="text",
        title="Long Doc",
        timestamp="2026-01-01T00:00:00",
        metadata={},
    )
    with patch.object(agent, "_process_document", new_callable=AsyncMock) as mock_proc:
        await agent._native_cycle([doc])
        mock_proc.assert_called_once_with(doc)
    assert agent._docs_processed == 1
    assert agent._last_processed_id == 5