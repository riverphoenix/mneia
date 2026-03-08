from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)


def test_connector_manifest_watch_fields():
    manifest = ConnectorManifest(
        name="test",
        display_name="Test",
        version="0.1.0",
        description="Test connector",
        author="test",
        mode=ConnectorMode.WATCH,
        auth_type="local",
        watch_paths_config_key="vault_path",
        watch_extensions=[".md", ".txt"],
    )
    assert manifest.watch_paths_config_key == "vault_path"
    assert manifest.watch_extensions == [".md", ".txt"]


def test_connector_manifest_defaults():
    manifest = ConnectorManifest(
        name="test",
        display_name="Test",
        version="0.1.0",
        description="Test",
        author="test",
        mode=ConnectorMode.POLL,
        auth_type="api_key",
    )
    assert manifest.watch_paths_config_key is None
    assert manifest.watch_extensions == []


def test_get_watch_path_returns_path(tmp_path):
    from mneia.connectors.obsidian import ObsidianConnector

    connector = ObsidianConnector()
    path = connector.get_watch_path({"vault_path": str(tmp_path)})
    assert path == tmp_path


def test_get_watch_path_returns_none_missing_key():
    from mneia.connectors.obsidian import ObsidianConnector

    connector = ObsidianConnector()
    path = connector.get_watch_path({})
    assert path is None


def test_get_watch_path_returns_none_nonexistent():
    from mneia.connectors.obsidian import ObsidianConnector

    connector = ObsidianConnector()
    path = connector.get_watch_path(
        {"vault_path": "/nonexistent/path/that/does/not/exist"}
    )
    assert path is None


async def test_obsidian_fetch_changed(tmp_path):
    from mneia.connectors.obsidian import ObsidianConnector

    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "test.md"
    note.write_text("# Hello\nWorld", encoding="utf-8")

    connector = ObsidianConnector()
    await connector.authenticate({"vault_path": str(vault)})

    docs = []
    async for doc in connector.fetch_changed([note]):
        docs.append(doc)

    assert len(docs) == 1
    assert docs[0].title == "Hello"
    assert docs[0].source == "obsidian"
    assert "World" in docs[0].content


async def test_obsidian_fetch_changed_skips_excluded(tmp_path):
    from mneia.connectors.obsidian import ObsidianConnector

    vault = tmp_path / "vault"
    vault.mkdir()
    hidden = vault / ".obsidian"
    hidden.mkdir()
    config_file = hidden / "config.md"
    config_file.write_text("config", encoding="utf-8")

    connector = ObsidianConnector()
    await connector.authenticate({"vault_path": str(vault)})

    docs = []
    async for doc in connector.fetch_changed([config_file]):
        docs.append(doc)

    assert len(docs) == 0


async def test_obsidian_fetch_changed_skips_non_md(tmp_path):
    from mneia.connectors.obsidian import ObsidianConnector

    vault = tmp_path / "vault"
    vault.mkdir()
    img = vault / "image.png"
    img.write_bytes(b"\x89PNG")

    connector = ObsidianConnector()
    await connector.authenticate({"vault_path": str(vault)})

    docs = []
    async for doc in connector.fetch_changed([img]):
        docs.append(doc)

    assert len(docs) == 0


async def test_obsidian_fetch_changed_multiple_files(tmp_path):
    from mneia.connectors.obsidian import ObsidianConnector

    vault = tmp_path / "vault"
    vault.mkdir()
    files = []
    for i in range(3):
        f = vault / f"note{i}.md"
        f.write_text(f"# Note {i}\nContent {i}", encoding="utf-8")
        files.append(f)

    connector = ObsidianConnector()
    await connector.authenticate({"vault_path": str(vault)})

    docs = []
    async for doc in connector.fetch_changed(files):
        docs.append(doc)

    assert len(docs) == 3
    titles = {d.title for d in docs}
    assert "Note 0" in titles
    assert "Note 1" in titles
    assert "Note 2" in titles


async def test_listener_selects_watch_mode():
    from mneia.agents.listener import ListenerAgent
    from mneia.config import ConnectorConfig, MneiaConfig

    connector = MagicMock()
    connector.manifest = ConnectorManifest(
        name="obsidian",
        display_name="Obsidian",
        version="0.1.0",
        description="Test",
        author="test",
        mode=ConnectorMode.WATCH,
        auth_type="local",
        watch_paths_config_key="vault_path",
        watch_extensions=[".md"],
    )

    config = MneiaConfig()
    conn_config = ConnectorConfig(
        enabled=True,
        settings={"vault_path": "/tmp"},
    )

    agent = ListenerAgent(
        name="listener-obsidian",
        connector=connector,
        config=config,
        connector_config=conn_config,
    )

    assert connector.manifest.mode == ConnectorMode.WATCH
    assert connector.manifest.watch_paths_config_key == "vault_path"


async def test_listener_selects_poll_for_api_connectors():
    from mneia.agents.listener import ListenerAgent
    from mneia.config import ConnectorConfig, MneiaConfig

    connector = MagicMock()
    connector.manifest = ConnectorManifest(
        name="gmail",
        display_name="Gmail",
        version="0.1.0",
        description="Test",
        author="test",
        mode=ConnectorMode.POLL,
        auth_type="oauth2",
    )

    config = MneiaConfig()
    conn_config = ConnectorConfig(enabled=True)

    agent = ListenerAgent(
        name="listener-gmail",
        connector=connector,
        config=config,
        connector_config=conn_config,
    )

    assert connector.manifest.mode == ConnectorMode.POLL
    assert connector.manifest.watch_paths_config_key is None
