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

Full-text search across all stored documents using SQLite FTS5. Supports natural language queries — special characters are automatically sanitized.

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

Run LLM-powered entity extraction on unprocessed documents. Extracts people, projects, topics, decisions, and relationships.

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

### `mneia context show`

List generated context files with sizes and modification dates.

### `mneia context link <target-dir>`

Create symlinks from generated context files into a project directory.

---

## Conversational Query

### `mneia ask <question>`

Ask a question about your knowledge using RAG (Retrieval-Augmented Generation). Searches relevant documents, builds context, and generates an LLM response.

**Options:**
- `--source, -s <name>` — Limit search to a specific source

---

## Agent Dashboard

### `mneia agents`

Launch an interactive TUI dashboard (built with Textual) showing:
- Daemon status
- Agent states (running, stopped, error)
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

## Other

### `mneia version`

Show the installed mneia version.

### `mneia update`

Check GitHub releases for a newer version and show upgrade instructions.
