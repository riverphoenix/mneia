from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mneia.config import MNEIA_DIR

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_DIR = MNEIA_DIR / "google_tokens"
SCOPES_BY_SERVICE = {
    "calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
    "drive": ["https://www.googleapis.com/auth/drive.readonly"],
}


def _token_path(service: str) -> Path:
    GOOGLE_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    return GOOGLE_TOKEN_DIR / f"{service}_token.json"


def get_google_credentials(
    service: str,
    client_id: str,
    client_secret: str,
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
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception:
            logger.warning(f"Token refresh failed for {service}, re-authenticating")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

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

    typer.echo(f"\n  Google {service.title()} setup")
    typer.echo("  You need a Google Cloud project with the appropriate API enabled.")
    typer.echo("  Create credentials at: https://console.cloud.google.com/apis/credentials\n")

    client_id = typer.prompt("  Google Client ID")
    client_secret = typer.prompt("  Google Client Secret", hide_input=True)

    settings: dict[str, Any] = {
        "google_client_id": client_id,
        "google_client_secret": client_secret,
    }

    typer.echo(f"\n  Authenticating with Google {service.title()}...")
    try:
        creds = get_google_credentials(service, client_id, client_secret)
        if creds and creds.valid:
            typer.echo("  Authentication successful!")
        else:
            typer.echo("  Warning: Authentication may have failed.")
    except Exception as e:
        typer.echo(f"  Authentication error: {e}")
        typer.echo("  You can retry later with: mneia connector setup google-{service}")

    return settings
