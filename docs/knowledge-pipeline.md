# Knowledge Pipeline

mneia processes your data through a 5-stage pipeline that transforms raw documents into structured knowledge and context files.

## Stage 1: Ingest

**Module:** `mneia.pipeline.ingest`

ListenerAgents poll connectors at configured intervals and fetch new documents.

- Raw documents normalized: encoding to UTF-8, timestamps to UTC
- Stored in SQLite `documents` table with FTS5 full-text search index
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

Entities are stored in SQLite `entities` table. Entity node IDs are generated as `{type}:{slugified-name}` (e.g., `person:alice-smith`).

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

## Automatic Pipeline

When the daemon is running:
1. ListenerAgents continuously ingest new documents
2. WorkerAgent processes unprocessed documents every 30 seconds
3. MetaAgent merges duplicate entities every 60 seconds
4. Context files can be regenerated on demand

## Data Storage

All data is stored locally in `~/.mneia/`:

| File | Contents |
|------|----------|
| `memory.db` | Documents, entities, associations (SQLite + FTS5) |
| `graph.db` | Knowledge graph nodes and edges (SQLite) |
| `config.json` | Configuration (Pydantic model) |
| `context/` | Generated `.md` files |
| `logs/` | Daemon logs |
| `history.txt` | Interactive mode command history |
