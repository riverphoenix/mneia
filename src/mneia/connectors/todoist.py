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

TODOIST_API = "https://api.todoist.com/rest/v2"


class TodoistConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="todoist",
        display_name="Todoist",
        version="0.1.0",
        description="Read tasks and projects from Todoist",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="api_token",
        scopes=["read"],
        poll_interval_seconds=300,
        required_config=["todoist_api_token"],
        optional_config=[],
    )

    def __init__(self) -> None:
        self._token: str = ""
        self._client: httpx.AsyncClient | None = None

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self._token = config.get("todoist_api_token", "")
        if not self._token:
            return False

        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30,
        )

        return True

    async def fetch_since(
        self, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        projects = await self._fetch_projects()
        project_map = {p["id"]: p["name"] for p in projects}

        async for doc in self._fetch_tasks(project_map):
            yield doc

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(
                f"{TODOIST_API}/projects",
            )
            return resp.status_code == 200
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Todoist setup — requires an API token.")
        typer.echo(
            "  Find it at: Todoist Settings > Integrations > "
            "Developer\n"
        )

        token = typer.prompt("  Todoist API token", hide_input=True)
        settings = {"todoist_api_token": token}
        self._verify_setup(settings)
        return settings

    async def _fetch_projects(self) -> list[dict[str, Any]]:
        if not self._client:
            return []
        try:
            resp = await self._client.get(
                f"{TODOIST_API}/projects",
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Todoist projects fetch failed: {e}")
            return []

    async def _fetch_tasks(
        self, project_map: dict[str, str],
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        try:
            resp = await self._client.get(
                f"{TODOIST_API}/tasks",
            )
            resp.raise_for_status()
            tasks = resp.json()
        except Exception as e:
            logger.error(f"Todoist tasks fetch failed: {e}")
            return

        for task in tasks:
            doc = self._task_to_document(task, project_map)
            if doc:
                yield doc

    def _task_to_document(
        self,
        task: dict[str, Any],
        project_map: dict[str, str],
    ) -> RawDocument | None:
        task_id = task.get("id", "")
        if not task_id:
            return None

        content = task.get("content", "")
        description = task.get("description", "") or ""
        priority = task.get("priority", 1)
        project_id = task.get("project_id", "")
        project_name = project_map.get(project_id, "")
        labels = task.get("labels", [])
        due = task.get("due")

        content_parts = [f"# {content}"]
        if project_name:
            content_parts.append(f"**Project:** {project_name}")
        if priority > 1:
            priority_names = {
                4: "Urgent", 3: "High", 2: "Medium",
            }
            content_parts.append(
                f"**Priority:** "
                f"{priority_names.get(priority, str(priority))}"
            )
        if due:
            due_str = due.get("string", "") or due.get("date", "")
            if due_str:
                content_parts.append(f"**Due:** {due_str}")
        if labels:
            content_parts.append(f"**Labels:** {', '.join(labels)}")
        if description:
            content_parts.append(f"\n{description}")

        created = task.get("created_at", "")
        timestamp = self._parse_time(created)

        url = task.get("url")

        return RawDocument(
            source="todoist",
            source_id=str(task_id),
            content="\n".join(content_parts),
            content_type="task",
            title=content,
            timestamp=timestamp,
            url=url,
            metadata={
                "project": project_name,
                "priority": priority,
                "labels": labels,
                "is_completed": task.get("is_completed", False),
            },
        )

    @staticmethod
    def _parse_time(ts: str) -> datetime:
        try:
            return datetime.fromisoformat(
                ts.replace("Z", "+00:00"),
            )
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
