from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def mneia_search(
        query: str,
        limit: int = 10,
        source: str | None = None,
    ) -> str:
        """Search across all stored knowledge using full-text search.

        Args:
            query: The search query string
            limit: Maximum number of results (default 10)
            source: Optional source filter (e.g. 'obsidian', 'chrome-history')
        """
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        results = await store.search(query, limit=limit)

        if source:
            results = [r for r in results if r.source == source]

        if not results:
            return "No results found."

        parts = []
        for doc in results:
            content_preview = doc.content[:500]
            parts.append(
                f"## {doc.title}\n"
                f"Source: {doc.source} | Type: {doc.content_type}\n"
                f"Timestamp: {doc.timestamp}\n\n"
                f"{content_preview}"
            )
        return "\n\n---\n\n".join(parts)

    @mcp.tool()
    async def mneia_ask(
        question: str,
        source: str | None = None,
    ) -> str:
        """Ask a question about your knowledge using RAG.

        Uses retrieval-augmented generation to find relevant documents
        and generate an answer.

        Args:
            question: The question to ask
            source: Optional source filter
        """
        from mneia.config import MneiaConfig
        from mneia.conversation import ConversationEngine

        config = MneiaConfig.load()
        engine = ConversationEngine(config)

        try:
            result = await engine.ask(
                question, source_filter=source,
            )
            response = result.answer

            if result.citations:
                response += "\n\nSources:\n"
                for cite in result.citations:
                    response += f"- {cite.title} ({cite.source})\n"

            return response
        finally:
            await engine.close()

    @mcp.tool()
    async def mneia_list_connectors() -> str:
        """List all available connectors and their status."""
        from mneia.config import MneiaConfig
        from mneia.connectors import get_available_connectors

        config = MneiaConfig.load()
        available = get_available_connectors()

        lines = []
        for manifest in available:
            conn_config = config.connectors.get(manifest.name)
            status = (
                "enabled"
                if conn_config and conn_config.enabled
                else "disabled"
            )
            lines.append(
                f"- {manifest.name}: {manifest.display_name} "
                f"[{status}] ({manifest.auth_type})"
            )

        return "\n".join(lines) if lines else "No connectors available."

    @mcp.tool()
    async def mneia_connector_status(name: str) -> str:
        """Get detailed status for a specific connector.

        Args:
            name: The connector name (e.g. 'obsidian', 'chrome-history')
        """
        from mneia.config import MneiaConfig
        from mneia.connectors import get_connector_manifest

        config = MneiaConfig.load()
        manifest = get_connector_manifest(name)
        if not manifest:
            return f"Unknown connector: {name}"

        conn_config = config.connectors.get(name)
        enabled = conn_config.enabled if conn_config else False
        last_sync = (
            conn_config.last_checkpoint if conn_config else None
        )

        return (
            f"Connector: {manifest.display_name}\n"
            f"Name: {manifest.name}\n"
            f"Mode: {manifest.mode.value}\n"
            f"Enabled: {enabled}\n"
            f"Last sync: {last_sync or 'never'}\n"
            f"Poll interval: {manifest.poll_interval_seconds}s\n"
            f"Auth type: {manifest.auth_type}"
        )

    @mcp.tool()
    async def mneia_sync(name: str) -> str:
        """Trigger an immediate sync for a connector.

        Args:
            name: The connector name to sync
        """
        from mneia.config import MneiaConfig
        from mneia.connectors import create_connector
        from mneia.pipeline.ingest import ingest_connector

        config = MneiaConfig.load()
        conn_config = config.connectors.get(name)
        if not conn_config or not conn_config.enabled:
            return f"Connector '{name}' is not enabled."

        connector = create_connector(name)
        if not connector:
            return f"Unknown connector: {name}"

        result = await ingest_connector(
            connector, conn_config, config,
        )

        if conn_config.last_checkpoint != result.checkpoint:
            conn_config.last_checkpoint = result.checkpoint
            config.save()

        return (
            f"Synced {result.documents_ingested} documents "
            f"from {name}."
        )

    @mcp.tool()
    async def mneia_graph_query(
        entity_name: str,
        entity_type: str | None = None,
        depth: int = 2,
    ) -> str:
        """Query the knowledge graph for an entity and its connections.

        Args:
            entity_name: Name of the entity to look up
            entity_type: Optional type (person, topic, project, etc.)
            depth: How many hops to traverse (default 2)
        """
        from mneia.memory.graph import KnowledgeGraph

        graph = KnowledgeGraph()
        name_lower = entity_name.lower().replace(" ", "-")

        if entity_type:
            node_id = f"{entity_type}:{name_lower}"
        else:
            candidates = [
                nid
                for nid in graph._graph.nodes
                if name_lower in nid.lower()
            ]
            if not candidates:
                return f"No entity found matching '{entity_name}'."
            node_id = candidates[0]

        result = graph.get_neighbors(node_id, depth=depth)
        if not result["nodes"]:
            return f"No entity found: {node_id}"

        parts = [f"Entity: {node_id}"]
        node_data = graph._graph.nodes.get(node_id, {})
        desc = node_data.get("properties", {}).get("description", "")
        if desc:
            parts.append(f"Description: {desc}")

        if result["edges"]:
            parts.append("\nConnections:")
            for edge in result["edges"]:
                other = (
                    edge["target"]
                    if edge["source"] == node_id
                    else edge["source"]
                )
                other_name = (
                    other.split(":", 1)[-1].replace("-", " ").title()
                )
                parts.append(
                    f"  - {edge['relation']} → {other_name}"
                )

        return "\n".join(parts)

    @mcp.tool()
    async def mneia_memory_stats() -> str:
        """Get memory statistics (document counts, sources, etc.)."""
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        stats = await store.get_stats()

        parts = [
            f"Total documents: {stats.get('total_documents', 0)}",
            f"Total entities: {stats.get('total_entities', 0)}",
            f"Total associations: {stats.get('total_associations', 0)}",
        ]

        by_source = stats.get("by_source", {})
        if by_source:
            parts.append("\nBy source:")
            for source, count in by_source.items():
                parts.append(f"  {source}: {count}")

        return "\n".join(parts)

    @mcp.tool()
    async def mneia_marketplace_search(query: str) -> str:
        """Search for connectors in the marketplace.

        Args:
            query: Search query for marketplace connectors
        """
        from mneia.marketplace.registry import search_index

        results = search_index(query)
        if not results:
            return f"No connectors found matching: {query}"

        lines = []
        for entry in results:
            status = "installed" if entry.installed else "available"
            lines.append(
                f"- {entry.name}: {entry.description[:60]} "
                f"[{status}]"
            )

        return "\n".join(lines)
