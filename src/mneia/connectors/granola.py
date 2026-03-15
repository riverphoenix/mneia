from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)

DEFAULT_GRANOLA_DIR = "~/Documents/Personal/Notes/Granola"


class GranolaConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="granola",
        display_name="Granola Meeting Notes",
        version="0.1.0",
        description="Read meeting notes from Granola (markdown files with YAML frontmatter)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="local",
        scopes=[],
        poll_interval_seconds=120,
        required_config=[],
        optional_config=["notes_dir"],
        watch_paths_config_key="notes_dir",
        watch_extensions=[".md"],
    )

    def __init__(self) -> None:
        self._notes_dir: Path | None = None

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self.last_error = ""
        notes_dir = config.get("notes_dir", DEFAULT_GRANOLA_DIR)
        path = Path(notes_dir).expanduser().resolve()

        if not path.exists():
            self.last_error = f"Granola notes directory not found: {path}"
            return False

        if not path.is_dir():
            self.last_error = f"Path is not a directory: {path}"
            return False

        self._notes_dir = path
        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._notes_dir:
            return

        for md_file in sorted(self._notes_dir.glob("*.md")):
            if since:
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc)
                if mtime <= since:
                    continue

            doc = self._parse_note(md_file)
            if doc:
                yield doc

    async def health_check(self) -> bool:
        if not self._notes_dir:
            return False
        return self._notes_dir.exists() and self._notes_dir.is_dir()

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Granola Meeting Notes")
        typer.echo("  ─" * 25)
        typer.echo(
            "\n  Granola exports meeting notes as markdown files."
        )
        typer.echo(
            "  Point mneia to the directory where Granola saves notes.\n"
        )

        default = DEFAULT_GRANOLA_DIR
        expanded = Path(default).expanduser()
        if expanded.exists():
            typer.echo(f"  Found Granola notes at: {expanded}")

        notes_dir = typer.prompt("  Notes directory", default=default)
        path = Path(notes_dir).expanduser().resolve()

        if path.exists():
            count = len(list(path.glob("*.md")))
            typer.echo(f"  ✓ Found {count} note(s)")
        else:
            typer.echo("  ⚠ Directory does not exist yet")

        return {"notes_dir": str(path)}

    def _parse_note(self, path: Path) -> RawDocument | None:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read {path.name}: {e}")
            return None

        if not text.strip():
            return None

        frontmatter, body = self._split_frontmatter(text)

        granola_id = frontmatter.get("granola_id", path.stem)
        title = frontmatter.get("title", path.stem.replace("_", " "))
        granola_url = frontmatter.get("granola_url", "")
        created_at = frontmatter.get("created_at", "")
        updated_at = frontmatter.get("updated_at", "")
        tags = frontmatter.get("tags", [])

        if created_at:
            try:
                timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                timestamp = datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc,
                )
        else:
            timestamp = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc,
            )

        participants = []
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.startswith("person/"):
                    participants.append(tag.removeprefix("person/"))

        metadata: dict[str, Any] = {
            "granola_id": granola_id,
            "file_name": path.name,
        }
        if updated_at:
            metadata["updated_at"] = updated_at
        if tags:
            metadata["tags"] = tags

        return RawDocument(
            source="granola",
            source_id=granola_id,
            content=body if body else text,
            content_type="meeting_notes",
            title=title,
            timestamp=timestamp,
            metadata=metadata,
            url=granola_url or None,
            participants=participants,
        )

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text

        fm_text = match.group(1)
        body = match.group(2)

        fm: dict[str, Any] = {}
        current_key = ""
        current_list: list[str] | None = None

        for line in fm_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("- ") and current_list is not None:
                current_list.append(stripped[2:].strip())
                continue

            if current_list is not None:
                fm[current_key] = current_list
                current_list = None

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if not val:
                    current_key = key
                    current_list = []
                else:
                    fm[key] = val

        if current_list is not None:
            fm[current_key] = current_list

        return fm, body
