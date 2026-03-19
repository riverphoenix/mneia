from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, AsyncIterator

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)


class GmailConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="gmail",
        display_name="Gmail",
        version="0.1.0",
        description="Read emails from Gmail (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="oauth2",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        poll_interval_seconds=300,
        required_config=[],
        optional_config=[
            "google_client_id", "google_client_secret",
            "max_results", "labels", "query",
        ],
    )

    def __init__(self) -> None:
        self._service: Any = None
        self._max_results: int = 100
        self._labels: list[str] = ["INBOX"]
        self._query: str = ""

    async def authenticate(self, config: dict[str, Any]) -> bool:
        try:
            from mneia.connectors.google_auth import build_service, get_google_credentials

            client_id = config.get("google_client_id", "")
            client_secret = config.get("google_client_secret", "")
            account = config.get("account_name", "")

            creds = get_google_credentials(
                "gmail", client_id, client_secret, account=account,
            )
            self._service = build_service("gmail", "v1", creds)
            self._account = account

            max_r = config.get("max_results", "")
            if max_r:
                self._max_results = int(max_r)

            labels = config.get("labels", "")
            if labels:
                self._labels = [l.strip() for l in labels.split(",") if l.strip()]

            self._query = config.get("query", "")

            return True
        except ImportError:
            logger.error("Google libraries not installed. Reinstall mneia.")
            return False
        except Exception as e:
            logger.error(f"Gmail auth failed: {e}")
            return False

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._service:
            return

        query = self._query
        if since:
            after_epoch = int(since.timestamp())
            date_filter = f"after:{after_epoch}"
            query = f"{query} {date_filter}".strip() if query else date_filter

        page_token = None
        fetched = 0

        while fetched < self._max_results:
            try:
                result = (
                    self._service.users()
                    .messages()
                    .list(
                        userId="me",
                        labelIds=self._labels,
                        q=query or None,
                        maxResults=min(50, self._max_results - fetched),
                        pageToken=page_token,
                    )
                    .execute()
                )
            except Exception as e:
                logger.error(f"Failed to list messages: {e}")
                break

            messages = result.get("messages", [])
            if not messages:
                break

            for msg_stub in messages:
                doc = await self._fetch_message(msg_stub["id"])
                if doc:
                    yield doc
                    fetched += 1

            page_token = result.get("nextPageToken")
            if not page_token:
                break

    async def health_check(self) -> bool:
        if not self._service:
            return False
        try:
            self._service.users().getProfile(userId="me").execute()
            return True
        except Exception:
            return False

    def interactive_setup(self, account: str = "") -> dict[str, Any]:
        from mneia.connectors.google_auth import interactive_google_setup

        settings = interactive_google_setup("gmail", account=account)

        import typer

        max_r = typer.prompt("  Max emails to fetch per sync", default="100")
        settings["max_results"] = max_r

        labels = typer.prompt("  Labels to read (comma-separated)", default="INBOX")
        settings["labels"] = labels

        query = typer.prompt("  Gmail search query (optional)", default="")
        if query:
            settings["query"] = query

        return settings

    async def _fetch_message(self, msg_id: str) -> RawDocument | None:
        try:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except Exception as e:
            logger.warning(f"Failed to fetch message {msg_id}: {e}")
            return None

        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

        subject = headers.get("subject", "No Subject")
        from_addr = headers.get("from", "")
        to_addr = headers.get("to", "")
        cc_addr = headers.get("cc", "")
        date_str = headers.get("date", "")

        body = self._extract_body(msg.get("payload", {}))

        participants = []
        for addr_field in [from_addr, to_addr, cc_addr]:
            participants.extend(self._parse_addresses(addr_field))

        try:
            timestamp = parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
        except Exception:
            timestamp = datetime.now(timezone.utc)

        content_parts = [f"# {subject}"]
        if from_addr:
            content_parts.append(f"**From:** {from_addr}")
        if to_addr:
            content_parts.append(f"**To:** {to_addr}")
        if cc_addr:
            content_parts.append(f"**CC:** {cc_addr}")
        content_parts.append(f"**Date:** {date_str}")
        if body:
            content_parts.append(f"\n{body}")

        content = "\n".join(content_parts)

        labels = msg.get("labelIds", [])
        metadata: dict[str, Any] = {
            "labels": labels,
            "thread_id": msg.get("threadId", ""),
            "snippet": msg.get("snippet", ""),
        }

        source = f"gmail-{self._account}" if getattr(self, "_account", "") else "gmail"
        return RawDocument(
            source=source,
            source_id=msg_id,
            content=content,
            content_type="email",
            title=subject,
            timestamp=timestamp,
            metadata=metadata,
            participants=participants,
        )

    def _extract_body(self, payload: dict[str, Any]) -> str:
        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        if mime_type == "text/html":
            data = payload.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                return self._strip_html(html)

        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result

        return ""

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _parse_addresses(addr_str: str) -> list[str]:
        if not addr_str:
            return []
        results = []
        for part in addr_str.split(","):
            part = part.strip()
            match = re.search(r"([^<]+)\s*<", part)
            if match:
                name = match.group(1).strip().strip('"')
                if name:
                    results.append(name)
            else:
                email_match = re.search(r"[\w.+-]+@[\w.-]+", part)
                if email_match:
                    results.append(email_match.group(0))
        return results
