from __future__ import annotations

import hashlib
import logging
import re
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

TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".text", ".rst", ".org",
    ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml",
    ".xml", ".html", ".htm", ".css", ".js", ".ts",
    ".py", ".rb", ".go", ".rs", ".java", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".sh", ".bash", ".zsh",
    ".sql", ".r", ".m", ".tex", ".bib", ".log", ".cfg", ".ini", ".conf",
    ".env", ".properties", ".gradle", ".tf", ".hcl",
}

BINARY_DOC_EXTENSIONS = {".pdf"}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _is_bm25_available() -> bool:
    try:
        from rank_bm25 import BM25Okapi  # noqa: F401
        return True
    except ImportError:
        return False


class LocalFoldersConnector(BaseConnector):
    manifest = ConnectorManifest(
        name="local-folders",
        display_name="Local Folders",
        version="0.1.0",
        description=(
            "Scan and monitor local directories for documents "
            "(markdown, text, code, PDF). Supports multiple folders "
            "with glob patterns and exclusions."
        ),
        author="mneia-team",
        mode=ConnectorMode.WATCH,
        auth_type="local",
        scopes=["filesystem:read"],
        poll_interval_seconds=120,
        required_config=["paths"],
        optional_config=[
            "extensions", "exclude_patterns", "exclude_dirs",
            "max_file_size_mb", "include_hidden", "bm25_search",
        ],
        watch_paths_config_key="paths",
        watch_extensions=[".md", ".txt", ".py", ".json"],
    )

    def __init__(self) -> None:
        self._paths: list[Path] = []
        self._extensions: set[str] = TEXT_EXTENSIONS | BINARY_DOC_EXTENSIONS
        self._exclude_patterns: list[str] = []
        self._exclude_dirs: set[str] = {
            ".git", ".hg", ".svn", "node_modules", "__pycache__",
            ".venv", "venv", ".tox", ".mypy_cache", ".ruff_cache",
            "dist", "build", ".eggs", "*.egg-info",
        }
        self._max_file_size: int = MAX_FILE_SIZE
        self._include_hidden: bool = False
        self._bm25_enabled: bool = True
        self._bm25_index: Any = None
        self._bm25_docs: list[str] = []

    async def authenticate(self, config: dict[str, Any]) -> bool:
        self.last_error = ""
        paths_str = config.get("paths", "")
        if not paths_str:
            self.last_error = "No paths configured. Run: mneia connector setup local-folders"
            return False

        paths = [p.strip() for p in paths_str.split(",") if p.strip()]
        resolved: list[Path] = []
        for p in paths:
            path = Path(p).expanduser().resolve()
            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                continue
            if not path.is_dir():
                logger.warning(f"Not a directory: {path}")
                continue
            resolved.append(path)

        if not resolved:
            self.last_error = f"None of the configured paths exist: {paths_str}"
            return False

        self._paths = resolved

        ext = config.get("extensions", "")
        if ext:
            self._extensions = {
                e.strip() if e.strip().startswith(".") else f".{e.strip()}"
                for e in ext.split(",") if e.strip()
            }

        exclude_pat = config.get("exclude_patterns", "")
        if exclude_pat:
            self._exclude_patterns = [p.strip() for p in exclude_pat.split(",") if p.strip()]

        exclude_dirs = config.get("exclude_dirs", "")
        if exclude_dirs:
            extra = {d.strip() for d in exclude_dirs.split(",") if d.strip()}
            self._exclude_dirs = self._exclude_dirs | extra

        max_size = config.get("max_file_size_mb", "")
        if max_size:
            self._max_file_size = int(float(max_size) * 1024 * 1024)

        self._include_hidden = config.get("include_hidden", "").lower() in ("true", "1", "yes")

        bm25_setting = config.get("bm25_search", "true").lower()
        self._bm25_enabled = bm25_setting in ("true", "1", "yes", "")
        if self._bm25_enabled and _is_bm25_available():
            logger.info("BM25 search enabled for local folders")
        elif self._bm25_enabled:
            logger.info("rank_bm25 not installed — install with: pip install 'mneia[search]'")
            self._bm25_enabled = False

        return True

    async def fetch_since(self, since: datetime | None) -> AsyncIterator[RawDocument]:
        for base_path in self._paths:
            async for doc in self._scan_directory(base_path, since):
                yield doc

    async def fetch_changed(self, changed_paths: list[Path]) -> AsyncIterator[RawDocument]:
        for file_path in changed_paths:
            if not file_path.is_file():
                continue
            if not self._should_include(file_path):
                continue
            doc = self._file_to_document(file_path)
            if doc:
                yield doc

    async def health_check(self) -> bool:
        return bool(self._paths) and all(p.exists() for p in self._paths)

    def interactive_setup(self) -> dict[str, Any]:
        import typer

        typer.echo("\n  Local Folders Scanner")
        typer.echo("  ─" * 25)
        typer.echo(
            "\n  Add directories to scan for documents."
        )
        typer.echo(
            "  mneia will read text files, markdown, code, and PDFs."
        )
        typer.echo(
            "  Changes are monitored in real-time.\n"
        )

        paths: list[str] = []
        while True:
            default = "" if paths else "~/Documents"
            prompt = "  Add folder path (Enter to finish)" if paths else "  Folder path"
            p = typer.prompt(prompt, default=default)
            if not p and paths:
                break
            expanded = Path(p).expanduser().resolve()
            if expanded.exists() and expanded.is_dir():
                count = sum(1 for f in expanded.rglob("*") if f.is_file() and f.suffix in TEXT_EXTENSIONS)
                typer.echo(f"    Found ~{count} text files in {expanded}")
                paths.append(str(expanded))
            else:
                typer.echo(f"    Warning: {expanded} does not exist or is not a directory")
                add_anyway = typer.prompt("    Add anyway? (y/n)", default="n")
                if add_anyway.lower() == "y":
                    paths.append(str(expanded))

            more = typer.prompt("  Add another folder? (y/n)", default="n")
            if more.lower() != "y":
                break

        settings: dict[str, Any] = {"paths": ",".join(paths)}

        ext = typer.prompt(
            "  File extensions to include (comma-separated, or Enter for all text/code/pdf)",
            default="",
        )
        if ext:
            settings["extensions"] = ext

        exclude = typer.prompt(
            "  Directories to exclude (comma-separated, or Enter for defaults)",
            default="",
        )
        if exclude:
            settings["exclude_dirs"] = exclude

        if _is_bm25_available():
            typer.echo("\n  BM25 search is available (rank_bm25 installed).")
            typer.echo(
                "  Documents will be indexed automatically for fast keyword search."
            )
            settings["bm25_search"] = "true"
        else:
            typer.echo(
                "\n  For enhanced BM25 keyword search, install the search extra:"
            )
            typer.echo("    pip install 'mneia[search]'")

        if not paths:
            typer.echo("\n  No paths added. You can add them later in config.")

        return settings

    def get_watch_path(self, config: dict[str, Any]) -> Path | None:
        paths_str = config.get("paths", "")
        if not paths_str:
            return None
        first = paths_str.split(",")[0].strip()
        if first:
            p = Path(first).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p
        return None

    async def _scan_directory(
        self, base_path: Path, since: datetime | None,
    ) -> AsyncIterator[RawDocument]:
        for file_path in base_path.rglob("*"):
            if not file_path.is_file():
                continue
            if not self._should_include(file_path):
                continue

            if since:
                mtime = datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=timezone.utc,
                )
                if mtime <= since:
                    continue

            doc = self._file_to_document(file_path)
            if doc:
                yield doc

    def _should_include(self, file_path: Path) -> bool:
        if file_path.suffix not in self._extensions:
            return False

        if file_path.stat().st_size > self._max_file_size:
            return False

        parts = file_path.parts
        for part in parts:
            if part in self._exclude_dirs:
                return False
            if not self._include_hidden and part.startswith(".") and part != ".":
                return False

        for pattern in self._exclude_patterns:
            if re.search(pattern, str(file_path)):
                return False

        return True

    def _file_to_document(self, file_path: Path) -> RawDocument | None:
        try:
            content = self._read_file(file_path)
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return None

        if not content or not content.strip():
            return None

        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        parent = None
        for base in self._paths:
            try:
                file_path.relative_to(base)
                parent = base
                break
            except ValueError:
                continue

        if parent:
            relative = file_path.relative_to(parent)
            folder_label = parent.name
        else:
            relative = file_path
            folder_label = ""

        source_id = hashlib.md5(str(file_path).encode()).hexdigest()
        title = file_path.stem.replace("_", " ").replace("-", " ")

        frontmatter: dict[str, Any] = {}
        body = content
        if file_path.suffix in (".md", ".markdown"):
            frontmatter, body = _split_frontmatter(content)
            if "title" in frontmatter:
                title = frontmatter["title"]
            else:
                heading = _extract_heading(body or content)
                if heading:
                    title = heading

        content_type = _classify_content_type(file_path.suffix)

        metadata: dict[str, Any] = {
            "file_path": str(file_path),
            "relative_path": str(relative),
            "folder": folder_label,
            "extension": file_path.suffix,
            "size_bytes": stat.st_size,
        }
        if frontmatter:
            metadata["frontmatter"] = frontmatter

        return RawDocument(
            source="local-folders",
            source_id=source_id,
            content=body if body else content,
            content_type=content_type,
            title=title,
            timestamp=mtime,
            metadata=metadata,
        )

    def _read_file(self, file_path: Path) -> str:
        if file_path.suffix == ".pdf":
            return self._read_pdf(file_path)
        return file_path.read_text(encoding="utf-8", errors="replace")

    def _read_pdf(self, file_path: Path) -> str:
        try:
            import subprocess as sp
            result = sp.run(
                ["pdftotext", "-layout", str(file_path), "-"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except FileNotFoundError:
            pass
        except Exception:
            logger.debug(f"pdftotext failed for {file_path}")

        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(file_path))
            pages = []
            for page in reader.pages[:50]:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except ImportError:
            pass
        except Exception:
            logger.debug(f"PyPDF2 failed for {file_path}")

        return ""

    def build_bm25_index(self, documents: list[tuple[str, str]]) -> None:
        if not self._bm25_enabled or not _is_bm25_available():
            return
        from rank_bm25 import BM25Okapi
        self._bm25_docs = [doc_id for doc_id, _ in documents]
        tokenized = [text.lower().split() for _, text in documents]
        if tokenized:
            self._bm25_index = BM25Okapi(tokenized)
            logger.debug(f"BM25 index built with {len(tokenized)} documents")

    def bm25_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not self._bm25_index or not self._bm25_docs:
            return []
        tokens = query.lower().split()
        scores = self._bm25_index.get_scores(tokens)
        ranked = sorted(
            zip(self._bm25_docs, scores), key=lambda x: x[1], reverse=True,
        )
        return [(doc_id, score) for doc_id, score in ranked[:top_k] if score > 0]


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end < 0:
        return {}, content
    fm_text = content[3:end].strip()
    body = content[end + 3:].strip()
    fm: dict[str, Any] = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm, body


def _extract_heading(content: str) -> str | None:
    match = re.match(r"^#\s+(.+)$", content.strip(), re.MULTILINE)
    return match.group(1).strip() if match else None


def _classify_content_type(ext: str) -> str:
    if ext in (".md", ".markdown", ".rst", ".org"):
        return "note"
    if ext in (".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".c", ".cpp", ".h", ".hpp", ".swift", ".kt"):
        return "code"
    if ext in (".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg", ".conf", ".env", ".properties"):
        return "config"
    if ext == ".pdf":
        return "pdf"
    if ext in (".csv", ".tsv"):
        return "data"
    if ext in (".html", ".htm", ".css"):
        return "web"
    if ext in (".sh", ".bash", ".zsh"):
        return "script"
    if ext in (".sql",):
        return "query"
    if ext in (".tex", ".bib"):
        return "academic"
    return "document"
