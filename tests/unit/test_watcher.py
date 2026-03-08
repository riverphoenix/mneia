from __future__ import annotations

from pathlib import Path

from mneia.core.watcher import FileWatcher


def test_file_watcher_init():
    watcher = FileWatcher(
        watch_path=Path("/tmp/test"),
        extensions={".md", ".txt"},
        debounce_ms=1000,
    )
    assert watcher._watch_path == Path("/tmp/test")
    assert watcher._extensions == {".md", ".txt"}
    assert watcher._debounce_ms == 1000


def test_file_watcher_default_extensions():
    watcher = FileWatcher(watch_path=Path("/tmp"))
    assert ".md" in watcher._extensions


def test_should_include_matching_extension(tmp_path):
    watcher = FileWatcher(
        watch_path=tmp_path,
        extensions={".md"},
    )
    test_file = tmp_path / "note.md"
    test_file.touch()
    assert watcher._should_include(test_file) is True


def test_should_exclude_wrong_extension(tmp_path):
    watcher = FileWatcher(
        watch_path=tmp_path,
        extensions={".md"},
    )
    test_file = tmp_path / "image.png"
    test_file.touch()
    assert watcher._should_include(test_file) is False


def test_should_exclude_hidden_directory(tmp_path):
    watcher = FileWatcher(
        watch_path=tmp_path,
        extensions={".md"},
        exclude_hidden=True,
    )
    hidden_dir = tmp_path / ".obsidian"
    hidden_dir.mkdir()
    test_file = hidden_dir / "config.md"
    test_file.touch()
    assert watcher._should_include(test_file) is False


def test_should_include_hidden_when_disabled(tmp_path):
    watcher = FileWatcher(
        watch_path=tmp_path,
        extensions={".md"},
        exclude_hidden=False,
    )
    hidden_dir = tmp_path / ".obsidian"
    hidden_dir.mkdir()
    test_file = hidden_dir / "config.md"
    test_file.touch()
    assert watcher._should_include(test_file) is True


def test_should_include_nested_file(tmp_path):
    watcher = FileWatcher(
        watch_path=tmp_path,
        extensions={".md"},
    )
    sub = tmp_path / "projects" / "mneia"
    sub.mkdir(parents=True)
    test_file = sub / "readme.md"
    test_file.touch()
    assert watcher._should_include(test_file) is True


def test_should_exclude_nested_hidden(tmp_path):
    watcher = FileWatcher(
        watch_path=tmp_path,
        extensions={".md"},
    )
    sub = tmp_path / "projects" / ".git"
    sub.mkdir(parents=True)
    test_file = sub / "config.md"
    test_file.touch()
    assert watcher._should_include(test_file) is False


def test_multiple_extensions(tmp_path):
    watcher = FileWatcher(
        watch_path=tmp_path,
        extensions={".md", ".txt", ".org"},
    )
    for ext in [".md", ".txt", ".org", ".py"]:
        f = tmp_path / f"test{ext}"
        f.touch()

    assert watcher._should_include(tmp_path / "test.md") is True
    assert watcher._should_include(tmp_path / "test.txt") is True
    assert watcher._should_include(tmp_path / "test.org") is True
    assert watcher._should_include(tmp_path / "test.py") is False
