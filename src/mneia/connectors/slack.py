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

SLACK_API = "https://slack.com/api"


class SlackConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="slack",
        display_name="Slack",
        version="0.1.0",
        description="Read messages from Slack channels (bot token)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="bot_token",
        scopes=["channels:history", "channels:read"],
        poll_interval_seconds=300,
        required_config=["slack_token"],
        optional_config=["channels"],
    )

    def __init__(self) -> None:
        self._token: str = ""
        self._channels: list[str] = []
        self._client: httpx.AsyncClient | None = None

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self._token = config.get("slack_token", "")
        if not self._token:
            return False

        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30,
        )

        channels = config.get("channels", "")
        if channels:
            self._channels = [
                c.strip() for c in channels.split(",") if c.strip()
            ]

        return True

    async def fetch_since(
        self, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        channel_ids = self._channels
        if not channel_ids:
            channel_ids = await self._list_channels()

        for channel_id in channel_ids:
            async for doc in self._fetch_channel(
                channel_id, since,
            ):
                yield doc

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.post(
                f"{SLACK_API}/auth.test",
            )
            data = resp.json()
            return data.get("ok", False)
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Slack setup — requires a Bot User OAuth Token.")
        typer.echo(
            "  Create an app at: https://api.slack.com/apps\n"
        )

        token = typer.prompt("  Bot token (xoxb-...)", hide_input=True)
        channels = typer.prompt(
            "  Channel IDs (comma-separated, or empty for all)",
            default="",
        )

        settings: dict[str, Any] = {"slack_token": token}
        if channels:
            settings["channels"] = channels
        self._verify_setup(settings)
        return settings

    async def _list_channels(self) -> list[str]:
        if not self._client:
            return []
        try:
            resp = await self._client.get(
                f"{SLACK_API}/conversations.list",
                params={
                    "types": "public_channel",
                    "limit": 100,
                },
            )
            data = resp.json()
            if data.get("ok"):
                return [
                    ch["id"]
                    for ch in data.get("channels", [])
                    if ch.get("is_member")
                ]
        except Exception as e:
            logger.error(f"Failed to list Slack channels: {e}")
        return []

    async def _fetch_channel(
        self,
        channel_id: str,
        since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        params: dict[str, Any] = {"channel": channel_id, "limit": 100}
        if since:
            params["oldest"] = str(since.timestamp())

        try:
            resp = await self._client.get(
                f"{SLACK_API}/conversations.history",
                params=params,
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error(
                    f"Slack API error: {data.get('error', 'unknown')}"
                )
                return
        except Exception as e:
            logger.error(f"Slack fetch failed: {e}")
            return

        for msg in data.get("messages", []):
            doc = self._message_to_document(msg, channel_id)
            if doc:
                yield doc

    def _message_to_document(
        self, msg: dict[str, Any], channel_id: str,
    ) -> RawDocument | None:
        text = msg.get("text", "")
        if not text:
            return None

        ts = msg.get("ts", "")
        user = msg.get("user", "unknown")

        try:
            timestamp = datetime.fromtimestamp(
                float(ts), tz=timezone.utc,
            )
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        return RawDocument(
            source="slack",
            source_id=f"{channel_id}-{ts}",
            content=text,
            content_type="message",
            title=f"Slack message in {channel_id}",
            timestamp=timestamp,
            metadata={
                "channel_id": channel_id,
                "user": user,
                "thread_ts": msg.get("thread_ts"),
            },
            participants=[user],
        )
