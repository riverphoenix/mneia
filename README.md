```
                         _
  _ __ ___  _ __   ___  (_) __ _
 | '_ ` _ \| '_ \ / _ \ | |/ _` |
 | | | | | | | | |  __/ | | (_| |
 |_| |_| |_|_| |_|\___| |_|\__,_|
```

> *mneia (μνεία)* — Greek for "memory, reference"

Autonomous multi-agent personal knowledge system. mneia connects to your apps (read-only), learns about your work, and builds persistent local memory that powers AI assistants with deep personal context.

## What it does

- **Connects** to 18 data sources (Calendar, Slack, GitHub, Notes, Chrome, Audio, and more) — read-only, always
- **Learns** by extracting entities, relationships, and patterns from your data via LLM
- **Remembers** everything locally in a knowledge graph with vector embeddings — nothing leaves your machine
- **Thinks** autonomously — identifies gaps, proposes connections, and surfaces insights
- **Generates** `.md` context files for Claude Code, Cursor, and other AI tools
- **Serves** as an MCP server so AI tools can query your knowledge directly
- **Converses** with you about your knowledge through a CLI/interactive interface

## Install

```bash
pip install mneia
```

Or with all optional extras (Google, Slack, audio, vector search, etc.):

```bash
pip install mneia[all]
```

## Quick Start

```bash
# Prerequisites: local LLM via Ollama
brew install ollama
ollama pull phi3:mini
ollama pull nomic-embed-text

# Setup
mneia config setup

# Enable a connector
mneia connector enable obsidian
mneia connector setup obsidian

# Sync and start
mneia connector sync obsidian
mneia start
```

## Interactive Mode

Run `mneia` with no arguments to enter interactive mode:

```
mneia › /help              # See all commands
mneia › /search meetings   # Search your knowledge
mneia › /stats             # View memory statistics
mneia › What did I discuss with Alice last week?  # Natural language query
```

The interactive mode supports slash commands, natural language intent detection, and LLM-powered conversational queries with automatic command routing. Cross-session memory means mneia learns your preferences over time.

## MCP Server

mneia exposes an MCP server for AI tool integration. Add it to your Claude Code config:

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

Available MCP tools: `mneia_search`, `mneia_ask`, `mneia_list_connectors`, `mneia_connector_status`, `mneia_sync`, `mneia_graph_query`, `mneia_memory_stats`, `mneia_marketplace_search`.

## CLI Commands

### Daemon Management

```bash
mneia start [--detach] [--connectors name1,name2]  # Start the knowledge daemon
mneia stop                                          # Stop gracefully
mneia status                                        # Show agent states and stats
```

### Configuration

```bash
mneia config setup         # Interactive setup wizard
mneia config show          # Show current configuration
mneia config set <key> <v> # Set a configuration value
mneia config reset         # Reset to defaults
```

### Connectors

```bash
mneia connector list                  # List connectors and status
mneia connector enable <name>         # Enable a connector
mneia connector disable <name>        # Disable a connector
mneia connector setup <name>          # Interactive connector setup
mneia connector sync <name>           # Trigger immediate sync
mneia connector start-agent <name>    # Start a connector's listener agent
mneia connector stop-agent <name>     # Stop a connector's listener agent
mneia connector agents                # List running connector agents
```

### Memory & Search

```bash
mneia memory stats                    # Show ingestion statistics
mneia memory search <query>           # Full-text + vector search across all knowledge
mneia memory recent                   # Show recently ingested items
mneia memory purge [--source <name>]  # Clear stored memory
```

### Knowledge Graph

```bash
mneia graph show                      # Knowledge graph summary
mneia graph entities [--type person]  # List entities, optionally by type
mneia graph person <name>             # Show everything about a person
mneia graph topic <name>              # Show everything about a topic
mneia graph export [--format json]    # Export the knowledge graph
```

### Entity Extraction

```bash
mneia extract [--limit 50]            # Run entity extraction on unprocessed docs
```

### Context Generation

```bash
mneia context generate                # Generate .md context files
mneia context show                    # List generated context files
mneia context link <target-dir>       # Symlink context to a project directory
```

### Conversational Query

```bash
mneia ask <question> [--source <name>]  # Single query with RAG
mneia chat                              # Multi-turn conversation mode
```

### Permissions

```bash
mneia permission list                 # List granted permissions
mneia permission grant <operation>    # Pre-approve an operation
mneia permission revoke <operation>   # Revoke a permission
```

### Agent Dashboard & Logs

```bash
mneia agents                          # Interactive TUI dashboard (Textual)
mneia logs [--level info] [--follow]  # Tail daemon logs
```

### MCP Server

```bash
mneia mcp serve                       # Start MCP server (stdio transport)
```

### Marketplace

```bash
mneia marketplace list                # List available connectors
mneia marketplace search <query>      # Search marketplace
mneia marketplace install <name>      # Install a connector
```

### Other

```bash
mneia version                         # Show version
mneia update                          # Check for updates
```

## Interactive Mode Commands

All CLI commands are also available as slash commands in interactive mode:

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/status` | Show daemon and agent status |
| `/search <query>` | Search your knowledge |
| `/ask <question>` | Ask a question with RAG |
| `/stats` | Show memory statistics |
| `/recent` | Show recently ingested documents |
| `/connectors` | List connectors and status |
| `/sync <name>` | Sync a connector |
| `/connector-start <name>` | Start a connector agent |
| `/connector-stop <name>` | Stop a connector agent |
| `/agents` | List running agents |
| `/extract [limit]` | Run entity extraction |
| `/graph` | Show knowledge graph summary |
| `/graph-entities [type]` | List entities |
| `/graph-person <name>` | Show person details |
| `/graph-topic <name>` | Show topic details |
| `/context` | Generate context files |
| `/config` | Show configuration |
| `/start` | Start daemon in background |
| `/stop` | Stop the daemon |
| `/chat` | Enter multi-turn chat mode |
| `/logs [level]` | Show daemon logs |

Natural language is also supported — the LLM detects intent and can automatically route to the appropriate command.

## Built-in Connectors

| Connector | Source | Auth | Mode |
|-----------|--------|------|------|
| Obsidian | Markdown vault | Local files | Watch |
| Google Calendar | Calendar events | OAuth2 (readonly) | Poll |
| Gmail | Email messages | OAuth2 (readonly) | Poll |
| Google Drive | Files, Docs, Sheets, Slides | OAuth2 (readonly) | Poll |
| Apple Notes | macOS Notes app | AppleScript | Poll |
| Asana | Projects & tasks | API token | Poll |
| JIRA | Tickets | API token | Poll |
| Confluence | Wiki pages | API token | Poll |
| Notion | Pages & databases | Bearer token | Poll |
| Zoom | Meeting recordings & transcripts | OAuth2 (S2S) | Poll |
| Chrome History | Browser history + page content | Local SQLite | Poll |
| Audio Transcription | Audio files (WAV, MP3, M4A) | Local (whisper) | Poll |
| Live Audio | Real-time meeting capture | Sounddevice | Watch |
| Slack | Channel messages | Bot token | Poll |
| GitHub | Issues & pull requests | PAT | Poll |
| Linear | Issues & projects | API key | Poll |
| Todoist | Tasks & projects | API token | Poll |

## Architecture

```
CLI / Interactive REPL ──── MCP Server (stdio)
        |
   Unix Socket IPC
        |
  AgentManager (daemon)
   /    |    \      \         \
Listener Worker Meta Enrichment Autonomous
Agents   Agent  Agent  Agent     Agent
  |        |                       |
Connectors Pipeline               ReasoningEngine
  |        Extract → Associate     (LLM gap analysis)
  |        → Summarize → Generate
  |                        |
MemoryStore (SQLite+FTS5)  .md Context Files
VectorStore (ChromaDB)     (~/.mneia/context/)
KnowledgeGraph (NetworkX)
PersistentMemory (cross-session)
```

**Agent Types:**
- **ListenerAgent** — one per connector, polls or watches data sources in real-time
- **WorkerAgent** — entity extraction, association building, vector embedding
- **MetaAgent** — orchestrator, health monitoring, entity deduplication
- **EnrichmentAgent** — web research to enrich sparse entities
- **WebResearchAgent** — deep topic research with scraping and LLM synthesis
- **AutonomousAgent** — identifies knowledge gaps, proposes connections, generates insights

## Memory Pipeline

1. **Ingest** — Connectors fetch raw documents, normalize and store in SQLite with FTS5 + ChromaDB vectors
2. **Extract** — LLM extracts entities (people, projects, topics, decisions) and relationships
3. **Associate** — Cross-reference entities, merge duplicates, build graph edges
4. **Summarize** — Generate rolling summaries per person, topic, and time period
5. **Generate** — Render Jinja2 templates into `.md` context files (auto-regenerated on changes)

## Search

mneia uses hybrid search combining:
- **Full-text search** (SQLite FTS5) for keyword matching
- **Vector search** (ChromaDB + nomic-embed-text) for semantic similarity
- **Knowledge graph** traversal for entity context

Results are merged and deduplicated for optimal relevance.

## Safety

Operations are classified by risk level:
- **LOW** — auto-approved (searches, reads)
- **MEDIUM** — requires user consent (web scraping, sync)
- **HIGH** — requires explicit approval (live audio capture)
- **CRITICAL** — always prompts (data purge)

Pre-approve operations with `mneia permission grant <operation>`.

## Resilience

- **Retry with backoff** — API calls retry automatically on transient failures
- **Circuit breaker** — LLM client pauses after repeated failures, auto-resets
- **Agent auto-restart** — crashed agents restart with exponential backoff (max 3 retries)
- **In-process metrics** — counters, gauges, and timers for observability

## Core Principles

1. **Read-only** — Connectors never modify your data. No sending, no editing, no deleting.
2. **Local-only** — All data stays on your machine. No cloud sync. No telemetry.
3. **Open source** — MIT licensed. Inspect every line. Fork and customize.
4. **Lightweight** — Async agents, not heavy processes. Runs alongside your work.

## Extending

Third-party connectors are pip packages using Python entry points:

```bash
mneia marketplace search slack
mneia marketplace install slack
```

Build your own: implement `BaseConnector` and publish as `mneia-connector-yourname`.

## Development

```bash
git clone https://github.com/riverphoenix/mneia.git
cd mneia
pip install -e ".[dev]"
pytest
```

### Testing

```bash
pytest tests/unit/              # Unit tests (mocked, fast)
pytest tests/connectors/        # Connector tests with fixtures
pytest tests/integration/       # CLI integration tests
pytest -v                       # All tests with verbose output
```

497 tests covering all agents, connectors, pipeline stages, and core infrastructure.

## License

MIT
