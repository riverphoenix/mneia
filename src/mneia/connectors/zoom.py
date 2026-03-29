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

ZOOM_API = "https://api.zoom.us/v2"


class ZoomConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="zoom",
        display_name="Zoom",
        version="0.1.0",
        description="Read meeting recordings and transcripts from Zoom (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="oauth2",
        scopes=["recording:read", "meeting:read"],
        poll_interval_seconds=600,
        required_config=["account_id", "client_id", "client_secret"],
        optional_config=["max_results"],
    )

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_results: int = 50

    async def authenticate(self, config: dict[str, Any]) -> bool:
        account_id = config.get("account_id", "")
        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")
        if not all([account_id, client_id, client_secret]):
            return False

        try:
            async with httpx.AsyncClient() as auth_client:
                resp = await auth_client.post(
                    "https://zoom.us/oauth/token",
                    params={"grant_type": "account_credentials", "account_id": account_id},
                    auth=(client_id, client_secret),
                    timeout=30,
                )
                resp.raise_for_status()
                token_data = resp.json()
                access_token = token_data.get("access_token", "")
        except Exception as e:
            logger.error(f"Zoom auth failed: {e}")
            return False

        if not access_token:
            return False

        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        max_r = config.get("max_results", "")
        if max_r:
            self._max_results = int(max_r)

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._client:
            return

        from_date = since.strftime("%Y-%m-%d") if since else "2020-01-01"
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        params: dict[str, Any] = {
            "from": from_date,
            "to": to_date,
            "page_size": min(30, self._max_results),
        }

        fetched = 0
        next_page_token = ""

        while fetched < self._max_results:
            if next_page_token:
                params["next_page_token"] = next_page_token

            try:
                resp = await self._client.get(f"{ZOOM_API}/users/me/recordings", params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Zoom recordings fetch failed: {e}")
                break

            for meeting in data.get("meetings", []):
                doc = await self._meeting_to_document(meeting)
                if doc:
                    yield doc
                    fetched += 1
                    if fetched >= self._max_results:
                        break

            next_page_token = data.get("next_page_token", "")
            if not next_page_token:
                break

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(f"{ZOOM_API}/users/me")
            return resp.status_code == 200
        except Exception:
            return False

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Zoom setup — requires a Server-to-Server OAuth app.")
        typer.echo("  Create one at: https://marketplace.zoom.us/develop/create")
        typer.echo("  Choose 'Server-to-Server OAuth' app type.")
        typer.echo("  Required scopes: recording:read, meeting:read\n")

        account_id = typer.prompt("  Zoom Account ID")
        client_id = typer.prompt("  Zoom Client ID")
        client_secret = typer.prompt("  Zoom Client Secret", hide_input=True)

        settings = {
            "account_id": account_id,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        self._verify_setup(settings)
        return settings

    async def _meeting_to_document(self, meeting: dict[str, Any]) -> RawDocument | None:
        meeting_id = str(meeting.get("id", ""))
        if not meeting_id:
            return None

        topic = meeting.get("topic", "Untitled Meeting")
        start_time = meeting.get("start_time", "")

        try:
            timestamp = datetime.fromisoformat(start_time.replace("Z", "+00:00")) if start_time else datetime.now(timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        duration = meeting.get("duration", 0)
        participant_count = meeting.get("total_size", 0)

        transcript = await self._fetch_transcript(meeting)

        content_parts = [f"# {topic}"]
        content_parts.append(f"Duration: {duration} minutes")
        if participant_count:
            content_parts.append(f"Participants: {participant_count}")

        if transcript:
            content_parts.append("")
            content_parts.append("## Transcript")
            content_parts.append(transcript)

        recordings = meeting.get("recording_files", [])
        metadata: dict[str, Any] = {
            "duration_minutes": duration,
            "recording_count": len(recordings),
        }

        host_email = meeting.get("host_email", "")
        participants = [host_email] if host_email else []

        return RawDocument(
            source="zoom",
            source_id=meeting_id,
            content="\n".join(content_parts),
            content_type="meeting",
            title=topic,
            timestamp=timestamp,
            metadata=metadata,
            participants=participants,
        )

    async def _fetch_transcript(self, meeting: dict[str, Any]) -> str:
        if not self._client:
            return ""

        recordings = meeting.get("recording_files", [])
        for rec in recordings:
            if rec.get("recording_type") == "audio_transcript":
                download_url = rec.get("download_url", "")
                if not download_url:
                    continue
                try:
                    resp = await self._client.get(download_url)
                    resp.raise_for_status()
                    return self._parse_vtt(resp.text)
                except Exception as e:
                    logger.warning(f"Failed to fetch Zoom transcript: {e}")
        return ""

    @staticmethod
    def _parse_vtt(vtt_content: str) -> str:
        lines = vtt_content.split("\n")
        text_lines: list[str] = []
        for line in lines:
            line = line.strip()
            if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
                continue
            if line.startswith("NOTE"):
                continue
            text_lines.append(line)
        return " ".join(text_lines)
