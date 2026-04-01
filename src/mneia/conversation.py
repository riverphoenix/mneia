from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.llm import LLMClient
from mneia.memory.embeddings import EmbeddingClient
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore, StoredDocument
from mneia.memory.vector_store import VectorStore
from mneia.pipeline.rag_fusion import reciprocal_rank_fusion
from mneia.pipeline.temporal import extract_temporal_range

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10
MAX_CONTEXT_CHARS = 80_000
MAX_DOCS_PER_SOURCE = 15
MAX_SEARCH_LIMIT = 200
MAX_REACT_ITERATIONS = 3

# Maps source name → keywords that trigger it
SOURCE_KEYWORDS: dict[str, list[str]] = {
    "google-calendar": [
        "calendar", "meeting", "meetings", "event", "events", "schedule",
        "appointment", "standup", "sync", "1:1", "one-on-one", "invite",
        "agenda", "today", "tomorrow", "next week", "this week",
    ],
    "gmail": [
        "email", "emails", "mail", "inbox", "gmail", "message", "thread",
        "sent", "received", "newsletter", "replied", "forwarded",
    ],
    "google-drive": [
        "drive", "doc", "docs", "sheet", "sheets", "slide", "slides",
        "google doc", "spreadsheet", "presentation",
    ],
    "granola": [
        "meeting notes", "transcript", "transcription", "said", "mentioned",
        "discussed", "recorded meeting", "granola",
    ],
    "obsidian": [
        "note", "notes", "obsidian", "vault", "wrote", "journal",
        "daily note", "idea", "brain dump",
    ],
    "apple-notes": [
        "apple notes", "iphone note", "macos note", "quick note",
    ],
    "github": [
        "github", "repo", "repository", "commit", "pull request", "pr",
        "branch", "code", "issue", "bug", "feature", "release",
    ],
    "chrome-history": [
        "browsed", "visited", "website", "url", "chrome", "browser",
        "searched online", "looked up",
    ],
    "local-folders": [
        "file", "files", "folder", "document", "pdf", "download",
        "desktop", "local",
    ],
}


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
class RouteDecision:
    primary_sources: list[str]
    fallback_sources: list[str]
    search_queries: list[str]
    needs_clarification: bool = False
    clarifying_question: str | None = None
    clarifying_options: list[str] = field(default_factory=list)


@dataclass
class ReactEvaluation:
    has_enough: bool
    additional_queries: list[str] = field(default_factory=list)
    additional_sources: list[str] = field(default_factory=list)


@dataclass
class ConversationResult:
    answer: str
    citations: list[Citation]
    suggested_followups: list[str]
    needs_clarification: bool = False
    clarifying_question: str | None = None
    clarifying_options: list[str] = field(default_factory=list)


