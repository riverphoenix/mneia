from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mneia.marketplace.registry import (
    MarketplaceEntry,
    _get_builtin_entries,
    _parse_entries,
    fetch_index,
    search_index,
)


def _sample_entries() -> list[dict]:
    return [
        {
            "name": "slack",
            "display_name": "Slack",
            "description": "Read messages from Slack",
            "version": "0.1.0",
            "author": "mneia-community",
            "package_name": "mneia-connector-slack",
            "auth_type": "oauth2",
            "tags": ["messaging", "chat"],
        },
        {
            "name": "github",
            "display_name": "GitHub",
            "description": "Read issues and PRs from GitHub",
            "version": "0.1.0",
            "author": "mneia-community",
            "package_name": "mneia-connector-github",
            "auth_type": "api_token",
            "tags": ["code", "development"],
        },
        {
            "name": "linear",
            "display_name": "Linear",
            "description": "Read issues from Linear project management",
            "version": "0.1.0",
            "author": "mneia-community",
            "package_name": "mneia-connector-linear",
            "auth_type": "api_token",
            "tags": ["project-management"],
        },
    ]


def test_parse_entries():
    entries = _parse_entries(_sample_entries())
    assert len(entries) == 3
    assert entries[0].name == "slack"
    assert entries[0].display_name == "Slack"
    assert entries[0].package_name == "mneia-connector-slack"
    assert entries[0].auth_type == "oauth2"
    assert "messaging" in entries[0].tags


def test_parse_entries_empty():
    entries = _parse_entries([])
    assert entries == []


def test_search_index_by_name():
    entries = _parse_entries(_sample_entries())
    results = search_index("slack", entries)
    assert len(results) >= 1
    assert results[0].name == "slack"


def test_search_index_by_tag():
    entries = _parse_entries(_sample_entries())
    results = search_index("messaging", entries)
    assert len(results) >= 1
    assert results[0].name == "slack"


def test_search_index_by_description():
    entries = _parse_entries(_sample_entries())
    results = search_index("issues", entries)
    assert len(results) >= 1
    names = [e.name for e in results]
    assert "github" in names or "linear" in names


def test_search_index_no_match():
    entries = _parse_entries(_sample_entries())
    results = search_index("nonexistent-xyz", entries)
    assert results == []


def test_marketplace_entry_dataclass():
    entry = MarketplaceEntry(
        name="test",
        display_name="Test",
        description="A test connector",
        version="1.0.0",
        author="tester",
        package_name="mneia-connector-test",
    )
    assert entry.name == "test"
    assert entry.installed is False
    assert entry.tags == []


def test_get_builtin_entries():
    entries = _get_builtin_entries()
    assert len(entries) > 0
    names = [e.name for e in entries]
    assert "obsidian" in names
    for entry in entries:
        assert entry.installed is True
        assert "built-in" in entry.tags


def test_fetch_index_falls_back_to_builtins():
    with patch("mneia.marketplace.registry._load_cache", return_value=None):
        with patch("mneia.marketplace.registry.httpx.get", side_effect=Exception("offline")):
            entries = fetch_index()
            assert len(entries) > 0
            assert any(e.name == "obsidian" for e in entries)
