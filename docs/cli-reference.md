# CLI Reference

## Global Options

mneia supports both direct CLI commands and an interactive REPL mode.

- `mneia` (no args) — Enter interactive mode
- `mneia <command>` — Execute a command directly

---

## Daemon Management

### `mneia start`

Start the mneia knowledge daemon.

**Options:**
- `--detach, -d` — Run in background (default: foreground)
- `--connectors, -c <names>` — Comma-separated list of connectors to start (default: all enabled)

**Examples:**
```bash
mneia start                      # Start in foreground
mneia start -d                   # Start as background daemon
mneia start -c obsidian          # Start with only obsidian connector
```

### `mneia stop`

Gracefully stop the running daemon via IPC.

### `mneia status`

Show daemon status, running agents, and their states.

---

## Configuration

### `mneia config setup`

Interactive wizard to configure LLM provider, model, and output directory. Supports Ollama (default), Anthropic, and OpenAI.

### `mneia config show`

Display current configuration as JSON.

### `mneia config set <key> <value>`

Set a configuration value using dot-separated key paths.

```bash
mneia config set llm.model phi3:mini
mneia config set llm.provider anthropic
mneia config set enrichment_scrape_enabled true
```

### `mneia config reset`

Reset all configuration to defaults (requires confirmation).

---

## Connectors

### `mneia connector list`

List all available connectors with their enabled/disabled status and auth type.

### `mneia connector enable <name>`

Enable a connector for use. Must be followed by `connector setup` to configure it.

### `mneia connector disable <name>`

Disable a connector.

### `mneia connector setup <name>`

Run interactive setup for a connector (e.g., setting vault path for Obsidian).

### `mneia connector sync <name>`

Trigger an immediate sync for a connector, ingesting new documents since the last checkpoint.

### `mneia connector start-agent <name>`

Start a connector's listener agent while the daemon is running. Requires the daemon to be active.

### `mneia connector stop-agent <name>`

Stop a specific connector's listener agent without stopping the entire daemon.

### `mneia connector agents`

List all currently running agents and their states.

---

## Memory & Search

### `mneia memory stats`

Show memory statistics including total documents, entities, associations, and per-source breakdowns.

### `mneia memory search <query>`

Hybrid search across all stored documents using SQLite FTS5 full-text search and ChromaDB vector similarity. Results are merged and deduplicated.

**Options:**
- `--limit, -n <int>` — Maximum results (default: 10)

### `mneia memory recent`

Show recently ingested documents.

**Options:**
- `--limit, -n <int>` — Maximum results (default: 10)

### `mneia memory purge`

Clear stored memory data.

**Options:**
- `--source, -s <name>` — Purge only documents from this source
- `--confirm` — Skip confirmation prompt

---

## Entity Extraction

### `mneia extract`

Run LLM-powered entity extraction on unprocessed documents. Extracts people, projects, topics, decisions, and relationships. Entities are also embedded into ChromaDB for vector search.

**Options:**
- `--limit, -n <int>` — Maximum documents to process (default: 50)

---

## Knowledge Graph

### `mneia graph show`

Display knowledge graph summary with entity and relationship counts, broken down by type.

### `mneia graph entities`

List all entities in the knowledge graph.

**Options:**
- `--type, -t <type>` — Filter by entity type (person, project, topic, etc.)

### `mneia graph person <name>`

Show all relationships and information known about a person.

### `mneia graph topic <name>`

Show all relationships and information known about a topic.

### `mneia graph export`

Export the full knowledge graph.

**Options:**
- `--format, -f <format>` — Export format (default: json)

---

## Context Generation

### `mneia context generate`

Force regenerate all `.md` context files from the current knowledge graph using Jinja2 templates. Output directory is configured via `context_output_dir`.

Generated files: `CLAUDE.md`, `people.md`, `projects.md`, `decisions.md`, `beliefs.md`

Context files are also auto-regenerated when the daemon detects enough new documents (configurable via `context_min_changes_for_regen`).

### `mneia context show`

List generated context files with sizes and modification dates.

### `mneia context link <target-dir>`

Create symlinks from generated context files into a project directory.

---

## Conversational Query

### `mneia ask <question>`

Ask a question about your knowledge using RAG (Retrieval-Augmented Generation). Uses hybrid search (FTS5 + vector similarity) to find relevant documents, queries the knowledge graph for entity context, and generates an LLM response with citations.

**Options:**
- `--source, -s <name>` — Limit search to a specific source

### `mneia chat`

Enter multi-turn conversation mode with preserved history and cross-session memory. The conversation engine injects personal context (learned preferences, patterns) from persistent memory.

---

## Permissions

### `mneia permission list`

List all currently granted permissions with their expiry times.

### `mneia permission grant <operation>`

Pre-approve a risky operation. Operations are classified by risk level (LOW, MEDIUM, HIGH, CRITICAL). LOW-risk operations are auto-approved; MEDIUM and above require explicit consent.

### `mneia permission revoke <operation>`

Revoke a previously granted permission.

---

## MCP Server

### `mneia mcp serve`

Start the MCP (Model Context Protocol) server using stdio transport. This allows AI tools like Claude Code to query your knowledge base directly.

**Available MCP tools:**
- `mneia_search` — Full-text search across stored knowledge
- `mneia_ask` — Ask a question with RAG
- `mneia_list_connectors` — List connectors and status
- `mneia_connector_status` — Detailed connector info
- `mneia_sync` — Trigger a connector sync
- `mneia_graph_query` — Query the knowledge graph by entity
- `mneia_memory_stats` — Get document/entity counts
- `mneia_marketplace_search` — Search marketplace

**Available MCP resources:**
- `mneia://documents/{doc_id}` — Retrieve a specific document
- `mneia://context/{filename}` — Read a generated context file

See [MCP Integration](mcp-integration.md) for setup instructions.

---

## Agent Dashboard

### `mneia agents`

Launch an interactive TUI dashboard (built with Textual) showing:
- Daemon status
- Agent states (running, stopped, error) for all 6 agent types
- Memory statistics
- Knowledge graph overview

Auto-refreshes every 5 seconds. Press `q` to quit, `r` to refresh.

---

## Logs

### `mneia logs`

Show daemon log output.

**Options:**
- `--level, -l <level>` — Filter by log level (debug, info, warn, error)
- `--follow, -f` — Follow log output (like `tail -f`)
- `--lines, -n <int>` — Number of lines to show (default: 50)

---

## Marketplace

### `mneia marketplace list`

Shows all connectors in the marketplace index with installation status.

### `mneia marketplace search <query>`

Search by name, description, and tags.

### `mneia marketplace install <name>`

Install a connector package via pip.

---

## Other

### `mneia version`

Show the installed mneia version.

### `mneia update`

Check GitHub releases for a newer version and show upgrade instructions.
