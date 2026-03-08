from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mneia.config import MneiaConfig
from mneia.memory.store import MemoryStore


@pytest.fixture
def tmp_db(tmp_path: Path) -> MemoryStore:
    db_path = tmp_path / "test.db"
    return MemoryStore(db_path=db_path)


@pytest.fixture
def config() -> MneiaConfig:
    return MneiaConfig()


@pytest.fixture
def obsidian_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "test-vault"
    vault.mkdir()

    (vault / "note1.md").write_text(
        "---\ntitle: Meeting Notes\n---\n\nDiscussed project Alpha with John Smith.\nDecided to proceed with the new design.",
        encoding="utf-8",
    )

    (vault / "note2.md").write_text(
        "# Weekly Review\n\nTasks completed:\n- Finished API integration\n- Reviewed PR from Sarah\n\n#weekly #review",
        encoding="utf-8",
    )

    subfolder = vault / "projects"
    subfolder.mkdir()
    (subfolder / "alpha.md").write_text(
        "---\ntitle: Project Alpha\ntags: project\n---\n\nProject Alpha is our main initiative.\nLead: [[John Smith]]\nStatus: In Progress",
        encoding="utf-8",
    )

    hidden = vault / ".obsidian"
    hidden.mkdir()
    (hidden / "config.json").write_text("{}", encoding="utf-8")

    return vault
