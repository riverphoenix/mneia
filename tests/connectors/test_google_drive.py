from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mneia.connectors.google_drive import GoogleDriveConnector


@pytest.fixture
def connector():
    return GoogleDriveConnector()


def test_manifest():
    c = GoogleDriveConnector()
    assert c.manifest.name == "google-drive"
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


async def test_fetch_file_content_google_doc(connector):
    connector._service = MagicMock()

    mock_export = MagicMock()
    mock_export.execute.return_value = b"This is my document content."
    connector._service.files.return_value.export.return_value = mock_export

    file_meta = {
        "id": "file123",
        "name": "My Doc",
        "mimeType": "application/vnd.google-apps.document",
        "modifiedTime": "2025-03-01T10:00:00Z",
        "owners": [{"displayName": "Alice"}],
        "webViewLink": "https://docs.google.com/doc/file123",
    }

    doc = await connector._fetch_file_content(file_meta)
    assert doc is not None
    assert doc.source == "google-drive"
    assert doc.source_id == "file123"
    assert doc.title == "My Doc"
    assert "document content" in doc.content
    assert doc.content_type == "doc"
    assert "Alice" in doc.participants


async def test_fetch_file_content_plain_text(connector):
    connector._service = MagicMock()

    mock_media = MagicMock()
    mock_media.execute.return_value = b"Some plain text file."
    connector._service.files.return_value.get_media.return_value = mock_media

    file_meta = {
        "id": "file456",
        "name": "notes.txt",
        "mimeType": "text/plain",
        "modifiedTime": "2025-03-02T12:00:00Z",
        "owners": [],
    }

    doc = await connector._fetch_file_content(file_meta)
    assert doc is not None
    assert doc.title == "notes.txt"
    assert doc.content_type == "document"


async def test_fetch_file_content_empty(connector):
    connector._service = MagicMock()

    mock_export = MagicMock()
    mock_export.execute.return_value = b""
    connector._service.files.return_value.export.return_value = mock_export

    file_meta = {
        "id": "file_empty",
        "name": "Empty Doc",
        "mimeType": "application/vnd.google-apps.document",
        "modifiedTime": "2025-03-01T10:00:00Z",
    }

    doc = await connector._fetch_file_content(file_meta)
    assert doc is None


async def test_fetch_file_content_truncation(connector):
    connector._service = MagicMock()

    mock_export = MagicMock()
    mock_export.execute.return_value = ("x" * 60000).encode()
    connector._service.files.return_value.export.return_value = mock_export

    file_meta = {
        "id": "file_big",
        "name": "Large Doc",
        "mimeType": "application/vnd.google-apps.document",
        "modifiedTime": "2025-03-01T10:00:00Z",
    }

    doc = await connector._fetch_file_content(file_meta)
    assert doc is not None
    assert len(doc.content) <= 50100
    assert "[Content truncated]" in doc.content


async def test_fetch_file_content_unsupported_mime(connector):
    connector._service = MagicMock()

    file_meta = {
        "id": "file_img",
        "name": "photo.jpg",
        "mimeType": "image/jpeg",
        "modifiedTime": "2025-03-01T10:00:00Z",
    }

    doc = await connector._fetch_file_content(file_meta)
    assert doc is None


async def test_health_check_no_service(connector):
    result = await connector.health_check()
    assert result is False


async def test_health_check_with_service(connector):
    connector._service = MagicMock()
    mock_about = MagicMock()
    mock_about.execute.return_value = {"user": {"displayName": "Test"}}
    connector._service.about.return_value.get.return_value = mock_about

    result = await connector.health_check()
    assert result is True
