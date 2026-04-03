# Changelog

All notable changes to mneia are documented here.

## [0.3.5] — 2026-04-03

### Changed
- README updated with `/improve`, `/visualize`, `/sync all`, and background auto-cycle sections
- `docs/conversational-interface.md` updated with background cycle, `/improve`, and `/visualize` documentation

---

## [0.3.4] — 2026-04-03

### Added

**`/sync all`**
- `/sync all` (or `/sync` with no argument) syncs all enabled connectors sequentially with per-connector status output
- Natural language intent detection: "sync all", "sync everything", "sync all connectors" triggers `/sync all`

**`/improve` — interactive knowledge improvement (RLHF-style)**
- New `src/mneia/commands/improve.py` module
- Walks through all entities ordered by importance (mention_count + connections)
- Per-entity actions: keep (validate), update description (free text), delete
- Per-relationship actions: mark correct, change relation type, remove
- Changes applied immediately to both the in-memory NetworkX graph and SQLite
- Corrections saved to `~/.mneia/preferences.json` for future LLM extraction runs
- Session ends with summary (entities reviewed, changes applied)
- No new dependencies — uses `rich` (already required) + `input()`

**`/visualize` — interactive knowledge graph explorer**
- New `src/mneia/commands/visualize.py` module
- Menu-driven navigation: graph overview, entity browser by type, entity explorer, search
- Entity browser shows paginated table with type, connections, mentions, description
- Entity explorer shows a full Rich tree of relationships up to depth 2 with navigation
- Graph overview shows entity type distribution with ASCII bar chart + top mentioned entities
- Search by entity name substring, pick result to explore
- Navigation stack: drill into any connected entity and backtrack
- No new dependencies — uses `rich.tree.Tree`, `rich.table.Table`, `rich.panel.Panel`

**Background auto-cycle (every 10 minutes)**
- REPL starts a daemon background thread on startup via `_start_background_cycle()`
- Every 10 minutes (after first 10-min delay): syncs all enabled connectors, then runs entity extraction on new documents, then regenerates context files
- Only activates when the background daemon is NOT running (daemon handles the same cycle via its own agents when running)
- Silent: errors are debug-logged, never printed to the REPL prompt

### Updated docs
- `docs/cli-reference.md`: `/sync all`, `/improve`, `/visualize` command references

---

## [0.3.3] — 2026-04-03

### Added

**Claude Code skill**
- `mneia install-skill` — copies skill to `~/.agents/skills/mneia/`, generates `~/.mneia/claude-context.md`, and adds context pointer to `~/.claude/CLAUDE.md`
- `mneia context generate-claude` — writes personalized `~/.mneia/claude-context.md` with per-source document counts, entity types, people from knowledge graph, and recent activity
- `scripts/install-claude-code-skill.sh` — standalone install script (no Python required)
- Claude Code plugin marketplace support: `skills/claude-code/mneia/` skill with SKILL.md and reference docs; `plugins/mneia-plugin/` for `/plugin marketplace add riverphoenix/mneia`
- `.claude-plugin/marketplace.json` and `plugins/mneia-plugin/.claude-plugin/plugin.json` marketplace manifests

**Smarter RAG**
- `SOURCE_DESCRIPTIONS` — rich natural-language descriptions for each source used in LLM routing prompt; routing now correctly targets obsidian for people/personal queries, granola + calendar for meetings
- Whole-word regex entity matching in `_get_graph_context` with scoring (exact > whole-word > partial > substring); stops confusing partial name matches
- Entity-grounded extra searches: matched entity names used as additional BM25 queries, re-merged via RRF
- ENTITY ACCURACY system prompt section instructs LLM to treat graph entity properties as authoritative ground truth
- People/family keyword expansion in obsidian routing (`who is`, `child`, `daughter`, `son`, `school`, etc.)

**UX**
- Drain-first-chunk pattern: routing/search step indicators now print before Rich `Live` streaming starts — no more invisible progress messages
- Sources display grouped and summarised (`3 from obsidian, 2 from granola`) with max 3 representative titles instead of listing all 100+ citations
- `THINKING_PHRASES` expanded to 20 entries; topic-aware phrases for meetings, calendar, email, GitHub, code, etc.
- Step indicators use rotating emoji (`⟳ ⚡ 🔍 🧠 💡 ↻ ◉ ▸ ✦`)
- `_get_thinking_phrase(question)` selects topic-matched phrase first

