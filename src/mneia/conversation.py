from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.llm import LLMClient
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore, StoredDocument

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10
MAX_CONTEXT_CHARS = 6000


@dataclass
class Citation:
    title: str
    source: str
    snippet: str


@dataclass
class ConversationTurn:
    role: str
    content: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class ConversationResult:
    answer: str
    citations: list[Citation]
    suggested_followups: list[str]


class ConversationEngine:
    def __init__(self, config: MneiaConfig) -> None:
        self.config = config
        self._store = MemoryStore()
        self._graph = KnowledgeGraph()
        self._llm = LLMClient(config.llm)
        self._history: list[ConversationTurn] = []

    async def ask(self, question: str, source_filter: str | None = None) -> ConversationResult:
        doc_results = await self._store.search(question, limit=5)

        graph_context = self._get_graph_context(question)

        context_block = self._build_context(doc_results, graph_context)

        citations = [
            Citation(
                title=doc.title,
                source=doc.source,
                snippet=doc.content[:200].replace("\n", " "),
            )
            for doc in doc_results
        ]

        history_block = self._format_history()

        system_prompt = (
            "You are mneia, a personal knowledge assistant. "
            "You help the user understand their own knowledge, notes, meetings, and work.\n\n"
            "RULES:\n"
            "- Answer based on the provided context from the user's documents and knowledge graph.\n"
            "- Be concise, direct, and helpful.\n"
            "- If the context doesn't contain relevant information, say so honestly.\n"
            "- Reference specific documents by title when citing information.\n"
            "- When listing people, projects, or topics, include what you know about each.\n"
            "- At the end of your response, suggest 2-3 follow-up questions the user could ask, "
            "prefixed with 'You could also ask:'\n"
            "- If the user's question is ambiguous, ask a clarifying question instead of guessing."
        )

        prompt_parts = []
        if history_block:
            prompt_parts.append(f"Previous conversation:\n{history_block}\n")
        prompt_parts.append(f"Context from knowledge base:\n\n{context_block}")
        prompt_parts.append(f"\nQuestion: {question}")

        prompt = "\n".join(prompt_parts)

        response = await self._llm.generate(prompt, system=system_prompt)

        followups = self._extract_followups(response)
        clean_answer = self._strip_followups(response)

        self._history.append(ConversationTurn(role="user", content=question))
        self._history.append(ConversationTurn(
            role="assistant", content=clean_answer, citations=citations,
        ))

        if len(self._history) > MAX_HISTORY_TURNS * 2:
            self._history = self._history[-(MAX_HISTORY_TURNS * 2):]

        return ConversationResult(
            answer=clean_answer,
            citations=citations,
            suggested_followups=followups,
        )

    def clear_history(self) -> None:
        self._history.clear()

    async def close(self) -> None:
        await self._llm.close()

    def _get_graph_context(self, question: str) -> str:
        parts: list[str] = []

        stats = self._graph.get_stats()
        if stats["total_nodes"] == 0:
            return ""

        tokens = question.lower().split()
        matched_nodes: list[dict[str, Any]] = []

        for nid, data in self._graph._graph.nodes(data=True):
            name = data.get("name", "").lower()
            if any(token in name for token in tokens if len(token) > 2):
                matched_nodes.append({"id": nid, **data})

        if not matched_nodes:
            return ""

        for node in matched_nodes[:5]:
            node_id = node["id"]
            name = node.get("name", node_id)
            etype = node.get("entity_type", "unknown")
            desc = node.get("properties", {}).get("description", "")

            parts.append(f"[Entity: {name} ({etype})]")
            if desc:
                parts.append(f"  Description: {desc}")

            neighbors = self._graph.get_neighbors(node_id, depth=1)
            for edge in neighbors.get("edges", [])[:10]:
                other_id = edge["target"] if edge["source"] == node_id else edge["source"]
                other_name = other_id.split(":", 1)[-1].replace("-", " ").title()
                parts.append(f"  → {edge['relation']} → {other_name}")

        return "\n".join(parts)

    def _build_context(
        self,
        docs: list[StoredDocument],
        graph_context: str,
    ) -> str:
        parts: list[str] = []
        total_chars = 0

        if graph_context:
            parts.append("--- Knowledge Graph ---")
            parts.append(graph_context)
            parts.append("")
            total_chars += len(graph_context)

        if docs:
            parts.append("--- Documents ---")
            for doc in docs:
                remaining = MAX_CONTEXT_CHARS - total_chars
                if remaining <= 200:
                    break
                snippet = doc.content[:min(1500, remaining)]
                entry = f"[{doc.title} — {doc.source}]\n{snippet}"
                parts.append(entry)
                parts.append("")
                total_chars += len(entry)

        if not parts:
            return "No relevant context found in your knowledge base."

        return "\n".join(parts)

    def _format_history(self) -> str:
        if not self._history:
            return ""

        lines: list[str] = []
        for turn in self._history[-(MAX_HISTORY_TURNS * 2):]:
            prefix = "User" if turn.role == "user" else "Assistant"
            content = turn.content[:500]
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    @staticmethod
    def _extract_followups(response: str) -> list[str]:
        followups: list[str] = []
        lines = response.split("\n")
        in_followups = False

        for line in lines:
            stripped = line.strip()
            if "you could also ask" in stripped.lower() or "follow-up" in stripped.lower():
                in_followups = True
                continue
            if in_followups and stripped:
                clean = stripped.lstrip("- •*0123456789.)")
                clean = clean.strip(' "\'')
                if clean and "?" in clean:
                    followups.append(clean)

        return followups[:3]

    @staticmethod
    def _strip_followups(response: str) -> str:
        lines = response.split("\n")
        result_lines: list[str] = []
        in_followups = False

        for line in lines:
            stripped = line.strip()
            if "you could also ask" in stripped.lower():
                in_followups = True
                continue
            if in_followups:
                if stripped and not stripped.startswith(("-", "•", "*", "1", "2", "3")):
                    in_followups = False
                    result_lines.append(line)
            else:
                result_lines.append(line)

        return "\n".join(result_lines).rstrip()
