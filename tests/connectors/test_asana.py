from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mneia.connectors.asana import AsanaConnector


@pytest.fixture
def connector():
    return AsanaConnector()


def test_manifest():
    c = AsanaConnector()
    assert c.manifest.name == "asana"
    assert c.manifest.auth_type == "api_token"


async def test_authenticate_no_token(connector):
    result = await connector.authenticate({})
    assert result is False


async def test_health_check_no_client(connector):
    result = await connector.health_check()
    assert result is False


def test_task_to_document(connector):
    task = {
        "gid": "task-123",
        "name": "Fix the bug",
        "notes": "This bug needs fixing ASAP.",
        "assignee": {"name": "Alice"},
        "due_on": "2025-06-15",
        "completed": False,
        "tags": [{"name": "urgent"}, {"name": "backend"}],
        "modified_at": "2025-06-01T10:00:00Z",
        "permalink_url": "https://app.asana.com/0/task-123",
    }

    doc = connector._task_to_document(task)
    assert doc is not None
    assert doc.source == "asana"
    assert doc.source_id == "task-123"
    assert doc.title == "Fix the bug"
    assert "Alice" in doc.content
    assert "urgent" in doc.content
    assert "Open" in doc.content
    assert "Alice" in doc.participants
    assert doc.metadata["completed"] is False
    assert doc.metadata["due_on"] == "2025-06-15"


def test_task_to_document_completed(connector):
    task = {
        "gid": "task-456",
        "name": "Deploy v2",
        "notes": "",
        "assignee": None,
        "completed": True,
        "tags": [],
        "completed_at": "2025-06-01T10:00:00Z",
    }

    doc = connector._task_to_document(task)
    assert doc is not None
    assert "Completed" in doc.content
    assert doc.metadata["completed"] is True


def test_task_to_document_no_gid(connector):
    doc = connector._task_to_document({})
    assert doc is None
