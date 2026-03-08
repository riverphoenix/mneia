# Daemon & Agents

mneia runs as a daemon process with multiple async agents coordinated by an AgentManager.

## Starting the Daemon

```bash
mneia start           # Foreground (Ctrl+C to stop)
mneia start -d        # Background (detached)
mneia start -c obs    # Only specific connectors
```

In interactive mode: `/start`

## Stopping the Daemon

```bash
mneia stop
```

In interactive mode: `/stop`

The daemon shuts down gracefully: stops all agents, cancels tasks, closes the IPC socket, and cleans up.

## Agent Types

### ListenerAgent

One per enabled connector. Operates in poll mode (configurable interval) or watch mode (real-time file detection via `watchfiles`).

- Configurable poll interval per connector
- Watch mode for filesystem connectors (Obsidian)
- Stops cleanly via `asyncio.Event`
- Reports state: `running`, `stopped`, `error`

### WorkerAgent

Shared worker that processes the extraction pipeline. Polls for unprocessed documents every 30 seconds and runs entity extraction via LLM. Also generates vector embeddings for new documents and entities.

### MetaAgent

Orchestrator agent that:
- Monitors health of all other agents every 60 seconds
- Logs warnings for agents in ERROR state
- Runs entity deduplication (merge_duplicate_entities) on each cycle

### EnrichmentAgent

Enhances sparse entities in the knowledge graph by searching the web:
- Scans for entities with missing or short descriptions
- Performs DuckDuckGo searches and optionally scrapes pages for richer context
- Updates entity properties with LLM-generated descriptions
- Runs on a 5-minute cycle, up to 5 entities per cycle
- See [Enrichment](enrichment.md) for details

### WebResearchAgent

On-demand deep research agent for a given topic:
- Searches DuckDuckGo for URLs related to a topic
- Scrapes pages using the shared web scraper (crawl4ai fallback to httpx)
- Synthesizes a structured research summary via LLM
- Stores the result as a `RawDocument` with source metadata

### AutonomousAgent

Autonomous intelligence agent that identifies gaps and surfaces insights:
- Runs on a configurable interval (default: 30 minutes)
- Uses `ReasoningEngine` to analyze graph state with LLM
- Identifies sparse entities, isolated nodes, missing connections
- Executes three action types:
  - **Enrich** — fill missing entity descriptions via LLM
  - **Connect** — propose new relationships between entities
  - **Insight** — generate synthetic insight documents
- Confidence threshold (0.6) filters low-quality proposals
- Configurable via `autonomous_*` settings

### ContextWatcher

Background task (not a full agent) that auto-regenerates context `.md` files:
- Polls for new documents at configured interval
- Triggers regeneration when enough new documents are detected
- Configurable threshold via `context_min_changes_for_regen`

## Auto-Restart & Resilience

Agents that crash are automatically restarted with exponential backoff:
- Up to 3 restart attempts per agent
- Backoff starts at 5 seconds, doubles each retry (max 60 seconds)
- After max restarts, the agent enters ERROR state
- MetaAgent monitors and logs ERROR state agents

The LLM client includes a **circuit breaker** that opens after 5 consecutive failures, pausing for 5 minutes before retrying. This prevents agents from hammering a down LLM service.

## Agent Management

### Per-Agent Control

You can start/stop individual connector agents without restarting the daemon:

```bash
mneia connector start-agent obsidian
mneia connector stop-agent obsidian
mneia connector agents
```

Interactive mode:
```
/connector-start obsidian
/connector-stop obsidian
/agents
```

### IPC Protocol

The daemon listens on a Unix domain socket at `~/.mneia/mneia.sock`. Commands are JSON messages:

| Action | Description |
|--------|-------------|
| `stop` | Stop the daemon |
| `status` | Get daemon status and agent states |
| `list_agents` | List all agents with states |
| `start_agent` | Start a specific connector agent |
| `stop_agent` | Stop a specific agent |

### Agent States

| State | Meaning |
|-------|---------|
| `idle` | Created but not yet started |
| `running` | Actively processing |
| `paused` | Temporarily paused |
| `stopped` | Cleanly shut down |
| `error` | Crashed (logged, monitored by MetaAgent) |

## Metrics

mneia includes an in-process `MetricsCollector` singleton for observability:

- **Counters** — docs processed, entities extracted, LLM calls, errors
- **Gauges** — memory usage, active agents
- **Timers** — LLM latency, pipeline stage durations

Access via `MetricsCollector.get().snapshot()` for a point-in-time view.

## TUI Dashboard

```bash
mneia agents
```

Launches a Textual-based terminal dashboard with four panels:

1. **Daemon Status** — Running/stopped indicator
2. **Agents** — Live agent states with status icons (all 6 agent types)
3. **Knowledge Base** — Document, entity, and association counts
4. **Knowledge Graph** — Entity and relationship counts by type

Auto-refreshes every 5 seconds. Keybindings: `q` quit, `r` refresh.

## Logs

```bash
mneia logs                  # Last 50 lines, info level
mneia logs -l debug         # Debug level
mneia logs -f               # Follow (tail -f style)
mneia logs -n 100           # Last 100 lines
```

Interactive mode: `/logs [level]`

Log file location: `~/.mneia/logs/daemon.log`
