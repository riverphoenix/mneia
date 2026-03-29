from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import httpx

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)

LINEAR_API = "https://api.linear.app/graphql"


class LinearConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="linear",
        display_name="Linear",
        version="0.1.0",
        description="Read issues and projects from Linear",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="api_key",
        scopes=["read"],
        poll_interval_seconds=300,
        required_config=["linear_api_key"],
        optional_config=["team_ids"],
    )

    def __init__(self) -> None:
        self._api_key: str = ""
        self._team_ids: list[str] = []
        self._client: httpx.AsyncClient | None = None

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self._api_key = config.get("linear_api_key", "")
        if not self._api_key:
            return False

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        team_ids = config.get("team_ids", "")
        if team_ids:
            self._team_ids = [
                t.strip() for t in team_ids.split(",") if t.strip()
            ]

        return True

    async def fetch_since(
        self, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        async for doc in self._fetch_issues(since):
            yield doc

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.post(
                LINEAR_API,
                json={"query": "{ viewer { id } }"},
            )
            data = resp.json()
            return "data" in data and "viewer" in data["data"]
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Linear setup — requires an API key.")
        typer.echo(
            "  Create one at: Linear Settings > API > "
            "Personal API keys\n"
        )

        key = typer.prompt("  Linear API key", hide_input=True)
        teams = typer.prompt(
            "  Team IDs (comma-separated, or empty for all)",
            default="",
        )

        settings: dict[str, Any] = {"linear_api_key": key}
        if teams:
            settings["team_ids"] = teams
        self._verify_setup(settings)
        return settings

    async def _fetch_issues(
        self, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        after_filter = ""
        if since:
            after_filter = (
                f', filter: {{ updatedAt: {{ gte: '
                f'"{since.isoformat()}" }} }}'
            )

        team_filter = ""
        if self._team_ids:
            ids_str = ", ".join(f'"{t}"' for t in self._team_ids)
            team_filter = (
                f', filter: {{ team: {{ id: {{ in: [{ids_str}] }} }}'
                f'{after_filter.lstrip(", filter: ")} }}'
            )
            after_filter = ""

        query_filter = team_filter or after_filter
        query = f"""{{
            issues(first: 50{query_filter}) {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    state {{ name }}
                    assignee {{ name }}
                    priority
                    labels {{ nodes {{ name }} }}
                    updatedAt
                    createdAt
                    url
                    team {{ name }}
                }}
            }}
        }}"""

        try:
            resp = await self._client.post(
                LINEAR_API, json={"query": query},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Linear fetch failed: {e}")
            return

        issues = (
            data.get("data", {}).get("issues", {}).get("nodes", [])
        )
        for issue in issues:
            doc = self._issue_to_document(issue)
            if doc:
                yield doc

    def _issue_to_document(
        self, issue: dict[str, Any],
    ) -> RawDocument | None:
        issue_id = issue.get("id", "")
        identifier = issue.get("identifier", "")
        title = issue.get("title", "")
        description = issue.get("description", "") or ""
        state = issue.get("state", {}).get("name", "")
        assignee = issue.get("assignee", {})
        assignee_name = assignee.get("name", "") if assignee else ""
        team = issue.get("team", {}).get("name", "")
        priority = issue.get("priority", 0)
        labels = [
            lb.get("name", "")
            for lb in issue.get("labels", {}).get("nodes", [])
        ]

        content_parts = [f"# {identifier}: {title}"]
        if team:
            content_parts.append(f"**Team:** {team}")
        if state:
            content_parts.append(f"**State:** {state}")
        if assignee_name:
            content_parts.append(f"**Assignee:** {assignee_name}")
        if priority:
            priority_names = {
                1: "Urgent", 2: "High", 3: "Medium", 4: "Low",
            }
            content_parts.append(
                f"**Priority:** "
                f"{priority_names.get(priority, str(priority))}"
            )
        if labels:
            content_parts.append(f"**Labels:** {', '.join(labels)}")
        if description:
            content_parts.append(f"\n{description[:5000]}")

        timestamp = self._parse_time(
            issue.get("updatedAt")
            or issue.get("createdAt", ""),
        )

        participants = [assignee_name] if assignee_name else []

        return RawDocument(
            source="linear",
            source_id=issue_id,
            content="\n".join(content_parts),
            content_type="issue",
            title=f"{identifier}: {title}",
            timestamp=timestamp,
            url=issue.get("url"),
            metadata={
                "identifier": identifier,
                "state": state,
                "priority": priority,
                "team": team,
                "labels": labels,
            },
            participants=participants,
        )

    @staticmethod
    def _parse_time(ts: str) -> datetime:
        try:
            return datetime.fromisoformat(
                ts.replace("Z", "+00:00"),
            )
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
