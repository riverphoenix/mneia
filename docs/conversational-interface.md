# Conversational Interface

mneia provides a RAG-powered conversational interface for querying your personal knowledge base, with hybrid search and cross-session memory.

## Single Query

```bash
mneia ask "Who did I meet with last week?"
mneia ask "What decisions were made about Project X?" --source obsidian
```

The `ask` command performs a single query with full RAG:
1. Searches your document store using hybrid search (FTS5 + vector similarity)
2. Queries the knowledge graph for matching entities and relationships
3. Injects personal context from persistent memory (preferences, patterns)
4. Sends context + question to the LLM
5. Returns the answer with source citations and follow-up suggestions

## Multi-Turn Chat

```bash
mneia chat
```

Enters an interactive multi-turn conversation mode:
- Conversation history is preserved across turns
- The LLM has context from previous questions and answers
- Cross-session memory remembers your preferences over time
- Type `clear` to reset the conversation
- Type `exit` to return

In interactive mode: `/chat`

## How RAG Works

### Hybrid Search

For each question, mneia searches your knowledge using two complementary methods:

1. **Full-Text Search (FTS5)** — SQLite FTS5 finds documents matching keywords in your query. Handles exact terms, phrases, and boolean operators.

2. **Vector Search (ChromaDB)** — Embeds the query using nomic-embed-text (or OpenAI text-embedding-3-small) and finds semantically similar documents, even when exact keywords don't match.

Results from both are merged and deduplicated, giving you the best of keyword and semantic search.

### Knowledge Graph Context

Entities matching keywords in the question are looked up in the graph. Their descriptions and immediate relationships are included as structured context. This provides relational information that pure document search might miss.

### Personal Context (Persistent Memory)

When a `SessionManager` is active, mneia injects personal context into the system prompt:
- **Preferences** — learned over time (e.g., "prefers concise answers")
- **Patterns** — recurring topics and interests
- **Session history** — summaries of previous conversations

This makes responses increasingly personalized across sessions.

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

The LLM is prompted to suggest 2-3 follow-up questions at the end of each response.

## Session Memory

When running in interactive mode, mneia tracks your conversations:

1. **During the session** — interactions are recorded (role + content)
2. **On exit** — the LLM summarizes the session in 2-3 sentences
3. **Next session** — summaries and learned patterns are injected as context

Memory entries have a **decay weight** that fades over time unless reinforced by access. This naturally prioritizes recent and frequently-referenced knowledge.

## LLM Providers

The conversational interface works with any configured LLM provider:

| Provider | Model | Quality | Speed |
|----------|-------|---------|-------|
| Ollama | phi3:mini | Good | Fast (local) |
| Ollama | mistral:7b | Better | Moderate (local) |
| Anthropic | claude-sonnet-4-6 | Best | Fast (API) |
| OpenAI | gpt-4o-mini | Better | Fast (API) |

Configure via `mneia config setup` or `mneia config set llm.provider <provider>`.

## Circuit Breaker

The LLM client includes a circuit breaker that opens after 5 consecutive failures and pauses requests for 5 minutes before retrying. This prevents cascading failures when the LLM service is down.

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

## MCP Integration

The conversational interface is also available as an MCP tool (`mneia_ask`), allowing AI tools like Claude Code to query your knowledge directly. See [MCP Integration](mcp-integration.md).
