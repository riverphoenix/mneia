from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from mneia.connectors.google_gmail import GmailConnector


@pytest.fixture
def connector():
    return GmailConnector()


def test_manifest():
    c = GmailConnector()
    assert c.manifest.name == "gmail"
    assert c.manifest.auth_type == "oauth2"
    assert "readonly" in c.manifest.scopes[0]


async def test_authenticate_no_credentials(connector, monkeypatch):
    import mneia.connectors.google_auth as ga
    monkeypatch.setattr(ga, "get_google_credentials", lambda *a, **kw: (_ for _ in ()).throw(Exception("no creds")))
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_missing_secret(connector, monkeypatch):
    import mneia.connectors.google_auth as ga
    monkeypatch.setattr(ga, "get_google_credentials", lambda *a, **kw: (_ for _ in ()).throw(Exception("no creds")))
    result = await connector.authenticate({"google_client_id": "id"})
    assert result is False


def test_strip_html():
    html = "<p>Hello <b>World</b></p><br/>Next line"
    result = GmailConnector._strip_html(html)
    assert "Hello" in result
    assert "World" in result
    assert "<b>" not in result
    assert "<p>" not in result


def test_strip_html_entities():
    html = "A &amp; B &lt;C&gt; D&nbsp;E"
    result = GmailConnector._strip_html(html)
    assert "A & B" in result
    assert "<C>" in result


def test_parse_addresses_named():
    result = GmailConnector._parse_addresses('"Alice Smith" <alice@example.com>, Bob <bob@example.com>')
    assert "Alice Smith" in result
    assert "Bob" in result


def test_parse_addresses_email_only():
    result = GmailConnector._parse_addresses("alice@example.com")
    assert "alice@example.com" in result


def test_parse_addresses_empty():
    result = GmailConnector._parse_addresses("")
    assert result == []


def test_extract_body_plain(connector):
    import base64

    text = "Hello, this is a test email."
    encoded = base64.urlsafe_b64encode(text.encode()).decode()
    payload = {"mimeType": "text/plain", "body": {"data": encoded}}
    result = connector._extract_body(payload)
    assert result == text


def test_extract_body_html(connector):
    import base64

    html = "<p>Hello <b>World</b></p>"
    encoded = base64.urlsafe_b64encode(html.encode()).decode()
    payload = {"mimeType": "text/html", "body": {"data": encoded}}
    result = connector._extract_body(payload)
    assert "Hello" in result
    assert "World" in result
    assert "<b>" not in result


def test_extract_body_multipart(connector):
    import base64

    text = "Plain text content"
    encoded = base64.urlsafe_b64encode(text.encode()).decode()
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": encoded}},
        ],
    }
    result = connector._extract_body(payload)
    assert result == text


def test_extract_body_empty(connector):
    payload = {"mimeType": "application/octet-stream", "body": {}}
    result = connector._extract_body(payload)
    assert result == ""


async def test_health_check_no_service(connector):
    result = await connector.health_check()
    assert result is False