class ConversationEngine:
    def __init__(
        self,
        config: MneiaConfig,
        vector_store: VectorStore | None = None,
        embedding_client: EmbeddingClient | None = None,
        session_manager: Any | None = None,
    ) -> None:
        self.config = config
        self._store = MemoryStore()
        self._graph = KnowledgeGraph()
        self._llm = LLMClient(config.llm)
        self._vector_store = vector_store
        self._embedding_client = embedding_client
        self._session_manager = session_manager
        self._history: list[ConversationTurn] = []

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def ask(
        self,
        question: str,
        source_filter: str | None = None,
        source_hints: list[str] | None = None,
    ) -> ConversationResult:
        """Answer a question using the ReAct (Reason + Act) retrieval loop."""

        # ── 1. Temporal range detection ───────────────────────────────────
        time_range = extract_temporal_range(question)
        since, until = (time_range[0], time_range[1]) if time_range else (None, None)

        # ── 2. Keyword-based source detection (instant) ──────────────────
        keyword_sources = self._keyword_detect_sources(question)

        # ── 3. Determine starting sources ────────────────────────────────
        if source_filter:
            starting_sources: list[str] | None = [source_filter]
        elif source_hints:
            starting_sources = source_hints
        elif keyword_sources:
            starting_sources = keyword_sources
        else:
            starting_sources = None  # search everything

        # ── 4. LLM routing + initial search (concurrent) ─────────────────
        routing_task = asyncio.ensure_future(
            self._llm_route_query(question, starting_sources)
        )
        initial_search_task = asyncio.ensure_future(
            self._store.search(
                question, limit=MAX_SEARCH_LIMIT, sources=starting_sources,
                since=since, until=until,
            )
            if not source_filter
            else self._store.search(
                question, limit=MAX_SEARCH_LIMIT, source=source_filter,
                since=since, until=until,
            )
        )

        routing_result, initial_docs = await asyncio.gather(
            routing_task, initial_search_task, return_exceptions=True,
        )

        if isinstance(routing_result, Exception):
            logger.debug("LLM routing failed: %s", routing_result)
            routing_result = None
        if isinstance(initial_docs, Exception):
            logger.debug("Initial search failed: %s", initial_docs)
            initial_docs = []

        # ── 5. Check if clarification needed ─────────────────────────────
        if routing_result and routing_result.needs_clarification:
            return ConversationResult(
                answer=routing_result.clarifying_question or "Could you clarify your question?",
                citations=[],
                suggested_followups=routing_result.clarifying_options,
                needs_clarification=True,
                clarifying_question=routing_result.clarifying_question,
                clarifying_options=routing_result.clarifying_options,
            )

        # ── 6. ReAct gather loop — keep result lists separate for RRF ────
        result_lists: list[list[StoredDocument]] = []
        if initial_docs:
            result_lists.append(list(initial_docs))

        seen_ids: set[int] = {d.id for d in initial_docs}

        effective_sources = (
            routing_result.primary_sources if routing_result else starting_sources
        )
        extra_queries = (
            routing_result.search_queries[1:] if routing_result else []
        )

        # Iteration 0: Search with routing's sub-queries concurrently
        if extra_queries:
            sub_tasks = [
                self._store.search(
                    q, limit=100, sources=effective_sources or None,
                    since=since, until=until,
                )
                for q in extra_queries[:3]
            ]
            sub_results = await asyncio.gather(*sub_tasks, return_exceptions=True)
            for batch in sub_results:
                if isinstance(batch, list) and batch:
                    result_lists.append(batch)
                    for doc in batch:
                        seen_ids.add(doc.id)

        # Iteration 1: Fallback to global search if too few results.
        # Skip when source_filter is set — the caller explicitly scoped the search.
        all_so_far = {d.id for lst in result_lists for d in lst}
        if len(all_so_far) < 5 and effective_sources and not source_filter:
            global_docs = await self._store.search(
                question, limit=MAX_SEARCH_LIMIT, since=since, until=until,
            )
            if global_docs:
                result_lists.append(global_docs)
                for doc in global_docs:
                    seen_ids.add(doc.id)

        # Iteration 2: LLM evaluates context and decides if more needed
        flat_so_far = [d for lst in result_lists for d in lst]
        if len(flat_so_far) >= 3:
            eval_result = await self._react_evaluate(question, flat_so_far[:15])
            if eval_result and not eval_result.has_enough:
                extra_tasks = [
                    self._store.search(
                        q, limit=100,
                        sources=eval_result.additional_sources or None,
                        since=since, until=until,
                    )
                    for q in eval_result.additional_queries[:2]
                ]
                if extra_tasks:
                    extra_batches = await asyncio.gather(
                        *extra_tasks, return_exceptions=True,
                    )
                    for batch in extra_batches:
                        if isinstance(batch, list) and batch:
                            result_lists.append(batch)

        # ── 7. Vector search with HyDE (semantic similarity) ─────────────
        vector_results = await self._vector_search_hyde(question, n_results=20)
        if vector_results:
            result_lists.append(vector_results)

        # ── 8. RRF merge → source-cap → rerank ───────────────────────────
        rrf_merged = reciprocal_rank_fusion(result_lists)
        merged = self._merge_and_diversify(rrf_merged)
        doc_results = self._rerank(question, merged, top_k=30)

        # ── 9. Graph context ──────────────────────────────────────────────
        graph_context = self._get_graph_context(question)

        # ── 10. Build context block ───────────────────────────────────────
        context_block = self._build_context(doc_results, graph_context, question)

        citations = [
            Citation(
                title=doc.title,
                source=doc.source,
                snippet=doc.content[:200].replace("\n", " "),
            )
            for doc in doc_results
        ]

        # ── 10. Build and send final prompt ───────────────────────────────
        history_block = self._format_history()

        now_local = datetime.now()
        date_str = now_local.strftime("%A, %B %d, %Y")
        time_str = now_local.strftime("%H:%M")

        system_parts = [
            "You are mneia (\u03bc\u03bd\u03b5\u03af\u03b1 — Greek for 'memory'), "
            "a personal knowledge assistant that continuously learns from the user's "
            "digital life. You have access to their calendar events, emails, documents, "
            "notes, audio transcripts, and web research — all ingested from connected "
            "sources and organised into a searchable knowledge base with a knowledge graph "
            "of entities and relationships.\n\n"
            f"Current date and time: {date_str}, {time_str} (local time)\n\n"
            "RULES:\n"
            "- Answer based on the provided context from the user's documents "
            "and knowledge graph.\n"
            "- Be concise, direct, and helpful.\n"
            "- If the context doesn't contain relevant information, say so honestly.\n"
            "- Reference specific documents by title when citing information.\n"
            "- When listing people, projects, or topics, include what you know about each.\n"
            "- For time-relative questions ('tomorrow', 'next week', 'yesterday'), "
            "use the current date above to calculate the correct dates.\n"
            "- At the end of your response, suggest 2-3 follow-up questions the user could ask, "
            "prefixed with 'You could also ask:'\n"
            "- If the user's question is ambiguous, ask a clarifying question instead of guessing."
        ]

        if self._session_manager:
            personal = self._session_manager.get_personal_context()
            if personal:
                system_parts.append(f"\n\nPersonal context:\n{personal}")

        system_prompt = "\n".join(system_parts)

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

        if self._session_manager:
            self._session_manager.record_interaction("user", question)
            self._session_manager.record_interaction("assistant", clean_answer)

        if len(self._history) > MAX_HISTORY_TURNS * 2:
            self._history = self._history[-(MAX_HISTORY_TURNS * 2):]

        return ConversationResult(
            answer=clean_answer,
            citations=citations,
            suggested_followups=followups,
        )

    # ------------------------------------------------------------------ #
    # ReAct routing + evaluation                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _keyword_detect_sources(question: str) -> list[str]:
        """Fast keyword-based source detection — no LLM needed."""
        q = question.lower()
        matched: list[str] = []
        for source, keywords in SOURCE_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                matched.append(source)
        return matched

    def _get_active_sources(self) -> list[str]:
        """Return enabled connector names from config."""
        return [
            name for name, cfg in self.config.connectors.items()
            if cfg.enabled
        ]

    async def _llm_route_query(
        self,
        question: str,
        hint_sources: list[str] | None,
    ) -> RouteDecision | None:
        """Use the LLM to identify which sources to search and generate sub-queries.

        Returns None on any failure so callers can fall back gracefully.
        """
        active = self._get_active_sources()
        if not active:
            return None

        source_descriptions = {
            "google-calendar": "calendar events, meetings, schedules",
            "gmail": "emails, email threads",
            "google-drive": "Google Docs, Sheets, Slides",
            "granola": "meeting transcripts and notes",
            "obsidian": "personal knowledge notes",
            "apple-notes": "Apple Notes",
            "github": "code repositories, commits, pull requests, issues",
            "chrome-history": "browser history and visited pages",
            "local-folders": "local files and documents",
        }
        source_list = "\n".join(
            f"- {s}: {source_descriptions.get(s, s)}"
            for s in active
        )

        hint_str = f"\nKeyword pre-filter suggests: {hint_sources}" if hint_sources else ""

        routing_prompt = (
            f"Analyze this question and return JSON routing instructions.\n"
            f"Question: {question}{hint_str}\n\n"
            f"Available sources:\n{source_list}\n\n"
            f"Return ONLY valid JSON with these fields:\n"
            f'{{"primary_sources": ["source1"], '
            f'"fallback_sources": [], '
            f'"search_queries": ["main query", "alt query"], '
            f'"needs_clarification": false, '
            f'"clarifying_question": null, '
            f'"clarifying_options": []}}\n\n'
            f"Rules:\n"
            f"- primary_sources: 1-3 most relevant sources (empty list = search all)\n"
            f"- search_queries: 2-4 search terms covering different angles of the question\n"
            f"- needs_clarification: true only if question is genuinely ambiguous between "
            f"very different intents\n"
            f"- JSON only, no explanation"
        )

        try:
            raw = await asyncio.wait_for(
                self._llm.generate(
                    routing_prompt,
                    system="You are a query router. Respond with valid JSON only.",
                ),
                timeout=10.0,
            )
            # Extract JSON from response
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            return RouteDecision(
                primary_sources=data.get("primary_sources") or [],
                fallback_sources=data.get("fallback_sources") or [],
                search_queries=data.get("search_queries") or [question],
                needs_clarification=bool(data.get("needs_clarification")),
                clarifying_question=data.get("clarifying_question"),
                clarifying_options=data.get("clarifying_options") or [],
            )
        except Exception as exc:
            logger.debug("LLM routing failed (%s), using keyword detection", exc)
            return None

    async def _react_evaluate(
        self,
        question: str,
        docs_so_far: list[StoredDocument],
    ) -> ReactEvaluation | None:
        """Ask the LLM if the gathered context is sufficient, or what else to fetch."""
        if not docs_so_far:
            return ReactEvaluation(has_enough=False, additional_queries=[question])

        sources_present = list({d.source for d in docs_so_far})
        brief = "\n".join(
            f"- [{d.source}] {d.title}: {d.content[:80].replace(chr(10), ' ')}"
            for d in docs_so_far[:8]
        )

        eval_prompt = (
            f"Question: {question}\n\n"
            f"Context gathered ({len(docs_so_far)} docs from: "
            f"{', '.join(sources_present)}):\n{brief}\n\n"
            f"Is this sufficient to answer the question well?\n"
            f'Return ONLY JSON: {{"has_enough": true, "additional_queries": [], '
            f'"additional_sources": []}}\n'
            f"- has_enough: true if context covers the question\n"
            f"- additional_queries: if not enough, 1-2 extra search terms\n"
            f"- additional_sources: specific source names to search (or empty for all)"
        )

        try:
            raw = await asyncio.wait_for(
                self._llm.generate(
                    eval_prompt,
                    system="You are a retrieval evaluator. Respond with JSON only.",
                ),
                timeout=8.0,
            )
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            return ReactEvaluation(
                has_enough=bool(data.get("has_enough", True)),
                additional_queries=data.get("additional_queries") or [],
                additional_sources=data.get("additional_sources") or [],
            )
        except Exception as exc:
            logger.debug("ReAct evaluation failed (%s)", exc)
            return None

    # ------------------------------------------------------------------ #
    # Vector search (with HyDE)                                           #
    # ------------------------------------------------------------------ #

    async def _vector_search_hyde(self, query: str, n_results: int = 20) -> list[StoredDocument]:
        """HyDE: generate a hypothetical answer first, embed that for better recall.

        Falls back to embedding the raw query if the LLM call fails or times out.
        HyDE (Hypothetical Document Embeddings) significantly improves semantic
        search precision by bridging the vocabulary gap between questions and docs.
        """
        if not self._vector_store or not self._vector_store.available or not self._embedding_client:
            return []

        embed_text = query
        try:
            hypothetical = await asyncio.wait_for(
                self._llm.generate(
                    f"Write a short factual document (2-3 sentences) that would "
                    f"directly answer this question: {query}",
                    system="You are generating a hypothetical document for semantic search. "
                           "Write a plausible, concise answer as if it came from a document. "
                           "No preamble.",
                ),
                timeout=8.0,
            )
            if hypothetical and len(hypothetical.strip()) > 10:
                embed_text = hypothetical.strip()
        except Exception:
            pass  # Fall back to raw query

        return await self._vector_search(embed_text, n_results=n_results)

    async def _vector_search(self, query: str, n_results: int = 20) -> list[StoredDocument]:
        if not self._vector_store or not self._vector_store.available or not self._embedding_client:
            return []
        try:
            emb = await self._embedding_client.embed_for_search(query)
            if not emb:
                return []
            hits = await self._vector_store.search_documents(emb, n_results=n_results)
            docs = []
            for hit in hits:
                try:
                    doc_id = int(hit["id"])
                    doc = await self._store.get_by_id(doc_id)
                    if doc:
                        docs.append(doc)
                except (ValueError, TypeError):
                    pass
            return docs
        except Exception:
            logger.debug("Vector search failed", exc_info=True)
            return []

    # ------------------------------------------------------------------ #
    # Reranking                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rerank(
        query: str,
        docs: list[StoredDocument],
        top_k: int = 30,
    ) -> list[StoredDocument]:
        """Apply cross-encoder reranking if available; otherwise return as-is."""
        if len(docs) <= 1:
            return docs
        try:
            from mneia.pipeline.rerank import get_reranker
            reranker = get_reranker()
            if reranker.available:
                return reranker.rerank(query, docs, top_k=top_k)
        except Exception:
            pass
        return docs[:top_k]

    # ------------------------------------------------------------------ #
    # Merging                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_and_diversify(
        docs: list[StoredDocument],
    ) -> list[StoredDocument]:
        """Cap each source at MAX_DOCS_PER_SOURCE, preserving RRF order."""
        seen_ids: set[int] = set()
        source_counts: dict[str, int] = {}
        first_pass: list[StoredDocument] = []
        overflow: list[StoredDocument] = []

        for doc in docs:
            if doc.id in seen_ids:
                continue
            seen_ids.add(doc.id)
            count = source_counts.get(doc.source, 0)
            if count < MAX_DOCS_PER_SOURCE:
                source_counts[doc.source] = count + 1
                first_pass.append(doc)
            else:
                overflow.append(doc)

        return (first_pass + overflow)[:50]

    # ------------------------------------------------------------------ #
    # Graph context                                                        #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Context building                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sentence_window(text: str, query_terms: set[str], window: int = 8) -> str:
        """Return the N sentences around the best query-matching sentence."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= window:
            return text[:4000]
        scores = [
            sum(1 for t in query_terms if t.lower() in s.lower())
            for s in sentences
        ]
        best = scores.index(max(scores))
        lo = max(0, best - window // 2)
        hi = min(len(sentences), lo + window)
        return " ".join(sentences[lo:hi])

    def _build_context(
        self,
        docs: list[StoredDocument],
        graph_context: str,
        question: str = "",
    ) -> str:
        parts: list[str] = []
        total_chars = 0
        query_terms: set[str] = {
            w for w in question.lower().split() if len(w) > 3
        }

        if graph_context:
            parts.append("--- Knowledge Graph ---")
            parts.append(graph_context)
            parts.append("")
            total_chars += len(graph_context)

        if docs:
            parts.append("--- Documents ---")
            for doc in docs:
                remaining = MAX_CONTEXT_CHARS - total_chars
                if remaining <= 300:
                    break
                if query_terms and len(doc.content) > 400:
                    raw = self._sentence_window(doc.content, query_terms)
                else:
                    raw = doc.content
                snippet = raw[:min(4000, remaining - 100)]
                ts = (
                    doc.timestamp.strftime("%Y-%m-%d")
                    if hasattr(doc.timestamp, "strftime")
                    else str(doc.timestamp)[:10] if doc.timestamp else ""
                )
                header = f"[{doc.title} — {doc.source}{', ' + ts if ts else ''}]"
                entry = f"{header}\n{snippet}"
                parts.append(entry)
                parts.append("")
                total_chars += len(entry)

        if not parts:
            return "No relevant context found in your knowledge base."

        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    # History                                                              #
    # ------------------------------------------------------------------ #

    def clear_history(self) -> None:
        self._history.clear()

    async def close(self) -> None:
        await self._llm.close()

    def _format_history(self) -> str:
        if not self._history:
            return ""

        lines: list[str] = []
        for turn in self._history[-(MAX_HISTORY_TURNS * 2):]:
            prefix = "User" if turn.role == "user" else "Assistant"
            content = turn.content[:500]
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Follow-up extraction                                                 #
    # ------------------------------------------------------------------ #

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
