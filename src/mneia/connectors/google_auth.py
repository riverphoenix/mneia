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

    api_name = {
        "calendar": "Google Calendar API",
        "gmail": "Gmail API",
        "drive": "Google Drive API",
    }.get(service, f"Google {service.title()} API")

    typer.echo(f"\n  Google {service.title()} — Connect Your Account")
    typer.echo("  ─" * 25)

    existing_config = _resolve_client_config()
    if existing_config:
        typer.echo(
            "\n  ✓ Google credentials found. "
            "Opening browser to authorize..."
        )
        typer.echo(
            "  Sign in with your Google account and grant "
            "read-only access.\n"
        )
        try:
            creds = get_google_credentials(service)
            if creds and creds.valid:
                typer.echo("  ✓ Connected successfully!")
                return {}
            else:
                typer.echo("  ⚠ Authorization may have failed.")
                return {}
        except Exception as e:
            typer.echo(f"  ✗ Error: {e}")
            return {}

    typer.echo("\n  First-time setup — choose how to connect:\n")
    typer.echo(
        "  [1] Download credentials file (recommended)"
    )
    typer.echo("  [2] Enter Client ID and Secret manually")
    typer.echo("")

    choice = typer.prompt("  Choice", default="1")

    settings: dict[str, Any] = {}

    if choice == "1":
        typer.echo("\n  Quick setup (one-time, ~2 minutes):")
        typer.echo("")
        typer.echo(
            "  1. Go to https://console.cloud.google.com/"
        )
        typer.echo("  2. Create a project (or pick an existing one)")
        typer.echo(
            f"  3. Enable {api_name}: search it in API Library → Enable"
        )
        typer.echo("  4. Go to APIs & Services → Credentials")
        typer.echo(
            "  5. + Create Credentials → OAuth client ID → "
            "Desktop app"
        )
        typer.echo(
            "     (If asked, configure consent screen: "
            "External, add your email)"
        )
        typer.echo("  6. Click 'Download JSON' on the created credential")
        typer.echo(
            f"  7. Save it as: {GOOGLE_CREDENTIALS_PATH}"
        )
        typer.echo("")

        typer.echo("  Press Enter once the file is in place...")
        input()

        if GOOGLE_CREDENTIALS_PATH.exists():
            typer.echo(
                "  ✓ Credentials file found. "
                "Opening browser to authorize..."
            )
            typer.echo(
                "  Sign in and grant read-only access.\n"
            )
            try:
                creds = get_google_credentials(service)
                if creds and creds.valid:
                    typer.echo("  ✓ Connected successfully!")
                else:
                    typer.echo("  ⚠ Authorization may have failed.")
            except Exception as e:
                typer.echo(f"  ✗ Error: {e}")
        else:
            typer.echo(
                f"  ✗ File not found: {GOOGLE_CREDENTIALS_PATH}"
            )
            typer.echo(
                "  You can retry with: "
                f"mneia connector setup google-{service}"
            )

    else:
        typer.echo("")
        client_id = typer.prompt("  Google Client ID")
        client_secret = typer.prompt(
            "  Google Client Secret", hide_input=True,
        )

        settings = {
            "google_client_id": client_id,
            "google_client_secret": client_secret,
        }

        typer.echo(
            f"\n  Authenticating with {api_name}..."
        )
        typer.echo("  A browser window will open — sign in "
                    "and grant read-only access.\n")
        try:
            creds = get_google_credentials(
                service, client_id, client_secret,
            )
            if creds and creds.valid:
                typer.echo("  ✓ Connected successfully!")
            else:
                typer.echo("  ⚠ Authorization may have failed.")
        except Exception as e:
            typer.echo(f"  ✗ Error: {e}")
            typer.echo(
                "  Retry with: "
                f"mneia connector setup google-{service}"
            )

    return settings
