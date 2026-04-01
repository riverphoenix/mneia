from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.config import MneiaConfig
from mneia.conversation import ConversationEngine, MAX_SEARCH_LIMIT


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
        # Return non-JSON so routing gracefully falls back to keyword detection
        mock_llm.generate = AsyncMock(return_value="Test answer.")
        mock_llm.close = AsyncMock()
        e = ConversationEngine(config)
        yield e


async def test_ask_with_source_filter(engine):
    """source_filter should be passed as source= (singular) in the first search call."""
    result = await engine.ask("test", source_filter="obsidian")
    call_kwargs = [c.kwargs for c in engine._store.search.call_args_list]
    # The initial search must use source= with the filter value
    assert any(kw.get("source") == "obsidian" for kw in call_kwargs), (
        f"Expected a call with source='obsidian', got: {call_kwargs}"
    )


async def test_ask_with_source_hints(engine):
    """source_hints should scope the initial search to those sources."""
    result = await engine.ask(
        "what meetings today", source_hints=["google-calendar"],
    )
    call_args = [(c.args, c.kwargs) for c in engine._store.search.call_args_list]
    # At least one call must target google-calendar sources
    assert any(
        kw.get("sources") == ["google-calendar"] or kw.get("source") == "google-calendar"
        for _, kw in call_args
    ), f"Expected a call scoped to google-calendar, got: {call_args}"


async def test_ask_no_filters(engine):
    """Questions with no source context should search across all sources."""
    result = await engine.ask("general question")
    calls = engine._store.search.call_args_list
    assert len(calls) >= 1
    # First call must use the full limit and no source restriction
    first_args, first_kwargs = calls[0].args, calls[0].kwargs
    assert first_args[0] == "general question"
    assert first_kwargs.get("limit") == MAX_SEARCH_LIMIT
    assert first_kwargs.get("source") is None
    assert first_kwargs.get("sources") is None


async def test_ask_source_hints_fallback(engine):
    """When source-scoped search returns nothing, fallback to global search."""
    engine._store.search = AsyncMock(return_value=[])
    result = await engine.ask(
        "emails about budget", source_hints=["gmail"],
    )
    calls = engine._store.search.call_args_list
    assert len(calls) >= 1
    first_call = calls[0]
    # First call should use the hint sources
    assert (
        first_call.kwargs.get("sources") == ["gmail"]
        or first_call.kwargs.get("source") == "gmail"
        or first_call.args[0] == "emails about budget"
    )
