# mneia

> *mneia (μνεία)* — Greek for "memory, reference"

Autonomous multi-agent personal knowledge system. mneia connects to your apps (read-only), learns about your work, and builds persistent local memory that powers AI assistants with deep personal context.

## What it does

- **Connects** to your apps (Calendar, Email, Notes, Tasks, Documents) — read-only, always
- **Learns** by extracting entities, relationships, and patterns from your data
- **Remembers** everything locally in a knowledge graph — nothing leaves your machine
- **Generates** `.md` context files for Claude Code, Cursor, and other AI tools
- **Converses** with you about your knowledge through a CLI interface

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

# Start learning
mneia connector enable obsidian
mneia connector setup obsidian
mneia start
```

## Built-in Connectors

| Connector | Source | Auth |
|-----------|--------|------|
| Obsidian | Markdown vault | Local files |
| Apple Notes | macOS Notes app | AppleScript |
| Google Calendar | Calendar events | OAuth2 (readonly) |
| Gmail | Email messages | OAuth2 (readonly) |
| Google Drive | Files & Docs | OAuth2 (readonly) |
| Asana | Projects & tasks | API token |
| JIRA | Tickets | API token |
| Confluence | Wiki pages | API token |
| Notion | Pages & databases | Bearer token |
| Zoom | Meeting details | API key |
| Chrome | Browser history | Local SQLite |
| Audio | Meeting transcription | System audio |

## Core Principles

1. **Read-only** — Connectors never modify your data. No sending, no editing, no deleting.
2. **Local-only** — All data stays on your machine. No cloud sync. No telemetry.
3. **Open source** — MIT licensed. Inspect every line. Fork and customize.
4. **Lightweight** — Async agents, not heavy processes. Runs alongside your work.

## CLI Commands

```bash
mneia start                    # Start the knowledge daemon
mneia stop                     # Stop gracefully
mneia status                   # Show agent states and stats

mneia connector list           # List connectors and status
mneia connector sync obsidian  # Trigger immediate sync

mneia memory search "project"  # Search your knowledge
mneia memory stats             # Show ingestion stats

mneia context generate         # Generate .md context files
mneia context link ./project   # Symlink context to a project

mneia ask "Who is working on X?"  # Query your knowledge

mneia graph show               # Knowledge graph summary
mneia agents                   # Interactive agent dashboard
```

## Extending

Third-party connectors are pip packages:

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

## License

MIT
