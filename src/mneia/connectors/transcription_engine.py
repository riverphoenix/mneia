from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_backend() -> str:
    try:
        import faster_whisper  # noqa: F401
        return "faster-whisper"
    except ImportError:
        pass

    if shutil.which("whisper-cpp") or shutil.which("main"):
        return "whisper-cpp"

    return "none"


def transcribe(
    audio_path: Path,
    backend: str = "auto",
    model: str = "base",
    language: str = "en",
) -> str:
    if backend == "auto":
        backend = detect_backend()

    if backend == "faster-whisper":
        return _transcribe_faster_whisper(audio_path, model, language)
    if backend == "whisper-cpp":
        return _transcribe_whisper_cpp(audio_path, model, language)

    logger.error("No whisper backend available")
    return ""


def _transcribe_faster_whisper(
    audio_path: Path, model_name: str, language: str,
) -> str:
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(
            model_name, device="auto", compute_type="int8",
        )
        segments, _info = model.transcribe(
            str(audio_path), language=language,
        )
        return " ".join(segment.text.strip() for segment in segments)
    except ImportError:
        logger.error("faster-whisper not installed")
        return ""
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return ""


def _transcribe_whisper_cpp(
    audio_path: Path, model_name: str, language: str,
) -> str:
    whisper_bin = shutil.which("whisper-cpp") or shutil.which("main")
    if not whisper_bin:
        logger.error("whisper-cpp binary not found")
        return ""

    try:
        result = subprocess.run(
            [
                whisper_bin,
                "-m", f"models/ggml-{model_name}.bin",
                "-f", str(audio_path),
                "-l", language,
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
