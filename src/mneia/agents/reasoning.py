from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum

from mneia.core.llm import LLMClient
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    ENRICH = "enrich"
    CONNECT = "connect"
    INSIGHT = "insight"


@dataclass
class ReasoningAction:
    action_type: ActionType
    target: str
    description: str
    confidence: float = 0.5
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class ReasoningPlan:
    actions: list[ReasoningAction] = field(default_factory=list)
    reasoning: str = ""


class ReasoningEngine:
    def __init__(
        self,
        llm: LLMClient,
        graph: KnowledgeGraph,
        store: MemoryStore,
        confidence_threshold: float = 0.6,
    ) -> None:
        self._llm = llm
        self._graph = graph
        self._store = store
        self._confidence_threshold = confidence_threshold

    async def analyze(self, max_actions: int = 5) -> ReasoningPlan:
        context = self._build_context()
        prompt = self._build_prompt(context, max_actions)

        try:
            response = await self._llm.generate(prompt)
            plan = self._parse_response(response)
            plan.actions = [
                a
                for a in plan.actions
                if a.confidence >= self._confidence_threshold
            ][:max_actions]
            return plan
        except Exception:
            logger.exception("Reasoning analysis failed")
            return ReasoningPlan(reasoning="Analysis failed due to LLM error")

    def _build_context(self) -> dict[str, object]:
        graph_stats = self._graph.get_stats()

        sparse_entities = []
        for nid, data in self._graph._graph.nodes(data=True):
            props = data.get("properties", {})
            desc = props.get("description", "")
            degree = self._graph._graph.degree(nid)
            if (not desc or len(desc) < 30) and degree < 2:
                sparse_entities.append({
                    "id": nid,
                    "name": data.get("name", ""),
                    "type": data.get("entity_type", ""),
                    "connections": degree,
                })
            if len(sparse_entities) >= 10:
                break

        isolated_nodes = [
            {
                "id": nid,
                "name": data.get("name", ""),
                "type": data.get("entity_type", ""),
            }
            for nid, data in self._graph._graph.nodes(data=True)
            if self._graph._graph.degree(nid) == 0
        ][:10]

        return {
            "graph_stats": graph_stats,
            "sparse_entities": sparse_entities,
            "isolated_nodes": isolated_nodes,
        }

    def _build_prompt(
        self, context: dict[str, object], max_actions: int,
    ) -> str:
        return (
            "You are a knowledge graph analyst. Analyze the following "
            "knowledge state and propose actions to improve it.\n\n"
            f"Graph statistics: {json.dumps(context['graph_stats'])}\n\n"
            f"Sparse entities (few connections, lacking descriptions):\n"
            f"{json.dumps(context['sparse_entities'], indent=2)}\n\n"
            f"Isolated nodes (no connections):\n"
            f"{json.dumps(context['isolated_nodes'], indent=2)}\n\n"
            f"Propose up to {max_actions} actions. For each action, "
            "respond with a JSON array of objects with these fields:\n"
            '- "action_type": one of "enrich", "connect", "insight"\n'
            '- "target": entity ID or topic\n'
            '- "description": what to do and why\n'
            '- "confidence": 0.0-1.0 how confident this is useful\n'
            '- "params": optional dict with extra parameters\n\n'
            "Action types:\n"
            '- "enrich": look up more info about a sparse entity\n'
            '- "connect": propose a relationship between entities\n'
            '- "insight": generate a synthetic insight document\n\n'
            "Respond with ONLY a JSON object like:\n"
            '{"reasoning": "...", "actions": [...]}'
        )

    def _parse_response(self, response: str) -> ReasoningPlan:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Could not parse reasoning response as JSON")
            return ReasoningPlan(reasoning=response)

        actions = []
        for item in data.get("actions", []):
            try:
                action = ReasoningAction(
                    action_type=ActionType(item["action_type"]),
                    target=item["target"],
                    description=item.get("description", ""),
                    confidence=float(item.get("confidence", 0.5)),
                    params=item.get("params", {}),
                )
                actions.append(action)
            except (KeyError, ValueError):
                logger.debug(f"Skipping malformed action: {item}")

        return ReasoningPlan(
            actions=actions,
            reasoning=data.get("reasoning", ""),
        )
