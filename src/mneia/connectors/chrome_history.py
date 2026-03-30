from __future__ import annotations

import logging
import platform
import shutil
import sqlite3
import tempfile
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

CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _default_chrome_history_path() -> Path | None:
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library/Application Support/Google/Chrome/Default/History"
    if system == "Linux":
        return home / ".config/google-chrome/Default/History"
    if system == "Windows":
        return home / "AppData/Local/Google/Chrome/User Data/Default/History"
    return None


def _find_chrome_history() -> list[Path]:
    """Search common Chrome-based browser locations and return existing History files."""
    system = platform.system()
    home = Path.home()
    candidates: list[Path] = []

    if system == "Darwin":
        candidates = [
            home / "Library/Application Support/Google/Chrome/Default/History",
            home / "Library/Application Support/Google/Chrome Canary/Default/History",
            home / "Library/Application Support/BraveSoftware/Brave-Browser/Default/History",
            home / "Library/Application Support/Microsoft Edge/Default/History",
            home / "Library/Application Support/Chromium/Default/History",
        ]
    elif system == "Linux":
        candidates = [
            home / ".config/google-chrome/Default/History",
            home / ".config/google-chrome-beta/Default/History",
            home / ".config/chromium/Default/History",
            home / ".config/BraveSoftware/Brave-Browser/Default/History",
            home / "snap/chromium/current/.config/chromium/Default/History",
        ]
    elif system == "Windows":
        local = home / "AppData/Local"
        candidates = [
            local / "Google/Chrome/User Data/Default/History",
            local / "Google/Chrome Beta/User Data/Default/History",
            local / "BraveSoftware/Brave-Browser/User Data/Default/History",
            local / "Microsoft/Edge/User Data/Default/History",
            local / "Chromium/User Data/Default/History",
        ]

    return [p for p in candidates if p.exists()]


def _chrome_time_to_datetime(chrome_ts: int) -> datetime:
    if chrome_ts == 0:
        return datetime.now(timezone.utc)
    seconds = chrome_ts / 1_000_000
    return CHROME_EPOCH + __import__("datetime").timedelta(seconds=seconds)


class ChromeHistoryConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="chrome-history",
        display_name="Chrome History",
        version="0.1.0",
        description="Read browsing history from Google Chrome (read-only, local)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="local",
        scopes=["read"],
        poll_interval_seconds=600,
        required_config=[],
        optional_config=[
            "history_path", "max_results",
            "scrape_content", "scrape_max_pages",
            "scrape_domains_exclude",
        ],
    )

    def __init__(self) -> None:
        self._history_path: Path | None = None
        self._max_results: int = 200
        self._scrape_content: bool = False
        self._scrape_max_pages: int = 20
        self._scrape_domains_exclude: set[str] = set()

    async def authenticate(self, config: dict[str, Any]) -> bool:
        path_str = config.get("history_path", "")
        if path_str:
            self._history_path = Path(path_str)
        else:
            default = _default_chrome_history_path()
            if default and default.exists():
                self._history_path = default
            else:
                found = _find_chrome_history()
                self._history_path = found[0] if found else default

        if not self._history_path or not self._history_path.exists():
            logger.error(f"Chrome history not found at: {self._history_path}")
            return False

        max_r = config.get("max_results", "")
        if max_r:
            self._max_results = int(max_r)

        scrape = config.get("scrape_content", "")
        if isinstance(scrape, bool):
            self._scrape_content = scrape
        elif isinstance(scrape, str) and scrape:
            self._scrape_content = scrape.lower() in (
                "true", "1", "yes",
            )

        max_pages = config.get("scrape_max_pages", "")
        if max_pages:
            self._scrape_max_pages = int(max_pages)

        exclude = config.get("scrape_domains_exclude", "")
        if exclude:
            self._scrape_domains_exclude = {
                d.strip()
                for d in exclude.split(",")
                if d.strip()
            }

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._history_path:
            return

        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir) / "History"
        try:
            shutil.copy2(self._history_path, tmp_path)
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot copy Chrome history: {e}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        try:
            conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row

            query = """
                SELECT u.id, u.url, u.title, u.visit_count, u.last_visit_time,
                       u.typed_count
                FROM urls u
            """
            params: list[Any] = []

            if since:
                chrome_ts = int((since - CHROME_EPOCH).total_seconds() * 1_000_000)
                query += " WHERE u.last_visit_time > ?"
                params.append(chrome_ts)

            query += " ORDER BY u.last_visit_time DESC LIMIT ?"
            params.append(self._max_results)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            scraped_count = 0
            for row in rows:
                doc = self._row_to_document(row)
                if doc:
                    yield doc

                    if (
                        self._scrape_content
                        and doc.url
                        and scraped_count < self._scrape_max_pages
                        and not self._is_excluded_domain(doc.url)
                        and not doc.metadata.get("content_scraped")
                    ):
                        scraped = await self._scrape_page(doc)
                        if scraped:
                            scraped_count += 1
                            yield scraped
        except Exception as e:
            logger.error(f"Chrome history read failed: {e}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    async def health_check(self) -> bool:
        if not self._history_path:
            return False
        return self._history_path.exists()

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        found = _find_chrome_history()
        if not found:
            typer.echo("\n  No Chrome-based browser history found at standard locations.")
            typer.echo("  Please enter the full path to your browser's History file.")
            typer.echo("  (e.g. ~/Library/Application Support/Google/Chrome/Default/History)")
            path = typer.prompt("  History file path")
            return {"history_path": path}

        if len(found) == 1:
            typer.echo(f"\n  Found browser history: {found[0]}")
            return {"history_path": str(found[0])}

        typer.echo("\n  Found multiple browser history files:")
        for i, p in enumerate(found):
            typer.echo(f"  [{i}] {p}")
        choice = typer.prompt("  Select browser (number or press Enter for first)", default="0")
        try:
            idx = int(choice)
            if 0 <= idx < len(found):
                return {"history_path": str(found[idx])}
        except ValueError:
            if choice.strip():
                return {"history_path": choice.strip()}
        return {"history_path": str(found[0])}

    def _is_excluded_domain(self, url: str) -> bool:
        from urllib.parse import urlparse

        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            return True
        if not domain:
            return True
        for excluded in self._scrape_domains_exclude:
            if excluded in domain:
                return True
        internal_prefixes = (
            "chrome://", "chrome-extension://",
            "about:", "file://",
        )
        if any(url.startswith(p) for p in internal_prefixes):
            return True
        return False

    async def _scrape_page(
        self, doc: RawDocument,
    ) -> RawDocument | None:
        if not doc.url:
            return None
        try:
            from mneia.connectors.web_scraper import scrape_url

            content = await scrape_url(doc.url)
            if not content or len(content) < 50:
                return None

            return RawDocument(
                source="chrome-history",
                source_id=f"scraped-{doc.source_id}",
                content=content,
                content_type="webpage",
                title=f"{doc.title} (content)",
                timestamp=doc.timestamp,
                url=doc.url,
                metadata={
                    **doc.metadata,
                    "content_scraped": True,
                    "original_source_id": doc.source_id,
                },
            )
        except Exception as e:
            logger.debug(f"Scrape failed for {doc.url}: {e}")
            return None

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> RawDocument | None:
        url = row["url"]
        title = row["title"] or url
        if not url:
            return None

        visit_count = row["visit_count"] or 0
        typed_count = row["typed_count"] or 0
        last_visit = row["last_visit_time"] or 0

        timestamp = _chrome_time_to_datetime(last_visit)

        content_parts = [f"# {title}", f"URL: {url}"]
        content_parts.append(f"Visits: {visit_count}")
        if typed_count:
            content_parts.append(f"Typed: {typed_count}")

        return RawDocument(
            source="chrome-history",
            source_id=str(row["id"]),
            content="\n".join(content_parts),
            content_type="bookmark",
            title=title,
            timestamp=timestamp,
            url=url,
            metadata={
                "visit_count": visit_count,
                "typed_count": typed_count,
            },
        )
