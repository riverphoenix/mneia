from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mneia.connectors.audio_transcription import AudioTranscriptionConnector, SUPPORTED_EXTENSIONS


@pytest.fixture
def connector():
    return AudioTranscriptionConnector()


def test_manifest():
    c = AudioTranscriptionConnector()
    assert c.manifest.name == "audio-transcription"
    assert c.manifest.auth_type == "local"


def test_supported_extensions():
    assert ".mp3" in SUPPORTED_EXTENSIONS
    assert ".wav" in SUPPORTED_EXTENSIONS
    assert ".m4a" in SUPPORTED_EXTENSIONS


async def test_authenticate_no_dir(connector):
    result = await connector.authenticate({})
    assert result is False


async def test_authenticate_missing_dir(connector, tmp_path):
    result = await connector.authenticate({"audio_dir": str(tmp_path / "nonexistent")})
    assert result is False


async def test_authenticate_valid_dir(connector, tmp_path):
    with patch.object(
        AudioTranscriptionConnector, "_detect_backend", return_value="faster-whisper",
    ):
        result = await connector.authenticate({"audio_dir": str(tmp_path)})
    assert result is True
    assert connector._audio_dir == tmp_path


async def test_authenticate_with_options(connector, tmp_path):
    with patch.object(
        AudioTranscriptionConnector, "_detect_backend", return_value="faster-whisper",
    ):
        await connector.authenticate({
            "audio_dir": str(tmp_path),
            "whisper_model": "small",
            "language": "fr",
        })
    assert connector._whisper_model == "small"
    assert connector._language == "fr"


async def test_health_check_no_dir(connector):
    result = await connector.health_check()
    assert result is False


def test_detect_backend():
    backend = AudioTranscriptionConnector._detect_backend()
    assert backend in ("faster-whisper", "whisper-cpp", "none")


async def test_fetch_since_empty_dir(connector, tmp_path):
    connector._audio_dir = tmp_path
    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)
    assert docs == []


async def test_fetch_since_skips_non_audio(connector, tmp_path):
    (tmp_path / "readme.txt").write_text("not audio")
    (tmp_path / "data.json").write_text("{}")
    connector._audio_dir = tmp_path
    docs = []
    async for doc in connector.fetch_since(None):
        docs.append(doc)
    assert docs == []
