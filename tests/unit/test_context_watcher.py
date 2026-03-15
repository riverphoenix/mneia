from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from mneia.context.watcher import ContextWatcher


def _mock_config(auto_gen=True, min_changes=5, interval=30):
    config = MagicMock()
    config.auto_generate_context = auto_gen
    config.context_regenerate_interval_minutes = interval
    config.context_min_changes_for_regen = min_changes
    config.llm = MagicMock()
    return config


async def test_should_regenerate_no_auto_gen():
    config = _mock_config(auto_gen=False)
    with patch("mneia.context.watcher.MemoryStore"):
        watcher = ContextWatcher(config)
    result = await watcher._should_regenerate()
    assert result is False


async def test_should_regenerate_no_docs():
    config = _mock_config()
    with patch("mneia.context.watcher.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.get_stats = AsyncMock(
            return_value={"total_documents": 0},
        )
        mock_store_cls.return_value = mock_store
        watcher = ContextWatcher(config)

    result = await watcher._should_regenerate()
    assert result is False


async def test_should_regenerate_first_time():
    config = _mock_config()
    with patch("mneia.context.watcher.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.get_stats = AsyncMock(
            return_value={"total_documents": 10},
        )
        mock_store_cls.return_value = mock_store
        watcher = ContextWatcher(config)

    result = await watcher._should_regenerate()
    assert result is True


async def test_should_regenerate_enough_new_docs():
    config = _mock_config(min_changes=2)
    with patch("mneia.context.watcher.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.get_stats = AsyncMock(
            return_value={"total_documents": 10},
        )
        doc1 = MagicMock()
        doc1.timestamp = "2026-03-14T12:00:00+00:00"
        doc2 = MagicMock()
        doc2.timestamp = "2026-03-14T13:00:00+00:00"
        mock_store.get_recent = AsyncMock(return_value=[doc1, doc2])
        mock_store_cls.return_value = mock_store
        watcher = ContextWatcher(config)

    watcher._last_gen_time = datetime(
        2020, 1, 1, tzinfo=timezone.utc,
    )
    result = await watcher._should_regenerate()
    assert result is True


async def test_should_regenerate_not_enough_new_docs():
    config = _mock_config(min_changes=5)
    with patch("mneia.context.watcher.MemoryStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.get_stats = AsyncMock(
            return_value={"total_documents": 10},
        )
        doc1 = MagicMock()
        doc1.timestamp = "2019-01-01T00:00:00+00:00"
        mock_store.get_recent = AsyncMock(return_value=[doc1])
        mock_store_cls.return_value = mock_store
        watcher = ContextWatcher(config)

    watcher._last_gen_time = datetime(
        2020, 1, 1, tzinfo=timezone.utc,
    )
    result = await watcher._should_regenerate()
    assert result is False


async def test_regenerate_calls_generate():
    config = _mock_config()
    with patch("mneia.context.watcher.MemoryStore"):
        watcher = ContextWatcher(config)

    with patch(
        "mneia.pipeline.generate.generate_context_files",
        new_callable=AsyncMock,
        return_value=["people.md", "topics.md"],
    ) as mock_gen, \
         patch("mneia.memory.graph.KnowledgeGraph"), \
         patch("mneia.core.llm.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.close = AsyncMock()
        mock_llm_cls.return_value = mock_llm

        await watcher._regenerate()

    mock_gen.assert_called_once()
    assert watcher._last_gen_time is not None


async def test_stop():
    config = _mock_config()
    with patch("mneia.context.watcher.MemoryStore"):
        watcher = ContextWatcher(config)
    watcher._running = True
    await watcher.stop()
    assert watcher._running is False
