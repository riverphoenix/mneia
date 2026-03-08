from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.core.connector import RawDocument
from mneia.core.llm import LLMClient
from mneia.memory.graph import GraphEdge, KnowledgeGraph
from mneia.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class AutonomousAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        config: MneiaConfig,
        store: MemoryStore,
        graph: KnowledgeGraph,
    ) -> None:
        super().__init__(
            name=name,
            description="Autonomous intelligence — identifies gaps and surfaces insights",
        )
        self._config = config
        self._store = store
        self._graph = graph
        self._llm = LLMClient(config.llm)
        self._stop_event = asyncio.Event()
        self._interval = config.autonomous_interval_minutes * 60
        self._max_actions = config.autonomous_max_actions
        self._actions_executed = 0

    async def run(self, **kwargs: Any) -> AgentResult:
        self._state = AgentState.RUNNING
        logger.info(
            f"{self.name}: started (interval={self._interval}s, "
            f"max_actions={self._max_actions})"
        )

        while not self._stop_event.is_set():
            try:
                executed = await self._cycle()
                self._actions_executed += executed
            except Exception:
                logger.exception(f"{self.name}: cycle failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval,
                )
            except asyncio.TimeoutError:
                pass

        self._state = AgentState.STOPPED
        await self._llm.close()
        return AgentResult(
            agent_name=self.name,
            metadata={"actions_executed": self._actions_executed},
        )

    async def stop(self) -> None:
        self._stop_event.set()

    async def _cycle(self) -> int:
        from mneia.agents.reasoning import ActionType, ReasoningEngine

        engine = ReasoningEngine(
            llm=self._llm,
            graph=self._graph,
            store=self._store,
            confidence_threshold=0.6,
        )

        plan = await engine.analyze(max_actions=self._max_actions)
        if not plan.actions:
            logger.debug(f"{self.name}: no actions proposed")
            return 0

        logger.info(
            f"{self.name}: executing {len(plan.actions)} actions "
            f"(reasoning: {plan.reasoning[:100]})"
        )

        executed = 0
        for action in plan.actions:
            try:
                if action.action_type == ActionType.ENRICH:
                    await self._execute_enrich(action.target, action.description)
                elif action.action_type == ActionType.CONNECT:
                    await self._execute_connect(action.target, action.params)
                elif action.action_type == ActionType.INSIGHT:
                    await self._execute_insight(action.target, action.description)
                executed += 1
            except Exception:
                logger.exception(
                    f"{self.name}: action failed: {action.action_type.value} "
                    f"on {action.target}"
                )
        return executed

    async def _execute_enrich(self, target: str, description: str) -> None:
        entity_name = target.split(":")[-1].replace("-", " ")
        prompt = (
            f"Provide a brief, factual description (2-3 sentences) "
            f"about: {entity_name}\n"
            f"Context: {description}"
        )
        result = await self._llm.generate(prompt)
        if result and len(result) > 20:
            node_data = self._graph._graph.nodes.get(target, {})
            props = dict(node_data.get("properties", {}))
            props["description"] = result[:500]
            props["enriched_by"] = "autonomous"
            self._graph.update_node_properties(target, props)
            logger.info(f"{self.name}: enriched {target}")

    async def _execute_connect(
        self, target: str, params: dict[str, str],
    ) -> None:
        source_id = params.get("source_id", "")
        target_id = params.get("target_id", target)
        relation = params.get("relation", "related_to")

        if not source_id or not target_id:
            logger.warning(f"{self.name}: connect action missing IDs")
            return

        if source_id not in self._graph._graph:
            logger.warning(f"{self.name}: source node not found: {source_id}")
            return
        if target_id not in self._graph._graph:
            logger.warning(f"{self.name}: target node not found: {target_id}")
            return

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=0.5,
            evidence="Proposed by autonomous agent",
        )
        self._graph.add_relationship(edge)
        logger.info(f"{self.name}: connected {source_id} -> {target_id} ({relation})")

    async def _execute_insight(self, topic: str, description: str) -> None:
        prompt = (
            f"Generate a brief insight document about: {topic}\n"
            f"Context: {description}\n\n"
            "Write 3-5 sentences summarizing the key insight and why it matters."
        )
        content = await self._llm.generate(prompt)
        if not content or len(content) < 30:
            return

        doc = RawDocument(
            source="autonomous-insight",
            source_id=f"insight-{topic[:50].replace(' ', '-').lower()}",
            content=content,
            content_type="insight",
            title=f"Insight: {topic}",
            timestamp=datetime.now(timezone.utc),
            metadata={
                "generated_by": "autonomous-agent",
                "description": description[:200],
            },
        )
        await self._store.store_document(doc)
        logger.info(f"{self.name}: stored insight on '{topic}'")
