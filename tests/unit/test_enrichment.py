from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
            (
                "person:alice",
                {
                    "name": "Alice",
                    "entity_type": "person",
                    "properties": {"description": ""},
                },
            ),
            (
                "person:bob",
                {
                    "name": "Bob",
                    "entity_type": "person",
                    "properties": {
                        "description": (
                            "A very detailed description of Bob "
                            "that is long enough"
                        ),
                    },
                },
            ),
            (
                "topic:ai",
                {
                    "name": "AI",
                    "entity_type": "topic",
                    "properties": {},
                },
            ),
        ]
        mock_graph_cls.return_value = mock_graph

        agent = EnrichmentAgent(config)
        sparse = agent._find_sparse_nodes()
        assert len(sparse) == 2
        names = [d.get("name", "") for _, d in sparse]
        assert "Alice" in names
        assert "AI" in names


async def test_enrich_entity_with_scraping():
    config = MagicMock()
    config.llm = MagicMock()
    config.enrichment_scrape_enabled = True
    config.enrichment_max_scrape_pages = 2
    config.enrichment_scrape_delay_seconds = 0

    with patch("mneia.agents.enrichment.KnowledgeGraph"), \
         patch("mneia.agents.enrichment.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=(
                "DESCRIPTION: A Python library.\n"
                "URL: https://example.com\n"
                "TAGS: python, library"
            ),
        )
        mock_llm_cls.return_value = mock_llm

        agent = EnrichmentAgent(config)
        agent._web_search = AsyncMock(return_value="Some search info")
        agent._scrape_search_urls = AsyncMock(
            return_value="Scraped content from pages",
        )

        result = await agent._enrich_entity("TestLib", "library")

    assert result is not None
    assert result["description"] == "A Python library."
    agent._scrape_search_urls.assert_called_once()


async def test_enrich_entity_scraping_disabled():
    config = MagicMock()
    config.llm = MagicMock()
    config.enrichment_scrape_enabled = False

    with patch("mneia.agents.enrichment.KnowledgeGraph"), \
         patch("mneia.agents.enrichment.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value="DESCRIPTION: A thing.\nURL: none\nTAGS: none",
        )
        mock_llm_cls.return_value = mock_llm

        agent = EnrichmentAgent(config)
        agent._web_search = AsyncMock(return_value="Search info")
        agent._scrape_search_urls = AsyncMock()

        result = await agent._enrich_entity("Thing", "concept")

    assert result is not None
    agent._scrape_search_urls.assert_not_called()


async def test_extract_search_urls():
    config = MagicMock()
    config.llm = MagicMock()

    with patch("mneia.agents.enrichment.KnowledgeGraph"), \
         patch("mneia.agents.enrichment.LLMClient"):
        agent = EnrichmentAgent(config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "AbstractURL": "https://en.wikipedia.org/wiki/Python",
        "RelatedTopics": [
            {"FirstURL": "https://python.org", "Text": "Python"},
            {"FirstURL": "https://docs.python.org", "Text": "Docs"},
        ],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        urls = await agent._extract_search_urls("Python", "language")

    assert len(urls) == 3
    assert "wikipedia.org" in urls[0]
