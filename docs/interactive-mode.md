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

1. Searches your knowledge base for relevant documents
2. Builds a context block from the top matches
3. Sends the context + your question to the LLM
4. Displays the response in a formatted panel

The LLM can also suggest and automatically execute commands when appropriate. For example, if you ask "what's in my graph?", the LLM might respond with an explanation and also trigger `/graph`.

## Command Suggestions

When the LLM is not available, mneia suggests relevant slash commands based on keywords in your input. For example, typing "search for meetings" will suggest `/search meetings`.

## Features

- **Command history** — Arrow keys navigate previous inputs (persisted to `~/.mneia/history.txt`)
- **Tab completion** — Slash commands auto-complete with Tab
- **Ctrl+C** — Cancel current input (doesn't exit)
- **Ctrl+D / /exit** — Exit interactive mode
