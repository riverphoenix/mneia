from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from mneia.core.connector import (
    BaseConnector,
    ConnectorManifest,
    ConnectorMode,
    RawDocument,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}


class AudioTranscriptionConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="audio-transcription",
        display_name="Audio Transcription",
        version="0.1.0",
        description="Transcribe audio files using whisper.cpp or faster-whisper",
        author="mneia-team",
        mode=ConnectorMode.POLL,
        auth_type="local",
        scopes=["read"],
        poll_interval_seconds=600,
        required_config=["audio_dir"],
        optional_config=["whisper_model", "language", "backend"],
    )

    def __init__(self) -> None:
        self._audio_dir: Path | None = None
        self._whisper_model: str = "base"
        self._language: str = "en"
        self._backend: str = "auto"

    async def authenticate(self, config: dict[str, Any]) -> bool:
        audio_dir = config.get("audio_dir", "")
        if not audio_dir:
            return False

        self._audio_dir = Path(audio_dir)
        if not self._audio_dir.exists():
            logger.error(f"Audio directory not found: {self._audio_dir}")
            return False

        self._whisper_model = config.get("whisper_model", "base")
        self._language = config.get("language", "en")
        self._backend = config.get("backend", "auto")

        if self._backend == "auto":
            self._backend = self._detect_backend()

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        if not self._audio_dir:
            return

        for audio_file in sorted(self._audio_dir.iterdir()):
            if audio_file.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if not audio_file.is_file():
                continue

            mtime = datetime.fromtimestamp(audio_file.stat().st_mtime, tz=timezone.utc)
            if since and mtime <= since:
                continue

            transcript = self._transcribe(audio_file)
            if not transcript:
                continue

            source_id = hashlib.md5(str(audio_file).encode()).hexdigest()

            yield RawDocument(
                source="audio-transcription",
                source_id=source_id,
                content=transcript,
                content_type="transcript",
                title=audio_file.stem,
                timestamp=mtime,
                metadata={
                    "file_path": str(audio_file),
                    "file_size": audio_file.stat().st_size,
                    "backend": self._backend,
                    "model": self._whisper_model,
                },
            )

    async def health_check(self) -> bool:
        if not self._audio_dir or not self._audio_dir.exists():
            return False
        backend = self._detect_backend()
        return backend != "none"

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Audio Transcription setup — transcribes audio files locally.")
        typer.echo("  Requires whisper.cpp or faster-whisper installed.\n")

        backend = self._detect_backend()
        if backend == "none":
            typer.echo("  [WARNING] No whisper backend found!")
            typer.echo("  Install faster-whisper: pip install faster-whisper")
            typer.echo("  Or install whisper.cpp: brew install whisper-cpp\n")

        audio_dir = typer.prompt("  Directory containing audio files")
        model = typer.prompt("  Whisper model (tiny/base/small/medium/large)", default="base")
        language = typer.prompt("  Language code", default="en")

        return {
            "audio_dir": audio_dir,
            "whisper_model": model,
            "language": language,
        }

    def _transcribe(self, audio_path: Path) -> str:
        if self._backend == "faster-whisper":
            return self._transcribe_faster_whisper(audio_path)
        if self._backend == "whisper-cpp":
            return self._transcribe_whisper_cpp(audio_path)
        logger.error("No whisper backend available")
        return ""

    def _transcribe_faster_whisper(self, audio_path: Path) -> str:
        try:
            from faster_whisper import WhisperModel

            model = WhisperModel(self._whisper_model, device="auto", compute_type="int8")
            segments, _info = model.transcribe(str(audio_path), language=self._language)
            return " ".join(segment.text.strip() for segment in segments)
        except ImportError:
            logger.error("faster-whisper not installed")
            return ""
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    def _transcribe_whisper_cpp(self, audio_path: Path) -> str:
        whisper_bin = shutil.which("whisper-cpp") or shutil.which("main")
        if not whisper_bin:
            logger.error("whisper-cpp binary not found")
            return ""

        try:
            result = subprocess.run(
                [
                    whisper_bin,
                    "-m", f"models/ggml-{self._whisper_model}.bin",
                    "-f", str(audio_path),
                    "-l", self._language,
                    "--no-timestamps",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            logger.error(f"whisper-cpp error: {result.stderr}")
            return ""
        except Exception as e:
            logger.error(f"whisper-cpp failed: {e}")
            return ""

    @staticmethod
    def _detect_backend() -> str:
        try:
            import faster_whisper  # noqa: F401
            return "faster-whisper"
        except ImportError:
            pass

        if shutil.which("whisper-cpp") or shutil.which("main"):
            return "whisper-cpp"

        return "none"
