from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mneia.connectors.google_calendar import GoogleCalendarConnector


@pytest.fixture
def connector():
    return GoogleCalendarConnector()


def test_manifest():
    c = GoogleCalendarConnector()
    assert c.manifest.name == "google-calendar"
    assert c.manifest.auth_type == "oauth2"
    assert "readonly" in c.manifest.scopes[0]


async def test_authenticate_no_credentials(connector, monkeypatch):
    import mneia.connectors.google_auth as ga
    monkeypatch.setattr(ga, "get_google_credentials", lambda *a, **kw: (_ for _ in ()).throw(Exception("no creds")))
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_missing_client_id(connector, monkeypatch):
    import mneia.connectors.google_auth as ga
    monkeypatch.setattr(ga, "get_google_credentials", lambda *a, **kw: (_ for _ in ()).throw(Exception("no creds")))
    result = await connector.authenticate({"google_client_secret": "secret"})
    assert result is False


def test_event_to_document(connector):
    event = {
        "id": "evt123",
        "summary": "Team Standup",
        "description": "Daily sync",
        "location": "Zoom",
        "start": {"dateTime": "2025-03-01T10:00:00Z"},
        "end": {"dateTime": "2025-03-01T10:30:00Z"},
        "organizer": {"displayName": "Alice", "email": "alice@example.com"},
        "attendees": [
            {"displayName": "Bob", "email": "bob@example.com"},
            {"displayName": "Carol", "email": "carol@example.com"},
        ],
        "htmlLink": "https://calendar.google.com/event?id=evt123",
        "status": "confirmed",
    }

    doc = connector._event_to_document(event, "primary")
    assert doc is not None
    assert doc.source == "google-calendar"
    assert doc.source_id == "evt123"
    assert doc.title == "Team Standup"
    assert "Daily sync" in doc.content
    assert "Alice" in doc.content
    assert "Bob" in doc.participants
    assert "Carol" in doc.participants
    assert doc.content_type == "event"
    assert doc.url == "https://calendar.google.com/event?id=evt123"


def test_event_to_document_date_only(connector):
    event = {
        "id": "evt456",
        "summary": "Vacation",
        "start": {"date": "2025-03-15"},
        "end": {"date": "2025-03-20"},
    }
    doc = connector._event_to_document(event, "primary")
    assert doc is not None
    assert doc.title == "Vacation"


def test_event_to_document_no_id(connector):
    event = {"summary": "Missing ID"}
    doc = connector._event_to_document(event, "primary")
    assert doc is None


def test_event_with_conference(connector):
    event = {
        "id": "evt789",
        "summary": "Video Call",
        "start": {"dateTime": "2025-03-01T14:00:00Z"},
        "end": {"dateTime": "2025-03-01T15:00:00Z"},
        "conferenceData": {
            "entryPoints": [
                {"entryPointType": "video", "uri": "https://meet.google.com/abc"}
            ]
        },
    }
    doc = connector._event_to_document(event, "primary")
    assert doc is not None
    assert doc.metadata.get("meeting_link") == "https://meet.google.com/abc"


def test_event_recurring(connector):
    event = {
        "id": "evt_rec",
        "summary": "Weekly",
        "start": {"dateTime": "2025-03-01T09:00:00Z"},
        "end": {"dateTime": "2025-03-01T09:30:00Z"},
        "recurringEventId": "base_evt",
    }
    doc = connector._event_to_document(event, "primary")
    assert doc is not None
    assert doc.metadata.get("recurring") is True


async def test_health_check_no_service(connector):
    result = await connector.health_check()
    assert result is False
