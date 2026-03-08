# MCP Server Integration

mneia exposes a Model Context Protocol (MCP) server that allows AI tools to query your personal knowledge base directly.

## Setup

### Claude Code

Add mneia to your Claude Code MCP configuration (`~/.claude/claude_desktop_config.json` or project settings):

```json
{
  "mcpServers": {
    "mneia": {
      "command": "mneia",
      "args": ["mcp", "serve"]
    }
  }
}
```

### Other MCP Clients

Any MCP-compatible client can connect to mneia via stdio transport:

```bash
mneia mcp serve
```

The server communicates over stdin/stdout using the MCP protocol.

## Available Tools

### `mneia_search`

Search across all stored knowledge using full-text search.

**Parameters:**
- `query` (string, required) — Search query
- `limit` (int, default: 10) — Maximum results
- `source` (string, optional) — Filter by source (e.g., "obsidian", "chrome-history")

**Returns:** Formatted search results with title, source, timestamp, and content preview.

### `mneia_ask`

Ask a question using retrieval-augmented generation (RAG).

**Parameters:**
- `question` (string, required) — The question to ask
- `source` (string, optional) — Limit context to a specific source

**Returns:** LLM-generated answer with source citations.

### `mneia_list_connectors`

List all available connectors and their enabled/disabled status.

**Returns:** Connector names, display names, status, and auth type.

### `mneia_connector_status`

Get detailed status for a specific connector.

**Parameters:**
- `name` (string, required) — Connector name (e.g., "obsidian")

**Returns:** Connector details including mode, enabled state, last sync time, poll interval, and auth type.

### `mneia_sync`

Trigger an immediate sync for a connector.

**Parameters:**
- `name` (string, required) — Connector name to sync

**Returns:** Number of documents ingested.

### `mneia_graph_query`

Query the knowledge graph for an entity and its connections.

**Parameters:**
- `entity_name` (string, required) — Name of the entity to look up
- `entity_type` (string, optional) — Type filter (person, topic, project, etc.)
- `depth` (int, default: 2) — How many relationship hops to traverse

**Returns:** Entity details, description, and all connections within the specified depth.

### `mneia_memory_stats`

Get memory statistics (document counts, entity counts, sources).

**Returns:** Total documents, entities, associations, and per-source breakdowns.

### `mneia_marketplace_search`

Search for connectors in the marketplace.

**Parameters:**
- `query` (string, required) — Search query

**Returns:** Matching connectors with descriptions and installation status.

## Available Resources

### `mneia://documents/{doc_id}`

Retrieve a specific document by its ID.

**Returns:** Full document content with metadata (source, title, timestamp, URL).

### `mneia://context/{filename}`

Read a generated context file (e.g., `CLAUDE.md`, `people.md`).

**Returns:** File contents.

## Requirements

The `mcp` Python package must be installed:

```bash
pip install mneia[mcp]
```

If the package is not installed, `mneia mcp serve` will show an error with installation instructions.

## Use Cases

- **Claude Code context** — Claude can search your notes, meetings, and documents while coding
- **Project context** — Query who's involved in a project and recent decisions
- **Knowledge graph exploration** — Traverse entity relationships through natural language
- **Connector management** — Trigger syncs and check connector status from within your AI tool
