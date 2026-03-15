from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from mneia.core.connector import BaseConnector, ConnectorManifest

_BUILTIN_CONNECTORS: dict[str, type[BaseConnector]] = {}
_MANIFESTS: dict[str, ConnectorManifest] = {}

MULTI_ACCOUNT_CONNECTORS = {"gmail", "google-drive", "google-calendar"}


def _register(cls: type[BaseConnector]) -> None:
    manifest = cls.manifest
    _BUILTIN_CONNECTORS[manifest.name] = cls
    _MANIFESTS[manifest.name] = manifest


def _discover_builtins() -> None:
    if _BUILTIN_CONNECTORS:
        return

    from mneia.connectors.obsidian import ObsidianConnector

    _register(ObsidianConnector)

    from mneia.connectors.google_calendar import GoogleCalendarConnector
    from mneia.connectors.google_drive import GoogleDriveConnector
    from mneia.connectors.google_gmail import GmailConnector

    _register(GoogleCalendarConnector)
    _register(GmailConnector)
    _register(GoogleDriveConnector)

    from mneia.connectors.apple_notes import AppleNotesConnector
    from mneia.connectors.asana import AsanaConnector
    from mneia.connectors.chrome_history import ChromeHistoryConnector
    from mneia.connectors.confluence import ConfluenceConnector
    from mneia.connectors.jira import JiraConnector
    from mneia.connectors.notion import NotionConnector
    from mneia.connectors.zoom import ZoomConnector

    _register(AppleNotesConnector)
    _register(AsanaConnector)
    _register(JiraConnector)
    _register(ConfluenceConnector)
    _register(NotionConnector)
    _register(ZoomConnector)
    _register(ChromeHistoryConnector)

    from mneia.connectors.audio_transcription import AudioTranscriptionConnector
    from mneia.connectors.github import GitHubConnector
    from mneia.connectors.granola import GranolaConnector
    from mneia.connectors.linear import LinearConnector
    from mneia.connectors.local_folders import LocalFoldersConnector
    from mneia.connectors.slack import SlackConnector
    from mneia.connectors.todoist import TodoistConnector

    _register(AudioTranscriptionConnector)
    _register(GitHubConnector)
    _register(GranolaConnector)
    _register(LinearConnector)
    _register(LocalFoldersConnector)
    _register(SlackConnector)
    _register(TodoistConnector)


def _discover_third_party() -> None:
    try:
        from importlib.metadata import entry_points as _ep

        eps = _ep(group="mneia.connectors")
    except TypeError:
        eps = entry_points().get("mneia.connectors", [])  # type: ignore[assignment]
    group = eps
    for ep in group:
        try:
            cls = ep.load()
            _register(cls)
        except Exception:
            pass


def _resolve_base_connector(name: str) -> str | None:
    if name in _BUILTIN_CONNECTORS:
        return name
    for base in MULTI_ACCOUNT_CONNECTORS:
        if name.startswith(f"{base}-") and len(name) > len(base) + 1:
            return base
    return None


def get_available_connectors() -> list[ConnectorManifest]:
    _discover_builtins()
    _discover_third_party()
    return list(_MANIFESTS.values())


def get_connector_manifest(name: str) -> ConnectorManifest | None:
    _discover_builtins()
    _discover_third_party()
    base = _resolve_base_connector(name)
    if base:
        return _MANIFESTS.get(base)
    return _MANIFESTS.get(name)


def create_connector(name: str) -> BaseConnector | None:
    _discover_builtins()
    _discover_third_party()
    base = _resolve_base_connector(name)
    if base:
        cls = _BUILTIN_CONNECTORS[base]
        return cls()
    cls = _BUILTIN_CONNECTORS.get(name)
    if cls:
        return cls()
    return None
