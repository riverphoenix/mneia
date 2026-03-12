from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from mneia.config import MNEIA_DIR

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_DIR = MNEIA_DIR / "google_tokens"
GOOGLE_CREDENTIALS_PATH = MNEIA_DIR / "google_credentials.json"

_EMBEDDED_CLIENT_ID = (
    "1012814324132-4qsc451k3nint5s7rn01m8l8n3njm236"
    ".apps.googleusercontent.com"
)
_EMBEDDED_CLIENT_SECRET = "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"

SCOPES_BY_SERVICE = {
    "calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
    "drive": ["https://www.googleapis.com/auth/drive.readonly"],
}


def _token_path(service: str) -> Path:
    GOOGLE_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    return GOOGLE_TOKEN_DIR / f"{service}_token.json"


def _resolve_client_config(
    client_id: str = "",
    client_secret: str = "",
) -> dict[str, Any] | None:
    if client_id and client_secret:
        return {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

    env_id = os.environ.get("MNEIA_GOOGLE_CLIENT_ID", "")
    env_secret = os.environ.get("MNEIA_GOOGLE_CLIENT_SECRET", "")
    if env_id and env_secret:
        return {
            "installed": {
                "client_id": env_id,
                "client_secret": env_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

    if GOOGLE_CREDENTIALS_PATH.exists():
        try:
            data = json.loads(
                GOOGLE_CREDENTIALS_PATH.read_text(encoding="utf-8")
            )
            if "installed" in data or "web" in data:
                return data
        except Exception:
            logger.warning("Could not parse google_credentials.json")

    if _EMBEDDED_CLIENT_ID and _EMBEDDED_CLIENT_SECRET:
        return {
            "installed": {
                "client_id": _EMBEDDED_CLIENT_ID,
                "client_secret": _EMBEDDED_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

    return None


def get_google_credentials(
    service: str,
    client_id: str = "",
    client_secret: str = "",
    scopes: list[str] | None = None,
) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ImportError(
            "Google auth libraries not installed. "
            "Install with: pip install 'mneia[google]'"
        )

    if scopes is None:
        scopes = SCOPES_BY_SERVICE.get(service, [])

    token_file = _token_path(service)
    creds: Credentials | None = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(
            str(token_file), scopes,
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception:
            logger.warning(
                f"Token refresh failed for {service}, re-authenticating"
            )

    client_config = _resolve_client_config(client_id, client_secret)
    if not client_config:
        raise ValueError(
            "No Google OAuth credentials found. "
            "Run: mneia connector setup google-calendar"
        )

    flow = InstalledAppFlow.from_client_config(client_config, scopes)
    creds = flow.run_local_server(port=0, open_browser=True)

    token_file.write_text(creds.to_json(), encoding="utf-8")
    logger.info(f"Google OAuth2 credentials saved for {service}")
    return creds


def build_service(service_name: str, version: str, credentials: Any) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Google API client not installed. "
            "Install with: pip install 'mneia[google]'"
        )
    return build(service_name, version, credentials=credentials)


def interactive_google_setup(service: str) -> dict[str, Any]:
    import typer

    service_label = {
        "calendar": "Google Calendar",
        "gmail": "Gmail",
        "drive": "Google Drive",
    }.get(service, f"Google {service.title()}")

    typer.echo(f"\n  Connect {service_label}")
    typer.echo("  ─" * 25)
    typer.echo(
        "\n  A browser window will open."
    )
    typer.echo(
        "  Sign in with your Google account and grant "
        "read-only access."
    )
    typer.echo(
        "  mneia will never modify your data.\n"
    )

    try:
        creds = get_google_credentials(service)
        if creds and creds.valid:
            typer.echo("  ✓ Connected successfully!")
        else:
            typer.echo("  ⚠ Authorization may have failed.")
    except Exception as e:
        typer.echo(f"  ✗ Error: {e}")
        typer.echo(
            "  You can retry with: "
            f"mneia connector setup google-{service}"
        )

    return {}
