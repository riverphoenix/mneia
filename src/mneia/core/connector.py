from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
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
    watch_paths_config_key: str | None = None
    watch_extensions: list[str] = field(default_factory=list)


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

    async def fetch_changed(
        self, changed_paths: list[Path],
    ) -> AsyncIterator[RawDocument]:
        """Process specific changed files. Default: falls back to fetch_since."""
        async for doc in self.fetch_since(None):
            yield doc

    def get_watch_path(self, config: dict[str, Any]) -> Path | None:
        """Return the path to watch for changes, or None if not watchable."""
        key = self.manifest.watch_paths_config_key
        if key and key in config:
            p = Path(config[key]).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p
        return None

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

    def _verify_setup(self, settings: dict[str, Any]) -> None:
        """Test credentials immediately after setup and print the result. Never raises."""
        import asyncio
        import typer

        typer.echo("\n  Verifying credentials...")
        try:
            ok = asyncio.run(self.authenticate(settings))
        except Exception:
            ok = False

        if ok:
            typer.echo(f"  {self.manifest.display_name} credentials verified.\n")
        else:
            typer.echo(
                f"  [WARNING] Could not connect to {self.manifest.display_name}.\n"
                "  Check your credentials and try /connector-setup again.\n"
                "  Credentials saved — re-run /connector-setup with correct credentials.\n"
            )
