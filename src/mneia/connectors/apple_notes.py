from __future__ import annotations

import hashlib
import logging
import platform
import re
import subprocess
from datetime import datetime
from typing import Any, AsyncIterator

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)

APPLESCRIPT_LIST = '''
tell application "Notes"
    set noteList to {}
    repeat with n in notes
        set noteId to id of n
        set noteName to name of n
        set noteBody to body of n
        set noteDate to modification date of n
        set noteFolder to name of container of n
        set end of noteList to noteId & "|||" & noteName & "|||" & noteBody & "|||" & (noteDate as string) & "|||" & noteFolder & "###SEPARATOR###"
    end repeat
    return noteList as string
end tell
'''


class AppleNotesConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="apple-notes",
        display_name="Apple Notes",
        version="0.1.0",
        description="Read notes from macOS Apple Notes app via AppleScript",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="applescript",
        scopes=["notes:read"],
        poll_interval_seconds=300,
        required_config=[],
        optional_config=["folders"],
    )

    def __init__(self) -> None:
        self._folders: list[str] = []

    async def authenticate(self, config: dict[str, Any]) -> bool:
        if platform.system() != "Darwin":
            logger.error("Apple Notes connector only works on macOS")
            return False

        folders = config.get("folders", "")
        if folders:
            self._folders = [f.strip() for f in folders.split(",") if f.strip()]

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        try:
            result = subprocess.run(
                ["osascript", "-e", APPLESCRIPT_LIST],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                logger.error(f"AppleScript error: {result.stderr}")
                return
        except subprocess.TimeoutExpired:
            logger.error("AppleScript timed out")
            return
        except FileNotFoundError:
            logger.error("osascript not found — not on macOS?")
            return

        raw = result.stdout.strip()
        if not raw:
            return

        entries = raw.split("###SEPARATOR###")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            parts = entry.split("|||", 4)
            if len(parts) < 5:
                continue

            note_id, name, body, date_str, folder = parts

            if self._folders and folder not in self._folders:
                continue

            body_text = self._strip_html(body)

            try:
                timestamp = datetime.strptime(date_str.strip(), "%A, %B %d, %Y at %I:%M:%S %p")
            except (ValueError, TypeError):
                timestamp = datetime.now()

            if since and timestamp <= since:
                continue

            source_id = hashlib.md5(note_id.encode()).hexdigest()

            yield RawDocument(
                source="apple-notes",
                source_id=source_id,
                content=body_text,
                content_type="note",
                title=name.strip(),
                timestamp=timestamp,
                metadata={"folder": folder.strip(), "apple_note_id": note_id.strip()},
            )

    async def health_check(self) -> bool:
        if platform.system() != "Darwin":
            return False
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "Notes" to count of notes'],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Apple Notes reads directly from the Notes app on macOS.")
        typer.echo("  No credentials needed — uses AppleScript for access.\n")

        folders = typer.prompt("  Folders to include (comma-separated, or empty for all)", default="")
        settings: dict[str, Any] = {}
        if folders:
            settings["folders"] = folders
        return settings

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"</?(?:div|p|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
