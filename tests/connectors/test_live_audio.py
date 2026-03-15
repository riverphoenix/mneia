from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from unittest.mock import patch

from mneia.connectors.live_audio import LiveAudioConnector
from mneia.connectors.transcription_engine import detect_backend

_mock_sd = types.ModuleType("sounddevice")
sys.modules.setdefault("sounddevice", _mock_sd)


def test_live_audio_manifest():
    c = LiveAudioConnector()
    assert c.manifest.name == "live-audio"
    assert c.manifest.mode.value == "watch"


async def test_authenticate_success():
    with patch(
        "mneia.connectors.live_audio.detect_backend",
        return_value="faster-whisper",
    ), patch(
        "mneia.connectors.live_audio._detect_capture_method",
        return_value="sounddevice",
    ):
        c = LiveAudioConnector()
        result = await c.authenticate({
            "whisper_model": "small",
            "language": "en",
        })
    assert result is True
    assert c._whisper_model == "small"


async def test_authenticate_no_backend():
    with patch(
        "mneia.connectors.live_audio.detect_backend",
        return_value="none",
    ):
        c = LiveAudioConnector()
        result = await c.authenticate({})
    assert result is False


async def test_authenticate_with_device():
    with patch(
        "mneia.connectors.live_audio.detect_backend",
        return_value="faster-whisper",
    ), patch(
        "mneia.connectors.live_audio._detect_capture_method",
        return_value="sounddevice",
    ):
        c = LiveAudioConnector()
        result = await c.authenticate({
            "audio_device": "BlackHole 2ch",
            "chunk_seconds": "15",
        })
    assert result is True
    assert c._audio_device == "BlackHole 2ch"
    assert c._chunk_seconds == 15


async def test_authenticate_screencapturekit():
    with patch(
        "mneia.connectors.live_audio.detect_backend",
        return_value="faster-whisper",
    ), patch(
        "mneia.connectors.live_audio._detect_capture_method",
        return_value="screencapturekit",
    ), patch(
        "mneia.connectors.screencapturekit_audio.compile_capture_binary",
        return_value="/tmp/fake-binary",
    ):
        c = LiveAudioConnector()
        result = await c.authenticate({})
    assert result is True
    assert c._capture_method == "screencapturekit"


def test_create_document():
    c = LiveAudioConnector()
    c._meeting_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    c._chunk_index = 3
    c._whisper_model = "base"
    c._chunk_seconds = 30

    doc = c._create_document("Hello, this is a test transcript.")
    assert doc.source == "live-audio"
    assert doc.content_type == "live_transcript"
    assert "chunk 3" in doc.title
    assert doc.metadata["chunk_index"] == 3
    assert doc.metadata["meeting_id"] == "20240101-000000"


async def test_stop_recording():
    c = LiveAudioConnector()
    c._recording = True
    await c.stop_recording()
    assert c._recording is False


async def test_fetch_since_empty():
    c = LiveAudioConnector()
    docs = []
    async for doc in c.fetch_since(None):
        docs.append(doc)
    assert docs == []


def test_detect_backend_none():
    with patch.dict("sys.modules", {"faster_whisper": None}), \
         patch("shutil.which", return_value=None):
        result = detect_backend()
    assert result == "none"


def test_granola_registered():
    from mneia.connectors import get_available_connectors

    manifests = get_available_connectors()
    names = {m.name for m in manifests}
    assert "granola" in names
