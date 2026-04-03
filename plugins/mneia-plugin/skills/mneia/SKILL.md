---
name: mneia
description: Personal knowledge assistant powered by mneia. Use when the user wants to ask questions about their notes, calendar, emails, GitHub, meetings, or personal knowledge base. Also handles mneia setup, sync, status, and connector management. Trigger for: "what did I work on", "who is X", "what meetings do I have", "sync my notes", "mneia status", "set up mneia", "add a connector".
---

# mneia — Personal Knowledge Assistant

You have access to the user's **mneia** personal knowledge system via the `mneia` CLI.
mneia indexes the user's digital life (notes, calendar, emails, GitHub, meetings, files) into
a searchable knowledge base with a knowledge graph of entities and relationships.

## Personal Context

If `~/.mneia/claude-context.md` exists, read it first — it contains personalized facts about
the user's life, people, projects, and recent activity that make your answers more relevant.

```bash
cat ~/.mneia/claude-context.md 2>/dev/null
```

## Commands You Can Run

### Ask a question about the user's knowledge
```bash
mneia ask "QUESTION"
```
Use this for any question about the user's notes, people they know, meetings, code, documents,
emails, or calendar. The full RAG pipeline runs: BM25 + vector search + knowledge graph.

### Check system status
```bash
mneia status
```
Shows daemon state, agent activity, connector sync times, document counts, and queue depth.

### Sync all connectors
```bash
mneia sync
```
Pulls new data from all enabled connectors (calendar, email, GitHub, Obsidian, etc.).
Use when the user says their data seems stale or asks to refresh.

### Search memory directly
```bash
mneia memory search "QUERY"
mneia memory search "QUERY" --source obsidian
mneia memory search "QUERY" --limit 10
```

### Explore the knowledge graph
```bash
mneia graph stats
mneia graph search "NAME"
```

### Context files
```bash
mneia context list
mneia context generate
mneia context generate-claude          # refreshes ~/.mneia/claude-context.md
```

### Connector management
```bash
mneia connector list
mneia connector sync CONNECTOR_NAME
mneia connector status CONNECTOR_NAME
```

### Configuration
```bash
mneia config show
mneia config get KEY
mneia config set KEY VALUE
```

### Logs (for debugging)
```bash
mneia logs --lines 50
```

## How to Help

### Answering knowledge questions
1. Run `mneia ask "question"` — prefer this over individual searches
2. Present the answer naturally; include source titles when citing specifics
3. If the answer seems incomplete, try `mneia memory search` with different terms

### Setup wizard (when user wants to install or configure mneia)
Walk through these steps:
1. Check if installed: `mneia version 2>/dev/null || echo "not installed"`
2. If not installed: `pip install mneia`
3. Run setup: `mneia config setup` (follow interactive prompts)
4. Add first connector: `mneia connector setup obsidian` or whichever the user has
5. Run first sync: `mneia sync`
6. Generate context: `mneia context generate-claude`
7. Confirm: `mneia status`

### Status check
Run `mneia status` and summarise:
- Whether the daemon is running
- Last sync time for each connector
- Total documents and entities indexed
- Any errors or warnings

### Refreshing context
Run `mneia context generate-claude` to update `~/.mneia/claude-context.md` with the latest
summary of the user's knowledge base. Suggest doing this after a sync.

## Tips

- For people questions ("who is X", "tell me about Y"), always use `mneia ask` — it combines
  the knowledge graph (entity properties) with document search for accurate answers.
- For time-based questions, mneia understands natural language dates — just pass them directly.
- If mneia returns no results, try `mneia sync` first then retry the question.
- The `--json` flag is available on most commands for structured output if needed.
