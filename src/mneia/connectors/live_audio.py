from __future__ import annotations

import asyncio
import logging
import tempfile
import wave
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mneia.connectors.transcription_engine import detect_backend, transcribe
from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)

CHUNK_DURATION_SECONDS = 30
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2


class LiveAudioConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="live-audio",
        display_name="Live Audio Capture",
        version="0.1.0",
        description=(
            "Capture system audio during meetings and transcribe "
            "in real-time (requires virtual audio device)"
        ),
        author="mneia-team",
        mode=ConnectorMode.WATCH,
        auth_type="local",
        scopes=["audio:capture"],
        poll_interval_seconds=0,
        required_config=[],
        optional_config=[
            "audio_device",
            "whisper_model",
            "language",
            "chunk_seconds",
        ],
    )

    def __init__(self) -> None:
        self._audio_device: str | None = None
        self._whisper_model: str = "base"
        self._language: str = "en"
        self._chunk_seconds: int = CHUNK_DURATION_SECONDS
        self._backend: str = "auto"
        self._recording: bool = False
        self._meeting_start: datetime | None = None
        self._chunk_index: int = 0

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self.last_error = ""
        self._audio_device = config.get("audio_device")
        self._whisper_model = config.get("whisper_model", "base")
        self._language = config.get("language", "en")

        chunk_s = config.get("chunk_seconds", "")
        if chunk_s:
            self._chunk_seconds = int(chunk_s)

        try:
            import sounddevice  # noqa: F401
        except ImportError:
            self.last_error = "sounddevice not installed. Run: pip install 'mneia[audio]'"
            logger.error(self.last_error)
            return False

        self._backend = detect_backend()
        if self._backend == "none":
            self.last_error = (
                "No whisper backend found. Install faster-whisper or whisper-cpp"
            )
            logger.error(self.last_error)
            return False

        return True

    async def fetch_since(
        self, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        return
        yield  # noqa: RET504

    async def start_recording(self) -> AsyncIterator[RawDocument]:
        self._recording = True
        self._meeting_start = datetime.now(timezone.utc)
        self._chunk_index = 0

        logger.info(
            f"Live audio capture started "
            f"(device={self._audio_device}, "
            f"chunk={self._chunk_seconds}s)"
        )

        try:
            async for doc in self._capture_loop():
                yield doc
        finally:
            self._recording = False
            logger.info("Live audio capture stopped")

    async def stop_recording(self) -> None:
        self._recording = False

    async def health_check(self) -> bool:
        backend = detect_backend()
        if backend == "none":
            return False
        has_sounddevice = _check_sounddevice()
        return has_sounddevice

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo(
            "\n  Live Audio Capture — records system audio "
            "and transcribes."
        )
        typer.echo(
            "  macOS: Install BlackHole for virtual audio device."
        )
        typer.echo(
            "  Linux: Use PulseAudio monitor source.\n"
        )

        device = typer.prompt(
            "  Audio device name (or empty for default)",
            default="",
        )
        model = typer.prompt("  Whisper model", default="base")
        language = typer.prompt("  Language", default="en")

        settings: dict[str, Any] = {
            "whisper_model": model,
            "language": language,
        }
        if device:
            settings["audio_device"] = device
        return settings

    async def _capture_loop(self) -> AsyncIterator[RawDocument]:
        while self._recording:
            tmp_dir = tempfile.mkdtemp(prefix="mneia-audio-")
            wav_path = Path(tmp_dir) / f"chunk_{self._chunk_index}.wav"

            try:
                recorded = await self._record_chunk(wav_path)
                if not recorded:
                    await asyncio.sleep(1)
                    continue

                text = await asyncio.to_thread(
                    transcribe,
                    wav_path,
                    backend=self._backend,
                    model=self._whisper_model,
                    language=self._language,
                )

                if text and len(text.strip()) > 10:
                    self._chunk_index += 1
                    yield self._create_document(text)
            except Exception as e:
                logger.error(f"Capture chunk failed: {e}")
                await asyncio.sleep(1)
            finally:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)

    async def _record_chunk(self, output_path: Path) -> bool:
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice not installed")
            return False

        try:
            device_index = None
            if self._audio_device:
                devices = sd.query_devices()
                for i, dev in enumerate(devices):
                    if self._audio_device.lower() in dev["name"].lower():
                        device_index = i
                        break

            frames = await asyncio.to_thread(
                sd.rec,
                int(self._chunk_seconds * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                device=device_index,
            )
            await asyncio.to_thread(sd.wait)

            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(frames.tobytes())

            return True
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            return False

    def _create_document(self, text: str) -> RawDocument:
        now = datetime.now(timezone.utc)
        meeting_id = (
            self._meeting_start.strftime("%Y%m%d-%H%M%S")
            if self._meeting_start
            else "unknown"
        )

        return RawDocument(
            source="live-audio",
            source_id=f"live-{meeting_id}-{self._chunk_index}",
            content=text,
            content_type="live_transcript",
            title=(
                f"Live transcript chunk {self._chunk_index} "
                f"({meeting_id})"
            ),
            timestamp=now,
            metadata={
                "meeting_id": meeting_id,
                "chunk_index": self._chunk_index,
                "meeting_start": (
                    self._meeting_start.isoformat()
                    if self._meeting_start
                    else None
                ),
                "chunk_duration_seconds": self._chunk_seconds,
                "whisper_model": self._whisper_model,
            },
        )


def _check_sounddevice() -> bool:
    try:
        import sounddevice  # noqa: F401
        return True
    except ImportError:
        return False
