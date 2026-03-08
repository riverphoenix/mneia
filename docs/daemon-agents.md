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

One per enabled connector. Polls the data source at the configured interval and ingests new documents into the memory store.

- Configurable poll interval per connector
- Stops cleanly via `asyncio.Event`
- Reports state: `running`, `stopped`, `error`

### WorkerAgent

Shared worker that processes the extraction pipeline. Polls for unprocessed documents every 30 seconds and runs entity extraction via LLM.

### MetaAgent

Orchestrator agent that:
- Monitors health of all other agents every 60 seconds
- Logs warnings for agents in ERROR state
- Runs entity deduplication (merge_duplicate_entities) on each cycle

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
| `stopped` | Cleanly shut down |
| `error` | Crashed (logged, monitored by MetaAgent) |

## TUI Dashboard

```bash
mneia agents
```

Launches a Textual-based terminal dashboard with four panels:

1. **Daemon Status** — Running/stopped indicator
2. **Agents** — Live agent states with status icons
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
