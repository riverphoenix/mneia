# Changelog

All notable changes to mneia are documented here.

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
