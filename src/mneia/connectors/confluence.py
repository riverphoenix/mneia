from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)


class ConfluenceConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="confluence",
        display_name="Confluence",
        version="0.1.0",
        description="Read pages from Atlassian Confluence (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="api_token",
        scopes=["read"],
        poll_interval_seconds=600,
        required_config=["base_url", "email", "api_token"],
        optional_config=["space_keys", "max_results"],
    )

    def __init__(self) -> None:
        self._base_url: str = ""
        self._client: httpx.AsyncClient | None = None
        self._space_keys: list[str] = []
        self._max_results: int = 100

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self._base_url = config.get("base_url", "").rstrip("/")
        email = config.get("email", "")
        token = config.get("api_token", "")

        if not self._base_url or not email or not token:
            return False

        self._client = httpx.AsyncClient(auth=(email, token), timeout=30)

        keys = config.get("space_keys", "")
        if keys:
            self._space_keys = [k.strip() for k in keys.split(",") if k.strip()]

        max_r = config.get("max_results", "")
        if max_r:
            self._max_results = int(max_r)

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        cql_parts = ["type = page"]
        if self._space_keys:
            spaces = " or ".join(f'space = "{k}"' for k in self._space_keys)
            cql_parts.append(f"({spaces})")
        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M")
            cql_parts.append(f'lastModified >= "{since_str}"')

        cql = " AND ".join(cql_parts) + " ORDER BY lastModified DESC"

        start = 0
        fetched = 0

        while fetched < self._max_results:
            try:
                resp = await self._client.get(
                    f"{self._base_url}/rest/api/content/search",
                    params={
                        "cql": cql,
                        "start": start,
                        "limit": min(25, self._max_results - fetched),
                        "expand": "body.storage,version,space,ancestors",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Confluence search failed: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for page in results:
                doc = self._page_to_document(page)
                if doc:
                    yield doc
                    fetched += 1

            start += len(results)
            if start >= data.get("totalSize", data.get("size", 0)):
                break

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(f"{self._base_url}/rest/api/space", params={"limit": 1})
            return resp.status_code == 200
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Confluence setup — requires an API token.")
        typer.echo("  Create one at: https://id.atlassian.com/manage-profile/security/api-tokens\n")

        base_url = typer.prompt("  Confluence base URL (e.g. https://yourorg.atlassian.net/wiki)")
        email = typer.prompt("  Email address")
        token = typer.prompt("  API token", hide_input=True)
        spaces = typer.prompt("  Space keys (comma-separated, or empty for all)", default="")

        settings: dict[str, Any] = {
            "base_url": base_url,
            "email": email,
            "api_token": token,
        }
        if spaces:
            settings["space_keys"] = spaces
        return settings

    def _page_to_document(self, page: dict[str, Any]) -> RawDocument | None:
        page_id = page.get("id", "")
        if not page_id:
            return None

        title = page.get("title", "Untitled")
        html_body = page.get("body", {}).get("storage", {}).get("value", "")
        space_name = page.get("space", {}).get("name", "")
        space_key = page.get("space", {}).get("key", "")

        content = self._strip_html(html_body) if html_body else ""

        version = page.get("version", {})
        modified_by = version.get("by", {}).get("displayName", "")
        when = version.get("when", "")

        try:
            timestamp = datetime.fromisoformat(when.replace("Z", "+00:00")) if when else datetime.now(timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        ancestors = [a.get("title", "") for a in page.get("ancestors", [])]

        content_parts = [f"# {title}"]
        if space_name:
            content_parts.append(f"**Space:** {space_name}")
        if modified_by:
            content_parts.append(f"**Last edited by:** {modified_by}")
        if ancestors:
            content_parts.append(f"**Path:** {' > '.join(ancestors)}")
        if content:
            content_parts.append(f"\n{content}")

        participants = [modified_by] if modified_by else []

        base = self._base_url.replace("/wiki", "") if "/wiki" in self._base_url else self._base_url

        return RawDocument(
            source="confluence",
            source_id=page_id,
            content="\n".join(content_parts),
            content_type="wiki",
            title=title,
            timestamp=timestamp,
            metadata={
                "space_key": space_key,
                "space_name": space_name,
                "ancestors": ancestors,
            },
            url=f"{base}/wiki/spaces/{space_key}/pages/{page_id}",
            participants=participants,
        )

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"</?(?:div|p|h[1-6]|li|ul|ol|tr|td|th)[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
