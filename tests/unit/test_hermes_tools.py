from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.agents.hermes_tools import (
    TOOL_DEFINITIONS,
    _make_node_id,
    create_tool_handlers,
)
from mneia.memory.store import StoredDocument


def test_tool_definitions_count():
    assert len(TOOL_DEFINITIONS) == 5


def test_tool_definitions_names():
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert names == {
        "search_knowledge",
        "get_recent_documents",
        "query_graph",
        "store_insight",
        "add_connection",
    }


def test_tool_definitions_have_required_fields():
    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        func = tool["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func


def test_make_node_id():
    assert _make_node_id("person", "Alice Smith") == "person:alice-smith"
    assert _make_node_id("tool", "Kubernetes") == "tool:kubernetes"


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.search = AsyncMock(return_value=[])
    store.store_document = AsyncMock(return_value=42)
    store._get_conn = MagicMock()
    store._row_to_doc = MagicMock()
    return store


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph._graph = MagicMock()
    graph._graph.nodes = MagicMock(return_value=[])
    graph.add_entity = MagicMock()
    graph.add_relationship = MagicMock()
    graph.get_neighbors = MagicMock(return_value={"nodes": [], "edges": []})
    return graph


@pytest.fixture
def handlers(mock_store, mock_graph):
    return create_tool_handlers(mock_store, mock_graph)


def test_search_knowledge_no_results(handlers, mock_store):
    mock_store.search = AsyncMock(return_value=[])
    result = json.loads(handlers["search_knowledge"]("test query"))
    assert result["results"] == []
    assert "No documents" in result["message"]


def test_search_knowledge_with_results(handlers, mock_store):
    doc = StoredDocument(
        id=1,
        source="gmail",
        source_id="msg1",
        content="Test email content here with enough text",
        content_type="email",
        title="Budget Email",
        timestamp="2026-01-01T00:00:00",
        metadata={},
    )
    mock_store.search = AsyncMock(return_value=[doc])
    result = json.loads(handlers["search_knowledge"]("budget"))
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Budget Email"
    assert result["results"][0]["source"] == "gmail"


def test_search_knowledge_with_source_filter(handlers, mock_store):
    mock_store.search = AsyncMock(return_value=[])
    handlers["search_knowledge"]("meetings", source="google-calendar")
    mock_store.search.assert_called_once_with("meetings", limit=5, source="google-calendar")


def test_get_recent_documents(handlers, mock_store):
    conn_mock = MagicMock()
    cursor_mock = MagicMock()
    cursor_mock.fetchall.return_value = []
    conn_mock.execute.return_value = cursor_mock
    mock_store._get_conn.return_value = conn_mock

    result = json.loads(handlers["get_recent_documents"](count=5))
    assert result["documents"] == []
    conn_mock.execute.assert_called_once()


def test_get_recent_documents_with_source(handlers, mock_store):
    conn_mock = MagicMock()
    cursor_mock = MagicMock()
    cursor_mock.fetchall.return_value = []
    conn_mock.execute.return_value = cursor_mock
    mock_store._get_conn.return_value = conn_mock

    handlers["get_recent_documents"](count=5, source="obsidian")
    call_args = conn_mock.execute.call_args
    assert "source = ?" in call_args[0][0]


def test_query_graph_not_found(handlers, mock_graph):
    mock_graph._graph.nodes.return_value = []
    result = json.loads(handlers["query_graph"]("Unknown Entity"))
    assert result["found"] is False


def test_query_graph_found(handlers, mock_graph):
    mock_graph._graph.nodes.return_value = [
        ("person:alice", {"name": "Alice", "entity_type": "person"}),
    ]
    mock_graph._graph.nodes.__iter__ = MagicMock(
        return_value=iter([("person:alice", {"name": "Alice"})])
    )
    mock_graph._graph.nodes.side_effect = None
    mock_graph._graph.nodes = MagicMock()
    mock_graph._graph.nodes.return_value = [
        ("person:alice", {"name": "Alice", "entity_type": "person"}),
    ]
    mock_graph._graph.nodes.data = True

    class FakeNodes:
        def __call__(self, data: bool = False) -> list:
            return [("person:alice", {"name": "Alice", "entity_type": "person"})]

        def __iter__(self):
            return iter(["person:alice"])

    mock_graph._graph.nodes = FakeNodes()
    mock_graph.get_neighbors.return_value = {
        "nodes": [{"id": "person:alice", "name": "Alice", "type": "person"}],
        "edges": [],
    }

    result = json.loads(handlers["query_graph"]("Alice"))
    assert result["found"] is True


def test_store_insight(handlers, mock_store):
    result = json.loads(handlers["store_insight"](
        title="Cross-doc insight",
        content="Alice and Bob both discuss budget in separate threads.",
    ))
    assert result["stored"] is True
    assert result["document_id"] == 42
    mock_store.store_document.assert_called_once()


def test_add_connection(handlers, mock_graph):
    result = json.loads(handlers["add_connection"](
        entity_a="Alice",
        entity_b="Project X",
        relation="leads",
        entity_a_type="person",
        entity_b_type="project",
    ))
    assert result["added"] is True
    assert "Alice" in result["edge"]
    assert "Project X" in result["edge"]
    assert mock_graph.add_entity.call_count == 2
    mock_graph.add_relationship.assert_called_once()
