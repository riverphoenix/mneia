from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from mneia.config import ConnectorConfig, MneiaConfig
from mneia.core.connector import ConnectorManifest, ConnectorMode, RawDocument
from mneia.pipeline.ingest import ingest_connector


def _make_connector(authenticated=False, auth_result=True):
    connector = MagicMock()
    connector.manifest = ConnectorManifest(
        name="test",
        display_name="Test",
        version="0.1.0",
        description="test connector",
        author="test",
        mode=ConnectorMode.POLL,
        auth_type="none",
    )
    connector.authenticate = AsyncMock(return_value=auth_result)
    if authenticated:
        connector._authenticated = True
    else:
        connector._authenticated = False

    async def empty_fetch(since):
        return
        yield

    connector.fetch_since = empty_fetch
    return connector


def _make_config():
    return ConnectorConfig(
        connector_type="test",
        enabled=True,
        settings={},
    )


async def test_ingest_skips_auth_when_already_authenticated():
    connector = _make_connector(authenticated=True)
    conn_config = _make_config()
    config = MneiaConfig()

    with patch("mneia.pipeline.ingest.MemoryStore") as mock_store_cls:
        mock_store = mock_store_cls.return_value
        mock_store.get_checkpoint = AsyncMock(return_value=None)
        mock_store.set_checkpoint = AsyncMock()
        mock_store.store_document = AsyncMock(return_value=1)

        result = await ingest_connector(connector, conn_config, config)

    connector.authenticate.assert_not_called()
    assert result.documents_ingested == 0


async def test_ingest_authenticates_when_not_cached():
    connector = _make_connector(authenticated=False, auth_result=True)
    conn_config = _make_config()
    config = MneiaConfig()

    with patch("mneia.pipeline.ingest.MemoryStore") as mock_store_cls:
        mock_store = mock_store_cls.return_value
        mock_store.get_checkpoint = AsyncMock(return_value=None)
        mock_store.set_checkpoint = AsyncMock()

        result = await ingest_connector(connector, conn_config, config)

    connector.authenticate.assert_called_once_with(conn_config.settings)
    assert connector._authenticated is True


async def test_ingest_auth_failure_returns_error():
    connector = _make_connector(authenticated=False, auth_result=False)
    conn_config = _make_config()
    config = MneiaConfig()

    with patch("mneia.pipeline.ingest.MemoryStore") as mock_store_cls:
        mock_store = mock_store_cls.return_value
        mock_store.get_checkpoint = AsyncMock(return_value=None)

        result = await ingest_connector(connector, conn_config, config)

    assert result.documents_ingested == 0
    assert len(result.errors) == 1
    assert "Authentication failed" in result.errors[0]


async def test_ingest_stores_documents():
    connector = _make_connector(authenticated=True)

    doc = RawDocument(
        source="test",
        source_id="doc1",
        content="hello world",
        content_type="text",
        title="Test Doc",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        metadata={},
    )

    async def fetch_with_doc(since):
        yield doc

    connector.fetch_since = fetch_with_doc
    conn_config = _make_config()
    config = MneiaConfig()

    with patch("mneia.pipeline.ingest.MemoryStore") as mock_store_cls:
        mock_store = mock_store_cls.return_value
        mock_store.get_checkpoint = AsyncMock(return_value=None)
        mock_store.set_checkpoint = AsyncMock()
        mock_store.store_document = AsyncMock(return_value=1)

        result = await ingest_connector(connector, conn_config, config)

    assert result.documents_ingested == 1
    mock_store.store_document.assert_called_once_with(doc)
