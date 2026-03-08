from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.agents.enrichment import EnrichmentAgent


def test_parse_enrichment_response():
    response = """DESCRIPTION: A software company based in San Francisco.
URL: https://example.com
TAGS: technology, software, san-francisco"""

    result = EnrichmentAgent._parse_enrichment_response(response)
    assert result["description"] == "A software company based in San Francisco."
    assert result["url"] == "https://example.com"
    assert "technology" in result["tags"]
    assert "software" in result["tags"]


def test_parse_enrichment_response_none_values():
    response = """DESCRIPTION: Some entity.
URL: none
TAGS: none"""

    result = EnrichmentAgent._parse_enrichment_response(response)
    assert result["description"] == "Some entity."
    assert "url" not in result
    assert "tags" not in result


def test_parse_enrichment_response_empty():
    result = EnrichmentAgent._parse_enrichment_response("")
    assert result == {}


def test_parse_enrichment_response_partial():
    response = "DESCRIPTION: Just a description."
    result = EnrichmentAgent._parse_enrichment_response(response)
    assert result["description"] == "Just a description."
    assert "url" not in result
    assert "tags" not in result


def test_find_sparse_nodes():
    config = MagicMock()
    config.llm = MagicMock()

    with patch("mneia.agents.enrichment.KnowledgeGraph") as mock_graph_cls, \
         patch("mneia.agents.enrichment.LLMClient"):
        mock_graph = MagicMock()
        mock_graph._graph.nodes.return_value = [
            ("person:alice", {"name": "Alice", "entity_type": "person", "properties": {"description": ""}}),
            ("person:bob", {"name": "Bob", "entity_type": "person", "properties": {"description": "A very detailed description of Bob that is long enough"}}),
            ("topic:ai", {"name": "AI", "entity_type": "topic", "properties": {}}),
        ]
        mock_graph_cls.return_value = mock_graph

        agent = EnrichmentAgent(config)
        sparse = agent._find_sparse_nodes()
        assert len(sparse) == 2
        names = [d.get("name", "") for _, d in sparse]
        assert "Alice" in names
        assert "AI" in names
