from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.core.connector import RawDocument
from mneia.core.llm import LLMClient
from mneia.memory.graph import GraphEdge, GraphNode, KnowledgeGraph
from mneia.memory.store import MemoryStore, StoredDocument

logger = logging.getLogger(__name__)

KNOWLEDGE_INTERVAL_SECONDS = 300
MAX_DOCS_PER_CYCLE = 20


class KnowledgeAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        config: MneiaConfig,
        store: MemoryStore,
        graph: KnowledgeGraph,
    ) -> None:
        super().__init__(
            name=name,
            description=(
                "Continuous learning agent — processes new documents, "
                "builds connections, and generates summaries"
            ),
        )
        self._config = config
        self._store = store
        self._graph = graph
        self._llm = LLMClient(config.llm)
        self._stop_event = asyncio.Event()
        self._docs_processed = 0
        self._connections_made = 0
        self._summaries_generated = 0
        self._last_processed_id = 0
        self._hermes_agent: Any = None
        self._use_hermes = False

        if config.hermes_enabled:
            try:
                from mneia.agents.hermes_bridge import (
                    create_hermes_agent,
                    is_hermes_available,
                )

                if is_hermes_available():
                    self._hermes_agent = create_hermes_agent(config, store, graph)
                    self._use_hermes = True
                    logger.info(f"{name}: hermes-agent enabled")
                else:
                    logger.info(f"{name}: hermes-agent not installed, using native fallback")
            except Exception:
                logger.warning(f"{name}: failed to initialize hermes-agent, using native fallback")

    async def run(self, **kwargs: Any) -> AgentResult:
        self._state = AgentState.RUNNING
        logger.info(f"{self.name}: started (interval={KNOWLEDGE_INTERVAL_SECONDS}s)")

        await self._initial_sync()

        while not self._stop_event.is_set():
            try:
                await self._cycle()
            except Exception:
                logger.exception(f"{self.name}: cycle failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=KNOWLEDGE_INTERVAL_SECONDS,
                )
            except TimeoutError:
                pass

        self._state = AgentState.STOPPED
        await self._llm.close()
        return AgentResult(
            agent_name=self.name,
            documents_processed=self._docs_processed,
            metadata={
                "connections_made": self._connections_made,
                "summaries_generated": self._summaries_generated,
            },
        )

    async def stop(self) -> None:
        self._stop_event.set()

    async def notify_new_documents(self) -> None:
        await self._cycle()

    async def _initial_sync(self) -> None:
        checkpoint = await self._store.get_checkpoint(f"knowledge-agent-{self.name}")
        if checkpoint:
            try:
                self._last_processed_id = int(checkpoint)
            except (ValueError, TypeError):
                pass
        logger.info(
            f"{self.name}: initial sync from doc id {self._last_processed_id}"
        )

    async def _cycle(self) -> None:
        unprocessed = await self._get_unprocessed_docs()
        if not unprocessed:
            logger.debug(f"{self.name}: no new documents to process")
            return

        logger.info(f"{self.name}: processing {len(unprocessed)} new documents")

        if self._use_hermes and self._hermes_agent is not None:
            await self._hermes_cycle(unprocessed)
        else:
            await self._native_cycle(unprocessed)

        await self._store.set_checkpoint(
            f"knowledge-agent-{self.name}",
            str(self._last_processed_id),
        )

    async def _hermes_cycle(self, docs: list[StoredDocument]) -> None:
        from mneia.agents.hermes_bridge import run_hermes_cycle

        doc_summaries = []
        for doc in docs:
            doc_summaries.append(
                f"[{doc.source}] {doc.title} (id={doc.id}):\n{doc.content[:1000]}"
            )
            if doc.id > self._last_processed_id:
                self._last_processed_id = doc.id
            self._docs_processed += 1

        try:
            result = await asyncio.to_thread(
                run_hermes_cycle, self._hermes_agent, doc_summaries,
            )
            if result:
                self._summaries_generated += 1
                logger.info(f"{self.name}: hermes cycle completed — {result[:200]}")
        except Exception:
            logger.exception(f"{self.name}: hermes cycle failed, running native fallback")
            await self._native_cycle(docs)

    async def _native_cycle(self, docs: list[StoredDocument]) -> None:
        for doc in docs:
            try:
                await self._process_document(doc)
                self._docs_processed += 1
                if doc.id > self._last_processed_id:
                    self._last_processed_id = doc.id
            except Exception:
                logger.exception(
                    f"{self.name}: failed to process doc {doc.id}: {doc.title}"
                )

        if len(docs) >= 3:
            try:
                await self._generate_cross_document_connections(docs)
            except Exception:
                logger.exception(f"{self.name}: cross-doc connections failed")

    async def _get_unprocessed_docs(self) -> list[StoredDocument]:
        conn = self._store._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM documents WHERE id > ? ORDER BY id ASC LIMIT ?",
                (self._last_processed_id, MAX_DOCS_PER_CYCLE),
            )
            return [self._store._row_to_doc(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def _process_document(self, doc: StoredDocument) -> None:
        if len(doc.content) < 50:
            return

        content_preview = doc.content[:2000]
        prompt = (
            "Analyze this document and extract:\n"
            "1. Key entities (people, projects, topics, tools)\n"
            "2. Key relationships between entities\n"
            "3. A one-sentence summary\n\n"
            f"Source: {doc.source}\n"
            f"Title: {doc.title}\n"
            f"Content:\n{content_preview}\n\n"
            "Respond in this exact format:\n"
            "ENTITIES: entity1 (type), entity2 (type), ...\n"
            "RELATIONSHIPS: entity1 -> relation -> entity2, ...\n"
            "SUMMARY: one sentence summary"
        )

        try:
            response = await self._llm.generate(prompt)
        except Exception:
            logger.debug(f"{self.name}: LLM failed for doc {doc.id}")
            return

        self._parse_and_store_analysis(doc, response)

    def _parse_and_store_analysis(
        self, doc: StoredDocument, response: str,
    ) -> None:
        lines = response.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("ENTITIES:"):
                self._extract_entities(stripped[9:].strip(), doc)
            elif stripped.startswith("RELATIONSHIPS:"):
                self._extract_relationships(stripped[14:].strip(), doc)

    def _extract_entities(self, text: str, doc: StoredDocument) -> None:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        for part in parts:
            name = part.split("(")[0].strip()
            entity_type = "unknown"
            if "(" in part and ")" in part:
                entity_type = part.split("(")[1].split(")")[0].strip().lower()

            if not name or len(name) < 2:
                continue

            node_id = f"{entity_type}:{name.lower().replace(' ', '-')}"
            try:
                node = GraphNode(
                    id=node_id,
                    entity_type=entity_type,
                    name=name,
                    properties={
                        "source_doc": doc.title,
                        "source": doc.source,
                    },
                )
                self._graph.add_entity(node)
            except Exception:
                pass

    def _extract_relationships(self, text: str, doc: StoredDocument) -> None:
        rels = [r.strip() for r in text.split(",") if "->" in r]
        for rel in rels:
            parts = [p.strip() for p in rel.split("->")]
            if len(parts) < 3:
                continue
            source_name = parts[0]
            relation = parts[1]
            target_name = parts[2]

            source_id = f"unknown:{source_name.lower().replace(' ', '-')}"
            target_id = f"unknown:{target_name.lower().replace(' ', '-')}"

            for nid in self._graph._graph.nodes:
                node_name = self._graph._graph.nodes[nid].get("name", "").lower()
                if node_name == source_name.lower():
                    source_id = nid
                if node_name == target_name.lower():
                    target_id = nid

            if (
                source_id in self._graph._graph
                and target_id in self._graph._graph
            ):
                try:
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=target_id,
                        relation=relation.lower().replace(" ", "_"),
                        weight=0.7,
                        evidence=f"From: {doc.title}",
                    )
                    self._graph.add_relationship(edge)
                    self._connections_made += 1
                except Exception:
                    pass

    async def _generate_cross_document_connections(
        self, docs: list[StoredDocument],
    ) -> None:
        doc_summaries = []
        for doc in docs[:10]:
            doc_summaries.append(
                f"[{doc.source}] {doc.title}: {doc.content[:300]}"
            )

        prompt = (
            "Given these recently ingested documents, identify "
            "connections between them. What themes, people, or topics "
            "appear across multiple documents?\n\n"
            + "\n\n".join(doc_summaries)
            + "\n\nList connections as:\n"
            "- Connection: doc_title1 <-> doc_title2 via shared_topic"
        )

        try:
            response = await self._llm.generate(prompt)
            if response and len(response) > 30:
                summary_doc = RawDocument(
                    source="knowledge-agent",
                    source_id=f"connections-{datetime.now(timezone.utc).isoformat()}",
                    content=response,
                    content_type="connection-summary",
                    title="Cross-document connections",
                    timestamp=datetime.now(timezone.utc),
                    metadata={"generated_by": self.name},
                )
                await self._store.store_document(summary_doc)
                self._summaries_generated += 1
                logger.info(f"{self.name}: generated cross-doc summary")
        except Exception:
            logger.debug(f"{self.name}: cross-doc summary LLM failed")
