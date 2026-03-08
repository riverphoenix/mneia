from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mneia.connectors.chrome_history import ChromeHistoryConnector
from mneia.core.connector import RawDocument


def test_scrape_config_defaults():
    connector = ChromeHistoryConnector()
    assert connector._scrape_content is False
    assert connector._scrape_max_pages == 20
    assert connector._scrape_domains_exclude == set()


async def test_auth_with_scrape_config(tmp_path):
    history_db = tmp_path / "History"
    history_db.touch()

    connector = ChromeHistoryConnector()
    result = await connector.authenticate({
        "history_path": str(history_db),
        "scrape_content": "true",
        "scrape_max_pages": "10",
        "scrape_domains_exclude": "google.com, facebook.com",
    })
    assert result is True
    assert connector._scrape_content is True
    assert connector._scrape_max_pages == 10
    assert "google.com" in connector._scrape_domains_exclude
    assert "facebook.com" in connector._scrape_domains_exclude


async def test_auth_with_bool_scrape_config(tmp_path):
    history_db = tmp_path / "History"
    history_db.touch()

    connector = ChromeHistoryConnector()
    result = await connector.authenticate({
        "history_path": str(history_db),
        "scrape_content": True,
    })
    assert result is True
    assert connector._scrape_content is True


def test_is_excluded_domain():
    connector = ChromeHistoryConnector()
    connector._scrape_domains_exclude = {"google.com", "facebook.com"}

    assert connector._is_excluded_domain("https://www.google.com/search") is True
    assert connector._is_excluded_domain("https://facebook.com/profile") is True
    assert connector._is_excluded_domain("https://github.com/repo") is False


def test_is_excluded_domain_internal():
    connector = ChromeHistoryConnector()
    assert connector._is_excluded_domain("chrome://settings") is True
    assert connector._is_excluded_domain("chrome-extension://abc") is True
    assert connector._is_excluded_domain("about:blank") is True
    assert connector._is_excluded_domain("file:///tmp/test.html") is True


def test_is_excluded_domain_empty_url():
    connector = ChromeHistoryConnector()
    assert connector._is_excluded_domain("") is True


async def test_scrape_page_success():
    connector = ChromeHistoryConnector()
    from datetime import datetime, timezone

    doc = RawDocument(
        source="chrome-history",
        source_id="123",
        content="# Test\nURL: https://example.com",
        content_type="bookmark",
        title="Example",
        timestamp=datetime.now(timezone.utc),
        url="https://example.com",
        metadata={"visit_count": 5},
    )

    with patch(
        "mneia.connectors.web_scraper.scrape_url",
        new_callable=AsyncMock,
        return_value="This is the scraped page content that is long enough.",
    ):
        result = await connector._scrape_page(doc)

    assert result is not None
    assert result.content_type == "webpage"
    assert result.source_id == "scraped-123"
    assert result.metadata["content_scraped"] is True


async def test_scrape_page_too_short():
    connector = ChromeHistoryConnector()
    from datetime import datetime, timezone

    doc = RawDocument(
        source="chrome-history",
        source_id="123",
        content="# Test",
        content_type="bookmark",
        title="Example",
        timestamp=datetime.now(timezone.utc),
        url="https://example.com",
        metadata={},
    )

    with patch(
        "mneia.connectors.web_scraper.scrape_url",
        new_callable=AsyncMock,
        return_value="Short",
    ):
        result = await connector._scrape_page(doc)

    assert result is None


async def test_scrape_page_no_url():
    connector = ChromeHistoryConnector()
    from datetime import datetime, timezone

    doc = RawDocument(
        source="chrome-history",
        source_id="123",
        content="No URL",
        content_type="bookmark",
        title="Test",
        timestamp=datetime.now(timezone.utc),
        url=None,
        metadata={},
    )

    result = await connector._scrape_page(doc)
    assert result is None
