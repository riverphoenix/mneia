from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_resources(mcp: FastMCP) -> None:
    @mcp.resource("mneia://documents/{doc_id}")
    async def get_document(doc_id: str) -> str:
        """Retrieve a specific document by its ID."""
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        try:
            doc = await store.get_by_id(int(doc_id))
        except (ValueError, TypeError):
            return f"Invalid document ID: {doc_id}"

        if not doc:
            return f"Document {doc_id} not found."

        return (
            f"# {doc.title}\n\n"
            f"Source: {doc.source}\n"
            f"Type: {doc.content_type}\n"
            f"Timestamp: {doc.timestamp}\n\n"
            f"{doc.content}"
        )

    @mcp.resource("mneia://context/{filename}")
    async def get_context_file(filename: str) -> str:
        """Read a generated context markdown file."""
        from mneia.config import CONTEXT_DIR

        file_path = CONTEXT_DIR / filename
        if not file_path.exists():
            available = [
                f.name for f in CONTEXT_DIR.glob("*.md")
            ] if CONTEXT_DIR.exists() else []
            return (
                f"Context file '{filename}' not found. "
                f"Available: {', '.join(available) or 'none'}"
            )

        return file_path.read_text(encoding="utf-8")
