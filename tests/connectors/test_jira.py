from __future__ import annotations

import pytest

from mneia.connectors.jira import JiraConnector


@pytest.fixture
def connector():
    return JiraConnector()


def test_manifest():
    c = JiraConnector()
    assert c.manifest.name == "jira"
    assert c.manifest.auth_type == "api_token"


async def test_authenticate_no_config(connector):
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_partial(connector):
    result = await connector.authenticate({"base_url": "https://test.atlassian.net"})
    assert result is False


async def test_authenticate_full(connector):
    result = await connector.authenticate({
        "base_url": "https://test.atlassian.net",
        "email": "user@test.com",
        "api_token": "token123",
    })
    assert result is True
    assert connector._client is not None


async def test_authenticate_custom_jql(connector):
    await connector.authenticate({
        "base_url": "https://test.atlassian.net",
        "email": "user@test.com",
        "api_token": "token123",
        "jql": "project = TEST",
        "max_results": "50",
    })
    assert connector._jql == "project = TEST"
    assert connector._max_results == 50


async def test_health_check_no_client(connector):
    result = await connector.health_check()
    assert result is False


def test_extract_adf_text_string():
    assert JiraConnector._extract_adf_text("plain text") == "plain text"


def test_extract_adf_text_node():
    node = {"type": "text", "text": "Hello"}
    assert JiraConnector._extract_adf_text(node) == "Hello"


def test_extract_adf_text_paragraph():
    node = {
        "type": "paragraph",
        "content": [
            {"type": "text", "text": "Line one"},
        ],
    }
    result = JiraConnector._extract_adf_text(node)
    assert "Line one" in result


def test_extract_adf_text_nested():
    node = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "First"},
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Second"},
                ],
            },
        ],
    }
    result = JiraConnector._extract_adf_text(node)
    assert "First" in result
    assert "Second" in result


def test_extract_adf_text_non_dict():
    assert JiraConnector._extract_adf_text(42) == ""
    assert JiraConnector._extract_adf_text(None) == ""


def test_issue_to_document(connector):
    connector._base_url = "https://test.atlassian.net"
    issue = {
        "key": "TEST-42",
        "fields": {
            "summary": "Fix login page",
            "description": {"type": "paragraph", "content": [{"type": "text", "text": "Login is broken"}]},
            "assignee": {"displayName": "Alice"},
            "reporter": {"displayName": "Bob"},
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "labels": ["frontend", "urgent"],
            "updated": "2025-06-01T10:00:00Z",
            "comment": {
                "comments": [
                    {
                        "author": {"displayName": "Charlie"},
                        "body": {"type": "text", "text": "Looking into this"},
                    },
                ],
            },
        },
    }

    doc = connector._issue_to_document(issue)
    assert doc is not None
    assert doc.source == "jira"
    assert doc.source_id == "TEST-42"
    assert "Fix login page" in doc.title
    assert "Alice" in doc.content
    assert "In Progress" in doc.content
    assert "High" in doc.content
    assert "Charlie" in doc.content
    assert "Alice" in doc.participants
    assert "Bob" in doc.participants


def test_issue_to_document_no_key(connector):
    doc = connector._issue_to_document({})
    assert doc is None
