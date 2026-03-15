from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from mneia.connectors.google_auth import (
    _EMBEDDED_CLIENT_ID,
    _EMBEDDED_CLIENT_SECRET,
    _resolve_client_config,
)


def test_resolve_explicit_credentials():
    result = _resolve_client_config("my-id", "my-secret")
    assert result is not None
    assert result["installed"]["client_id"] == "my-id"
    assert result["installed"]["client_secret"] == "my-secret"


def test_resolve_env_vars():
    with patch.dict(os.environ, {
        "MNEIA_GOOGLE_CLIENT_ID": "env-id",
        "MNEIA_GOOGLE_CLIENT_SECRET": "env-secret",
    }):
        result = _resolve_client_config()
    assert result is not None
    assert result["installed"]["client_id"] == "env-id"
    assert result["installed"]["client_secret"] == "env-secret"


def test_resolve_credentials_file(tmp_path):
    creds_file = tmp_path / "google_credentials.json"
    creds_file.write_text(
        '{"installed": {"client_id": "file-id", "client_secret": "file-secret"}}'
    )
    with patch(
        "mneia.connectors.google_auth.GOOGLE_CREDENTIALS_PATH",
        creds_file,
    ), patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MNEIA_GOOGLE_CLIENT_ID", None)
        os.environ.pop("MNEIA_GOOGLE_CLIENT_SECRET", None)
        result = _resolve_client_config()
    assert result is not None
    assert result["installed"]["client_id"] == "file-id"


def test_resolve_falls_back_to_embedded():
    with patch(
        "mneia.connectors.google_auth.GOOGLE_CREDENTIALS_PATH",
        Path("/nonexistent/path"),
    ), patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MNEIA_GOOGLE_CLIENT_ID", None)
        os.environ.pop("MNEIA_GOOGLE_CLIENT_SECRET", None)
        result = _resolve_client_config()
    assert result is not None
    assert result["installed"]["client_id"] == _EMBEDDED_CLIENT_ID
    assert result["installed"]["client_secret"] == _EMBEDDED_CLIENT_SECRET


def test_resolve_explicit_takes_priority_over_env():
    with patch.dict(os.environ, {
        "MNEIA_GOOGLE_CLIENT_ID": "env-id",
        "MNEIA_GOOGLE_CLIENT_SECRET": "env-secret",
    }):
        result = _resolve_client_config("explicit-id", "explicit-secret")
    assert result["installed"]["client_id"] == "explicit-id"


def test_resolve_env_takes_priority_over_file(tmp_path):
    creds_file = tmp_path / "google_credentials.json"
    creds_file.write_text(
        '{"installed": {"client_id": "file-id", "client_secret": "file-secret"}}'
    )
    with patch(
        "mneia.connectors.google_auth.GOOGLE_CREDENTIALS_PATH",
        creds_file,
    ), patch.dict(os.environ, {
        "MNEIA_GOOGLE_CLIENT_ID": "env-id",
        "MNEIA_GOOGLE_CLIENT_SECRET": "env-secret",
    }):
        result = _resolve_client_config()
    assert result["installed"]["client_id"] == "env-id"


def test_resolve_bad_credentials_file(tmp_path):
    creds_file = tmp_path / "google_credentials.json"
    creds_file.write_text("not valid json {{")
    with patch(
        "mneia.connectors.google_auth.GOOGLE_CREDENTIALS_PATH",
        creds_file,
    ), patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MNEIA_GOOGLE_CLIENT_ID", None)
        os.environ.pop("MNEIA_GOOGLE_CLIENT_SECRET", None)
        result = _resolve_client_config()
    assert result is not None
    assert result["installed"]["client_id"] == _EMBEDDED_CLIENT_ID


def test_embedded_credentials_present():
    assert _EMBEDDED_CLIENT_ID
    assert _EMBEDDED_CLIENT_SECRET
    assert "apps.googleusercontent.com" in _EMBEDDED_CLIENT_ID
    assert _EMBEDDED_CLIENT_SECRET.startswith("GOCSPX-")
