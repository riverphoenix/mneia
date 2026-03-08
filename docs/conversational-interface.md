# Conversational Interface

mneia provides a RAG-powered conversational interface for querying your personal knowledge base.

## Single Query

```bash
mneia ask "Who did I meet with last week?"
mneia ask "What decisions were made about Project X?" --source obsidian
```

The `ask` command performs a single query with full RAG:
1. Searches your document store for relevant context
2. Queries the knowledge graph for matching entities and relationships
3. Sends context + question to the LLM
4. Returns the answer with source citations and follow-up suggestions

## Multi-Turn Chat

```bash
mneia chat
```

Enters an interactive multi-turn conversation mode:
- Conversation history is preserved across turns
- The LLM has context from previous questions and answers
- Type `clear` to reset the conversation
- Type `exit` to return

In interactive mode: `/chat`

## How RAG Works

### Context Building

For each question, mneia builds context from two sources:

1. **Document Search** — Full-text search (SQLite FTS5) finds the most relevant documents based on keyword matching. Up to 5 documents are included, with content truncated to fit within context limits.

2. **Knowledge Graph** — Entities matching keywords in the question are looked up in the graph. Their descriptions and immediate relationships are included as structured context.

### Context Window Management

Total context is capped at ~6000 characters to work well with smaller local models (Phi-3 Mini, Mistral 7B). Graph context is prioritized, then documents fill the remaining space.

### Multi-Turn History

In chat mode, previous turns are included in the prompt (up to 10 turns). Each turn is summarized to 500 characters to keep the context window manageable.

### Source Citations

Every response includes citations listing which documents were used as context:
```
Sources:
  - Meeting Notes (obsidian)
  - Project Alpha (obsidian)
  - Team Standup (google-calendar)
```

### Follow-Up Suggestions

The LLM is prompted to suggest 2-3 follow-up questions at the end of each response. These appear as clickable suggestions in the interactive mode.

## LLM Providers

The conversational interface works with any configured LLM provider:

| Provider | Model | Quality | Speed |
|----------|-------|---------|-------|
| Ollama | phi3:mini | Good | Fast (local) |
| Ollama | mistral:7b | Better | Moderate (local) |
| Anthropic | claude-sonnet | Best | Fast (API) |
| OpenAI | gpt-4o-mini | Better | Fast (API) |

Configure via `mneia config setup` or `mneia config set llm.provider <provider>`.

## Interactive Mode Integration

In interactive mode (`mneia` with no args), natural language queries are automatically routed through the conversation engine:

```
mneia › What meetings do I have this week?
  Found 3 relevant documents

  ✦ Connecting the dots...

  Based on your calendar events, you have...

  Sources:
    - Team Standup (google-calendar)
    - 1:1 with Alice (google-calendar)
```

The conversation engine is also used by the `/ask` command and feeds into the LLM command routing (where the LLM can suggest and auto-execute slash commands).
