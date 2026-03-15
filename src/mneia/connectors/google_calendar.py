from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)


class GoogleCalendarConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="google-calendar",
        display_name="Google Calendar",
        version="0.1.0",
        description="Read events from Google Calendar (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="oauth2",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        poll_interval_seconds=300,
        required_config=[],
        optional_config=[
            "google_client_id", "google_client_secret",
            "calendar_ids", "lookback_days",
        ],
    )

    def __init__(self) -> None:
        self._service: Any = None
        self._calendar_ids: list[str] = ["primary"]
        self._lookback_days: int = 30

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self.last_error = ""
        try:
            from mneia.connectors.google_auth import (
                build_service,
                get_google_credentials,
            )

            client_id = config.get("google_client_id", "")
            client_secret = config.get("google_client_secret", "")
            account = config.get("account_name", "")

            creds = get_google_credentials(
                "calendar", client_id, client_secret, account=account,
            )
            self._service = build_service("calendar", "v3", creds)
            self._account = account

            cal_ids = config.get("calendar_ids", "")
            if cal_ids:
                self._calendar_ids = [
                    c.strip() for c in cal_ids.split(",") if c.strip()
                ]

            lookback = config.get("lookback_days", "")
            if lookback:
                self._lookback_days = int(lookback)

            return True
        except ImportError:
            self.last_error = (
                "Google libraries not installed. "
                "Run: pip install 'mneia[google]'"
            )
            return False
        except Exception as e:
            self.last_error = f"Google Calendar auth failed: {e}"
            return False

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._service:
            return

        time_min = since or (datetime.now(timezone.utc) - timedelta(days=self._lookback_days))
        time_min_str = time_min.isoformat()

        for cal_id in self._calendar_ids:
            page_token = None
            while True:
                try:
                    result = (
                        self._service.events()
                        .list(
                            calendarId=cal_id,
                            timeMin=time_min_str,
                            maxResults=250,
                            singleEvents=True,
                            orderBy="startTime",
                            pageToken=page_token,
                        )
                        .execute()
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch events from {cal_id}: {e}")
                    break

                for event in result.get("items", []):
                    doc = self._event_to_document(event, cal_id)
                    if doc:
                        yield doc

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

    async def health_check(self) -> bool:
        if not self._service:
            return False
        try:
            self._service.calendarList().list(maxResults=1).execute()
            return True
        except Exception:
            return False

    def interactive_setup(self, account: str = "") -> dict[str, Any]:
        from mneia.connectors.google_auth import interactive_google_setup

        settings = interactive_google_setup("calendar", account=account)

        import typer

        cal_ids = typer.prompt(
            "  Calendar IDs (comma-separated, or 'primary' for default)",
            default="primary",
        )
        settings["calendar_ids"] = cal_ids

        lookback = typer.prompt("  Days of history to fetch", default="30")
        settings["lookback_days"] = lookback

        return settings

    def _event_to_document(self, event: dict[str, Any], cal_id: str) -> RawDocument | None:
        event_id = event.get("id", "")
        if not event_id:
            return None

        summary = event.get("summary", "Untitled Event")
        description = event.get("description", "")
        location = event.get("location", "")

        start_info = event.get("start", {})
        start_str = start_info.get("dateTime") or start_info.get("date", "")
        end_info = event.get("end", {})
        end_str = end_info.get("dateTime") or end_info.get("date", "")

        attendees = []
        for att in event.get("attendees", []):
            name = att.get("displayName") or att.get("email", "")
            if name:
                attendees.append(name)

        organizer = event.get("organizer", {})
        organizer_name = organizer.get("displayName") or organizer.get("email", "")

        content_parts = [f"# {summary}"]
        if start_str:
            content_parts.append(f"**When:** {start_str} — {end_str}")
        if location:
            content_parts.append(f"**Where:** {location}")
        if organizer_name:
            content_parts.append(f"**Organizer:** {organizer_name}")
        if attendees:
            content_parts.append(f"**Attendees:** {', '.join(attendees)}")
        if description:
            content_parts.append(f"\n{description}")

        content = "\n".join(content_parts)

        try:
            if "T" in start_str:
                timestamp = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.fromisoformat(start_str)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        metadata: dict[str, Any] = {
            "calendar_id": cal_id,
            "event_status": event.get("status", ""),
            "event_type": event.get("eventType", "default"),
        }
        if event.get("recurringEventId"):
            metadata["recurring"] = True
        if event.get("hangoutLink"):
            metadata["meeting_link"] = event["hangoutLink"]
        if event.get("conferenceData"):
            for entry in event["conferenceData"].get("entryPoints", []):
                if entry.get("entryPointType") == "video":
                    metadata["meeting_link"] = entry.get("uri", "")
                    break

        source = f"google-calendar-{self._account}" if getattr(self, "_account", "") else "google-calendar"
        return RawDocument(
            source=source,
            source_id=event_id,
            content=content,
            content_type="event",
            title=summary,
            timestamp=timestamp,
            metadata=metadata,
            url=event.get("htmlLink"),
            participants=attendees,
        )
