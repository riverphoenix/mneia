from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mneia.agents.autonomous import AutonomousAgent
from mneia.agents.reasoning import ActionType, ReasoningAction, ReasoningPlan
from mneia.config import MneiaConfig
from mneia.core.agent import AgentState


def _make_agent() -> AutonomousAgent:
    config = MneiaConfig()
    store = MagicMock()
    store.store_document = AsyncMock(return_value="doc-1")
    graph = MagicMock()
    graph._graph = MagicMock()
    graph._graph.nodes = MagicMock()
    graph.add_relationship = MagicMock()
    graph.update_node_properties = MagicMock()

    agent = AutonomousAgent(
        name="autonomous",
        config=config,
        store=store,
        graph=graph,
    )
    agent._llm = MagicMock()
    agent._llm.generate = AsyncMock(return_value="A brief description of the entity.")
    agent._llm.close = AsyncMock()
    return agent


async def test_execute_enrich():
    agent = _make_agent()
    agent._graph._graph.nodes.get.return_value = {"properties": {}}

    await agent._execute_enrich("person:alice", "Sparse entity")

    agent._graph.update_node_properties.assert_called_once()
    call_args = agent._graph.update_node_properties.call_args
    assert call_args[0][0] == "person:alice"
    assert "description" in call_args[0][1]
    assert call_args[0][1]["enriched_by"] == "autonomous"


async def test_execute_enrich_short_response():
    agent = _make_agent()
    agent._llm.generate = AsyncMock(return_value="Too short")

    await agent._execute_enrich("person:bob", "test")

    agent._graph.update_node_properties.assert_not_called()


async def test_execute_connect():
    agent = _make_agent()
    agent._graph._graph.__contains__ = MagicMock(return_value=True)

    await agent._execute_connect(
        "topic:ai",
        {"source_id": "topic:ai", "target_id": "topic:ml", "relation": "related_to"},
    )

    agent._graph.add_relationship.assert_called_once()
    edge = agent._graph.add_relationship.call_args[0][0]
    assert edge.source_id == "topic:ai"
    assert edge.target_id == "topic:ml"


async def test_execute_connect_missing_source():
    agent = _make_agent()

    await agent._execute_connect("x", {"target_id": "y"})

    agent._graph.add_relationship.assert_not_called()


async def test_execute_insight():
    agent = _make_agent()
    agent._llm.generate = AsyncMock(
        return_value="This is a generated insight about the topic that is long enough."
    )

    await agent._execute_insight("AI trends", "Recent patterns in AI")

    agent._store.store_document.assert_called_once()
    doc = agent._store.store_document.call_args[0][0]
    assert doc.source == "autonomous-insight"
    assert doc.content_type == "insight"
    assert "AI trends" in doc.title


async def test_execute_insight_short_response():
    agent = _make_agent()
    agent._llm.generate = AsyncMock(return_value="Short")

    await agent._execute_insight("topic", "desc")

    agent._store.store_document.assert_not_called()


async def test_cycle_no_actions():
    agent = _make_agent()

    with patch(
        "mneia.agents.reasoning.ReasoningEngine.analyze",
        new_callable=AsyncMock,
        return_value=ReasoningPlan(actions=[], reasoning="nothing to do"),
    ):
        result = await agent._cycle()

    assert result == 0


async def test_cycle_executes_actions():
    agent = _make_agent()
    agent._graph._graph.nodes.get.return_value = {"properties": {}}

    plan = ReasoningPlan(
        actions=[
            ReasoningAction(
                action_type=ActionType.ENRICH,
                target="person:test",
                description="Enrich test",
                confidence=0.9,
            ),
        ],
        reasoning="found sparse entity",
    )

    with patch(
        "mneia.agents.reasoning.ReasoningEngine.analyze",
        new_callable=AsyncMock,
        return_value=plan,
    ):
        result = await agent._cycle()

    assert result == 1
    agent._graph.update_node_properties.assert_called_once()


async def test_stop():
    agent = _make_agent()
    assert not agent._stop_event.is_set()
    await agent.stop()
    assert agent._stop_event.is_set()


def test_initial_state():
    agent = _make_agent()
    assert agent.state == AgentState.IDLE
    assert agent._interval == 30 * 60
    assert agent._max_actions == 5
