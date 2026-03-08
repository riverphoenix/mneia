from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mneia.mcp.server import mcp


def _get_tool(name: str):
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    return tools[name]


async def test_mneia_search_returns_results():
    mock_doc = MagicMock()
    mock_doc.title = "Test Doc"
    mock_doc.source = "obsidian"
    mock_doc.content_type = "note"
    mock_doc.timestamp = "2024-01-01"
    mock_doc.content = "Test content here"

    with patch("mneia.memory.store.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[mock_doc])
        mock_store_cls.return_value = mock_store

        result = await _get_tool("mneia_search").fn(
            query="test", limit=10, source=None,
        )

    assert "Test Doc" in result
    assert "obsidian" in result


async def test_mneia_search_no_results():
    with patch("mneia.memory.store.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store_cls.return_value = mock_store

        result = await _get_tool("mneia_search").fn(
            query="nothing", limit=10, source=None,
        )

    assert "No results" in result


async def test_mneia_search_source_filter():
    doc1 = MagicMock()
    doc1.title = "Obsidian Note"
    doc1.source = "obsidian"
    doc1.content_type = "note"
    doc1.timestamp = "2024-01-01"
    doc1.content = "Note content"

    doc2 = MagicMock()
    doc2.title = "Chrome History"
    doc2.source = "chrome-history"
    doc2.content_type = "bookmark"
    doc2.timestamp = "2024-01-01"
    doc2.content = "Chrome content"

    with patch("mneia.memory.store.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[doc1, doc2])
        mock_store_cls.return_value = mock_store

        result = await _get_tool("mneia_search").fn(
            query="test", limit=10, source="obsidian",
        )

    assert "Obsidian Note" in result
    assert "Chrome History" not in result


async def test_mneia_list_connectors():
    mock_manifest = MagicMock()
    mock_manifest.name = "obsidian"
    mock_manifest.display_name = "Obsidian"
    mock_manifest.auth_type = "local"

    with patch("mneia.config.MneiaConfig.load") as mock_load, \
         patch(
             "mneia.connectors.get_available_connectors",
             return_value=[mock_manifest],
         ):
        mock_config = MagicMock()
        mock_config.connectors = {}
        mock_load.return_value = mock_config

        result = await _get_tool("mneia_list_connectors").fn()

    assert "obsidian" in result
    assert "disabled" in result


async def test_mneia_memory_stats():
    with patch("mneia.memory.store.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.get_stats = AsyncMock(return_value={
            "total_documents": 42,
            "total_entities": 10,
            "total_associations": 5,
            "by_source": {"obsidian": 30, "chrome-history": 12},
        })
        mock_store_cls.return_value = mock_store

        result = await _get_tool("mneia_memory_stats").fn()

    assert "42" in result
    assert "obsidian" in result


async def test_mneia_graph_query():
    with patch("mneia.memory.graph.KnowledgeGraph") as mock_graph_cls:
        mock_graph = MagicMock()
        mock_graph._graph.nodes.__iter__ = MagicMock(
            return_value=iter(["person:alice"]),
        )
        mock_graph._graph.nodes.__contains__ = MagicMock(
            return_value=True,
        )
        mock_graph._graph.nodes.get.return_value = {
            "properties": {"description": "A person"},
        }
        mock_graph.get_neighbors.return_value = {
            "nodes": [{"id": "person:alice"}],
            "edges": [
                {
                    "source": "person:alice",
                    "target": "topic:ai",
                    "relation": "interested_in",
                },
            ],
        }
        mock_graph_cls.return_value = mock_graph

        result = await _get_tool("mneia_graph_query").fn(
            entity_name="Alice",
            entity_type="person",
            depth=2,
        )

    assert "person:alice" in result
    assert "interested_in" in result


async def test_mneia_connector_status():
    mock_manifest = MagicMock()
    mock_manifest.display_name = "Obsidian"
    mock_manifest.name = "obsidian"
    mock_manifest.mode.value = "watch"
    mock_manifest.poll_interval_seconds = 60
    mock_manifest.auth_type = "local"

    with patch("mneia.config.MneiaConfig.load") as mock_load, \
         patch(
             "mneia.connectors.get_connector_manifest",
             return_value=mock_manifest,
         ):
        mock_config = MagicMock()
        mock_conn_config = MagicMock()
        mock_conn_config.enabled = True
        mock_conn_config.last_checkpoint = "2024-01-01T00:00:00"
        mock_config.connectors = {"obsidian": mock_conn_config}
        mock_load.return_value = mock_config

        result = await _get_tool("mneia_connector_status").fn(
            name="obsidian",
        )

    assert "Obsidian" in result
    assert "Enabled: True" in result


async def test_mcp_server_has_all_tools():
    tools = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {
        "mneia_search",
        "mneia_ask",
        "mneia_list_connectors",
        "mneia_connector_status",
        "mneia_sync",
        "mneia_graph_query",
        "mneia_memory_stats",
        "mneia_marketplace_search",
    }
    assert expected.issubset(tools)
