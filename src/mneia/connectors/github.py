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

GITHUB_API = "https://api.github.com"


class GitHubConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="github",
        display_name="GitHub",
        version="0.1.0",
        description="Read issues, PRs, and commits from GitHub repos",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="api_token",
        scopes=["repo:read"],
        poll_interval_seconds=600,
        required_config=["github_token"],
        optional_config=["repos"],
    )

    def __init__(self) -> None:
        self._token: str = ""
        self._repos: list[str] = []
        self._client: httpx.AsyncClient | None = None
        self._skipped_resources: list[str] = []

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self._token = config.get("github_token", "")
        if not self._token:
            return False

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

        repos = config.get("repos", "")
        if repos:
            self._repos = [
                r.strip() for r in repos.split(",") if r.strip()
            ]

        return True

    async def fetch_since(
        self, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client or not self._repos:
            return

        for repo in self._repos:
            if repo in self._skipped_resources:
                logger.debug(f"Skipping {repo} (previously not found)")
                continue
            async for doc in self._fetch_issues(repo, since):
                yield doc
            async for doc in self._fetch_pulls(repo, since):
                yield doc

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(f"{GITHUB_API}/user")
            return resp.status_code == 200
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  GitHub setup")

        token, token_source = self._detect_github_token()
        username = ""

        if token:
            typer.echo(f"  Found existing token ({token_source})")
            use_found = typer.confirm("  Use this token?", default=True)
            if not use_found:
                token = typer.prompt("  GitHub token", hide_input=True)
                token_source = "manual"
            else:
                username = self._get_username_from_gh_cli()
        else:
            typer.echo("  No existing token found.")
            typer.echo("  Create one at: https://github.com/settings/tokens")
            token = typer.prompt("  GitHub token", hide_input=True)

        if not username:
            username = typer.prompt("  GitHub username (to find your repos)", default="")

        settings: dict[str, Any] = {"github_token": token}

        if username:
            discovered = self._discover_user_repos(token, username)
            if discovered:
                typer.echo(f"\n  Found {len(discovered)} repos for @{username}:")
                for r in discovered[:8]:
                    typer.echo(f"    {r}")
                if len(discovered) > 8:
                    typer.echo(f"    ... and {len(discovered) - 8} more")
                repos_input = typer.prompt(
                    "\n  Repos to sync (comma-separated, or Enter for all listed)",
                    default=",".join(discovered),
                )
            else:
                repos_input = typer.prompt(
                    "  Repos (owner/repo, comma-separated)", default="",
                )
        else:
            repos_input = typer.prompt(
                "  Repos (owner/repo, comma-separated)", default="",
            )

        if repos_input:
            settings["repos"] = repos_input

        self._verify_setup(settings)
        return settings

    @staticmethod
    def _detect_github_token() -> tuple[str, str]:
        """Return (token, source) from env vars, gh CLI, or config file. Returns ('', '') if not found."""
        import os
        import shutil
        import subprocess
        from pathlib import Path

        for env_var in ("GITHUB_TOKEN", "GH_TOKEN"):
            token = os.environ.get(env_var, "")
            if token:
                return token, f"${env_var}"

        if shutil.which("gh"):
            try:
                result = subprocess.run(
                    ["gh", "auth", "token"],
                    capture_output=True, text=True, timeout=5,
                )
                token = result.stdout.strip()
                if token:
                    return token, "gh CLI (keychain)"
            except Exception:
                pass

        gh_hosts = Path.home() / ".config" / "gh" / "hosts.yml"
        if gh_hosts.exists():
            try:
                for line in gh_hosts.read_text().splitlines():
                    stripped = line.strip()
                    if stripped.startswith("oauth_token:"):
                        token = stripped.split(":", 1)[-1].strip()
                        if token:
                            return token, "gh CLI config"
            except Exception:
                pass

        return "", ""

    @staticmethod
    def _get_username_from_gh_cli() -> str:
        """Read GitHub username from gh CLI config if available."""
        from pathlib import Path

        gh_hosts = Path.home() / ".config" / "gh" / "hosts.yml"
        if gh_hosts.exists():
            try:
                for line in gh_hosts.read_text().splitlines():
                    stripped = line.strip()
                    if stripped.startswith("user:"):
                        return stripped.split(":", 1)[-1].strip()
            except Exception:
                pass
        return ""

    @staticmethod
    def _discover_user_repos(token: str, username: str) -> list[str]:
        """Fetch up to 30 repos for the given user via GitHub API."""
        import httpx as _httpx

        try:
            resp = _httpx.get(
                f"https://api.github.com/users/{username}/repos",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"sort": "pushed", "per_page": 30},
                timeout=10,
            )
            if resp.status_code == 200:
                return [r["full_name"] for r in resp.json()]
        except Exception:
            pass
        return []

    async def _fetch_issues(
        self, repo: str, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        params: dict[str, Any] = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": 50,
        }
        if since:
            params["since"] = since.isoformat()

        try:
            resp = await self._client.get(
                f"{GITHUB_API}/repos/{repo}/issues",
                params=params,
            )
            if resp.status_code in (404, 410):
                logger.warning(
                    f"GitHub repo not found: {repo} (HTTP {resp.status_code}) — "
                    "removing from future syncs"
                )
                if repo not in self._skipped_resources:
                    self._skipped_resources.append(repo)
                return
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub issues fetch failed for {repo}: {e}")
            return
        except Exception as e:
            logger.error(f"GitHub issues fetch failed for {repo}: {e}")
            return

        for item in resp.json():
            if item.get("pull_request"):
                continue
            doc = self._issue_to_document(item, repo)
            if doc:
                yield doc

    async def _fetch_pulls(
        self, repo: str, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        params: dict[str, Any] = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": 50,
        }

        try:
            resp = await self._client.get(
                f"{GITHUB_API}/repos/{repo}/pulls",
                params=params,
            )
            if resp.status_code in (404, 410):
                logger.warning(
                    f"GitHub repo not found: {repo} (HTTP {resp.status_code}) — "
                    "removing from future syncs"
                )
                if repo not in self._skipped_resources:
                    self._skipped_resources.append(repo)
                return
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub PRs fetch failed for {repo}: {e}")
            return
        except Exception as e:
            logger.error(f"GitHub PRs fetch failed for {repo}: {e}")
            return

        for pr in resp.json():
            updated = pr.get("updated_at", "")
            if since and updated:
                try:
                    pr_time = datetime.fromisoformat(
                        updated.replace("Z", "+00:00"),
                    )
                    if pr_time <= since:
                        continue
                except (ValueError, TypeError):
                    pass

            doc = self._pr_to_document(pr, repo)
            if doc:
                yield doc

    def _issue_to_document(
        self, item: dict[str, Any], repo: str,
    ) -> RawDocument | None:
        number = item.get("number")
        title = item.get("title", "")
        body = item.get("body", "") or ""
        state = item.get("state", "open")
        user = item.get("user", {}).get("login", "")
        labels = [
            lb.get("name", "") for lb in item.get("labels", [])
        ]

        content_parts = [f"# {title}", f"**State:** {state}"]
        if user:
            content_parts.append(f"**Author:** {user}")
        if labels:
            content_parts.append(f"**Labels:** {', '.join(labels)}")
        if body:
            content_parts.append(f"\n{body[:5000]}")

        timestamp = self._parse_time(
            item.get("updated_at") or item.get("created_at", ""),
        )

        return RawDocument(
            source="github",
            source_id=f"{repo}/issues/{number}",
            content="\n".join(content_parts),
            content_type="issue",
            title=f"[{repo}] #{number}: {title}",
            timestamp=timestamp,
            url=item.get("html_url"),
            metadata={
                "repo": repo,
                "number": number,
                "state": state,
                "labels": labels,
            },
            participants=[user] if user else [],
        )

    def _pr_to_document(
        self, pr: dict[str, Any], repo: str,
    ) -> RawDocument | None:
        number = pr.get("number")
        title = pr.get("title", "")
        body = pr.get("body", "") or ""
        state = pr.get("state", "open")
        merged = pr.get("merged_at") is not None
        user = pr.get("user", {}).get("login", "")

        content_parts = [f"# PR: {title}"]
        status = "merged" if merged else state
        content_parts.append(f"**Status:** {status}")
        if user:
            content_parts.append(f"**Author:** {user}")
        if body:
            content_parts.append(f"\n{body[:5000]}")

        timestamp = self._parse_time(
            pr.get("updated_at") or pr.get("created_at", ""),
        )

        return RawDocument(
            source="github",
            source_id=f"{repo}/pulls/{number}",
            content="\n".join(content_parts),
            content_type="pull_request",
            title=f"[{repo}] PR #{number}: {title}",
            timestamp=timestamp,
            url=pr.get("html_url"),
            metadata={
                "repo": repo,
                "number": number,
                "state": status,
            },
            participants=[user] if user else [],
        )

    @staticmethod
    def _parse_time(ts: str) -> datetime:
        try:
            return datetime.fromisoformat(
                ts.replace("Z", "+00:00"),
            )
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
