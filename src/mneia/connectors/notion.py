from __future__ import annotations

import logging
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

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="notion",
        display_name="Notion",
        version="0.1.0",
        description="Read pages and databases from Notion (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="bearer_token",
        scopes=["read"],
        poll_interval_seconds=300,
        required_config=["api_token"],
        optional_config=["database_ids", "max_results"],
    )

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._database_ids: list[str] = []
        self._max_results: int = 100

    async def authenticate(self, config: dict[str, Any]) -> bool:
        token = config.get("api_token", "")
        if not token:
            return False

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        db_ids = config.get("database_ids", "")
        if db_ids:
            self._database_ids = [d.strip() for d in db_ids.split(",") if d.strip()]

        max_r = config.get("max_results", "")
        if max_r:
            self._max_results = int(max_r)

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        payload: dict[str, Any] = {
            "page_size": min(100, self._max_results),
        }
        if since:
            payload["filter"] = {
                "property": "object",
                "value": "page",
                "timestamp": "last_edited_time",
                "last_edited_time": {"after": since.isoformat()},
            }

        fetched = 0
        has_more = True
        start_cursor = None

        while has_more and fetched < self._max_results:
            if start_cursor:
                payload["start_cursor"] = start_cursor

            try:
                resp = await self._client.post(f"{NOTION_API}/search", json=payload)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Notion search failed: {e}")
                break

            for result in data.get("results", []):
                if result.get("object") != "page":
                    continue
                doc = await self._page_to_document(result)
                if doc:
                    yield doc
                    fetched += 1

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(f"{NOTION_API}/users/me")
            return resp.status_code == 200
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Notion setup — requires an Integration token.")
        typer.echo("  Create one at: https://www.notion.so/my-integrations\n")
        typer.echo("  Make sure to share pages/databases with your integration.\n")

        token = typer.prompt("  Notion API token", hide_input=True)
        db_ids = typer.prompt("  Database IDs to sync (comma-separated, or empty for all pages)", default="")

        settings: dict[str, Any] = {"api_token": token}
        if db_ids:
            settings["database_ids"] = db_ids
        return settings

    async def _page_to_document(self, page: dict[str, Any]) -> RawDocument | None:
        page_id = page.get("id", "")
        if not page_id:
            return None

        props = page.get("properties", {})
        title = self._extract_title(props)
        url = page.get("url", "")

        content = await self._fetch_page_content(page_id)

        edited_time = page.get("last_edited_time", "")
        try:
            timestamp = datetime.fromisoformat(edited_time.replace("Z", "+00:00")) if edited_time else datetime.now(timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        edited_by = page.get("last_edited_by", {}).get("name", "")
        created_by = page.get("created_by", {}).get("name", "")
        participants = list({p for p in [edited_by, created_by] if p})

        parent = page.get("parent", {})
        parent_type = parent.get("type", "")

        metadata: dict[str, Any] = {"parent_type": parent_type}
        if parent_type == "database_id":
            metadata["database_id"] = parent.get("database_id", "")

        content_parts = [f"# {title}"]
        if content:
            content_parts.append(content)

        return RawDocument(
            source="notion",
            source_id=page_id,
            content="\n".join(content_parts),
            content_type="page",
            title=title,
            timestamp=timestamp,
            metadata=metadata,
            url=url,
            participants=participants,
        )

    async def _fetch_page_content(self, page_id: str) -> str:
        if not self._client:
            return ""

        try:
            resp = await self._client.get(f"{NOTION_API}/blocks/{page_id}/children", params={"page_size": 100})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch Notion page content: {e}")
            return ""

        parts: list[str] = []
        for block in data.get("results", []):
            text = self._block_to_text(block)
            if text:
                parts.append(text)

        return "\n".join(parts)

    @staticmethod
    def _extract_title(props: dict[str, Any]) -> str:
        for prop_name in ("title", "Name", "name"):
            prop = props.get(prop_name, {})
            if prop.get("type") == "title":
                title_arr = prop.get("title", [])
                if title_arr:
                    return "".join(t.get("plain_text", "") for t in title_arr)
        return "Untitled"

    @staticmethod
    def _block_to_text(block: dict[str, Any]) -> str:
        block_type = block.get("type", "")
        type_data = block.get(block_type, {})

        if block_type in ("paragraph", "bulleted_list_item", "numbered_list_item", "toggle", "quote", "callout"):
            rich_text = type_data.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            if block_type == "bulleted_list_item":
                return f"- {text}"
            if block_type == "numbered_list_item":
                return f"1. {text}"
            if block_type == "quote":
                return f"> {text}"
            return text

        if block_type.startswith("heading_"):
            level = block_type[-1]
            rich_text = type_data.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            return f"{'#' * int(level)} {text}"

        if block_type == "code":
            rich_text = type_data.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            lang = type_data.get("language", "")
            return f"```{lang}\n{text}\n```"

        if block_type == "to_do":
            rich_text = type_data.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            checked = type_data.get("checked", False)
            return f"- [{'x' if checked else ' '}] {text}"

        if block_type == "divider":
            return "---"

        return ""
