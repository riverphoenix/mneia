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

- **Connects** to 19 data sources (Calendar, Gmail, Obsidian, Local Folders, Slack, GitHub, and more) — read-only, always
- **Learns** by extracting entities, relationships, and patterns via GLiNER NER + LLM structured extraction
- **Remembers** everything locally in a temporal knowledge graph with vector embeddings — nothing leaves your machine
- **Thinks** autonomously — identifies gaps, proposes connections, and surfaces insights
- **Generates** `.md` context files for Claude Code, Cursor, and other AI tools
- **Serves** as an MCP server so AI tools can query your knowledge directly
- **Converses** with you through a beautiful terminal UI with search, chat, and graph browser

## Install

```bash
pip install mneia
```

With intelligence extras (NER, reranking, structured extraction):

```bash
pip install 'mneia[intelligence]'
```

With everything:

```bash
pip install 'mneia[all]'
```

## Quick Start

```bash
# Just run it — the TUI handles everything
mneia
```

The TUI auto-starts the daemon, shows a dashboard, and guides you through setup. No manual config needed.

For headless/server use:

```bash
mneia config setup           # Interactive setup wizard
mneia connector enable obsidian
mneia connector setup obsidian
mneia start -d               # Start daemon in background
```

## Terminal UI

Running `mneia` launches a full Textual TUI with:

- **Dashboard** — stats panels, agent status, recent activity, quick actions
- **Search** — hybrid search with BM25 + vector + cross-encoder reranking, document preview
- **Chat** — multi-turn RAG conversation with citations and follow-ups
- **Agents** — live agent status with start/stop controls
- **Sources** — connector list, enable/disable, setup wizard
- **Graph** — knowledge graph browser with entity types, relationships, trending entities
- **Settings** — LLM provider, model, behavior configuration

Navigate with sidebar, keyboard shortcuts (1-7), or `/slash` commands in the command bar.

For the classic REPL experience: `mneia repl`

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
mneia repl                              # Classic interactive REPL mode
```

### Permissions

```bash
mneia permission list                 # List granted permissions
mneia permission grant <operation>    # Pre-approve an operation
mneia permission revoke <operation>   # Revoke a permission
```

### Agent Dashboard & Logs

```bash
mneia agent-stats                     # Show 24h agent activity stats
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
| Granola | Meeting notes (markdown) | Local files | Poll |
| Local Folders | Text, code, PDF files | Local files | Watch |
| Slack | Channel messages | Bot token | Poll |
| GitHub | Issues & pull requests | PAT | Poll |
| Linear | Issues & projects | API key | Poll |
| Todoist | Tasks & projects | API token | Poll |

Multi-account support: Gmail, Google Calendar, and Google Drive support multiple accounts (e.g., `gmail-work`, `gmail-personal`).

## Architecture

```
TUI (Textual) ──── CLI (Typer) ──── MCP Server (stdio)
     |                  |
  EmbeddedDaemon    Unix Socket IPC
     |                  |
  AgentManager ─────────┘
   /    |    \      \         \
Listener Worker Meta Knowledge Autonomous
Agents   Agent  Agent  Agent     Agent
  |        |                       |
Connectors Pipeline               ReasoningEngine
  |        NER (GLiNER)            (LLM gap analysis)
  |        Extract (Instructor)
  |        Rerank → Associate
  |        → Summarize → Generate
  |                        |
MemoryStore (SQLite+FTS5)  .md Context Files
VectorStore (ChromaDB)     (~/.mneia/context/)
KnowledgeGraph (NetworkX + temporal)
GraphRAG (LightRAG, optional)
CognitiveMemory (Cognee, optional)
```

**Agent Types:**
- **ListenerAgent** — one per connector, polls or watches data sources in real-time
- **WorkerAgent** — entity extraction (GLiNER + Instructor), association building, vector embedding
- **MetaAgent** — orchestrator, health monitoring, entity deduplication
- **KnowledgeAgent** — knowledge graph operations, cross-document connections
- **AutonomousAgent** — identifies knowledge gaps, proposes connections, generates insights

## Intelligence Pipeline

1. **Ingest** — Connectors fetch raw documents, normalize and store in SQLite with FTS5 + ChromaDB vectors
2. **NER** — GLiNER zero-shot NER extracts entities with confidence scores (optional, `pip install gliner`)
3. **Extract** — Instructor produces Pydantic-validated entities and relationships from LLM (optional, `pip install instructor`)
4. **Rerank** — Cross-encoder reranking for search quality (optional, `pip install rerankers`)
5. **Associate** — Cross-reference entities, merge duplicates, build temporal graph edges
6. **Summarize** — Generate rolling summaries per person, topic, and time period
7. **Generate** — Render Jinja2 templates into `.md` context files (auto-regenerated on changes)

Falls back gracefully to basic LLM JSON extraction when optional deps are not installed.

## Search

mneia uses hybrid search combining:
- **Full-text search** (SQLite FTS5) for keyword matching
- **BM25 ranking** (rank_bm25) for relevance scoring (included by default)
- **Cross-encoder reranking** (rerankers) for precision — `pip install 'mneia[intelligence]'`
- **Vector search** (ChromaDB + nomic-embed-text) for semantic similarity — `pip install 'mneia[vector]'`
- **Knowledge graph** traversal for entity context
- **GraphRAG** (LightRAG) for graph-augmented retrieval — `pip install 'mneia[graphrag]'`
- **Cognitive memory** (Cognee) for consolidated long-term memory — `pip install 'mneia[cognitive]'`

Results are merged, reranked, and deduplicated for optimal relevance.

## Temporal Knowledge Graph

The knowledge graph tracks when entities and relationships were first seen, last seen, and how often they're mentioned. This enables:
- **Trending entities** — who/what is most active recently
- **Timeline queries** — "what did I discuss with X last week"
- **Decay scoring** — older, less-mentioned entities rank lower

## Safety

Operations are classified by risk level:
- **LOW** — auto-approved (searches, reads)
- **MEDIUM** — requires user consent (web scraping, sync)
- **HIGH** — requires explicit approval (filesystem scanning, audio transcription)
- **CRITICAL** — always prompts (data purge)

Pre-approve operations with `mneia permission grant <operation>`.

## Resilience

- **Retry with backoff** — API calls retry automatically on transient failures
- **Circuit breaker** — LLM client pauses after repeated failures, auto-resets
- **Agent auto-restart** — crashed agents restart with exponential backoff (max 3 retries)
- **Dead connector cleanup** — stale config entries auto-removed on startup

## Core Principles

1. **Read-only** — Connectors never modify your data. No sending, no editing, no deleting.
2. **Local-only** — All data stays on your machine. No cloud sync. No telemetry.
3. **Open source** — MIT licensed. Inspect every line. Fork and customize.
4. **Zero-config** — `pip install mneia && mneia` — the TUI handles the rest.

## Optional Extras

```bash
pip install 'mneia[intelligence]'  # GLiNER NER + Instructor + Rerankers
pip install 'mneia[vector]'        # ChromaDB vector search
pip install 'mneia[graphrag]'      # LightRAG graph-augmented retrieval
pip install 'mneia[cognitive]'     # Cognee cognitive memory
pip install 'mneia[audio]'         # Whisper audio transcription
pip install 'mneia[web]'           # Web scraping (crawl4ai + playwright)
pip install 'mneia[mcp]'           # MCP server for AI tool integration
pip install 'mneia[all]'           # Everything
```

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

574 tests covering all agents, connectors, pipeline stages, TUI, and core infrastructure.

## License

MIT
