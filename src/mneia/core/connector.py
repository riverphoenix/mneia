from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator


class ConnectorMode(str, Enum):
    POLL = "poll"
    WATCH = "watch"
    ONDEMAND = "ondemand"


@dataclass
class ConnectorManifest:
    name: str
    display_name: str
    version: str
    description: str
    author: str
    mode: ConnectorMode
    auth_type: str
    scopes: list[str] = field(default_factory=list)
    poll_interval_seconds: int = 300
    required_config: list[str] = field(default_factory=list)
    optional_config: list[str] = field(default_factory=list)


@dataclass
class RawDocument:
    source: str
    source_id: str
    content: str
    content_type: str
    title: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    url: str | None = None
    participants: list[str] = field(default_factory=list)


class BaseConnector(ABC):
    manifest: ConnectorManifest

    @abstractmethod
    async def authenticate(self, config: dict[str, Any]) -> bool:
        ...

    @abstractmethod
    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        settings: dict[str, Any] = {}
        for key in self.manifest.required_config:
            value = typer.prompt(f"  {key}")
            settings[key] = value
        for key in self.manifest.optional_config:
            value = typer.prompt(f"  {key} (optional)", default="")
            if value:
                settings[key] = value
        return settings
