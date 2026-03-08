from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from mneia.mcp.resources import register_resources
from mneia.mcp.tools import register_tools

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mneia",
    instructions=(
        "mneia is a personal knowledge management system. "
        "Use the available tools to search documents, ask questions, "
        "list connectors, check status, trigger syncs, and query "
        "the knowledge graph."
    ),
)

register_tools(mcp)
register_resources(mcp)


def run_server() -> None:
    mcp.run(transport="stdio")
