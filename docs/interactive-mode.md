# Interactive Mode

mneia's interactive mode provides a REPL interface with slash commands, natural language intent detection, and LLM-powered conversational queries.

## Starting Interactive Mode

Run `mneia` with no arguments:

```bash
mneia
```

This displays the mneia banner, checks Ollama availability, shows quick status (document count, enabled connectors, daemon state), and enters the prompt loop.

## Slash Commands

All commands start with `/`:

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/status` | Show daemon and agent status |
| `/search <query>` | Full-text search across knowledge |
| `/ask <question>` | Ask a question with RAG |
| `/stats` | Show memory statistics |
| `/recent` | Show recently ingested documents |
| `/connectors` | List connectors and status |
| `/sync <name>` | Sync a connector immediately |
| `/connector-start <name>` | Start a connector's listener agent |
| `/connector-stop <name>` | Stop a connector's listener agent |
| `/agents` | List running agents |
| `/extract [limit]` | Run entity extraction |
| `/graph` | Show knowledge graph summary |
| `/graph-entities [type]` | List entities (optional type filter) |
| `/graph-person <name>` | Show everything about a person |
| `/graph-topic <name>` | Show everything about a topic |
| `/context` | Generate context .md files |
| `/config` | Show current configuration |
| `/start` | Start daemon in background |
| `/stop` | Stop the daemon |
| `/logs [level]` | Show recent daemon logs |
| `/clear` | Clear the screen |
| `/exit` | Exit mneia (alias: `/quit`) |

## Natural Language Intent Detection

When you type text without a `/` prefix, mneia first tries to detect intent and route to the appropriate command. Examples:

| You type | Detected command |
|----------|-----------------|
| "start the daemon" | `/start` |
| "how many documents do I have" | `/stats` |
| "show me latest documents" | `/recent` |
| "list connectors" | `/connectors` |
| "sync obsidian" | `/sync obsidian` |
| "show knowledge graph" | `/graph` |
| "run extraction" | `/extract` |
| "generate context files" | `/context` |
| "list agents" | `/agents` |
| "start obsidian agent" | `/connector-start obsidian` |
| "stop obsidian agent" | `/connector-stop obsidian` |

## LLM-Powered Conversation

If no intent is detected and an LLM is available (Ollama or API key configured), mneia:

1. Searches your knowledge base using hybrid search (FTS5 + vector similarity)
2. Queries the knowledge graph for matching entities and relationships
3. Injects personal context from persistent memory (preferences, patterns)
4. Sends context + your question to the LLM
5. Displays the response with source citations and follow-up suggestions

The LLM can also suggest and automatically execute commands when appropriate. For example, if you ask "what's in my graph?", the LLM might respond with an explanation and also trigger `/graph`.

## Session Memory

Interactive mode tracks your conversations across sessions:

1. **During the session** — interactions are recorded (role + content)
2. **On exit** — the LLM summarizes the session in 2-3 sentences
3. **Next session** — summaries and learned patterns are injected as context

Memory entries have a **decay weight** that fades over time unless reinforced by access. This naturally prioritizes recent and frequently-referenced knowledge.

## Command Suggestions

When the LLM is not available, mneia suggests relevant slash commands based on keywords in your input. For example, typing "search for meetings" will suggest `/search meetings`.

## Features

- **Command history** — Arrow keys navigate previous inputs (persisted to `~/.mneia/history.txt`)
- **Tab completion** — Slash commands auto-complete with Tab
- **Ctrl+C** — Cancel current input (doesn't exit)
- **Ctrl+D / /exit** — Exit interactive mode
