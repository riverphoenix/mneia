from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mneia.connectors.screencapturekit_audio import (
    _find_sck_binary,
    compile_capture_binary,
    is_available,
)


def test_is_available_not_darwin():
    with patch.object(platform, "system", return_value="Linux"):
        assert is_available() is False


def test_is_available_old_macos():
    with patch.object(platform, "system", return_value="Darwin"), \
         patch.object(platform, "mac_ver", return_value=("12.0.0", ("", "", ""), "")):
        assert is_available() is False


def test_is_available_macos_13():
    with patch.object(platform, "system", return_value="Darwin"), \
         patch.object(platform, "mac_ver", return_value=("13.0.0", ("", "", ""), "")):
        assert is_available() is True


def test_is_available_macos_14():
    with patch.object(platform, "system", return_value="Darwin"), \
         patch.object(platform, "mac_ver", return_value=("14.2.1", ("", "", ""), "")):
        assert is_available() is True


def test_is_available_bad_version():
    with patch.object(platform, "system", return_value="Darwin"), \
         patch.object(platform, "mac_ver", return_value=("", ("", "", ""), "")):
        assert is_available() is False


def test_find_sck_binary_not_exists(tmp_path):
    fake_dir = tmp_path / "connectors"
    fake_dir.mkdir()
    fake_file = fake_dir / "screencapturekit_audio.py"
    fake_file.write_text("")
    with patch(
        "mneia.connectors.screencapturekit_audio.__file__",
        str(fake_file),
    ):
        result = _find_sck_binary()
    assert result is None


def test_find_sck_binary_exists(tmp_path):
    fake_dir = tmp_path / "connectors"
    fake_dir.mkdir()
    fake_file = fake_dir / "screencapturekit_audio.py"
    fake_file.write_text("")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    binary = bin_dir / "mneia-audio-capture"
    binary.write_text("#!/bin/sh\necho test")
    binary.chmod(0o755)

    with patch(
        "mneia.connectors.screencapturekit_audio.__file__",
        str(fake_file),
    ):
        result = _find_sck_binary()
    assert result == binary


def test_compile_capture_binary_existing():
    fake_binary = Path("/tmp/fake-binary")
    with patch(
        "mneia.connectors.screencapturekit_audio._find_sck_binary",
        return_value=fake_binary,
    ):
        result = compile_capture_binary()
    assert result == fake_binary


def test_compile_capture_binary_swiftc_not_found():
    with patch(
        "mneia.connectors.screencapturekit_audio._find_sck_binary",
        return_value=None,
    ), patch(
        "subprocess.run",
        side_effect=FileNotFoundError("swiftc not found"),
    ):
        result = compile_capture_binary()
    assert result is None


def test_compile_capture_binary_compilation_fails():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "compilation error"

    with patch(
        "mneia.connectors.screencapturekit_audio._find_sck_binary",
        return_value=None,
    ), patch(
        "subprocess.run",
        return_value=mock_result,
    ):
        result = compile_capture_binary()
    assert result is None


@pytest.mark.asyncio
async def test_record_system_audio_no_binary():
    from mneia.connectors.screencapturekit_audio import record_system_audio

    with patch(
        "mneia.connectors.screencapturekit_audio._find_sck_binary",
        return_value=None,
    ), patch(
        "mneia.connectors.screencapturekit_audio.compile_capture_binary",
        return_value=None,
    ):
        result = await record_system_audio(Path("/tmp/test.wav"), duration_seconds=5)
    assert result is False
