# mneia Command Reference

## Top-level
| Command | What it does |
|---------|-------------|
| `mneia version` | Show installed version |
| `mneia status` | Daemon state, agents, connector sync times, doc counts |
| `mneia start` | Start the background knowledge daemon |
| `mneia stop` | Stop the daemon |
| `mneia sync` | Pull new data from all enabled connectors |
| `mneia ask "Q"` | Ask a question (full RAG + knowledge graph) |
| `mneia chat` | Interactive multi-turn chat (terminal) |
| `mneia logs` | Tail daemon logs |
| `mneia update` | Check for and install updates |

## `mneia config`
| Command | What it does |
|---------|-------------|
| `mneia config show` | Print current config |
| `mneia config get KEY` | Get a single config value (e.g. `llm.provider`) |
| `mneia config set KEY VALUE` | Set a config value |
| `mneia config setup` | Interactive setup wizard |

## `mneia connector`
| Command | What it does |
|---------|-------------|
| `mneia connector list` | List connectors and enabled/disabled state |
| `mneia connector setup NAME` | Interactive auth + config for a connector |
| `mneia connector sync NAME` | Force sync a specific connector |
| `mneia connector status NAME` | Show sync history and error log |
| `mneia connector enable NAME` | Enable a connector |
| `mneia connector disable NAME` | Disable a connector |

## `mneia memory`
| Command | What it does |
|---------|-------------|
| `mneia memory search "Q"` | BM25 full-text search across all indexed docs |
| `mneia memory search "Q" --source SRC` | Search within a specific source |
| `mneia memory search "Q" --limit N` | Cap results |
| `mneia memory stats` | Document counts by source |
| `mneia memory recent` | Most recently ingested documents |

## `mneia graph`
| Command | What it does |
|---------|-------------|
| `mneia graph stats` | Node/edge counts, entity type breakdown |
| `mneia graph search "NAME"` | Find entities by name |
| `mneia graph show ID` | Show entity details and relationships |

## `mneia context`
| Command | What it does |
|---------|-------------|
| `mneia context list` | List generated context files |
| `mneia context generate` | Regenerate all context files |
| `mneia context generate-claude` | Write `~/.mneia/claude-context.md` for Claude Code |
| `mneia context show FILE` | Print a context file |

## `mneia marketplace`
| Command | What it does |
|---------|-------------|
| `mneia marketplace list` | Browse available community connectors |
| `mneia marketplace install NAME` | Install a connector package |
| `mneia marketplace info NAME` | Show connector details |

## Available Connectors
| Name | Data |
|------|------|
| `obsidian` | Personal Obsidian vault (markdown notes) |
| `google-calendar` | Google Calendar events |
| `gmail` | Gmail inbox and sent mail |
| `google-drive` | Google Docs, Sheets, Slides |
| `granola` | AI meeting notes and transcripts |
| `github` | Repos, commits, PRs, issues |
| `apple-notes` | Apple Notes |
| `chrome-history` | Browser history |
| `local-folders` | Local files and PDFs |
| `live-audio` | Real-time audio transcription |
