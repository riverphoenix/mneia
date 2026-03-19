from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)

GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEETS_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDES_MIME = "application/vnd.google-apps.presentation"
EXPORT_MIME_MAP = {
    GOOGLE_DOCS_MIME: ("text/plain", "doc"),
    GOOGLE_SHEETS_MIME: ("text/csv", "sheet"),
    GOOGLE_SLIDES_MIME: ("text/plain", "slides"),
}
READABLE_MIMES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "application/json",
}


class GoogleDriveConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="google-drive",
        display_name="Google Drive",
        version="0.1.0",
        description="Read files from Google Drive including Docs, Sheets, Slides (read-only)",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="oauth2",
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        poll_interval_seconds=600,
        required_config=[],
        optional_config=[
            "google_client_id", "google_client_secret",
            "folder_ids", "max_results", "include_shared",
        ],
    )

    def __init__(self) -> None:
        self._service: Any = None
        self._folder_ids: list[str] = []
        self._max_results: int = 100
        self._include_shared: bool = True

    async def authenticate(self, config: dict[str, Any]) -> bool:
        try:
            from mneia.connectors.google_auth import build_service, get_google_credentials

            client_id = config.get("google_client_id", "")
            client_secret = config.get("google_client_secret", "")
            account = config.get("account_name", "")

            creds = get_google_credentials(
                "drive", client_id, client_secret, account=account,
            )
            self._service = build_service("drive", "v3", creds)
            self._account = account

            folder_ids = config.get("folder_ids", "")
            if folder_ids:
                self._folder_ids = [f.strip() for f in folder_ids.split(",") if f.strip()]

            max_r = config.get("max_results", "")
            if max_r:
                self._max_results = int(max_r)

            shared = config.get("include_shared", "true")
            self._include_shared = shared.lower() in ("true", "1", "yes")

            return True
        except ImportError:
            logger.error("Google libraries not installed. Reinstall mneia.")
            return False
        except Exception as e:
            logger.error(f"Google Drive auth failed: {e}")
            return False

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._service:
            return

        query_parts = ["trashed = false"]

        if since:
            modified_time = since.strftime("%Y-%m-%dT%H:%M:%S")
            query_parts.append(f"modifiedTime > '{modified_time}'")

        if self._folder_ids:
            folder_filter = " or ".join(f"'{fid}' in parents" for fid in self._folder_ids)
            query_parts.append(f"({folder_filter})")

        mime_filter_parts = []
        for mime in EXPORT_MIME_MAP:
            mime_filter_parts.append(f"mimeType = '{mime}'")
        for mime in READABLE_MIMES:
            mime_filter_parts.append(f"mimeType = '{mime}'")
        query_parts.append(f"({' or '.join(mime_filter_parts)})")

        query = " and ".join(query_parts)

        page_token = None
        fetched = 0

        while fetched < self._max_results:
            try:
                result = (
                    self._service.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, owners, webViewLink, parents)",
                        pageSize=min(50, self._max_results - fetched),
                        pageToken=page_token,
                        orderBy="modifiedTime desc",
                        includeItemsFromAllDrives=self._include_shared,
                        supportsAllDrives=True,
                    )
                    .execute()
                )
            except Exception as e:
                logger.error(f"Failed to list Drive files: {e}")
                break

            files = result.get("files", [])
            if not files:
                break

            for file_meta in files:
                doc = await self._fetch_file_content(file_meta)
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
            self._service.about().get(fields="user").execute()
            return True
        except Exception:
            return False

    def interactive_setup(self, account: str = "") -> dict[str, Any]:
        from mneia.connectors.google_auth import interactive_google_setup

        settings = interactive_google_setup("drive", account=account)

        import typer

        folder_ids = typer.prompt("  Folder IDs to scan (comma-separated, or empty for all)", default="")
        if folder_ids:
            settings["folder_ids"] = folder_ids

        max_r = typer.prompt("  Max files to fetch per sync", default="100")
        settings["max_results"] = max_r

        shared = typer.prompt("  Include shared drives? (yes/no)", default="yes")
        settings["include_shared"] = shared

        return settings

    async def _fetch_file_content(self, file_meta: dict[str, Any]) -> RawDocument | None:
        file_id = file_meta.get("id", "")
        name = file_meta.get("name", "Untitled")
        mime_type = file_meta.get("mimeType", "")
        modified_time = file_meta.get("modifiedTime", "")

        try:
            if mime_type in EXPORT_MIME_MAP:
                export_mime, content_type = EXPORT_MIME_MAP[mime_type]
                content = (
                    self._service.files()
                    .export(fileId=file_id, mimeType=export_mime)
                    .execute()
                )
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="replace")
            elif mime_type in READABLE_MIMES:
                content = (
                    self._service.files()
                    .get_media(fileId=file_id)
                    .execute()
                )
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="replace")
                content_type = "document"
            else:
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch content for {name}: {e}")
            return None

        if not content or not content.strip():
            return None

        if len(content) > 50000:
            content = content[:50000] + "\n\n[Content truncated]"

        try:
            timestamp = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        owners = file_meta.get("owners", [])
        participants = [o.get("displayName", o.get("emailAddress", "")) for o in owners]

        metadata: dict[str, Any] = {
            "mime_type": mime_type,
            "parents": file_meta.get("parents", []),
        }

        source = f"google-drive-{self._account}" if getattr(self, "_account", "") else "google-drive"
        return RawDocument(
            source=source,
            source_id=file_id,
            content=content,
            content_type=content_type if mime_type in EXPORT_MIME_MAP else "document",
            title=name,
            timestamp=timestamp,
            metadata=metadata,
            url=file_meta.get("webViewLink"),
            participants=participants,
        )
