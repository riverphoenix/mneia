from __future__ import annotations

import pytest

from mneia.connectors.confluence import ConfluenceConnector


@pytest.fixture
def connector():
    return ConfluenceConnector()


def test_manifest():
    c = ConfluenceConnector()
    assert c.manifest.name == "confluence"
    assert c.manifest.auth_type == "api_token"


async def test_authenticate_no_config(connector):
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_partial(connector):
    result = await connector.authenticate({"base_url": "https://test.atlassian.net/wiki"})
    assert result is False


async def test_authenticate_full(connector):
    result = await connector.authenticate({
        "base_url": "https://test.atlassian.net/wiki",
        "email": "user@test.com",
        "api_token": "token123",
    })
    assert result is True
    assert connector._client is not None


async def test_authenticate_with_options(connector):
    await connector.authenticate({
        "base_url": "https://test.atlassian.net/wiki",
        "email": "user@test.com",
        "api_token": "token123",
        "space_keys": "DEV, TEAM, OPS",
        "max_results": "50",
    })
    assert connector._space_keys == ["DEV", "TEAM", "OPS"]
    assert connector._max_results == 50


async def test_health_check_no_client(connector):
    result = await connector.health_check()
    assert result is False


def test_strip_html():
    html = "<p>Hello <b>World</b></p><br/>Next"
    result = ConfluenceConnector._strip_html(html)
    assert "Hello" in result
    assert "World" in result
    assert "<b>" not in result


def test_strip_html_entities():
    html = "A &amp; B &lt;C&gt;"
    result = ConfluenceConnector._strip_html(html)
    assert "A & B" in result
    assert "<C>" in result


def test_strip_html_table():
    html = "<table><tr><td>Cell1</td><td>Cell2</td></tr></table>"
    result = ConfluenceConnector._strip_html(html)
    assert "Cell1" in result
    assert "Cell2" in result
    assert "<td>" not in result


def test_page_to_document(connector):
    connector._base_url = "https://test.atlassian.net/wiki"
    page = {
        "id": "page-123",
        "title": "Architecture Guide",
        "body": {"storage": {"value": "<p>This is the guide content.</p>"}},
        "space": {"name": "Engineering", "key": "ENG"},
        "version": {
            "by": {"displayName": "Alice"},
            "when": "2025-06-01T10:00:00Z",
        },
        "ancestors": [{"title": "Docs"}, {"title": "Technical"}],
    }

    doc = connector._page_to_document(page)
    assert doc is not None
    assert doc.source == "confluence"
    assert doc.source_id == "page-123"
    assert doc.title == "Architecture Guide"
    assert "guide content" in doc.content
    assert "Engineering" in doc.content
    assert "Alice" in doc.content
    assert "Docs" in doc.content
    assert "Alice" in doc.participants
    assert doc.metadata["space_key"] == "ENG"


def test_page_to_document_no_id(connector):
    doc = connector._page_to_document({})
    assert doc is None
