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

ASANA_API = "https://app.asana.com/api/1.0"


class AsanaConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="asana",
        display_name="Asana",
        version="0.1.0",
        description="Read tasks and projects from Asana (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="api_token",
        scopes=["read"],
        poll_interval_seconds=300,
        required_config=["api_token"],
        optional_config=["workspace_gid", "project_gids"],
    )

    def __init__(self) -> None:
        self._token: str = ""
        self._workspace_gid: str = ""
        self._project_gids: list[str] = []
        self._client: httpx.AsyncClient | None = None

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self._token = config.get("api_token", "")
        if not self._token:
            return False

        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30,
        )

        self._workspace_gid = config.get("workspace_gid", "")
        gids = config.get("project_gids", "")
        if gids:
            self._project_gids = [g.strip() for g in gids.split(",") if g.strip()]

        if not self._workspace_gid:
            try:
                resp = await self._client.get(f"{ASANA_API}/workspaces")
                resp.raise_for_status()
                workspaces = resp.json().get("data", [])
                if workspaces:
                    self._workspace_gid = workspaces[0]["gid"]
            except Exception as e:
                logger.error(f"Failed to get Asana workspaces: {e}")
                return False

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        if self._project_gids:
            for gid in self._project_gids:
                async for doc in self._fetch_project_tasks(gid, since):
                    yield doc
        elif self._workspace_gid:
            async for doc in self._fetch_workspace_tasks(since):
                yield doc

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(f"{ASANA_API}/users/me")
            return resp.status_code == 200
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Asana setup — requires a Personal Access Token.")
        typer.echo("  Create one at: https://app.asana.com/0/developer-console\n")

        token = typer.prompt("  Asana API token", hide_input=True)
        workspace = typer.prompt("  Workspace GID (leave empty for auto-detect)", default="")
        projects = typer.prompt("  Project GIDs (comma-separated, or empty for all)", default="")

        settings: dict[str, Any] = {"api_token": token}
        if workspace:
            settings["workspace_gid"] = workspace
        if projects:
            settings["project_gids"] = projects
        return settings

    async def _fetch_project_tasks(
        self, project_gid: str, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        params: dict[str, Any] = {
            "opt_fields": "name,notes,assignee.name,due_on,completed,completed_at,modified_at,tags.name,permalink_url",
        }
        if since:
            params["modified_since"] = since.isoformat()

        offset = None
        while True:
            if offset:
                params["offset"] = offset
            try:
                resp = await self._client.get(
                    f"{ASANA_API}/projects/{project_gid}/tasks", params=params,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Failed to fetch Asana tasks: {e}")
                break

            for task in data.get("data", []):
                doc = self._task_to_document(task)
                if doc:
                    yield doc

            next_page = data.get("next_page")
            if next_page:
                offset = next_page.get("offset")
            else:
                break

    async def _fetch_workspace_tasks(
        self, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        params: dict[str, Any] = {
            "workspace": self._workspace_gid,
            "assignee": "me",
            "opt_fields": "name,notes,assignee.name,due_on,completed,completed_at,modified_at,tags.name,permalink_url",
        }
        if since:
            params["modified_since"] = since.isoformat()

        try:
            resp = await self._client.get(f"{ASANA_API}/tasks", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch Asana tasks: {e}")
            return

        for task in data.get("data", []):
            doc = self._task_to_document(task)
            if doc:
                yield doc

    def _task_to_document(self, task: dict[str, Any]) -> RawDocument | None:
        gid = task.get("gid", "")
        if not gid:
            return None

        name = task.get("name", "Untitled Task")
        notes = task.get("notes", "")
        assignee = task.get("assignee", {})
        assignee_name = assignee.get("name", "") if assignee else ""
        due_on = task.get("due_on", "")
        completed = task.get("completed", False)
        tags = [t.get("name", "") for t in task.get("tags", [])]

        content_parts = [f"# {name}"]
        if assignee_name:
            content_parts.append(f"**Assignee:** {assignee_name}")
        if due_on:
            content_parts.append(f"**Due:** {due_on}")
        content_parts.append(f"**Status:** {'Completed' if completed else 'Open'}")
        if tags:
            content_parts.append(f"**Tags:** {', '.join(tags)}")
        if notes:
            content_parts.append(f"\n{notes}")

        modified = task.get("modified_at") or task.get("completed_at", "")
        try:
            timestamp = datetime.fromisoformat(modified.replace("Z", "+00:00")) if modified else datetime.now(timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        participants = [assignee_name] if assignee_name else []

        return RawDocument(
            source="asana",
            source_id=gid,
            content="\n".join(content_parts),
            content_type="task",
            title=name,
            timestamp=timestamp,
            metadata={"completed": completed, "due_on": due_on, "tags": tags},
            url=task.get("permalink_url"),
            participants=participants,
        )
