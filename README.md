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

- **Connects** to 10 data sources (Calendar, Gmail, Obsidian, Local Folders, GitHub, and more) — read-only, always
- **Learns** by extracting entities, relationships, and patterns via GLiNER NER + LLM structured extraction
- **Remembers** everything locally in a temporal knowledge graph with vector embeddings — nothing leaves your machine
- **Thinks** autonomously — identifies gaps, proposes connections, and surfaces insights
- **Generates** `.md` context files for Claude Code, Cursor, and other AI tools
- **Serves** as an MCP server so AI tools can query your knowledge directly
- **Converses** with you through an interactive REPL with search, chat, and graph queries

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
mneia config setup           # Configure LLM provider (Ollama, Anthropic, or OpenAI)
mneia connector enable obsidian
mneia connector setup obsidian
mneia start -d               # Start daemon in background
mneia                        # Enter interactive REPL
```

Or for immediate one-off queries without the daemon:

```bash
mneia ask "what did I discuss with Alice last week?"
mneia memory search "project deadline"
```

## Interactive Mode

Running `mneia` with no arguments enters an interactive REPL with:

- **Slash commands** — `/search`, `/ask`, `/graph`, `/sync`, `/agents`, and more
- **Natural language routing** — type plain text and mneia detects intent automatically
- **RAG conversations** — queries your knowledge base with context-aware LLM responses and citations
- **Session memory** — conversations are summarized and injected as context on next session
- **Tab completion** and **command history**

```
mneia › /search project alpha
mneia › who did I meet with at the last planning session?
mneia › /graph-person Alice
mneia › /sync obsidian
```

For all available commands: `mneia --help` or type `/help` in the REPL.

## Smart RAG (v0.3.0)

mneia's conversational search uses a multi-stage intelligent retrieval pipeline:

- **ReAct loop** — LLM routes each question to the most relevant sources, generates sub-queries, and evaluates whether gathered context is sufficient before answering
- **Source routing** — keyword detection + LLM routing directs queries to the right connectors (calendar for meetings, gmail for email, etc.)
- **Temporal reasoning** — natural language time expressions ("last week", "Q1 2024", "yesterday") are parsed into timestamp filters applied at the DB level
- **RAG Fusion (RRF)** — Reciprocal Rank Fusion merges results from multiple independent searches (initial, sub-queries, fallback, vector) for better recall
- **HyDE** — Hypothetical Document Embeddings: LLM generates a hypothetical answer first, then embeds that for semantic search — bridges vocabulary gap between questions and documents
- **Sentence-window retrieval** — returns the best-matching sentence window from each document rather than a raw content slice
- **RAPTOR** — KnowledgeAgent periodically clusters documents with TF-IDF + agglomerative clustering and generates LLM summaries of each cluster, stored as synthetic searchable documents
- **Co-reference resolution** — pronouns in documents are resolved to canonical names before entity extraction (optional: `pip install fastcoref`)
- **Cross-encoder reranking** — final results ranked by a cross-encoder (optional: `pip install 'mneia[intelligence]'`)

Context window: 80,000 characters. Search limit: 200 documents per pass.

## Claude Code Integration

mneia integrates with Claude Code in three ways — pick whichever fits your workflow.

### Option 1 — Install skill after pip install (recommended)

```bash
pip install mneia
mneia config setup
mneia sync
mneia install-skill          # copies skill + generates context + updates CLAUDE.md
```

From that point, Claude Code understands mneia commands and your personal context is loaded
automatically into every conversation.

### Option 2 — Install skill via script (same as option 1, without Python)

```bash
bash scripts/install-claude-code-skill.sh
```

### Option 3 — Claude Code plugin marketplace

```
/plugin marketplace add riverphoenix/mneia
/plugin install mneia-plugin@mneia
```

Then install mneia itself and run a first sync:

```bash
pip install mneia && mneia config setup && mneia sync
mneia context generate-claude    # write ~/.mneia/claude-context.md
```

---

Once installed, try these in Claude Code:

```
ask mneia what I worked on last week
run mneia status
set up mneia for me
sync my notes and refresh context
```

Regenerate context after each sync to keep Claude's view of your knowledge base current:

```bash
mneia context generate-claude
```

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
mneia connector setup <name>          # Interactive connector setup (validates credentials)
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
mneia                                   # Interactive REPL (default)
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
| Confluence | Wiki pages | API token | Poll |
| Notion | Pages & databases | Bearer token | Poll |
| Zoom | Meeting recordings & transcripts | OAuth2 (S2S) | Poll |
| Chrome History | Browser history + page content | Local SQLite | Poll |
| Granola | Meeting notes (markdown) | Local files | Poll |
| Local Folders | Text, code, PDF files | Local files | Watch |
| Slack | Channel messages | Bot token | Poll |
| GitHub | Issues & pull requests | PAT | Poll |

Multi-account support: Gmail, Google Calendar, and Google Drive support multiple accounts (e.g., `gmail-work`, `gmail-personal`).

## Architecture

```
CLI (Typer) ──── Interactive REPL ──── MCP Server (stdio)
     |                  |
  Unix Socket IPC       |
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
- **HIGH** — requires explicit approval (filesystem scanning)
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
4. **Credential validation** — Setup verifies credentials immediately — no silent failures.

## Optional Extras

```bash
pip install 'mneia[intelligence]'  # GLiNER NER + Instructor + Rerankers
pip install 'mneia[vector]'        # ChromaDB vector search
pip install 'mneia[graphrag]'      # LightRAG graph-augmented retrieval
pip install 'mneia[cognitive]'     # Cognee cognitive memory
pip install 'mneia[web]'           # Web scraping (crawl4ai + playwright)
pip install 'mneia[mcp]'           # MCP server for AI tool integration
pip install 'mneia[all]'           # Everything
```

## Extending

Third-party connectors are pip packages using Python entry points:

```bash
mneia marketplace search myservice
mneia marketplace install myservice
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

388+ unit tests covering all agents, connectors, pipeline stages, and core infrastructure.

## License

MIT
