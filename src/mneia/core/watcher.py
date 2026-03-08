from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watches a directory for file changes using watchfiles with debouncing."""

    def __init__(
        self,
        watch_path: Path,
        extensions: set[str] | None = None,
        debounce_ms: int = 500,
        exclude_hidden: bool = True,
    ) -> None:
        self._watch_path = watch_path
        self._extensions = extensions or {".md"}
        self._debounce_ms = debounce_ms
        self._exclude_hidden = exclude_hidden

    def _should_include(self, path: Path) -> bool:
        if self._extensions and path.suffix not in self._extensions:
            return False
        if self._exclude_hidden:
            for part in path.relative_to(self._watch_path).parts:
                if part.startswith("."):
                    return False
        return True

    async def watch(self) -> AsyncIterator[list[Path]]:
        """Yield batches of changed file paths (debounced)."""
        try:
            from watchfiles import Change, awatch
        except ImportError:
            logger.warning(
                "watchfiles not installed — falling back to poll mode"
            )
            return

        async for changes in awatch(
            self._watch_path,
            debounce=self._debounce_ms,
            step=100,
            rust_timeout=5000,
        ):
            changed_paths: list[Path] = []
            for change_type, path_str in changes:
                if change_type == Change.deleted:
                    continue
                path = Path(path_str)
                if path.is_file() and self._should_include(path):
                    changed_paths.append(path)

            if changed_paths:
                logger.debug(
                    f"Detected {len(changed_paths)} file change(s) "
                    f"in {self._watch_path}"
                )
                yield changed_paths
