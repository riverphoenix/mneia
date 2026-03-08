# Connectors

Connectors are the data sources that mneia reads from to build your personal knowledge base. All connectors are **read-only** — they never modify your data.

## Available Connectors

### Obsidian

Reads markdown files from an Obsidian vault.

**Auth:** Local filesystem access
**Mode:** Watch (real-time file change detection)
**Setup:**
```bash
mneia connector enable obsidian
mneia connector setup obsidian   # Prompts for vault path
mneia connector sync obsidian    # Ingest documents
```

**Features:**
- Reads all `.md` files recursively
- Parses YAML frontmatter (title, tags, date)
- Extracts headings structure
- Detects `#tags` and `[[wikilinks]]`
- Excludes `.obsidian/` and other hidden directories
- Supports configurable exclude folders
- Real-time file watching via `watchfiles` when running as daemon

### Google Calendar

Reads events from Google Calendar via OAuth2.

**Auth:** OAuth2 (readonly)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable google-calendar
mneia connector setup google-calendar   # OAuth2 flow opens browser
mneia connector sync google-calendar
```

**Features:**
- Fetches events from one or more calendars
- Extracts attendees, organizer, location, meeting links
- Supports configurable lookback period
- Detects recurring events and conference data

### Gmail

Reads emails from Gmail via OAuth2.

**Auth:** OAuth2 (readonly)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable gmail
mneia connector setup gmail
mneia connector sync gmail
```

**Features:**
- Fetches emails from specified labels (default: INBOX)
- Extracts sender, recipients, CC, subject, body
- Handles multipart emails (plain text and HTML)
- Supports Gmail search query filters
- Configurable max results per sync

### Google Drive

Reads files from Google Drive including Docs, Sheets, and Slides.

**Auth:** OAuth2 (readonly)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable google-drive
mneia connector setup google-drive
mneia connector sync google-drive
```

**Features:**
- Reads Google Docs (exported as plain text)
- Reads Google Sheets (exported as CSV)
- Reads Google Slides (exported as plain text)
- Reads plain text, markdown, CSV, HTML, and JSON files
- Supports folder ID filtering
- Includes shared drives
- Truncates large files (>50KB) to prevent memory issues

### Apple Notes

Reads notes from the macOS Apple Notes app via AppleScript.

**Auth:** AppleScript (macOS only)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable apple-notes
mneia connector setup apple-notes
mneia connector sync apple-notes
```

**Features:**
- Reads all notes via AppleScript
- Strips HTML formatting from note bodies
- Supports folder filtering
- Extracts modification dates and folder metadata

### Asana

Reads tasks and projects from Asana.

**Auth:** API token (Personal Access Token)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable asana
mneia connector setup asana
mneia connector sync asana
```

**Features:**
- Fetches tasks from specific projects or entire workspace
- Extracts assignee, due date, status, tags
- Supports modified_since filtering
- Auto-detects workspace if not specified

### JIRA

Reads issues from Atlassian JIRA.

**Auth:** API token (email + token)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable jira
mneia connector setup jira
mneia connector sync jira
```

**Features:**
- Fetches issues via JQL queries
- Extracts Atlassian Document Format (ADF) descriptions
- Includes last 5 comments per issue
- Extracts assignee, reporter, status, priority, labels

### Confluence

Reads pages from Atlassian Confluence.

**Auth:** API token (email + token)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable confluence
mneia connector setup confluence
mneia connector sync confluence
```

**Features:**
- Searches pages via CQL
- Strips HTML from storage format body
- Supports space key filtering
- Extracts page hierarchy (ancestors)

### Notion

Reads pages and databases from Notion.

**Auth:** Bearer token (Integration token)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable notion
mneia connector setup notion
mneia connector sync notion
```

**Features:**
- Fetches pages via search API with pagination
- Converts blocks to markdown (paragraphs, headings, lists, code, to-do, dividers)
- Supports database ID filtering
- Extracts page metadata, participants, parent info

### Zoom

Reads meeting recordings and transcripts from Zoom.

**Auth:** OAuth2 (Server-to-Server app)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable zoom
mneia connector setup zoom
mneia connector sync zoom
```

**Features:**
- Fetches meeting recordings list
- Downloads and parses VTT transcripts
- Extracts meeting topic, duration, host
- Supports date range filtering

### Chrome History

Reads browsing history and optionally scrapes page content from Google Chrome.

**Auth:** Local filesystem (read-only copy)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable chrome-history
mneia connector setup chrome-history
mneia connector sync chrome-history
```

**Features:**
- Copies Chrome history database (read-only, non-blocking)
- Extracts URLs, titles, visit counts
- Auto-detects Chrome profile path on macOS, Linux, Windows
- Supports custom history file path
- Optional page content scraping (opt-in via `scrape_content` setting)
- Configurable domain exclusion list for scraping
- Rate-limited scraping to avoid overloading sites

**Content scraping settings:**
| Setting | Default | Description |
|---------|---------|-------------|
| `scrape_content` | `false` | Enable page content scraping |
| `scrape_max_pages` | `20` | Max pages to scrape per sync |
| `scrape_domains_exclude` | (empty) | Comma-separated domains to skip |

### Audio Transcription

Transcribes audio files using whisper.cpp or faster-whisper.

**Auth:** Local filesystem
**Mode:** Poll
**Setup:**
```bash
pip install faster-whisper  # or: brew install whisper-cpp
mneia connector enable audio-transcription
mneia connector setup audio-transcription
mneia connector sync audio-transcription
```

