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


class JiraConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="jira",
        display_name="JIRA",
        version="0.1.0",
        description="Read issues from Atlassian JIRA (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="api_token",
        scopes=["read"],
        poll_interval_seconds=300,
        required_config=["base_url", "email", "api_token"],
        optional_config=["jql", "max_results"],
    )

    def __init__(self) -> None:
        self._base_url: str = ""
        self._client: httpx.AsyncClient | None = None
        self._jql: str = ""
        self._max_results: int = 100

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self._base_url = config.get("base_url", "").rstrip("/")
        email = config.get("email", "")
        token = config.get("api_token", "")

        if not self._base_url or not email or not token:
            return False

        self._client = httpx.AsyncClient(
            auth=(email, token),
            timeout=30,
        )

        self._jql = config.get("jql", "assignee = currentUser() ORDER BY updated DESC")
        max_r = config.get("max_results", "")
        if max_r:
            self._max_results = int(max_r)

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        jql = self._jql
        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M")
            jql = f"({jql}) AND updated >= '{since_str}'"

        start_at = 0
        fetched = 0

        while fetched < self._max_results:
            try:
                resp = await self._client.get(
                    f"{self._base_url}/rest/api/3/search",
                    params={
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": min(50, self._max_results - fetched),
                        "fields": "summary,description,assignee,reporter,status,priority,labels,updated,created,comment",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"JIRA search failed: {e}")
                break

            issues = data.get("issues", [])
            if not issues:
                break

            for issue in issues:
                doc = self._issue_to_document(issue)
                if doc:
                    yield doc
                    fetched += 1

            start_at += len(issues)
            if start_at >= data.get("total", 0):
                break

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(f"{self._base_url}/rest/api/3/myself")
            return resp.status_code == 200
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  JIRA setup — requires an API token.")
        typer.echo("  Create one at: https://id.atlassian.com/manage-profile/security/api-tokens\n")

        base_url = typer.prompt("  JIRA base URL (e.g. https://yourorg.atlassian.net)")
        email = typer.prompt("  Email address")
        token = typer.prompt("  API token", hide_input=True)
        jql = typer.prompt("  JQL filter", default="assignee = currentUser() ORDER BY updated DESC")

        return {
            "base_url": base_url,
            "email": email,
            "api_token": token,
            "jql": jql,
        }

    def _issue_to_document(self, issue: dict[str, Any]) -> RawDocument | None:
        key = issue.get("key", "")
        if not key:
            return None

        fields = issue.get("fields", {})
        summary = fields.get("summary", "Untitled")

        desc_raw = fields.get("description")
        description = self._extract_adf_text(desc_raw) if desc_raw else ""

        assignee = fields.get("assignee") or {}
        reporter = fields.get("reporter") or {}
        status = (fields.get("status") or {}).get("name", "")
        priority = (fields.get("priority") or {}).get("name", "")
        labels = fields.get("labels", [])

        content_parts = [f"# [{key}] {summary}"]
        if status:
            content_parts.append(f"**Status:** {status}")
        if priority:
            content_parts.append(f"**Priority:** {priority}")
        if assignee.get("displayName"):
            content_parts.append(f"**Assignee:** {assignee['displayName']}")
        if reporter.get("displayName"):
            content_parts.append(f"**Reporter:** {reporter['displayName']}")
        if labels:
            content_parts.append(f"**Labels:** {', '.join(labels)}")
        if description:
            content_parts.append(f"\n{description}")

        comments = fields.get("comment", {}).get("comments", [])
        if comments:
            content_parts.append("\n## Comments")
            for c in comments[-5:]:
                author = (c.get("author") or {}).get("displayName", "Unknown")
                body = self._extract_adf_text(c.get("body", {}))
                content_parts.append(f"\n**{author}:**\n{body}")

        updated = fields.get("updated", "")
        try:
            timestamp = datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else datetime.now(timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        participants = []
        if assignee.get("displayName"):
            participants.append(assignee["displayName"])
        if reporter.get("displayName"):
            participants.append(reporter["displayName"])

        return RawDocument(
            source="jira",
            source_id=key,
            content="\n".join(content_parts),
            content_type="ticket",
            title=f"[{key}] {summary}",
            timestamp=timestamp,
            metadata={"status": status, "priority": priority, "labels": labels},
            url=f"{self._base_url}/browse/{key}",
            participants=participants,
        )

    @staticmethod
    def _extract_adf_text(node: Any) -> str:
        if isinstance(node, str):
            return node
        if not isinstance(node, dict):
            return ""
        if node.get("type") == "text":
            return node.get("text", "")
        parts = []
        for child in node.get("content", []):
            parts.append(JiraConnector._extract_adf_text(child))
        text = "".join(parts)
        if node.get("type") in ("paragraph", "heading"):
            text += "\n"
        return text
