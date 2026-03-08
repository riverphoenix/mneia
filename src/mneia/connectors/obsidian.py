from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import typer

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)


class ObsidianConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="obsidian",
        display_name="Obsidian",
        version="0.1.0",
        description="Read notes from an Obsidian vault (markdown files on disk)",
        author="mneia-team",
        mode=ConnectorMode.WATCH,
        auth_type="local",
        scopes=["filesystem:read"],
        poll_interval_seconds=60,
        required_config=["vault_path"],
        optional_config=["exclude_folders", "include_extensions"],
        watch_paths_config_key="vault_path",
        watch_extensions=[".md"],
    )

    def __init__(self) -> None:
        self._vault_path: Path | None = None
        self._exclude_folders: set[str] = set()
        self._include_extensions: set[str] = {".md"}

    async def authenticate(self, config: dict[str, Any]) -> bool:
        vault_path = config.get("vault_path", "")
        if not vault_path:
            return False

        path = Path(vault_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            logger.error(f"Vault path does not exist: {path}")
            return False

        self._vault_path = path

        exclude = config.get("exclude_folders", "")
        if exclude:
            self._exclude_folders = {f.strip() for f in exclude.split(",") if f.strip()}

        extensions = config.get("include_extensions", "")
        if extensions:
            self._include_extensions = {e.strip() for e in extensions.split(",") if e.strip()}

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._vault_path:
            return

        for file_path in self._vault_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix not in self._include_extensions:
                continue
            if self._is_excluded(file_path):
                continue

            stat = file_path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime)

            if since and modified <= since:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                logger.warning(f"Could not read: {file_path}")
                continue

            relative = file_path.relative_to(self._vault_path)
            source_id = hashlib.md5(str(relative).encode()).hexdigest()

            title = file_path.stem
            content_type = "note"

            frontmatter, body = self._parse_frontmatter(content)
            if "title" in frontmatter:
                title = frontmatter["title"]
            elif body:
                heading = self._extract_first_heading(body)
                if heading:
                    title = heading
            else:
                heading = self._extract_first_heading(content)
                if heading:
                    title = heading

            metadata: dict[str, Any] = {
                "relative_path": str(relative),
                "folder": str(relative.parent),
                "extension": file_path.suffix,
            }
            if frontmatter:
                metadata["frontmatter"] = frontmatter

            tags = self._extract_tags(content)
            if tags:
                metadata["tags"] = tags

            wikilinks = self._extract_wikilinks(content)
            if wikilinks:
                metadata["wikilinks"] = wikilinks

            yield RawDocument(
                source="obsidian",
                source_id=source_id,
                content=body or content,
                content_type=content_type,
                title=title,
                timestamp=modified,
                metadata=metadata,
                url=f"obsidian://open?vault={self._vault_path.name}&file={relative}",
            )

    async def fetch_changed(
        self, changed_paths: list[Path],
    ) -> AsyncIterator[RawDocument]:
        if not self._vault_path:
            return

        for file_path in changed_paths:
            if not file_path.is_file():
                continue
            if file_path.suffix not in self._include_extensions:
                continue
            if self._is_excluded(file_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                logger.warning(f"Could not read: {file_path}")
                continue

            relative = file_path.relative_to(self._vault_path)
            source_id = hashlib.md5(str(relative).encode()).hexdigest()

            title = file_path.stem
            frontmatter, body = self._parse_frontmatter(content)
            if "title" in frontmatter:
                title = frontmatter["title"]
            elif body:
                heading = self._extract_first_heading(body)
                if heading:
                    title = heading
            else:
                heading = self._extract_first_heading(content)
                if heading:
                    title = heading

            stat = file_path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime)

            metadata: dict[str, Any] = {
                "relative_path": str(relative),
                "folder": str(relative.parent),
                "extension": file_path.suffix,
            }
            if frontmatter:
                metadata["frontmatter"] = frontmatter
            tags = self._extract_tags(content)
            if tags:
                metadata["tags"] = tags
            wikilinks = self._extract_wikilinks(content)
            if wikilinks:
                metadata["wikilinks"] = wikilinks

            yield RawDocument(
                source="obsidian",
                source_id=source_id,
                content=body or content,
                content_type="note",
                title=title,
                timestamp=modified,
                metadata=metadata,
                url=(
                    f"obsidian://open?vault="
                    f"{self._vault_path.name}&file={relative}"
                ),
            )

    async def health_check(self) -> bool:
        return self._vault_path is not None and self._vault_path.exists()

    def interactive_setup(self) -> dict[str, Any]:
        vault_path = typer.prompt("  Path to Obsidian vault")
        path = Path(vault_path).expanduser().resolve()
        if not path.exists():
            typer.echo(f"  Warning: {path} does not exist")

        exclude = typer.prompt("  Folders to exclude (comma-separated, optional)", default="")
        settings: dict[str, Any] = {"vault_path": str(path)}
        if exclude:
            settings["exclude_folders"] = exclude
        return settings

    def _is_excluded(self, file_path: Path) -> bool:
        if not self._vault_path:
            return True
        relative = file_path.relative_to(self._vault_path)
        parts = relative.parts
        for folder in self._exclude_folders:
            if folder in parts:
                return True
        if any(p.startswith(".") for p in parts):
            return True
        return False

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        if not content.startswith("---"):
            return {}, content

        end = content.find("---", 3)
        if end < 0:
            return {}, content

        fm_text = content[3:end].strip()
        body = content[end + 3:].strip()

        frontmatter: dict[str, Any] = {}
        for line in fm_text.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip()

        return frontmatter, body

    def _extract_first_heading(self, content: str) -> str | None:
        import re

        match = re.match(r"^#\s+(.+)$", content.strip(), re.MULTILINE)
        return match.group(1).strip() if match else None

    def _extract_tags(self, content: str) -> list[str]:
        import re

        return re.findall(r"(?:^|\s)#([a-zA-Z0-9_/-]+)", content)

    def _extract_wikilinks(self, content: str) -> list[str]:
        import re

        return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
