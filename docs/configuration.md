# Configuration

mneia stores configuration in `~/.mneia/config.json` using Pydantic models.

## Setup Wizard

```bash
mneia config setup
```

The wizard walks through:
1. LLM provider selection (ollama, anthropic, openai)
2. Model configuration
3. Context output directory

## LLM Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `llm.provider` | `ollama` | LLM provider |
| `llm.model` | `phi3:mini` | Model for extraction/generation |
| `llm.embedding_model` | `nomic-embed-text` | Model for embeddings |
| `llm.ollama_base_url` | `http://localhost:11434` | Ollama API URL |
| `llm.anthropic_api_key` | (none) | Anthropic API key |
| `llm.openai_api_key` | (none) | OpenAI API key |
| `llm.temperature` | `0.1` | Generation temperature |
| `llm.max_tokens` | `2048` | Maximum tokens per generation |

### Ollama (Default)

```bash
brew install ollama
ollama pull phi3:mini
ollama pull nomic-embed-text
```

### Anthropic

```bash
mneia config set llm.provider anthropic
mneia config set llm.model claude-sonnet-4-6
mneia config set llm.anthropic_api_key sk-ant-...
```

### OpenAI

```bash
mneia config set llm.provider openai
mneia config set llm.model gpt-4o-mini
mneia config set llm.openai_api_key sk-...
```

## Connector Configuration

Each connector has its own configuration block:

| Key | Description |
|-----|-------------|
| `connectors.<name>.enabled` | Whether the connector is active |
| `connectors.<name>.poll_interval_seconds` | How often to poll (default varies) |
| `connectors.<name>.last_checkpoint` | Last sync timestamp |
| `connectors.<name>.settings` | Connector-specific settings (e.g., vault path) |

## Context Generation

| Key | Default | Description |
|-----|---------|-------------|
| `context_output_dir` | `~/.mneia/context` | Where to write generated .md files |
| `auto_generate_context` | `true` | Auto-regenerate context when knowledge changes |
| `context_regenerate_interval_minutes` | `30` | How often to check for changes |
| `context_min_changes_for_regen` | `5` | Minimum new documents before regenerating |

## Enrichment & Web Scraping

| Key | Default | Description |
|-----|---------|-------------|
| `enrichment_scrape_enabled` | `false` | Enable web scraping for entity enrichment |
| `enrichment_max_scrape_pages` | `5` | Maximum pages to scrape per enrichment cycle |
| `enrichment_scrape_delay_seconds` | `2.0` | Delay between scrape requests (rate limiting) |

## Safety & Permissions

| Key | Default | Description |
|-----|---------|-------------|
| `safety.auto_approve_low_risk` | `true` | Auto-approve LOW risk operations |
| `safety.approval_ttl_hours` | `24` | How long approvals last before expiring |
| `safety.blocked_operations` | `[]` | Operations that are always blocked |

## Autonomous Agent

| Key | Default | Description |
|-----|---------|-------------|
| `autonomous_enabled` | `true` | Enable the autonomous intelligence agent |
| `autonomous_interval_minutes` | `30` | How often the agent runs analysis |
| `autonomous_max_actions` | `5` | Maximum actions per analysis cycle |
| `autonomous_creativity_temperature` | `0.7` | Temperature for autonomous LLM calls |

## General Settings

| Key | Default | Description |
|-----|---------|-------------|
| `max_memory_mb` | `2048` | Maximum memory usage |
| `log_level` | `info` | Logging level (debug, info, warn, error) |

## Commands

```bash
mneia config show          # Display current config as JSON
mneia config set <k> <v>   # Set a dot-separated key
mneia config reset         # Reset to defaults
```

## File Locations

| Path | Purpose |
|------|---------|
| `~/.mneia/config.json` | Configuration file |
| `~/.mneia/data/mneia.db` | Document and entity store (SQLite + FTS5) |
| `~/.mneia/data/graph.db` | Knowledge graph (SQLite + NetworkX) |
| `~/.mneia/data/persistent_memory.db` | Cross-session persistent memory |
| `~/.mneia/data/chroma/` | Vector embeddings (ChromaDB) |
| `~/.mneia/context/` | Generated context files |
| `~/.mneia/logs/` | Daemon logs |
| `~/.mneia/mneia.sock` | Unix socket for IPC |
| `~/.mneia/history.txt` | Interactive mode history |
| `~/.mneia/templates/` | User template overrides |
