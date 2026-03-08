from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mneia.connectors.chrome_history import (
    ChromeHistoryConnector,
    _chrome_time_to_datetime,
    _default_chrome_history_path,
)


@pytest.fixture
def connector():
    return ChromeHistoryConnector()


def test_manifest():
    c = ChromeHistoryConnector()
    assert c.manifest.name == "chrome-history"
    assert c.manifest.auth_type == "local"


def test_default_chrome_history_path():
    path = _default_chrome_history_path()
    assert path is not None
    assert "Chrome" in str(path) or "chrome" in str(path)


def test_chrome_time_to_datetime():
    ts = 13350000000000000
    dt = _chrome_time_to_datetime(ts)
    assert dt.year > 2020
    assert dt.tzinfo == timezone.utc


def test_chrome_time_zero():
    dt = _chrome_time_to_datetime(0)
    assert dt.year >= 2025


async def test_authenticate_no_path(connector, tmp_path):
    result = await connector.authenticate({"history_path": str(tmp_path / "nonexistent")})
    assert result is False


async def test_authenticate_with_path(connector, tmp_path):
    history_file = tmp_path / "History"
    history_file.touch()
    result = await connector.authenticate({"history_path": str(history_file)})
    assert result is True
    assert connector._history_path == history_file


async def test_authenticate_max_results(connector, tmp_path):
    history_file = tmp_path / "History"
    history_file.touch()
    await connector.authenticate({
        "history_path": str(history_file),
        "max_results": "50",
    })
    assert connector._max_results == 50


async def test_health_check_no_path(connector):
    result = await connector.health_check()
    assert result is False


async def test_health_check_with_path(connector, tmp_path):
    history_file = tmp_path / "History"
    history_file.touch()
    connector._history_path = history_file
    result = await connector.health_check()
    assert result is True


def test_row_to_document():
    class FakeRow:
        def __getitem__(self, key):
            data = {
                "id": 1,
                "url": "https://example.com/page",
                "title": "Example Page",
                "visit_count": 5,
                "typed_count": 2,
                "last_visit_time": 13350000000000000,
            }
            return data[key]

    doc = ChromeHistoryConnector._row_to_document(FakeRow())
    assert doc is not None
    assert doc.source == "chrome-history"
    assert doc.source_id == "1"
    assert doc.title == "Example Page"
    assert "https://example.com/page" in doc.content
    assert doc.url == "https://example.com/page"
    assert doc.metadata["visit_count"] == 5


def test_row_to_document_no_url():
    class FakeRow:
        def __getitem__(self, key):
            data = {
                "id": 2,
                "url": "",
                "title": "",
                "visit_count": 0,
                "typed_count": 0,
                "last_visit_time": 0,
            }
            return data[key]

    doc = ChromeHistoryConnector._row_to_document(FakeRow())
    assert doc is None


async def test_fetch_since_with_real_db(connector, tmp_path):
    db_path = tmp_path / "History"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE urls (
            id INTEGER PRIMARY KEY,
            url TEXT,
            title TEXT,
            visit_count INTEGER DEFAULT 0,
            typed_count INTEGER DEFAULT 0,
            last_visit_time INTEGER DEFAULT 0
        )
    """)
    conn.execute(
        "INSERT INTO urls (id, url, title, visit_count, typed_count, last_visit_time) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "https://example.com", "Example", 3, 1, 13350000000000000),
    )
    conn.execute(
        "INSERT INTO urls (id, url, title, visit_count, typed_count, last_visit_time) VALUES (?, ?, ?, ?, ?, ?)",
        (2, "https://github.com", "GitHub", 10, 5, 13350000000000000),
    )
    conn.commit()
    conn.close()

    connector._history_path = db_path
    connector._max_results = 10

    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)

    assert len(docs) == 2
    assert any(d.title == "Example" for d in docs)
    assert any(d.title == "GitHub" for d in docs)
