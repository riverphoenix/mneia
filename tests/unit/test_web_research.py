from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mneia.agents.web_research import WebResearchAgent


def _mock_config():
    config = MagicMock()
    config.llm = MagicMock()
    config.enrichment_max_scrape_pages = 3
    config.enrichment_scrape_delay_seconds = 0
    return config


def _make_agent(mock_store=None):
    config = _mock_config()
    with patch("mneia.agents.web_research.LLMClient") as mock_llm_cls, \
         patch("mneia.agents.web_research.MemoryStore") as mock_store_cls:
        mock_llm = MagicMock()
        mock_llm.close = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="Summary")
        mock_llm_cls.return_value = mock_llm
        if mock_store:
            mock_store_cls.return_value = mock_store
        agent = WebResearchAgent(config)
    return agent


async def test_run_no_topic():
    agent = _make_agent()
    result = await agent.run()
    assert result.errors
    assert "No topic" in result.errors[0]


async def test_run_no_urls_found():
    agent = _make_agent()
    agent._search_urls = AsyncMock(return_value=[])
    result = await agent.run(topic="test topic")
    assert "No URLs found" in result.errors[0]


async def test_run_no_scraped_content():
    agent = _make_agent()
    agent._search_urls = AsyncMock(
        return_value=["https://example.com"],
    )
    agent._scrape_pages = AsyncMock(return_value=[])
    result = await agent.run(topic="test topic")
    assert "Could not scrape" in result.errors[0]


async def test_run_success():
    mock_store = MagicMock()
    mock_store.store_document = AsyncMock(return_value=42)
    agent = _make_agent(mock_store=mock_store)
    agent._search_urls = AsyncMock(
        return_value=["https://example.com"],
    )
    agent._scrape_pages = AsyncMock(
        return_value=[
            {"url": "https://example.com", "content": "Page content"},
        ],
    )
    agent._synthesize = AsyncMock(
        return_value="Research summary here",
    )

    result = await agent.run(topic="test topic")

    assert result.documents_processed == 1
    assert result.metadata["topic"] == "test topic"
    assert result.metadata["doc_id"] == 42
    mock_store.store_document.assert_called_once()


async def test_search_urls_parses_duckduckgo():
    agent = _make_agent()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "AbstractURL": "https://en.wikipedia.org/wiki/Test",
        "RelatedTopics": [
            {"FirstURL": "https://example.com/1", "Text": "Foo"},
            {"FirstURL": "https://example.com/2", "Text": "Bar"},
        ],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        urls = await agent._search_urls("test topic")

    assert len(urls) == 3
    assert "wikipedia.org" in urls[0]


async def test_scrape_pages_filters_short_content():
    agent = _make_agent()

    with patch(
        "mneia.connectors.web_scraper.scrape_url",
        new_callable=AsyncMock,
        side_effect=[
            "Short",
            "This is a long enough page content for testing purposes.",
        ],
    ):
        pages = await agent._scrape_pages(
            ["https://a.com", "https://b.com"],
        )

    assert len(pages) == 1
    assert pages[0]["url"] == "https://b.com"


async def test_synthesize_calls_llm():
    agent = _make_agent()
    result = await agent._synthesize(
        "AI", [{"url": "https://x.com", "content": "AI info"}],
    )
    assert result == "Summary"
    agent._llm.generate.assert_called_once()


async def test_synthesize_fallback_on_llm_failure():
    agent = _make_agent()
    agent._llm.generate = AsyncMock(
        side_effect=RuntimeError("LLM down"),
    )
    result = await agent._synthesize(
        "AI", [{"url": "https://x.com", "content": "AI info"}],
    )
    assert "https://x.com" in result
    assert "AI info" in result
