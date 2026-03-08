# mneia

> *mneia (μνεία)* — Greek for "memory, reference"

Autonomous multi-agent personal knowledge system. mneia connects to your apps (read-only), learns about your work, and builds persistent local memory that powers AI assistants with deep personal context.

## What it does

- **Connects** to your apps (Calendar, Email, Notes, Tasks, Documents) — read-only, always
- **Learns** by extracting entities, relationships, and patterns from your data via LLM
- **Remembers** everything locally in a knowledge graph — nothing leaves your machine
- **Generates** `.md` context files for Claude Code, Cursor, and other AI tools
- **Converses** with you about your knowledge through a CLI/interactive interface

## Quick Start

```bash
# Install
pipx install mneia

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

The interactive mode supports slash commands, natural language intent detection, and LLM-powered conversational queries with automatic command routing.

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
mneia memory search <query>           # Full-text search across all knowledge
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

### Agent Dashboard & Logs

```bash
mneia agents                          # Interactive TUI dashboard (Textual)
mneia logs [--level info] [--follow]  # Tail daemon logs
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

| Connector | Source | Auth | Status |
|-----------|--------|------|--------|
| Obsidian | Markdown vault | Local files | Available |
| Google Calendar | Calendar events | OAuth2 (readonly) | Available |
| Gmail | Email messages | OAuth2 (readonly) | Available |
| Google Drive | Files, Docs, Sheets, Slides | OAuth2 (readonly) | Available |
| Apple Notes | macOS Notes app | AppleScript | Available |
| Asana | Projects & tasks | API token | Available |
| JIRA | Tickets | API token | Available |
| Confluence | Wiki pages | API token | Available |
| Notion | Pages & databases | Bearer token | Available |
| Zoom | Meeting recordings & transcripts | OAuth2 (S2S) | Available |
| Chrome History | Browser history | Local SQLite | Available |
| Audio Transcription | Audio files | Local (whisper) | Available |

## Architecture

```
CLI / Interactive REPL
        |
   Unix Socket IPC
        |
  AgentManager (daemon)
   /    |    \
Listener  Worker   Meta
Agents    Agent    Agent
  |         |
Connectors  Pipeline: Extract → Associate → Summarize → Generate
  |                                                        |
MemoryStore (SQLite + FTS5)                     .md Context Files
KnowledgeGraph (NetworkX + SQLite)              (~/.mneia/context/)
```

**Agent Types:**
- **ListenerAgent** — one per connector, polls/watches data sources
- **WorkerAgent** — entity extraction, association building
- **MetaAgent** — orchestrator, health monitoring, entity deduplication

## Memory Pipeline

1. **Ingest** — Connectors fetch raw documents, normalize and store in SQLite with FTS5
2. **Extract** — LLM extracts entities (people, projects, topics, decisions) and relationships
3. **Associate** — Cross-reference entities, merge duplicates, build graph edges
4. **Summarize** — Generate rolling summaries per person, topic, and time period
5. **Generate** — Render Jinja2 templates into `.md` context files

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

## Documentation

See the [docs/](docs/) folder for detailed feature documentation.

## License

MIT
