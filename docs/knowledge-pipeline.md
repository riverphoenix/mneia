# Knowledge Pipeline

mneia processes your data through a 5-stage pipeline that transforms raw documents into structured knowledge and context files, backed by hybrid search (FTS5 + vector embeddings).

## Stage 1: Ingest

**Module:** `mneia.pipeline.ingest`

ListenerAgents poll or watch connectors and fetch new documents.

- Raw documents normalized: encoding to UTF-8, timestamps to UTC
- Stored in SQLite `documents` table with FTS5 full-text search index
- Vector embeddings generated via nomic-embed-text (Ollama) or text-embedding-3-small (OpenAI) and stored in ChromaDB
- Deduplication by `(source, source_id)` — existing documents are updated, not duplicated
- Checkpoint timestamp saved per connector for incremental sync

**CLI:** `mneia connector sync <name>`
**Interactive:** `/sync <name>`

## Stage 2: Extract

**Module:** `mneia.pipeline.extract`

WorkerAgent picks unprocessed documents and uses LLM to extract structured entities.

**Extracted entity types:**
- People (name, role, organization)
- Projects (name, description, status)
- Topics (name, description)
- Decisions (what was decided, context)
- Beliefs (opinions, preferences)

**Extracted relationships:**
- Source entity → Target entity with relation type (e.g., "Alice" → "Falcon" with relation "manages")

Entities are stored in SQLite `entities` table. Entity node IDs are generated as `{type}:{slugified-name}` (e.g., `person:alice-smith`). Entity name + description are also embedded and stored in a separate ChromaDB collection for semantic entity search.

**CLI:** `mneia extract [--limit 50]`
**Interactive:** `/extract [limit]`

## Stage 3: Associate

**Module:** `mneia.pipeline.associate`

Cross-references entities across sources to merge duplicates.

**Matching strategy:**
1. Exact name match → confidence 1.0
2. Partial match (one name contains the other) → confidence 0.7
3. No match → entities kept separate

**Deduplication:**
- Finds nodes with the same name across different types
- Merges edges to the canonical node (prefers `person:` type)
- Removes duplicate nodes

Runs automatically in the MetaAgent every 60 seconds.

## Stage 4: Summarize

**Module:** `mneia.pipeline.summarize`

Generates rolling summaries using LLM:

- **Overview summary** — General knowledge base overview
- **Per-person summaries** — Interaction history, role, context
- **Per-topic summaries** — What's known about each topic

Summaries are versioned in SQLite `summaries` table.

## Stage 5: Generate

**Module:** `mneia.pipeline.generate`

Renders Jinja2 templates into `.md` context files:

| File | Content |
|------|---------|
| `CLAUDE.md` | Overview + key people + active projects |
| `people.md` | All known people with descriptions and relationships |
| `projects.md` | All known projects with descriptions |
| `decisions.md` | Extracted decisions |
| `beliefs.md` | Extracted beliefs and preferences |

**Output directory:** `~/.mneia/context/` (configurable)

**Template override:** Place custom templates in `~/.mneia/templates/` to override built-in templates.

**CLI:** `mneia context generate`
**Interactive:** `/context`

## Auto-Regeneration

When the daemon is running with `auto_generate_context: true`, a **ContextWatcher** monitors for new documents:

1. Polls the document store at the configured interval (`context_regenerate_interval_minutes`, default: 30)
2. When new documents exceed the threshold (`context_min_changes_for_regen`, default: 5), triggers regeneration
3. Context files are regenerated using the full pipeline (graph + LLM)
4. Timestamp is recorded to avoid redundant regeneration

## Automatic Pipeline

When the daemon is running:
1. ListenerAgents continuously ingest new documents (poll or watch mode)
2. WorkerAgent processes unprocessed documents every 30 seconds
3. Vector embeddings are generated for new documents and entities
4. MetaAgent merges duplicate entities every 60 seconds
5. AutonomousAgent identifies gaps and generates insights every 30 minutes
6. ContextWatcher auto-regenerates `.md` files when enough changes accumulate

## Search Architecture

mneia uses **hybrid search** combining:

1. **Full-Text Search (FTS5)** — Fast keyword matching with SQLite's built-in FTS5 engine. Handles exact terms, phrases, and boolean operators. Special characters are automatically sanitized.

2. **Vector Search (ChromaDB)** — Semantic similarity using embeddings. Finds related documents even when exact keywords don't match. Uses nomic-embed-text (768 dimensions) via Ollama, or OpenAI text-embedding-3-small as fallback.

3. **Knowledge Graph** — Entity and relationship lookups for structured context.

Results from FTS5 and vector search are merged by document ID, deduplicated, and limited to the top 10 results.

**Graceful degradation:** If ChromaDB is not installed or the embedding service is unavailable, mneia falls back to FTS5-only search with no errors.

## Data Storage

All data is stored locally in `~/.mneia/`:

| Path | Contents |
|------|----------|
| `data/mneia.db` | Documents, entities, associations (SQLite + FTS5) |
| `data/graph.db` | Knowledge graph nodes and edges (SQLite + NetworkX) |
| `data/persistent_memory.db` | Cross-session memory with decay weights |
| `data/chroma/` | Vector embeddings (ChromaDB, optional) |
| `config.json` | Configuration (Pydantic model) |
| `context/` | Generated `.md` files |
| `logs/` | Daemon logs |
| `history.txt` | Interactive mode command history |
