from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from mneia.core.connector import BaseConnector, ConnectorManifest

_BUILTIN_CONNECTORS: dict[str, type[BaseConnector]] = {}
_MANIFESTS: dict[str, ConnectorManifest] = {}


def _register(cls: type[BaseConnector]) -> None:
    manifest = cls.manifest
    _BUILTIN_CONNECTORS[manifest.name] = cls
    _MANIFESTS[manifest.name] = manifest


def _discover_builtins() -> None:
    if _BUILTIN_CONNECTORS:
        return

    from mneia.connectors.obsidian import ObsidianConnector

    _register(ObsidianConnector)

    # Future built-in connectors registered here as they are implemented:
    # from mneia.connectors.google_calendar import GoogleCalendarConnector
    # _register(GoogleCalendarConnector)


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


def get_available_connectors() -> list[ConnectorManifest]:
    _discover_builtins()
    _discover_third_party()
    return list(_MANIFESTS.values())


def get_connector_manifest(name: str) -> ConnectorManifest | None:
    _discover_builtins()
    _discover_third_party()
    return _MANIFESTS.get(name)


def create_connector(name: str) -> BaseConnector | None:
    _discover_builtins()
    _discover_third_party()
    cls = _BUILTIN_CONNECTORS.get(name)
    if cls:
        return cls()
    return None