**Features:**
- Supports MP3, WAV, M4A, OGG, FLAC, WebM, MP4
- Auto-detects backend (faster-whisper or whisper-cpp)
- Configurable model size (tiny/base/small/medium/large)
- Configurable language

### Live Audio

Captures system audio in real-time during meetings and transcribes using whisper.

**Auth:** Sounddevice (requires virtual audio device on macOS)
**Mode:** Watch (continuous recording)
**Setup:**
```bash
pip install mneia[audio]    # Installs sounddevice
mneia connector enable live-audio
mneia connector setup live-audio
```

**Features:**
- Records audio in 30-second chunks at 16kHz mono
- Real-time transcription via shared transcription engine
- Yields `live_transcript` documents with meeting metadata
- macOS: requires BlackHole virtual audio device
- Linux: uses PulseAudio monitor source
- Generates meeting_id for grouping chunks
- Requires HIGH-level safety permission

**Settings:**
| Setting | Default | Description |
|---------|---------|-------------|
| `device_index` | (auto) | Audio input device index |
| `model` | `base` | Whisper model size |
| `language` | `en` | Transcription language |

### Slack

Reads channel messages from Slack workspaces.

**Auth:** Bot token (with `channels:history`, `channels:read` scopes)
**Mode:** Poll
**Setup:**
```bash
mneia connector enable slack
mneia connector setup slack
mneia connector sync slack
```

**Features:**
- Fetches messages from configured channels
- Extracts message text, sender, timestamps
- Supports `since` filtering via checkpoint
- Rate-limited to 1 request/second

**Settings:**
| Setting | Default | Description |
|---------|---------|-------------|
| `slack_token` | (required) | Bot token (`xoxb-...`) |
| `channels` | (required) | Comma-separated channel names |

### GitHub

Reads issues and pull requests from GitHub repositories.

**Auth:** Personal Access Token
**Mode:** Poll
**Setup:**
```bash
mneia connector enable github
mneia connector setup github
mneia connector sync github
```

**Features:**
- Fetches open and closed issues
- Fetches pull requests with merge status
- Extracts labels, assignees, comments count
- Supports multiple repositories
- Incremental sync via `since` parameter

**Settings:**
| Setting | Default | Description |
|---------|---------|-------------|
| `github_token` | (required) | Personal Access Token |
| `repos` | (required) | Comma-separated `owner/repo` list |

### Linear

Reads issues and projects from Linear via GraphQL API.

**Auth:** API key
**Mode:** Poll
**Setup:**
```bash
mneia connector enable linear
mneia connector setup linear
mneia connector sync linear
```

**Features:**
- Fetches issues with state, priority, labels, team
- Priority mapping: 1=Urgent, 2=High, 3=Medium, 4=Low
- Optional team filtering
- Date-based incremental sync

**Settings:**
| Setting | Default | Description |
|---------|---------|-------------|
| `linear_api_key` | (required) | Linear API key |
| `team_ids` | (optional) | Comma-separated team IDs |

### Todoist

Reads tasks and projects from Todoist.

**Auth:** API token
**Mode:** Poll
**Setup:**
```bash
mneia connector enable todoist
mneia connector setup todoist
mneia connector sync todoist
```

**Features:**
- Fetches active tasks with project mapping
- Extracts priority, due dates, labels
- Maps project IDs to project names
- Supports incremental sync

**Settings:**
| Setting | Default | Description |
|---------|---------|-------------|
| `todoist_api_token` | (required) | Todoist API token |

## Connector Modes

Connectors operate in one of two modes:

| Mode | Description | Connectors |
|------|-------------|------------|
| **Poll** | Fetches data at configured intervals | Most connectors |
| **Watch** | Real-time event-based detection | Obsidian, Live Audio |

Watch mode uses `watchfiles` for filesystem events with 500ms debouncing and extension filtering. Poll mode uses configurable intervals (default: 300 seconds).

## Agent Management

Each enabled connector gets a `ListenerAgent` that runs inside the daemon. You can manage individual agents:

```bash
mneia connector start-agent obsidian   # Start obsidian's listener
mneia connector stop-agent obsidian    # Stop without stopping daemon
mneia connector agents                 # List running agents
```

In interactive mode:
```
/connector-start obsidian
/connector-stop obsidian
/agents
```

## Building Custom Connectors

Implement the `BaseConnector` interface:

```python
from mneia.core.connector import BaseConnector, ConnectorManifest, ConnectorMode, RawDocument

class MyConnector(BaseConnector):
    MANIFEST = ConnectorManifest(
        name="myservice",
        display_name="My Service",
        version="1.0.0",
        description="Read data from My Service",
        auth_type="api_key",
        mode=ConnectorMode.POLL,
        poll_interval_seconds=300,
    )

    async def authenticate(self, settings: dict) -> bool:
        # Validate credentials
        return True

    async def fetch(self, since: str | None = None) -> list[RawDocument]:
        # Fetch documents since checkpoint
        return [...]

    async def health_check(self) -> bool:
        return True

    def interactive_setup(self) -> dict:
        # Return settings dict from user input
        return {"api_key": "..."}
```

### Watch Mode Connectors

For real-time connectors, set `mode=ConnectorMode.WATCH` and implement `fetch_changed`:

```python
async def fetch_changed(self, changed_paths: list[Path]) -> list[RawDocument]:
    # Process only the changed files
    return [...]
```

### Publishing

Package as `mneia-connector-myservice` and register via entry points:

```toml
[project.entry-points."mneia.connectors"]
myservice = "mneia_connector_myservice:MyConnector"
```

Users install with:
```bash
pip install mneia-connector-myservice
```

The connector is automatically discovered on next startup.
