from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mneia.connectors.zoom import ZoomConnector


@pytest.fixture
def connector():
    return ZoomConnector()


def test_manifest():
    c = ZoomConnector()
    assert c.manifest.name == "zoom"
    assert c.manifest.auth_type == "oauth2"
    assert "recording:read" in c.manifest.scopes


async def test_authenticate_missing_fields(connector):
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_partial_fields(connector):
    result = await connector.authenticate({"account_id": "acc", "client_id": "cid"})
    assert result is False


async def test_health_check_no_client(connector):
    result = await connector.health_check()
    assert result is False


def test_parse_vtt_basic():
    vtt = """WEBVTT

1
00:00:00.000 --> 00:00:05.000
Hello everyone.

2
00:00:05.000 --> 00:00:10.000
Welcome to the meeting.
"""
    result = ZoomConnector._parse_vtt(vtt)
    assert "Hello everyone." in result
    assert "Welcome to the meeting." in result
    assert "WEBVTT" not in result
    assert "-->" not in result


def test_parse_vtt_empty():
    assert ZoomConnector._parse_vtt("") == ""


def test_parse_vtt_with_notes():
    vtt = """WEBVTT

NOTE This is a comment

1
00:00:00.000 --> 00:00:05.000
Actual text here.
"""
    result = ZoomConnector._parse_vtt(vtt)
    assert "Actual text here." in result
    assert "comment" not in result


async def test_meeting_to_document(connector):
    connector._client = MagicMock()
    connector._fetch_transcript = AsyncMock(return_value="Hello everyone.")

    meeting = {
        "id": 12345,
        "topic": "Weekly Standup",
        "start_time": "2025-06-01T10:00:00Z",
        "duration": 30,
        "total_size": 5,
        "host_email": "host@example.com",
        "recording_files": [
            {"recording_type": "shared_screen_with_speaker_view"},
        ],
    }

    doc = await connector._meeting_to_document(meeting)
    assert doc is not None
    assert doc.source == "zoom"
    assert doc.source_id == "12345"
    assert doc.title == "Weekly Standup"
    assert "30 minutes" in doc.content
    assert "Hello everyone." in doc.content
    assert "host@example.com" in doc.participants
    assert doc.metadata["duration_minutes"] == 30


async def test_meeting_to_document_no_id(connector):
    connector._client = MagicMock()
    doc = await connector._meeting_to_document({})
    assert doc is None
