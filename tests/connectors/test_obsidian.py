from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mneia.connectors.obsidian import ObsidianConnector


@pytest.fixture
def connector() -> ObsidianConnector:
    return ObsidianConnector()


@pytest.mark.asyncio
async def test_authenticate_valid_path(connector: ObsidianConnector, obsidian_vault: Path):
    result = await connector.authenticate({"vault_path": str(obsidian_vault)})
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_invalid_path(connector: ObsidianConnector):
    result = await connector.authenticate({"vault_path": "/nonexistent/path"})
    assert result is False


@pytest.mark.asyncio
async def test_authenticate_missing_path(connector: ObsidianConnector):
    result = await connector.authenticate({})
    assert result is False


@pytest.mark.asyncio
async def test_fetch_all(connector: ObsidianConnector, obsidian_vault: Path):
    await connector.authenticate({"vault_path": str(obsidian_vault)})

    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)

    assert len(docs) == 3
    sources = {d.source for d in docs}
    assert sources == {"obsidian"}

    titles = {d.title for d in docs}
    assert "Meeting Notes" in titles
    assert "Weekly Review" in titles
    assert "Project Alpha" in titles


@pytest.mark.asyncio
async def test_fetch_since_filters(connector: ObsidianConnector, obsidian_vault: Path):
    await connector.authenticate({"vault_path": str(obsidian_vault)})

    future = datetime(2099, 1, 1)
    docs = []
    async for doc in connector.fetch_since(future):
        docs.append(doc)

    assert len(docs) == 0


@pytest.mark.asyncio
async def test_excludes_hidden_folders(connector: ObsidianConnector, obsidian_vault: Path):
    await connector.authenticate({"vault_path": str(obsidian_vault)})

    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)

    paths = [d.metadata.get("relative_path", "") for d in docs]
    for p in paths:
        assert not p.startswith(".obsidian")


@pytest.mark.asyncio
async def test_extracts_tags(connector: ObsidianConnector, obsidian_vault: Path):
    await connector.authenticate({"vault_path": str(obsidian_vault)})

    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)

    weekly_doc = next(d for d in docs if d.title == "Weekly Review")
    tags = weekly_doc.metadata.get("tags", [])
    assert "weekly" in tags
    assert "review" in tags


@pytest.mark.asyncio
async def test_extracts_wikilinks(connector: ObsidianConnector, obsidian_vault: Path):
    await connector.authenticate({"vault_path": str(obsidian_vault)})

    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)

    alpha_doc = next(d for d in docs if d.title == "Project Alpha")
    wikilinks = alpha_doc.metadata.get("wikilinks", [])
    assert "John Smith" in wikilinks


@pytest.mark.asyncio
async def test_parses_frontmatter(connector: ObsidianConnector, obsidian_vault: Path):
    await connector.authenticate({"vault_path": str(obsidian_vault)})

    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)

    meeting_doc = next(d for d in docs if d.title == "Meeting Notes")
    assert meeting_doc.title == "Meeting Notes"
    assert "frontmatter" in meeting_doc.metadata


@pytest.mark.asyncio
async def test_exclude_folders(connector: ObsidianConnector, obsidian_vault: Path):
    await connector.authenticate({
        "vault_path": str(obsidian_vault),
        "exclude_folders": "projects",
    })

    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)

    assert len(docs) == 2
    for doc in docs:
        assert "projects" not in doc.metadata.get("relative_path", "")


@pytest.mark.asyncio
async def test_health_check(connector: ObsidianConnector, obsidian_vault: Path):
    assert await connector.health_check() is False

    await connector.authenticate({"vault_path": str(obsidian_vault)})
    assert await connector.health_check() is True