**Reliability**
- `ConnectorConfig.skipped_resources: list[str]` — persisted list of 404/410 resources; injected into connectors before each sync so deleted repos/resources are permanently skipped without error
- GitHub connector: `_fetch_issues` / `_fetch_pulls` detect 404/410, log warning, append repo to `_skipped_resources`; `skipped_resources` saved back to config after each sync run

### Fixed
- Integration test `test_memory_search_no_results` no longer asserts literal "No results" string against a live store

---

## [0.3.0] — 2026-04-01

### Added

**Smart RAG pipeline (conversation.py)**
- ReAct reasoning loop: LLM routes queries, generates sub-queries, evaluates context sufficiency
- RAG Fusion (Reciprocal Rank Fusion): merges results from multiple independent search passes using RRF (k=60)
- HyDE (Hypothetical Document Embeddings): generates a hypothetical answer with LLM, embeds that for semantic search
- Temporal reasoning: natural language time expressions parsed into `(since, until)` UTC range filters
- Sentence-window retrieval: returns best-matching sentence context window instead of raw content slice
- Source routing: keyword detection + LLM routing to target the right connectors per query
- Clarifying questions: LLM asks for clarification when query intent is genuinely ambiguous
- `MAX_SEARCH_LIMIT=200`, `MAX_CONTEXT_CHARS=80_000`

**New pipeline modules**
- `pipeline/rag_fusion.py` — `reciprocal_rank_fusion()` implementation (Cormack et al. 2009)
- `pipeline/temporal.py` — `extract_temporal_range()` parsing today/yesterday/last week/Q1/etc.
- `pipeline/coref.py` — `resolve_coreferences()` using fastcoref (optional)
- `pipeline/raptor.py` — `build_raptor_tree()` TF-IDF + agglomerative clustering + LLM summarization

**Knowledge pipeline**
- Co-reference resolution wired into `pipeline/extract.py` before NER extraction
- RAPTOR cycle wired into `KnowledgeAgent` (runs every 6th cycle, ~30 min)
- RAPTOR cluster summaries stored as `source="raptor"` documents, searchable via FTS5

**MemoryStore**
- `search()` now accepts `since: datetime | None` and `until: datetime | None` for temporal filtering

**Optional extras**
- `intelligence` extra now includes `fastcoref>=0.1` and `scikit-learn>=1.3`

### Changed
- Background context refresh interval: 30 min → 10 min (triggered by WorkerAgent events)
- WorkerAgent and ContextWatcher share an `asyncio.Event` for immediate wakeup on new docs
- `_merge_and_diversify` refactored to accept a single pre-merged list (RRF handles the merge)

## [0.2.2] — 2026-03

### Added
- NER pipeline (GLiNER, optional)
- Instructor structured extraction (optional)
- Cross-encoder reranking pipeline (optional)
- Vector search with ChromaDB + nomic-embed-text (optional)
- HyDE vector search in ConversationEngine
- Knowledge graph temporal metadata
- EmbeddedDaemon for in-process agent management

### Fixed
- `/chat` asyncio conflict in interactive REPL (threading fix)

## [0.2.0] — 2026-02

### Added
- 14 connectors: Google Calendar, Gmail, Google Drive, Obsidian, Apple Notes, GitHub, Chrome History, Granola, Local Folders, and more
- Multi-agent daemon: ListenerAgent, WorkerAgent, MetaAgent, KnowledgeAgent, AutonomousAgent
- MCP server for AI tool integration
- Context generation (`.md` files for Claude Code / Cursor)
- Session memory in conversational REPL
- GraphRAG and CognitiveMemory optional integrations

## [0.1.0] — 2026-01

Initial release.
- SQLite + FTS5 memory store
- Knowledge graph (NetworkX)
- Basic entity extraction via LLM JSON prompts
- Interactive REPL (`/search`, `/ask`, `/graph`, etc.)
