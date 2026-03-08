from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mneia.connectors.notion import NotionConnector


@pytest.fixture
def connector():
    return NotionConnector()


def test_manifest():
    c = NotionConnector()
    assert c.manifest.name == "notion"
    assert c.manifest.auth_type == "bearer_token"


async def test_authenticate_no_token(connector):
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_with_token(connector):
    result = await connector.authenticate({"api_token": "ntn_test123"})
    assert result is True
    assert connector._client is not None


async def test_authenticate_with_database_ids(connector):
    await connector.authenticate({
        "api_token": "ntn_test",
        "database_ids": "db1, db2, db3",
    })
    assert connector._database_ids == ["db1", "db2", "db3"]


async def test_authenticate_max_results(connector):
    await connector.authenticate({
        "api_token": "ntn_test",
        "max_results": "50",
    })
    assert connector._max_results == 50


async def test_health_check_no_client(connector):
    result = await connector.health_check()
    assert result is False


def test_extract_title():
    props = {
        "title": {
            "type": "title",
            "title": [{"plain_text": "My Page"}],
        },
    }
    assert NotionConnector._extract_title(props) == "My Page"


def test_extract_title_name_field():
    props = {
        "Name": {
            "type": "title",
            "title": [{"plain_text": "Named Page"}],
        },
    }
    assert NotionConnector._extract_title(props) == "Named Page"


def test_extract_title_fallback():
    props = {"status": {"type": "select"}}
    assert NotionConnector._extract_title(props) == "Untitled"


def test_block_to_text_paragraph():
    block = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"plain_text": "Hello world"}],
        },
    }
    assert NotionConnector._block_to_text(block) == "Hello world"


def test_block_to_text_heading():
    block = {
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"plain_text": "Section Title"}],
        },
    }
    assert NotionConnector._block_to_text(block) == "## Section Title"


def test_block_to_text_bulleted_list():
    block = {
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"plain_text": "Item one"}],
        },
    }
    assert NotionConnector._block_to_text(block) == "- Item one"


def test_block_to_text_code():
    block = {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": "print('hi')"}],
            "language": "python",
        },
    }
    result = NotionConnector._block_to_text(block)
    assert "```python" in result
    assert "print('hi')" in result


def test_block_to_text_todo():
    block = {
        "type": "to_do",
        "to_do": {
            "rich_text": [{"plain_text": "Buy milk"}],
            "checked": True,
        },
    }
    assert NotionConnector._block_to_text(block) == "- [x] Buy milk"


def test_block_to_text_divider():
    block = {"type": "divider", "divider": {}}
    assert NotionConnector._block_to_text(block) == "---"


def test_block_to_text_unknown():
    block = {"type": "table", "table": {}}
    assert NotionConnector._block_to_text(block) == ""


async def test_page_to_document(connector):
    connector._client = MagicMock()
    connector._fetch_page_content = AsyncMock(return_value="Some content here")

    page = {
        "id": "page-123",
        "object": "page",
        "properties": {
            "title": {
                "type": "title",
                "title": [{"plain_text": "Test Page"}],
            },
        },
        "url": "https://notion.so/test-page",
        "last_edited_time": "2025-06-01T10:00:00.000Z",
        "last_edited_by": {"name": "Alice"},
        "created_by": {"name": "Bob"},
        "parent": {"type": "database_id", "database_id": "db-456"},
    }

    doc = await connector._page_to_document(page)
    assert doc is not None
    assert doc.source == "notion"
    assert doc.source_id == "page-123"
    assert doc.title == "Test Page"
    assert "Test Page" in doc.content
    assert "Some content here" in doc.content
    assert "Alice" in doc.participants
    assert "Bob" in doc.participants
    assert doc.metadata["database_id"] == "db-456"
