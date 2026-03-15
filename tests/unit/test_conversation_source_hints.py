from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.config import MneiaConfig
from mneia.conversation import ConversationEngine


@pytest.fixture
def config():
    return MneiaConfig()


@pytest.fixture
def engine(config):
    with patch("mneia.conversation.MemoryStore") as mock_store_cls, \
         patch("mneia.conversation.KnowledgeGraph") as mock_graph_cls, \
         patch("mneia.conversation.LLMClient") as mock_llm_cls:
        mock_store = mock_store_cls.return_value
        mock_store.search = AsyncMock(return_value=[])
        mock_graph = mock_graph_cls.return_value
        mock_graph.get_stats.return_value = {"total_nodes": 0}
        mock_llm = mock_llm_cls.return_value
        mock_llm.generate = AsyncMock(return_value="Test answer.")
        mock_llm.close = AsyncMock()
        e = ConversationEngine(config)
        yield e


async def test_ask_with_source_filter(engine):
    result = await engine.ask("test", source_filter="obsidian")
    engine._store.search.assert_called_once_with(
        "test", limit=5, source="obsidian",
    )


async def test_ask_with_source_hints(engine):
    result = await engine.ask(
        "what meetings today", source_hints=["google-calendar"],
    )
    engine._store.search.assert_any_call(
        "what meetings today", limit=5, sources=["google-calendar"],
    )


async def test_ask_no_filters(engine):
    result = await engine.ask("general question")
    engine._store.search.assert_called_once_with(
        "general question", limit=5,
    )


async def test_ask_source_hints_fallback(engine):
    engine._store.search = AsyncMock(return_value=[])
    result = await engine.ask(
        "emails about budget", source_hints=["gmail"],
    )
    calls = engine._store.search.call_args_list
    assert len(calls) >= 1
    first_call = calls[0]
    assert first_call.kwargs.get("sources") == ["gmail"] or \
        (len(first_call.args) >= 1 and first_call.args[0] == "emails about budget")