# mneia Setup Guide

## Fresh install

```bash
pip install mneia
mneia config setup        # choose LLM provider, model, API key
mneia connector setup obsidian   # or whichever connector(s) you have
mneia sync                # first ingest
mneia context generate-claude    # write Claude Code context file
mneia status              # confirm everything is working
```

## LLM Providers

mneia works with any of these — set during `mneia config setup`:

| Provider | Config key | Notes |
|----------|-----------|-------|
| Ollama (local) | `llm.provider = ollama` | Free, private, needs Ollama running |
| Anthropic | `llm.provider = anthropic` | Best quality, needs API key |
| OpenAI | `llm.provider = openai` | Good quality, needs API key |
| Google | `llm.provider = google` | Needs API key |

```bash
mneia config set llm.provider anthropic
mneia config set llm.model claude-sonnet-4-6
# API key stored securely in system keychain
```

## Adding a connector

```bash
mneia connector setup CONNECTOR_NAME
```

mneia will guide you through authentication. For most connectors:
- **Obsidian**: provide the vault path
- **GitHub**: provide a personal access token (or detected from `gh` CLI)
- **Google (calendar/gmail/drive)**: OAuth2 browser flow
- **Granola**: provide app data path (auto-detected on macOS)

## Syncing

Sync runs automatically when the daemon is running (`mneia start`).
Manual sync: `mneia sync` or `mneia connector sync NAME`

## Keeping Claude Code context fresh

After a sync, refresh Claude Code's view of your knowledge base:
```bash
mneia context generate-claude
```
This writes `~/.mneia/claude-context.md` — the mneia skill reads this automatically.

## Troubleshooting

```bash
mneia status              # check daemon and connector health
mneia logs --lines 100    # check for errors
mneia connector status NAME   # check a specific connector
```
