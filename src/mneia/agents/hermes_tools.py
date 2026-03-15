from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from mneia.core.connector import RawDocument
from mneia.memory.graph import GraphEdge, GraphNode, KnowledgeGraph
from mneia.memory.store import MemoryStore

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Search the user's personal knowledge base across all ingested sources "
                "(calendar, email, drive, notes, audio transcripts, etc.)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "source": {
                        "type": "string",
                        "description": "Optional source filter",
                        "enum": [
                            "google-calendar",
                            "gmail",
                            "google-drive",
                            "obsidian",
                            "granola",
                            "local-folders",
                            "web",
                            "knowledge-agent",
                        ],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_documents",
            "description": "Fetch the most recently ingested documents from the knowledge base",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of recent documents to fetch (default 10)",
                        "default": 10,
                    },
                    "source": {
                        "type": "string",
                        "description": "Optional source filter",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_graph",
            "description": (
                "Query the knowledge graph for an entity and its neighbors/connections"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Name of the entity to look up",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "How many hops to traverse (default 1)",
                        "default": 1,
                    },
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "store_insight",
            "description": (
                "Store a new insight or summary document back into the knowledge base"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the insight",
                    },
                    "content": {
                        "type": "string",
                        "description": "The insight content",
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Type of content (default 'insight')",
                        "default": "insight",
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_connection",
            "description": "Add or update a relationship between two entities in the graph",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_a": {
                        "type": "string",
                        "description": "Name of the first entity",
                    },
                    "entity_a_type": {
                        "type": "string",
                        "description": "Type of entity_a (person, project, topic, tool, etc.)",
                        "default": "unknown",
                    },
                    "entity_b": {
                        "type": "string",
                        "description": "Name of the second entity",
                    },
                    "entity_b_type": {
                        "type": "string",
                        "description": "Type of entity_b",
                        "default": "unknown",
                    },
                    "relation": {
                        "type": "string",
                        "description": "Relationship type (e.g. works_with, leads)",
                    },
                },
                "required": ["entity_a", "entity_b", "relation"],
            },
        },
    },
]


def _make_node_id(entity_type: str, name: str) -> str:
    return f"{entity_type}:{name.lower().replace(' ', '-')}"


def create_tool_handlers(
    store: MemoryStore,
    graph: KnowledgeGraph,
) -> dict[str, Callable[..., str]]:
    import asyncio

    def _run_async(coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def search_knowledge(
        query: str,
        source: str | None = None,
        limit: int = 5,
    ) -> str:
        async def _search() -> list[Any]:
            if source:
                return await store.search(query, limit=limit, source=source)
            return await store.search(query, limit=limit)

        results = _run_async(_search())
        if not results:
            return json.dumps({"results": [], "message": "No documents found"})
        output = []
        for doc in results:
            output.append({
                "id": doc.id,
                "source": doc.source,
                "title": doc.title,
                "content_preview": doc.content[:500],
                "timestamp": doc.timestamp,
            })
        return json.dumps({"results": output})

    def get_recent_documents(count: int = 10, source: str | None = None) -> str:
        conn = store._get_conn()
        try:
            if source:
                cursor = conn.execute(
                    "SELECT * FROM documents WHERE source = ? ORDER BY id DESC LIMIT ?",
                    (source, count),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM documents ORDER BY id DESC LIMIT ?",
                    (count,),
                )
            rows = cursor.fetchall()
            docs = []
            for row in rows:
                doc = store._row_to_doc(row)
                docs.append({
                    "id": doc.id,
                    "source": doc.source,
                    "title": doc.title,
                    "content_preview": doc.content[:500],
                    "timestamp": doc.timestamp,
                })
            return json.dumps({"documents": docs})
        finally:
            conn.close()

    def query_graph_fn(entity_name: str, depth: int = 1) -> str:
        node_id = None
        for nid, data in graph._graph.nodes(data=True):
            if data.get("name", "").lower() == entity_name.lower():
                node_id = nid
                break
        if not node_id:
            return json.dumps({
                "found": False,
                "message": f"Entity '{entity_name}' not found in graph",
            })
        neighbors = graph.get_neighbors(node_id, depth=depth)
        return json.dumps({"found": True, "entity_id": node_id, **neighbors})

    def store_insight(
        title: str,
        content: str,
        content_type: str = "insight",
    ) -> str:
        doc = RawDocument(
            source="knowledge-agent",
            source_id=f"hermes-insight-{datetime.now(timezone.utc).isoformat()}",
            content=content,
            content_type=content_type,
            title=title,
            timestamp=datetime.now(timezone.utc),
            metadata={"generated_by": "hermes-agent"},
        )
        doc_id = _run_async(store.store_document(doc))
        return json.dumps({"stored": True, "document_id": doc_id, "title": title})

    def add_connection(
        entity_a: str,
        entity_b: str,
        relation: str,
        entity_a_type: str = "unknown",
        entity_b_type: str = "unknown",
    ) -> str:
        node_a_id = _make_node_id(entity_a_type, entity_a)
        node_b_id = _make_node_id(entity_b_type, entity_b)
        node_a = GraphNode(
            id=node_a_id,
            entity_type=entity_a_type,
            name=entity_a,
            properties={"added_by": "hermes-agent"},
        )
        node_b = GraphNode(
            id=node_b_id,
            entity_type=entity_b_type,
            name=entity_b,
            properties={"added_by": "hermes-agent"},
        )
        graph.add_entity(node_a)
        graph.add_entity(node_b)

        edge = GraphEdge(
            source_id=node_a_id,
            target_id=node_b_id,
            relation=relation.lower().replace(" ", "_"),
            weight=0.8,
            evidence=f"Identified by hermes-agent at {datetime.now(timezone.utc).isoformat()}",
        )
        graph.add_relationship(edge)
        return json.dumps({
            "added": True,
            "edge": f"{entity_a} --[{relation}]--> {entity_b}",
        })

    return {
        "search_knowledge": search_knowledge,
        "get_recent_documents": get_recent_documents,
        "query_graph": query_graph_fn,
        "store_insight": store_insight,
        "add_connection": add_connection,
    }
