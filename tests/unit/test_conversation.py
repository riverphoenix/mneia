from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.config import MneiaConfig
from mneia.conversation import ConversationEngine, ConversationResult, Citation


@pytest.fixture
def config():
    return MneiaConfig()


def test_extract_followups():
    response = """Here's the answer.

You could also ask:
- What is Alice's role?
- When did we last meet with Bob?
- What are the project deadlines?
"""
    followups = ConversationEngine._extract_followups(response)
    assert len(followups) == 3
    assert "Alice's role?" in followups[0]


def test_extract_followups_none():
    response = "This is a simple answer with no followups."
    followups = ConversationEngine._extract_followups(response)
    assert len(followups) == 0


def test_extract_followups_max_three():
    response = """Answer.

You could also ask:
- Q1?
- Q2?
- Q3?
- Q4?
- Q5?
"""
    followups = ConversationEngine._extract_followups(response)
    assert len(followups) == 3


def test_strip_followups():
    response = """Here's the main answer.

You could also ask:
- What is X?
- When is Y?
"""
    stripped = ConversationEngine._strip_followups(response)
    assert "main answer" in stripped
    assert "What is X?" not in stripped
    assert "You could also ask" not in stripped


def test_strip_followups_no_followups():
    response = "Just a simple answer."
    stripped = ConversationEngine._strip_followups(response)
    assert stripped == response


async def test_conversation_engine_ask(config, tmp_path):
    engine = ConversationEngine(config)
    engine._store = MagicMock()
    engine._store.search = AsyncMock(return_value=[])
    engine._graph = MagicMock()
    engine._graph.get_stats = MagicMock(return_value={"total_nodes": 0, "total_edges": 0})
    engine._llm = MagicMock()
    engine._llm.generate = AsyncMock(return_value="The answer is 42.\n\nYou could also ask:\n- Why 42?")
    engine._llm.close = AsyncMock()

    result = await engine.ask("What is the answer?")
    assert isinstance(result, ConversationResult)
    assert "42" in result.answer
    assert len(result.suggested_followups) == 1
    assert "42?" in result.suggested_followups[0]


async def test_conversation_history(config):
    engine = ConversationEngine(config)
    engine._store = MagicMock()
    engine._store.search = AsyncMock(return_value=[])
    engine._graph = MagicMock()
    engine._graph.get_stats = MagicMock(return_value={"total_nodes": 0, "total_edges": 0})
    engine._llm = MagicMock()
    engine._llm.generate = AsyncMock(return_value="Answer one.")
    engine._llm.close = AsyncMock()

    await engine.ask("First question")
    assert len(engine._history) == 2

    engine._llm.generate = AsyncMock(return_value="Answer two.")
    await engine.ask("Second question")
    assert len(engine._history) == 4

    engine.clear_history()
    assert len(engine._history) == 0


async def test_conversation_graph_context(config, tmp_path):
    engine = ConversationEngine(config)
    engine._store = MagicMock()
    engine._store.search = AsyncMock(return_value=[])

    from mneia.memory.graph import GraphNode, KnowledgeGraph

    engine._graph = KnowledgeGraph(db_path=tmp_path / "graph.db")
    engine._graph.add_entity(GraphNode(
        id="person:alice", entity_type="person", name="Alice",
        properties={"description": "Product Manager"},
    ))

    engine._llm = MagicMock()
    engine._llm.generate = AsyncMock(return_value="Alice is a PM.")
    engine._llm.close = AsyncMock()

    result = await engine.ask("Tell me about Alice")

    call_args = engine._llm.generate.call_args
    prompt = call_args[0][0]
    assert "Alice" in prompt
    assert "Product Manager" in prompt


async def test_conversation_context_building(config):
    engine = ConversationEngine(config)

    from mneia.memory.store import StoredDocument

    docs = [
        StoredDocument(
            id=1, source="obsidian", source_id="a",
            content="Meeting with Bob about project X.",
            content_type="note", title="Meeting Notes", timestamp="2025-01-15",
        ),
    ]

    context = engine._build_context(docs, "")
    assert "Meeting Notes" in context
    assert "Meeting with Bob" in context


def test_citation_dataclass():
    cite = Citation(title="Note", source="obsidian", snippet="Some text")
    assert cite.title == "Note"
    assert cite.source == "obsidian"


def test_conversation_result_dataclass():
    result = ConversationResult(
        answer="The answer",
        citations=[Citation(title="A", source="b", snippet="c")],
        suggested_followups=["Q1?"],
    )
    assert result.answer == "The answer"
    assert len(result.citations) == 1
    assert len(result.suggested_followups) == 1
