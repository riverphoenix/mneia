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

### Ollama (Default)

```bash
brew install ollama
ollama pull phi3:mini
ollama pull nomic-embed-text
```

### Anthropic

```bash
mneia config set llm.provider anthropic
mneia config set llm.anthropic_api_key sk-ant-...
```

### OpenAI

```bash
mneia config set llm.provider openai
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

## General Settings

| Key | Default | Description |
|-----|---------|-------------|
| `context_output_dir` | `~/.mneia/context` | Where to write generated .md files |

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
| `~/.mneia/memory.db` | Document and entity store |
| `~/.mneia/graph.db` | Knowledge graph |
| `~/.mneia/context/` | Generated context files |
| `~/.mneia/logs/` | Daemon logs |
| `~/.mneia/mneia.sock` | Unix socket for IPC |
| `~/.mneia/history.txt` | Interactive mode history |
| `~/.mneia/templates/` | User template overrides |
