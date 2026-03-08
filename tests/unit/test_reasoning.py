from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from mneia.agents.reasoning import (
    ActionType,
    ReasoningAction,
    ReasoningEngine,
    ReasoningPlan,
)


def _make_engine(llm_response: str = "{}") -> ReasoningEngine:
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=llm_response)
    graph = MagicMock()
    graph.get_stats.return_value = {"total_nodes": 5, "total_edges": 3, "by_type": {}}
    graph._graph = MagicMock()
    graph._graph.nodes = MagicMock(return_value=[])
    graph._graph.nodes.data = MagicMock(return_value=[])
    store = MagicMock()
    return ReasoningEngine(llm=llm, graph=graph, store=store)


def test_reasoning_plan_dataclass():
    plan = ReasoningPlan(
        actions=[
            ReasoningAction(
                action_type=ActionType.ENRICH,
                target="person:alice",
                description="Enrich Alice",
                confidence=0.8,
            )
        ],
        reasoning="Test reasoning",
    )
    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == ActionType.ENRICH
    assert plan.reasoning == "Test reasoning"


def test_action_types():
    assert ActionType.ENRICH.value == "enrich"
    assert ActionType.CONNECT.value == "connect"
    assert ActionType.INSIGHT.value == "insight"


def test_parse_valid_response():
    engine = _make_engine()
    response = json.dumps({
        "reasoning": "Found sparse entities",
        "actions": [
            {
                "action_type": "enrich",
                "target": "person:bob",
                "description": "Look up Bob",
                "confidence": 0.9,
            },
            {
                "action_type": "connect",
                "target": "topic:ai",
                "description": "Connect AI to ML",
                "confidence": 0.7,
                "params": {"source_id": "topic:ai", "target_id": "topic:ml"},
            },
        ],
    })
    plan = engine._parse_response(response)
    assert len(plan.actions) == 2
    assert plan.actions[0].action_type == ActionType.ENRICH
    assert plan.actions[0].target == "person:bob"
    assert plan.actions[1].params["source_id"] == "topic:ai"
    assert plan.reasoning == "Found sparse entities"


def test_parse_code_fenced_response():
    engine = _make_engine()
    response = (
        "```json\n"
        + json.dumps({
            "reasoning": "test",
            "actions": [
                {
                    "action_type": "insight",
                    "target": "topic:test",
                    "description": "Generate insight",
                    "confidence": 0.8,
                }
            ],
        })
        + "\n```"
    )
    plan = engine._parse_response(response)
    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == ActionType.INSIGHT


def test_parse_invalid_json():
    engine = _make_engine()
    plan = engine._parse_response("not json at all")
    assert len(plan.actions) == 0
    assert "not json" in plan.reasoning


def test_parse_malformed_action_skipped():
    engine = _make_engine()
    response = json.dumps({
        "reasoning": "partial",
        "actions": [
            {"action_type": "enrich", "target": "x", "confidence": 0.9},
            {"bad": "data"},
        ],
    })
    plan = engine._parse_response(response)
    assert len(plan.actions) == 1


async def test_confidence_filtering():
    engine = _make_engine()
    engine._confidence_threshold = 0.7
    response = json.dumps({
        "reasoning": "mixed confidence",
        "actions": [
            {
                "action_type": "enrich",
                "target": "a",
                "description": "low",
                "confidence": 0.3,
            },
            {
                "action_type": "enrich",
                "target": "b",
                "description": "high",
                "confidence": 0.9,
            },
        ],
    })
    engine._llm.generate = AsyncMock(return_value=response)
    engine._build_context = MagicMock(return_value={
        "graph_stats": {},
        "sparse_entities": [],
        "isolated_nodes": [],
    })

    plan = await engine.analyze(max_actions=5)
    assert len(plan.actions) == 1
    assert plan.actions[0].target == "b"


async def test_analyze_llm_failure():
    engine = _make_engine()
    engine._llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
    engine._build_context = MagicMock(return_value={
        "graph_stats": {},
        "sparse_entities": [],
        "isolated_nodes": [],
    })
    plan = await engine.analyze()
    assert len(plan.actions) == 0
    assert "failed" in plan.reasoning.lower()


def test_build_prompt_includes_stats():
    engine = _make_engine()
    context = {
        "graph_stats": {"total_nodes": 10},
        "sparse_entities": [{"id": "x", "name": "X"}],
        "isolated_nodes": [],
    }
    prompt = engine._build_prompt(context, max_actions=3)
    assert "total_nodes" in prompt
    assert "up to 3 actions" in prompt
